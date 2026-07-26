"""Input/output guardrail gate for Ask iPerform (FIX_SPEC_R7 A9-A12, R14).

The FIRST thing every user turn passes through — before routing, before
context resolution, before any model call. Wraps the existing V1 guardrail
stack (app/guardrails/client.py: check_input / check_output — eight categories
incl. PROMPT_INJECTION, JAILBREAK, PII with Luhn-validated card numbers,
TOXICITY) which V2 never called until R7.

R14 — DEFENSE IN DEPTH. screen_input is now three layers, in order:
  1. regex pre-filter (existing, unchanged): PII redaction + literal patterns
  2. LLM intent classifier (app/v2/assistant/intent_classifier) on the
     PII-redacted text — catches PARAPHRASED attacks regex misses; ADDITIVE
     only, never downgrades a regex BLOCK; fails SAFE when unavailable (D)
  3. the hardened assistant system prompt (system_prompts) backstops both.
screen_output additionally blocks responses leaking system-prompt fragments.
GUARDRAILS_ENABLED gates the whole stack; GUARDRAIL_LLM_ENABLED gates layer 2.

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

from app.config.settings import get_settings
from app.guardrails.models import GuardrailAction, GuardrailResult
from app.guardrails.service import GuardrailService
from app.shared.logging import get_logger
from app.v2.assistant.intent_classifier import (
    BLOCK_CATEGORIES,
    ClassifierUnavailable,
    classify,
)
from app.v2.assistant.system_prompts import leaks_system_prompt

_log = get_logger("app.v2.assistant.guardrails")

# PII sub-rules exempted for the assistant: account references are domain data
# here, not PII (see module docstring). Everything else stays enforced.
_EXEMPT_RULES = {"PII-ACCOUNT"}

# R15 B — the regex INJECTION/JAILBREAK pattern rules (app/guardrails/client.py
# _INJECTION_PATTERNS use these prefixes). GUARDRAIL_REGEX_ENABLED=false
# bypasses ONLY these pattern-based BLOCK findings — NOT PII redaction (which
# stays active: redaction is cheap and safe; only the injection/jailbreak
# pattern matching is bypassed) and NOT the oversize input check (IV-LENGTH).
_PATTERN_BLOCK_PREFIXES = ("PI-", "JB-")


@dataclass
class GateResult:
    """What the assistant service needs from a guardrail pass."""
    status: str                      # PASS | REDACTED | BLOCKED
    text: str                        # safe text (redacted if PII found) — the ONLY text stored
    findings: list[dict] = field(default_factory=list)  # [{category, severity, action}]
    refusal: str = ""                # neutral refusal wording when BLOCKED
    note: str = ""                   # one-line user-visible note when REDACTED
    # R14 B3 — the LLM classifier judged the input off_scope_use: not a
    # guardrail block, the service routes it to the existing polite
    # OUT_OF_SCOPE decline (before routing, so no selector LLM call).
    out_of_scope: bool = False

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


def _demote_pattern_blocks(result: GuardrailResult) -> GuardrailResult:
    """R15 B — GUARDRAIL_REGEX_ENABLED=false: demote regex injection/jailbreak
    PATTERN blocks to FLAG (kept as an audit trail) so the block decision is
    the LLM classifier's alone. PII redaction findings and IV-LENGTH are left
    untouched — redaction stays on regardless of this toggle."""
    demoted = []
    kept = []
    for f in result.findings:
        if (f.action == GuardrailAction.BLOCK
                and f.matched_rule.startswith(_PATTERN_BLOCK_PREFIXES)):
            kept.append(f.model_copy(update={"action": GuardrailAction.FLAG}))
            demoted.append(f.matched_rule)
        else:
            kept.append(f)
    if not demoted:
        return result
    result = result.model_copy(update={"findings": kept})
    action = GuardrailAction.ALLOW
    for f in kept:
        if f.action.rank > action.rank:
            action = f.action
    result.action = action
    result.blocked = action == GuardrailAction.BLOCK
    _log.warning(
        "GUARDRAIL_REGEX_ENABLED=false — regex pattern match(es) %s NOT blocking "
        "(demoted to FLAG); block decision deferred to the LLM classifier; "
        "PII redaction remains ACTIVE", ", ".join(demoted))
    return result


def _classifier_severity(confidence: float) -> str:
    if confidence >= 0.9:
        return "CRITICAL"
    if confidence >= 0.7:
        return "HIGH"
    return "MEDIUM"


def screen_input(text: str) -> GateResult:
    """A9 order of operations, step 1 — runs before ANYTHING else sees the text.

    R14 defense in depth, in order:
      1. regex pre-filter (existing): PII redaction + literal patterns
      2. LLM intent classifier on the PII-REDACTED text (never raw PII)
      3. combine: EITHER layer's block blocks; the classifier NEVER downgrades
         a regex BLOCK (a regex block returns before the classifier runs).
    Fail-safe (R14 D): a classifier failure is logged as a degradation and the
    regex result stands — the turn proceeds only to the scoped router; the
    hardened system prompt is the backstop. Never fail open, never full-trust.
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        # Config kill-switch for the WHOLE stack (R14 B3) — loud, never silent.
        _log.warning("GUARDRAILS_ENABLED=false — input guardrail stack skipped")
        return GateResult(status="PASS", text=text or "")

    service = GuardrailService()
    result = _strip_exempt(service.check_input(text or ""), text or "")
    if not settings.guardrail_regex_enabled:
        # R15 B — posture noted on every screened turn so the operator can see
        # the active configuration in the logs (Env Health shows it too).
        _log.info("guardrail posture: regex PATTERN blocking DISABLED "
                  "(GUARDRAIL_REGEX_ENABLED=false) — classifier-only block "
                  "decisions; PII redaction still active")
        result = _demote_pattern_blocks(result)

    findings = [
        {"category": f.category.value, "severity": f.severity, "action": f.action.value}
        for f in result.findings
    ]
    if result.blocked:
        # Layer-1 BLOCK is final — the classifier is additive-only and can
        # never downgrade it (R14 B4), so it is not consulted.
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

    # Regex layer passed (possibly with redactions). Layer 2 — the LLM intent
    # classifier, on the SANITIZED text only (raw PII never reaches a model).
    safe_text = result.sanitized_text if result.redacted else (text or "")
    out_of_scope = False
    if settings.guardrail_llm_enabled:
        try:
            cls = classify(safe_text, settings)
        except Exception as exc:  # noqa: BLE001 — incl. ClassifierUnavailable
            # R14 D — FAIL SAFE, never open: the regex result stands, the turn
            # proceeds ONLY to the deterministic scoped router (which cannot
            # execute arbitrary actions); the hardened system prompt (R14 C)
            # is the backstop. Logged every time — never a silent full-trust.
            _log.warning(
                "GUARDRAIL DEGRADATION (R14 D): LLM intent classifier unavailable "
                "(%s) — failing SAFE: regex result stands, turn proceeds only to "
                "the scoped router under the hardened system prompt", exc)
            findings.append({"category": "CLASSIFIER_DEGRADED", "severity": "LOW",
                             "action": "FLAG"})
            cls = None
        if cls is not None:
            if (cls.category in BLOCK_CATEGORIES
                    and cls.confidence >= settings.guardrail_block_threshold):
                severity = _classifier_severity(cls.confidence)
                # category + severity ONLY are persisted/rendered — the
                # classifier's `reason` NEVER leaves the log (R14 F).
                findings.append({"category": cls.category.upper(),
                                 "severity": severity, "action": "BLOCK"})
                _log.warning(
                    "assistant input BLOCKED by LLM intent classifier "
                    "(%s, confidence %.2f, served=%s) — no routing, no LLM call; "
                    "reason (log-only): %s",
                    cls.category, cls.confidence, cls.served_path, cls.reason)
                return GateResult(
                    status="BLOCKED", text=safe_text, findings=findings,
                    refusal=GuardrailService.neutral_refusal(),
                )
            if (cls.category == "off_scope_use"
                    and cls.confidence >= settings.guardrail_block_threshold):
                _log.info("LLM intent classifier judged the input off_scope_use "
                          "(confidence %.2f) — polite OUT_OF_SCOPE decline",
                          cls.confidence)
                out_of_scope = True

    if result.redacted:
        cats = sorted({f["category"] for f in findings if f["action"] == "REDACT"})
        _log.info("assistant input REDACTED (%s) before storage/model", ", ".join(cats))
        return GateResult(
            status="REDACTED",
            text=result.sanitized_text,
            findings=findings,
            note="Sensitive details were redacted before processing.",
            out_of_scope=out_of_scope,
        )
    return GateResult(status="PASS", text=text or "", findings=findings,
                      out_of_scope=out_of_scope)


