from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class GuardrailAction(str, Enum):
    """What the guardrail decided to do with the content. Ordered by severity so the overall
    result can take the strongest action across all findings."""
    ALLOW = "ALLOW"      # nothing found
    FLAG = "FLAG"        # surfaced for review, content unchanged (e.g. possible ungrounded claim)
    REDACT = "REDACT"    # sensitive spans masked; sanitized content is safe to use
    BLOCK = "BLOCK"      # content must not be sent to the model / returned to the user

    @property
    def rank(self) -> int:
        return {"ALLOW": 0, "FLAG": 1, "REDACT": 2, "BLOCK": 3}[self.value]


class GuardrailCategory(str, Enum):
    PII = "PII"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    JAILBREAK = "JAILBREAK"
    TOXICITY = "TOXICITY"
    CONTENT_SAFETY = "CONTENT_SAFETY"
    HALLUCINATION = "HALLUCINATION"
    GROUNDING = "GROUNDING"
    POLICY = "POLICY"
    INPUT_VALIDATION = "INPUT_VALIDATION"


class GuardrailFinding(BaseModel):
    category: GuardrailCategory
    severity: str            # LOW | MEDIUM | HIGH | CRITICAL
    action: GuardrailAction
    matched_rule: str        # the rule/pattern id or name that fired
    detail: str              # human-readable explanation
    match_preview: str = ""  # short, already-masked preview of what matched (never the raw secret)


class GuardrailResult(BaseModel):
    stage: str                                   # "input" | "output"
    action: GuardrailAction = GuardrailAction.ALLOW
    blocked: bool = False
    findings: list[GuardrailFinding] = Field(default_factory=list)
    sanitized_text: str = ""                     # input/output with PII redacted (== original if none)
    original_text: str = ""
    grounding_score: float | None = None         # output only: fraction of numeric claims supported
    provider: str = "local"

    @property
    def redacted(self) -> bool:
        return self.action == GuardrailAction.REDACT or any(
            f.action == GuardrailAction.REDACT for f in self.findings
        )

    def summary(self) -> str:
        if not self.findings:
            return f"{self.stage}: clean"
        cats = ", ".join(sorted({f.category.value for f in self.findings}))
        return f"{self.stage}: {self.action.value} ({cats})"
