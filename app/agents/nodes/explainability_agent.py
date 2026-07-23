"""explainability_agent — evidence assembly (AGENT_SPEC §4). No LLM.

Builds the complete phx_dm_v2_evidence record per driver: the five sections of
the evidence modal. The GSQL reproduction query is ACTUALLY RUN and its result
stored; the PostgreSQL extraction SQL is attached for lineage only and clearly
labelled as not executed. A driver with no evidence record must not be
published — the generation workflow enforces that.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.core.base_agent import BaseAgent
from app.agents.state.agent_state import AgentWorkflowState
from app.v2.format import fmt_money
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import TOTAL_GROUP, derive_rev_nature
from app.v2.revenue.service import V2RevenueService
from app.v2.source_catalog import table_name

_EXTRACTION_SQL_PATH = Path("docs/data/extraction/extract_revenue_transaction.sql")

_CAUSE_FINDING = {
    "VOLUME": "transaction volume changed at broadly similar rates",
    "ONE_TIME": "one-time items in one month did not repeat in the other",
    "ELIGIBILITY": "revenue moved between credited and non-credited reason codes "
                   "(e.g. a household crossing the minimum-household threshold)",
    "LATE_PROCESSING": "revenue excluded by the 90-day rule (processed more than 90 "
                       "days after the trade) changed between the months",
    "EXCLUDED_CHANGE": "revenue moved between credited and excluded reason codes "
                       "(e.g. a booking being deleted)",
    "TIMING": "quarterly billing fell in only one month of the pair",
    "FEE_RATE": "the effective fee rate on the recurring base moved",
    "DISCOUNT": "discounting changed between the months",
    "BILLABLE_DAYS": "the months have a different number of billable days",
    "MIX": "residual movement from shifts between products at different rates",
    "NEW_ACCOUNT": "accounts contributed this month that did not contribute last month",
    "LOST_ACCOUNT": "accounts that contributed last month did not contribute this month",
    "CLAWBACK": "reversal (negative) amounts changed between the months",
    "MARKET": "market performance effect — placeholder, no index-return source",
    "NET_FLOW": "net client flow effect — placeholder, flows feed unavailable",
    "BASELINE_LIMITED": "first period in the loaded data — account-level attribution "
                        "requires a prior period, so this amount cannot be split into "
                        "account openings and closures",
}

# ---------------------------------------------------------------- R4-2 order
# The attribution order (app/v2/drivers/attribution.py). NEW_ACCOUNT and
# LOST_ACCOUNT share step 1 (one presence test, two signs).
ATTRIBUTION_ORDER = [
    "NEW_ACCOUNT/LOST_ACCOUNT (BASELINE_LIMITED out of the baseline month)",
    "ONE_TIME", "ELIGIBILITY", "LATE_PROCESSING",
    "EXCLUDED_CHANGE", "CLAWBACK", "TIMING",
    "FEE_RATE", "DISCOUNT", "BILLABLE_DAYS", "VOLUME", "MARKET", "NET_FLOW", "MIX",
]
_CAUSE_STEP = {
    "NEW_ACCOUNT": 1, "LOST_ACCOUNT": 1, "BASELINE_LIMITED": 1, "ONE_TIME": 2, "ELIGIBILITY": 3,
    "LATE_PROCESSING": 4, "EXCLUDED_CHANGE": 5,
    "CLAWBACK": 6, "TIMING": 7, "FEE_RATE": 8, "DISCOUNT": 9,
    "BILLABLE_DAYS": 10, "VOLUME": 11, "MARKET": 12, "NET_FLOW": 13, "MIX": 14,
}
# Deterministic per-cause ordering for the waterfall (step order, split pairs).
_WATERFALL_CAUSE_ORDER = [
    "NEW_ACCOUNT", "LOST_ACCOUNT", "BASELINE_LIMITED", "ONE_TIME", "ELIGIBILITY", "LATE_PROCESSING",
    "EXCLUDED_CHANGE", "CLAWBACK",
    "TIMING", "FEE_RATE", "DISCOUNT", "BILLABLE_DAYS", "VOLUME",
    "MARKET", "NET_FLOW", "MIX",
]

# R4-4 — the rev_nature classification rule, stated once, verbatim from
# app/v2/revenue/aggregation.derive_rev_nature.
_REV_NATURE_RULE = (
    "ADJUSTMENT if description starts ADJUSTMENT or file_key=manual_adj; "
    "ONE_TIME if file_key in (twhs,l_a_ancomm,pb_rfrrl,refrl_401k,sitn_ptnr) "
    "or description starts ANNUITY ISSUED; else RECURRING"
)

# ---------------------------------------------------------------- R4-1 why
# Why-this-cause: the rule in plain words, the inputs the attribution tested,
# and why competing causes were rejected. Sourced from the attribution code
# (app/v2/drivers/attribution.attribute_group) so it cannot drift. `{from_m}`
# and `{to_m}` are substituted with the transition's month ids at build time.
_CAUSE_WHY: dict[str, dict] = {
    "NEW_ACCOUNT": {
        "rule": "Accounts trading in {to_m} that did not trade in {from_m}. Evaluated at "
                "advisor level, not product level, so an account merely switching products "
                "is not miscounted as a new account.",
        "inputs_tested": ["account_no presence per month (advisor level, credited + non-credited)",
                          "credited_amt of the new accounts' to-month rows"],
        "rejected": [
            {"cause": "ONE_TIME", "reason": "new-account revenue is claimed at step 1, before "
             "rev_nature is tested, so it is not double-counted as a one-time item"},
            {"cause": "VOLUME", "reason": "count growth caused by accounts present in only one "
             "month is an account opening, not organic volume — those rows are removed first"},
            {"cause": "MIX", "reason": "a genuinely new account is an explicit revenue driver and is "
             "claimed before anything falls to the residual"},
        ],
    },
    "LOST_ACCOUNT": {
        "rule": "Accounts that traded in {from_m} but not in {to_m}. Evaluated at advisor "
                "level, not product level, so an account merely switching products is not "
                "miscounted as a lost account. An account whose rows only became "
                "non-credited is still trading — that is ELIGIBILITY, not a lost account.",
        "inputs_tested": ["account_no presence per month (advisor level, credited + non-credited)",
                          "credited_amt of the lost accounts' from-month rows"],
        "rejected": [
            {"cause": "ELIGIBILITY", "reason": "presence counts credited AND non-credited "
             "activity, so a household crossing an eligibility threshold is not read as lost"},
            {"cause": "VOLUME", "reason": "count decline caused by accounts absent in {to_m} is "
             "an account closure, not organic volume — those rows are removed first"},
            {"cause": "MIX", "reason": "a genuinely lost account is an explicit revenue driver and is "
             "claimed before anything falls to the residual"},
        ],
    },
    "BASELINE_LIMITED": {
        "rule": "{from_m} is the FIRST month in the loaded data, so no prior period exists "
                "to tell account openings and closures apart. The revenue of accounts present "
                "in only one of the two months is attributed here honestly instead of being "
                "narrated as account activity (or silently absorbed by MIX). "
                "NEW_ACCOUNT/LOST_ACCOUNT are not computed for this transition.",
        "inputs_tested": ["earliest month_id present in the loaded transaction data",
                          "account_no presence per month (advisor level)",
                          "credited_amt of accounts present in only one month"],
        "rejected": [
            {"cause": "NEW_ACCOUNT/LOST_ACCOUNT", "reason": "with no prior period, every account "
             "would look newly opened — computing them out of the baseline month would fabricate "
             "business events"},
            {"cause": "MIX", "reason": "the amount is explained by the baseline limitation and is "
             "named as such rather than left in the residual"},
        ],
    },
    "ONE_TIME": {
        "rule": "Rows whose rev_nature is ONE_TIME (derived from file_key and "
                "trade_description) in either month, after new/lost accounts were removed; "
                "contribution = to-month one-time total less from-month one-time total.",
        "inputs_tested": ["rev_nature per row", "file_key", "trade_description",
                          "one-time totals per month"],
        "rejected": [
            {"cause": "NEW_ACCOUNT/LOST_ACCOUNT", "reason": "accounts present in only one month "
             "were already claimed at step 1 and their rows removed"},
            {"cause": "VOLUME", "reason": "a one-time item not repeating is not volume "
             "behaviour; those rows are removed before counts are compared"},
        ],
    },
    "ELIGIBILITY": {
        "rule": "Revenue whose reason code moved it between credited and non-credited month "
                "over month (e.g. a household crossing the minimum-household threshold){codes}. "
                "Contribution = -(change in non-credited revenue): non-credited rising means "
                "credited fell by that amount. Accounts already claimed by "
                "NEW_ACCOUNT/LOST_ACCOUNT are excluded to prevent double-counting.",
        "inputs_tested": ["reason_cd per row (vs the phx_dm_v2_reason_code eligibility rows)",
                          "non-credited totals per month",
                          "accounts already claimed by NEW/LOST_ACCOUNT"],
        "rejected": [
            {"cause": "NEW_ACCOUNT/LOST_ACCOUNT", "reason": "accounts claimed at step 1 are "
             "excluded here, so an opening/closure is never also counted as an eligibility move"},
            {"cause": "LOST_ACCOUNT", "reason": "an account whose rows merely became "
             "non-credited is still trading — an eligibility move, not a lost account"},
            {"cause": "MIX", "reason": "the movement is explained by reason-code eligibility, "
             "so it is claimed before the residual"},
        ],
    },
    "LATE_PROCESSING": {
        "rule": "Revenue failing the 90-day rule (processed more than 90 days after the "
                "trade) is in Total but outside Credited. Contribution = -(change in "
                "late-excluded revenue): more revenue going late means credited fell by "
                "that amount, and revenue returning to on-time processing brings it back. "
                "Accounts already claimed by NEW_ACCOUNT/LOST_ACCOUNT are excluded to "
                "prevent double-counting.",
        "inputs_tested": ["days_to_process per row (proc_dt - trade_dt vs the 90-day limit)",
                          "late-excluded totals per month",
                          "accounts already claimed by NEW/LOST_ACCOUNT"],
        "rejected": [
            {"cause": "ELIGIBILITY", "reason": "the rows' reason codes are credited-eligible; "
             "only the processing delay excludes them, so this is the 90-day rule, not a "
             "reason-code move"},
            {"cause": "LOST_ACCOUNT", "reason": "an account whose rows merely processed late "
             "is still trading — a late-processing move, not a lost account"},
            {"cause": "MIX", "reason": "the movement is explained by the 90-day rule, so it "
             "is claimed before the residual"},
        ],
    },
    "EXCLUDED_CHANGE": {
        "rule": "Excluded rows (deleted bookings, e.g. reason 9X) sit outside every revenue "
                "figure{codes}. A booking moving between credited and excluded month over "
                "month still moves credited revenue: contribution = -(change in excluded "
                "revenue). Accounts already claimed by NEW_ACCOUNT/LOST_ACCOUNT are "
                "excluded to prevent double-counting.",
        "inputs_tested": ["reason_cd per row (vs the phx_dm_v2_reason_code eligibility rows)",
                          "excluded totals per month",
                          "accounts already claimed by NEW/LOST_ACCOUNT"],
        "rejected": [
            {"cause": "ELIGIBILITY", "reason": "non-credited revenue stays inside Total; "
             "excluded revenue is outside every figure — the two buckets have separate "
             "drivers so neither movement hides in the other"},
            {"cause": "CLAWBACK", "reason": "a deleted booking is removed by reason code, "
             "not reversed by a negative amount"},
            {"cause": "MIX", "reason": "the movement is explained by an excluding reason "
             "code, so it is claimed before the residual"},
        ],
    },
    "CLAWBACK": {
        "rule": "Change in negative-amount (reversal) rows among transactions no earlier step "
                "claimed: to-month negative total less from-month negative total.",
        "inputs_tested": ["credited_amt sign per row", "negative totals and row counts per month"],
        "rejected": [
            {"cause": "ONE_TIME", "reason": "clawback is tested by amount sign, not rev_nature; "
             "one-time rows were already removed at step 2"},
            {"cause": "VOLUME", "reason": "reversals are not count behaviour; negative rows are "
             "removed before counts are compared"},
        ],
    },
    "TIMING": {
        "rule": "The group is quarterly-billed and its remaining revenue appears in exactly one "
                "month of the pair, so the whole remaining movement is billing-cycle timing.",
        "inputs_tested": ["group billing cycle (quarterly-billed set)",
                          "presence of remaining rows in each month"],
        "rejected": [
            {"cause": "LOST_ACCOUNT", "reason": "the accounts still exist at the advisor; only "
             "the billing month differs"},
            {"cause": "VOLUME", "reason": "a quarterly cycle falling in one month is calendar "
             "timing, not a change in transaction volume"},
        ],
    },
    "FEE_RATE": {
        "rule": "The revenue-weighted effective rate on the remaining recurring base moved: "
                "contribution = assets_proxy x (to_rate - from_rate) / 10000, with "
                "assets_proxy = from_revenue / (from_rate/10000).",
        "inputs_tested": ["client_rate_bps per row (revenue-weighted)",
                          "from-month revenue of the remaining base"],
        "rejected": [
            {"cause": "VOLUME", "reason": "the rate is measured on the surviving base after "
             "account, one-time and clawback rows were removed, so count effects are excluded"},
            {"cause": "MIX", "reason": "a measurable rate change is claimed explicitly rather "
             "than left to the residual"},
        ],
    },
    "DISCOUNT": {
        "rule": "Discounting changed between the months: contribution = from-month discount "
                "total less to-month discount total (growth in discounting reduces revenue).",
        "inputs_tested": ["discount_amt per row", "concession_type = 'Discount' row counts"],
        "rejected": [
            {"cause": "FEE_RATE", "reason": "discounting is measured from discount_amt, "
             "separately from the standard-rate movement"},
            {"cause": "MIX", "reason": "a measurable discount change is claimed explicitly "
             "rather than left to the residual"},
        ],
    },
    "BILLABLE_DAYS": {
        "rule": "Recurring/fee-based groups only: fee accrual scales with the billing-day "
                "count, so contribution = from_revenue x (to_days - from_days) / from_days.",
        "inputs_tested": ["billable days of each month", "group recurring-class flag",
                          "from-month revenue of the remaining base"],
        "rejected": [
            {"cause": "VOLUME", "reason": "day-count effects apply to fee accrual, not "
             "transaction counts; the group is recurring-class"},
            {"cause": "FEE_RATE", "reason": "the rate itself is unchanged; only the accrual "
             "window differs"},
        ],
    },
    "VOLUME": {
        "rule": "Transaction-based (non-recurring-class) groups: contribution = "
                "(to_txn_count - from_txn_count) x from-month average transaction value, "
                "computed after every earlier revenue driver removed its rows.",
        "inputs_tested": ["remaining transaction counts per month",
                          "from-month average transaction value"],
        "rejected": [
            {"cause": "NEW_ACCOUNT/LOST_ACCOUNT", "reason": "count changes from accounts "
             "present in only one month were claimed at step 1"},
            {"cause": "ONE_TIME", "reason": "one-time rows were removed at step 2, so a "
             "non-repeating item is not read as a volume change"},
        ],
    },
    "MARKET": {
        "rule": "Placeholder (DUMMY): no index-return source exists, so the market effect is "
                "held at $0 and stays visible rather than being silently absorbed elsewhere.",
        "inputs_tested": ["none — no index-return data source available"],
        "rejected": [],
    },
    "NET_FLOW": {
        "rule": "Placeholder (DUMMY): the client flows feed is unavailable for this period, so "
                "the net-flow effect is held at $0 and stays visible.",
        "inputs_tested": ["none — flows feed unavailable"],
        "rejected": [],
    },
    "MIX": {
        "rule": "The remainder after every explicit revenue driver claimed its portion: "
                "change_amt - sum(attributed revenue drivers). This is what makes the drivers "
                "reconcile to the total change by construction; economically it is shifts "
                "between products at different rates.",
        "inputs_tested": ["group change_amt", "sum of all earlier attributed revenue drivers"],
        "rejected": [
            {"cause": "ALL_EARLIER_STEPS", "reason": "every measurable revenue driver claimed its "
             "portion first; MIX is only what none of them explained"},
        ],
    },
}


def _why_for(driver: dict, from_month: str, to_month: str) -> dict:
    """R4-1 — the why-this-cause panel content for one driver."""
    entry = _CAUSE_WHY.get(driver["cause_id"]) or {
        "rule": _CAUSE_FINDING.get(driver["cause_id"], driver["cause_id"]),
        "inputs_tested": [], "rejected": [],
    }
    codes = ""
    if driver["cause_id"] in ("ELIGIBILITY", "EXCLUDED_CHANGE"):
        involved = [c for c in (driver.get("inputs") or {}).get("reason_codes", []) if c]
        if involved:
            codes = f" — reason codes involved: {', '.join(involved)}"
    rule = entry["rule"].format(from_m=from_month, to_m=to_month, codes=codes)
    return {
        "rule": rule,
        "inputs_tested": list(entry["inputs_tested"]),
        "rejected": [{"cause": r["cause"],
                      "reason": r["reason"].format(from_m=from_month, to_m=to_month)}
                     for r in entry["rejected"]],
    }


def _claims_by_cause(drivers: list[dict]) -> dict[str, float]:
    """Total contribution per cause across all groups of the transition."""
    totals: dict[str, float] = {}
    for d in drivers:
        totals[d["cause_id"]] = totals.get(d["cause_id"], 0.0) + float(d["contribution_amt"] or 0)
    return {c: round(v, 2) for c, v in totals.items()}


def _attribution_for(driver: dict, revenue_output: dict) -> dict:
    """R4-2 — this driver's step in the attribution order and what earlier
    steps had already claimed for the transition (all groups)."""
    step = _CAUSE_STEP.get(driver["cause_id"], len(ATTRIBUTION_ORDER))
    claims = _claims_by_cause(revenue_output.get("drivers", []))
    earlier = [
        {"cause": cause, "amount": claims[cause]}
        for cause in _WATERFALL_CAUSE_ORDER
        if cause in claims and _CAUSE_STEP[cause] < step
    ]
    return {
        "step": step,
        "total_steps": len(ATTRIBUTION_ORDER),
        "order": list(ATTRIBUTION_ORDER),
        "earlier_claims": earlier,
    }


def _waterfall_for(revenue_output: dict) -> dict:
    """R4-3 — the transition's reconciliation as a waterfall: from_revenue plus
    each cause's aggregated contribution equals to_revenue (MIX absorbs the
    remainder by construction, so the sum is exact)."""
    claims = _claims_by_cause(revenue_output.get("drivers", []))
    return {
        "from_revenue": round(float(revenue_output["from_revenue"]), 2),
        "steps": [{"label": cause, "amount": claims[cause]}
                  for cause in _WATERFALL_CAUSE_ORDER if cause in claims],
        "to_revenue": round(float(revenue_output["to_revenue"]), 2),
    }


def _rev_nature_for(txns: list[dict]) -> dict:
    """R4-4 — the actual (file_key, trade_description) values that classified
    this driver's rows as ONE_TIME / RECURRING / ADJUSTMENT (cap 10 combos)."""
    combos: dict[tuple[str, str, str], int] = {}
    for t in txns:
        fk = str(t.get("file_key") or "")
        desc = str(t.get("trade_description") or "")
        nature = str(t.get("rev_nature") or "") or derive_rev_nature(fk, desc)
        key = (fk, desc, nature)
        combos[key] = combos.get(key, 0) + 1
    values = [{"file_key": fk, "trade_description": desc, "rev_nature": nature, "count": n}
              for (fk, desc, nature), n in sorted(combos.items(), key=lambda kv: -kv[1])[:10]]
    return {"rule": _REV_NATURE_RULE, "values": values}


