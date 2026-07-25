"""Batch commentary generation workflow (AGENT_SPEC §6, CLAUDE.md §7).

R11 B1 — versions are PER-ADVISOR. Each advisor's run creates its own NEW
phx_dm_v2_commentary_version (advisor_sid stamped on the version), generates
commentary + evidence for that advisor's transitions, persists everything
attached to that version, publishes it and marks the advisor's prior PUBLISHED
version(s) SUPERSEDED — other advisors' versions are untouched. "Regenerate
all" iterates every advisor, each getting its OWN version (never a global
blob). Legacy pre-R11 global versions carry advisor_sid = "" and are
superseded only by a regenerate-all (every advisor then has a newer scoped
version). Previous versions are never deleted. Page loads retrieve; they never
reach this module.

R11 C1 — the workflow runs ASYNC from the API: start_generation() spawns a
daemon thread and returns a job id immediately; get_status() reports
state / phase / advisor N of M and, on completion, the new version ids. The
job keeps running if the browser closes. The synchronous run_generation()
remains the CLI entry point.

Persistence is dual: upsert through the active graph client (tier 1 on the
client machine, local store here) AND appended to the data-set CSVs, so stored
commentary survives a local-mode restart and reloads with the manifest.
"""
from __future__ import annotations

import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.agents.nodes.commentary_agent import PROMPT_VERSION
from app.agents.nodes.supervisor_agent import SupervisorAgent
from app.config.settings import get_settings
from app.graph.client import get_graph_client
from app.v2.dataset.builder import csv_file_for
from app.graph.queries.common import COMMENTARY_VERSION
from app.ingestion.tigergraph_upsert import TigerGraphUpsertClient
from app.shared.logging import get_logger
from app.v2.commentary import judge as judge_mod

_log = get_logger("app.v2.commentary")
_lock = threading.Lock()
_status: dict = {"state": "idle"}


def _csv_append(file_rel: str, rows: list[dict]) -> None:
    """Append rows to a data-set CSV (header written by the generator)."""
    if not rows:
        return
    path = get_settings().resolved_data_set_dir / file_rel
    header = _csv_header(path)  # header written by the sample generator
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        for r in rows:
            writer.writerow(r)


def _csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f))


def _persist(upsert: TigerGraphUpsertClient, entity: str, kind: str,
             file_rel: str, rows: list[dict], id_column: str = "") -> None:
    if not rows:
        return
    if kind == "vertex":
        upsert.upsert_vertex_rows(f"phx_dm_v2_{entity}", rows, id_column)
    else:
        upsert.upsert_edge_rows(f"phx_dm_v2_{entity}", rows)
    _csv_append(file_rel, rows)


def get_status() -> dict:
    with _lock:
        return dict(_status)


def _set_status(**fields) -> None:
    with _lock:
        _status.update(fields)


def _latest_version_no(graph) -> int:
    """Global max version_no — version ids stay globally unique (R11 decision:
    per-advisor SCOPE via advisor_sid, one shared version_no sequence so ids
    never collide and history stays totally ordered)."""
    result = graph.run_query("get_commentary_versions", {})
    versions = []
    for obj in result.get("results", []):
        versions = [r.get("attributes", {}) for r in obj.get("versions", [])]
    return max((int(v.get("version_no") or 0) for v in versions), default=0)


def start_generation(notes: str = "", advisor_id: str = "") -> dict:
    """R11 C1 — async entry point for the API. Reserves the single job slot,
    spawns a daemon thread (the job survives the browser closing) and returns
    the job id immediately. A POST while a job runs returns that job's id and
    NEVER starts a second run (C3: polling must not re-trigger)."""
    with _lock:
        if _status.get("state") in ("starting", "running"):
            return {"already_running": True, "job_id": _status.get("job_id"),
                    "state": _status.get("state")}
        job_id = "gen-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        _status.clear()
        _status.update({"state": "starting", "job_id": job_id, "kind": "commentary",
                        "scope": advisor_id or "ALL",
                        "started_at": datetime.now(timezone.utc).isoformat()})
    threading.Thread(target=_run_job, args=(job_id, notes, advisor_id),
                     daemon=True, name=f"commentary-{job_id}").start()
    return {"started": True, "job_id": job_id, "state": "starting",
            "scope": advisor_id or "ALL"}


