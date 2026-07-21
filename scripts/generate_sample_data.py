"""Generate the synthetic sample data set (EXTRACTION_SPEC §8, FIX_SPEC R1-11).

Writes data/sample/{vertices,edges}/*.csv and the ingestion manifest
(docs/tigergraph_foundation/data/manifest.json). Deterministic (seeded), and
OBVIOUSLY synthetic: 3 advisors named "Sample Advisor One/Two/Three", ids
SMPL001..003, months Apr/May/Jun 2026.

The transaction set is engineered so every driver cause is exercised:
  NEW_ACCOUNT   SMPL001 account SMPLACCT-1109 first contributes in Jun
  LOST_ACCOUNT  SMPL001 account SMPLACCT-1104 stops after Apr
  ONE_TIME      structured-products syndicate rows land in May only (file_key twhs)
  ELIGIBILITY   SMPL001 account SMPLACCT-1103's UMA fee goes reason 9E (small
                household) in Jun — revenue moves credited -> non-credited
  TIMING        alternatives bill quarterly: Apr and Jun rows, none in May
  FEE_RATE      SMPL002 managed UMA rate steps 82 -> 88 bps in Jun
  DISCOUNT      SMPL003 managed rows gain concession_type=Discount in Jun
  BILLABLE_DAYS May has 21 business days vs Apr 22 / Jun 22 (recurring groups)
  VOLUME        equities trade counts swing month to month
  CLAWBACK      mutual-fund trail reversals (negative credited_amt) vary
  MIX           the remainder of every decomposition
  MARKET / NET_FLOW emitted as DUMMY zero-contribution drivers (no source data)

Reason-code coverage (R1-11) — every eligibility path is visible in the UI:
  __NONE__  the bulk of rows (Grid transactions, credited)
  91        equity-below-minimum rows (credited, incentive-INeligible)
  9E        the ELIGIBILITY story above (non-credited)
  9G        SMPL002 inherited account, steady non-credited trail all 3 months
  9X        one deleted SMPL003 equity row (EXCLUDED — in no total at all)
  + one SMPL003 UMA row with days_to_process > 90 (the 90-day rule)
  + UMA|PAYS pay-type-summary rows (grid_type filter, OUT_OF_GRID by config)

Derived CSVs (monthly_product_revenue, revenue_change, revenue_driver) are
computed by the SAME Phase-4 code the app uses (app/v2/revenue, app/v2/drivers)
— nothing is hand-typed twice. Workflow CSVs (commentary/evidence) are
PRESERVED if they exist: regeneration of the data set must not delete
commentary history (versions are additive).
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.calendar import month_rows
from app.v2.drivers.attribution import attribute_transition, reconcile
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import (
    TOTAL_GROUP,
    EligibilityContext,
    aggregate_monthly,
    derive_rev_nature,
    split_by_eligibility,
)

OUT = Path("data/sample")
MANIFEST = Path("docs/tigergraph_foundation/data/manifest.json")
MONTHS = ["202604", "202605", "202606"]
RNG = random.Random(20260720)

ADVISORS = [
    {"advisor_sid": "SMPL001", "advisor_name": "Sample Advisor One", "rep_code": "SR01",
     "branch_cd": "SMPLBR1", "standard_id": "SMPL001", "data_source": "REAL"},
    {"advisor_sid": "SMPL002", "advisor_name": "Sample Advisor Two", "rep_code": "SR02",
     "branch_cd": "SMPLBR1", "standard_id": "SMPL002", "data_source": "REAL"},
    {"advisor_sid": "SMPL003", "advisor_name": "Sample Advisor Three", "rep_code": "SR03",
     "branch_cd": "SMPLBR2", "standard_id": "SMPL003", "data_source": "REAL"},
]

CLASSES = [
    {"class_id": "RECURRING", "class_name": "Recurring", "display_order": 1, "data_source": "REAL"},
    {"class_id": "NON_RECURRING", "class_name": "Non-recurring", "display_order": 2, "data_source": "REAL"},
]

# line_id, line_name, class, order
LINES = [
    ("managed", "Managed", "RECURRING", 1),
    ("trails", "Trails", "RECURRING", 2),
    ("structured_products", "Structured Products", "NON_RECURRING", 3),
    ("alternative_investments", "Alternative Investments", "NON_RECURRING", 4),
    ("equities_and_options", "Equities and Options", "NON_RECURRING", 5),
    ("cash_management", "Cash Management", "NON_RECURRING", 6),
    ("annuities", "Annuities", "NON_RECURRING", 7),
]

# group_id, group_name, line_id, order
GROUPS = [
    ("unified_managed_account", "Unified Managed Account", "managed", 1),
    ("jpmcap", "JPMCAP", "managed", 2),
    ("advisory", "Advisory", "managed", 3),
    ("mutual_fund_trails", "Mutual Fund Trails", "trails", 4),
    ("structured_products", "Structured Products", "structured_products", 5),
    ("alternative_investments", "Alternative Investments", "alternative_investments", 6),
    ("equities", "Equities", "equities_and_options", 7),
    ("cash_management", "Cash Management", "cash_management", 8),
    ("annuities", "Annuities", "annuities", 9),
]

# product_id -> (product_cd, product_sub_cd, product_name, group_id, grid_type)
# UMA|PAYS is a PAY_TYPE_SUMMARY row: extracted (grid no longer filtered at
# extraction, R1-4/R1-5) but OUT_OF_GRID under the default CREDITED_GRID_TYPES
# config — relaxing the config makes it count, with no code change.
PRODUCTS = [
    ("UMA|FEE", "UMA", "FEE", "UMA Advisory Fee", "unified_managed_account", "PRODUCT_TYPE"),
    ("JPMCAP|FEE", "JPMCAP", "FEE", "JPMCAP Program Fee", "jpmcap", "PRODUCT_TYPE"),
    ("ADV|FEE", "ADV", "FEE", "Advisory Fee", "advisory", "PRODUCT_TYPE"),
    ("MFT|12B1", "MFT", "12B1", "Mutual Fund 12b-1 Trail", "mutual_fund_trails", "PRODUCT_TYPE"),
    ("STRP|SYND", "STRP", "SYND", "Structured Product Syndicate", "structured_products", "PRODUCT_TYPE"),
    ("ALTS|QFEE", "ALTS", "QFEE", "Alternatives Quarterly Fee", "alternative_investments", "PRODUCT_TYPE"),
    ("EQ|COMM", "EQ", "COMM", "Equity Commission", "equities", "PRODUCT_TYPE"),
    ("CASH|SWP", "CASH", "SWP", "Cash Sweep Revenue", "cash_management", "PRODUCT_TYPE"),
    ("ANNU|COMM", "ANNU", "COMM", "Annuity Commission", "annuities", "PRODUCT_TYPE"),
    ("UMA|PAYS", "UMA", "PAYS", "UMA Pay-Type Summary", "unified_managed_account", "PAY_TYPE_SUMMARY"),
]

# ELIGIBILITY (R1-8) sits immediately after ONE_TIME in the attribution order.
CAUSES = [
    ("VOLUME", "Transaction volume", "More or fewer transactions at similar rates", "REAL", 1),
    ("ONE_TIME", "One-time items", "Syndicate allocations, new issues, referrals that don't repeat", "REAL", 2),
    ("ELIGIBILITY", "Credited eligibility", "Revenue moved between credited and non-credited reason codes month over month", "REAL", 3),
    ("TIMING", "Billing timing", "Quarterly billing cycle falls in one month not the other", "REAL", 4),
    ("FEE_RATE", "Effective fee rate", "Change in client_rate_bps / std_tier_rate", "REAL", 5),
    ("DISCOUNT", "Discounting", "Change in concession_type / discount_amt / eff_disc_pct", "REAL", 6),
    ("BILLABLE_DAYS", "Billable days", "Different number of billing days between months", "DERIVED", 7),
    ("MIX", "Product mix", "Shift between products at different rates", "DERIVED", 8),
    ("NEW_ACCOUNT", "Accounts opened", "Accounts contributing this month but not last", "REAL", 9),
    ("LOST_ACCOUNT", "Accounts closed", "Accounts contributing last month but not this", "REAL", 10),
    ("CLAWBACK", "Reversals", "Negative credited amounts (chargebacks)", "REAL", 11),
    ("MARKET", "Market performance", "Asset value movement", "DUMMY", 12),
    ("NET_FLOW", "Net client flows", "Inflows less outflows", "DUMMY", 13),
]

PRODUCT_GROUP = {p[0]: p[4] for p in PRODUCTS}
PRODUCT_GRID = {p[0]: p[5] for p in PRODUCTS}
GROUP_LINE = {g[0]: g[2] for g in GROUPS}
LINE_CLASS = {l[0]: l[2] for l in LINES}
RECURRING_CLASS_GROUPS = {g for g, line in GROUP_LINE.items() if LINE_CLASS[line] == "RECURRING"}
BILLABLE_DAYS = {"202604": 22, "202605": 21, "202606": 22}

REASONS = elig.reason_map()  # the seed — same rows written to reason_code.csv

# The generator uses the app's default eligibility config (settings defaults):
CTX = EligibilityContext(
    reasons=REASONS,
    product_grid_type=PRODUCT_GRID,
    credited_grid_types=frozenset({"PRODUCT_TYPE"}),
    max_processing_days=90,
)


def _mk_txn(advisor: str, month: str, product_id: str, account: str, day: int,
            amount: float, rate_bps: float = 0.0, file_key: str = "ace",
            description: str = "", concession: str = "None", discount: float = 0.0,
            split_pct: float = 1.0, balance: float = 0.0,
            reason: str = "", proc_days: int = 1) -> dict:
    _mk_txn.counter += 1
    n = _mk_txn.counter
    ai = int(advisor[-1])
    trade = date(int(month[:4]), int(month[4:6]), day)
    proc = trade + timedelta(days=proc_days)
    pre_split = round(amount / split_pct, 2) if split_pct else amount
    desc = description or f"MONTH M{int(month[4:6]):02d}-{month[:4]}"
    reason_cd = elig.normalize_reason(reason)
    return {
        "txn_id": f"SMPLTRD{n:05d}|1",
        "trade_ref_no": f"SMPLTRD{n:05d}",
        "split_seq_no": 1,
        "advisor_sid": advisor,
        "month_id": month,
        "product_id": product_id,
        "account_no": account,
        "trade_dt": f"{trade} 00:00:00",
        "proc_dt": f"{proc} 00:00:00",
        "credited_amt": round(amount, 2),
        "pre_split_amt": pre_split,
        "split_pct": split_pct,
        "client_rate_bps": rate_bps,
        "std_tier_rate": rate_bps,
        "concession_type": concession,
        "discount_amt": round(discount, 2),
        "eff_disc_pct": round(discount / (amount + discount) * 100, 2) if discount else 0.0,
        "avg_balance_amt": balance,
        "file_key": file_key,
        "trade_description": desc,
        "rev_nature": derive_rev_nature(file_key, desc),
        # R1-3 eligibility attributes — DERIVED from the reason-code seed data.
        "reason_cd": reason_cd,
        "rm_sid": f"SMPLRM{ai}",
        "cs_sid": f"SMPLCS{ai}",
        "revenue_eligibility": elig.reason_eligibility(reason_cd, REASONS),
        "incentive_eligible": elig.incentive_eligible(reason_cd, REASONS),
        "days_to_process": elig.days_to_process(trade, proc),
        # R1-7: posting month = trade month (ASSUMED — no iComp feed to identify
        # closed months, so no prior-period-adjustment logic in this round).
        "posting_month_id": month,
        "data_source": "REAL",
    }


_mk_txn.counter = 0


def build_transactions() -> list[dict]:
    txns: list[dict] = []
    for ai, adv in enumerate(("SMPL001", "SMPL002", "SMPL003"), start=1):
        base = ai * 1000
        accounts = [f"SMPLACCT-{base + i}" for i in range(101, 109)]
        lost = f"SMPLACCT-{base + 104}"       # contributes Apr only
        new = f"SMPLACCT-{base + 109}"        # first contributes Jun
        small_household = f"SMPLACCT-{base + 103}"  # SMPL001: goes 9E in Jun
        for m in MONTHS:
            days = BILLABLE_DAYS[m]
            # Managed UMA — recurring fee per account, revenue scales with billable days.
            # SMPL002 rate steps 82 -> 88 bps in Jun (FEE_RATE).
            rate = 88.0 if (adv == "SMPL002" and m == "202606") else 82.0
            for acct in accounts[:4]:
                if acct == lost and m != "202604":
                    continue
                fee = round((5200 + ai * 700 + int(acct[-1]) * 130) * days / 22 * rate / 82.0, 2)
                disc = 0.0
                concession = "None"
                if adv == "SMPL003" and m == "202606" and acct in accounts[:2]:
                    disc = round(fee * 0.12, 2)   # DISCOUNT appears in Jun
                    fee = round(fee - disc, 2)
                    concession = "Discount"
                # ELIGIBILITY story: SMPL001's account crosses below the
                # minimum-household threshold in Jun -> its fee goes 9E
                # (non-credited); the account keeps trading, so it is an
                # eligibility move, not a lost account.
                reason = "9E" if (adv == "SMPL001" and m == "202606"
                                  and acct == small_household) else ""
                txns.append(_mk_txn(adv, m, "UMA|FEE", acct, 28, fee, rate_bps=rate,
                                    file_key="ace", concession=concession, discount=disc,
                                    split_pct=0.8 if ai == 2 else 1.0, reason=reason))
            if new and m == "202606":
                txns.append(_mk_txn(adv, m, "UMA|FEE", new, 28,
                                    round(4100 + ai * 350, 2), rate_bps=rate, file_key="ace"))
            # 90-day rule: one SMPL003 April UMA row processed 100 days late —
            # in Total revenue, excluded from Credited (LATE).
            if adv == "SMPL003" and m == "202604":
                txns.append(_mk_txn(adv, m, "UMA|FEE", accounts[2], 2, 900.0,
                                    rate_bps=82.0, file_key="ace",
                                    description="MONTH M04-2026 LATE PROCESS",
                                    proc_days=100))
            # Pay-type-summary rows (grid_type demo): extracted but OUT_OF_GRID
            # under the default CREDITED_GRID_TYPES config.
            if adv == "SMPL001":
                txns.append(_mk_txn(adv, m, "UMA|PAYS", accounts[0], 28,
                                    round(20000 * days / 22, 2), rate_bps=0.0,
                                    file_key="ace", description="PAY TYPE SUMMARY"))
            # JPMCAP + Advisory — steady recurring base.
            txns.append(_mk_txn(adv, m, "JPMCAP|FEE", accounts[4], 27,
                                round((3600 + ai * 400) * days / 22, 2), rate_bps=65.0, file_key="ace"))
            txns.append(_mk_txn(adv, m, "ADV|FEE", accounts[5], 27,
                                round((2900 + ai * 300) * days / 22, 2), rate_bps=58.0, file_key="ace"))
            # Mutual fund trails — recurring plus CLAWBACK reversals that vary.
            txns.append(_mk_txn(adv, m, "MFT|12B1", accounts[6], 25,
                                round(1900 + ai * 250, 2), rate_bps=25.0, file_key="mf_12b1"))
            neg_rows = {"202604": 1, "202605": 2, "202606": 4}[m] + (ai - 1)
            for k in range(neg_rows):
                txns.append(_mk_txn(adv, m, "MFT|12B1", accounts[6], 26,
                                    -round(120 + 35 * k + ai * 10, 2), rate_bps=25.0,
                                    file_key="mf_12b1", description=f"MONTH M{int(m[4:6]):02d}-2026 REVERSAL"))
            # 9G inherited account: SMPL002 carries a steady NON_CREDITED trail
            # all three months (visible in the breakdown; no MoM driver).
            if adv == "SMPL002":
                txns.append(_mk_txn(adv, m, "MFT|12B1", f"SMPLACCT-{base + 110}", 25,
                                    800.0, rate_bps=25.0, file_key="mf_12b1",
                                    reason="9G"))
            # Structured products — ONE_TIME syndicate in May only.
            if m == "202605":
                for k in range(3):
                    txns.append(_mk_txn(adv, m, "STRP|SYND", accounts[0], 12 + k,
                                        round(9800 + ai * 1500 + k * 900, 2),
                                        file_key="twhs", description="SYNDICATE ALLOCATION"))
            # Alternatives — quarterly billing: Apr and Jun only (TIMING).
            if m in ("202604", "202606"):
                txns.append(_mk_txn(adv, m, "ALTS|QFEE", accounts[1], 15,
                                    round(6200 + ai * 800, 2), rate_bps=120.0, file_key="ace",
                                    description=f"QUARTERLY BILLING M{int(m[4:6]):02d}-2026"))
            # Equities — VOLUME swings: 8 -> 5 -> 11 trades (+ advisor offset).
            # The first trade each month is 91 (equity below minimum): still
            # credited, but incentive-INeligible — the badge is visible with no
            # revenue effect.
            n_trades = {"202604": 8, "202605": 5, "202606": 11}[m] + (ai - 1) * 2
            for k in range(n_trades):
                txns.append(_mk_txn(adv, m, "EQ|COMM", accounts[5 + (k % 3)], 3 + (k * 2) % 24,
                                    round(140 + RNG.uniform(-25, 25), 2), file_key="ace",
                                    description="EQUITY TRADE COMMISSION",
                                    reason="91" if k == 0 else ""))
            # 9X deleted transaction: EXCLUDED — appears in NO revenue figure.
            if adv == "SMPL003" and m == "202605":
                txns.append(_mk_txn(adv, m, "EQ|COMM", accounts[5], 14, 500.0,
                                    file_key="ace",
                                    description="EQUITY TRADE COMMISSION (DELETED)",
                                    reason="9X"))
            # Cash management — steady.
            txns.append(_mk_txn(adv, m, "CASH|SWP", accounts[7], 24,
                                round(1450 + ai * 150, 2), rate_bps=18.0,
                                file_key="money_mkt", balance=round(950000 + ai * 120000, 2)))
            # Annuities — ONE_TIME issuance for SMPL003 in Apr only.
            if adv == "SMPL003" and m == "202604":
                txns.append(_mk_txn(adv, m, "ANNU|COMM", accounts[3], 9,
                                    7400.0, file_key="l_a_ancomm",
                                    description="ANNUITY ISSUED CONTRACT SMPL-77"))
    return txns


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def preserve_or_create(path: Path, columns: list[str]) -> int | None:
    """Workflow-generated CSVs (commentary/evidence): keep existing content —
    versions are additive and regeneration must not delete history. Returns the
    existing row count, or 0 after creating a header-only file."""
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    return write_csv(path, [], columns)


def main() -> int:
    txns = build_transactions()
    months = month_rows(MONTHS)
    mpr = aggregate_monthly(txns, PRODUCT_GROUP, GROUP_LINE, LINE_CLASS, CTX)
    changes = compute_changes_from(mpr)

    # Attribution runs on CREDITED transactions; the ELIGIBILITY step reads the
    # NON_CREDITED ones (FIX_SPEC R1-8).
    split = split_by_eligibility(txns, CTX)
    cred_by_advisor: dict[str, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in split[elig.CREDITED]:
        cred_by_advisor[t["advisor_sid"]][(PRODUCT_GROUP[t["product_id"]], t["month_id"])].append(t)
    nc_by_advisor: dict[str, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in split[elig.NON_CREDITED]:
        nc_by_advisor[t["advisor_sid"]][(PRODUCT_GROUP[t["product_id"]], t["month_id"])].append(t)

    drivers: list[dict] = []
    by_transition: dict[tuple, list[dict]] = defaultdict(list)
    for c in changes:
        by_transition[(c["advisor_sid"], c["from_month_id"], c["to_month_id"])].append(c)
    for (advisor, from_m, to_m), rows in sorted(by_transition.items()):
        drivers.extend(attribute_transition(
            rows, cred_by_advisor[advisor], RECURRING_CLASS_GROUPS,
            BILLABLE_DAYS[from_m], BILLABLE_DAYS[to_m],
            nc_txns_by_group_month=nc_by_advisor[advisor],
        ))

    report = reconcile(changes, drivers)
    if not report["all_reconcile"]:
        print("RECONCILIATION FAILED:", json.dumps(report, indent=2))
        return 1

    # ------------------------------------------------ vertex CSVs
    v = OUT / "vertices"
    counts: dict[str, int] = {}
    counts["advisor.csv"] = write_csv(v / "advisor.csv", ADVISORS,
        ["advisor_sid", "advisor_name", "rep_code", "branch_cd", "standard_id", "data_source"])
    counts["month.csv"] = write_csv(v / "month.csv", months, list(months[0].keys()))
    counts["revenue_class.csv"] = write_csv(v / "revenue_class.csv", CLASSES,
        ["class_id", "class_name", "display_order", "data_source"])
    counts["product_line.csv"] = write_csv(v / "product_line.csv",
        [{"line_id": l, "line_name": n, "display_order": o, "data_source": "REAL"} for l, n, _c, o in LINES],
        ["line_id", "line_name", "display_order", "data_source"])
    counts["product_group.csv"] = write_csv(v / "product_group.csv",
        [{"group_id": g, "group_name": n, "display_order": o, "data_source": "REAL"} for g, n, _l, o in GROUPS],
        ["group_id", "group_name", "display_order", "data_source"])
    counts["product.csv"] = write_csv(v / "product.csv",
        [{"product_id": pid, "product_cd": cd, "product_sub_cd": sub, "product_name": name,
          "grid_type": grid, "data_source": "REAL"} for pid, cd, sub, name, _g, grid in PRODUCTS],
        ["product_id", "product_cd", "product_sub_cd", "product_name", "grid_type", "data_source"])
    account_ids = sorted({t["account_no"] for t in txns})
    counts["account.csv"] = write_csv(v / "account.csv",
        [{"account_no": a, "account_typ": "BROKERAGE" if int(a[-1]) % 2 else "ADVISORY",
          "wrap_flg": "Y" if int(a[-1]) % 2 == 0 else "N", "data_source": "REAL"} for a in account_ids],
        ["account_no", "account_typ", "wrap_flg", "data_source"])
    counts["driver_cause.csv"] = write_csv(v / "driver_cause.csv",
        [{"cause_id": c, "cause_name": n, "cause_description": d, "default_data_source": s,
          "display_order": o, "data_source": "REAL"} for c, n, d, s, o in CAUSES],
        ["cause_id", "cause_name", "cause_description", "default_data_source", "display_order", "data_source"])
    counts["reason_code.csv"] = write_csv(v / "reason_code.csv", elig.seed_rows(),
        ["reason_code", "description", "ui_mapping", "owned_by", "eligibility",
         "include_in_credited", "incentive_eligible", "display_order", "data_source"])
    txn_cols = ["txn_id", "trade_ref_no", "split_seq_no", "advisor_sid", "month_id", "product_id",
                "account_no", "trade_dt", "proc_dt", "credited_amt", "pre_split_amt", "split_pct",
                "client_rate_bps", "std_tier_rate", "concession_type", "discount_amt", "eff_disc_pct",
                "avg_balance_amt", "file_key", "trade_description", "rev_nature",
                "reason_cd", "rm_sid", "cs_sid", "revenue_eligibility", "incentive_eligible",
                "days_to_process", "posting_month_id", "data_source"]
    counts["revenue_transaction.csv"] = write_csv(v / "revenue_transaction.csv", txns, txn_cols)
    counts["monthly_product_revenue.csv"] = write_csv(v / "monthly_product_revenue.csv", mpr,
        ["mpr_id", "advisor_sid", "month_id", "group_id", "line_id", "class_id", "revenue",
         "txn_count", "account_count", "avg_rate_bps", "recurring_amt", "one_time_amt",
         "total_revenue", "non_credited_amt", "excluded_amt", "late_excluded_amt", "data_source"])
    balances = [{"balance_id": f"{a}|{m}", "account_no": a, "month_id": m,
                 "avg_billable_assets": 0.0, "effective_fee_bps": 0.0,
                 "billable_days": BILLABLE_DAYS[m], "data_source": "DUMMY"}
                for a in account_ids for m in MONTHS]
    counts["account_month_balance.csv"] = write_csv(v / "account_month_balance.csv", balances,
        ["balance_id", "account_no", "month_id", "avg_billable_assets", "effective_fee_bps",
         "billable_days", "data_source"])
    counts["revenue_change.csv"] = write_csv(v / "revenue_change.csv", changes,
        ["change_id", "advisor_sid", "from_month_id", "to_month_id", "group_id", "from_revenue",
         "to_revenue", "change_amt", "change_pct", "direction", "data_source"])
    counts["revenue_driver.csv"] = write_csv(v / "revenue_driver.csv", drivers,
        ["driver_id", "change_id", "cause_id", "group_id", "contribution_amt", "contribution_pct",
         "direction", "rank", "inputs_json", "data_source"])
    # Workflow-generated vertices: PRESERVED if present (versions are additive);
    # created header-only on a fresh data set.
    counts["commentary_version.csv"] = preserve_or_create(v / "commentary_version.csv",
        ["version_id", "version_no", "generated_at", "model", "prompt_version", "data_snapshot_dt",
         "status", "advisor_count", "transition_count", "blocked_count", "notes", "data_source"])
    counts["commentary.csv"] = preserve_or_create(v / "commentary.csv",
        ["commentary_id", "version_id", "advisor_sid", "from_month_id", "to_month_id", "headline",
         "narrative_text", "bullets_json", "status", "blocked_reason", "data_source"])
    counts["evidence.csv"] = preserve_or_create(v / "evidence.csv",
        ["evidence_id", "driver_id", "finding_text", "calc_json", "source_records_json",
         "lineage_json", "checks_json", "gsql_query_name", "gsql_params_json", "gsql_result_json",
         "source_sql", "source_table", "source_row_count", "data_source"])

    # ------------------------------------------------ edge CSVs
    e = OUT / "edges"

    def edge_rows(name: str, pairs: list[tuple[str, str]]) -> int:
        seen, rows = set(), []
        for f_, t_ in pairs:
            if (f_, t_) not in seen:
                seen.add((f_, t_))
                rows.append({"from_id": f_, "to_id": t_})
        return write_csv(e / f"{name}.csv", rows, ["from_id", "to_id"])

    counts["product_in_group.csv"] = edge_rows("product_in_group",
        [(pid, g) for pid, _cd, _sub, _name, g, _grid in PRODUCTS])
    counts["group_in_line.csv"] = edge_rows("group_in_line", [(g, l) for g, _n, l, _o in GROUPS])
    counts["line_in_class.csv"] = edge_rows("line_in_class", [(l, c) for l, _n, c, _o in LINES])
    counts["txn_for_advisor.csv"] = edge_rows("txn_for_advisor", [(t["txn_id"], t["advisor_sid"]) for t in txns])
    counts["txn_in_month.csv"] = edge_rows("txn_in_month", [(t["txn_id"], t["month_id"]) for t in txns])
    counts["txn_for_product.csv"] = edge_rows("txn_for_product", [(t["txn_id"], t["product_id"]) for t in txns])
    counts["txn_for_account.csv"] = edge_rows("txn_for_account", [(t["txn_id"], t["account_no"]) for t in txns])
    counts["txn_has_reason.csv"] = edge_rows("txn_has_reason", [(t["txn_id"], t["reason_cd"]) for t in txns])
    counts["mpr_for_advisor.csv"] = edge_rows("mpr_for_advisor", [(r["mpr_id"], r["advisor_sid"]) for r in mpr])
    counts["mpr_in_month.csv"] = edge_rows("mpr_in_month", [(r["mpr_id"], r["month_id"]) for r in mpr])
    counts["mpr_for_group.csv"] = edge_rows("mpr_for_group", [(r["mpr_id"], r["group_id"]) for r in mpr])
    counts["balance_for_account.csv"] = edge_rows("balance_for_account", [(b["balance_id"], b["account_no"]) for b in balances])
    counts["balance_in_month.csv"] = edge_rows("balance_in_month", [(b["balance_id"], b["month_id"]) for b in balances])
    counts["change_for_advisor.csv"] = edge_rows("change_for_advisor", [(c["change_id"], c["advisor_sid"]) for c in changes])
    counts["change_for_group.csv"] = edge_rows("change_for_group",
        [(c["change_id"], c["group_id"]) for c in changes if c["group_id"] != TOTAL_GROUP])
    counts["change_from_month.csv"] = edge_rows("change_from_month", [(c["change_id"], c["from_month_id"]) for c in changes])
    counts["change_to_month.csv"] = edge_rows("change_to_month", [(c["change_id"], c["to_month_id"]) for c in changes])
    counts["driver_of_change.csv"] = edge_rows("driver_of_change", [(d["driver_id"], d["change_id"]) for d in drivers])
    counts["driver_has_cause.csv"] = edge_rows("driver_has_cause", [(d["driver_id"], d["cause_id"]) for d in drivers])
    counts["driver_for_group.csv"] = edge_rows("driver_for_group",
        [(d["driver_id"], d["group_id"]) for d in drivers if d["group_id"] != TOTAL_GROUP])
    # Workflow-generated edges — preserved if present.
    for name in ("commentary_for_advisor", "commentary_from_month", "commentary_to_month",
                 "commentary_in_version", "commentary_cites_driver", "evidence_for_driver"):
        counts[f"{name}.csv"] = preserve_or_create(e / f"{name}.csv", ["from_id", "to_id"])

    # ------------------------------------------------ manifest
    WORKFLOW_FILES = {"commentary_version.csv", "commentary.csv", "evidence.csv",
                      "commentary_for_advisor.csv", "commentary_from_month.csv",
                      "commentary_to_month.csv", "commentary_in_version.csv",
                      "commentary_cites_driver.csv", "evidence_for_driver.csv"}
    schema = json.load(open("docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json"))
    files = []
    vertex_order = ["advisor", "month", "revenue_class", "product_line", "product_group", "product",
                    "account", "driver_cause", "reason_code", "revenue_transaction",
                    "monthly_product_revenue", "account_month_balance", "revenue_change",
                    "revenue_driver", "commentary_version", "commentary", "evidence"]
    order = 0
    for name in vertex_order:
        target = f"phx_dm_v2_{name}"
        spec = schema["vertices"][target]
        cols = list(spec["attributes"].keys())
        fname = f"{name}.csv"
        order += 1
        files.append({
            "kind": "vertex", "target": target, "file": f"vertices/{fname}", "order": order,
            "id_column": spec["primary_id"]["name"],
            "columns": {c: c for c in cols},
            "required_columns": [spec["primary_id"]["name"], "data_source"],
            "expected_rows": None if fname in WORKFLOW_FILES else counts[fname],
            "workflow_generated": fname in WORKFLOW_FILES,
        })
    edge_order = ["product_in_group", "group_in_line", "line_in_class",
                  "txn_for_advisor", "txn_in_month", "txn_for_product", "txn_for_account",
                  "txn_has_reason",
                  "mpr_for_advisor", "mpr_in_month", "mpr_for_group",
                  "balance_for_account", "balance_in_month",
                  "change_for_advisor", "change_for_group", "change_from_month", "change_to_month",
                  "driver_of_change", "driver_has_cause", "driver_for_group",
                  "commentary_for_advisor", "commentary_from_month", "commentary_to_month",
                  "commentary_in_version", "commentary_cites_driver", "evidence_for_driver"]
    for name in edge_order:
        target = f"phx_dm_v2_{name}"
        spec = schema["edges"][target]
        fname = f"{name}.csv"
        order += 1
        files.append({
            "kind": "edge", "target": target, "file": f"edges/{fname}", "order": order,
            "from_type": spec["from"], "to_type": spec["to"],
            "from_column": "from_id", "to_column": "to_id",
            "columns": {},
            "expected_rows": None if fname in WORKFLOW_FILES else counts[fname],
            "workflow_generated": fname in WORKFLOW_FILES,
        })
    manifest = {
        "graph": "iperform_v2_revenue",
        "prefix": "phx_dm_v2_",
        "batch_size": 500,
        "note": "Files listed in dependency order: dimensions, facts, analytics, then edges. "
                "Load top-to-bottom; delete bottom-to-top (vertex deletes cascade their edges). "
                "workflow_generated files start header-only and are appended by the commentary workflow.",
        "files": files,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    json.dump(manifest, open(MANIFEST, "w"), indent=2)

    print(f"transactions: {len(txns)}  mpr: {len(mpr)}  changes: {len(changes)}  drivers: {len(drivers)}")
    print("eligibility mix:", {k: len(rows) for k, rows in split.items()})
    print("reconciliation:", json.dumps(report["transitions"], indent=2)[:400], "…")
    print("causes exercised:", sorted({d['cause_id'] for d in drivers}))
    return 0


def compute_changes_from(mpr: list[dict]) -> list[dict]:
    from app.v2.revenue.aggregation import compute_changes
    return compute_changes(mpr, MONTHS)


if __name__ == "__main__":
    sys.exit(main())