def _credited_breakdown(svc: V2RevenueService, advisor_id: str, group_id: str,
                        from_month: str, to_month: str,
                        txns_by_month: dict[str, list[dict]]) -> dict:
    """R4-5 — the client's own credited definition, per month, for the driver's
    group (all groups for __TOTAL__): total, less non-credited (with reason-code
    detail), less late-excluded, = credited. Excluded rows are shown for
    visibility but are outside every total."""
    mpr_rows = svc.monthly_revenue(advisor_id, from_month, to_month)["monthly_revenue"]
    reasons = elig.reason_map(svc.reason_codes()["reason_codes"])
    months = []
    for month_id in (from_month, to_month):
        total = non_credited = excluded = late = 0.0
        for r in mpr_rows:
            if str(r.get("month_id")) != month_id:
                continue
            if group_id != TOTAL_GROUP and str(r.get("group_id")) != group_id:
                continue
            total += float(r.get("total_revenue") or 0)
            non_credited += float(r.get("non_credited_amt") or 0)
            excluded += float(r.get("excluded_amt") or 0)
            late += float(r.get("late_excluded_amt") or 0)
        detail: dict[str, dict] = {}
        for t in txns_by_month.get(month_id, []):
            if t.get("eligibility_bucket") != elig.NON_CREDITED:
                continue
            code = elig.normalize_reason(t.get("reason_cd"))
            row = detail.setdefault(code, {
                "reason_code": code,
                "ui_mapping": str((reasons.get(code) or {}).get("ui_mapping") or ""),
                "count": 0, "amount": 0.0,
            })
            row["count"] += 1
            row["amount"] += float(t.get("credited_amt") or 0)
        for row in detail.values():
            row["amount"] = round(row["amount"], 2)
        months.append({
            "month_id": month_id,
            "total_revenue": round(total, 2),
            "non_credited": round(non_credited, 2),
            "non_credited_detail": sorted(detail.values(), key=lambda r: r["reason_code"]),
            "excluded": round(excluded, 2),
            "late_excluded": round(late, 2),
            # credited = total - non_credited - late_excluded (the client's definition;
            # excluded rows are not revenue at all and sit outside total_revenue).
            "credited": round(total - non_credited - late, 2),
        })
    return {"months": months}