def screen_output(text: str, context: str) -> GateResult:
    """A9 output side — in ADDITION to numeric validation: catches PII
    surfacing from data into a narrative, which numeric validation cannot see.

    R14 E adds a deterministic system-prompt LEAK check: a response that
    contains fragments of the assistant/classifier system prompts is BLOCKED
    (the honest "couldn't verify" message renders; the leaking text never
    displays). Compliance with injected instructions is covered upstream (the
    input classifier blocks the injection) and by the numeric/grounding checks.
    """
    if not get_settings().guardrails_enabled:
        _log.warning("GUARDRAILS_ENABLED=false — output guardrail stack skipped")
        return GateResult(status="PASS", text=text or "")

    service = GuardrailService()
    result = _strip_exempt(service.check_output(text or "", context or ""), text or "")
    findings = [
        {"category": f.category.value, "severity": f.severity, "action": f.action.value}
        for f in result.findings
        if f.action in (GuardrailAction.BLOCK, GuardrailAction.REDACT)
    ]
    if leaks_system_prompt(text or ""):
        # R14 E — never display the leaking text; category+severity only.
        findings.append({"category": "SYSTEM_PROMPT_LEAK", "severity": "CRITICAL",
                         "action": "BLOCK"})
        _log.warning("assistant output BLOCKED — system-prompt/instruction "
                     "fragment detected in the response (R14 E)")
        return GateResult(status="BLOCKED", text="", findings=findings,
                          refusal="I couldn't verify that answer, so I won't show it.")
    if result.blocked:
        _log.warning("assistant output BLOCKED by guardrails")
        return GateResult(status="BLOCKED", text="", findings=findings,
                          refusal="I couldn't verify that answer, so I won't show it.")
    if result.redacted:
        _log.info("assistant output REDACTED (PII surfaced from narrative)")
        return GateResult(status="REDACTED", text=result.sanitized_text, findings=findings)
    return GateResult(status="PASS", text=text or "")
