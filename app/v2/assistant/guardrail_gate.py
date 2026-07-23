"""Input/output guardrail gate for Ask iPerform (FIX_SPEC_R7 A9-A12).

The FIRST thing every user turn passes through — before routing, before
context resolution, before any model call. Wraps the existing V1 guardrail
stack (app/guardrails/client.py: check_input / check_output — eight categories
incl. PROMPT_INJECTION, JAILBREAK, PII with Luhn-validated card numbers,
TOXICITY) which V2 never called until this round.

Actions (A9):
    PROMPT_INJECTION / JAILBREAK / TOXICITY / CONTENT_SAFETY / oversize -> BLOCK
        (no routing, no LLM call; the neutral refusal renders)
    PII -> REDACT before storing and before any provider sees it — a pasted
        SSN or card number never reaches TigerGraph, a log, or a model.

What is persisted (A12): guardrail_status PASS|REDACTED|BLOCKED and
guardrail_json [{category, severity, action}] — category and severity ONLY,
never the matched text or rule (explaining which pattern matched teaches
bypass).

ACCOUNT-NUMBER EXCEPTION (recorded decision): the V1 PII scanner redacts
"account <digits>" references. In THIS application account numbers are the
subject matter — they render on every screen and in stored query results, and
FIX_SPEC_R7 A11 requires "show me account 83700968" to pass untouched. The
gate therefore drops PII-ACCOUNT findings (input and output). SSN, card
numbers, email, phone and secrets remain redacted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.guardrails.models import GuardrailAction, GuardrailResult
from app.guardrails.service import GuardrailService
from app.shared.logging import get_logger

_log = get_logger("app.v2.assistant.guardrails")

# PII sub-rules exempted for the assistant: account references are domain data
# here, not PII (see module docstring). Everything else stays enforced.
_EXEMPT_RULES = {"PII-ACCOUNT"}


@dataclass
class GateResult:
    """What the assistant service needs from a guardrail pass."""
    status: str                      # PASS | REDACTED | BLOCKED
    text: str                        # safe text (redacted if PII found) — the ONLY text stored
    findings: list[dict] = field(default_factory=list)  # [{category, severity, action}]
    refusal: str = ""                # neutral refusal wording when BLOCKED
    note: str = ""                   # one-line user-visible note when REDACTED

    @property
    def blocked(self) -> bool:
        return self.status == "BLOCKED"

    @property
    def findings_json(self) -> str:
        return json.dumps(self.findings) if self.findings else ""


def _strip_exempt(result: GuardrailResult, original_text: str) -> GuardrailResult:
    """Drop exempted findings and, when the ONLY redactions were exempt rules,
    restore the original text so benign account references pass untouched."""
    kept = [f for f in result.findings if f.matched_rule not in _EXEMPT_RULES]
    if len(kept) == len(result.findings):
        return result
    result = result.model_copy(update={"findings": kept})
    if not any(f.action == GuardrailAction.REDACT for f in kept):
        # No non-exempt redaction remains -> the sanitized text only masked
        # exempt spans; rerun the redaction-free view by keeping the original.
        result.sanitized_text = original_text
    action = GuardrailAction.ALLOW
    for f in kept:
        if f.action.rank > action.rank:
            action = f.action
    result.action = action
    result.blocked = action == GuardrailAction.BLOCK
    return result


def screen_input(text: str) -> GateResult:
    """A9 order of operations, step 1 — runs before ANYTHING else sees the text."""
    service = GuardrailService()
    result = _strip_exempt(service.check_input(text or ""), text or "")

    findings = [
        {"category": f.category.value, "severity": f.severity, "action": f.action.value}
        for f in result.findings
    ]
    if result.blocked:
        cats = sorted({f["category"] for f in findings if f["action"] == "BLOCK"})
        _log.warning("assistant input BLOCKED (%s) — no routing, no LLM call", ", ".join(cats))
        return GateResult(
            status="BLOCKED",
            # Store the ORIGINAL text for injection/jailbreak (A9 table: the
            # attempt is part of the audit record) but still through the PII
            # redactor, so a probe that ALSO pastes an SSN never persists it.
            text=result.sanitized_text,
            findings=findings,
            refusal=GuardrailService.neutral_refusal(result),
        )
    if result.redacted:
        cats = sorted({f["category"] for f in findings if f["action"] == "REDACT"})
        _log.info("assistant input REDACTED (%s) before storage/model", ", ".join(cats))
        return GateResult(
            status="REDACTED",
            text=result.sanitized_text,
            findings=findings,
            note="Sensitive details were redacted before processing.",
        )
    return GateResult(status="PASS", text=text or "", findings=findings)


def screen_output(text: str, context: str) -> GateResult:
    """A9 output side — in ADDITION to numeric validation: catches PII
    surfacing from data into a narrative, which numeric validation cannot see."""
    service = GuardrailService()
    result = _strip_exempt(service.check_output(text or "", context or ""), text or "")
    findings = [
        {"category": f.category.value, "severity": f.severity, "action": f.action.value}
        for f in result.findings
        if f.action in (GuardrailAction.BLOCK, GuardrailAction.REDACT)
    ]
    if result.blocked:
        _log.warning("assistant output BLOCKED by guardrails")
        return GateResult(status="BLOCKED", text="", findings=findings,
                          refusal="I couldn't verify that answer, so I won't show it.")
    if result.redacted:
        _log.info("assistant output REDACTED (PII surfaced from narrative)")
        return GateResult(status="REDACTED", text=result.sanitized_text, findings=findings)
    return GateResult(status="PASS", text=text or "")
