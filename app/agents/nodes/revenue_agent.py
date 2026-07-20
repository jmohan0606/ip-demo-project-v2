"""revenue_agent — metrics + attribution (AGENT_SPEC §2).

Fully deterministic. No LLM. No randomness. A thin node over app/v2/revenue and
app/v2/drivers, so the same code is callable outside the agent framework.
"""
from __future__ import annotations

import json

from app.agents.core.base_agent import BaseAgent
from app.agents.state.agent_state import AgentWorkflowState
from app.v2.drivers.attribution import RECONCILE_TOLERANCE
from app.v2.drivers.service import V2DriverService
from app.v2.revenue.aggregation import TOTAL_GROUP
from app.v2.revenue.service import V2RevenueService


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def analyze_transition(advisor_id: str, from_month: str, to_month: str) -> dict:
    """The revenue_agent output contract for one transition — every figure from
    catalogued queries over graph data."""
    revenue = V2RevenueService()
    drivers_svc = V2DriverService()

    changes = revenue.revenue_changes(advisor_id, from_month, to_month)["changes"]
    total = next(
        (c for c in changes
         if c.get("group_id") == TOTAL_GROUP
         and str(c.get("from_month_id")) == from_month
         and str(c.get("to_month_id")) == to_month),
        None,
    )
    if total is None:
        raise LookupError(f"no revenue_change __TOTAL__ row for {advisor_id} {from_month}->{to_month}")

    totals = revenue.monthly_totals(advisor_id, from_month, to_month)
    txn_count = sum(int(v) for v in (totals.get("txn_count_by_month") or {}).values())

    group_names = {
        g.get("group_id"): g.get("group_name")
        for g in revenue.product_hierarchy()["groups"]
    }

    raw_drivers = drivers_svc.change_drivers(advisor_id, from_month, to_month, 10000)["drivers"]
    drivers = []
    for d in raw_drivers:
        try:
            inputs = json.loads(d.get("inputs_json") or "{}")
        except (TypeError, ValueError):
            inputs = {}
        drivers.append({
            "driver_id": d.get("driver_id"),
            "rank": int(d.get("rank") or 0),
            "group_id": d.get("group_id"),
            "group_name": group_names.get(d.get("group_id"), "Total" if d.get("group_id") == TOTAL_GROUP else d.get("group_id")),
            "cause_id": d.get("cause_id"),
            "contribution_amt": _num(d.get("contribution_amt")),
            "contribution_pct": _num(d.get("contribution_pct")),
            "direction": d.get("direction"),
            "data_source": d.get("data_source"),
            "inputs": inputs,
        })

    attributed = round(sum(d["contribution_amt"] for d in drivers), 2)
    change_amt = _num(total.get("change_amt"))
    residual = round(change_amt - attributed, 2)
    return {
        "advisor_id": advisor_id,
        "from_month": from_month,
        "to_month": to_month,
        "from_revenue": _num(total.get("from_revenue")),
        "to_revenue": _num(total.get("to_revenue")),
        "change_amt": change_amt,
        "change_pct": _num(total.get("change_pct")),
        "txn_count": txn_count,
        "reconciled": abs(residual) <= RECONCILE_TOLERANCE,
        "residual": residual,
        "drivers": sorted(drivers, key=lambda d: d["rank"]),
    }


class RevenueAgent(BaseAgent):
    name = "revenue_agent"
    description = "Deterministic monthly revenue, MoM change and driver attribution over graph data."

    def run(self, state: AgentWorkflowState) -> AgentWorkflowState:
        ctx = state.context
        task = self.create_task(
            f"analyze {ctx.get('advisor_id')} {ctx.get('from_month')}->{ctx.get('to_month')}")
        try:
            result = analyze_transition(
                str(ctx["advisor_id"]), str(ctx["from_month"]), str(ctx["to_month"]))
            state.context["revenue_output"] = result
            state.tasks.append(self.complete_task(task, {"drivers": len(result["drivers"])}))
        except Exception as exc:  # noqa: BLE001 — recorded, surfaced by supervisor
            state.errors.append(f"revenue_agent: {exc}")
            state.tasks.append(self.fail_task(task, exc))
        return state
