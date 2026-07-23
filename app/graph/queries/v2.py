"""Local-tier (tier 2) implementations of GQ-001..GQ-019.

Each function mirrors its GSQL counterpart's traversal semantics and returns the
IDENTICAL RESTPP result shape (one dict per PRINT statement; vertex rows as
{"v_id", "v_type", "attributes"}; vertex accumulators inside attributes under
their "@name"), so verifying a reader against this tier genuinely proves what
tier 1 will return.
"""
from __future__ import annotations

import json
from typing import Any

from app.graph.client import mock_query
from app.graph.foundation_store import FoundationGraphStore
from app.graph.queries.common import (
    ACCOUNT_MONTH_BALANCE,
    ANOMALY,
    ANOMALY_SCAN,
    ADVISOR,
    COMMENTARY,
    COMMENTARY_EVALUATION,
    COMMENTARY_VERSION,
    DRIVER_CAUSE,
    EVIDENCE,
    MONTH,
    MONTHLY_PRODUCT_REVENUE,
    PRODUCT,
    PRODUCT_GROUP,
    PRODUCT_LINE,
    REASON_CODE,
    REVENUE_CHANGE,
    REVENUE_CLASS,
    REVENUE_DRIVER,
    REVENUE_TRANSACTION,
    V2_VERTEX_TYPES,
    vrows,
)


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _attr(row: dict, key: str) -> Any:
    return row.get("attributes", {}).get(key)


# ---------------------------------------------------------------- reference

