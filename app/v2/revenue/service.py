"""Read services for the Trends and AI Insights screens.

Every figure comes from a catalogued GQ query over graph data (ABSOLUTE RULES
1-2). run_catalog_query does the logged local-store fallback; served_by_tier is
carried on every payload so the UI's tier pill is honest.
"""
from __future__ import annotations

from typing import Any

from app.config.settings import get_settings
from app.graph.client import get_graph_client
from app.graph.queries.common import v2_served_by_tier
from app.v2.revenue import eligibility as elig


def _attrs(row: dict) -> dict:
    return row.get("attributes", {})


class V2RevenueService:
    def __init__(self) -> None:
        self.graph = get_graph_client()

    def _run(self, query_name: str, params: dict) -> tuple[list[dict], int]:
        """(results, served_by_tier). Raises if no tier can serve — the caller
        surfaces the error; nothing is fabricated."""
        result = self.graph.run_query(query_name, params)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"{query_name} returned an error envelope")
        return result.get("results", []), v2_served_by_tier(result)

    # ---------------------------------------------------------- reference

    def advisors(self) -> dict:
        results, tier = self._run("get_advisors", {})
        rows = [_attrs(r) for r in results[0].get("advisors", [])] if results else []
        return {"advisors": rows, "served_by_tier": tier}

    def months(self) -> dict:
        results, tier = self._run("get_months", {})
        rows = [_attrs(r) for r in results[0].get("months", [])] if results else []
        return {"months": rows, "served_by_tier": tier}

    def product_hierarchy(self) -> dict:
        results, tier = self._run("get_product_hierarchy", {})
        payload: dict[str, Any] = {"classes": [], "lines": [], "groups": [], "products": []}
        for obj in results:
            for key in payload:
                if key in obj:
                    payload[key] = [
                        {**_attrs(r), "parent_id": _attrs(r).get("@parent_id", "")}
                        for r in obj[key]
                    ]
        payload["served_by_tier"] = tier
        return payload

    def driver_causes(self) -> dict:
        results, tier = self._run("get_driver_causes", {})
        rows = [_attrs(r) for r in results[0].get("causes", [])] if results else []
        return {"causes": rows, "served_by_tier": tier}

    def reason_codes(self) -> dict:
        """The eligibility reference rows (FIX_SPEC R1) — read from the graph so
        seeding a new code changes behaviour with no code change."""
        results, tier = self._run("get_reason_codes", {})
        rows = [_attrs(r) for r in results[0].get("reason_codes", [])] if results else []
        return {"reason_codes": rows, "served_by_tier": tier}

    # ---------------------------------------------------------- trends

    def monthly_revenue(self, advisor_id: str, from_month: str, to_month: str) -> dict:
        results, tier = self._run(
            "get_monthly_revenue_by_product",
            {"advisor_id": advisor_id, "from_month": from_month, "to_month": to_month},
        )
        rows = [_attrs(r) for r in results[0].get("monthly_revenue", [])] if results else []
        return {"monthly_revenue": rows, "served_by_tier": tier}

    def monthly_totals(self, advisor_id: str, from_month: str, to_month: str) -> dict:
        results, tier = self._run(
            "get_monthly_revenue_totals",
            {"advisor_id": advisor_id, "from_month": from_month, "to_month": to_month},
        )
        payload = dict(results[0]) if results else {}
        payload["served_by_tier"] = tier
        return payload

    def revenue_changes(self, advisor_id: str, from_month: str, to_month: str) -> dict:
        results, tier = self._run(
            "get_revenue_changes",
            {"advisor_id": advisor_id, "from_month": from_month, "to_month": to_month},
        )
        rows = [_attrs(r) for r in results[0].get("changes", [])] if results else []
        return {"changes": rows, "served_by_tier": tier}

    # ---------------------------------------------------------- drill-down & ops

    def transactions(self, advisor_id: str, month_id: str, group_id: str, result_limit: int) -> dict:
        """Drill-down rows. Every extracted transaction is shown (source-record
        honesty), each classified per the credited definition (R1-6):
        eligibility_bucket = CREDITED | NON_CREDITED | EXCLUDED | LATE |
        OUT_OF_GRID. credited_total sums ONLY the CREDITED rows, so it equals
        the pivot cell it is opened from."""
        results, tier = self._run(
            "get_transactions",
            {"advisor_id": advisor_id, "month_id": month_id,
             "group_id": group_id, "result_limit": result_limit},
        )
        settings = get_settings()
        reasons = elig.reason_map(self.reason_codes()["reason_codes"])
        grid_types = settings.credited_grid_type_set
        max_days = int(settings.max_processing_days)
        rows = []
        for r in (results[0].get("transactions", []) if results else []):
            a = _attrs(r)
            bucket = elig.classify(
                a.get("reason_cd"), a.get("@grid_type") or "PRODUCT_TYPE",
                int(float(a.get("days_to_process") or 0)), reasons, grid_types, max_days,
            )
            rows.append({**a, "group_id": a.get("@group_id", ""),
                         "product_name": a.get("@product_name", ""),
                         "grid_type": a.get("@grid_type", ""),
                         "eligibility_bucket": bucket})
        total = round(sum(float(r.get("credited_amt") or 0) for r in rows
                          if r["eligibility_bucket"] == elig.CREDITED), 2)
        return {"transactions": rows, "row_count": len(rows),
                "credited_total": total, "served_by_tier": tier}

    def product_revenue_change(self, advisor_id: str, product_group: str,
                               from_month: str, to_month: str) -> dict:
        results, tier = self._run(
            "get_product_revenue_change",
            {"advisor_id": advisor_id, "product_group": product_group,
             "from_month": from_month, "to_month": to_month},
        )
        payload = dict(results[0]) if results else {}
        payload["served_by_tier"] = tier
        return payload

    def ingestion_counts(self) -> dict:
        results, tier = self._run("get_ingestion_counts", {})
        payload = dict(results[0]) if results else {"counts": {}, "source_mix": {}}
        payload["served_by_tier"] = tier
        return payload

    def advisor_month_summary(self, advisor_id: str) -> dict:
        results, tier = self._run("get_advisor_month_summary", {"advisor_id": advisor_id})
        payload = dict(results[0]) if results else {}
        payload["served_by_tier"] = tier
        return payload