def _run_job(job_id: str, notes: str, advisor_id: str) -> None:
    _set_status(state="running")
    try:
        summary = _run(notes, advisor_id)
        _set_status(state="completed", summary=summary, phase="done",
                    finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:  # noqa: BLE001 — recorded and surfaced, never hidden
        _log.error("commentary generation failed: %s", exc, exc_info=True)
        _set_status(state="failed", error=str(exc),
                    finished_at=datetime.now(timezone.utc).isoformat())


def run_generation(notes: str = "", advisor_id: str = "") -> dict:
    """Synchronous batch run (CLI / verification). advisor_id = "" runs every
    advisor; each advisor still gets its OWN per-advisor version (R11 B3)."""
    with _lock:
        if _status.get("state") in ("starting", "running"):
            return {"error": True, "message": "generation already running",
                    "job_id": _status.get("job_id")}
        _status.clear()
        _status.update({"state": "running", "kind": "commentary",
                        "scope": advisor_id or "ALL",
                        "started_at": datetime.now(timezone.utc).isoformat()})

    try:
        summary = _run(notes, advisor_id)
        with _lock:
            _status.update({"state": "completed", "summary": summary,
                            "finished_at": datetime.now(timezone.utc).isoformat()})
        return summary
    except Exception as exc:  # noqa: BLE001 — recorded and surfaced, never hidden
        _log.error("commentary generation failed: %s", exc, exc_info=True)
        with _lock:
            _status.update({"state": "failed", "error": str(exc)})
        raise


def _run(notes: str = "", advisor_id: str = "") -> dict:
    """R11 B — one PER-ADVISOR version per advisor in scope. advisor_id = ""
    (Regenerate all) iterates every advisor serially — serial keeps the
    "advisor N of M" progress honest and each advisor's version independent."""
    graph = get_graph_client()
    upsert = TigerGraphUpsertClient()
    supervisor = SupervisorAgent()
    settings = get_settings()

    # Advisors + transitions from the graph.
    all_advisors = [r.get("attributes", {}).get("advisor_sid")
                    for r in graph.run_query("get_advisors", {})["results"][0]["advisors"]]
    if advisor_id:
        if advisor_id not in all_advisors:
            raise ValueError(f"unknown advisor_sid {advisor_id!r}")
        advisors = [advisor_id]
    else:
        advisors = all_advisors
    months_rows = [r.get("attributes", {})
                   for r in graph.run_query("get_months", {})["results"][0]["months"]]
    month_ids = sorted(str(m.get("month_id")) for m in months_rows)
    transitions = list(zip(month_ids, month_ids[1:]))
    # Version-row model label (metadata only). R12 — when WRITER_* config is
    # set, the label names the writer's effective model; unconfigured keeps
    # the pre-R12 label exactly.
    from app.llm.roles import resolve_role_config
    wcfg = resolve_role_config("writer", settings)
    if wcfg.configured:
        model = f"{wcfg.mode}:{wcfg.deployment or wcfg.model or wcfg.default_model_label()}"
    else:
        model = (settings.anthropic_model if settings.llm_client_mode == "claude"
                 else settings.llm_client_mode)
    judge_llm = judge_mod.get_judge_llm() if settings.judge_enabled else None

    per_version: list[dict] = []
    for idx, advisor in enumerate(advisors, start=1):
        _set_status(phase="generating commentary", advisor_current=advisor,
                    advisor_index=idx, advisor_total=len(advisors))
        per_version.append(_run_for_advisor(
            advisor, transitions, notes, graph, upsert, supervisor,
            settings, model, judge_llm))
        _set_status(versions=[s["version_id"] for s in per_version])

    if not advisor_id:
        # Regenerate-all: every advisor now has a newer per-advisor version, so
        # legacy pre-R11 GLOBAL versions (advisor_sid = "") are superseded.
        # A single-advisor run leaves them PUBLISHED — other advisors still
        # resolve to them.
        _supersede_global_versions(upsert, settings)

    summary = {
        "scope": advisor_id or "ALL",
        "advisors": len(advisors),
        "versions": per_version,
        "version_ids": [s["version_id"] for s in per_version],
        "transitions": sum(s["transitions"] for s in per_version),
        "published": sum(s["published"] for s in per_version),
        "published_fallback": sum(s["published_fallback"] for s in per_version),
        "blocked": sum(s["blocked"] for s in per_version),
        "evidence_records": sum(s["evidence_records"] for s in per_version),
        "judge": {k: sum(s["judge"][k] for s in per_version)
                  for k in ("pass", "review", "fail")},
    }
    _log.info("commentary generation complete: %s", summary)
    return summary


def _run_for_advisor(advisor_sid: str, transitions: list[tuple[str, str]],
                     notes: str, graph, upsert: TigerGraphUpsertClient,
                     supervisor, settings, model: str, judge_llm) -> dict:
    """Generate + persist + publish ONE advisor's version (R11 B1). Supersedes
    only THIS advisor's prior PUBLISHED versions."""
    prior_no = _latest_version_no(graph)
    version_no = prior_no + 1
    version_id = f"v{version_no}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    version_row = {
        "version_id": version_id, "version_no": version_no,
        "advisor_sid": advisor_sid,
        "generated_at": generated_at, "model": model,
        "prompt_version": PROMPT_VERSION, "data_snapshot_dt": generated_at,
        "status": "DRAFT", "advisor_count": 1,
        "transition_count": len(transitions),
        "blocked_count": 0, "notes": notes, "data_source": "DERIVED",
    }
    upsert.upsert_vertex_rows("phx_dm_v2_commentary_version", [version_row], "version_id")

    per_advisor = [[]]
    for from_m, to_m in transitions:  # serial within an advisor
        _set_status(phase=f"generating {from_m}→{to_m}")
        state = supervisor.run_generation_sequence(advisor_sid, from_m, to_m, version_id)
        per_advisor[0].append({"advisor_id": advisor_sid, "from_month": from_m,
                               "to_month": to_m, "state": state})

    blocked = 0
    commentary_rows, evidence_rows = [], []
    e_cfa, e_cfm, e_ctm, e_civ, e_ccd, e_efd = [], [], [], [], [], []
    # LLM-as-judge (FIX_SPEC R5). ADVISORY ONLY — verdicts are persisted for
    # human attention and never publish or suppress a commentary.
    evaluation_rows, e_eoc = [], []

    def run_judge(commentary_id: str, revenue_output: dict, commentary: dict) -> None:
        """Judge one transition (after guardrails). Skips when there is no
        narrative to judge; BLOCKED transitions with text are judged too."""
        if not settings.judge_enabled or not (commentary.get("narrative_text") or "").strip():
            return
        evaluation = judge_mod.judge_commentary(revenue_output, commentary, judge_llm)
        evaluation_id = f"{commentary_id}|j1"
        evaluation_rows.append({
            "evaluation_id": evaluation_id,
            "commentary_id": commentary_id,
            "version_id": version_id,
            "judge_model": evaluation["judge_model"],
            "faithfulness_score": evaluation["faithfulness_score"],
            "hallucination_flag": evaluation["hallucination_flag"],
            "completeness_score": evaluation["completeness_score"],
            "clarity_score": evaluation["clarity_score"],
            "verdict": evaluation["verdict"],
            "reasoning": evaluation["reasoning"],
            "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "data_source": "DERIVED",
        })
        e_eoc.append({"from_id": evaluation_id, "to_id": commentary_id})

    for advisor_results in per_advisor:
        for item in advisor_results:
            state = item["state"]
            advisor_id, from_m, to_m = item["advisor_id"], item["from_month"], item["to_month"]
            commentary_id = f"{version_id}|{advisor_id}|{from_m}|{to_m}"
            if state.errors:
                blocked += 1
                commentary_rows.append({
                    "commentary_id": commentary_id, "version_id": version_id,
                    "advisor_sid": advisor_id, "from_month_id": from_m, "to_month_id": to_m,
                    "headline": "", "narrative_text": "", "bullets_json": "[]",
                    "status": "BLOCKED", "blocked_reason": "; ".join(state.errors)[:500],
                    "data_source": "DERIVED",
                })
                e_cfa.append({"from_id": commentary_id, "to_id": advisor_id})
                e_cfm.append({"from_id": commentary_id, "to_id": from_m})
                e_ctm.append({"from_id": commentary_id, "to_id": to_m})
                e_civ.append({"from_id": commentary_id, "to_id": version_id})
                continue
            commentary = state.context["commentary"]
            validation = state.context["validation"]
            evidence = state.context.get("evidence", [])
            fallback_reason = str(state.context.get("fallback_reason") or "")
            # R9 D — three outcomes: PUBLISHED (model wording passed),
            # PUBLISHED_FALLBACK (model wording failed COMMENTARY_MAX_ATTEMPTS
            # times; the validated deterministic template publishes, clearly
            # marked — the panel is never empty), BLOCKED (even the
            # deterministic template failed — should never happen).
            if validation["passed"]:
                status = "PUBLISHED_FALLBACK" if fallback_reason else "PUBLISHED"
            else:
                status = "BLOCKED"
                blocked += 1
                _log.warning("commentary BLOCKED for %s %s->%s: %s",
                             advisor_id, from_m, to_m, validation["blocked_reason"])
            commentary_rows.append({
                "commentary_id": commentary_id, "version_id": version_id,
                "advisor_sid": advisor_id, "from_month_id": from_m, "to_month_id": to_m,
                "headline": commentary["headline"],
                "narrative_text": commentary["narrative_text"],
                "bullets_json": json.dumps(commentary["bullets"], sort_keys=True),
                "status": status,
                "blocked_reason": (fallback_reason if status == "PUBLISHED_FALLBACK"
                                   else validation["blocked_reason"] or ""),
                "data_source": "DERIVED",
            })
            e_cfa.append({"from_id": commentary_id, "to_id": advisor_id})
            e_cfm.append({"from_id": commentary_id, "to_id": from_m})
            e_ctm.append({"from_id": commentary_id, "to_id": to_m})
            e_civ.append({"from_id": commentary_id, "to_id": version_id})
            for b in commentary["bullets"]:
                e_ccd.append({"from_id": commentary_id, "to_id": b["driver_id"]})
            # R5-2: judge runs AFTER guardrails validation — BLOCKED transitions
            # with a narrative are judged too (diagnostic value).
            run_judge(commentary_id, state.context["revenue_output"], commentary)
            # Evidence persists even for blocked transitions (diagnostic value);
            # publication of the COMMENTARY is what the gate controls.
            for e in evidence:
                evidence_rows.append(e)
                e_efd.append({"from_id": e["evidence_id"], "to_id": e["driver_id"]})

    _set_status(phase="persisting")
    upsert_client = upsert
    _persist(upsert_client, "commentary", "vertex", csv_file_for("vertex", "commentary"),
             commentary_rows, "commentary_id")
    _persist(upsert_client, "evidence", "vertex", csv_file_for("vertex", "evidence"),
             evidence_rows, "evidence_id")
    _persist(upsert_client, "commentary_for_advisor", "edge", csv_file_for("edge", "commentary_for_advisor"), e_cfa)
    _persist(upsert_client, "commentary_from_month", "edge", csv_file_for("edge", "commentary_from_month"), e_cfm)
    _persist(upsert_client, "commentary_to_month", "edge", csv_file_for("edge", "commentary_to_month"), e_ctm)
    _persist(upsert_client, "commentary_in_version", "edge", csv_file_for("edge", "commentary_in_version"), e_civ)
    _persist(upsert_client, "commentary_cites_driver", "edge", csv_file_for("edge", "commentary_cites_driver"), e_ccd)
    _persist(upsert_client, "evidence_for_driver", "edge", csv_file_for("edge", "evidence_for_driver"), e_efd)
    _persist(upsert_client, "commentary_evaluation", "vertex",
             csv_file_for("vertex", "commentary_evaluation"), evaluation_rows, "evaluation_id")
    _persist(upsert_client, "evaluation_of_commentary", "edge",
             csv_file_for("edge", "evaluation_of_commentary"), e_eoc)

    # Publish this version; supersede THIS ADVISOR's prior PUBLISHED versions
    # (R11 B1 — supersede applies WITHIN an advisor; never delete, never touch
    # another advisor's versions or the legacy global ones).
    version_row.update({"status": "PUBLISHED", "blocked_count": blocked})
    upsert.upsert_vertex_rows("phx_dm_v2_commentary_version", [version_row], "version_id")
    graph = get_graph_client()
    store = getattr(graph, "store", None)
    if store is not None:
        for vid, attrs in store.all_vertices(COMMENTARY_VERSION).items():
            if (vid != version_id and attrs.get("status") == "PUBLISHED"
                    and str(attrs.get("advisor_sid") or "") == advisor_sid):
                upsert.upsert_vertex_rows(
                    "phx_dm_v2_commentary_version",
                    [{**attrs, "version_id": vid, "status": "SUPERSEDED"}], "version_id")
    # The version CSV is REWRITTEN (not appended): supersede is a status update
    # on existing rows, and append-only would resurrect PUBLISHED on reload.
    _rewrite_version_csv(settings, version_row,
                         supersede=lambda row: str(row.get("advisor_sid") or "") == advisor_sid)

    return {
        "version_id": version_id, "version_no": version_no,
        "advisor_sid": advisor_sid, "model": model,
        "prompt_version": PROMPT_VERSION, "generated_at": generated_at,
        "transitions": len(transitions),
        "published": sum(1 for c in commentary_rows if c["status"] == "PUBLISHED"),
        # R9 D — deterministic template published after the model's wording
        # failed COMMENTARY_MAX_ATTEMPTS validations (panel never empty).
        "published_fallback": sum(1 for c in commentary_rows
                                  if c["status"] == "PUBLISHED_FALLBACK"),
        "blocked": blocked, "evidence_records": len(evidence_rows),
        # Advisory judge tally (R5) — informational only, never a gate.
        "judge": {
            "pass": sum(1 for e in evaluation_rows if e["verdict"] == "PASS"),
            "review": sum(1 for e in evaluation_rows if e["verdict"] == "REVIEW"),
            "fail": sum(1 for e in evaluation_rows if e["verdict"] == "FAIL"),
        },
    }


