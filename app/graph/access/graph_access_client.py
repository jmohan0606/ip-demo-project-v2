from __future__ import annotations

from typing import Any

from app.config.settings import get_settings
from app.graph.access.graph_models import GraphAccessMode, GraphAccessResult, GraphHealthStatus, GraphOperation
from app.graph.mock.mock_graph_data_service import MockGraphDataService
from app.graph.tigergraph.mcp_client import TigerGraphMcpClient
from app.graph.tigergraph.rest_client import TigerGraphRestClient


class GraphAccessClient:
    """Central MCP-first graph access layer.

    All graph operations should route here:
        MCP -> REST -> Mock
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.mcp = TigerGraphMcpClient()
        self.rest = TigerGraphRestClient()
        self.mock = MockGraphDataService()

    def health(self) -> GraphHealthStatus:
        details = {}
        mcp_ok = False
        rest_ok = False
        mock_ok = self.mock.available()

        if self.mcp.is_configured():
            try:
                details["mcp"] = self.mcp.health_check()
                mcp_ok = True
            except Exception as exc:
                details["mcp_error"] = str(exc)

        if self.rest.is_configured():
            try:
                details["rest"] = self.rest.health_check() if hasattr(self.rest, "health_check") else {"success": True}
                rest_ok = True
            except Exception as exc:
                details["rest_error"] = str(exc)

        if mock_ok:
            details["mock"] = self.mock.health_check()

        active = GraphAccessMode.MCP if mcp_ok else GraphAccessMode.REST if rest_ok else GraphAccessMode.MOCK if mock_ok else GraphAccessMode.UNAVAILABLE

        return GraphHealthStatus(
            active_mode=active,
            mcp_available=mcp_ok,
            rest_available=rest_ok,
            mock_available=mock_ok,
            graph_name=self.settings.tigergraph_graph,
            strategy=getattr(self.settings, "graph_access_strategy", "mcp_rest_mock"),
            details=details,
        )

    def _tool_name(self, operation: GraphOperation) -> str:
        mapping = {
            GraphOperation.HEALTH_CHECK: "tigergraph_mcp_tool_health_check",
            GraphOperation.QUERY_GRAPH: "tigergraph_mcp_tool_query_graph",
            GraphOperation.RUN_INSTALLED_QUERY: "tigergraph_mcp_tool_run_installed_query",
            GraphOperation.UPSERT_VERTEX: "tigergraph_mcp_tool_upsert_vertex",
            GraphOperation.UPSERT_EDGE: "tigergraph_mcp_tool_upsert_edge",
            GraphOperation.RUN_GSQL: "tigergraph_mcp_tool_run_gsql",
            GraphOperation.GET_SCHEMA: "tigergraph_mcp_tool_get_schema",
        }
        return getattr(self.settings, mapping[operation], operation.value)

    def _run_with_fallbacks(self, operation: GraphOperation, payload: dict[str, Any]) -> GraphAccessResult:
        attempted: list[GraphAccessMode] = []
        errors: list[str] = []

        # 1. MCP first.
        if self.mcp.is_configured():
            attempted.append(GraphAccessMode.MCP)
            try:
                data = self.mcp.call_tool(self._tool_name(operation), payload)
                return GraphAccessResult(
                    success=True, mode=GraphAccessMode.MCP, operation=operation,
                    data=data, message="Operation completed via TigerGraph MCP.",
                    attempted_modes=attempted,
                )
            except Exception as exc:
                errors.append(f"mcp: {exc}")

        # 2. REST fallback.
        if self.rest.is_configured() and getattr(self.settings, "enable_tigergraph_rest_fallback", True):
            attempted.append(GraphAccessMode.REST)
            try:
                data = self._run_rest(operation, payload)
                return GraphAccessResult(
                    success=True, mode=GraphAccessMode.REST, operation=operation,
                    data=data, message="Operation completed via TigerGraph REST fallback.",
                    attempted_modes=attempted,
                )
            except Exception as exc:
                errors.append(f"rest: {exc}")

        # 3. Mock final fallback.
        if getattr(self.settings, "enable_local_mock_fallback", True) and self.mock.available():
            attempted.append(GraphAccessMode.MOCK)
            try:
                data = self._run_mock(operation, payload)
                return GraphAccessResult(
                    success=True, mode=GraphAccessMode.MOCK, operation=operation,
                    data=data, message="Operation completed via local mock graph fallback.",
                    attempted_modes=attempted,
                )
            except Exception as exc:
                errors.append(f"mock: {exc}")

        return GraphAccessResult(
            success=False, mode=GraphAccessMode.UNAVAILABLE, operation=operation,
            error="; ".join(errors) or "No graph access mode is available.",
            attempted_modes=attempted,
        )

    def _run_rest(self, operation: GraphOperation, payload: dict[str, Any]) -> dict[str, Any]:
        graph = self.settings.tigergraph_graph
        if operation == GraphOperation.UPSERT_VERTEX:
            return self.rest.post(f"graph/{graph}/vertices/{payload['vertex_type']}", payload)
        if operation == GraphOperation.UPSERT_EDGE:
            return self.rest.post(f"graph/{graph}/edges/{payload['edge_type']}", payload)
        if operation == GraphOperation.RUN_INSTALLED_QUERY:
            query_name = payload["query_name"]
            return self.rest.post(f"query/{graph}/{query_name}", payload.get("params", {}))
        if operation == GraphOperation.QUERY_GRAPH:
            return self.rest.post(f"graph/{graph}/query", payload)
        if operation == GraphOperation.RUN_GSQL:
            return self.rest.post("gsql", payload)
        if operation == GraphOperation.GET_SCHEMA:
            return self.rest.get(f"graph/{graph}/schema") if hasattr(self.rest, "get") else self.rest.post(f"graph/{graph}/schema", {})
        if operation == GraphOperation.HEALTH_CHECK:
            return self.rest.health_check() if hasattr(self.rest, "health_check") else {"success": True}
        raise ValueError(f"Unsupported REST graph operation: {operation}")

    def _run_mock(self, operation: GraphOperation, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == GraphOperation.HEALTH_CHECK:
            return self.mock.health_check()
        if operation == GraphOperation.UPSERT_VERTEX:
            return self.mock.upsert_vertex(payload["vertex_type"], payload["primary_key"], payload.get("attributes", {}))
        if operation == GraphOperation.UPSERT_EDGE:
            return self.mock.upsert_edge(payload["edge_type"], payload["from_id"], payload["to_id"], payload.get("attributes", {}))
        if operation == GraphOperation.RUN_INSTALLED_QUERY:
            return self.mock.run_installed_query(payload["query_name"], payload.get("params", {}))
        if operation == GraphOperation.QUERY_GRAPH:
            return self.mock.query_graph(payload["query"], payload.get("params", {}))
        if operation == GraphOperation.RUN_GSQL:
            return self.mock.run_gsql(payload["gsql"], payload.get("params", {}))
        if operation == GraphOperation.GET_SCHEMA:
            return self.mock.get_schema()
        raise ValueError(f"Unsupported mock graph operation: {operation}")

    def health_check(self) -> GraphAccessResult:
        return self._run_with_fallbacks(GraphOperation.HEALTH_CHECK, {"graph": self.settings.tigergraph_graph})

    def upsert_vertex(self, vertex_type: str, primary_key: str, attributes: dict[str, Any]) -> GraphAccessResult:
        return self._run_with_fallbacks(
            GraphOperation.UPSERT_VERTEX,
            {"graph": self.settings.tigergraph_graph, "vertex_type": vertex_type, "primary_key": primary_key, "attributes": attributes},
        )

    def upsert_edge(self, edge_type: str, from_id: str, to_id: str, attributes: dict[str, Any] | None = None) -> GraphAccessResult:
        return self._run_with_fallbacks(
            GraphOperation.UPSERT_EDGE,
            {"graph": self.settings.tigergraph_graph, "edge_type": edge_type, "from_id": from_id, "to_id": to_id, "attributes": attributes or {}},
        )

    def run_installed_query(self, query_name: str, params: dict[str, Any] | None = None) -> GraphAccessResult:
        return self._run_with_fallbacks(
            GraphOperation.RUN_INSTALLED_QUERY,
            {"graph": self.settings.tigergraph_graph, "query_name": query_name, "params": params or {}},
        )

    def query_graph(self, query: str, params: dict[str, Any] | None = None) -> GraphAccessResult:
        return self._run_with_fallbacks(
            GraphOperation.QUERY_GRAPH,
            {"graph": self.settings.tigergraph_graph, "query": query, "params": params or {}},
        )

    def run_gsql(self, gsql: str, params: dict[str, Any] | None = None) -> GraphAccessResult:
        return self._run_with_fallbacks(
            GraphOperation.RUN_GSQL,
            {"graph": self.settings.tigergraph_graph, "gsql": gsql, "params": params or {}},
        )

    def get_schema(self) -> GraphAccessResult:
        return self._run_with_fallbacks(GraphOperation.GET_SCHEMA, {"graph": self.settings.tigergraph_graph})