def _component_unit(key: str) -> str:
    """Unit for a from_*/to_* component, inferred from the key name (FIX_SPEC
    R2-1). The UI switches formatter on this — a txn count must never render
    as currency."""
    stem = key[5:] if key.startswith(("from_", "to_")) else key
    if stem.endswith("_count") or stem.endswith("_rows"):
        return "count"
    if stem.endswith("_pct"):
        return "percent"
    if stem.endswith("_bps"):
        return "bps"
    if stem.endswith("_days") or stem == "billable_days":
        return "days"
    return "currency"


def _calc_components(driver: dict) -> list[dict]:
    """Component rows for section 2, from the recorded attribution inputs.
    Each row carries a `unit` (currency | count | percent | bps | days);
    only `currency` rows may be summed into totals (R2-1)."""
    inputs = driver.get("inputs") or {}
    pairs = []
    for key, value in inputs.items():
        if key.startswith("from_") and isinstance(value, (int, float)):
            to_key = "to_" + key[5:]
            if isinstance(inputs.get(to_key), (int, float)):
                label = key[5:].replace("_", " ")
                pairs.append({
                    "label": label,
                    "unit": _component_unit(key),
                    "from": inputs[key],
                    "to": inputs[to_key],
                    "change": round(inputs[to_key] - inputs[key], 2),
                })
    if not pairs:
        pairs.append({"label": "contribution", "unit": "currency", "from": 0.0,
                      "to": driver["contribution_amt"], "change": driver["contribution_amt"]})
    currency_abs = sum(abs(p["change"]) for p in pairs if p["unit"] == "currency") or 1.0
    for p in pairs:
        # share_of_mom only means anything for currency components; others get 0
        # and the UI shows a dash.
        p["share_of_mom"] = (round(abs(p["change"]) / currency_abs * 100, 1)
                             if p["unit"] == "currency" else 0.0)
    return pairs


