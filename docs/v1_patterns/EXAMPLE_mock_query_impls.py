from __future__ import annotations

from app.graph.client import mock_query
from app.graph.foundation_store import FoundationGraphStore
from app.graph.queries.common import (
    ADVISOR,
    advisor_transactions,
    date10,
    in_window,
    resolve_scope_advisor_ids,
    vset,
)


@mock_query("get_revenue_summary_by_scope")
def get_revenue_summary_by_scope(store: FoundationGraphStore, params: dict) -> list[dict]:
    scope_type = (params.get("scope_type") or "").upper()
    scope_id = str(params.get("scope_id") or "")
    period_type = (params.get("period_type") or "LTM").upper()
    start_date, end_date = params.get("start_date"), params.get("end_date")

    advisor_ids = resolve_scope_advisor_ids(store, scope_type, scope_id)
    household_ids: set[str] = set()
    account_ids: set[str] = set()
    for advisor_id in advisor_ids:
        for household_id in store.out_ids("phx_dm_advisor_serves_household", advisor_id):
            household_ids.add(household_id)
            account_ids.update(store.out_ids("phx_dm_household_owns_account", household_id))

    revenue = 0.0
    transaction_count = 0
    for _, attrs in advisor_transactions(store, advisor_ids, start_date, end_date):
        revenue += float(attrs.get("revenue_amount") or 0)
        transaction_count += 1

    aum = ncf = nnm = 0.0
    for advisor_id in advisor_ids:
        for row_id in store.in_ids("phx_dm_aum_for_advisor", advisor_id):
            attrs = store.vertex("phx_dm_monthly_aum", row_id) or {}
            if date10(attrs.get("month_end")) == date10(end_date):
                aum += float(attrs.get("aum_amount") or 0)
        for row_id in store.in_ids("phx_dm_ncf_for_advisor", advisor_id):
            attrs = store.vertex("phx_dm_monthly_ncf", row_id) or {}
            if in_window(attrs.get("month_end"), start_date, end_date):
                ncf += float(attrs.get("ncf_amount") or 0)
        for row_id in store.in_ids("phx_dm_nnm_for_advisor", advisor_id):
            attrs = store.vertex("phx_dm_monthly_nnm", row_id) or {}
            if in_window(attrs.get("month_end"), start_date, end_date):
                nnm += float(attrs.get("nnm_amount") or 0)

    return [
        {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "period_type": period_type,
            "start_date": start_date,
            "end_date": end_date,
            "total_revenue": round(revenue, 2),
            "ending_aum": round(aum, 2),
            "total_ncf": round(ncf, 2),
            "total_nnm": round(nnm, 2),
            "transaction_count": transaction_count,
            "advisor_count": len(advisor_ids),
            "household_count": len(household_ids),
            "account_count": len(account_ids),
        }
    ]


@mock_query("get_revenue_trend_by_scope")
def get_revenue_trend_by_scope(store: FoundationGraphStore, params: dict) -> list[dict]:
    scope_type = (params.get("scope_type") or "").upper()
    scope_id = str(params.get("scope_id") or "")
    period_grain = (params.get("period_grain") or "ALL").upper()
    start_date, end_date = params.get("start_date"), params.get("end_date")

    advisor_ids = resolve_scope_advisor_ids(store, scope_type, scope_id)
    trend: dict[tuple[str, str], dict] = {}
    for tx_id, attrs in advisor_transactions(store, advisor_ids, start_date, end_date):
        for period_id in store.out_ids("phx_dm_transaction_in_period", tx_id):
            period = store.vertex("phx_dm_time_period", period_id) or {}
            if period_grain != "ALL" and period.get("period_type") != period_grain:
                continue
            bucket = trend.setdefault(
                (period_id, period.get("label")),
                {"period_id": period_id, "label": period.get("label"), "revenue": 0.0, "transaction_count": 0},
            )
            bucket["revenue"] += float(attrs.get("revenue_amount") or 0)
            bucket["transaction_count"] += 1

    revenue_trend = sorted(trend.values(), key=lambda r: str(r["period_id"]))
    for row in revenue_trend:
        row["revenue"] = round(row["revenue"], 2)
    return [
        {"scope_type": scope_type, "scope_id": scope_id, "period_grain": period_grain, "revenue_trend": revenue_trend}
    ]


