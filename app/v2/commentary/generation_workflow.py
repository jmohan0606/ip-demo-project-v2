"""Batch commentary generation workflow (AGENT_SPEC §6, CLAUDE.md §7).

Each run creates a NEW phx_dm_v2_commentary_version, generates commentary +
evidence for every advisor × transition (parallel across advisors, serial
within one), persists everything attached to that version, publishes it and
marks the prior PUBLISHED version SUPERSEDED. Previous versions are never
deleted. Page loads retrieve; they never reach this module.

Persistence is dual: upsert through the active graph client (tier 1 on the
client machine, local store here) AND appended to the data-set CSVs, so stored
commentary survives a local-mode restart and reloads with the manifest.
"""
from __future__ import annotations

import csv
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.agents.nodes.commentary_agent import PROMPT_VERSION
from app.agents.nodes.supervisor_agent import SupervisorAgent
from app.config.settings import get_settings
from app.graph.client import get_graph_client
from app.graph.queries.common import COMMENTARY_VERSION
from app.ingestion.tigergraph_upsert import TigerGraphUpsertClient
from app.shared.logging import get_logger

_log = get_logger("app.v2.commentary")
_lock = threading.Lock()
_status: dict = {"state": "idle"}


def _csv_append(file_rel: str, rows: list[dict]) -> None:
    """Append rows to a data-set CSV (header written by the generator)."""
    if not rows:
        return
    path = Path("data") / get_settings().data_set / file_rel
    header = _csv_header(path)  # header written by the sample generator
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        for r in rows:
            writer.writerow(r)


def _csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as f:
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


def _latest_version_no(graph) -> int:
    result = graph.run_query("get_commentary_versions", {})
    versions = []
    for obj in result.get("results", []):
        versions = [r.get("attributes", {}) for r in obj.get("versions", [])]
    return max((int(v.get("version_no") or 0) for v in versions), default=0)


def run_generation(notes: str = "") -> dict:
    """Synchronous batch run (small advisor set). Returns the version summary."""
    with _lock:
        if _status.get("state") == "running":
            return {"error": True, "message": "generation already running"}
        _status.update({"state": "running", "started_at": datetime.now(timezone.utc).isoformat()})

    try:
        summary = _run(notes)
        with _lock:
            _status.update({"state": "completed", "summary": summary,
                            "finished_at": datetime.now(timezone.utc).isoformat()})
        return summary
    except Exception as exc:  # noqa: BLE001 — recorded and surfaced, never hidden
        _log.error("commentary generation failed: %s", exc, exc_info=True)
        with _lock:
            _status.update({"state": "failed", "error": str(exc)})
        raise