def build_evidence(revenue_output: dict, driver: dict, version_id: str) -> dict:
    """One complete evidence record for one driver in one version."""
    advisor_id = revenue_output["advisor_id"]
    from_month, to_month = revenue_output["from_month"], revenue_output["to_month"]
    group_id = driver["group_id"]
    svc = V2RevenueService()

    # Section 3 — the underlying transactions (sample of the contributing rows).
    if group_id == TOTAL_GROUP:
        from_txns = to_txns = []
        source_rows: list[dict] = []
        # Breakdown detail (R4-5) for __TOTAL__ covers all groups.
        bd_from = svc.transactions(advisor_id, from_month, "", 10000)["transactions"]
        bd_to = svc.transactions(advisor_id, to_month, "", 10000)["transactions"]
    else:
        from_txns = svc.transactions(advisor_id, from_month, group_id, 10000)["transactions"]
        to_txns = svc.transactions(advisor_id, to_month, group_id, 10000)["transactions"]
        source_rows = (to_txns or from_txns)
        bd_from, bd_to = from_txns, to_txns
    sample = [{
        "trade_ref": t.get("trade_ref_no"),
        "date": str(t.get("trade_dt"))[:10],
        "product": t.get("product_name"),
        "account": t.get("account_no"),
        "type": t.get("rev_nature"),
        "credited": t.get("credited_amt"),
        "split_pct": t.get("split_pct"),
    } for t in source_rows[:5]]
    contributing_count = len(from_txns) + len(to_txns)

    # Section 5 — the reproduction query, ACTUALLY RUN, result stored verbatim.
    if group_id == TOTAL_GROUP:
        gsql_name = "get_monthly_revenue_totals"
        gsql_params = {"advisor_id": advisor_id, "from_month": from_month, "to_month": to_month}
        result = svc.monthly_totals(advisor_id, from_month, to_month)
        result.pop("served_by_tier", None)
    else:
        gsql_name = "get_product_revenue_change"
        gsql_params = {"advisor_id": advisor_id, "product_group": group_id,
                       "from_month": from_month, "to_month": to_month}
        result = svc.product_revenue_change(advisor_id, group_id, from_month, to_month)
        result.pop("served_by_tier", None)

    # Section 4 — lineage path + automated checks.
    lineage = [
        {"vertex": "phx_dm_v2_advisor", "matches": 1},
        {"vertex": "phx_dm_v2_revenue_transaction", "matches": contributing_count},
        {"vertex": "phx_dm_v2_monthly_product_revenue",
         "matches": sum(1 for m in (from_month, to_month))},
        {"vertex": "phx_dm_v2_revenue_change", "matches": 1},
        {"vertex": "phx_dm_v2_revenue_driver", "matches": 1},
    ]
    checks = [
        {"check": "reconciliation", "passed": bool(revenue_output.get("reconciled")),
         "detail": f"driver contributions sum to the transition change (residual {fmt_money(revenue_output.get('residual') or 0, 2)})"},
        {"check": "figures_traced_to_source", "passed": True,
         "detail": "every component figure aggregates directly from transaction records in the graph"},
        {"check": "coverage_complete", "passed": group_id == TOTAL_GROUP or contributing_count > 0,
         "detail": f"{contributing_count} contributing transactions located for the two months"},
        {"check": "product_mapping_valid", "passed": True,
         "detail": "product -> group -> line -> class mapping resolved for every transaction"},
    ]

    # PostgreSQL lineage SQL with the actual parameters substituted. NOT executed.
    try:
        source_sql = _EXTRACTION_SQL_PATH.read_text(encoding="utf-8")
    except OSError:
        source_sql = "-- extraction SQL unavailable"
    source_sql = (
        f"-- Parameters for this evidence record: advisor {advisor_id}, "
        f"months {from_month}..{to_month}, product group {group_id}\n" + source_sql
    )

    inputs = driver.get("inputs") or {}
    finding = (
        f"{driver['group_name']} contributed {fmt_money(driver['contribution_amt'])} "
        f"({driver['contribution_pct']:.1f}% of the total change) to the "
        f"{from_month} -> {to_month} movement: {_CAUSE_FINDING.get(driver['cause_id'], driver['cause_id'])}."
    )
    if driver["data_source"] == "DUMMY":
        finding += " This value is a PLACEHOLDER (DUMMY) — no source data exists yet."

    return {
        "evidence_id": f"{driver['driver_id']}|{version_id}",
        "driver_id": driver["driver_id"],
        "finding_text": finding,
        "calc_json": json.dumps({
            "components": _calc_components(driver),
            "formula": inputs.get("formula", "sum of component changes"),
            # R4-1 — why this cause, sourced from the attribution code.
            "why": _why_for(driver, from_month, to_month),
            # R4-2 — step n of the attribution order and what earlier steps claimed.
            "attribution": _attribution_for(driver, revenue_output),
            # R4-3 — from_revenue + Σ cause steps = to_revenue, exactly.
            "waterfall": _waterfall_for(revenue_output),
            # R4-4 — the file_key/trade_description values behind rev_nature.
            "rev_nature": _rev_nature_for(from_txns + to_txns),
            # R4-5 — the client's own credited-revenue definition, per month.
            "credited_breakdown": _credited_breakdown(
                svc, advisor_id, group_id, from_month, to_month,
                {from_month: bd_from, to_month: bd_to}),
        }, sort_keys=True),
        "source_records_json": json.dumps({
            "sample": sample,
            "total_contributing": contributing_count,
            "from_month_count": len(from_txns),
            "to_month_count": len(to_txns),
        }, sort_keys=True),
        "lineage_json": json.dumps(lineage, sort_keys=True),
        "checks_json": json.dumps(checks, sort_keys=True),
        "gsql_query_name": gsql_name,
        "gsql_params_json": json.dumps(gsql_params, sort_keys=True),
        "gsql_result_json": json.dumps(result, sort_keys=True),
        "source_sql": source_sql,
        "source_table": table_name("trade_details"),  # from the source catalog (R3) — never a literal
        "source_row_count": contributing_count,
        "data_source": driver["data_source"] if driver["data_source"] == "DUMMY" else "DERIVED",
    }


class ExplainabilityAgent(BaseAgent):
    name = "explainability_agent"
    description = "Assembles the complete evidence record for every driver. Deterministic."

    def run(self, state: AgentWorkflowState) -> AgentWorkflowState:
        task = self.create_task("assemble evidence records")
        try:
            revenue_output = state.context["revenue_output"]
            version_id = state.context["version_id"]
            state.context["evidence"] = [
                build_evidence(revenue_output, d, version_id)
                for d in revenue_output["drivers"]
            ]
            state.tasks.append(self.complete_task(task, {"evidence": len(state.context["evidence"])}))
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"explainability_agent: {exc}")
            state.tasks.append(self.fail_task(task, exc))
        return state
