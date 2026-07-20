"""Input/output AI guardrails (Security & Governance poster, sections 1 & 3).

A real, wired guardrail layer on the AI request/response path — input guardrails (PII
detection/redaction, prompt-injection & jailbreak detection, input validation) and output
guardrails (PII filtering, toxicity/content-safety, grounding/hallucination check, redaction).

Adapter discipline (same as Graph/LLM/Embedding): `GUARDRAIL_CLIENT_MODE=local|smartsdk` selects
the implementation. `local` (default) is a real regex/heuristic implementation; `smartsdk` plugs
in JPMC's SmartSDK EvaluationService (toxicity/qa_correctness/hallucination) in the client env.
"""

from app.guardrails.client import get_guardrail_client
from app.guardrails.models import GuardrailAction, GuardrailFinding, GuardrailResult
from app.guardrails.service import GuardrailService

__all__ = [
    "get_guardrail_client",
    "GuardrailAction",
    "GuardrailFinding",
    "GuardrailResult",
    "GuardrailService",
]