@mock_query("get_product_mix_by_scope")
def get_product_mix_by_scope(store: FoundationGraphStore, params: dict) -> list[dict]:
    scope_type = (params.get("scope_type") or "").upper()
    scope_id = str(params.get("scope_id") or "")
    start_date, end_date = params.get("start_date"), params.get("end_date")

    advisor_ids = resolve_scope_advisor_ids(store, scope_type, scope_id)
    total_revenue = 0.0
    mix: dict[str, dict] = {}
    product_ids: set[str] = set()
    for tx_id, attrs in advisor_transactions(store, advisor_ids, start_date, end_date):
        amount = float(attrs.get("revenue_amount") or 0)
        total_revenue += amount
        for product_id in store.out_ids("phx_dm_transaction_for_product", tx_id):
            product = store.vertex("phx_dm_product", product_id) or {}
            product_ids.add(product_id)
            bucket = mix.setdefault(
                product_id,
                {"product_id": product_id, "product_name": product.get("product_name"), "revenue": 0.0, "transaction_count": 0},
            )
            bucket["revenue"] += amount
            bucket["transaction_count"] += 1

    subcategory_ids: set[str] = set()
    for product_id in product_ids:
        subcategory_ids.update(store.out_ids("phx_dm_product_in_subcategory", product_id))
    category_ids: set[str] = set()
    for subcategory_id in subcategory_ids:
        category_ids.update(store.out_ids("phx_dm_subcategory_in_category", subcategory_id))

    product_mix = sorted(mix.values(), key=lambda r: -r["revenue"])
    for row in product_mix:
        row["revenue"] = round(row["revenue"], 2)
    return [
        {
            "total_revenue": round(total_revenue, 2),
            "product_mix": product_mix,
            "products": vset(store, "phx_dm_product", product_ids),
            "subcategories": vset(store, "phx_dm_product_subcategory", subcategory_ids),
            "categories": vset(store, "phx_dm_product_category", category_ids),
        }
    ]


def _score_advisors(store: FoundationGraphStore, advisor_ids: list[str], start_date, end_date) -> list[dict]:
    scored = []
    for advisor_id in advisor_ids:
        revenue = 0.0
        count = 0
        for _, attrs in advisor_transactions(store, [advisor_id], start_date, end_date):
            revenue += float(attrs.get("revenue_amount") or 0)
            count += 1
        advisor = store.vertex(ADVISOR, advisor_id) or {}
        scored.append(
            {
                "advisor_id": advisor_id,
                "advisor_name": advisor.get("advisor_name"),
                "revenue": round(revenue, 2),
                "transaction_count": count,
            }
        )
    return scored


@mock_query("get_top_bottom_advisors")
def get_top_bottom_advisors(store: FoundationGraphStore, params: dict) -> list[dict]:
    scope_type = (params.get("scope_type") or "").upper()
    scope_id = str(params.get("scope_id") or "")
    direction = (params.get("direction") or "TOP").upper()
    result_limit = int(params.get("result_limit") or 10)
    start_date, end_date = params.get("start_date"), params.get("end_date")

    scored = _score_advisors(store, resolve_scope_advisor_ids(store, scope_type, scope_id), start_date, end_date)
    ranked = sorted(scored, key=lambda r: -r["revenue"])
    return [
        {
            "direction": direction,
            "top_advisors": ranked[:result_limit] if direction == "TOP" else [],
            "bottom_advisors": list(reversed(ranked))[:result_limit] if direction == "BOTTOM" else [],
        }
    ]


