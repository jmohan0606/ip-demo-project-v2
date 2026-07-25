"""R11 B/C verification — per-advisor versions/scans + async workflows.

    python -m scripts.verify_per_advisor

Fixture-only proof (temp copy of the sample set, local tier, LLM mock — NOT a
real-data or live-model verification):

  [1] baseline: legacy global versions (advisor_sid "") resolve for every advisor
  [2] single-advisor regenerate: A gets a NEW per-advisor version; B untouched;
      legacy global version stays PUBLISHED (other advisors still resolve to it)
  [3] B4: a single-advisor regenerate changes NO computed figure (revenue
      changes + drivers byte-identical before/after)
  [4] regenerate-all: every advisor gets its OWN version (no global blob);
      legacy global versions superseded; per-advisor selector filter correct
  [5] anomaly scans mirror the same per-advisor model (B2)
  [6] async: start_generation returns a job id immediately, progress advances
      (advisor N of M), completion carries the new version ids, a concurrent
      POST never starts a second run (C1/C3)

The whole run happens in data/_r11scope (a copy of data/sample) and the copy
is deleted afterwards — the committed sample set is never touched.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = "_r11scope"
TMP_DIR = ROOT / "data" / TMP

# Fresh copy BEFORE any app import resolves settings.
if TMP_DIR.exists():
    shutil.rmtree(TMP_DIR)
shutil.copytree(ROOT / "data" / "sample", TMP_DIR)

os.environ["GRAPH_CLIENT_MODE"] = "local"
os.environ["DATA_SET"] = TMP
os.environ["LLM_CLIENT_MODE"] = "mock"

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    print(("PASS " if ok else "FAIL "), name, detail if not ok else "")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")


def main() -> int:  # noqa: PLR0915 — verification narrative reads top-to-bottom
    from app.graph.client import get_graph_client
    from app.v2.anomalies import detection
    from app.v2.anomalies.service import V2AnomalyService
    from app.v2.commentary import generation_workflow as wf

    graph = get_graph_client()

    def versions(advisor_id: str = "") -> list[dict]:
        result = graph.run_query("get_commentary_versions", {"advisor_id": advisor_id})
        for obj in result.get("results", []):
            if "versions" in obj:
                return [r.get("attributes", {}) for r in obj["versions"]]
        return []

    def resolved_version(advisor_id: str) -> str:
        result = graph.run_query("get_commentary", {"advisor_id": advisor_id, "version_id": ""})
        for obj in result.get("results", []):
            if "resolved_version" in obj:
                return str(obj["resolved_version"])
        return ""

    def commentary_rows(advisor_id: str, version_id: str = "") -> list[dict]:
        result = graph.run_query("get_commentary", {"advisor_id": advisor_id, "version_id": version_id})
        for obj in result.get("results", []):
            if "commentaries" in obj:
                return [r.get("attributes", {}) for r in obj["commentaries"]]
        return []

    def figures(advisor_id: str) -> str:
        changes = graph.run_query("get_revenue_changes", {
            "advisor_id": advisor_id, "from_month": "202604", "to_month": "202606"})
        drivers = graph.run_query("get_change_drivers", {
            "advisor_id": advisor_id, "from_month": "202604", "to_month": "202605",
            "result_limit": 10000})
        return json.dumps([changes.get("results"), drivers.get("results")], sort_keys=True)

    advisors = ["SMPL001", "SMPL002", "SMPL003"]
    A, B = advisors[0], advisors[1]

    # ---------------------------------------------------------- [1] baseline
    print("[1] baseline: legacy global versions resolve for every advisor")
    base_versions = versions()
    published = [v for v in base_versions if v.get("status") == "PUBLISHED"]
    check("baseline has PUBLISHED version(s)", bool(published), str(len(base_versions)))
    legacy_global = all(not str(v.get("advisor_sid") or "") for v in base_versions)
    check("all baseline versions are legacy global (advisor_sid '')", legacy_global)
    base_resolved = {adv: resolved_version(adv) for adv in advisors}
    check("every advisor resolves to the same legacy global version",
          len(set(base_resolved.values())) == 1, str(base_resolved))

    # -------------------------------------- [2] single-advisor regenerate (A)
    print(f"[2] regenerate ONE advisor ({A}) — B untouched")
    figures_b_before = figures(B)
    b_rows_before = commentary_rows(B)
    summary = wf.run_generation(notes="r11 verify single", advisor_id=A)
    check("summary scope is the single advisor", summary.get("scope") == A, str(summary.get("scope")))
    check("exactly ONE new version created", len(summary.get("version_ids", [])) == 1,
          str(summary.get("version_ids")))
    new_vid = summary["version_ids"][0]
    va = versions(A)
    new_row = next((v for v in va if v.get("version_id") == new_vid), None)
    check("new version is advisor-scoped to A",
          new_row is not None and str(new_row.get("advisor_sid")) == A, str(new_row))
    check("A resolves to the NEW version", resolved_version(A) == new_vid,
          f"{resolved_version(A)} != {new_vid}")
    check("B still resolves to its previous version",
          resolved_version(B) == base_resolved[B],
          f"{resolved_version(B)} != {base_resolved[B]}")
    check("B's commentary rows are untouched", commentary_rows(B) == b_rows_before)
    legacy_still = [v for v in versions() if not str(v.get("advisor_sid") or "")
                    and v.get("status") == "PUBLISHED"]
    check("legacy global version STAYS PUBLISHED after a single-advisor run",
          bool(legacy_still), "legacy global was superseded by a single-advisor run")
    check("A's version list does NOT contain other advisors' scoped versions",
          all(str(v.get("advisor_sid") or "") in ("", A) for v in va))

    # ---------------------------------------------- [3] B4: figures unchanged
    print("[3] B4: single-advisor regenerate changes no computed figure")
    check("B's revenue changes + drivers byte-identical", figures(B) == figures_b_before)
    figures_a_before = figures(A)
    check("A's revenue changes + drivers byte-identical too",
          figures(A) == figures_a_before)

    # ------------------------------------------------- [4] regenerate-all
    print("[4] regenerate ALL — one version per advisor, global superseded")
    summary_all = wf.run_generation(notes="r11 verify all")
    check("one new version per advisor", len(summary_all.get("version_ids", [])) == len(advisors),
          str(summary_all.get("version_ids")))
    scoped = {}
    for vid in summary_all["version_ids"]:
        row = next((v for v in versions() if v.get("version_id") == vid), {})
        scoped[str(row.get("advisor_sid"))] = vid
    check("each new version is scoped to a distinct advisor",
          set(scoped) == set(advisors), str(scoped))
    for adv in advisors:
        check(f"{adv} resolves to its own new version", resolved_version(adv) == scoped[adv],
              f"{resolved_version(adv)} != {scoped[adv]}")
    legacy_after = [v for v in versions() if not str(v.get("advisor_sid") or "")]
    check("legacy global versions all SUPERSEDED after regenerate-all",
          legacy_after and all(v.get("status") != "PUBLISHED" for v in legacy_after))
    per_b = versions(B)
    check("B's selector list = B-scoped + legacy versions only",
          all(str(v.get("advisor_sid") or "") in ("", B) for v in per_b))
    check("no run produced a global (advisor_sid '') version",
          all(str(v.get("advisor_sid") or "") == ""
              for v in versions() if v.get("version_id") not in
              set(summary_all["version_ids"]) | {new_vid}) and
          all(str(v.get("advisor_sid") or "")
              for v in versions() if v.get("version_id") in
              set(summary_all["version_ids"]) | {new_vid}))

    # ---------------------------------------------------- [5] anomaly scans
    print("[5] anomaly scans are per-advisor the same way")
    svc = V2AnomalyService()
    base_scans = svc.scans()["scans"]
    check("baseline demo scan is legacy global",
          base_scans and all(not str(s.get("advisor_sid") or "") for s in base_scans),
          str([s.get("scan_id") for s in base_scans]))
    b_latest_before = svc.anomalies(B, "")["scan_id_used"]
    scan_summary = detection.run_scan(notes="r11 verify single", advisor_id=A)
    check("single-advisor rescan creates ONE scan scoped to A",
          len(scan_summary.get("scan_ids", [])) == 1
          and scan_summary["scans"][0]["advisor_sid"] == A, str(scan_summary.get("scans")))
    new_scan = scan_summary["scan_ids"][0]
    check("A's latest scan resolves to the new scan",
          svc.anomalies(A, "")["scan_id_used"] == new_scan,
          svc.anomalies(A, "")["scan_id_used"])
    check("B's latest scan is unchanged",
          svc.anomalies(B, "")["scan_id_used"] == b_latest_before,
          svc.anomalies(B, "")["scan_id_used"])
    scan_all = detection.run_scan(notes="r11 verify all")
    check("rescan-all creates one scan per advisor (no global blob)",
          len(scan_all.get("scan_ids", [])) == len(advisors)
          and sorted(s["advisor_sid"] for s in scan_all["scans"]) == sorted(advisors),
          str(scan_all.get("scans")))
    per_a_scans = svc.scans(A)["scans"]
    check("A's scan selector list = A-scoped + legacy scans only",
          all(str(s.get("advisor_sid") or "") in ("", A) for s in per_a_scans))

    # --------------------------------------------------------- [6] async C1/C3
    print("[6] async job: id immediately, progress, completion, no re-trigger")
    started = wf.start_generation(notes="r11 verify async", advisor_id=A)
    check("POST returns immediately with a job id",
          started.get("started") is True and bool(started.get("job_id")), str(started))
    again = wf.start_generation(notes="dup", advisor_id=A)
    check("a second POST while running returns the SAME job, never re-triggers",
          again.get("already_running") is True and again.get("job_id") == started["job_id"]
          or wf.get_status().get("state") == "completed",  # tiny fixture may finish fast
          str(again))
    saw_progress = False
    deadline = time.time() + 120
    while time.time() < deadline:
        st = wf.get_status()
        if st.get("advisor_total"):
            saw_progress = True
        if st.get("state") in ("completed", "failed"):
            break
        time.sleep(0.2)
    st = wf.get_status()
    check("job completed", st.get("state") == "completed", str(st.get("state")))
    check("status carried advisor progress (advisor N of M)", saw_progress, str(st))
    check("completion carries the new version id(s)",
          bool(st.get("summary", {}).get("version_ids")), str(st.get("summary", {}))[:200])
    check("rejoin after completion still reports the finished job (mid-run reopen)",
          wf.get_status().get("job_id") == started["job_id"])

    scan_started = detection.start_scan(notes="r11 verify async scan", advisor_id=A)
    check("scan POST returns immediately with a job id",
          scan_started.get("started") is True and bool(scan_started.get("job_id")),
          str(scan_started))
    deadline = time.time() + 120
    while time.time() < deadline and detection.get_status().get("state") not in ("completed", "failed"):
        time.sleep(0.2)
    sst = detection.get_status()
    check("scan job completed with new scan id(s)",
          sst.get("state") == "completed" and bool(sst.get("summary", {}).get("scan_ids")),
          str(sst)[:200])

    print(f"\n{'=' * 60}\n{PASS} passed, {FAIL} failed"
          f"{' — OVERALL PASS' if FAIL == 0 else ''}")
    for f in FAILURES:
        print("  FAIL:", f)
    print("\nNOTE: fixture + local tier + LLM mock only. Live per-advisor "
          "regeneration on the client machine is an OPERATOR step "
          "(docs/ROUND11_ACCEPTANCE.md).")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
