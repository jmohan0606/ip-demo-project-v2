from __future__ import annotations

import re
from typing import Protocol

from app.config.settings import get_settings
from app.guardrails.models import (
    GuardrailAction,
    GuardrailCategory,
    GuardrailFinding,
    GuardrailResult,
)


class GuardrailClientError(RuntimeError):
    pass


class GuardrailClient(Protocol):
    """Adapter interface for input/output guardrails (Section 2 adapter pattern)."""

    def check_input(self, text: str) -> GuardrailResult: ...

    def check_output(self, text: str, context: str) -> GuardrailResult: ...

    def describe(self) -> dict: ...


def _strongest(findings: list[GuardrailFinding]) -> GuardrailAction:
    action = GuardrailAction.ALLOW
    for f in findings:
        if f.action.rank > action.rank:
            action = f.action
    return action


# --- PII patterns (input redaction + output filtering) ---------------------------------------
def _luhn_ok(digits: str) -> bool:
    ds = [int(c) for c in digits if c.isdigit()]
    if len(ds) < 13:
        return False
    checksum, parity = 0, len(ds) % 2
    for i, d in enumerate(ds):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


_PII_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    ("ACCOUNT", re.compile(r"\b(?:acct|account)[-#\s:]*\d{6,}\b", re.IGNORECASE), "[REDACTED_ACCOUNT]"),
    ("API_KEY", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9]{16,}\b"), "[REDACTED_SECRET]"),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_SECRET]"),
]
# credit-card handled separately so a Luhn check gates it (avoid matching plain 16-digit ids)
_CC_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")

