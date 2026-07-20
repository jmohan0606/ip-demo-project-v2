from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.graph_access_service import GraphAccessService
from app.shared.responses import ok

router = APIRouter(prefix="/graph-access", tags=["TigerGraph MCP-First Graph Access"])


class QueryGraphRequest(BaseModel):
    query: str
    params: dict[str, Any] = Field(default_factory=dict)


class InstalledQueryRequest(BaseModel):
    query_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class UpsertVertexRequest(BaseModel):
    vertex_type: str
    primary_key: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class UpsertEdgeRequest(BaseModel):
    edge_type: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] = Field(default_factory=dict)


@router.get("/health")
def health():
    return ok(data=GraphAccessService().health())


@router.post("/health-check")
def health_check_operation():
    return ok(data=GraphAccessService().health_check_operation())


@router.get("/schema")
def schema():
    return ok(data=GraphAccessService().schema())


@router.post("/query")
def query_graph(request: QueryGraphRequest):
    return ok(data=GraphAccessService().query_graph(request.query, request.params))


@router.post("/installed-query")
def installed_query(request: InstalledQueryRequest):
    return ok(data=GraphAccessService().run_installed_query(request.query_name, request.params))


@router.post("/upsert-vertex")
def upsert_vertex(request: UpsertVertexRequest):
    return ok(data=GraphAccessService().upsert_vertex(request.vertex_type, request.primary_key, request.attributes))


@router.post("/upsert-edge")
def upsert_edge(request: UpsertEdgeRequest):
    return ok(data=GraphAccessService().upsert_edge(request.edge_type, request.from_id, request.to_id, request.attributes))



@router.get("/mcp-tools")
def mcp_tools():
    return ok(data=GraphAccessService().list_mcp_tools())
