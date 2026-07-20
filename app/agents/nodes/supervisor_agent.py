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
        state = RevenueAgent().run(state)
        if state.errors:
            return state
        state = CommentaryAgent().run(state)
        if state.errors:
            return state
        # Evidence must exist BEFORE validation can pass check 3, so assemble it
        # first, then validate; a blocked transition still keeps its evidence.
        state = ExplainabilityAgent().run(state)
        if state.errors:
            return state
        evidence_ids = {e["driver_id"] for e in state.context.get("evidence", [])}
        state.context["validation"] = validate_commentary(
            state.context["revenue_output"], state.context["commentary"], evidence_ids)
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
