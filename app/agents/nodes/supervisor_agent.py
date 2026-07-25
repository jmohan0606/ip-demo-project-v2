"""supervisor_agent — orchestration (AGENT_SPEC §1).

Two workflows:
  A. Commentary generation (batch, offline) — sequence per advisor × transition:
     revenue_agent -> commentary_agent -> guardrails validation ->
     explainability_agent -> persist under a new version. Driven by
     app/v2/commentary/generation_workflow.py through run_generation_sequence().
  B. Read (online) — retrieval only, via stored queries. NEVER invokes
     commentary_agent; missing commentary returns an empty state telling the
     user to run generation.
"""
from __future__ import annotations

from typing import Any

from app.agents.core.base_agent import BaseAgent
from app.agents.state.agent_state import AgenticRequest, AgentWorkflowState
from app.shared.ids import timestamp_id

# Declarative routing (V1 pattern) — renderable as a topology if ever needed.
ROUTING_RULES: list[tuple[list[str], str, list[str]]] = [
    (["revenue", "change", "driver", "attribution"], "revenue_analysis", ["revenue_agent"]),
    (["commentary", "narrative", "insight"], "commentary_generation",
     ["revenue_agent", "commentary_agent", "explainability_agent"]),
    (["evidence", "why", "prove"], "explainability", ["explainability_agent"]),
]
ALWAYS: list[str] = []
INVARIANTS: list[tuple[str, str]] = [
    # commentary may only be produced with evidence assembled afterwards
    ("commentary_agent", "explainability_agent"),
]
ORDER = ["supervisor", "revenue_agent", "commentary_agent", "explainability_agent"]


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    description = "Routes requests; sequences revenue -> commentary -> guardrails -> evidence for generation; retrieval-only for reads."

    # ---- workflow A: one advisor × transition of the batch generation ------
    def run_generation_sequence(self, advisor_id: str, from_month: str, to_month: str,
                                version_id: str) -> AgentWorkflowState:
        """revenue -> commentary -> guardrails -> explainability for ONE
        transition. Guardrails run between commentary and evidence; the caller
        persists. Never mutates a prior version."""
        from app.agents.nodes.commentary_agent import CommentaryAgent
        from app.agents.nodes.explainability_agent import ExplainabilityAgent
        from app.agents.nodes.revenue_agent import RevenueAgent
        from app.guardrails.numeric_validation import validate_commentary

        state = AgentWorkflowState(
            request=AgenticRequest(question=f"commentary {advisor_id} {from_month}->{to_month}",
                                   scope_type="Advisor", scope_id=advisor_id),
            run_id=timestamp_id("v2gen"),
            route_plan=["revenue_agent", "commentary_agent", "guardrails", "explainability_agent"],
        )
        state.context.update({"advisor_id": advisor_id, "from_month": from_month,
                              "to_month": to_month, "version_id": version_id})
        import logging

        from app.agents.nodes.commentary_agent import deterministic_commentary
        from app.config.settings import get_settings

        log = logging.getLogger(__name__)

        state = RevenueAgent().run(state)
        if state.errors:
            return state

        # R9 D2 — bounded retry: a commentary that fails the guardrail is
        # REGENERATED (a fresh model call each time) up to
        # COMMENTARY_MAX_ATTEMPTS total attempts; every attempt is validated
        # and every failure logged. Evidence is assembled once after the first
        # generation (it derives from the computed drivers, not the wording)
        # and must exist BEFORE validation can pass check 3; a blocked
        # transition still keeps its evidence.
        max_attempts = max(1, int(get_settings().commentary_max_attempts))
        evidence_ids: set[str] = set()
        attempts: list[dict] = []
        validation: dict = {"passed": False, "blocked_reason": "not generated"}
        for attempt in range(1, max_attempts + 1):
            state = CommentaryAgent().run(state)
            if state.errors:
                return state
            if attempt == 1:
                state = ExplainabilityAgent().run(state)
                if state.errors:
                    return state
                evidence_ids = {e["driver_id"] for e in state.context.get("evidence", [])}
            validation = validate_commentary(
                state.context["revenue_output"], state.context["commentary"], evidence_ids)
            attempts.append({"attempt": attempt, "passed": validation["passed"],
                             "blocked_reason": validation["blocked_reason"] or ""})
            if validation["passed"]:
                break
            log.warning(
                "commentary guardrail attempt %d/%d FAILED for %s %s->%s: %s%s",
                attempt, max_attempts, advisor_id, from_month, to_month,
                validation["blocked_reason"],
                " — regenerating" if attempt < max_attempts else " — no attempts left",
            )

        # R9 D3 — never an empty panel: after the last failed attempt, publish
        # the deterministic template (computed drivers only, no model wording),
        # clearly marked as a fallback. It is validated too — the guardrail is
        # never bypassed; a bad figure is never displayed.
        if not validation["passed"]:
            fallback = deterministic_commentary(state.context["revenue_output"])
            fb_validation = validate_commentary(
                state.context["revenue_output"], fallback, evidence_ids)
            if fb_validation["passed"]:
                state.context["commentary"] = fallback
                state.context["fallback_reason"] = (
                    f"model wording failed the guardrail {len(attempts)} time(s); "
                    f"last reason: {attempts[-1]['blocked_reason']}")
                validation = fb_validation
                log.warning(
                    "commentary for %s %s->%s published as DETERMINISTIC FALLBACK "
                    "after %d failed attempt(s)",
                    advisor_id, from_month, to_month, len(attempts))
            else:
                log.error(
                    "deterministic fallback itself failed validation for %s %s->%s: %s "
                    "— transition stays BLOCKED",
                    advisor_id, from_month, to_month, fb_validation["blocked_reason"])
        state.context["validation"] = validation
        state.context["validation_attempts"] = attempts
        return state

    # ---- workflow B: read — retrieval only ---------------------------------
    def read_commentary(self, advisor_id: str, version_id: str = "") -> dict[str, Any]:
        """Stored commentary via run_query. Never generates. Missing commentary
        => empty payload with instructions, not an LLM call."""
        from app.graph.client import get_graph_client
        from app.graph.queries.common import v2_served_by_tier

        result = get_graph_client().run_query(
            "get_commentary", {"advisor_id": advisor_id, "version_id": version_id})
        rows: list[dict] = []
        resolved = version_id
        for obj in result.get("results", []):
            if "commentaries" in obj:
                rows = [r.get("attributes", {}) for r in obj["commentaries"]]
            if "resolved_version" in obj:
                resolved = obj["resolved_version"]
        return {
            "commentaries": rows,
            "resolved_version": resolved,
            "served_by_tier": v2_served_by_tier(result),
            "empty_state": None if rows else
            "No commentary generated for this advisor yet. Run generation to create a version.",
        }

    def run(self, state: AgentWorkflowState) -> AgentWorkflowState:
        # Framework entry point (workflow B): retrieval only.
        task = self.create_task("read stored commentary")
        payload = self.read_commentary(state.request.scope_id)
        state.context["commentary_read"] = payload
        state.answer = payload["empty_state"] or f"{len(payload['commentaries'])} stored commentary rows."
        state.tasks.append(self.complete_task(task, {"rows": len(payload["commentaries"])}))
        return state