@mock_query("get_advisors")
def get_advisors(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = vrows(store, ADVISOR)
    rows.sort(key=lambda r: str(_attr(r, "advisor_sid") or r["v_id"]))
    return [{"advisors": rows}]


@mock_query("get_months")
def get_months(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = vrows(store, MONTH)
    rows.sort(key=lambda r: str(_attr(r, "month_id") or r["v_id"]))
    return [{"months": rows}]


@mock_query("get_product_hierarchy")
def get_product_hierarchy(store: FoundationGraphStore, params: dict) -> list[dict]:
    def with_parent(vertex_type: str, edge_name: str) -> list[dict]:
        out = []
        for vid, attrs in store.all_vertices(vertex_type).items():
            parents = store.out_ids(edge_name, vid)
            out.append({
                "v_id": str(vid), "v_type": vertex_type,
                "attributes": {**attrs, "@parent_id": parents[0] if parents else ""},
            })
        return out

    classes = vrows(store, REVENUE_CLASS)
    classes.sort(key=lambda r: _int(_attr(r, "display_order")))
    lines = with_parent(PRODUCT_LINE, "phx_dm_v2_line_in_class")
    lines.sort(key=lambda r: _int(_attr(r, "display_order")))
    groups = with_parent(PRODUCT_GROUP, "phx_dm_v2_group_in_line")
    groups.sort(key=lambda r: _int(_attr(r, "display_order")))
    products = with_parent(PRODUCT, "phx_dm_v2_product_in_group")
    products.sort(key=lambda r: str(_attr(r, "product_id") or r["v_id"]))
    return [{"classes": classes}, {"lines": lines}, {"groups": groups}, {"products": products}]


@mock_query("get_driver_causes")
def get_driver_causes(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = vrows(store, DRIVER_CAUSE)
    rows.sort(key=lambda r: _int(_attr(r, "display_order")))
    return [{"causes": rows}]


@mock_query("get_reason_codes")
def get_reason_codes(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = vrows(store, REASON_CODE)
    rows.sort(key=lambda r: _int(_attr(r, "display_order")))
    return [{"reason_codes": rows}]


# ---------------------------------------------------------------- trends

def _mpr_rows(store: FoundationGraphStore, advisor_id: str, from_month: str, to_month: str) -> list[dict]:
    return vrows(
        store,
        MONTHLY_PRODUCT_REVENUE,
        lambda a: str(a.get("advisor_sid")) == advisor_id
        and from_month <= str(a.get("month_id")) <= to_month,
    )


@mock_query("get_monthly_revenue_by_product")
def get_monthly_revenue_by_product(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = _mpr_rows(store, str(params.get("advisor_id") or ""),
                     str(params.get("from_month") or ""), str(params.get("to_month") or ""))
    rows.sort(key=lambda r: (str(_attr(r, "month_id")), str(_attr(r, "group_id"))))
    return [{"monthly_revenue": rows}]


@mock_query("get_monthly_revenue_totals")
def get_monthly_revenue_totals(store: FoundationGraphStore, params: dict) -> list[dict]:
    revenue: dict[str, float] = {}
    recurring: dict[str, float] = {}
    non_recurring: dict[str, float] = {}
    txn_count: dict[str, int] = {}
    for r in _mpr_rows(store, str(params.get("advisor_id") or ""),
                       str(params.get("from_month") or ""), str(params.get("to_month") or "")):
        a = r["attributes"]
        m = str(a.get("month_id"))
        revenue[m] = revenue.get(m, 0.0) + _num(a.get("revenue"))
        recurring[m] = recurring.get(m, 0.0) + _num(a.get("recurring_amt"))
        non_recurring[m] = non_recurring.get(m, 0.0) + _num(a.get("one_time_amt"))
        txn_count[m] = txn_count.get(m, 0) + _int(a.get("txn_count"))
    return [{
        "revenue_by_month": revenue,
        "recurring_by_month": recurring,
        "non_recurring_by_month": non_recurring,
        "txn_count_by_month": txn_count,
    }]


@mock_query("get_revenue_changes")
def get_revenue_changes(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    from_month = str(params.get("from_month") or "")
    to_month = str(params.get("to_month") or "")
    rows = vrows(
        store,
        REVENUE_CHANGE,
        lambda a: str(a.get("advisor_sid")) == advisor_id
        and str(a.get("from_month_id")) >= from_month
        and str(a.get("to_month_id")) <= to_month,
    )
    rows.sort(key=lambda r: (str(_attr(r, "to_month_id")), str(_attr(r, "group_id"))))
    return [{"changes": rows}]


# ---------------------------------------------------------------- drivers & commentary

@mock_query("get_change_drivers")
def get_change_drivers(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    from_month = str(params.get("from_month") or "")
    to_month = str(params.get("to_month") or "")
    limit = _int(params.get("result_limit")) or 100
    change_ids = [
        vid for vid, a in store.all_vertices(REVENUE_CHANGE).items()
        if str(a.get("advisor_sid")) == advisor_id
        and str(a.get("from_month_id")) == from_month
        and str(a.get("to_month_id")) == to_month
    ]
    driver_rows: list[dict] = []
    for change_id in change_ids:
        for driver_id in store.in_ids("phx_dm_v2_driver_of_change", change_id):
            attrs = store.vertex(REVENUE_DRIVER, driver_id)
            if attrs is not None:
                driver_rows.append({"v_id": str(driver_id), "v_type": REVENUE_DRIVER, "attributes": attrs})
    driver_rows.sort(key=lambda r: _int(_attr(r, "rank")))
    return [{"drivers": driver_rows[:limit]}]


@mock_query("get_commentary")
def get_commentary(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    version_id = str(params.get("version_id") or "")
    if version_id == "":
        latest_no = 0
        for a in store.all_vertices(COMMENTARY_VERSION).values():
            if str(a.get("status")) == "PUBLISHED":
                latest_no = max(latest_no, _int(a.get("version_no")))
        target_version = f"v{latest_no}"
    else:
        target_version = version_id
    rows = vrows(
        store,
        COMMENTARY,
        lambda a: str(a.get("advisor_sid")) == advisor_id
        and str(a.get("version_id")) == target_version,
    )
    rows.sort(key=lambda r: str(_attr(r, "to_month_id")))
    return [{"commentaries": rows}, {"resolved_version": target_version}]


@mock_query("get_commentary_evaluations")
def get_commentary_evaluations(store: FoundationGraphStore, params: dict) -> list[dict]:
    version_id = str(params.get("version_id") or "")
    rows = vrows(
        store,
        COMMENTARY_EVALUATION,
        lambda a: version_id == "" or str(a.get("version_id")) == version_id,
    )
    rows.sort(key=lambda r: str(_attr(r, "evaluation_id") or r["v_id"]))
    return [{"evaluations": rows}]


@mock_query("get_commentary_versions")
def get_commentary_versions(store: FoundationGraphStore, params: dict) -> list[dict]:
    rows = vrows(store, COMMENTARY_VERSION)
    rows.sort(key=lambda r: -_int(_attr(r, "version_no")))
    return [{"versions": rows}]


# ---------------------------------------------------------------- evidence & drill-down

@mock_query("get_product_revenue_change")
def get_product_revenue_change(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    product_group = str(params.get("product_group") or "")
    from_month = str(params.get("from_month") or "")
    to_month = str(params.get("to_month") or "")
    from_revenue = to_revenue = 0.0
    txn_count = 0
    for a in store.all_vertices(MONTHLY_PRODUCT_REVENUE).values():
        if str(a.get("advisor_sid")) != advisor_id or str(a.get("group_id")) != product_group:
            continue
        month = str(a.get("month_id"))
        if month == from_month:
            from_revenue += _num(a.get("revenue"))
            txn_count += _int(a.get("txn_count"))
        elif month == to_month:
            to_revenue += _num(a.get("revenue"))
            txn_count += _int(a.get("txn_count"))
    return [{
        "from_revenue": from_revenue,
        "to_revenue": to_revenue,
        "change": to_revenue - from_revenue,
        "txn_count": txn_count,
    }]


@mock_query("get_evidence")
def get_evidence(store: FoundationGraphStore, params: dict) -> list[dict]:
    driver_id = str(params.get("driver_id") or "")
    version_id = str(params.get("version_id") or "")
    rows = vrows(
        store,
        EVIDENCE,
        lambda a: str(a.get("driver_id")) == driver_id,
    )
    if version_id != "":
        wanted = f"{driver_id}|{version_id}"
        rows = [r for r in rows if str(_attr(r, "evidence_id") or r["v_id"]) == wanted]
    rows.sort(key=lambda r: str(_attr(r, "evidence_id") or r["v_id"]))
    return [{"evidence": rows}]


@mock_query("get_transactions")
def get_transactions(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    month_id = str(params.get("month_id") or "")
    group_id = str(params.get("group_id") or "")
    limit = _int(params.get("result_limit")) or 10000

    groups = [
        gid for gid in store.all_vertices(PRODUCT_GROUP)
        if group_id == "" or str(gid) == group_id
    ]
    rows: list[dict] = []
    for gid in groups:
        for product_id in store.in_ids("phx_dm_v2_product_in_group", gid):
            product_attrs = store.vertex(PRODUCT, product_id) or {}
            for txn_id in store.in_ids("phx_dm_v2_txn_for_product", product_id):
                attrs = store.vertex(REVENUE_TRANSACTION, txn_id)
                if attrs is None:
                    continue
                if str(attrs.get("advisor_sid")) != advisor_id or str(attrs.get("month_id")) != month_id:
                    continue
                rows.append({
                    "v_id": str(txn_id), "v_type": REVENUE_TRANSACTION,
                    "attributes": {
                        **attrs,
                        "@group_id": str(gid),
                        "@product_name": str(product_attrs.get("product_name") or ""),
                        "@grid_type": str(product_attrs.get("grid_type") or ""),
                    },
                })
    rows.sort(key=lambda r: (str(_attr(r, "trade_dt")), str(_attr(r, "txn_id") or r["v_id"])))
    return [{"transactions": rows[:limit]}]


# ---------------------------------------------------------------- operations

@mock_query("get_ingestion_counts")
def get_ingestion_counts(store: FoundationGraphStore, params: dict) -> list[dict]:
    counts: dict[str, int] = {}
    source_mix: dict[str, dict[str, int]] = {}
    for vertex_type in V2_VERTEX_TYPES:
        vertices = store.all_vertices(vertex_type)
        if not vertices:
            continue  # mirrors GSQL: an empty type contributes no map entry
        counts[vertex_type] = len(vertices)
        mix: dict[str, int] = {}
        for attrs in vertices.values():
            src = str(attrs.get("data_source") or "")
            mix[src] = mix.get(src, 0) + 1
        source_mix[vertex_type] = mix
    return [{"counts": counts, "source_mix": source_mix}]


@mock_query("get_advisor_month_summary")
def get_advisor_month_summary(store: FoundationGraphStore, params: dict) -> list[dict]:
    advisor_id = str(params.get("advisor_id") or "")
    revenue: dict[str, float] = {}
    txn_count: dict[str, int] = {}
    products: dict[str, set] = {}
    accounts: dict[str, set] = {}
    for attrs in store.all_vertices(REVENUE_TRANSACTION).values():
        if str(attrs.get("advisor_sid")) != advisor_id:
            continue
        m = str(attrs.get("month_id"))
        revenue[m] = revenue.get(m, 0.0) + _num(attrs.get("credited_amt"))
        txn_count[m] = txn_count.get(m, 0) + 1
        products.setdefault(m, set()).add(str(attrs.get("product_id")))
        accounts.setdefault(m, set()).add(str(attrs.get("account_no")))
    return [{
        "revenue_by_month": revenue,
        "txn_count_by_month": txn_count,
        "products_by_month": {m: sorted(v) for m, v in products.items()},
        "accounts_by_month": {m: sorted(v) for m, v in accounts.items()},
    }]


# ---------------------------------------------------------------- anomalies (R6 Y)

@mock_query("get_anomalies")
def get_anomalies(store: FoundationGraphStore, params: dict) -> list[dict]:
    """Mirrors GQ-018: retrieval only (detection is batch). scan_id "" resolves
    to the latest scan by started_at; rows ordered by anomaly_id ASC in both
    tiers — the service applies the severity display ranking."""
    advisor_id = str(params.get("advisor_id") or "")
    scan_id = str(params.get("scan_id") or "")
    severity = str(params.get("severity") or "")
    result_limit = _int(params.get("result_limit")) or 1000
    if scan_id == "":
        scans = store.all_vertices(ANOMALY_SCAN)
        latest = max(
            scans.items(),
            key=lambda kv: (str(kv[1].get("started_at") or ""), str(kv[0])),
            default=None,
        )
        scan_id = str(latest[0]) if latest else ""
    rows = vrows(
        store, ANOMALY,
        lambda a: str(a.get("scan_id")) == scan_id
        and (advisor_id == "" or str(a.get("advisor_sid")) == advisor_id)
        and (severity == "" or str(a.get("severity")) == severity),
    )
    rows.sort(key=lambda r: str(_attr(r, "anomaly_id") or r["v_id"]))
    return [{"scan_id_used": scan_id}, {"anomalies": rows[:result_limit]}]


@mock_query("get_anomaly_scans")
def get_anomaly_scans(store: FoundationGraphStore, params: dict) -> list[dict]:
    """Mirrors GQ-019: full scan history, newest first (scans are additive)."""
    rows = vrows(store, ANOMALY_SCAN)
    rows.sort(key=lambda r: (str(_attr(r, "started_at") or ""), r["v_id"]), reverse=True)
    return [{"scans": rows}]
