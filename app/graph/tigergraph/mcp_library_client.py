from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any

from app.config.settings import get_settings


class TigerGraphMcpLibraryClient:
    """Library-based MCP client for an existing TigerGraph MCP server.

    Uses the official Python `mcp` SDK transports instead of hand-written JSON-RPC.
    The `tigergraph-mcp` package itself is the TigerGraph MCP server package; this
    application connects to an already-running TigerGraph MCP endpoint or can use
    stdio mode to launch a local MCP server command when configured.

    Supported modes:
      - streamable_http: MCP Streamable HTTP transport
      - sse: MCP SSE transport
      - stdio: MCP stdio transport, useful for `python -m tigergraph_mcp`
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return bool(
            getattr(self.settings, "enable_tigergraph_mcp", False)
            and getattr(self.settings, "tigergraph_mcp_use_library_client", True)
            and (
                getattr(self.settings, "tigergraph_mcp_url", "")
                or getattr(self.settings, "tigergraph_mcp_client_mode", "") == "stdio"
            )
        )

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("TigerGraph MCP library client is not configured.")
        return asyncio.run(self._call_tool_async(tool_name, arguments or {}))

    def list_tools(self) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("TigerGraph MCP library client is not configured.")
        return asyncio.run(self._list_tools_async())

    def health_check(self) -> dict[str, Any]:
        data: dict[str, Any] = {"success": True, "mode": "mcp_library", "message": "MCP library client configured."}
        if getattr(self.settings, "tigergraph_mcp_list_tools_on_health", True):
            tools = self.list_tools()
            data["tools"] = tools.get("tools", [])
            data["tool_count"] = len(data["tools"])
        return data

    async def _open_session(self):
        mode = getattr(self.settings, "tigergraph_mcp_client_mode", "streamable_http")
        stack = AsyncExitStack()
        try:
            if mode == "stdio":
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client

                args_raw = getattr(self.settings, "tigergraph_mcp_stdio_args", "-m,tigergraph_mcp")
                args = [x for x in args_raw.split(",") if x]
                command = getattr(self.settings, "tigergraph_mcp_stdio_command", "python")
                server_params = StdioServerParameters(command=command, args=args)
                read, write = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                return stack, session

            if mode == "sse":
                from mcp import ClientSession
                from mcp.client.sse import sse_client

                url = self.settings.tigergraph_mcp_url
                read, write = await stack.enter_async_context(sse_client(url))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                return stack, session

            # Default: streamable HTTP
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            url = self.settings.tigergraph_mcp_url
            read, write, _ = await stack.enter_async_context(streamablehttp_client(url))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            return stack, session

        except Exception:
            await stack.aclose()
            raise

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        stack, session = await self._open_session()
        try:
            result = await session.call_tool(tool_name, arguments)
            return self._normalize_tool_result(result)
        finally:
            await stack.aclose()

    async def _list_tools_async(self) -> dict[str, Any]:
        stack, session = await self._open_session()
        try:
            result = await session.list_tools()
            tools = []
            for tool in getattr(result, "tools", []) or []:
                tools.append(
                    {
                        "name": getattr(tool, "name", ""),
                        "description": getattr(tool, "description", ""),
                        "input_schema": getattr(tool, "inputSchema", None),
                    }
                )
            return {"success": True, "tools": tools}
        finally:
            await stack.aclose()

    def _normalize_tool_result(self, result: Any) -> dict[str, Any]:
        # MCP SDK CallToolResult commonly exposes `content`.
        content = getattr(result, "content", None)
        if content:
            parsed = []
            for item in content:
                text = getattr(item, "text", None)
                if text is not None:
                    try:
                        parsed.append(json.loads(text))
                    except Exception:
                        parsed.append({"text": text})
                else:
                    parsed.append(str(item))
            if len(parsed) == 1 and isinstance(parsed[0], dict):
                data = parsed[0]
            else:
                data = {"content": parsed}
        else:
            data = {"result": str(result)}

        is_error = bool(getattr(result, "isError", False))
        return {
            "success": not is_error,
            "mode": "mcp_library",
            "is_error": is_error,
            "data": data,
        }
