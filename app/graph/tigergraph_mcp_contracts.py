from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TigerGraphQueryContract:
    logical_name: str
    mcp_tool_name: str
    rest_query_name: str
    required_params: list[str] = field(default_factory=list)
    description: str = ""


QUERY_CONTRACTS: dict[str, TigerGraphQueryContract] = {
    "advisor_context": TigerGraphQueryContract(
        logical_name="advisor_context",
        mcp_tool_name="get_advisor_context",
        rest_query_name="get_advisor_context",
        required_params=["advisor_id"],
        description="Advisor → household → account → product → opportunity context.",
    ),
    "revenue_summary": TigerGraphQueryContract(
        logical_name="revenue_summary",
        mcp_tool_name="get_revenue_summary",
        rest_query_name="get_revenue_summary",
        required_params=["scope_type", "scope_id", "period"],
        description="Revenue, AUM, NNM, NCF and product mix rollup by persona/scope.",
    ),
    "advisor_360": TigerGraphQueryContract(
        logical_name="advisor_360",
        mcp_tool_name="get_advisor_360",
        rest_query_name="get_advisor_360",
        required_params=["advisor_id", "period"],
        description="Advisor profile, households, accounts, CRM and recommendations.",
    ),
    "recommendation_context": TigerGraphQueryContract(
        logical_name="recommendation_context",
        mcp_tool_name="get_recommendation_context",
        rest_query_name="get_recommendation_context",
        required_params=["scope_id"],
        description="Graph context used by recommendation generation.",
    ),
    "memory_timeline": TigerGraphQueryContract(
        logical_name="memory_timeline",
        mcp_tool_name="get_memory_timeline",
        rest_query_name="get_memory_timeline",
        required_params=["scope_id"],
        description="Temporal memory and agent trace lineage.",
    ),
    "graph_explorer": TigerGraphQueryContract(
        logical_name="graph_explorer",
        mcp_tool_name="get_graph_explorer",
        rest_query_name="get_graph_explorer",
        required_params=["scope_id"],
        description="Nodes and edges for UI graph exploration.",
    ),
}


def validate_params(contract: TigerGraphQueryContract, params: dict[str, Any]) -> list[str]:
    return [name for name in contract.required_params if name not in params or params.get(name) in {None, ""}]