def _run(notes: str = "") -> dict:
    graph = get_graph_client()
    upsert = TigerGraphUpsertClient()
    supervisor = SupervisorAgent()
    settings = get_settings()

    # Advisors + transitions from the graph.
    advisors = [r.get("attributes", {}).get("advisor_sid")
                for r in graph.run_query("get_advisors", {})["results"][0]["advisors"]]
    months_rows = [r.get("attributes", {})
                   for r in graph.run_query("get_months", {})["results"][0]["months"]]
    month_ids = sorted(str(m.get("month_id")) for m in months_rows)
    transitions = list(zip(month_ids, month_ids[1:]))

    prior_no = _latest_version_no(graph)
    version_no = prior_no + 1
    version_id = f"v{version_no}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    model = (settings.anthropic_model if settings.llm_client_mode == "claude"
             else settings.llm_client_mode)

    version_row = {
        "version_id": version_id, "version_no": version_no,
        "generated_at": generated_at, "model": model,
        "prompt_version": PROMPT_VERSION, "data_snapshot_dt": generated_at,
        "status": "DRAFT", "advisor_count": len(advisors),
        "transition_count": len(advisors) * len(transitions),
        "blocked_count": 0, "notes": notes, "data_source": "DERIVED",
    }
    upsert.upsert_vertex_rows("phx_dm_v2_commentary_version", [version_row], "version_id")

    def generate_for_advisor(advisor_id: str) -> list[dict]:
        results = []
        for from_m, to_m in transitions:  # serial within an advisor
            state = supervisor.run_generation_sequence(advisor_id, from_m, to_m, version_id)
            results.append({"advisor_id": advisor_id, "from_month": from_m,
                            "to_month": to_m, "state": state})
        return results

    with ThreadPoolExecutor(max_workers=min(4, len(advisors) or 1)) as pool:
        per_advisor = list(pool.map(generate_for_advisor, advisors))

    blocked = 0
    commentary_rows, evidence_rows = [], []
    e_cfa, e_cfm, e_ctm, e_civ, e_ccd, e_efd = [], [], [], [], [], []

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
            status = "PUBLISHED" if validation["passed"] else "BLOCKED"
            if status == "BLOCKED":
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
                "blocked_reason": validation["blocked_reason"] or "",
                "data_source": "DERIVED",
            })
            e_cfa.append({"from_id": commentary_id, "to_id": advisor_id})
            e_cfm.append({"from_id": commentary_id, "to_id": from_m})
            e_ctm.append({"from_id": commentary_id, "to_id": to_m})
            e_civ.append({"from_id": commentary_id, "to_id": version_id})
            for b in commentary["bullets"]:
                e_ccd.append({"from_id": commentary_id, "to_id": b["driver_id"]})
            # Evidence persists even for blocked transitions (diagnostic value);
            # publication of the COMMENTARY is what the gate controls.
            for e in evidence:
                evidence_rows.append(e)
                e_efd.append({"from_id": e["evidence_id"], "to_id": e["driver_id"]})

    upsert_client = upsert
    _persist(upsert_client, "commentary", "vertex", "vertices/commentary.csv",
             commentary_rows, "commentary_id")
    _persist(upsert_client, "evidence", "vertex", "vertices/evidence.csv",
             evidence_rows, "evidence_id")
    _persist(upsert_client, "commentary_for_advisor", "edge", "edges/commentary_for_advisor.csv", e_cfa)
    _persist(upsert_client, "commentary_from_month", "edge", "edges/commentary_from_month.csv", e_cfm)
    _persist(upsert_client, "commentary_to_month", "edge", "edges/commentary_to_month.csv", e_ctm)
    _persist(upsert_client, "commentary_in_version", "edge", "edges/commentary_in_version.csv", e_civ)
    _persist(upsert_client, "commentary_cites_driver", "edge", "edges/commentary_cites_driver.csv", e_ccd)
    _persist(upsert_client, "evidence_for_driver", "edge", "edges/evidence_for_driver.csv", e_efd)

    # Publish this version; supersede prior PUBLISHED versions (never delete).
    version_row.update({"status": "PUBLISHED", "blocked_count": blocked})
    upsert.upsert_vertex_rows("phx_dm_v2_commentary_version", [version_row], "version_id")
    graph = get_graph_client()
    store = getattr(graph, "store", None)
    if store is not None:
        for vid, attrs in store.all_vertices(COMMENTARY_VERSION).items():
            if vid != version_id and attrs.get("status") == "PUBLISHED":
                upsert.upsert_vertex_rows(
                    "phx_dm_v2_commentary_version",
                    [{**attrs, "version_id": vid, "status": "SUPERSEDED"}], "version_id")
    # The version CSV is REWRITTEN (not appended): supersede is a status update
    # on existing rows, and append-only would resurrect PUBLISHED on reload.
    path = Path("data") / settings.data_set / "vertices" / "commentary_version.csv"
    header = _csv_header(path)
    with path.open(encoding="utf-8") as f:
        existing = list(csv.DictReader(f))
    for row in existing:
        if row.get("status") == "PUBLISHED":
            row["status"] = "SUPERSEDED"
    existing.append({k: version_row.get(k, "") for k in header})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing)

    summary = {
        "version_id": version_id, "version_no": version_no, "model": model,
        "prompt_version": PROMPT_VERSION, "generated_at": generated_at,
        "advisors": len(advisors), "transitions": len(advisors) * len(transitions),
        "published": sum(1 for c in commentary_rows if c["status"] == "PUBLISHED"),
        "blocked": blocked, "evidence_records": len(evidence_rows),
    }
    _log.info("commentary generation complete: %s", summary)
    return summary
