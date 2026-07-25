"""Generate the synthetic sample data set (EXTRACTION_SPEC §8, FIX_SPEC R1-11).

Writes data/sample/{vertices,edges}/*.csv and the ingestion manifest
(docs/tigergraph_foundation/data/manifest.json). Deterministic (seeded), and
OBVIOUSLY synthetic: 3 advisors named "Sample Advisor One/Two/Three", ids
SMPL001..003, months Apr/May/Jun 2026.

The transaction set is engineered so every driver cause is exercised (R6: the
account-presence rule is now "recurring-class groups only, after
ACCOUNT_ABSENCE_MONTHS=2 consecutive quiet months", which moves the stories):
  NEW_ACCOUNT   SMPLACCT-x109 first contributes in Jun (quiet Apr+May confirmed)
                -> fires on May->Jun
  LOST_ACCOUNT  SMPLACCT-x110 contributes ONLY in April (quiet May+Jun confirmed)
                -> fires on Apr->May
  BASELINE_LIMITED SMPLACCT-x104 stops after May; only one loaded month follows,
                so the 2-month absence test cannot be evaluated -> May->Jun
  (persistence proof) SMPLACCT-x111 skips May and returns in Jun — intermittent,
                NOT lost and NOT new; no account driver may fire for it
  ONE_TIME      structured-products syndicate rows land in May only (file_key twhs)
  HOUSEHOLD     SMPL001 account SMPLACCT-1103's UMA fee goes reason 9E (small
                household) in Jun — the 9E carve-out claims the move (R10 C2)
  INHERITANCE   SMPL002's 9G trail: non-credited Apr+May, cooling ends in Jun
                and the 800 returns to credited (R10 C1)
  ELIGIBILITY   the 91 equity-below-minimum rows (non-credited since R10 B)
                vary month over month — the non-9E/9G remainder
  TIMING        MAC (Trails) bills quarterly: Apr and Jun rows, none in May
  FEE_RATE      SMPL002 managed UMA rate steps 82 -> 88 bps in Jun
  DISCOUNT      SMPL003 managed rows gain concession_type=Discount in Jun
  BILLABLE_DAYS May has 21 business days vs Apr 22 / Jun 22 (recurring groups)
  VOLUME        equities trade counts swing month to month
  CLAWBACK      mutual-fund trail reversals (negative credited_amt) vary
  LATE_PROCESSING SMPL003's 900 UMA fee processes 100 days late in Apr only —
                credited from May on, so Apr->May gains 900 via the 90-day rule
  EXCLUDED_CHANGE SMPL003's 500 MFT booking is credited in Apr, deleted (9X)
                from May on — Apr->May loses 500 to the excluded bucket
  MIX           the remainder of every decomposition
  MARKET / NET_FLOW emitted as DUMMY zero-contribution drivers (no source data)

Reason-code coverage (R1-11) — every eligibility path is visible in the UI:
  __NONE__  the bulk of rows (Grid transactions, credited)
  91        equity-below-minimum rows (NON_CREDITED since R10 B)
  9E        the HOUSEHOLD story above (non-credited)
  9G        SMPL002 inherited account trail — 9G Apr+May, credited from Jun
  9X        SMPL003's deleted trail booking (EXCLUDED — in no total at all)
  + one SMPL003 UMA row with days_to_process > 90 (the 90-day rule)
  + UMA|PAYS pay-type-summary rows (grid_type filter, OUT_OF_GRID by config)

Since FIX_SPEC_R4 (S-B2/S-B3) everything downstream of the fabricated
transactions — eligibility, aggregation, attribution, reconciliation, CSV
writing, data_source stamping and the manifest — lives in the SHARED builder
(app/v2/dataset/builder.py), which scripts/build_real_data.py also calls with
transactions parsed from real extracts. This script only fabricates the demo
inputs. Workflow CSVs (commentary/evidence) are PRESERVED if they exist:
regeneration of the data set must not delete commentary history (versions are
additive).
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.dataset.builder import ReconciliationError, build_dataset
from app.v2.revenue import eligibility as elig
from app.v2.revenue import taxonomy
from app.v2.revenue.aggregation import EligibilityContext, derive_rev_nature

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

# FIX_SPEC_R10 A — the taxonomy is seeded VERBATIM from the canonical module
# (app/v2/revenue/taxonomy.py), never redeclared here. The full A1 dimension
# set is written even where the sample has no product in a group.
CLASSES = taxonomy.classes()
LINES = taxonomy.lines()
GROUPS = taxonomy.groups()

# product_id -> (product_cd, product_sub_cd, product_name, group_id, grid_type)
# Group ids are PATH-SCOPED (class -> line -> group) per FIX_SPEC_R10 A2. The
# sample deliberately exercises the dual-name cases on BOTH sides:
#   Mutual funds     rec_trails__mutual_funds        vs  nonrec_mutual_funds__mutual_funds
#   Annuities        rec_trails__annuities           vs  nonrec_annuities__variable
#   Cash management  rec_cash_management__money_market_funds
#                                                    vs  nonrec_cash_management__brokered_cds
# UMA|PAYS is a PAY_TYPE_SUMMARY row: extracted (grid no longer filtered at
# extraction, R1-4/R1-5) but OUT_OF_GRID under the default CREDITED_GRID_TYPES
# config — relaxing the config makes it count, with no code change.
PRODUCTS = [
    ("UMA|FEE", "UMA", "FEE", "UMA Advisory Fee", "rec_managed__unified_managed_account", "PRODUCT_TYPE"),
    ("JPMCAP|FEE", "JPMCAP", "FEE", "JPMCAP Program Fee", "rec_managed__jpmcap", "PRODUCT_TYPE"),
    ("ADV|FEE", "ADV", "FEE", "Advisory Fee", "rec_managed__advisory", "PRODUCT_TYPE"),
    ("MFT|12B1", "MFT", "12B1", "Mutual Fund 12b-1 Trail", "rec_trails__mutual_funds", "PRODUCT_TYPE"),
    ("ANNU|TRL", "ANNU", "TRL", "Annuity Trail", "rec_trails__annuities", "PRODUCT_TYPE"),
    ("MAC|QFEE", "MAC", "QFEE", "MAC Quarterly Fee", "rec_trails__mac", "PRODUCT_TYPE"),
    ("STRP|SYND", "STRP", "SYND", "Structured Product Syndicate",
     "nonrec_structured_products__structured_products", "PRODUCT_TYPE"),
    ("EQ|COMM", "EQ", "COMM", "Equity Commission", "nonrec_equities_and_options__equities", "PRODUCT_TYPE"),
    ("CASH|SWP", "CASH", "SWP", "Cash Sweep Revenue",
     "rec_cash_management__money_market_funds", "PRODUCT_TYPE"),
    ("CASH|CD", "CASH", "CD", "Brokered CD Commission",
     "nonrec_cash_management__brokered_cds", "PRODUCT_TYPE"),
    ("MF|COMM", "MF", "COMM", "Mutual Fund Commission", "nonrec_mutual_funds__mutual_funds", "PRODUCT_TYPE"),
    ("ANNU|COMM", "ANNU", "COMM", "Annuity Commission", "nonrec_annuities__variable", "PRODUCT_TYPE"),
    ("UMA|PAYS", "UMA", "PAYS", "UMA Pay-Type Summary", "rec_managed__unified_managed_account", "PAY_TYPE_SUMMARY"),
]

PRODUCT_GRID = {p[0]: p[5] for p in PRODUCTS}
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
        # R6: stops after May — with only ONE loaded month following, the
        # 2-month absence test cannot be evaluated, so this is the
        # BASELINE_LIMITED story (fires on May->Jun), NOT a lost account.
        bl_lost = f"SMPLACCT-{base + 104}"
        new = f"SMPLACCT-{base + 109}"        # first contributes Jun; quiet
        # Apr+May are both loaded, so NEW_ACCOUNT is confirmed on May->Jun
        small_household = f"SMPLACCT-{base + 103}"  # SMPL001: goes 9E in Jun
        for m in MONTHS:
            days = BILLABLE_DAYS[m]
            # Managed UMA — recurring fee per account, revenue scales with billable days.
            # SMPL002 rate steps 82 -> 88 bps in Jun (FEE_RATE).
            rate = 88.0 if (adv == "SMPL002" and m == "202606") else 82.0
            for acct in accounts[:4]:
                if acct == bl_lost and m == "202606":
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
            # R6 — LOST_ACCOUNT story: an account contributing ONLY in April.
            # Both following loaded months (May, Jun) are quiet, so the 2-month
            # absence test CONFIRMS it lost on the Apr->May transition.
            # (For SMPL002 this account also carries the steady 9G trail below,
            # so it stays active and no account driver fires — intentional.)
            if m == "202604":
                txns.append(_mk_txn(adv, m, "UMA|FEE", f"SMPLACCT-{base + 110}", 15,
                                    round(1200 + ai * 400, 2), rate_bps=82.0, file_key="ace"))
            # R6 A2 persistence proof: an account that skips May and returns in
            # June is ordinary intermittency — NOT lost on Apr->May (activity in
            # Jun is inside the 2-month absence window) and NOT new on May->Jun
            # (activity in Apr is inside the look-back window). Its movement
            # stays with the group's other drivers/MIX; the amount is kept small
            # so the MIX share stays under the 15% gate.
            if m != "202605":
                txns.append(_mk_txn(adv, m, "UMA|FEE", f"SMPLACCT-{base + 111}", 18,
                                    round(420 + ai * 60, 2), rate_bps=82.0, file_key="ace"))
            # 90-day rule (LATE_PROCESSING driver, FIX_SPEC_R3 T1-1): SMPL003
            # carries a 900 UMA fee all three months. April's instance processed
            # 100 days late (in Total, excluded from Credited); May and June
            # process on time — so Apr->May credited genuinely gains 900 and
            # the LATE_PROCESSING driver claims exactly that.
            if adv == "SMPL003":
                late = m == "202604"
                txns.append(_mk_txn(adv, m, "UMA|FEE", accounts[2], 2, 900.0,
                                    rate_bps=82.0, file_key="ace",
                                    description=f"MONTH M{int(m[4:6]):02d}-2026"
                                                + (" LATE PROCESS" if late else ""),
                                    proc_days=100 if late else 1))
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
            # R10 D: mutual-fund trail reversals are OUT of CLAWBACK scope —
            # they stay real negative revenue in the ordinary buckets and must
            # NOT produce a CLAWBACK driver (proven by verify_clawback_scope).
            neg_rows = {"202604": 1, "202605": 2, "202606": 4}[m] + (ai - 1)
            for k in range(neg_rows):
                txns.append(_mk_txn(adv, m, "MFT|12B1", accounts[6], 26,
                                    -round(120 + 35 * k + ai * 10, 2), rate_bps=25.0,
                                    file_key="mf_12b1", description=f"MONTH M{int(m[4:6]):02d}-2026 REVERSAL"))
            # CLAWBACK story (R10 D — in scope): annuity trail reversals vary
            # month over month on the recurring Trails -> Annuities group.
            neg_annu = {"202604": 1, "202605": 2, "202606": 3}[m]
            for k in range(neg_annu):
                txns.append(_mk_txn(adv, m, "ANNU|TRL", accounts[4], 23,
                                    -round(90 + 25 * k + ai * 8, 2), rate_bps=0.0,
                                    file_key="l_a_btr",
                                    description=f"MONTH M{int(m[4:6]):02d}-2026 ANNUITY REVERSAL"))
            # 9G inherited account (R10 C1 — INHERITANCE story): SMPL002's
            # inherited trail is NON_CREDITED (9G) in Apr and May; the
            # inheritance cooling period ends in Jun, the 9G flag drops and
            # the same 800 trail returns to credited. Apr->May: 9G steady, no
            # driver. May->Jun: INHERITANCE +800 (revenue back to credited).
            if adv == "SMPL002":
                txns.append(_mk_txn(adv, m, "MFT|12B1", f"SMPLACCT-{base + 110}", 25,
                                    800.0, rate_bps=25.0, file_key="mf_12b1",
                                    reason="9G" if m != "202606" else "",
                                    description="INHERITED ACCOUNT TRAIL"))
            # Structured products — ONE_TIME syndicate in May only.
            if m == "202605":
                for k in range(3):
                    txns.append(_mk_txn(adv, m, "STRP|SYND", accounts[0], 12 + k,
                                        round(9800 + ai * 1500 + k * 900, 2),
                                        file_key="twhs", description="SYNDICATE ALLOCATION"))
            # MAC — quarterly billing: Apr and Jun only (TIMING). R10: the old
            # taxonomy's Alternative Investments line does not exist in the
            # corrected hierarchy; the quarterly-billing story moves to MAC
            # (Trails), which is in QUARTERLY_BILLED_GROUPS.
            if m in ("202604", "202606"):
                txns.append(_mk_txn(adv, m, "MAC|QFEE", accounts[1], 15,
                                    round(6200 + ai * 800, 2), rate_bps=120.0, file_key="ace",
                                    description=f"QUARTERLY BILLING M{int(m[4:6]):02d}-2026"))
            # R10 A — dual-name products on BOTH sides of the hierarchy, so the
            # fixture proves position-based classification: a recurring
            # Annuities trail (Trails -> Annuities) alongside the non-recurring
            # Annuity Commission below; a non-recurring Mutual Fund Commission
            # (top-level Mutual funds) alongside the recurring 12b-1 trail; a
            # non-recurring Brokered CD alongside the recurring cash sweep.
            txns.append(_mk_txn(adv, m, "ANNU|TRL", accounts[4], 22,
                                round(560 + ai * 90, 2), rate_bps=0.0, file_key="l_a_btr",
                                description="ANNUITY TRAIL"))
            txns.append(_mk_txn(adv, m, "MF|COMM", accounts[2], 16,
                                round(340 + ai * 45, 2), file_key="ace",
                                description="MUTUAL FUND COMMISSION"))
            txns.append(_mk_txn(adv, m, "CASH|CD", accounts[7], 19,
                                round(210 + ai * 30, 2), file_key="ace",
                                description="BROKERED CD COMMISSION"))
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
            # 9X deleted booking (EXCLUDED_CHANGE driver, FIX_SPEC_R3 T1-2): a
            # 500 MFT trail booking is credited in Apr, then deleted (9X) in
            # May; the deletion marker persists in Jun. Apr->May credited
            # genuinely loses 500 and EXCLUDED_CHANGE claims exactly that;
            # May->Jun the excluded amount is unchanged, so no driver fires.
            if adv == "SMPL003":
                deleted = m != "202604"
                txns.append(_mk_txn(adv, m, "MFT|12B1", accounts[6], 20, 500.0,
                                    rate_bps=25.0, file_key="mf_12b1",
                                    description="TRAIL BOOKING"
                                                + (" (DELETED)" if deleted else ""),
                                    reason="9X" if deleted else ""))
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


def main() -> int:
    txns = build_transactions()
    # Sample account attributes are fabricated (deterministically from the
    # account number) — that fabrication stays HERE, not in the shared builder;
    # the real builder writes only what the extracts actually contain.
    account_ids = sorted({t["account_no"] for t in txns})
    accounts = [{"account_no": a, "account_typ": "BROKERAGE" if int(a[-1]) % 2 else "ADVISORY",
                 "wrap_flg": "Y" if int(a[-1]) % 2 == 0 else "N", "data_source": "REAL"}
                for a in account_ids]

    try:
        summary = build_dataset(
            out_dir=OUT, manifest_path=MANIFEST,
            month_ids=MONTHS, billable_days=BILLABLE_DAYS,
            txns=txns, advisors=ADVISORS, classes=CLASSES,
            lines=LINES, groups=GROUPS, products=PRODUCTS,
            accounts=accounts, ctx=CTX,
        )
    except ReconciliationError as exc:
        print(exc)
        return 1

    print(f"transactions: {len(txns)}  mpr: {len(summary['mpr'])}  "
          f"changes: {len(summary['changes'])}  drivers: {len(summary['drivers'])}")
    print("eligibility mix:", summary["split_sizes"])
    print("reconciliation:", json.dumps(summary["report"]["transitions"], indent=2)[:400], "…")
    print("MIX share:", json.dumps(summary["mix_share"], indent=2))
    print(f"account presence (ACCOUNT_ABSENCE_MONTHS={summary['absence_months']}):",
          json.dumps(summary["account_presence"], indent=2))
    print("causes exercised:", sorted({d["cause_id"] for d in summary["drivers"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
