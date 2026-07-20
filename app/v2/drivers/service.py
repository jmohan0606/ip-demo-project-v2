"""Driver reads + the transition reconciliation check (ABSOLUTE RULE 7)."""
from __future__ import annotations

from app.graph.client import get_graph_client
from app.graph.queries.common import v2_served_by_tier
from app.v2.drivers.attribution import RECONCILE_TOLERANCE
from app.v2.revenue.aggregation import TOTAL_GROUP


def _attrs(row: dict) -> dict:
    return row.get("attributes", {})


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class V2DriverService:
    def __init__(self) -> None:
        self.graph = get_graph_client()

    def _run(self, query_name: str, params: dict) -> tuple[list[dict], int]:
        result = self.graph.run_query(query_name, params)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"{query_name} returned an error envelope")
        return result.get("results", []), v2_served_by_tier(result)

    def change_drivers(self, advisor_id: str, from_month: str, to_month: str,
                       result_limit: int = 100) -> dict:
        results, tier = self._run(
            "get_change_drivers",
            {"advisor_id": advisor_id, "from_month": from_month,
             "to_month": to_month, "result_limit": result_limit},
        )
        rows = [_attrs(r) for r in results[0].get("drivers", [])] if results else []
        return {"drivers": rows, "served_by_tier": tier}

    def reconciliation(self, advisor_id: str, from_month: str, to_month: str) -> dict:
        """Independent check over GRAPH data: for every transition of the advisor
        in range, Σ driver contributions must equal the __TOTAL__ change within
        $1. This is recomputed from what is stored — not from the code that
        wrote it — so a corrupted load cannot slip through."""
        changes_res, tier = self._run(
            "get_revenue_changes",
            {"advisor_id": advisor_id, "from_month": from_month, "to_month": to_month},
        )
        changes = [_attrs(r) for r in changes_res[0].get("changes", [])] if changes_res else []
        transitions = {}
        for c in changes:
            if c.get("group_id") != TOTAL_GROUP:
                continue
            f, t = str(c.get("from_month_id")), str(c.get("to_month_id"))
            drivers_res, _ = self._run(
                "get_change_drivers",
                {"advisor_id": advisor_id, "from_month": f, "to_month": t, "result_limit": 10000},
            )
            drivers = [_attrs(r) for r in drivers_res[0].get("drivers", [])] if drivers_res else []
            attributed = round(sum(_num(d.get("contribution_amt")) for d in drivers), 2)
            total = _num(c.get("change_amt"))
            discrepancy = round(total - attributed, 2)
            transitions[f"{f}->{t}"] = {
                "total_change": round(total, 2),
                "attributed": attributed,
                "discrepancy": discrepancy,
                "driver_count": len(drivers),
                "reconciles": abs(discrepancy) <= RECONCILE_TOLERANCE,
            }
        return {
            "advisor_id": advisor_id,
            "all_reconcile": all(t["reconciles"] for t in transitions.values()) if transitions else True,
            "tolerance_usd": RECONCILE_TOLERANCE,
            "transitions": transitions,
            "served_by_tier": tier,
        }
