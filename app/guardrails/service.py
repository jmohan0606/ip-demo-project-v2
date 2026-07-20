from __future__ import annotations

from datetime import datetime, timezone

from app.guardrails.client import get_guardrail_client
from app.guardrails.models import GuardrailAction, GuardrailResult
from app.shared.ids import timestamp_id
from app.shared.logging import get_logger

_log = get_logger("app.guardrails")


class GuardrailService:
    """Orchestrates input/output guardrails on the AI request/response path and persists a real
    `phx_dm_guardrail_event` for every finding (the schema vertex existed but nothing wrote it at
    runtime — this closes that gap so the Audit/Observability + agent-execution-trace surfaces show
    real guardrail activity)."""

    def __init__(self) -> None:
        self.client = get_guardrail_client()

    def check_input(self, text: str, execution_id: str | None = None) -> GuardrailResult:
        result = self.client.check_input(text)
        self._record(result, execution_id)
        return result

    def check_output(self, text: str, context: str, execution_id: str | None = None) -> GuardrailResult:
        result = self.client.check_output(text, context)
        self._record(result, execution_id)
        return result

    def describe(self) -> dict:
        return self.client.describe()

    @staticmethod
    def safe_refusal(result: GuardrailResult) -> str:
        """The user-facing message when input is BLOCKED (injection/jailbreak/oversize)."""
        cats = sorted({f.category.value for f in result.findings if f.action == GuardrailAction.BLOCK})
        return (
            "⛔ This request was blocked by the input guardrails "
            f"({', '.join(cats) or 'policy'}). I can't follow instructions that attempt to override "
            "my system rules, reveal internal prompts, or bypass safety controls. Please rephrase "
            "your question about advisors, households, revenue, opportunities, or coaching."
        )

    def _record(self, result: GuardrailResult, execution_id: str | None) -> None:
        """Persist one guardrail event per finding into phx_dm_guardrail_event (best-effort)."""
        if not result.findings:
            return
        try:
            from app.graph.artifacts import upsert_edge, upsert_vertex
            from app.graph.client import get_graph_client
            graph = get_graph_client()
            now = datetime.now(timezone.utc).isoformat()
            for f in result.findings:
                event_id = timestamp_id("guard")
                upsert_vertex(graph, "phx_dm_guardrail_event", "guardrail_event_id", {
                    "guardrail_event_id": event_id,
                    "event_type": f"{result.stage}:{f.category.value}",
                    "severity": f.severity,
                    "action": f.action.value,
                    "matched_rule": f.matched_rule,
                    "redacted_content": (f.match_preview or "")[:200],
                    "created_at": now,
                })
                if execution_id:
                    upsert_edge(graph, "phx_dm_execution_has_guardrail_event",
                                "phx_dm_agent_execution", "phx_dm_guardrail_event",
                                execution_id, event_id)
        except Exception as exc:  # noqa: BLE001 — recording must never break the request
            _log.warning("guardrail event recording failed: %s", exc)
