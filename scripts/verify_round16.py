"""R16 verification — per-advisor version/scan PRIMARY-KEY collision fix.

    python -m scripts.verify_round16

Fixture-only proof (temp copy of the sample set, local tier, LLM mock — NOT a
real-data or live-model verification). The round-16 bug only appears when
MULTIPLE advisors run in ONE bulk job, so every check here exercises
generate-all / rescan-all across the FULL sample advisor set:

  [1] generate-all: EVERY advisor keeps its OWN PUBLISHED commentary_version
      with a DISTINCT advisor-scoped version_id (v{no}|{advisor}); version
      vertices are never collapsed onto one advisor; get_commentary(adv, "")
      returns rows for EVERY advisor, not just the last
  [2] no overwrite: generate-all a second time — each advisor independently
      has 2 scoped versions, the latest PUBLISHED, the prior SUPERSEDED
  [3] rescan-all: EVERY advisor keeps its OWN scan with a distinct
      advisor-scoped scan_id; get_anomalies(adv, "") resolves that advisor's
      scan and returns its anomalies for EVERY advisor
  [4] single-advisor generate/rescan: only that advisor's version/scan
      advances; every other advisor's resolution is untouched
  [5] id references intact: commentary_in_version / anomaly_in_scan edges,
      evidence ids, judge evaluation ids all point at existing advisor-scoped
      ids — no dangling references
  [6] per-advisor sequences: version_no / scan number advance per advisor,
      never as one global sequence

The whole run happens in data/_r16keys (a copy of data/sample) and the copy
is deleted afterwards — the committed sample set is never touched.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = "_r16keys"
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
    from app.v2.commentary import generation_workflow as wf

    graph = get_graph_client()
    store = graph.store

    def first(result: dict, key: str):
        for obj in result.get("results", []):
            if key in obj:
                return obj[key]
        return None

    def versions(advisor_id: str = "") -> list[dict]:
        rows = first(graph.run_query("get_commentary_versions",
                                     {"advisor_id": advisor_id}), "versions") or []
        return [{"v_id": str(r.get("v_id")), **r.get("attributes", {})} for r in rows]

    def commentary(advisor_id: str, version_id: str = "") -> tuple[str, list[dict]]:
        result = graph.run_query("get_commentary",
                                 {"advisor_id": advisor_id, "version_id": version_id})
        rows = first(result, "commentaries") or []
        return str(first(result, "resolved_version") or ""), \
            [r.get("attributes", {}) for r in rows]

    def anomalies(advisor_id: str) -> tuple[str, list[dict]]:
        result = graph.run_query("get_anomalies", {
            "advisor_id": advisor_id, "scan_id": "", "severity": "",
            "result_limit": 1000})
        rows = first(result, "anomalies") or []
        return str(first(result, "scan_id_used") or ""), \
            [r.get("attributes", {}) for r in rows]

    advisors = sorted(
        str(r.get("attributes", {}).get("advisor_sid"))
        for r in first(graph.run_query("get_advisors", {}), "advisors") or [])
    n = len(advisors)
    check("sample has multiple advisors (the bug needs a multi-advisor bulk run)",
          n >= 2, f"advisors={advisors}")

    # ---------------------------------------------------------------- [1]
    print(f"\n[1] generate-all across {n} advisors — every advisor keeps its version")
    s1 = wf.run_generation("r16 [1] generate-all")
    vids1 = s1.get("version_ids", [])
    check("one new version id per advisor", len(vids1) == n, str(vids1))
    check("every new version_id is advisor-scoped and distinct",
          len(set(vids1)) == n and all(
              "|" in v and v.split("|", 1)[1] in advisors for v in vids1), str(vids1))
    survived = 0
    for adv in advisors:
        vid = next((v for v in vids1 if v.split("|", 1)[1] == adv), "")
        row = next((r for r in versions(adv) if r["v_id"] == vid), None)
        ok = row is not None and str(row.get("status")) == "PUBLISHED" \
            and str(row.get("advisor_sid")) == adv
        survived += 1 if ok else 0
        check(f"  {adv}: own PUBLISHED version vertex survives ({vid})", ok,
              str(row))
    print(f"    versions: {survived}/{n} advisors have their own PUBLISHED version")
    check("version survival count", survived == n, f"{survived}/{n}")
    resolved1: dict[str, str] = {}
    for adv in advisors:
        res, rows = commentary(adv, "")
        resolved1[adv] = res
        check(f"  get_commentary({adv},\"\") resolves {adv}'s own version with rows",
              res.endswith(f"|{adv}") and len(rows) > 0
              and all(str(r.get("advisor_sid")) == adv for r in rows),
              f"resolved={res} rows={len(rows)}")
    check("no two advisors resolve to the same version",
          len(set(resolved1.values())) == n, str(resolved1))

    # ---------------------------------------------------------------- [2]
    print(f"\n[2] generate-all AGAIN — 2 versions per advisor, no overwrite")
    s2 = wf.run_generation("r16 [2] generate-all again")
    vids2 = s2.get("version_ids", [])
    check("second run: one new version id per advisor", len(vids2) == n, str(vids2))
    for adv in advisors:
        own = [r for r in versions(adv) if str(r.get("advisor_sid")) == adv]
        scoped = [r for r in own if "|" in r["v_id"]]
        pub = [r for r in scoped if str(r.get("status")) == "PUBLISHED"]
        sup = [r for r in scoped if str(r.get("status")) == "SUPERSEDED"]
        new_vid = next((v for v in vids2 if v.split("|", 1)[1] == adv), "")
        check(f"  {adv}: 2 scoped versions — latest PUBLISHED, prior SUPERSEDED",
              len(scoped) == 2 and len(pub) == 1 and len(sup) == 1
              and pub[0]["v_id"] == new_vid and sup[0]["v_id"] == resolved1[adv],
              f"scoped={[(r['v_id'], r.get('status')) for r in scoped]}")
        nos = sorted(int(r.get("version_no") or 0) for r in scoped)
        check(f"  {adv}: version_no advanced by 1 within the advisor",
              nos[1] == nos[0] + 1, str(nos))

    # ---------------------------------------------------------------- [3]
    print(f"\n[3] rescan-all across {n} advisors — every advisor keeps its scan")
    sc = detection.run_scan("r16 [3] rescan-all")
    sids = sc.get("scan_ids", [])
    check("one new scan id per advisor", len(sids) == n, str(sids))
    check("every new scan_id is advisor-scoped and distinct",
          len(set(sids)) == n and all(
              "|" in s and s.split("|", 1)[1] in advisors for s in sids), str(sids))
    scan_survived = 0
    scan_resolved: dict[str, str] = {}
    for adv in advisors:
        sid = next((s for s in sids if s.split("|", 1)[1] == adv), "")
        vertex = store.vertex("phx_dm_v2_anomaly_scan", sid)
        ok = vertex is not None and str(vertex.get("advisor_sid")) == adv
        scan_survived += 1 if ok else 0
        check(f"  {adv}: own scan vertex survives ({sid})", ok, str(vertex))
        used, rows = anomalies(adv)
        scan_resolved[adv] = used
        check(f"  get_anomalies({adv},\"\") resolves {adv}'s scan and returns rows",
              used == sid and len(rows) > 0
              and all(str(r.get("advisor_sid")) == adv for r in rows),
              f"used={used} expected={sid} rows={len(rows)}")
    print(f"    scans: {scan_survived}/{n} advisors have their own scan")
    check("scan survival count", scan_survived == n, f"{scan_survived}/{n}")
    check("no two advisors resolve to the same scan",
          len(set(scan_resolved.values())) == n, str(scan_resolved))

    # ---------------------------------------------------------------- [4]
    print("\n[4] single-advisor generate/rescan does not clobber the others")
    target, others = advisors[0], advisors[1:]
    before_c = {adv: commentary(adv, "") for adv in others}
    before_a = {adv: anomalies(adv) for adv in others}
    s4 = wf.run_generation("r16 [4] single advisor", target)
    sc4 = detection.run_scan("r16 [4] single advisor", target)
    check(f"  {target}: new version created",
          len(s4.get("version_ids", [])) == 1
          and s4["version_ids"][0].endswith(f"|{target}"), str(s4.get("version_ids")))
    check(f"  {target}: new scan created",
          len(sc4.get("scan_ids", [])) == 1
          and sc4["scan_ids"][0].endswith(f"|{target}"), str(sc4.get("scan_ids")))
    res_t, rows_t = commentary(target, "")
    check(f"  {target}: resolves to the new version",
          res_t == s4["version_ids"][0] and len(rows_t) > 0, res_t)
    for adv in others:
        check(f"  {adv}: commentary resolution untouched",
              commentary(adv, "") == before_c[adv], str(commentary(adv, "")[0]))
        check(f"  {adv}: anomaly resolution untouched",
              anomalies(adv) == before_a[adv], str(anomalies(adv)[0]))

    # ---------------------------------------------------------------- [5]
    print("\n[5] id references intact — no dangling edges/evidence/evaluations")
    scoped_versions = {r["v_id"] for adv in advisors for r in versions(adv)
                       if "|" in r["v_id"]}
    dangling_civ = 0
    linked_c = 0
    for cid, attrs in store.all_vertices("phx_dm_v2_commentary").items():
        vid = str(attrs.get("version_id"))
        if "|" not in vid:
            continue  # legacy rows keep legacy version ids
        linked_c += 1
        targets = store.out_ids("phx_dm_v2_commentary_in_version", cid)
        if vid not in scoped_versions or vid not in [str(t) for t in targets]:
            dangling_civ += 1
    check("every scoped commentary row's version exists + edge points at it",
          linked_c > 0 and dangling_civ == 0,
          f"scoped_rows={linked_c} dangling={dangling_civ}")
    dangling_ev = 0
    scoped_ev = 0
    for eid, attrs in store.all_vertices("phx_dm_v2_evidence").items():
        # evidence_id = f"{driver_id}|{version_id}" and driver ids themselves
        # contain "|" — recover the version part by stripping the known
        # driver_id prefix, never by splitting on the first "|".
        did = str(attrs.get("driver_id") or "")
        eid = str(eid)
        if not did or not eid.startswith(did + "|"):
            continue
        vid = eid[len(did) + 1:]
        if "|" not in vid:
            continue  # legacy evidence names legacy version ids ("v22")
        scoped_ev += 1
        if vid not in scoped_versions:
            dangling_ev += 1
    check("every scoped evidence record names an existing version",
          scoped_ev > 0 and dangling_ev == 0,
          f"scoped={scoped_ev} dangling={dangling_ev}")
    dangling_j = 0
    scoped_j = 0
    commentary_ids = set(store.all_vertices("phx_dm_v2_commentary"))
    for jid, attrs in store.all_vertices("phx_dm_v2_commentary_evaluation").items():
        vid = str(attrs.get("version_id"))
        if "|" not in vid:
            continue
        scoped_j += 1
        if vid not in scoped_versions or str(attrs.get("commentary_id")) not in commentary_ids:
            dangling_j += 1
    check("every scoped judge evaluation names an existing version + commentary",
          scoped_j > 0 and dangling_j == 0, f"scoped={scoped_j} dangling={dangling_j}")
    scan_vertices = set(store.all_vertices("phx_dm_v2_anomaly_scan"))
    dangling_scan = 0
    scoped_an = 0
    for aid, attrs in store.all_vertices("phx_dm_v2_anomaly").items():
        sid = str(attrs.get("scan_id"))
        if "|" not in sid:
            continue
        scoped_an += 1
        targets = [str(t) for t in store.out_ids("phx_dm_v2_anomaly_in_scan", aid)]
        if sid not in scan_vertices or sid not in targets:
            dangling_scan += 1
    check("every scoped anomaly's scan exists + anomaly_in_scan points at it",
          scoped_an > 0 and dangling_scan == 0,
          f"scoped={scoped_an} dangling={dangling_scan}")

    # ---------------------------------------------------------------- [6]
    print("\n[6] sequences are per-advisor, not global")
    for adv in advisors:
        own_nos = sorted(int(r.get("version_no") or 0) for r in versions(adv)
                         if str(r.get("advisor_sid")) == adv and "|" in r["v_id"])
        expect = 3 if adv == target else 2
        check(f"  {adv}: {expect} scoped versions, consecutive version_no",
              len(own_nos) == expect
              and own_nos == list(range(own_nos[0], own_nos[0] + expect)),
              str(own_nos))
    # Two advisors may legitimately share a version_no now — that is the point
    # of per-advisor sequences: numbers can repeat ACROSS advisors while ids
    # never collide.
    all_scoped_ids = [r["v_id"] for adv in advisors for r in versions(adv)
                      if "|" in r["v_id"]]
    check("advisor-scoped version ids are globally distinct",
          len(all_scoped_ids) == len(set(all_scoped_ids)), str(sorted(all_scoped_ids)))

    print(f"\n{'=' * 60}\nRESULT: {PASS} PASS / {FAIL} FAIL")
    print(f"versions: {survived}/{n} advisors have their own PUBLISHED version")
    print(f"scans:    {scan_survived}/{n} advisors have their own scan")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print("  -", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        if TMP_DIR.exists():
            shutil.rmtree(TMP_DIR)
    sys.exit(code)
