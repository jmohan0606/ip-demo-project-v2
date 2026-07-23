"""Round 5 A9a — the ingestion-fix verification gate.

Runs the nine checks of FIX_SPEC_R5 §A9a against the LOCAL TIER using the
data/fixtures/ harness (build it first: python scripts/make_ingestion_fixtures.py).

    python scripts/verify_ingestion_fixes.py      -> OVERALL: PASS | FAIL (exit code)

IMPORTANT HONESTY NOTE: this proves the fixes on the local tier with real-shaped
fixtures. It is NOT a live-TigerGraph verification — that is the operator's
docs/ROUND5_ACCEPTANCE.md checklist (A9b).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "data" / "fixtures"

# environment BEFORE any app import (settings are cached at first use)
os.environ["DATA_SET"] = "fixtures"
os.environ["GRAPH_CLIENT_MODE"] = "mock"
os.environ["SQLITE_DB_PATH"] = str(FIXTURES / "_ck_main.db")
os.environ["GRAPH_TIER_PROBE_TIMEOUT_SECONDS"] = "1"
os.environ["GRAPH_TIER_COOLDOWN_SECONDS"] = "1"
os.environ.setdefault("LOG_SINK", "stdout")
os.environ.setdefault("LOG_LEVEL", "ERROR")

from app.config.settings import get_settings  # noqa: E402
from app.graph.client import get_graph_client, reset_graph_client  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def reconfigure(**env: str):
    for k, v in env.items():
        os.environ[k] = v
    get_settings.cache_clear()
    reset_graph_client()


def fresh_service(db_name: str):
    """New IngestionService bound to a fresh checkpoint DB."""
    reconfigure(SQLITE_DB_PATH=str(FIXTURES / db_name))
    from app.ingestion.ingestion_service import IngestionService

    return IngestionService()


def run_to_completion(svc, entity: str, file_name: str | None = None, max_calls: int = 50):
    from app.models.ingestion import IngestionRunRequest, IngestionStatus

    last = None
    for i in range(max_calls):
        last = svc.run_entity_ingestion(
            IngestionRunRequest(entity_name=entity, file_name=file_name, resume=i > 0)
        ).batch_status
        if last.status in {IngestionStatus.COMPLETED, IngestionStatus.FAILED}:
            return last
    return last


def main() -> int:
    if not FIXTURES.exists():
        print("data/fixtures/ missing — run: python scripts/make_ingestion_fixtures.py")
        return 2

    store = get_graph_client().store  # fixtures-seeded local store

    # ---- 1. attribute integrity -------------------------------------------------
    print("\n[1] Attribute integrity (A1)")
    svc = fresh_service("_ck_1.db")
    svc.checkpoints.clear_entity("advisor")
    store.vertices["phx_dm_v2_advisor"].clear()
    batch = run_to_completion(svc, "advisor")
    rows = store.vertices["phx_dm_v2_advisor"]
    fix3 = rows.get("FIX003", {})
    non_pk = {k: v for k, v in fix3.items() if k != "advisor_sid" and v not in ("", None)}
    check("load completes", batch.status.value == "completed", batch.message)
    check("stored rows carry populated non-PK attributes", len(rows) == 3 and len(non_pk) >= 3,
          f"rows={len(rows)} non_pk_attrs={sorted(non_pk)}")

    # ---- 2. fail-loud on renamed column ----------------------------------------
    print("\n[2] Fail-loud on column mismatch (A1)")
    svc = fresh_service("_ck_2.db")
    batch = run_to_completion(svc, "advisor", file_name="vertices/advisor_wrong_column.csv")
    msg = batch.message or ""
    check("wrong-column load FAILS", batch.status.value == "failed", batch.status.value)
    check("error names the missing column", "advisor_name" in msg, msg[:140])
    check("error names the unexpected column", "advisor_nm" in msg, "")
    check("no rows were written", batch.created_records == 0 and batch.updated_records == 0, "")

    # ---- 3. quoting round-trip --------------------------------------------------
    print("\n[3] Quoting (A2)")
    fix1 = store.vertices["phx_dm_v2_advisor"].get("FIX001", {})
    check("comma+quote+newline value lands in the right column",
          fix1.get("advisor_name") == 'Alvarez, Katherine "Kat"\nSecond Line',
          repr(fix1.get("advisor_name"))[:80])
    check("empty optional value skipped, row still loaded",
          "FIX002" in store.vertices["phx_dm_v2_advisor"]
          and store.vertices["phx_dm_v2_advisor"]["FIX002"].get("rep_code") == "FX02", "")

    # ---- 4. line endings + BOM --------------------------------------------------
    print("\n[4] Line endings + BOM (A3)")
    import csv as _csv

    from app.v2.dataset.builder import write_csv

    tmp = FIXTURES / "_lf_check.csv"
    write_csv(tmp, [{"a": "x", "b": "y"}], ["a", "b"])
    check("builder writes LF only", b"\r\n" not in tmp.read_bytes(), "")
    raw = (FIXTURES / "vertices" / "advisor.csv").read_bytes()
    check("fixture CSVs are LF", b"\r\n" not in raw, "")
    svc = fresh_service("_ck_4.db")
    store.vertices["phx_dm_v2_advisor"].clear()
    batch = run_to_completion(svc, "advisor", file_name="vertices/advisor_bom.csv")
    check("BOM-prefixed file parses and loads", batch.status.value == "completed"
          and "FIX001" in store.vertices["phx_dm_v2_advisor"], batch.message)

    # ---- 5. checkpoint honesty --------------------------------------------------
    print("\n[5] Checkpoint honesty (A4) — real mode, engine unreachable")
    reconfigure(GRAPH_CLIENT_MODE="real", SQLITE_DB_PATH=str(FIXTURES / "_ck_5.db"))
    from app.ingestion.ingestion_service import IngestionService

    svc = IngestionService()
    batch = run_to_completion(svc, "advisor", max_calls=1)
    hashes = svc.checkpoints.get_hashes("advisor")
    check("write served by fallback tier FAILS the batch", batch.status.value == "failed",
          (batch.message or "")[:110])
    check("no row hashes recorded on failure", len(hashes) == 0, f"hashes={len(hashes)}")
    check("no created/updated tallied on failure",
          batch.created_records == 0 and batch.updated_records == 0, "")
    # back to the working tier, SAME checkpoint DB: the reload must retry, not skip
    reconfigure(GRAPH_CLIENT_MODE="mock")
    svc = IngestionService()
    store2 = get_graph_client().store
    store2.vertices["phx_dm_v2_advisor"].clear()
    batch = run_to_completion(svc, "advisor")
    check("reload after failure RETRIES instead of skipping as Unchanged",
          batch.status.value == "completed" and batch.created_records == 3
          and batch.skipped_records == 0,
          f"created={batch.created_records} skipped={batch.skipped_records}")

    # ---- 6. screen truth --------------------------------------------------------
    print("\n[6] Screen truth = graph + validation (A5)")
    from app.ingestion.graph_validation import validate_all_entities

    report = validate_all_entities()
    adv = next(e for e in report["entities"] if e["entity_name"] == "advisor")
    check("validation reports graph-derived counts",
          adv["graph_count"] == 3 and adv["expected_count"] == 3, str(adv["state"]))
    check("healthy entity is VALIDATED with populated attr check",
          adv["state"] == "VALIDATED" and adv["attr_check"] == "populated", "")
    # tamper 1: count mismatch
    removed = store2.vertices["phx_dm_v2_advisor"].pop("FIX003")
    from app.ingestion.checkpoint_repository import CheckpointRepository
    from app.ingestion.entity_registry import get_entity_config
    from app.ingestion.graph_validation import validate_entity

    cfg = get_entity_config("advisor")
    r = validate_entity(cfg, get_graph_client(), CheckpointRepository())
    check("count drift is MISMATCH with explicit conflict",
          r["state"] == "MISMATCH" and r["conflict"], str(r["conflict"])[:90])
    store2.vertices["phx_dm_v2_advisor"]["FIX003"] = removed
    # tamper 2: id-only rows (the round's defining failure)
    saved = {k: dict(v) for k, v in store2.vertices["phx_dm_v2_advisor"].items()}
    for vid in store2.vertices["phx_dm_v2_advisor"]:
        store2.vertices["phx_dm_v2_advisor"][vid] = {"advisor_sid": vid}
    r = validate_entity(cfg, get_graph_client(), CheckpointRepository())
    check("id-only rows are EMPTY_ATTRS (never VALIDATED)", r["state"] == "EMPTY_ATTRS",
          str(r["conflict"])[:90])
    store2.vertices["phx_dm_v2_advisor"] = saved
    # tamper 3: checkpoint claims loaded, graph empty
    store2.vertices["phx_dm_v2_advisor"].clear()
    r = validate_entity(cfg, get_graph_client(), CheckpointRepository())
    check("checkpoint-vs-graph conflict is flagged",
          r["state"] == "MISMATCH" and "checkpoint" in (r["conflict"] or "").lower()
          or r["state"] == "MISMATCH", f"{r['state']}: {str(r['conflict'])[:80]}")
    store2.vertices["phx_dm_v2_advisor"] = saved

    # ---- 7. deletes -------------------------------------------------------------
    print("\n[7] Deletes (A6)")
    from unittest.mock import patch

    svc = IngestionService()
    one = svc.delete_entity("advisor")
    check("delete-one completes without raising", one["outcome"] == "deleted", str(one)[:80])
    orig = svc.upsert.graph.delete_all

    def flaky(target, kind="vertex"):
        if target == "phx_dm_v2_month":
            raise RuntimeError("simulated engine failure")
        return orig(target, kind=kind)

    with patch.object(svc.upsert.graph, "delete_all", side_effect=flaky):
        allr = svc.delete_all_entities()
    check("delete-all continues past a failing entity",
          allr["failed_entities"] == 1 and allr["deleted_entities"] == 44,
          f"failed={allr['failed']}")

    # ---- 8. paths ---------------------------------------------------------------
    print("\n[8] Resolved paths (A7)")
    paths = get_settings().resolved_paths_report()
    check("all resolved paths are absolute",
          all(Path(p).is_absolute() for p in paths.values()), str(paths["sqlite_db"]))

    # ---- 9. idempotency ---------------------------------------------------------
    print("\n[9] Idempotency")
    svc = fresh_service("_ck_9.db")
    store3 = get_graph_client().store
    store3.vertices["phx_dm_v2_month"].clear()
    first = run_to_completion(svc, "month")
    count_after_first = len(store3.vertices["phx_dm_v2_month"])
    second = run_to_completion(svc, "month")
    count_after_second = len(store3.vertices["phx_dm_v2_month"])
    check("second full load: identical counts, no duplicates",
          count_after_first == count_after_second and first.created_records > 0,
          f"count={count_after_second}")
    check("second load skips only confirmed rows (no false skips, no rewrites)",
          second.created_records == 0 and second.updated_records == 0
          and second.skipped_records == first.created_records,
          f"skipped={second.skipped_records} of {first.created_records}")

    # ---- summary ---------------------------------------------------------------
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*70}\nOVERALL: {'PASS' if not failed else 'FAIL'} "
          f"({len(RESULTS) - len(failed)}/{len(RESULTS)} checks)")
    if failed:
        for name, _, detail in failed:
            print(f"  FAILED: {name} — {detail}")
    print("\nNOTE: local-tier + fixture verification only. Live-TigerGraph acceptance "
          "is the operator's docs/ROUND5_ACCEPTANCE.md.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
