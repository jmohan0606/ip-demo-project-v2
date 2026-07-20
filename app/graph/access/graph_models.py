from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GraphAccessMode(StrEnum):
    MCP = "mcp"
    REST = "rest"
    MOCK = "mock"
    UNAVAILABLE = "unavailable"


class GraphOperation(StrEnum):
    HEALTH_CHECK = "health_check"
    QUERY_GRAPH = "query_graph"
    RUN_INSTALLED_QUERY = "run_installed_query"
    UPSERT_VERTEX = "upsert_vertex"
    UPSERT_EDGE = "upsert_edge"
    RUN_GSQL = "run_gsql"
    GET_SCHEMA = "get_schema"


class GraphAccessResult(BaseModel):
    success: bool
    mode: GraphAccessMode
    operation: GraphOperation
    data: Any = None
    message: str = ""
    error: str | None = None
    attempted_modes: list[GraphAccessMode] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GraphHealthStatus(BaseModel):
    active_mode: GraphAccessMode
    mcp_available: bool
    rest_available: bool
    mock_available: bool
    graph_name: str
    strategy: str
    details: dict = Field(default_factory=dict)
