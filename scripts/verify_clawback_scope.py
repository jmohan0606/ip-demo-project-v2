"""Verify the R10 CLAWBACK scope (FIX_SPEC_R10 D / H5).

    python -m scripts.verify_clawback_scope

  [1] a reversal on an Annuities product produces a CLAWBACK driver
  [2] a reversal on Equities does NOT — it reconciles through the ordinary
      buckets, unlabelled
  [3] the Life PRODUCT-CODE gate labels reversals even outside an
      Annuities/Insurance group
  [4] the scope set derives from hierarchy position (both Annuities sides +
      Insurance; nothing else)
  [5] reconciliation $0.00 with reversals both in and out of scope
  [6] committed sample: CLAWBACK only on Annuities groups; the out-of-scope
      MFT reversals exist and are unlabelled
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.drivers.attribution import attribute_transition, reconcile
from app.v2.revenue import taxonomy

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


ANNU, EQ = "nonrec_annuities__variable", "nonrec_equities_and_options__equities"
MONTHS = ["202604", "202605"]


def txn(month, group, product, account, amount):
    return {"advisor_sid": "FIX01", "month_id": month, "account_no": account,
            "product_id": product, "credited_amt": amount, "reason_cd": "__NONE__",
            "rev_nature": "RECURRING", "client_rate_bps": 0.0, "discount_amt": 0.0,
            "concession_type": "None", "file_key": "ace", "days_to_process": 1,
            "_group": group}


def run(txns):
    by_gm: dict[tuple, list[dict]] = {}
    for t in txns:
        by_gm.setdefault((t["_group"], t["month_id"]), []).append(t)
    groups = sorted({t["_group"] for t in txns})
    changes = []
    for gid in groups + ["__TOTAL__"]:
        def tot(m):
            if gid == "__TOTAL__":
                return sum(t["credited_amt"] for t in txns if t["month_id"] == m)
            return sum(t["credited_amt"] for t in by_gm.get((gid, m), []))
        changes.append({"change_id": f"FIX01|202604|202605|{gid}", "advisor_sid": "FIX01",
                        "from_month_id": "202604", "to_month_id": "202605", "group_id": gid,
                        "from_revenue": tot("202604"), "to_revenue": tot("202605"),
                        "change_amt": round(tot("202605") - tot("202604"), 2),
                        "change_pct": 0.0, "direction": "UP"})
    drivers = attribute_transition(
        changes, by_gm, set(), 22, 22, loaded_month_ids=MONTHS,
        clawback_group_ids=taxonomy.clawback_group_ids())
    return drivers, reconcile(changes, drivers)


base = [txn(m, g, p, a, 2000.0) for m in MONTHS
        for g, p, a in ((ANNU, "ANNU|VAR", "A-1"), (EQ, "EQ|COMM", "A-2"))]

print("[1] reversal on an Annuities product -> CLAWBACK")
d1, r1 = run(base + [txn("202605", ANNU, "ANNU|VAR", "A-1", -400.0)])
cb1 = [d for d in d1 if d["cause_id"] == "CLAWBACK"]
check("CLAWBACK fires on the Annuities group",
      any(d["group_id"] == ANNU for d in cb1), f"got {[d['group_id'] for d in cb1]}")
check("CLAWBACK amount = (400.00)",
      any(abs(float(d["contribution_amt"]) + 400.0) < 0.01 for d in cb1))

print("[2] reversal on Equities -> NO CLAWBACK, still reconciles")
d2, r2 = run(base + [txn("202605", EQ, "EQ|COMM", "A-2", -400.0)])
check("no CLAWBACK driver anywhere",
      not any(d["cause_id"] == "CLAWBACK" for d in d2))
check("the equities reversal reconciles through ordinary buckets",
      r2["all_reconcile"])

print("[3] Life product-code gate")
d3, r3 = run(base + [txn("202604", EQ, "LIFE|POL", "A-3", -250.0)])
cb3 = [d for d in d3 if d["cause_id"] == "CLAWBACK"]
check("a LIFE|* reversal in an out-of-scope group IS labelled CLAWBACK",
      any(d["group_id"] == EQ for d in cb3), f"got {[d['group_id'] for d in cb3]}")

print("[4] scope set from hierarchy position")
scope = taxonomy.clawback_group_ids()
check("scope == both Annuities sides + Insurance",
      scope == {"rec_trails__annuities", "nonrec_annuities__fixed",
                "nonrec_annuities__variable", "nonrec_insurance__insurance"},
      f"got {sorted(scope)}")

print("[5] reconciliation $0.00 in all three fixtures")
check("all fixtures reconcile",
      r1["all_reconcile"] and r2["all_reconcile"] and r3["all_reconcile"])

print("[6] committed sample")
drv = list(csv.DictReader(open("data/sample/vertices/phx_dm_v2_revenue_driver.csv")))
cb = [d for d in drv if d["cause_id"] == "CLAWBACK"]
check("sample CLAWBACK drivers exist and ALL sit on Annuities groups",
      bool(cb) and all("annuities" in d["group_id"] for d in cb),
      f"got {[d['group_id'] for d in cb]}")
txn_rows = list(csv.DictReader(open("data/sample/vertices/phx_dm_v2_revenue_transaction.csv")))
mft_neg = [t for t in txn_rows if t["product_id"] == "MFT|12B1" and float(t["credited_amt"]) < 0]
check("sample still carries out-of-scope MFT reversals (unlabelled by construction)",
      bool(mft_neg), "no MFT reversal rows found")

print()
if failures:
    print(f"OVERALL FAIL — {failures}")
    sys.exit(1)
print("OVERALL PASS — CLAWBACK scoped to Annuities/Insurance/Life; other reversals unlabelled")
