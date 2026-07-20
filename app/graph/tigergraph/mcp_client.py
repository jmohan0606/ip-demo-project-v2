from __future__ import annotations

import json
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from app.config.settings import get_settings
from app.graph.tigergraph.mcp_library_client import TigerGraphMcpLibraryClient


class TigerGraphMcpClient:
    """TigerGraph MCP client wrapper.

    Part 12.4 makes the official MCP SDK/library client the primary path.
    Legacy JSON-RPC HTTP remains only as a compatibility fallback for custom gateways.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.library_client = TigerGraphMcpLibraryClient()

    def is_configured(self) -> bool:
        return bool(
            getattr(self.settings, "enable_tigergraph_mcp", False)
            and (
                self.library_client.is_configured()
                or getattr(self.settings, "tigergraph_mcp_url", "")
            )
        )

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}

        if getattr(self.settings, "tigergraph_mcp_use_library_client", True) and self.library_client.is_configured():
            try:
                return self.library_client.call_tool(tool_name, args)
            except Exception as exc:
                # Continue to legacy HTTP only when URL exists.
                if not getattr(self.settings, "tigergraph_mcp_url", ""):
                    raise RuntimeError(f"MCP library client failed and no URL fallback exists: {exc}") from exc
                library_error = exc
        else:
            library_error = None

        try:
            return self._legacy_http_call_tool(tool_name, args)
        except Exception as http_error:
            if library_error:
                raise RuntimeError(
                    f"MCP library client failed: {library_error}; legacy HTTP fallback failed: {http_error}"
                ) from http_error
            raise

    def list_tools(self) -> dict[str, Any]:
        if self.library_client.is_configured():
            return self.library_client.list_tools()
        return {"success": False, "tools": [], "message": "Library MCP client is not configured."}

    def health_check(self) -> dict[str, Any]:
        tool = getattr(self.settings, "tigergraph_mcp_tool_health_check", "health_check")
        if getattr(self.settings, "tigergraph_mcp_list_tools_on_health", True) and self.library_client.is_configured():
            health = self.library_client.health_check()
            health["client"] = "mcp_sdk_library"
            return health
        result = self.call_tool(tool, {"graph": self.settings.tigergraph_graph})
        result["client"] = "mcp_wrapper"
        return result

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        api_key = getattr(self.settings, "tigergraph_mcp_api_key", "")
        if api_key:
            header = getattr(self.settings, "tigergraph_mcp_auth_header", "Authorization")
            scheme = getattr(self.settings, "tigergraph_mcp_auth_scheme", "Bearer")
            headers[header] = f"{scheme} {api_key}".strip()
        return headers

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(url, data=body, headers=self._headers(), method="POST")
        timeout = int(getattr(self.settings, "tigergraph_mcp_timeout_seconds", 30))
        try:
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8")
                return json.loads(text) if text else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"MCP HTTP error {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"MCP connection error: {exc}") from exc

    def _legacy_http_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not getattr(self.settings, "tigergraph_mcp_url", ""):
            raise RuntimeError("TigerGraph MCP URL is not configured for legacy HTTP fallback.")

        base_url = self.settings.tigergraph_mcp_url.rstrip("/")
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "id": "tg-mcp-call",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            response = self._post_json(base_url, json_rpc_payload)
            if "error" in response:
                raise RuntimeError(response["error"])
            return {"success": True, "mode": "mcp_legacy_http", "result": response.get("result", response)}
        except Exception as first_error:
            direct_url = f"{base_url}/tools/{tool_name}"
            try:
                direct = self._post_json(direct_url, arguments)
                return {"success": True, "mode": "mcp_legacy_direct", "result": direct}
            except Exception as second_error:
                raise RuntimeError(
                    f"MCP legacy tool call failed for {tool_name}. "
                    f"jsonrpc_error={first_error}; direct_error={second_error}"
                ) from second_error