# --- Prompt injection / jailbreak patterns (input) -------------------------------------------
_INJECTION_PATTERNS: list[tuple[str, re.Pattern, GuardrailCategory, str]] = [
    ("PI-IGNORE", re.compile(r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)", re.I), GuardrailCategory.PROMPT_INJECTION, "HIGH"),
    ("PI-DISREGARD", re.compile(r"disregard\s+(the\s+)?(above|previous|system|all)", re.I), GuardrailCategory.PROMPT_INJECTION, "HIGH"),
    ("PI-REVEAL", re.compile(r"(reveal|show|print|repeat|expose)\s+(me\s+)?(your\s+)?(system\s+)?(prompt|instructions|rules|guidelines)", re.I), GuardrailCategory.PROMPT_INJECTION, "HIGH"),
    ("PI-OVERRIDE", re.compile(r"(override|bypass|disable|turn\s+off)\s+(your\s+)?(safety|guardrails?|filters?|restrictions?|rules)", re.I), GuardrailCategory.JAILBREAK, "CRITICAL"),
    ("JB-DAN", re.compile(r"\b(do\s+anything\s+now|DAN\s+mode|developer\s+mode|jailbreak)\b", re.I), GuardrailCategory.JAILBREAK, "CRITICAL"),
    ("JB-ROLEPLAY", re.compile(r"you\s+are\s+now\s+(a\s+|an\s+)?(?!the\s+iperform)", re.I), GuardrailCategory.JAILBREAK, "MEDIUM"),
    ("JB-PRETEND", re.compile(r"(pretend|act)\s+(you\s+are|as\s+if|to\s+be)\s+(an?\s+)?(unrestricted|uncensored|evil|different)", re.I), GuardrailCategory.JAILBREAK, "HIGH"),
]

# --- Toxicity / content-safety terms (output) ------------------------------------------------
_TOXIC_TERMS = [
    "kill yourself", "kys", "you should die", "i hate you", "worthless idiot",
    "stupid moron", "go to hell",
]
# Broad slur/harm placeholder set — kept small and obvious; the SmartSDK provider does the
# heavy lifting in the client env. Real, not exhaustive.
_HARM_TERMS = ["make a bomb", "how to hack", "launder money", "evade taxes illegally"]

_MONEY_RE = re.compile(r"\$\s?[\d,]+(?:\.\d+)?[KMB]?|\b\d[\d,]*(?:\.\d+)?%")


class LocalGuardrailClient:
    """Real, dependency-free guardrails: regex PII redaction, prompt-injection/jailbreak
    detection, toxicity/content-safety term matching, and a numeric-grounding heuristic. This is
    the default and the fallback for the SmartSDK provider."""

    def _scan_pii(self, text: str) -> tuple[str, list[GuardrailFinding]]:
        findings: list[GuardrailFinding] = []
        redacted = text
        for name, pat, repl in _PII_PATTERNS:
            if pat.search(redacted):
                count = len(pat.findall(redacted))
                redacted = pat.sub(repl, redacted)
                findings.append(GuardrailFinding(
                    category=GuardrailCategory.PII, severity="HIGH", action=GuardrailAction.REDACT,
                    matched_rule=f"PII-{name}", detail=f"Detected and redacted {count} {name} value(s).",
                    match_preview=repl))
        # credit card with Luhn gate
        for m in list(_CC_PATTERN.finditer(redacted)):
            if _luhn_ok(m.group()):
                redacted = redacted.replace(m.group(), "[REDACTED_CC]")
                findings.append(GuardrailFinding(
                    category=GuardrailCategory.PII, severity="CRITICAL", action=GuardrailAction.REDACT,
                    matched_rule="PII-CC", detail="Detected and redacted a Luhn-valid card number.",
                    match_preview="[REDACTED_CC]"))
        return redacted, findings

    def check_input(self, text: str) -> GuardrailResult:
        text = text or ""
        findings: list[GuardrailFinding] = []

        # input validation / sanitization
        if len(text) > 8000:
            findings.append(GuardrailFinding(
                category=GuardrailCategory.INPUT_VALIDATION, severity="MEDIUM",
                action=GuardrailAction.BLOCK, matched_rule="IV-LENGTH",
                detail=f"Input length {len(text)} exceeds the 8000-char guardrail."))

        # prompt injection / jailbreak
        for name, pat, cat, sev in _INJECTION_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append(GuardrailFinding(
                    category=cat, severity=sev, action=GuardrailAction.BLOCK,
                    matched_rule=name, detail=f"{cat.value} pattern matched: '{m.group()[:60]}'.",
                    match_preview=m.group()[:60]))

        # PII detection + redaction
        sanitized, pii = self._scan_pii(text)
        findings.extend(pii)

        action = _strongest(findings)
        return GuardrailResult(
            stage="input", action=action, blocked=(action == GuardrailAction.BLOCK),
            findings=findings, sanitized_text=sanitized, original_text=text, provider="local")

    def check_output(self, text: str, context: str) -> GuardrailResult:
        text = text or ""
        findings: list[GuardrailFinding] = []

        # PII filtering on the outbound answer
        sanitized, pii = self._scan_pii(text)
        findings.extend(pii)

        # toxicity / content safety
        low = text.lower()
        for term in _TOXIC_TERMS:
            if term in low:
                findings.append(GuardrailFinding(
                    category=GuardrailCategory.TOXICITY, severity="HIGH", action=GuardrailAction.BLOCK,
                    matched_rule="TOX-TERM", detail=f"Toxic/harmful phrase detected: '{term}'.",
                    match_preview=term))
        for term in _HARM_TERMS:
            if term in low:
                findings.append(GuardrailFinding(
                    category=GuardrailCategory.CONTENT_SAFETY, severity="HIGH", action=GuardrailAction.BLOCK,
                    matched_rule="CS-TERM", detail=f"Unsafe-content phrase detected: '{term}'.",
                    match_preview=term))

        # grounding / hallucination: every $ / % figure in the answer should appear in the context
        grounding_score = self._grounding_score(text, context or "")
        claims = _MONEY_RE.findall(text)
        if claims and grounding_score is not None and grounding_score < 0.5:
            findings.append(GuardrailFinding(
                category=GuardrailCategory.HALLUCINATION, severity="MEDIUM", action=GuardrailAction.FLAG,
                matched_rule="GND-NUMERIC",
                detail=(f"{int(grounding_score * 100)}% of the {len(claims)} numeric claim(s) in the "
                        "answer appear in the retrieved context — possible ungrounded figures.")))

        action = _strongest(findings)
        return GuardrailResult(
            stage="output", action=action, blocked=(action == GuardrailAction.BLOCK),
            findings=findings, sanitized_text=sanitized, original_text=text,
            grounding_score=grounding_score, provider="local")

    @staticmethod
    def _grounding_score(answer: str, context: str) -> float | None:
        claims = _MONEY_RE.findall(answer)
        if not claims:
            return None
        ctx = context.replace(",", "").replace(" ", "")
        supported = 0
        for c in claims:
            norm = c.replace(",", "").replace(" ", "").replace("$", "")
            if norm and norm in ctx.replace("$", ""):
                supported += 1
        return round(supported / len(claims), 3)

    def describe(self) -> dict:
        return {"mode": "local", "provider": "regex+heuristic",
                "checks": ["pii", "prompt_injection", "jailbreak", "input_validation",
                           "toxicity", "content_safety", "grounding"]}


class SmartSdkGuardrailClient:
    """SmartSDK EvaluationService-backed output guardrails (client env). EvaluationService scores
    toxicity / qa_correctness / hallucination (SMARTSDK_REFERENCE.md §6). Input PII/injection still
    use the local scanners (fast, deterministic, no round-trip); output adds SmartSDK's scores on
    top of the local checks. Guarded import — smart_sdk only loads when this mode is selected."""

    def __init__(self) -> None:
        self._local = LocalGuardrailClient()
        try:
            from smart_sdk.evals import EvaluationService  # type: ignore  # noqa: F401
        except ImportError as exc:  # pragma: no cover — client-only package
            raise GuardrailClientError(
                "GUARDRAIL_CLIENT_MODE=smartsdk requires the client-only 'smart_sdk' package. "
                "Use GUARDRAIL_CLIENT_MODE=local here. Error: " + str(exc)
            ) from exc
        self._eval_cls = EvaluationService

    def _service(self):
        # Build per-call so config changes are picked up; the model is supplied by the LLM adapter
        # in the client env. Kept lazy to avoid holding a live handle across requests.
        return self._eval_cls(evaluation_input={
            "toxicity": None,
            "qa_correctness": {},
            "hallucination": {},
        })

    def check_input(self, text: str) -> GuardrailResult:
        # Injection/PII are deterministic and cheap — always local, no model round-trip.
        return self._local.check_input(text)

    def check_output(self, text: str, context: str) -> GuardrailResult:
        result = self._local.check_output(text, context)
        result.provider = "smartsdk"
        try:
            svc = self._service()
            scores = svc.evaluate(prediction=text, reference=context)  # type: ignore[attr-defined]
            tox = float((scores or {}).get("toxicity", 0) or 0)
            hall = float((scores or {}).get("hallucination", 0) or 0)
            if tox >= 0.5:
                result.findings.append(GuardrailFinding(
                    category=GuardrailCategory.TOXICITY, severity="HIGH", action=GuardrailAction.BLOCK,
                    matched_rule="SMARTSDK-TOXICITY", detail=f"EvaluationService toxicity={tox:.2f}"))
            if hall >= 0.5:
                result.findings.append(GuardrailFinding(
                    category=GuardrailCategory.HALLUCINATION, severity="MEDIUM", action=GuardrailAction.FLAG,
                    matched_rule="SMARTSDK-HALLUCINATION", detail=f"EvaluationService hallucination={hall:.2f}"))
            result.action = _strongest(result.findings)
            result.blocked = result.action == GuardrailAction.BLOCK
        except Exception as exc:  # noqa: BLE001 — fall back to the local result, never break the answer
            result.findings.append(GuardrailFinding(
                category=GuardrailCategory.POLICY, severity="LOW", action=GuardrailAction.FLAG,
                matched_rule="SMARTSDK-UNAVAILABLE",
                detail=f"SmartSDK EvaluationService unavailable, used local checks: {exc}"))
        return result

    def describe(self) -> dict:
        return {"mode": "smartsdk", "provider": "smart_sdk.evals.EvaluationService + local",
                "checks": ["pii", "prompt_injection", "jailbreak", "toxicity", "hallucination", "qa_correctness"]}


_guardrail_client: GuardrailClient | None = None


def get_guardrail_client() -> GuardrailClient:
    """Select the GuardrailClient per GUARDRAIL_CLIENT_MODE (local | smartsdk)."""
    global _guardrail_client
    if _guardrail_client is None:
        mode = getattr(get_settings(), "guardrail_client_mode", "local").lower()
        if mode == "local":
            _guardrail_client = LocalGuardrailClient()
        elif mode == "smartsdk":
            _guardrail_client = SmartSdkGuardrailClient()
        else:
            raise GuardrailClientError(f"Unknown GUARDRAIL_CLIENT_MODE '{mode}' (expected local|smartsdk)")
    return _guardrail_client


def reset_guardrail_client() -> None:
    global _guardrail_client
    _guardrail_client = None
