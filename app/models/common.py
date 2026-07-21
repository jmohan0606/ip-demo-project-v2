from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str
    app_version: str
    environment: str
    graph_name: str
    schema_prefix: str


class RuntimeStatus(BaseModel):
    component: str
    status: str
    detail: str | None = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)
