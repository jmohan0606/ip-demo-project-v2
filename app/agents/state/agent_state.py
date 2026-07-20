from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

AgentName = str

class AgentTask(BaseModel):
    task_id: str
    agent_name: AgentName
    instruction: str
    status: str = 'pending'
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

class AgentEvidence(BaseModel):
    source: str
    title: str
    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgenticRequest(BaseModel):
    question: str
    persona: str = 'Advisor'
    scope_type: str = 'Advisor'
    scope_id: str = 'A001'
    time_period: str = 'YTD'
    requested_capabilities: list[str] = Field(default_factory=list)
    write_to_memory: bool = True
    write_to_tigergraph: bool = False

class AgenticResponse(BaseModel):
    run_id: str
    answer: str
    final_agent: str = 'ai_assistant_agent'
    tasks: list[AgentTask] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    revenue_analysis: dict[str, Any] | None = None
    compliance_review: dict[str, Any] | None = None
    coaching_card: dict[str, Any] | None = None
    confidence: float = 0.80
    confidence_breakdown: dict[str, Any] | None = None
    route_plan: list[str] = Field(default_factory=list)
    graph_evidence: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    guardrails: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentWorkflowState(BaseModel):
    request: AgenticRequest
    run_id: str
    current_agent: str = 'supervisor'
    route_plan: list[str] = Field(default_factory=list)
    tasks: list[AgentTask] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    feedback_signals: list[dict[str, Any]] = Field(default_factory=list)
    answer: str = ''
    reasoning_steps: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    confidence: float = 0.80
