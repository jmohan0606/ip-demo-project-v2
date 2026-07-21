from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import RuntimeComponentStatus

class ComponentHealth(BaseModel):
    component_name: str
    status: RuntimeComponentStatus
    detail: str | None = None
    configured: bool = False
    checked_at: datetime = Field(default_factory=datetime.utcnow)

class RuntimeHealthReport(BaseModel):
    application: str
    version: str
    environment: str
    graph_name: str
    schema_prefix: str
    overall_status: RuntimeComponentStatus
    components: list[ComponentHealth] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)
