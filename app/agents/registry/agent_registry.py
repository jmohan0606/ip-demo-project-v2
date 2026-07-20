"""Registry of V2 agent nodes.

V1's thirteen agent nodes were removed with the prune. V2's four agents
(supervisor, revenue, commentary, explainability — see docs/agents/AGENT_SPEC.md)
register here as they are authored in Phase 5.
"""
from __future__ import annotations


def _build_agents() -> list:
    agents: list = []
    try:
        from app.agents.nodes.supervisor_agent import SupervisorAgent
        from app.agents.nodes.revenue_agent import RevenueAgent
        from app.agents.nodes.commentary_agent import CommentaryAgent
        from app.agents.nodes.explainability_agent import ExplainabilityAgent

        agents = [SupervisorAgent(), RevenueAgent(), CommentaryAgent(), ExplainabilityAgent()]
    except ImportError:
        # Phase-5 nodes not authored yet — registry stays empty so the app still boots.
        agents = []
    return agents


class AgentRegistry:
    def __init__(self):
        self._agents = {a.name: a for a in _build_agents()}

    def get(self, name):
        return self._agents[name]

    def list_agents(self):
        return [
            {"name": a.name, "description": a.description, "class": a.__class__.__name__}
            for a in self._agents.values()
        ]
