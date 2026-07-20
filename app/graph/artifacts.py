from __future__ import annotations

from app.graph.client import GraphClient


def upsert_vertex(graph: GraphClient, target: str, id_column: str, record: dict) -> None:
    """Persist an AI artifact vertex through the GraphClient adapter."""
    graph.upsert(
        {
            "kind": "vertex",
            "target": target,
            "id_column": id_column,
            "file": "runtime",
            "columns": {key: key for key in record},
        },
        [record],
    )


def upsert_edge(graph: GraphClient, edge: str, from_type: str, to_type: str, from_id: str, to_id: str) -> None:
    graph.upsert(
        {
            "kind": "edge",
            "target": edge,
            "from_type": from_type,
            "to_type": to_type,
            "from_column": "from_id",
            "to_column": "to_id",
            "file": "runtime",
            "columns": {},
        },
        [{"from_id": from_id, "to_id": to_id}],
    )


def write_reasoning_trace(
    graph: GraphClient,
    reasoning_id: str,
    artifact_type: str,
    artifact_id: str,
    steps: list[str],
    evidence: dict,
    feature_snapshot_id: str | None = None,
    created_at: str | None = None,
) -> None:
    """Every AI output persists a reasoning trace: which steps and which
    evidence produced it (Non-Negotiable FOUND-004)."""
    import json

    upsert_vertex(
        graph,
        "phx_dm_reasoning_trace",
        "reasoning_id",
        {
            "reasoning_id": reasoning_id,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "reasoning_steps_json": json.dumps(steps),
            "evidence_json": json.dumps(evidence),
            "created_at": created_at,
        },
    )
    artifact_edge = {
        "PREDICTION": ("phx_dm_reasoning_for_prediction", "phx_dm_prediction_result"),
        "OPPORTUNITY": ("phx_dm_reasoning_for_opportunity", "phx_dm_opportunity"),
        "RECOMMENDATION": ("phx_dm_reasoning_for_recommendation", "phx_dm_recommendation"),
        # ADVISOR: chat/agentic reasoning anchored directly to an advisor so prior traces
        # are retrievable by traversal (reasoning-trace reuse / experience memory).
        "ADVISOR": ("phx_dm_reasoning_for_advisor", "phx_dm_advisor"),
    }.get(artifact_type)
    if artifact_edge:
        upsert_edge(graph, artifact_edge[0], "phx_dm_reasoning_trace", artifact_edge[1], reasoning_id, artifact_id)
    if feature_snapshot_id:
        upsert_edge(
            graph,
            "phx_dm_reasoning_uses_feature_snapshot",
            "phx_dm_reasoning_trace",
            "phx_dm_feature_snapshot",
            reasoning_id,
            feature_snapshot_id,
        )