def _rewrite_version_csv(settings, new_row: dict | None,
                         supersede) -> None:
    """Rewrite the commentary_version CSV: PUBLISHED rows matching the
    supersede predicate become SUPERSEDED; new_row (if any) is appended."""
    path = settings.resolved_data_set_dir / csv_file_for("vertex", "commentary_version")
    header = _csv_header(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        existing = list(csv.DictReader(f))
    for row in existing:
        if row.get("status") == "PUBLISHED" and supersede(row):
            row["status"] = "SUPERSEDED"
    if new_row is not None:
        existing.append({k: new_row.get(k, "") for k in header})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(existing)


def _supersede_global_versions(upsert: TigerGraphUpsertClient, settings) -> None:
    """After a regenerate-ALL, legacy global versions (advisor_sid = "") are
    superseded — every advisor now resolves to a newer per-advisor version."""
    graph = get_graph_client()
    store = getattr(graph, "store", None)
    if store is not None:
        for vid, attrs in store.all_vertices(COMMENTARY_VERSION).items():
            if attrs.get("status") == "PUBLISHED" and not str(attrs.get("advisor_sid") or ""):
                upsert.upsert_vertex_rows(
                    "phx_dm_v2_commentary_version",
                    [{**attrs, "version_id": vid, "status": "SUPERSEDED"}], "version_id")
    _rewrite_version_csv(settings, None,
                         supersede=lambda row: not str(row.get("advisor_sid") or ""))


if __name__ == "__main__":  # pragma: no cover
    # FIX_SPEC_R4 B5.7 — headless CLI equivalent of the Regenerate button for
    # client environments without a browser:
    #     python -m app.v2.commentary.generation_workflow [--notes "..."]
    # Identical pipeline and gates; creates a new version, never deletes prior.
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Batch commentary generation (same as the UI Regenerate buttons)")
    parser.add_argument("--notes", default="", help="free-text note stored on the version")
    parser.add_argument("--advisor", default="",
                        help="R11 B — advisor_sid to regenerate (default: all advisors, "
                             "each getting its OWN per-advisor version)")
    args = parser.parse_args()
    result = run_generation(args.notes, args.advisor)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result.get("error") else 0)
