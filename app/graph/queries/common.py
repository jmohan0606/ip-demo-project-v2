from __future__ import annotations

import logging
from typing import Any, Iterable

from app.graph.foundation_store import FoundationGraphStore

logger = logging.getLogger(__name__)

# Vertex type constants (schema prefix phx_dm_v2_)
ADVISOR = "phx_dm_v2_advisor"
MONTH = "phx_dm_v2_month"
REVENUE_CLASS = "phx_dm_v2_revenue_class"
PRODUCT_LINE = "phx_dm_v2_product_line"
PRODUCT_GROUP = "phx_dm_v2_product_group"
PRODUCT = "phx_dm_v2_product"
ACCOUNT = "phx_dm_v2_account"
DRIVER_CAUSE = "phx_dm_v2_driver_cause"
REASON_CODE = "phx_dm_v2_reason_code"
REVENUE_TRANSACTION = "phx_dm_v2_revenue_transaction"
MONTHLY_PRODUCT_REVENUE = "phx_dm_v2_monthly_product_revenue"
ACCOUNT_MONTH_BALANCE = "phx_dm_v2_account_month_balance"
REVENUE_CHANGE = "phx_dm_v2_revenue_change"
REVENUE_DRIVER = "phx_dm_v2_revenue_driver"
COMMENTARY_VERSION = "phx_dm_v2_commentary_version"
COMMENTARY = "phx_dm_v2_commentary"
COMMENTARY_EVALUATION = "phx_dm_v2_commentary_evaluation"
EVIDENCE = "phx_dm_v2_evidence"

V2_VERTEX_TYPES = [
    ADVISOR, MONTH, REVENUE_CLASS, PRODUCT_LINE, PRODUCT_GROUP, PRODUCT,
    ACCOUNT, DRIVER_CAUSE, REASON_CODE, REVENUE_TRANSACTION, MONTHLY_PRODUCT_REVENUE,
    ACCOUNT_MONTH_BALANCE, REVENUE_CHANGE, REVENUE_DRIVER, COMMENTARY_VERSION,
    COMMENTARY, COMMENTARY_EVALUATION, EVIDENCE,
]


def vertex_out(store: FoundationGraphStore, vertex_type: str, vertex_id: str) -> dict | None:
    """RESTPP-style vertex serialization: {"v_id", "v_type", "attributes"}."""
    attrs = store.vertex(vertex_type, vertex_id)
    if attrs is None:
        return None
    return {"v_id": str(vertex_id), "v_type": vertex_type, "attributes": attrs}


def vset(store: FoundationGraphStore, vertex_type: str, ids: Iterable[str]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for vid in ids:
        vid = str(vid)
        if vid in seen:
            continue
        seen.add(vid)
        v = vertex_out(store, vertex_type, vid)
        if v is not None:
            out.append(v)
    return out


def vrows(store: FoundationGraphStore, vertex_type: str, predicate=None) -> list[dict]:
    """All vertices of a type as RESTPP rows, optionally filtered on attributes."""
    out = []
    for vid, attrs in store.all_vertices(vertex_type).items():
        if predicate is None or predicate(attrs):
            out.append({"v_id": str(vid), "v_type": vertex_type, "attributes": attrs})
    return out


def run_catalog_query(graph: Any, query_name: str, params: dict) -> list[dict] | None:
    """Dispatch a catalogued GQ-### query through the active GraphClient.

    Returns the `results` list on success, or None when the query raised or came
    back as an error envelope — callers treat None as "use the local-store
    fallback" and that fallback is always logged (never silent). Also logs when
    GRAPH_CLIENT_MODE=real but the local tier served the request (ABSOLUTE RULE 4).
    """
    try:
        result = graph.run_query(query_name, params)
    except Exception as exc:  # noqa: BLE001 — any tier failure funnels to the logged fallback
        logger.warning(
            "run_query(%s) raised %s: %s — falling back to local store traversal",
            query_name, type(exc).__name__, exc,
        )
        return None
    if not isinstance(result, dict) or result.get("error"):
        logger.warning(
            "run_query(%s) returned an error envelope (%s) — falling back to local store traversal",
            query_name,
            (result or {}).get("message") if isinstance(result, dict) else type(result).__name__,
        )
        return None
    from app.config.settings import get_settings

    mode = (get_settings().graph_client_mode or "local").lower()
    if v2_served_by_tier(result) == 2 and mode == "real":
        logger.warning(
            "run_query(%s) served by the LOCAL store (tier 2) while GRAPH_CLIENT_MODE=real — "
            "TigerGraph is not serving; the env-health screen must show RED",
            query_name,
        )
    return result.get("results", [])


def v2_served_by_tier(result: dict) -> int:
    """Map the internal tier chain (1 mcp / 2 pytg / 3 restpp / 4 local store) onto
    the V2 two-tier contract: 1 = TigerGraph, 2 = local store."""
    internal = result.get("served_by_tier")
    if internal is None:
        internal = 4 if result.get("mode") == "mock" else 1
    return 1 if internal in (1, 2, 3) else 2


def graph_fallback_store(graph: Any) -> FoundationGraphStore:
    """The FoundationGraphStore used for the logged local fallback path."""
    store = getattr(graph, "store", None)
    if store is not None:
        return store
    from app.graph.foundation_store import get_foundation_store

    return get_foundation_store()


def group_accum(rows: Iterable[dict], keys: list[str], sums: dict[str, str]) -> list[dict]:
    """GroupByAccum equivalent: group `rows` by `keys`, summing the mappings in
    `sums` (output_field -> input_field, input may be the literal __count__)."""
    grouped: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        bucket = grouped.setdefault(key, {**{k: row.get(k) for k in keys}, **{f: 0 for f in sums}})
        for out_field, in_field in sums.items():
            value = 1 if in_field == "__count__" else float(row.get(in_field) or 0)
            bucket[out_field] += value
    return list(grouped.values())