@mock_query("get_peer_benchmark")
def get_peer_benchmark(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    peer_method = (params.get("peer_method") or "MARKET").upper()
    start_date, end_date = params.get("start_date"), params.get("end_date")

    peer_ids: set[str] = set()
    similarity_match_ids: list[str] = []
    if peer_method in {"MARKET", "HYBRID"}:
        for market_id in store.out_ids("phx_dm_advisor_in_market", advisor_id):
            peer_ids.update(store.in_ids("phx_dm_advisor_in_market", market_id))
    if peer_method in {"SIMILARITY", "HYBRID"}:
        similarity_match_ids = store.out_ids("phx_dm_advisor_has_similarity_match", advisor_id)
        for match_id in similarity_match_ids:
            peer_ids.update(store.out_ids("phx_dm_similarity_match_targets_advisor", match_id))
    peer_ids.discard(advisor_id)

    peers = _score_advisors(store, sorted(peer_ids), start_date, end_date)
    advisor_revenue = _score_advisors(store, [advisor_id], start_date, end_date)
    return [
        {
            "peer_method": peer_method,
            "advisor_revenue": advisor_revenue[0]["revenue"] if advisor_revenue else 0.0,
            "peer_revenue_sum": round(sum(p["revenue"] for p in peers), 2),
            "peer_count": len(peers),
            "peers": peers,
            "similar_matches": vset(store, "phx_dm_similarity_match", similarity_match_ids),
        }
    ]


@mock_query("get_scope_transactions")
def get_scope_transactions(store: FoundationGraphStore, params: dict) -> list[dict]:
    """Mirror of GQ-051: raw transaction rows for a scope, each carrying its
    advisor/product/household context. Same aliased attribute keys as the GSQL
    PRINT so tier 4 and tier 2 are indistinguishable to readers."""
    scope_type = (params.get("scope_type") or "").upper()
    scope_id = str(params.get("scope_id") or "")
    start_date, end_date = params.get("start_date"), params.get("end_date")

    rows: list[dict] = []
    for advisor_id in resolve_scope_advisor_ids(store, scope_type, scope_id):
        advisor = store.vertex(ADVISOR, advisor_id) or {}
        for tx_id in store.in_ids("phx_dm_transaction_for_advisor", advisor_id):
            attrs = store.vertex("phx_dm_revenue_transaction", tx_id)
            if attrs is None:
                continue
            if start_date is not None and not in_window(attrs.get("transaction_date"), start_date, end_date):
                continue
            product_ids = store.out_ids("phx_dm_transaction_for_product", tx_id)
            household_ids = store.out_ids("phx_dm_transaction_for_household", tx_id)
            product = store.vertex("phx_dm_product", product_ids[0]) if product_ids else None
            household = store.vertex("phx_dm_household", household_ids[0]) if household_ids else None
            rows.append(
                {
                    "v_id": str(tx_id),
                    "v_type": "phx_dm_revenue_transaction",
                    "attributes": {
                        "advisor_id": str(advisor_id),
                        "advisor_name": str(advisor.get("advisor_name") or ""),
                        "transaction_date": attrs.get("transaction_date"),
                        "revenue_amount": attrs.get("revenue_amount"),
                        "transaction_type": attrs.get("transaction_type"),
                        "product_id": product_ids[0] if product_ids else "",
                        "product_name": str((product or {}).get("product_name") or ""),
                        "household_id": household_ids[0] if household_ids else "",
                        "household_name": str((household or {}).get("household_name") or ""),
                    },
                }
            )
    return [{"transactions": rows}]


@mock_query("get_product_category_map")
def get_product_category_map(store: FoundationGraphStore, params: dict) -> list[dict]:
    """Mirror of GQ-052: product -> subcategory -> category mapping. Like the GSQL
    version, products with no subcategory edge are absent (readers default them
    to Unclassified)."""
    categories = store.all_vertices("phx_dm_product_category")
    subcategories = store.all_vertices("phx_dm_product_subcategory")
    rows: list[dict] = []
    for product_id, product in store.all_vertices("phx_dm_product").items():
        sub_ids = store.out_ids("phx_dm_product_in_subcategory", product_id)
        if not sub_ids:
            continue
        sub_id = sub_ids[0]
        cat_ids = store.out_ids("phx_dm_subcategory_in_category", sub_id)
        cat_id = cat_ids[0] if cat_ids else ""
        rows.append(
            {
                "v_id": str(product_id),
                "v_type": "phx_dm_product",
                "attributes": {
                    "product_name": str(product.get("product_name") or ""),
                    "subcategory_id": str(sub_id),
                    "subcategory_name": str((subcategories.get(sub_id) or {}).get("subcategory_name") or ""),
                    "category_id": str(cat_id),
                    "category_name": str((categories.get(cat_id) or {}).get("category_name") or ""),
                },
            }
        )
    return [{"products": rows}]
