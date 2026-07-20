from __future__ import annotations

from app.models.tigergraph_schema import TigerGraphSchemaInventory, TigerGraphSchemaObject


VERTEX_NAMES = [
    "phx_dm_firm", "phx_dm_division", "phx_dm_region", "phx_dm_market", "phx_dm_persona_user",
    "phx_dm_advisor", "phx_dm_household", "phx_dm_account", "phx_dm_product_category",
    "phx_dm_product_subcategory", "phx_dm_product", "phx_dm_time_period", "phx_dm_transaction",
    "phx_dm_monthly_aum", "phx_dm_monthly_ncf", "phx_dm_monthly_nnm",
    "phx_dm_monthly_product_revenue", "phx_dm_monthly_eligibility", "phx_dm_crm_activity",
    "phx_dm_agp_program", "phx_dm_goal", "phx_dm_kpi", "phx_dm_coaching_session",
    "phx_dm_manager_review", "phx_dm_prediction_result", "phx_dm_opportunity",
    "phx_dm_recommendation", "phx_dm_feedback_event", "phx_dm_outcome_event",
    "phx_dm_learning_signal", "phx_dm_context_memory", "phx_dm_conversation_turn",
    "phx_dm_reasoning_trace", "phx_dm_document", "phx_dm_document_chunk", "phx_dm_playbook",
    "phx_dm_best_practice", "phx_dm_feature_snapshot", "phx_dm_embedding",
    "phx_dm_similarity_match", "phx_dm_notification", "phx_dm_business_glossary_term",
]

QUERY_NAMES = [
    "phx_dm_validateGraphCounts",
    "phx_dm_getAdvisor360",
    "phx_dm_getScopeRevenueSummary",
    "phx_dm_getAgpAdvisorStatus",
    "phx_dm_getRecommendationExplainability",
    "phx_dm_getMemoryTimeline",
    "phx_dm_getSimilarHouseholds",
    "phx_dm_getDataIngestionSummary",
]


def build_schema_inventory() -> TigerGraphSchemaInventory:
    return TigerGraphSchemaInventory(
        vertices=[
            TigerGraphSchemaObject(name=name, object_type="vertex")
            for name in VERTEX_NAMES
        ],
        edges=[],
        queries=[
            TigerGraphSchemaObject(name=name, object_type="query")
            for name in QUERY_NAMES
        ],
    )
