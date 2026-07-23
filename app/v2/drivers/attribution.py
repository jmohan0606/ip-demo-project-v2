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
import logging
from collections import defaultdict
from typing import Iterable

from app.v2.revenue.aggregation import ONE_TIME, RECURRING, TOTAL_GROUP, _num

logger = logging.getLogger(__name__)

# Groups billed quarterly (TIMING candidates). Sample + known client hierarchy.
QUARTERLY_BILLED_GROUPS = {"alternative_investments", "alternatives"}

# Causes whose contribution is DUMMY until a data source exists.
DUMMY_CAUSES = ("MARKET", "NET_FLOW")

RECONCILE_TOLERANCE = 1.0  # dollars

# T1-3: |MIX| above this fraction of a transition's absolute total change logs
# a WARNING — MIX is a residual of last resort, and a large one means a named
# driver is missing or mis-specified. Self-check only; never blocks.
MIX_WARNING_FRACTION = 0.15

# R6 A2 — an account only counts as LOST after this many consecutive months of
# no activity following the from-month (and symmetrically NEW requires this
# many quiet months before appearing). A single quiet month is ordinary trading
# intermittency, not attrition. Config: settings.account_absence_months
# (ACCOUNT_ABSENCE_MONTHS); this is only the shared default.
DEFAULT_ACCOUNT_ABSENCE_MONTHS = 2

CAUSE_DATA_SOURCE = {
    "VOLUME": "REAL", "ONE_TIME": "REAL", "ELIGIBILITY": "REAL",
    "LATE_PROCESSING": "REAL", "EXCLUDED_CHANGE": "REAL", "TIMING": "REAL",
    "FEE_RATE": "REAL", "DISCOUNT": "REAL", "BILLABLE_DAYS": "DERIVED", "MIX": "DERIVED",
    "NEW_ACCOUNT": "REAL", "LOST_ACCOUNT": "REAL", "CLAWBACK": "REAL",
    "MARKET": "DUMMY", "NET_FLOW": "DUMMY",
    # R5 D1 / R6 A3 — the account-presence (new/lost) test cannot be evaluated
    # because the loaded data does not span enough months on one side of the
    # transition; the amount those accounts moved is honest-limited, not claimed.
    "BASELINE_LIMITED": "DERIVED",
}


