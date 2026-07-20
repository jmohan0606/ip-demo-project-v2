"""Real agent-system topology for the orchestration page's live graph.

Grounded in the actual implementation, not a drawn diagram:
- agent nodes are enumerated from AgentRegistry (the same instances that execute);
- supervisor→agent routing edges come from SupervisorAgent.ROUTING_RULES / ALWAYS /
  INVARIANTS — the exact structures run() routes with;
- agent→tool/data-source edges mirror each agent node's real imports and calls
  (see the per-agent `uses` lists below; each entry names the concrete
  service/adapter the agent module actually invokes).
"""
from __future__ import annotations

from app.agents.nodes.supervisor_agent import SupervisorAgent
from app.agents.registry.agent_registry import AgentRegistry

# What each agent ACTUALLY calls (module → service/adapter → data source), verified
# against the agent node sources. Format: (tool_id, tool_label, data_source_id | None).
AGENT_DEPENDENCIES: dict[str, list[tuple[str, str, str | None]]] = {
    'context_retrieval_agent': [
        ('tool_context_service', 'ContextService (temporal memory assembly)', 'ds_memory'),
    ],
    'tigergraph_graph_agent': [
        ('tool_graph_client', 'Tiered GraphClient (MCP → pyTigerGraph → RESTPP → mock)', 'ds_tigergraph'),
    ],
    'rag_knowledge_agent': [
        ('tool_rag_service', 'RagGenerationService (retrieve + grounded generation)', 'ds_chroma'),
        ('tool_llm_client', 'LLMClient adapter (mock | claude | azure)', None),
    ],
    'revenue_agent': [
        ('tool_graph_client', 'Tiered GraphClient (MCP → pyTigerGraph → RESTPP → mock)', 'ds_tigergraph'),
    ],
    'prediction_agent': [
        ('tool_prediction_service', 'PredictionService (model tier: XGBoost / scorecard)', 'ds_feature_store'),
    ],
    'opportunity_agent': [
        ('tool_opportunity_service', 'OpportunityDetectionService (severity-composed detection)', 'ds_feature_store'),
    ],
    'recommendation_agent': [
        ('tool_recommendation_service', 'RecommendationService (learning-weighted ranking)', 'ds_feedback'),
    ],
    'compliance_agent': [
        ('tool_compliance_rules', 'Rule engine COMP-001..004 (in-process)', None),
    ],
    'coaching_agent': [
        ('tool_feature_engineering', 'FeatureEngineeringService (advisor snapshot)', 'ds_feature_store'),
        ('tool_llm_client', 'LLMClient adapter (mock | claude | azure)', None),
    ],
    'feedback_learning_agent': [
        ('tool_feedback_service', 'FeedbackLearningService (learning signals)', 'ds_feedback'),
    ],
    'explainability_agent': [],  # consolidates in-state evidence, no external calls
    'ai_assistant_agent': [
        ('tool_llm_client', 'LLMClient adapter (mock | claude | azure)', None),
    ],
}

DATA_SOURCES: dict[str, str] = {
    'ds_tigergraph': 'TigerGraph (foundation graph, 60v/132e)',
    'ds_memory': 'Context memory store (conversation / reasoning traces)',
    'ds_chroma': 'Chroma vector store (document chunks)',
    'ds_feature_store': 'Feature store (SQLite snapshots + lineage)',
    'ds_feedback': 'Feedback & learning-signal store',
}


def build_topology() -> dict:
    registry = AgentRegistry()
    agents = {a['name']: a for a in registry.list_agents()}

    rules_by_agent: dict[str, list[dict]] = {}
    for keywords, capability, targets in SupervisorAgent.ROUTING_RULES:
        for target in targets:
            rules_by_agent.setdefault(target, []).append(
                {'keywords': keywords, 'capability': capability})

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_tools: set[str] = set()
    used_sources: set[str] = set()

    for name, meta in agents.items():
        if name == 'supervisor':
            invoked = 'Runs first on every request; plans the route from question keywords / requested capabilities.'
        elif name in SupervisorAgent.ALWAYS:
            invoked = 'On EVERY route (supervisor always includes it).'
        else:
            conds = [f"keywords: {', '.join(r['keywords'])} (capability '{r['capability']}')"
                     for r in rules_by_agent.get(name, [])]
            for trigger, required in SupervisorAgent.INVARIANTS:
                if required == name:
                    conds.append(f'invariant: always follows {trigger}')
            invoked = 'When ' + ('; or '.join(conds) if conds else 'explicitly requested') + '.'
        nodes.append({'id': name, 'kind': 'supervisor' if name == 'supervisor' else 'agent',
                      'label': name.replace('_', ' '), 'description': meta['description'],
                      'class_name': meta['class'], 'invoked_when': invoked,
                      'order': SupervisorAgent.ORDER.index(name) if name in SupervisorAgent.ORDER else -1})

    # supervisor → each routable agent
    for name in agents:
        if name != 'supervisor':
            always = name in SupervisorAgent.ALWAYS
            edges.append({'source': 'supervisor', 'target': name, 'kind': 'routes',
                          'label': 'always' if always else 'conditional'})

    # agent → tool → data source
    for agent_name, deps in AGENT_DEPENDENCIES.items():
        for tool_id, tool_label, ds in deps:
            if tool_id not in seen_tools:
                seen_tools.add(tool_id)
                nodes.append({'id': tool_id, 'kind': 'tool', 'label': tool_label.split(' (')[0],
                              'description': tool_label, 'invoked_when': '', 'order': -1})
            edges.append({'source': agent_name, 'target': tool_id, 'kind': 'uses', 'label': 'calls'})
            if ds:
                used_sources.add(ds)
                edge = {'source': tool_id, 'target': ds, 'kind': 'reads', 'label': 'reads'}
                if edge not in edges:
                    edges.append(edge)

    for ds_id in sorted(used_sources):
        nodes.append({'id': ds_id, 'kind': 'datasource', 'label': DATA_SOURCES[ds_id].split(' (')[0],
                      'description': DATA_SOURCES[ds_id], 'invoked_when': '', 'order': -1})

    return {'nodes': nodes, 'edges': edges,
            'execution_order': SupervisorAgent.ORDER,
            'always_on': SupervisorAgent.ALWAYS,
            'invariants': [{'trigger': t, 'required': r} for t, r in SupervisorAgent.INVARIANTS]}
