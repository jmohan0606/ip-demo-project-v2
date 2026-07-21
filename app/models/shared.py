from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.enums import HierarchyLevel, Persona, TimePeriod


class AuditFields(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_system: str = "local_demo"
    source_record_id: str | None = None


class EntityReference(BaseModel):
    entity_type: str
    entity_id: str
    display_name: str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    source_type: str
    title: str
    description: str
    entity_reference: EntityReference | None = None
    metric_name: str | None = None
    metric_value: str | float | int | None = None
    confidence: float | None = None


class ReasoningStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    step_name: str
    description: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ExplainabilityPayload(BaseModel):
    conclusion: str
    confidence_score: float
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class DemoScope(BaseModel):
    persona: Persona = Persona.ADVISOR
    hierarchy_level: HierarchyLevel = HierarchyLevel.ADVISOR
    hierarchy_id: str = "ADV001"
    hierarchy_name: str = "Demo Advisor"
    time_period: TimePeriod = TimePeriod.YTD


class ApiEnvelope(BaseModel):
    success: bool = True
    data: Any | None = None
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: datetime = Field(default_factory=datetime.utcnow)