class AttributionError(RuntimeError):
    """A driver claimed more than the data can support (R6 A3 sanity rule) —
    fail the build loudly rather than publish an over-claiming attribution."""


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
    bl_new_accounts: set[str] | None = None,
    bl_lost_accounts: set[str] | None = None,
    presence_rule: dict | None = None,
    gate_to_recurring: bool = True,
    from_nc_txns: list[dict] | None = None,
    to_nc_txns: list[dict] | None = None,
    from_late_txns: list[dict] | None = None,
    to_late_txns: list[dict] | None = None,
    from_excl_txns: list[dict] | None = None,
    to_excl_txns: list[dict] | None = None,
    max_processing_days: int = 90,
) -> list[dict]:
    """Driver rows (without ids/rank — assigned per transition) for one group's
    change. Steps per EXTRACTION_SPEC §7 plus ELIGIBILITY (FIX_SPEC R1-8),
    LATE_PROCESSING and EXCLUDED_CHANGE (FIX_SPEC_R3 T1) immediately after it;
    MIX absorbs the remainder.

    from_txns/to_txns are the group's CREDITED transactions (the ones inside
    the revenue figure). from_nc_txns/to_nc_txns are its NON_CREDITED
    transactions — revenue that exists but is outside credited (9E small
    households, 9G transferred accounts, ...); their month-over-month movement
    is the ELIGIBILITY effect on credited revenue. from/to_late_txns are the
    LATE bucket (90-day rule) and from/to_excl_txns the EXCLUDED bucket (e.g.
    9X deleted rows) — each subtrahend of the credited
    identity gets its own named driver so its movement never falls to MIX.
    OUT_OF_GRID needs no driver by construction: grid_type is a static product
    attribute and CREDITED_GRID_TYPES is fixed config, so out-of-grid revenue
    cannot move into or out of credited month over month (verified by the
    OUT_OF_GRID composition check in scripts/verify_end_to_end.py)."""
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
    #
    # R6 A1 — the step runs ONLY for recurring-class groups (Managed, Trails),
    # where an account genuinely should bill every month and absence is a real
    # event. In transactional groups absence is ordinary trading intermittency;
    # VOLUME/ONE_TIME/TIMING already explain the change there, so no account
    # driver (and no BASELINE_LIMITED) is emitted for them.
    #
    # R6 A2 — the advisor_new/advisor_lost sets passed in are PERSISTENCE
    # FILTERED by attribute_transition: an account counts as lost only after
    # ACCOUNT_ABSENCE_MONTHS consecutive quiet months (symmetric for new).
    # bl_new/bl_lost hold the accounts whose presence test CANNOT be evaluated
    # because the loaded data does not span enough months on that side of the
    # transition — their movement goes to the honest BASELINE_LIMITED driver
    # (R6 A3), never to NEW/LOST and never silently to MIX.
    claimed_accounts: set[str] = set()
    rule = presence_rule or {}
    if is_recurring_class or not gate_to_recurring:
        from_accounts = {str(t.get("account_no")) for t in from_txns}
        to_accounts = {str(t.get("account_no")) for t in to_txns}
        adv_new = advisor_new_accounts if advisor_new_accounts is not None else (to_accounts - from_accounts)
        adv_lost = advisor_lost_accounts if advisor_lost_accounts is not None else (from_accounts - to_accounts)
        new_accounts = sorted((to_accounts - from_accounts) & adv_new)
        lost_accounts = sorted((from_accounts - to_accounts) & adv_lost)
        bl_new = sorted((to_accounts - from_accounts) & (bl_new_accounts or set()))
        bl_lost = sorted((from_accounts - to_accounts) & (bl_lost_accounts or set()))
        if new_accounts:
            new_txns = [t for t in to_txns if str(t.get("account_no")) in new_accounts]
            emit("NEW_ACCOUNT", _sum(new_txns), {
                "accounts": new_accounts, "txn_count": len(new_txns),
                "to_month_revenue_of_new_accounts": round(_sum(new_txns), 2),
                "account_absence_months": rule.get("absence_months"),
                "months_confirmed_quiet_before": rule.get("new_months_checked"),
                "formula": "sum(credited_amt of accounts appearing this month after "
                           "ACCOUNT_ABSENCE_MONTHS consecutive months of no activity); "
                           "recurring-class groups only",
            })
        if lost_accounts:
            lost_txns = [t for t in from_txns if str(t.get("account_no")) in lost_accounts]
            emit("LOST_ACCOUNT", -_sum(lost_txns), {
                "accounts": lost_accounts, "txn_count": len(lost_txns),
                "from_month_revenue_of_lost_accounts": round(_sum(lost_txns), 2),
                "account_absence_months": rule.get("absence_months"),
                "months_confirmed_quiet_after": rule.get("lost_months_checked"),
                "formula": "-(sum(credited_amt of accounts with no activity for "
                           "ACCOUNT_ABSENCE_MONTHS consecutive months after the from-month)); "
                           "recurring-class groups only",
            })
        if bl_new or bl_lost:
            new_txns = [t for t in to_txns if str(t.get("account_no")) in bl_new]
            lost_txns = [t for t in from_txns if str(t.get("account_no")) in bl_lost]
            emit("BASELINE_LIMITED", _sum(new_txns) - _sum(lost_txns), {
                "accounts_present_only_in_to_month": bl_new,
                "accounts_present_only_in_from_month": bl_lost,
                "to_month_revenue_of_those_accounts": round(_sum(new_txns), 2),
                "from_month_revenue_of_those_accounts": round(_sum(lost_txns), 2),
                "account_absence_months": rule.get("absence_months"),
                "reason": rule.get("bl_reason") or (
                    "the loaded data does not span enough months to apply the "
                    "account-presence persistence test on this side of the transition"),
                "formula": "sum(credited_amt of unevaluable accounts present only in to-month) - "
                           "sum(credited_amt of unevaluable accounts present only in from-month); "
                           "recurring-class groups only — NEW/LOST_ACCOUNT need "
                           "ACCOUNT_ABSENCE_MONTHS loaded months beyond the transition",
            })
        claimed_accounts = set(new_accounts) | set(lost_accounts) | set(bl_new) | set(bl_lost)
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

    # 3. ELIGIBILITY (FIX_SPEC R1-8) — revenue that moved between credited and
    # non-credited (e.g. a household crossing the minimum-household threshold).
    # Non-credited revenue rising means credited revenue fell by that amount,
    # so the contribution to the CREDITED change is -(Δ non-credited). Accounts
    # already claimed by NEW/LOST_ACCOUNT are excluded to prevent double-count.
    nc_from = [t for t in (from_nc_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    nc_to = [t for t in (to_nc_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    if nc_from or nc_to:
        nc_delta = _sum(nc_to) - _sum(nc_from)
        reason_mix = sorted({str(t.get("reason_cd") or "") for t in nc_from + nc_to})
        emit("ELIGIBILITY", -nc_delta, {
            "from_non_credited": round(_sum(nc_from), 2),
            "to_non_credited": round(_sum(nc_to), 2),
            "from_txn_count": len(nc_from), "to_txn_count": len(nc_to),
            "reason_codes": reason_mix,
            "formula": "-(to_non_credited - from_non_credited) — revenue moving to a "
                       "non-credited reason code leaves credited revenue, and vice versa",
        })

    # 3b. LATE_PROCESSING (FIX_SPEC_R3 T1-1) — symmetric with ELIGIBILITY:
    # revenue failing the 90-day rule (proc_dt - trade_dt > MAX_PROCESSING_DAYS)
    # is in Total but outside Credited. More revenue going late this month means
    # credited fell by that amount: contribution = -(Δ late_excluded).
    late_from = [t for t in (from_late_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    late_to = [t for t in (to_late_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    if late_from or late_to:
        late_delta = _sum(late_to) - _sum(late_from)
        emit("LATE_PROCESSING", -late_delta, {
            "from_late_excluded": round(_sum(late_from), 2),
            "to_late_excluded": round(_sum(late_to), 2),
            "from_txn_count": len(late_from), "to_txn_count": len(late_to),
            "processing_days_limit": max_processing_days,
            "days_to_process_seen": sorted({int(_num(t.get("days_to_process"))) for t in late_from + late_to}),
            "formula": "-(to_late_excluded - from_late_excluded) — revenue processed more than "
                       "90 days after the trade leaves credited revenue, and vice versa",
        })

    # 3c. EXCLUDED_CHANGE (FIX_SPEC_R3 T1-2) — EXCLUDED rows (deleted bookings,
    # e.g. reason 9X) are outside every figure; a booking moving between
    # credited and excluded month over month still moves credited revenue:
    # contribution = -(Δ excluded).
    excl_from = [t for t in (from_excl_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    excl_to = [t for t in (to_excl_txns or []) if str(t.get("account_no")) not in claimed_accounts]
    if excl_from or excl_to:
        excl_delta = _sum(excl_to) - _sum(excl_from)
        excl_reasons = sorted({str(t.get("reason_cd") or "") for t in excl_from + excl_to})
        emit("EXCLUDED_CHANGE", -excl_delta, {
            "from_excluded": round(_sum(excl_from), 2),
            "to_excluded": round(_sum(excl_to), 2),
            "from_txn_count": len(excl_from), "to_txn_count": len(excl_to),
            "reason_codes": excl_reasons,
            "formula": "-(to_excluded - from_excluded) — a booking moving to an excluded "
                       "reason code (e.g. deleted) leaves credited revenue, and vice versa",
        })

    # 4. CLAWBACK — change in negative-amount rows among the remainder.
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

    # 5. TIMING — quarterly-billed group present in exactly one month.
    if change["group_id"] in QUARTERLY_BILLED_GROUPS and bool(rem_from) != bool(rem_to):
        emit("TIMING", _sum(rem_to) - _sum(rem_from), {
            "from_revenue": round(_sum(rem_from), 2), "to_revenue": round(_sum(rem_to), 2),
            "billing_cycle": "quarterly",
            "formula": "to_revenue - from_revenue (quarterly billing falls in one month only)",
        })
        rem_from, rem_to = [], []

    # 6. FEE_RATE — effective rate movement on the remaining recurring base.
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

    # 7. DISCOUNT — change in discounting (more discount -> negative contribution).
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

    # 8. BILLABLE_DAYS — recurring/fee-based groups only. DERIVED.
    if is_recurring_class and from_billable_days and to_billable_days != from_billable_days:
        from_rev = _sum(rem_from)
        emit("BILLABLE_DAYS", from_rev * (to_billable_days - from_billable_days) / from_billable_days, {
            "from_billable_days": from_billable_days, "to_billable_days": to_billable_days,
            "from_revenue": round(from_rev, 2),
            "formula": "from_revenue * (to_billable_days - from_billable_days) / from_billable_days",
        })

    # 9. VOLUME — transaction-based (non-recurring-class) groups.
    if not is_recurring_class and rem_from:
        from_count, to_count = len(rem_from), len(rem_to)
        if from_count and to_count != from_count:
            avg_value = _sum(rem_from) / from_count
            emit("VOLUME", (to_count - from_count) * avg_value, {
                "from_txn_count": from_count, "to_txn_count": to_count,
                "from_avg_txn_value": round(avg_value, 2),
                "formula": "(to_txn_count - from_txn_count) * from_avg_txn_value",
            })

    # 12. MIX — the remainder, so contributions always reconcile.
    # (MARKET and NET_FLOW — steps 10 and 11 — are emitted per transition in
    # attribute_transition as zero-contribution DUMMY drivers.)
    remainder = round(change_amt - claimed, 2)
    if abs(remainder) >= 0.005:
        emit("MIX", remainder, {
            "change_amt": round(change_amt, 2),
            "sum_of_attributed_drivers": round(claimed - remainder, 2),
            "formula": "change_amt - sum(all attributed revenue drivers)",
        })
    return drivers


def attribute_transition(
    changes: list[dict],
    txns_by_group_month: dict[tuple[str, str], list[dict]],
    recurring_class_groups: set[str],
    from_billable_days: int,
    to_billable_days: int,
    nc_txns_by_group_month: dict[tuple[str, str], list[dict]] | None = None,
    late_txns_by_group_month: dict[tuple[str, str], list[dict]] | None = None,
    excl_txns_by_group_month: dict[tuple[str, str], list[dict]] | None = None,
    mix_warning_fraction: float = MIX_WARNING_FRACTION,
    max_processing_days: int = 90,
    loaded_month_ids: list[str] | None = None,
    absence_months: int = DEFAULT_ACCOUNT_ABSENCE_MONTHS,
    legacy_two_month_presence: bool = False,
) -> list[dict]:
    """All driver rows for one transition (advisor + from/to months).

    `changes` are that transition's revenue_change rows (groups + __TOTAL__).
    `txns_by_group_month` holds the CREDITED transactions;
    `nc_txns_by_group_month` the NON_CREDITED ones (ELIGIBILITY step, R1-8);
    `late_txns_by_group_month` the LATE ones (LATE_PROCESSING, FIX_SPEC_R3 T1-1)
    and `excl_txns_by_group_month` the EXCLUDED ones (EXCLUDED_CHANGE, T1-2).
    Group-level drivers attach to their group's change row; MARKET and NET_FLOW
    are emitted once per transition on the __TOTAL__ row (contribution 0, DUMMY)
    so the missing data sources stay visible. rank is global per transition by
    |contribution| descending; contribution_pct is the share of the transition's
    total change."""
    nc_txns_by_group_month = nc_txns_by_group_month or {}
    late_txns_by_group_month = late_txns_by_group_month or {}
    excl_txns_by_group_month = excl_txns_by_group_month or {}
    total_row = next(c for c in changes if c["group_id"] == TOTAL_GROUP)
    total_change = _num(total_row["change_amt"])
    from_month, to_month = total_row["from_month_id"], total_row["to_month_id"]
    raw: list[tuple[dict, dict]] = []  # (change_row, driver)

    # Advisor-level account ACTIVITY over every loaded month, for the
    # NEW/LOST_ACCOUNT persistence test (R6 A2). Activity counts credited,
    # non-credited AND late rows: an account whose rows merely became
    # non-credited (e.g. 9E) or processed late is still trading — an
    # ELIGIBILITY / LATE_PROCESSING move, not a lost account. EXCLUDED rows
    # (deleted bookings) are not evidence of trading and do not count.
    activity: dict[str, set[str]] = defaultdict(set)
    for source in (txns_by_group_month, nc_txns_by_group_month, late_txns_by_group_month):
        for (_g, month), txns in source.items():
            for t in txns:
                activity[str(t.get("account_no"))].add(month)
    months = sorted(loaded_month_ids) if loaded_month_ids else sorted(
        {m for ms in activity.values() for m in ms} | {from_month, to_month})
    from_all = {a for a, ms in activity.items() if from_month in ms}
    to_all = {a for a, ms in activity.items() if to_month in ms}
    naive_new = to_all - from_all    # traded this month, not last (two-month test)
    naive_lost = from_all - to_all   # traded last month, not this

    presence_rule: dict = {"absence_months": absence_months}
    if legacy_two_month_presence:
        # TEST-ONLY compatibility path (scripts/verify_attribution.py uses it to
        # PROVE the round-6 bug on a fixture): the pre-R6 two-month presence
        # test, applied to every group, with the pre-R6 baseline-month routing.
        # Never use in production builds — it over-claims on real data.
        if from_month == months[0]:
            advisor_new, advisor_lost = set(), set()
            bl_new, bl_lost = naive_new, naive_lost
        else:
            advisor_new, advisor_lost = naive_new, naive_lost
            bl_new, bl_lost = set(), set()
        presence_rule["legacy_two_month_presence"] = True
    else:
        # R6 A2 — persistence: NEW requires `absence_months` loaded months of no
        # activity immediately BEFORE the to-month; LOST requires the same
        # immediately AFTER the from-month. Where the loaded range is too short
        # to check (first/last transitions), the test is UNEVALUABLE and the
        # naive-presence accounts route to BASELINE_LIMITED (R6 A3) instead —
        # only ever for recurring-class groups (gated in attribute_group).
        i, j = months.index(from_month), months.index(to_month)
        preceding = months[max(0, j - absence_months):j]
        following = months[i + 1:i + 1 + absence_months]
        new_evaluable = j >= absence_months
        lost_evaluable = i + absence_months <= len(months) - 1
        if new_evaluable:
            advisor_new = {a for a in naive_new if not (activity[a] & set(preceding))}
            bl_new = set()
        else:
            advisor_new = set()
            bl_new = naive_new
        if lost_evaluable:
            advisor_lost = {a for a in naive_lost if not (activity[a] & set(following))}
            bl_lost = set()
        else:
            advisor_lost = set()
            bl_lost = naive_lost
        presence_rule.update({
            "new_months_checked": preceding, "lost_months_checked": following,
            "new_evaluable": new_evaluable, "lost_evaluable": lost_evaluable,
        })
        if not new_evaluable and not lost_evaluable:
            presence_rule["bl_reason"] = (
                f"fewer than {absence_months} loaded months exist on either side of "
                f"{from_month}->{to_month} — the account-presence test cannot be applied")
        elif not new_evaluable:
            presence_rule["bl_reason"] = (
                f"fewer than {absence_months} loaded months precede {to_month} — an account "
                "appearing here cannot be confirmed as genuinely new")
        elif not lost_evaluable:
            presence_rule["bl_reason"] = (
                f"fewer than {absence_months} loaded months follow {from_month} — an account "
                "going quiet here cannot be confirmed as genuinely lost")

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
            bl_new_accounts=bl_new,
            bl_lost_accounts=bl_lost,
            presence_rule=presence_rule,
            gate_to_recurring=not legacy_two_month_presence,
            from_nc_txns=nc_txns_by_group_month.get((group_id, change["from_month_id"]), []),
            to_nc_txns=nc_txns_by_group_month.get((group_id, change["to_month_id"]), []),
            from_late_txns=late_txns_by_group_month.get((group_id, change["from_month_id"]), []),
            to_late_txns=late_txns_by_group_month.get((group_id, change["to_month_id"]), []),
            from_excl_txns=excl_txns_by_group_month.get((group_id, change["from_month_id"]), []),
            to_excl_txns=excl_txns_by_group_month.get((group_id, change["to_month_id"]), []),
            max_processing_days=max_processing_days,
        ):
            raw.append((change, d))

    # R6 A3 sanity rule: BASELINE_LIMITED may only carry what genuinely cannot
    # be determined; a magnitude beyond the transition's total change means the
    # account sets are still wrong. Fail the build loudly — never publish an
    # over-claiming attribution. (Skipped on the test-only legacy path, whose
    # whole purpose is to demonstrate this failure on a fixture.)
    if not legacy_two_month_presence:
        bl_total = sum(_num(d["contribution_amt"]) for _c, d in raw
                       if d["cause_id"] == "BASELINE_LIMITED")
        if abs(bl_total) > abs(total_change) + RECONCILE_TOLERANCE:
            raise AttributionError(
                f"BASELINE_LIMITED over-claims on {total_row['advisor_sid']} "
                f"{from_month}->{to_month}: |{bl_total:,.2f}| > |total change "
                f"{total_change:,.2f}| — the account-presence sets are wrong; "
                "refusing to publish this attribution (FIX_SPEC_R6 A3)."
            )

    # T1-3 self-check: MIX is a residual of last resort. A large MIX relative to
    # the transition's total change means a named driver is missing or
    # mis-specified — WARN with the breakdown; never block (reconciliation
    # still holds by construction).
    mix_total = sum(_num(d["contribution_amt"]) for _c, d in raw if d["cause_id"] == "MIX")
    if abs(total_change) >= 1.0 and abs(mix_total) > mix_warning_fraction * abs(total_change):
        by_cause: dict[str, float] = defaultdict(float)
        for _c, d in raw:
            by_cause[d["cause_id"]] += _num(d["contribution_amt"])
        logger.warning(
            "MIX residual is %.1f%% of the total change for %s %s->%s "
            "(MIX %.2f of change %.2f) — a named driver may be missing. Breakdown: %s",
            abs(mix_total) / abs(total_change) * 100,
            total_row["advisor_sid"], from_month, to_month, mix_total, total_change,
            {c: round(v, 2) for c, v in sorted(by_cause.items())},
        )

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
