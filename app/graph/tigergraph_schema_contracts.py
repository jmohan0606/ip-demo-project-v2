from __future__ import annotations

GRAPH_NAME = "iperform_insights_coaching_demo"
VERTEX_PREFIX = "phx_dm_"
EDGE_PREFIX = "phx_dm_"
QUERY_PREFIX = "phx_dm_"

REQUIRED_VERTICES = [
    "phx_dm_firm",
    "phx_dm_division",
    "phx_dm_region",
    "phx_dm_market",
    "phx_dm_advisor",
    "phx_dm_household",
    "phx_dm_account",
    "phx_dm_product",
    "phx_dm_revenue_transaction",
    "phx_dm_opportunity",
    "phx_dm_recommendation",
    "phx_dm_feedback",
    "phx_dm_memory",
    "phx_dm_context_packet",
    "phx_dm_agent_execution",
    "phx_dm_tool_call",
    "phx_dm_document",
    "phx_dm_document_chunk",
    "phx_dm_feature_vector",
    "phx_dm_prediction",
    "phx_dm_scenario",
    "phx_dm_compliance_rule",
    "phx_dm_compliance_check"
]

REQUIRED_EDGES = [
    "phx_dm_has_division",
    "phx_dm_has_region",
    "phx_dm_has_market",
    "phx_dm_has_advisor",
    "phx_dm_serves_household",
    "phx_dm_owns_account",
    "phx_dm_holds_product",
    "phx_dm_generated_revenue",
    "phx_dm_has_opportunity",
    "phx_dm_generates_recommendation",
    "phx_dm_has_feedback",
    "phx_dm_has_memory",
    "phx_dm_has_context_packet",
    "phx_dm_executed_tool",
    "phx_dm_has_chunk",
    "phx_dm_uses_document",
    "phx_dm_has_feature_vector",
    "phx_dm_generated_prediction",
    "phx_dm_has_scenario",
    "phx_dm_checked_by_rule"
]

REQUIRED_QUERIES = [
    "phx_dm_get_advisor_context",
    "phx_dm_get_revenue_summary",
    "phx_dm_get_advisor_360",
    "phx_dm_get_recommendation_context",
    "phx_dm_get_memory_timeline",
    "phx_dm_get_graph_explorer"
]
