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


def _display_order_key(row: dict) -> tuple[float, str]:
    """Numeric sort key for display_order rows, whatever type the serving
    tier delivered (INT from the current schema, STRING from a pre-R8 live
    install, absent on unseeded rows). Missing/invalid/zero sorts LAST, ties
    break by display name — the R9 F glossary contract."""
    raw = row.get("display_order")
    try:
        order = float(raw)
    except (TypeError, ValueError):
        order = 0.0
    return (order if order > 0 else float("inf"),
            str(row.get("display_name") or row.get("cause_id") or ""))


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
        # display_order must sort NUMERICALLY on every serving path. A live
        # graph installed before display_order became INT holds it as STRING,
        # and GQ-004's ORDER BY then returns "1","10","11",…,"19","2" — so the
        # order is re-imposed here from the numeric value regardless of tier
        # or stored type (R9 F semantics: missing/invalid order sorts last,
        # ties break by display name).
        rows.sort(key=_display_order_key)
        return {"causes": rows, "served_by_tier": tier}

    def reason_codes(self) -> dict:
        """The eligibility reference rows (FIX_SPEC R1) — read from the graph so
        seeding a new code changes behaviour with no code change."""
        results, tier = self._run("get_reason_codes", {})
        rows = [_attrs(r) for r in results[0].get("reason_codes", [])] if results else []
        return {"reason_codes": rows, "served_by_tier": tier}

    def commentary_evaluations(self, version_id: str = "") -> dict:
        """LLM-as-judge evaluations (FIX_SPEC R5-4) — stored, advisory-only
        verdicts per commentary. version_id "" returns all versions."""
        results, tier = self._run("get_commentary_evaluations", {"version_id": version_id})
        rows = [_attrs(r) for r in results[0].get("evaluations", [])] if results else []
        return {"evaluations": rows, "served_by_tier": tier}

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
