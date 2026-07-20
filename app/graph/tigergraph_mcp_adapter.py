from __future__ import annotations

from typing import Any
import os

from app.config import get_runtime_config
from app.graph.tigergraph_mcp_stdio_client import TigerGraphMcpStdioClient, TigerGraphMcpToolMapper


class TigerGraphMcpAdapter:
    """Correct TigerGraph MCP adapter using official stdio MCP tooling."""

    def __init__(self) -> None:
        self.config = get_runtime_config()
        self.enabled = os.getenv("TIGERGRAPH_MCP_ENABLED", str(getattr(self.config, "tigergraph_mcp_enabled", False))).lower() == "true"
        self.client = TigerGraphMcpStdioClient()
        self.mapper = TigerGraphMcpToolMapper(self.client)
        self.last_error: str | None = None

    def _graph_name(self) -> str:
        return os.getenv("TG_GRAPHNAME", getattr(self.config, "tigergraph_graph", "iPerformInsights"))

    def _profile(self) -> str | None:
        return os.getenv("TG_PROFILE") or None

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            return bool(self.mapper.tool_catalog())
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def list_tools(self) -> dict[str, Any]:
        try:
            return {"status": "success", "tools": list(self.mapper.tool_catalog().values())}
        except Exception as exc:
            self.last_error = str(exc)
            return {"status": "failed", "message": str(exc), "tools": []}

    def list_connections(self) -> dict[str, Any]:
        try:
            if self.mapper.has_tool("tigergraph__list_connections"):
                return self.mapper.call("list_connections", {})
            return {"status": "skipped", "message": "Tool tigergraph__list_connections not exposed by this server version."}
        except Exception as exc:
            self.last_error = str(exc)
            return {"status": "failed", "message": str(exc)}

    def execute_query(self, query_name: str, params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params or {})
        graph_name = params.pop("graph_name", None) or self._graph_name()
        profile = params.pop("profile", None) or self._profile()
        return self.mapper.call("run_installed_query", {
            "graph_name": graph_name,
            "query_name": query_name,
            "params": params,
            "profile": profile,
        })

    def run_gsql(self, command: str, profile: str | None = None) -> dict[str, Any]:
        return self.mapper.call("gsql", {"command": command, "profile": profile or self._profile()})

    def get_graph_schema(self, graph_name: str | None = None, profile: str | None = None) -> dict[str, Any]:
        return self.mapper.call("get_graph_schema", {
            "graph_name": graph_name or self._graph_name(),
            "profile": profile or self._profile(),
        })

    def upsert_vertex(self, vertex_type: str, vertex_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        return self.mapper.call("add_node", {
            "graph_name": self._graph_name(),
            "vertex_type": vertex_type,
            "vertex_id": vertex_id,
            "attributes": attributes,
            "profile": self._profile(),
        })

    def upsert_edge(
        self,
        edge_type: str,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        return self.mapper.call("add_edge", {
            "graph_name": self._graph_name(),
            "edge_type": edge_type,
            "source_vertex_type": from_type,
            "source_vertex_id": from_id,
            "target_vertex_type": to_type,
            "target_vertex_id": to_id,
            "attributes": attributes,
            "profile": self._profile(),
        })
