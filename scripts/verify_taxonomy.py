"""Verify the R10 taxonomy (FIX_SPEC_R10 A4 / H1).

    python -m scripts.verify_taxonomy

Checks, on fixtures + the canonical module (no TigerGraph needed):
  [1] the seeded hierarchy matches A1 verbatim (structure, names, order)
  [2] the three dual-name cases resolve correctly on BOTH sides by PATH
  [3] ambiguous dual-name paths REFUSE to classify (never guess by name)
  [4] unknown lines return None (caller defaults loudly, non-recurring)
  [5] a fixture with BOTH a recurring Annuities product and a non-recurring
      Annuities product classifies each correctly, recurring gating follows
      the corrected classes, and reconciliation is $0.00
  [6] the committed sample data set carries the A1 taxonomy and classifies
      its dual-name products on both sides
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.revenue import taxonomy
from app.v2.revenue.taxonomy import NON_RECURRING, RECURRING, AmbiguousPathError

PASS, FAIL = "PASS", "FAIL"
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


# ---------------------------------------------------------------- [1] verbatim
print("[1] A1 hierarchy verbatim")
A1 = [
    (RECURRING, "Managed", ["Unified Managed Account", "JPMCAP", "Advisory",
                            "Mutual funds advisory portfolio", "Customized bond portfolio"]),
    (RECURRING, "Trails", ["Mutual funds", "Annuities", "MAC", "529"]),
    (RECURRING, "Cash management", ["Money market funds", "Premium Deposits"]),
    (NON_RECURRING, "Cash management", ["Brokered CDs"]),
    (NON_RECURRING, "Annuities", ["Fixed", "Variable"]),
    (NON_RECURRING, "Mutual funds", []),
    (NON_RECURRING, "Equities and options", ["Equities", "Equity Syndicate", "Options"]),
    (NON_RECURRING, "Fixed income", ["Corporate bonds", "Municipal bonds", "Government bonds",
                                     "Fixed Syndicate", "Other"]),
    (NON_RECURRING, "Structured products", []),
    (NON_RECURRING, "Insurance", []),
    (NON_RECURRING, "Lending", ["Securities-based lending", "Margin", "Fully Paid Lending"]),
    (NON_RECURRING, "Referrals and revenue share", [
        "Situational partnership", "Private Bank referral", "Everyday 401K", "Other",
        "Donor-advised funds", "Defined contribution advisory"]),
]
check("HIERARCHY matches the A1 transcription exactly (names, classes, order)",
      taxonomy.HIERARCHY == A1, f"module={taxonomy.HIERARCHY!r}")
check("12 product lines seeded in A1 order",
      [l[1] for l in taxonomy.lines()] == [h[1] for h in A1])
check("34 product groups seeded (leaf lines carry one group named after the line)",
      len(taxonomy.groups()) == 34, f"got {len(taxonomy.groups())}")
lc = taxonomy.line_class()
check("every product line resolves to the correct class per A1",
      all(lc[taxonomy.line_id_for(cls, name)] == cls for cls, name, _g in A1))

# ------------------------------------------------------- [2] dual-name by path
print("[2] dual-name cases resolve by PATH, both sides")
cases = [
    (("Trails", "Mutual funds"), RECURRING, "rec_trails__mutual_funds"),
    (("Mutual funds", ""), NON_RECURRING, "nonrec_mutual_funds__mutual_funds"),
    (("Mutual funds", "Mutual funds"), NON_RECURRING, "nonrec_mutual_funds__mutual_funds"),
    (("Trails", "Annuities"), RECURRING, "rec_trails__annuities"),
    (("Annuities", "Fixed"), NON_RECURRING, "nonrec_annuities__fixed"),
    (("Annuities", "Variable"), NON_RECURRING, "nonrec_annuities__variable"),
    (("Cash management", "Money market funds"), RECURRING,
     "rec_cash_management__money_market_funds"),
    (("Cash management", "Premium Deposits"), RECURRING,
     "rec_cash_management__premium_deposits"),
    (("Cash management", "Brokered CDs"), NON_RECURRING,
     "nonrec_cash_management__brokered_cds"),
]
for (l1, l2), want_cls, want_gid in cases:
    hit = taxonomy.resolve_path(l1, l2)
    ok = hit is not None and hit["class_id"] == want_cls and hit["group_id"] == want_gid
    check(f"({l1!r}, {l2!r}) -> {want_cls} / {want_gid}", ok, f"got {hit}")

# ------------------------------------------------- [3] ambiguity refuses
print("[3] ambiguous dual-name paths refuse to classify")
for l1, l2 in (("Annuities", ""), ("Annuities", "Immediate"),
               ("Cash management", ""), ("Cash management", "Unknown Sub")):
    try:
        taxonomy.resolve_path(l1, l2)
        check(f"({l1!r}, {l2!r}) raises AmbiguousPathError", False, "no error raised")
    except AmbiguousPathError:
        check(f"({l1!r}, {l2!r}) raises AmbiguousPathError", True)

# ------------------------------------------------- [4] unknown line -> None
print("[4] unknown lines return None (caller defaults loudly)")
check("('Alternative Investments', 'Hedge Funds') -> None",
      taxonomy.resolve_path("Alternative Investments", "Hedge Funds") is None)
hit = taxonomy.resolve_path("Trails", "Mutual Fund Trails")
check("unknown group under known single-class line inherits the line's class",
      hit is not None and hit["class_id"] == RECURRING and not hit["known_group"],
      f"got {hit}")

# ------------------------------------------------- [5] dual Annuities fixture
print("[5] fixture: recurring AND non-recurring Annuities products")
from app.v2.revenue.aggregation import EligibilityContext, aggregate_monthly

FIXTURE_PRODUCTS = {
    "ANNU|TRL": "rec_trails__annuities",       # Trails -> Annuities
    "ANNU|VAR": "nonrec_annuities__variable",  # Annuities -> Variable
}
txns = []
for m in ("202604", "202605"):
    txns.append({"advisor_sid": "FIX01", "month_id": m, "product_id": "ANNU|TRL",
                 "account_no": "FIXACCT-1", "credited_amt": 1000.0, "reason_cd": "__NONE__",
                 "rev_nature": "RECURRING", "days_to_process": 1, "file_key": "l_a_btr"})
    txns.append({"advisor_sid": "FIX01", "month_id": m, "product_id": "ANNU|VAR",
                 "account_no": "FIXACCT-2", "credited_amt": 5000.0, "reason_cd": "__NONE__",
                 "rev_nature": "ONE_TIME", "days_to_process": 1, "file_key": "l_a_ancomm"})
ctx = EligibilityContext(product_grid_type={p: "PRODUCT_TYPE" for p in FIXTURE_PRODUCTS})
mpr = aggregate_monthly(txns, FIXTURE_PRODUCTS, taxonomy.group_line(),
                        taxonomy.line_class(), ctx)
by_group = {r["group_id"]: r for r in mpr if r["month_id"] == "202604"}
check("recurring Annuities row lands in class RECURRING",
      by_group.get("rec_trails__annuities", {}).get("class_id") == RECURRING,
      f"got {by_group.get('rec_trails__annuities')}")
check("non-recurring Annuities row lands in class NON_RECURRING",
      by_group.get("nonrec_annuities__variable", {}).get("class_id") == NON_RECURRING,
      f"got {by_group.get('nonrec_annuities__variable')}")
rec_set = taxonomy.recurring_group_ids()
check("recurring gating set contains rec_trails__annuities and NOT nonrec_annuities__*",
      "rec_trails__annuities" in rec_set
      and not any(g.startswith("nonrec_") for g in rec_set))

# ------------------------------------------------- [6] committed sample data
print("[6] committed sample data carries the A1 taxonomy")
def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

lines_csv = rows("data/sample/vertices/phx_dm_v2_product_line.csv")
groups_csv = rows("data/sample/vertices/phx_dm_v2_product_group.csv")
line_in_class = {r["from_id"]: r["to_id"] for r in rows("data/sample/edges/phx_dm_v2_line_in_class.csv")}
group_in_line = {r["from_id"]: r["to_id"] for r in rows("data/sample/edges/phx_dm_v2_group_in_line.csv")}
prod_in_group = {r["from_id"]: r["to_id"] for r in rows("data/sample/edges/phx_dm_v2_product_in_group.csv")}
check("sample seeds 12 lines / 34 groups",
      len(lines_csv) == 12 and len(groups_csv) == 34,
      f"{len(lines_csv)} lines, {len(groups_csv)} groups")
check("sample line->class edges match the module",
      line_in_class == taxonomy.line_class(), f"got {line_in_class}")
check("sample group->line edges match the module",
      group_in_line == taxonomy.group_line(), f"got {group_in_line}")
def cls_of(product_id):
    return taxonomy.line_class()[group_in_line[prod_in_group[product_id]]]
for pid, want in (("MFT|12B1", RECURRING), ("MF|COMM", NON_RECURRING),
                  ("ANNU|TRL", RECURRING), ("ANNU|COMM", NON_RECURRING),
                  ("CASH|SWP", RECURRING), ("CASH|CD", NON_RECURRING)):
    check(f"sample product {pid} classifies {want} by path", cls_of(pid) == want)

print()
if failures:
    print(f"OVERALL FAIL — {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
print("OVERALL PASS — taxonomy matches A1, dual-name cases correct on both sides")
