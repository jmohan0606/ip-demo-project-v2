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
    # R11 A1: real-hierarchy addition, classification ASSUMED pending client.
    (NON_RECURRING, "Alternative Investments", []),
]
check("HIERARCHY matches the A1 transcription exactly (names, classes, order)",
      taxonomy.HIERARCHY == A1, f"module={taxonomy.HIERARCHY!r}")
check("13 product lines seeded in A1 order (12 + Alternative Investments, R11 A1)",
      [l[1] for l in taxonomy.lines()] == [h[1] for h in A1])
check("35 product groups seeded (leaf lines carry one group named after the line)",
      len(taxonomy.groups()) == 35, f"got {len(taxonomy.groups())}")
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
check("('Crypto Custody', 'Cold Storage') -> None",
      taxonomy.resolve_path("Crypto Custody", "Cold Storage") is None)
hit = taxonomy.resolve_path("Trails", "Mutual Fund Trails")
check("unknown group under known single-class line inherits the line's class",
      hit is not None and hit["class_id"] == RECURRING and not hit["known_group"],
      f"got {hit}")

# ---------------------------------------- [4b] R11 A1: Alternative Investments
print("[4b] R11 A1: Alternative Investments classifies NON_RECURRING (assumed)")
hit = taxonomy.resolve_path("Alternative Investments", "Alternative Investments")
check("('Alternative Investments', 'Alternative Investments') -> NON_RECURRING leaf",
      hit is not None and hit["class_id"] == NON_RECURRING
      and hit["group_id"] == "nonrec_alternative_investments__alternative_investments"
      and hit["known_group"], f"got {hit}")
hit = taxonomy.resolve_path("Alternative Investments", "")
check("('Alternative Investments', '') -> same leaf group",
      hit is not None and hit["class_id"] == NON_RECURRING
      and hit["group_id"] == "nonrec_alternative_investments__alternative_investments",
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
check("sample seeds 13 lines / 35 groups (incl. Alternative Investments, R11)",
      len(lines_csv) == 13 and len(groups_csv) == 35,
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

# ------------------------------------- [7] R11 A2/A3: real-hierarchy fixture
print("[7] R11: real-hierarchy fixture — every PRODUCT_TYPE path classifies; "
      "non-PRODUCT_TYPE rows excluded before classification")
from app.v2.revenue.taxonomy import NonProductGridRowError, PRODUCT_GRID_TYPE

# Fixture of the real hierarchy's distinct (grid_type, level_one, level_two)
# paths: every A1 (line, group) pair as PRODUCT_TYPE (35 paths — this is the
# shape pcr.product_hierarchy provides), plus the R11-confirmed
# NON_CREDITED_REVENUE and PAY_TYPE_SUMMARY reason/pay-type rows (7 paths).
REAL_PATHS = [(PRODUCT_GRID_TYPE, lname, gname)
              for cls, lname, gnames in taxonomy.HIERARCHY
              for gname in (gnames or [lname])]
REAL_PATHS += [
    ("NON_CREDITED_REVENUE", "Small Households", "Small Households"),
    ("NON_CREDITED_REVENUE", "Personal Accounts", "Personal Accounts"),
    ("NON_CREDITED_REVENUE", "Transferred Accounts", "Transferred Accounts"),
    ("PAY_TYPE_SUMMARY", "Grid", "Grid"),
    ("PAY_TYPE_SUMMARY", "Referral 25% payout", "Referral 25% payout"),
    ("PAY_TYPE_SUMMARY", "Incentive non-eligible", "Incentive non-eligible"),
    ("PAY_TYPE_SUMMARY", "LOA", "LOA"),
]
check(f"fixture covers {len(REAL_PATHS)} distinct real-hierarchy paths (~45)",
      40 <= len(REAL_PATHS) <= 50, f"got {len(REAL_PATHS)}")

product_rows = [p for p in REAL_PATHS if p[0] == PRODUCT_GRID_TYPE]
stops: list[str] = []
for grid, l1, l2 in product_rows:
    try:
        hit = taxonomy.resolve_path(l1, l2, grid_type=grid)
        if hit is None:
            stops.append(f"({l1!r}, {l2!r}) -> None")
    except AmbiguousPathError as exc:
        stops.append(f"({l1!r}, {l2!r}) -> Ambiguous")
check("every PRODUCT_TYPE path classifies with NO stop (no None, no Ambiguous)",
      not stops, f"stops: {stops}")
hit = taxonomy.resolve_path("Alternative Investments", "Alternative Investments",
                            grid_type=PRODUCT_GRID_TYPE)
check("ALTI path resolves NON_RECURRING with grid_type passed",
      hit is not None and hit["class_id"] == NON_RECURRING, f"got {hit}")

# Non-PRODUCT_TYPE rows: the guard refuses loudly if one reaches resolve_path.
guarded = 0
for grid, l1, l2 in REAL_PATHS:
    if grid == PRODUCT_GRID_TYPE:
        continue
    try:
        taxonomy.resolve_path(l1, l2, grid_type=grid)
    except NonProductGridRowError:
        guarded += 1
check("all 7 non-PRODUCT_TYPE rows refused by the resolve_path guard "
      "(NonProductGridRowError, logged loudly)", guarded == 7, f"got {guarded}")

# build_real_data.build_dimensions filters them BEFORE classification: none of
# the reason/pay-type names may appear as taxonomy lines; their products still
# register under a nongrid_* holding line.
from scripts.build_real_data import build_dimensions
hier_rows = [{"level_one_product": l1, "level_two_product": l2, "grid_type": grid,
              "product_code": f"P{i:02d}", "sub_product_code": "X"}
             for i, (grid, l1, l2) in enumerate(REAL_PATHS)]
dims = build_dimensions(hier_rows, [{"advisor_sid": "FIX01", "advisor_name": "F",
                                     "rr_nam": "", "rep_code": "", "branch_cd": ""}])
line_names = {name for _lid, name, _cls, _o in dims["lines"]}
check("no reason/pay-type name became a taxonomy line",
      not ({"Small Households", "Personal Accounts", "Transferred Accounts",
            "Grid", "Referral 25% payout", "Incentive non-eligible", "LOA"} & line_names),
      f"lines: {sorted(line_names)}")
nongrid_lines = {lid for lid, _n, _c, _o in dims["lines"] if lid.startswith("nongrid_")}
check("non-product rows land under nongrid_* holding lines (products keep a home)",
      nongrid_lines == {"nongrid_non_credited_revenue", "nongrid_pay_type_summary"},
      f"got {nongrid_lines}")
prods_by_grid = {}
for pid, _cd, _sub, _name, gid, grid in dims["products"]:
    prods_by_grid.setdefault(grid, set()).add(pid)
check("all 42 fixture products registered; 7 carry a non-PRODUCT_TYPE grid_type",
      len(dims["products"]) == len(REAL_PATHS)
      and sum(len(v) for g, v in prods_by_grid.items() if g != PRODUCT_GRID_TYPE) == 7,
      f"got {len(dims['products'])} products, grids {sorted(prods_by_grid)}")

print()
if failures:
    print(f"OVERALL FAIL — {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
print("OVERALL PASS — taxonomy matches A1 (+ALTI), dual-name cases correct on both "
      "sides, non-PRODUCT_TYPE rows excluded before classification")
