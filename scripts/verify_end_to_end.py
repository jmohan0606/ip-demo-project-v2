"""Phase 7 end-to-end verification (Definition of Done, CLAUDE.md §9).

Run with DATA_SET=sample. Checks, against the STORED graph data:
reconciliation per advisor/transition, evidence completeness for every driver,
cited-driver evidence, published commentary, GSQL result reproducibility,
data_source on every vertex, and full cause coverage.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.client import MockGraphClient
from app.v2.drivers.service import V2DriverService
from app.v2.revenue.service import V2RevenueService


def main() -> int:
    c = MockGraphClient()
    failures = []

    def check(name, cond, detail=""):
        print(("PASS" if cond else "FAIL"), name, detail)
        if not cond:
            failures.append(name)

    svc = V2DriverService()
    advisors = sorted(c.store.all_vertices("phx_dm_v2_advisor"))
    months = sorted(c.store.all_vertices("phx_dm_v2_month"))
    for adv in advisors:
        r = svc.reconciliation(adv, months[0], months[-1])
        check(f"reconciliation {adv}", r["all_reconcile"],
              str({k: v["discrepancy"] for k, v in r["transitions"].items()}))

    versions = c.store.all_vertices("phx_dm_v2_commentary_version")
    published = [v for v, a in versions.items() if a.get("status") == "PUBLISHED"]
    check("exactly one PUBLISHED version", len(published) == 1, str(sorted(versions)))
    latest = published[0] if published else None

    drivers = set(c.store.all_vertices("phx_dm_v2_revenue_driver"))
    evidence = c.store.all_vertices("phx_dm_v2_evidence")
    ev_drivers = {a["driver_id"] for a in evidence.values()
                  if str(a.get("evidence_id", "")).endswith(f"|{latest}")}
    check("every driver has latest-version evidence", drivers <= ev_drivers,
          f"{len(drivers)} drivers")

    rows = [a for a in c.store.all_vertices("phx_dm_v2_commentary").values()
            if a["version_id"] == latest]
    cited = {b["driver_id"] for a in rows if a.get("bullets_json")
             for b in json.loads(a["bullets_json"])}
    check("all cited drivers have evidence", cited <= ev_drivers, f"{len(cited)} cited")
    check("commentary exists for every transition",
          len(rows) == len(advisors) * (len(months) - 1),
          f"{len(rows)} rows")

    rev = V2RevenueService()
    sample = [a for a in evidence.values()
              if str(a.get("evidence_id", "")).endswith(f"|{latest}")
              and a["gsql_query_name"] == "get_product_revenue_change"][:10]
    mismatch = 0
    for a in sample:
        p = json.loads(a["gsql_params_json"])
        live = rev.product_revenue_change(p["advisor_id"], p["product_group"],
                                          p["from_month"], p["to_month"])
        live.pop("served_by_tier", None)
        if json.loads(a["gsql_result_json"]) != live:
            mismatch += 1
    check("stored GSQL results reproduce live", mismatch == 0,
          f"{len(sample)} sampled")

    required = ("finding_text", "calc_json", "source_records_json", "lineage_json",
                "checks_json", "gsql_query_name", "gsql_result_json", "source_sql",
                "source_table")
    incomplete = [a["evidence_id"] for a in evidence.values()
                  if not all(a.get(k) for k in required)]
    check("every evidence record complete", not incomplete, f"{len(evidence)} records")

    blank = [f"{vt}/{vid}" for vt, rs in c.store.vertices.items()
             for vid, a in rs.items() if not a.get("data_source")]
    check("data_source set on every vertex", not blank,
          f"{sum(len(r) for r in c.store.vertices.values())} vertices")

    causes = {a["cause_id"] for a in c.store.all_vertices("phx_dm_v2_revenue_driver").values()}
    check("all 16 causes exercised (incl. BASELINE_LIMITED on the baseline transition)",
          len(causes) == 16, str(sorted(causes)))

    # T1-4: MIX magnitude per transition. Reconciliation at $0.00 proves
    # COMPLETENESS only — MIX absorbs whatever named drivers don't claim, so it
    # holds no matter how wrong a named driver is. A large MIX share means a
    # driver is missing or mis-specified; report every transition's share so
    # attribution quality is visible at a glance.
    from collections import defaultdict as _dd
    mix_by_tr, tot_by_tr = _dd(float), {}
    for a in c.store.all_vertices("phx_dm_v2_revenue_driver").values():
        adv, f, t, _g = a["change_id"].split("|")
        if a["cause_id"] == "MIX":
            mix_by_tr[(adv, f, t)] += float(a.get("contribution_amt") or 0)
    for a in c.store.all_vertices("phx_dm_v2_revenue_change").values():
        if a.get("group_id") == "__TOTAL__":
            tot_by_tr[(a["advisor_sid"], a["from_month_id"], a["to_month_id"])] = \
                float(a.get("change_amt") or 0)
    mix_lines, mix_large = [], []
    for k in sorted(tot_by_tr):
        total = tot_by_tr[k]
        pct = abs(mix_by_tr.get(k, 0.0)) / abs(total) * 100 if total else 0.0
        mix_lines.append(f"{'|'.join(k)} MIX {mix_by_tr.get(k, 0.0):.2f} = {pct:.1f}% of {total:.2f}")
        if pct >= 15.0:
            mix_large.append(mix_lines[-1])
    print("  MIX share per transition:\n   ", "\n    ".join(mix_lines))
    check("MIX residual < 15% of every transition's change", not mix_large, str(mix_large))

    # T1-6: OUT_OF_GRID must be near-empty and fully explained. grid_type is a
    # static product attribute and CREDITED_GRID_TYPES fixed config, so
    # out-of-grid revenue cannot move month over month into credited (that is
    # why it needs no driver). On real data this bucket should be ~empty; the
    # sample deliberately carries PAY_TYPE_SUMMARY demo rows. Flag LOUDLY if
    # anything else lands here.
    products = c.store.all_vertices("phx_dm_v2_product")
    oog_amt, oog_unexpected = 0.0, []
    for tid, a in c.store.all_vertices("phx_dm_v2_revenue_transaction").items():
        grid = str(products.get(str(a.get("product_id")), {}).get("grid_type") or "PRODUCT_TYPE")
        if grid not in {"PRODUCT_TYPE"}:
            oog_amt += float(a.get("credited_amt") or 0)
            if grid != "PAY_TYPE_SUMMARY":
                oog_unexpected.append(f"{tid}:{grid}")
    print(f"  OUT_OF_GRID total: {oog_amt:.2f} "
          "(sample carries deliberate PAY_TYPE_SUMMARY demo rows; on REAL data "
          "this should be near zero — investigate loudly if it is not)")
    check("OUT_OF_GRID contains only PAY_TYPE_SUMMARY rows", not oog_unexpected,
          str(oog_unexpected[:3]))

    # R1-6: the stored credited breakdown must satisfy the client's identity
    # revenue = total_revenue - non_credited_amt - late_excluded_amt per cell.
    bad_cells = []
    for mid, a in c.store.all_vertices("phx_dm_v2_monthly_product_revenue").items():
        lhs = round(float(a.get("revenue") or 0), 2)
        rhs = round(float(a.get("total_revenue") or 0)
                    - float(a.get("non_credited_amt") or 0)
                    - float(a.get("late_excluded_amt") or 0), 2)
        if abs(lhs - rhs) > 0.01:
            bad_cells.append(mid)
    check("credited identity holds on every mpr cell", not bad_cells, str(bad_cells[:3]))

    reasons = c.store.all_vertices("phx_dm_v2_reason_code")
    check("reason codes seeded (15)", len(reasons) == 15, str(len(reasons)))
    buckets = {a.get("revenue_eligibility")
               for a in c.store.all_vertices("phx_dm_v2_revenue_transaction").values()}
    check("all reason eligibility states present in transactions",
          buckets >= {"CREDITED", "NON_CREDITED", "EXCLUDED"}, str(sorted(map(str, buckets))))

    print("\nOVERALL:", "PASS" if not failures else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
