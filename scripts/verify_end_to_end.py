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
    check("all 12 causes exercised", len(causes) == 12, str(sorted(causes)))

    print("\nOVERALL:", "PASS" if not failures else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
