from __future__ import annotations

from collections import defaultdict
from typing import Any


class MockGraphStore:
    """In-memory final fallback that preserves graph write/read semantics for demo mode."""

    def __init__(self) -> None:
        self.vertices: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.edges: list[dict[str, Any]] = []

    def execute_query(self, query_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if query_name == "get_advisor_context":
            advisor_id = params.get("advisor_id", "ADV0001")
            return {
                "advisor_id": advisor_id,
                "nodes": [
                    {"id": advisor_id, "type": "Advisor", "label": "Alex Morgan"},
                    {"id": "HH001", "type": "Household", "label": "Parker Family"},
                    {"id": "REC001", "type": "Recommendation", "label": "Schedule Managed Account Review"},
                ],
                "edges": [
                    {"source": advisor_id, "target": "HH001", "label": "SERVES"},
                    {"source": "HH001", "target": "REC001", "label": "GENERATES_RECOMMENDATION"},
                ],
            }
        return {
            "query_name": query_name,
            "params": params,
            "vertices": self.vertices,
            "edges": self.edges,
        }

    def upsert_vertex(self, vertex_type: str, vertex_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        self.vertices[vertex_type][vertex_id] = {**self.vertices[vertex_type].get(vertex_id, {}), **attributes}
        return {"vertex_type": vertex_type, "vertex_id": vertex_id, "attributes": self.vertices[vertex_type][vertex_id]}

    def upsert_edge(
        self,
        edge_type: str,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        edge = {
            "edge_type": edge_type,
            "from_type": from_type,
            "from_id": from_id,
            "to_type": to_type,
            "to_id": to_id,
            "attributes": attributes,
        }
        self.edges.append(edge)
        return edge
