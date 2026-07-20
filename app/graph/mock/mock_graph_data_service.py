from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class MockGraphDataService:
    """Final fallback graph service.

    Uses the enterprise demo CSVs plus generated in-memory relationships to support
    all demo scenarios even when MCP and REST are unavailable.
    """

    def __init__(self) -> None:
        self.sample_dir = Path("tigergraph/sample_data")

    def available(self) -> bool:
        return self.sample_dir.exists()

    def _read_csv(self, file_name: str, limit: int | None = None) -> list[dict]:
        path = self.sample_dir / file_name
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return rows[:limit] if limit else rows

    def health_check(self) -> dict:
        manifest_path = self.sample_dir / "demo_data_manifest.json"
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "success": True,
            "mode": "mock",
            "message": "Local mock graph service is available.",
            "manifest": manifest.get("scale", {}),
        }

    def upsert_vertex(self, vertex_type: str, primary_key: str, attributes: dict[str, Any]) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "operation": "upsert_vertex",
            "vertex_type": vertex_type,
            "primary_key": primary_key,
            "attributes": attributes,
            "message": "Mock graph accepted vertex upsert.",
        }

    def upsert_edge(self, edge_type: str, from_id: str, to_id: str, attributes: dict[str, Any] | None = None) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "operation": "upsert_edge",
            "edge_type": edge_type,
            "from_id": from_id,
            "to_id": to_id,
            "attributes": attributes or {},
            "message": "Mock graph accepted edge upsert.",
        }

    def run_installed_query(self, query_name: str, params: dict[str, Any] | None = None) -> dict:
        params = params or {}
        q = query_name.lower()

        if "advisor" in q and "evidence" in q:
            return self.get_advisor_evidence(params.get("advisorId") or params.get("advisor_id") or params.get("advisorId".lower()) or "ADV0001")

        if "memory" in q:
            return self.get_memory_by_scope(params.get("scopeType") or params.get("scope_type") or "Advisor", params.get("scopeId") or params.get("scope_id") or "ADV0001")

        if "recommendation" in q:
            return self.get_recommendations(params.get("advisorId") or params.get("advisor_id") or "ADV0001")

        return {
            "success": True,
            "mode": "mock",
            "query_name": query_name,
            "params": params,
            "data": self.generic_summary(),
        }

    def query_graph(self, query: str, params: dict[str, Any] | None = None) -> dict:
        lower = query.lower()
        params = params or {}
        if "advisor" in lower:
            return self.get_advisor_evidence(params.get("advisor_id", "ADV0001"))
        if "recommendation" in lower:
            return self.get_recommendations(params.get("advisor_id", "ADV0001"))
        return {"success": True, "mode": "mock", "query": query, "data": self.generic_summary()}

    def run_gsql(self, gsql: str, params: dict[str, Any] | None = None) -> dict:
        return {
            "success": True,
            "mode": "mock",
            "message": "Mock graph does not execute GSQL but records the request.",
            "gsql_preview": gsql[:500],
            "params": params or {},
        }

    def get_schema(self) -> dict:
        vertices = [
            "phx_dm_advisor", "phx_dm_household", "phx_dm_account",
            "phx_dm_transaction", "phx_dm_context_memory", "phx_dm_prediction_result",
            "phx_dm_opportunity", "phx_dm_recommendation", "phx_dm_feedback_event",
            "phx_dm_learning_signal", "phx_dm_document", "phx_dm_document_chunk",
        ]
        return {"success": True, "mode": "mock", "vertices": vertices, "prefix": "phx_dm_"}

    def generic_summary(self) -> dict:
        return {
            "advisors": len(self._read_csv("phx_dm_advisor.csv")),
            "households": len(self._read_csv("phx_dm_household.csv")),
            "accounts": len(self._read_csv("phx_dm_account.csv")),
            "recommendations": len(self._read_csv("phx_dm_recommendation.csv")),
            "memories": len(self._read_csv("phx_dm_context_memory.csv")),
        }

    def get_advisor_evidence(self, advisor_id: str) -> dict:
        advisors = [x for x in self._read_csv("phx_dm_advisor.csv") if x.get("advisor_id") == advisor_id]
        txns = [x for x in self._read_csv("phx_dm_transaction.csv", 250000) if x.get("advisor_id") == advisor_id]
        recs = [x for x in self._read_csv("phx_dm_recommendation.csv") if x.get("advisor_id") == advisor_id]
        opps = [x for x in self._read_csv("phx_dm_opportunity.csv") if x.get("advisor_id") == advisor_id]
        preds = [x for x in self._read_csv("phx_dm_prediction_result.csv") if x.get("advisor_id") == advisor_id]
        crm = [x for x in self._read_csv("phx_dm_crm_activity.csv") if x.get("advisor_id") == advisor_id]
        memories = [x for x in self._read_csv("phx_dm_context_memory.csv") if x.get("advisor_id") == advisor_id or x.get("scope_id") == advisor_id]

        revenue = sum(float(t.get("revenue_amount") or 0) for t in txns)
        nnm = sum(float(t.get("net_new_money_amount") or 0) for t in txns)
        ncf = sum(float(t.get("net_cash_flow_amount") or 0) for t in txns)

        return {
            "success": True,
            "mode": "mock",
            "advisor": advisors[0] if advisors else {"advisor_id": advisor_id},
            "metrics": {
                "revenue": round(revenue, 2),
                "nnm": round(nnm, 2),
                "ncf": round(ncf, 2),
                "crm_activity_count": len(crm),
                "recommendation_count": len(recs),
                "opportunity_count": len(opps),
                "prediction_count": len(preds),
                "memory_count": len(memories),
            },
            "predictions": preds[:10],
            "opportunities": opps[:10],
            "recommendations": recs[:10],
            "memories": memories[:10],
        }

    def get_memory_by_scope(self, scope_type: str, scope_id: str) -> dict:
        memories = [
            x for x in self._read_csv("phx_dm_context_memory.csv")
            if x.get("scope_type") == scope_type and x.get("scope_id") == scope_id
        ]
        if not memories and scope_type == "Advisor":
            memories = [
                x for x in self._read_csv("phx_dm_context_memory.csv")
                if x.get("advisor_id") == scope_id
            ]
        return {"success": True, "mode": "mock", "scope_type": scope_type, "scope_id": scope_id, "memories": memories[:25]}

    def get_recommendations(self, advisor_id: str) -> dict:
        recs = [x for x in self._read_csv("phx_dm_recommendation.csv") if x.get("advisor_id") == advisor_id]
        return {"success": True, "mode": "mock", "advisor_id": advisor_id, "recommendations": recs[:25]}
