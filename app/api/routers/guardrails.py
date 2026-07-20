from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.guardrails.service import GuardrailService
from app.shared.responses import ok

router = APIRouter(prefix="/guardrails", tags=["Security & Governance — Guardrails"])


class GuardrailInputRequest(BaseModel):
    text: str


class GuardrailOutputRequest(BaseModel):
    text: str
    context: str = ""


@router.get("/status")
def status():
    """Which guardrail provider is active and which checks it runs."""
    return ok(data=GuardrailService().describe())


@router.post("/check-input")
def check_input(request: GuardrailInputRequest):
    """Run the INPUT guardrails (PII redaction, prompt-injection/jailbreak, input validation)."""
    return ok(data=GuardrailService().check_input(request.text).model_dump())


@router.post("/check-output")
def check_output(request: GuardrailOutputRequest):
    """Run the OUTPUT guardrails (PII filtering, toxicity/content-safety, grounding/hallucination)."""
    return ok(data=GuardrailService().check_output(request.text, request.context).model_dump())
