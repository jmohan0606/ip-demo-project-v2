from __future__ import annotations

from typing import Any

from app.graph.access.graph_access_client import GraphAccessClient


class GraphAccessService:
    def __init__(self) -> None:
        self.client = GraphAccessClient()

    def health(self) -> dict[str, Any]:
        return self.client.health().model_dump()

    def health_check_operation(self) -> dict[str, Any]:
        return self.client.health_check().model_dump()

    def schema(self) -> dict[str, Any]:
        return self.client.get_schema().model_dump()

    def run_installed_query(self, query_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.run_installed_query(query_name, params or {}).model_dump()

    def query_graph(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.query_graph(query, params or {}).model_dump()

    def upsert_vertex(self, vertex_type: str, primary_key: str, attributes: dict[str, Any]) -> dict[str, Any]:
        return self.client.upsert_vertex(vertex_type, primary_key, attributes).model_dump()

    def upsert_edge(self, edge_type: str, from_id: str, to_id: str, attributes: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.upsert_edge(edge_type, from_id, to_id, attributes or {}).model_dump()


    def list_mcp_tools(self) -> dict[str, Any]:
        return self.client.mcp.list_tools()
