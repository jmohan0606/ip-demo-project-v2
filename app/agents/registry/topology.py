"""Agent-system topology, enumerated from the live AgentRegistry.

V2's topology is small: supervisor routes to revenue, commentary and
explainability agents (docs/agents/AGENT_SPEC.md). Edges are derived from the
registered agents rather than a drawn diagram.
"""
from __future__ import annotations

from app.agents.registry.agent_registry import AgentRegistry


def build_topology() -> dict:
    registry = AgentRegistry()
    agents = registry.list_agents()
    nodes = [
        {
            "id": a["name"],
            "kind": "supervisor" if a["name"] == "supervisor" else "agent",
            "label": a["name"].replace("_", " "),
            "description": a["description"],
            "class_name": a["class"],
        }
        for a in agents
    ]
    edges = [
        {"source": "supervisor", "target": a["name"], "kind": "routes", "label": "routes"}
        for a in agents
        if a["name"] != "supervisor"
    ]
    return {"nodes": nodes, "edges": edges}
