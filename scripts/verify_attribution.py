"""Round 6 attribution verification (FIX_SPEC_R6 A4).

Runs entirely on fixtures + the committed sample data set — NO real client data
is available here, so the real-data acceptance (MIX < 15% on the operator's
build) remains an OPERATOR step; this script proves the mechanism.

1. BUG REPRODUCTION — a real-shaped fixture (accounts trading intermittently in
   a transactional group with month-to-month composition shift, consistently in
   Managed) is attributed with the PRE-R6 rules (legacy_two_month_presence):
   MIX must exceed 90% of the first transition's change, BASELINE_LIMITED must
   over-claim (|BL| > |total change|), and large symmetric NEW/LOST_ACCOUNT
   must appear on the transactional group — the three symptoms from the first
   real-data build.
2. FIX PROOF — the same fixture under the R6 rules: MIX < 15% on EVERY
   transition, reconciliation $0.00, account drivers only on recurring-class
   groups, persistence honoured (an account skipping one month is NOT lost/new),
   |BL| <= |total change|.
3. GUARD PROOF — a crafted over-claim raises AttributionError (build fails
   loudly rather than publishing).
4. SAMPLE SET — the committed data/sample driver rows satisfy the same gates.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.drivers.attribution import (
    DEFAULT_ACCOUNT_ABSENCE_MONTHS,
    AttributionError,
    attribute_transition,
    reconcile,
)
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import (
    TOTAL_GROUP,
    EligibilityContext,
    aggregate_monthly,
    compute_changes,
    split_by_eligibility,
)

MONTHS = ["202604", "202605", "202606"]
BILLABLE_DAYS = {m: 22 for m in MONTHS}  # equal on purpose — no BILLABLE_DAYS noise
ADVISOR = "DFIX001"

# Fixture hierarchy: one recurring group (Managed/UMA) + one transactional
# (Equities) — the minimal real shape the account-presence rule must respect.
PRODUCTS = [
    ("UMA|FEE", "UMA", "FEE", "UMA FEE", "unified_managed_account", "PRODUCT_TYPE"),
    ("EQ|COMM", "EQ", "COMM", "EQ COMM", "equities", "PRODUCT_TYPE"),
]
PRODUCT_GROUP = {p[0]: p[4] for p in PRODUCTS}
GROUP_LINE = {"unified_managed_account": "managed", "equities": "equities_and_options"}
LINE_CLASS = {"managed": "RECURRING", "equities_and_options": "NON_RECURRING"}
RECURRING_GROUPS = {g for g, l in GROUP_LINE.items() if LINE_CLASS[l] == "RECURRING"}

REASONS = elig.reason_map()
CTX = EligibilityContext(
    reasons=REASONS,
    product_grid_type={p[0]: p[5] for p in PRODUCTS},
    credited_grid_types=frozenset({"PRODUCT_TYPE"}),
    max_processing_days=90,
)

_counter = [0]


def txn(month: str, product_id: str, account: str, amount: float,
        rate_bps: float = 0.0) -> dict:
    _counter[0] += 1
    day = f"{month[:4]}-{month[4:6]}-15"
    return {
        "txn_id": f"FIXTRD{_counter[0]:05d}|1", "trade_ref_no": f"FIXTRD{_counter[0]:05d}",
        "split_seq_no": 1, "advisor_sid": ADVISOR, "month_id": month,
        "product_id": product_id, "account_no": account,
        "trade_dt": f"{day} 00:00:00", "proc_dt": f"{day} 00:00:00",
        "credited_amt": round(amount, 2), "pre_split_amt": round(amount, 2),
        "split_pct": 1.0, "client_rate_bps": rate_bps, "std_tier_rate": rate_bps,
        "concession_type": "None", "discount_amt": 0.0, "eff_disc_pct": 0.0,
        "avg_balance_amt": 0.0, "file_key": "ace", "trade_description": "FIXTURE ROW",
        "rev_nature": "RECURRING", "reason_cd": "__NONE__",
        "rm_sid": "", "cs_sid": "",
        "revenue_eligibility": elig.reason_eligibility("__NONE__", REASONS),
        "incentive_eligible": elig.incentive_eligible("__NONE__", REASONS),
        "days_to_process": 0, "posting_month_id": month, "data_source": "REAL",
    }


def make_fixture() -> list[dict]:
    """Real-shaped: Managed bills consistently; Equities accounts trade
    intermittently with COMPOSITION SHIFT (exiting accounts traded big,
    entering accounts trade small, continuing accounts grew) — exactly the
    pattern the two-month presence test misreads as account gains/losses."""
    txns: list[dict] = []
    # --- Managed (recurring, rate 80bps everywhere — no FEE_RATE noise)
    for m in MONTHS:
        for i in range(6):  # 6 stable accounts, flat $5,000/month
            txns.append(txn(m, "UMA|FEE", f"FIXM-STAB{i}", 5000.0, 80.0))
    txns.append(txn("202604", "UMA|FEE", "FIXM-LOST", 4000.0, 80.0))     # Apr only -> LOST on Apr->May
    txns.append(txn("202606", "UMA|FEE", "FIXM-NEW", 4500.0, 80.0))      # Jun only -> NEW on May->Jun
    txns.append(txn("202604", "UMA|FEE", "FIXM-SKIP", 300.0, 80.0))      # skips May -> NOT lost/new
    txns.append(txn("202606", "UMA|FEE", "FIXM-SKIP", 310.0, 80.0))
    txns.append(txn("202604", "UMA|FEE", "FIXM-BLST", 1500.0, 80.0))     # stops after May -> only one
    txns.append(txn("202605", "UMA|FEE", "FIXM-BLST", 1500.0, 80.0))     # loaded month follows -> BL
    # --- Equities (transactional): 10 continuing accounts + 10 month-only
    # accounts per month; group total flat at $100k while composition shifts.
    cont = {"202604": 4000.0, "202605": 6000.0, "202606": 5000.0}
    only = {"202604": 6000.0, "202605": 4000.0, "202606": 5000.0}
    for mi, m in enumerate(MONTHS):
        for i in range(10):
            txns.append(txn(m, "EQ|COMM", f"FIXE-CONT{i}", cont[m]))
            txns.append(txn(m, "EQ|COMM", f"FIXE-M{mi}X{i}", only[m]))
    return txns


def attribute(txns: list[dict], *, legacy: bool) -> tuple[list[dict], list[dict]]:
    """The exact per-transition flow app/v2/dataset/builder.py runs."""
    split = split_by_eligibility(txns, CTX)
    buckets: dict[str, dict[tuple, list[dict]]] = {}
    for bucket in (elig.CREDITED, elig.NON_CREDITED, elig.LATE, elig.EXCLUDED):
        by_gm: dict[tuple, list[dict]] = defaultdict(list)
        for t in split[bucket]:
            by_gm[(PRODUCT_GROUP[t["product_id"]], t["month_id"])].append(t)
        buckets[bucket] = by_gm
    mpr = aggregate_monthly(txns, PRODUCT_GROUP, GROUP_LINE, LINE_CLASS, CTX)
    changes = compute_changes(mpr, MONTHS)
    by_tr: dict[tuple, list[dict]] = defaultdict(list)
    for c in changes:
        by_tr[(c["advisor_sid"], c["from_month_id"], c["to_month_id"])].append(c)
    drivers: list[dict] = []
    for (_adv, f, t), rows in sorted(by_tr.items()):
        drivers.extend(attribute_transition(
            rows, buckets[elig.CREDITED], RECURRING_GROUPS,
            BILLABLE_DAYS[f], BILLABLE_DAYS[t],
            nc_txns_by_group_month=buckets[elig.NON_CREDITED],
            late_txns_by_group_month=buckets[elig.LATE],
            excl_txns_by_group_month=buckets[elig.EXCLUDED],
            loaded_month_ids=MONTHS,
            absence_months=DEFAULT_ACCOUNT_ABSENCE_MONTHS,
            legacy_two_month_presence=legacy,
        ))
    return changes, drivers


def per_transition(changes: list[dict], drivers: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    totals = {(c["advisor_sid"], c["from_month_id"], c["to_month_id"]): float(c["change_amt"])
              for c in changes if c["group_id"] == TOTAL_GROUP}
    for key, total in sorted(totals.items()):
        rows = [d for d in drivers if tuple(d["driver_id"].split("|")[:3]) == key]
        by_cause: dict[str, float] = defaultdict(float)
        for d in rows:
            by_cause[d["cause_id"]] += float(d["contribution_amt"])
        out["|".join(key)] = {"total": round(total, 2), "rows": rows,
                              "by_cause": {k: round(v, 2) for k, v in by_cause.items()}}
    return out


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS" if cond else "FAIL"), name, detail)
        if not cond:
            failures.append(name)

    txns = make_fixture()
    print(f"fixture: {len(txns)} transactions, "
          f"{len({t['account_no'] for t in txns})} accounts, months {MONTHS[0]}..{MONTHS[-1]}\n")

    # ---------------------------------------------------------------- 1. bug repro
    print("— legacy (pre-R6) rules: the fixture must REPRODUCE the bug —")
    changes, legacy_drivers = attribute(txns, legacy=True)
    legacy = per_transition(changes, legacy_drivers)
    first = legacy[f"{ADVISOR}|202604|202605"]
    mix_pct = abs(first["by_cause"].get("MIX", 0.0)) / abs(first["total"]) * 100
    print(f"  first transition: total {first['total']:,.2f}  by cause {first['by_cause']}")
    check("legacy: MIX > 90% of the first transition's change",
          mix_pct > 90.0, f"{mix_pct:.1f}%")
    bl = first["by_cause"].get("BASELINE_LIMITED", 0.0)
    check("legacy: BASELINE_LIMITED over-claims (|BL| > |total change|)",
          abs(bl) > abs(first["total"]), f"BL {bl:,.2f} vs total {first['total']:,.2f}")
    second = legacy[f"{ADVISOR}|202605|202606"]
    eq_lost = sum(float(d["contribution_amt"]) for d in second["rows"]
                  if d["cause_id"] == "LOST_ACCOUNT" and d["group_id"] == "equities")
    eq_new = sum(float(d["contribution_amt"]) for d in second["rows"]
                 if d["cause_id"] == "NEW_ACCOUNT" and d["group_id"] == "equities")
    print(f"  second transition: by cause {second['by_cause']}")
    check("legacy: large symmetric NEW/LOST on the TRANSACTIONAL group",
          eq_lost <= -40000 and eq_new >= 40000,
          f"equities LOST {eq_lost:,.2f} / NEW {eq_new:,.2f}")

    # ---------------------------------------------------------------- 2. fix proof
    print("\n— R6 rules on the SAME fixture: the fix must hold —")
    changes, drivers = attribute(txns, legacy=False)
    fixed = per_transition(changes, drivers)
    worst = 0.0
    for key, tr in fixed.items():
        pct = abs(tr["by_cause"].get("MIX", 0.0)) / abs(tr["total"]) * 100
        worst = max(worst, pct)
        print(f"  {key}: total {tr['total']:>10,.2f}  MIX {pct:5.1f}%  by cause {tr['by_cause']}")
    check("fixed: MIX < 15% on EVERY transition (was >90%)", worst < 15.0,
          f"worst {worst:.1f}%")
    rec = reconcile(changes, drivers)
    check("fixed: reconciliation $0.00 on every transition", rec["all_reconcile"],
          json.dumps({k: v["discrepancy"] for k, v in rec["transitions"].items()}))
    bad_groups = sorted({d["group_id"] for d in drivers
                         if d["cause_id"] in ("NEW_ACCOUNT", "LOST_ACCOUNT", "BASELINE_LIMITED")
                         and d["group_id"] not in RECURRING_GROUPS})
    check("fixed: account drivers ONLY on recurring-class groups", not bad_groups,
          str(bad_groups))
    for key, tr in fixed.items():
        bl = tr["by_cause"].get("BASELINE_LIMITED", 0.0)
        if abs(bl) > abs(tr["total"]) + 1.0:
            check(f"fixed: |BL| <= |total| on {key}", False, f"{bl:,.2f} vs {tr['total']:,.2f}")
    presence_accounts = set()
    for d in drivers:
        if d["cause_id"] in ("NEW_ACCOUNT", "LOST_ACCOUNT", "BASELINE_LIMITED"):
            inputs = json.loads(d["inputs_json"])
            for k in ("accounts", "accounts_present_only_in_to_month",
                      "accounts_present_only_in_from_month"):
                presence_accounts.update(inputs.get(k) or [])
    check("fixed: intermittent account (skips one month) claimed by NO account driver",
          "FIXM-SKIP" not in presence_accounts, sorted(presence_accounts))
    first_f = fixed[f"{ADVISOR}|202604|202605"]
    check("fixed: genuinely-quiet account IS lost on Apr->May (persistence satisfied)",
          "FIXM-LOST" in presence_accounts
          and round(first_f["by_cause"].get("LOST_ACCOUNT", 0.0), 2) == -4000.00,
          str(first_f["by_cause"].get("LOST_ACCOUNT")))
    second_f = fixed[f"{ADVISOR}|202605|202606"]
    check("fixed: genuinely-new account IS new on May->Jun (quiet Apr+May confirmed)",
          round(second_f["by_cause"].get("NEW_ACCOUNT", 0.0), 2) == 4500.00,
          str(second_f["by_cause"].get("NEW_ACCOUNT")))
    check("fixed: unevaluable stop (only 1 loaded month follows) -> BASELINE_LIMITED, May->Jun",
          round(second_f["by_cause"].get("BASELINE_LIMITED", 0.0), 2) == -1500.00,
          str(second_f["by_cause"].get("BASELINE_LIMITED")))
    check("fixed: no BASELINE_LIMITED on the first transition "
          "(naive-new accounts were transactional-only, so nothing is unevaluable there)",
          "BASELINE_LIMITED" not in first_f["by_cause"],
          str(first_f["by_cause"].get("BASELINE_LIMITED")))

    # ---------------------------------------------------------------- 3. guard
    print("\n— A3 guard: a BL over-claim must fail the build loudly —")
    guard = [t for t in txns if t["account_no"] != "FIXM-BLST"]
    # FIXM-GUARD bills Apr+May at $9,000 and stops; equities May->Jun swings
    # +8,000 so the total change is small — BL (-9,000) must exceed it.
    guard.append(txn("202604", "UMA|FEE", "FIXM-GUARD", 9000.0, 80.0))
    guard.append(txn("202605", "UMA|FEE", "FIXM-GUARD", 9000.0, 80.0))
    guard.append(txn("202606", "EQ|COMM", "FIXE-CONT0", 8000.0))
    try:
        attribute(guard, legacy=False)
        check("AttributionError raised on |BL| > |total change|", False, "no exception")
    except AttributionError as exc:
        check("AttributionError raised on |BL| > |total change|", True, str(exc)[:80])

    # ---------------------------------------------------------------- 4. sample set
    print("\n— committed sample data set —")
    sample = Path("data/sample/vertices")
    with (sample / "phx_dm_v2_revenue_driver.csv").open(newline="", encoding="utf-8-sig") as f:
        driver_rows = list(csv.DictReader(f))
    with (sample / "phx_dm_v2_revenue_change.csv").open(newline="", encoding="utf-8-sig") as f:
        change_rows = list(csv.DictReader(f))
    with (sample / "phx_dm_v2_monthly_product_revenue.csv").open(newline="", encoding="utf-8-sig") as f:
        group_class = {r["group_id"]: r["class_id"] for r in csv.DictReader(f)}
    totals = {(r["advisor_sid"], r["from_month_id"], r["to_month_id"]): float(r["change_amt"])
              for r in change_rows if r["group_id"] == TOTAL_GROUP}
    mix_sum: dict[tuple, float] = defaultdict(float)
    for r in driver_rows:
        if r["cause_id"] == "MIX":
            mix_sum[tuple(r["driver_id"].split("|")[:3])] += float(r["contribution_amt"])
    worst_s = max(abs(mix_sum.get(k, 0.0)) / abs(v) * 100 for k, v in totals.items())
    check("sample: MIX < 15% on every transition", worst_s < 15.0, f"worst {worst_s:.1f}%")
    bad_sample = sorted({r["group_id"] for r in driver_rows
                         if r["cause_id"] in ("NEW_ACCOUNT", "LOST_ACCOUNT", "BASELINE_LIMITED")
                         and group_class.get(r["group_id"]) != "RECURRING"})
    check("sample: account drivers only on recurring-class groups", not bad_sample,
          str(bad_sample))

    print("\nNOTE: this proves the MECHANISM on fixtures + sample only. The real-data "
          "acceptance (MIX < 15% on every transition of the client build) is an "
          "OPERATOR step — run scripts/build_real_data.py and read its summary.")
    print("\nOVERALL:", "PASS" if not failures else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
