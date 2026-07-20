"""Driver attribution (EXTRACTION_SPEC §7).

Decomposes each (advisor, transition, product group) change_amt into causes.
Sequential consumption: each step claims part of the change and removes its
transactions from later steps; the remainder falls to MIX, so contributions
always reconcile to change_amt by construction. An independent reconciliation
check (reconcile()) still validates every transition to $1.

Pure deterministic Python. Every number an attribution used lands in
inputs_json — that is what the evidence modal's calculation table renders.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable

from app.v2.revenue.aggregation import ONE_TIME, RECURRING, TOTAL_GROUP, _num

# Groups billed quarterly (TIMING candidates). Sample + known client hierarchy.
QUARTERLY_BILLED_GROUPS = {"alternative_investments", "alternatives"}

# Causes whose contribution is DUMMY until a data source exists.
DUMMY_CAUSES = ("MARKET", "NET_FLOW")

RECONCILE_TOLERANCE = 1.0  # dollars

CAUSE_DATA_SOURCE = {
    "VOLUME": "REAL", "ONE_TIME": "REAL", "TIMING": "REAL", "FEE_RATE": "REAL",
    "DISCOUNT": "REAL", "BILLABLE_DAYS": "DERIVED", "MIX": "DERIVED",
    "NEW_ACCOUNT": "REAL", "LOST_ACCOUNT": "REAL", "CLAWBACK": "REAL",
    "MARKET": "DUMMY", "NET_FLOW": "DUMMY",
}


def _sum(txns: Iterable[dict]) -> float:
    return sum(_num(t.get("credited_amt")) for t in txns)


def _weighted_rate(txns: list[dict]) -> float:
    base = sum(_num(t.get("credited_amt")) for t in txns
               if _num(t.get("credited_amt")) > 0 and _num(t.get("client_rate_bps")) > 0)
    if not base:
        return 0.0
    weight = sum(_num(t.get("client_rate_bps")) * _num(t.get("credited_amt")) for t in txns
                 if _num(t.get("credited_amt")) > 0 and _num(t.get("client_rate_bps")) > 0)
    return weight / base


def attribute_group(
    change: dict,
    from_txns: list[dict],
    to_txns: list[dict],
    is_recurring_class: bool,
    from_billable_days: int,
    to_billable_days: int,
    advisor_new_accounts: set[str] | None = None,
    advisor_lost_accounts: set[str] | None = None,
) -> list[dict]:
    """Driver rows (without ids/rank — assigned per transition) for one group's
    change. Steps per EXTRACTION_SPEC §7; MIX absorbs the remainder."""
    drivers: list[dict] = []
    change_amt = _num(change["change_amt"])
    claimed = 0.0

    def emit(cause: str, contribution: float, inputs: dict, data_source: str | None = None) -> None:
        nonlocal claimed
        contribution = round(contribution, 2)
        if cause not in DUMMY_CAUSES and abs(contribution) < 0.005:
            return
        claimed += contribution
        drivers.append({
            "cause_id": cause,
            "group_id": change["group_id"],
            "contribution_amt": contribution,
            "direction": "UP" if contribution >= 0 else "DOWN",
            "inputs_json": json.dumps(inputs, sort_keys=True),
            "data_source": data_source or CAUSE_DATA_SOURCE[cause],
        })

    # 1. NEW_ACCOUNT / LOST_ACCOUNT — accounts present in one month only AT THE
    # ADVISOR LEVEL. An account that merely starts or stops one product while
    # trading elsewhere is product behaviour (ONE_TIME/TIMING/MIX), not an
    # account opening/closure — judging presence per group would swallow those
    # causes into NEW/LOST_ACCOUNT.
    from_accounts = {str(t.get("account_no")) for t in from_txns}
    to_accounts = {str(t.get("account_no")) for t in to_txns}
    adv_new = advisor_new_accounts if advisor_new_accounts is not None else (to_accounts - from_accounts)
    adv_lost = advisor_lost_accounts if advisor_lost_accounts is not None else (from_accounts - to_accounts)
    new_accounts = sorted((to_accounts - from_accounts) & adv_new)
    lost_accounts = sorted((from_accounts - to_accounts) & adv_lost)
    if new_accounts:
        new_txns = [t for t in to_txns if str(t.get("account_no")) in new_accounts]
        emit("NEW_ACCOUNT", _sum(new_txns), {
            "accounts": new_accounts, "txn_count": len(new_txns),
            "to_month_revenue_of_new_accounts": round(_sum(new_txns), 2),
            "formula": "sum(credited_amt of accounts contributing this month but not last)",
        })
    if lost_accounts:
        lost_txns = [t for t in from_txns if str(t.get("account_no")) in lost_accounts]
        emit("LOST_ACCOUNT", -_sum(lost_txns), {
            "accounts": lost_accounts, "txn_count": len(lost_txns),
            "from_month_revenue_of_lost_accounts": round(_sum(lost_txns), 2),
            "formula": "-(sum(credited_amt of accounts contributing last month but not this))",
        })
    claimed_accounts = set(new_accounts) | set(lost_accounts)
    rem_from = [t for t in from_txns if str(t.get("account_no")) not in claimed_accounts]
    rem_to = [t for t in to_txns if str(t.get("account_no")) not in claimed_accounts]

    # 2. ONE_TIME — rev_nature ONE_TIME delta among remaining rows.
    from_ot = [t for t in rem_from if t.get("rev_nature") == ONE_TIME]
    to_ot = [t for t in rem_to if t.get("rev_nature") == ONE_TIME]
    if from_ot or to_ot:
        emit("ONE_TIME", _sum(to_ot) - _sum(from_ot), {
            "from_one_time": round(_sum(from_ot), 2), "to_one_time": round(_sum(to_ot), 2),
            "from_txn_count": len(from_ot), "to_txn_count": len(to_ot),
            "file_keys": sorted({str(t.get("file_key")) for t in from_ot + to_ot}),
            "formula": "to_one_time - from_one_time",
        })
    rem_from = [t for t in rem_from if t.get("rev_nature") != ONE_TIME]
    rem_to = [t for t in rem_to if t.get("rev_nature") != ONE_TIME]

    # 3. CLAWBACK — change in negative-amount rows among the remainder.
    from_neg = [t for t in rem_from if _num(t.get("credited_amt")) < 0]
    to_neg = [t for t in rem_to if _num(t.get("credited_amt")) < 0]
    if from_neg or to_neg:
        emit("CLAWBACK", _sum(to_neg) - _sum(from_neg), {
            "from_negative_total": round(_sum(from_neg), 2), "to_negative_total": round(_sum(to_neg), 2),
            "from_negative_rows": len(from_neg), "to_negative_rows": len(to_neg),
            "formula": "to_negative_total - from_negative_total",
        })
    rem_from = [t for t in rem_from if _num(t.get("credited_amt")) >= 0]
    rem_to = [t for t in rem_to if _num(t.get("credited_amt")) >= 0]

    # 4. TIMING — quarterly-billed group present in exactly one month.
    if change["group_id"] in QUARTERLY_BILLED_GROUPS and bool(rem_from) != bool(rem_to):
        emit("TIMING", _sum(rem_to) - _sum(rem_from), {
            "from_revenue": round(_sum(rem_from), 2), "to_revenue": round(_sum(rem_to), 2),
            "billing_cycle": "quarterly",
            "formula": "to_revenue - from_revenue (quarterly billing falls in one month only)",
        })
        rem_from, rem_to = [], []

    # 5. FEE_RATE — effective rate movement on the remaining recurring base.
    from_rate = _weighted_rate(rem_from)
    to_rate = _weighted_rate(rem_to)
    if from_rate > 0 and to_rate > 0 and abs(to_rate - from_rate) > 1e-6:
        from_rev = _sum(rem_from)
        assets_proxy = from_rev / (from_rate / 10000.0)
        emit("FEE_RATE", assets_proxy * (to_rate - from_rate) / 10000.0, {
            "from_avg_rate_bps": round(from_rate, 4), "to_avg_rate_bps": round(to_rate, 4),
            "from_revenue": round(from_rev, 2), "assets_proxy": round(assets_proxy, 2),
            "formula": "assets_proxy * (to_avg_rate_bps - from_avg_rate_bps) / 10000; "
                       "assets_proxy = from_revenue / (from_avg_rate_bps/10000)",
        })

    # 6. DISCOUNT — change in discounting (more discount -> negative contribution).
    from_disc = sum(_num(t.get("discount_amt")) for t in rem_from)
    to_disc = sum(_num(t.get("discount_amt")) for t in rem_to)
    from_disc_rows = sum(1 for t in rem_from if str(t.get("concession_type")) == "Discount")
    to_disc_rows = sum(1 for t in rem_to if str(t.get("concession_type")) == "Discount")
    if abs(to_disc - from_disc) > 0.005:
        emit("DISCOUNT", from_disc - to_disc, {
            "from_discount_total": round(from_disc, 2), "to_discount_total": round(to_disc, 2),
            "from_discount_rows": from_disc_rows, "to_discount_rows": to_disc_rows,
            "formula": "from_discount_total - to_discount_total (growth in discounting reduces revenue)",
        })

    # 7. BILLABLE_DAYS — recurring/fee-based groups only. DERIVED.
    if is_recurring_class and from_billable_days and to_billable_days != from_billable_days:
        from_rev = _sum(rem_from)
        emit("BILLABLE_DAYS", from_rev * (to_billable_days - from_billable_days) / from_billable_days, {
            "from_billable_days": from_billable_days, "to_billable_days": to_billable_days,
            "from_revenue": round(from_rev, 2),
            "formula": "from_revenue * (to_billable_days - from_billable_days) / from_billable_days",
        })

    # 8. VOLUME — transaction-based (non-recurring-class) groups.
    if not is_recurring_class and rem_from:
        from_count, to_count = len(rem_from), len(rem_to)
        if from_count and to_count != from_count:
            avg_value = _sum(rem_from) / from_count
            emit("VOLUME", (to_count - from_count) * avg_value, {
                "from_txn_count": from_count, "to_txn_count": to_count,
                "from_avg_txn_value": round(avg_value, 2),
                "formula": "(to_txn_count - from_txn_count) * from_avg_txn_value",
            })

    # 11. MIX — the remainder, so contributions always reconcile.
    remainder = round(change_amt - claimed, 2)
    if abs(remainder) >= 0.005:
        emit("MIX", remainder, {
            "change_amt": round(change_amt, 2),
            "sum_of_attributed_causes": round(claimed - remainder, 2),
            "formula": "change_amt - sum(all attributed causes)",
        })
    return drivers


def attribute_transition(
    changes: list[dict],
    txns_by_group_month: dict[tuple[str, str], list[dict]],
    recurring_class_groups: set[str],
    from_billable_days: int,
    to_billable_days: int,
) -> list[dict]:
    """All driver rows for one transition (advisor + from/to months).

    `changes` are that transition's revenue_change rows (groups + __TOTAL__).
    Group-level drivers attach to their group's change row; MARKET and NET_FLOW
    are emitted once per transition on the __TOTAL__ row (contribution 0, DUMMY)
    so the missing data sources stay visible. rank is global per transition by
    |contribution| descending; contribution_pct is the share of the transition's
    total change."""
    total_row = next(c for c in changes if c["group_id"] == TOTAL_GROUP)
    total_change = _num(total_row["change_amt"])
    from_month, to_month = total_row["from_month_id"], total_row["to_month_id"]
    raw: list[tuple[dict, dict]] = []  # (change_row, driver)

    # Advisor-level account presence for the NEW/LOST_ACCOUNT test.
    from_all: set[str] = set()
    to_all: set[str] = set()
    for (_g, month), txns in txns_by_group_month.items():
        if month == from_month:
            from_all.update(str(t.get("account_no")) for t in txns)
        elif month == to_month:
            to_all.update(str(t.get("account_no")) for t in txns)
    advisor_new = to_all - from_all
    advisor_lost = from_all - to_all

    for change in changes:
        if change["group_id"] == TOTAL_GROUP:
            continue
        group_id = change["group_id"]
        from_txns = txns_by_group_month.get((group_id, change["from_month_id"]), [])
        to_txns = txns_by_group_month.get((group_id, change["to_month_id"]), [])
        for d in attribute_group(
            change, from_txns, to_txns,
            is_recurring_class=group_id in recurring_class_groups,
            from_billable_days=from_billable_days,
            to_billable_days=to_billable_days,
            advisor_new_accounts=advisor_new,
            advisor_lost_accounts=advisor_lost,
        ):
            raw.append((change, d))

    for cause in DUMMY_CAUSES:
        raw.append((total_row, {
            "cause_id": cause,
            "group_id": TOTAL_GROUP,
            "contribution_amt": 0.0,
            "direction": "UP",
            "inputs_json": json.dumps({
                "contribution": 0.0,
                "reason": ("no index-return source" if cause == "MARKET"
                           else "flows feed stops 2026-01-30"),
            }, sort_keys=True),
            "data_source": "DUMMY",
        }))

    raw.sort(key=lambda cd: -abs(_num(cd[1]["contribution_amt"])))
    seq_by_change: dict[str, int] = defaultdict(int)
    drivers = []
    for rank, (change, d) in enumerate(raw, start=1):
        seq_by_change[change["change_id"]] += 1
        drivers.append({
            "driver_id": f"{change['change_id']}|{d['cause_id']}|{seq_by_change[change['change_id']]}",
            "change_id": change["change_id"],
            "cause_id": d["cause_id"],
            "group_id": d["group_id"],
            "contribution_amt": d["contribution_amt"],
            "contribution_pct": round(_num(d["contribution_amt"]) / total_change * 100, 2) if total_change else 0.0,
            "direction": d["direction"],
            "rank": rank,
            "inputs_json": d["inputs_json"],
            "data_source": d["data_source"],
        })
    return drivers


def reconcile(changes: list[dict], drivers: list[dict]) -> dict:
    """Independent check (ABSOLUTE RULE 7): Σ driver contributions of a
    transition == the transition's __TOTAL__ change_amt within $1."""
    total_by_transition: dict[tuple, float] = {}
    for c in changes:
        if c["group_id"] == TOTAL_GROUP:
            total_by_transition[(c["advisor_sid"], c["from_month_id"], c["to_month_id"])] = _num(c["change_amt"])
    driver_sum: dict[tuple, float] = defaultdict(float)
    for d in drivers:
        advisor, from_m, to_m, _group = d["change_id"].split("|")
        driver_sum[(advisor, from_m, to_m)] += _num(d["contribution_amt"])

    transitions = {}
    for key, total in sorted(total_by_transition.items()):
        attributed = round(driver_sum.get(key, 0.0), 2)
        discrepancy = round(total - attributed, 2)
        transitions["|".join(key)] = {
            "total_change": round(total, 2),
            "attributed": attributed,
            "discrepancy": discrepancy,
            "reconciles": abs(discrepancy) <= RECONCILE_TOLERANCE,
        }
    return {
        "all_reconcile": all(t["reconciles"] for t in transitions.values()),
        "tolerance_usd": RECONCILE_TOLERANCE,
        "transitions": transitions,
    }
