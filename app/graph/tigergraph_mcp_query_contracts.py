from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InstalledQueryContract:
    logical_name: str
    installed_query_name: str
    required_params: list[str] = field(default_factory=list)
    description: str = ""


INSTALLED_QUERY_CONTRACTS: dict[str, InstalledQueryContract] = {
    "advisor_context": InstalledQueryContract(
        logical_name="advisor_context",
        installed_query_name="phx_dm_get_advisor_context",
        required_params=["advisor_id"],
        description="Advisor to household/account/product/opportunity context.",
    ),
    "revenue_summary": InstalledQueryContract(
        logical_name="revenue_summary",
        installed_query_name="phx_dm_get_revenue_summary",
        required_params=["scope_type", "scope_id", "period"],
        description="Revenue and AUM rollup by scope.",
    ),
    "advisor_360": InstalledQueryContract(
        logical_name="advisor_360",
        installed_query_name="phx_dm_get_advisor_360",
        required_params=["advisor_id", "period"],
        description="Advisor 360 graph context.",
    ),
    "recommendation_context": InstalledQueryContract(
        logical_name="recommendation_context",
        installed_query_name="phx_dm_get_recommendation_context",
        required_params=["scope_id"],
        description="Recommendation generation graph context.",
    ),
    "memory_timeline": InstalledQueryContract(
        logical_name="memory_timeline",
        installed_query_name="phx_dm_get_memory_timeline",
        required_params=["scope_id"],
        description="Memory timeline graph context.",
    ),
    "graph_explorer": InstalledQueryContract(
        logical_name="graph_explorer",
        installed_query_name="phx_dm_get_graph_explorer",
        required_params=["scope_id"],
        description="Graph explorer subgraph.",
    ),
}


def validate_params(contract: InstalledQueryContract, params: dict[str, Any]) -> list[str]:
    return [name for name in contract.required_params if params.get(name) in {None, ""}]
