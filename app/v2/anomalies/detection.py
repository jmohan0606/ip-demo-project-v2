"""Anomaly detection — batch scan over STORED drivers and revenue (FIX_SPEC_R6 Y).

Detection is deterministic Python; the model only phrases each finding
(commentary_agent.narrate_anomaly, gated by the no-invented-figures guardrail
with a deterministic template fallback). Every anomaly carries metrics_json —
the computed figures that triggered it — and threshold_json — the config
values in force when it fired.

Batch, never on read: the /anomalies screen RETRIEVES stored anomalies
(GQ-018/019); this module runs only from POST /api/v2/anomalies/scan or the
headless CLI:

    python -m app.v2.anomalies.detection

Scans are ADDITIVE and versioned exactly like commentary: every run creates a
new phx_dm_v2_anomaly_scan and attaches its anomalies to it; prior scans are
never deleted and remain queryable through the scan selector.

Six rules (Y2), thresholds ALL in config (settings.anomaly_*):
    UNEXPLAINED_RESIDUAL      HIGH    |MIX| / |total change| > threshold
    CLAWBACK_CONCENTRATION    HIGH    month clawbacks > N x trailing mean, min floor
    LARGE_SWING               MEDIUM  |change_pct| > threshold and |change_amt| > floor
    FEE_RATE_SHIFT            MEDIUM  effective rate moved > N bps on a recurring group
    SINGLE_DRIVER_DOMINANCE   LOW     one named driver > N% of the change
    BASELINE_LIMITED_PRESENT  INFO    transition carries a BASELINE_LIMITED driver
BOOK_MOVEMENT is deliberately NOT implemented this round (Y2) — it depends on
account movement being real, which work-stream A showed is largely trading
intermittency; re-evaluate once the fixed attribution has run on real data.
"""
from __future__ import annotations

import csv
import json
import threading
from datetime import datetime, timezone

from app.config.settings import get_settings
from app.graph.client import get_graph_client
from app.graph.queries.common import ANOMALY_SCAN
from app.ingestion.tigergraph_upsert import TigerGraphUpsertClient
from app.shared.logging import get_logger
from app.v2.dataset.builder import csv_file_for
from app.v2.format import fmt_money, fmt_pct

_log = get_logger("app.v2.anomalies")
_lock = threading.Lock()
_status: dict = {"state": "idle"}

SEVERITY = {
    "UNEXPLAINED_RESIDUAL": "HIGH",
    "CLAWBACK_CONCENTRATION": "HIGH",
    "LARGE_SWING": "MEDIUM",
    "FEE_RATE_SHIFT": "MEDIUM",
    "SINGLE_DRIVER_DOMINANCE": "LOW",
    "BASELINE_LIMITED_PRESENT": "INFO",
}
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


def get_status() -> dict:
    with _lock:
        return dict(_status)


def thresholds_in_force() -> dict:
    """The config values every scan stamps into threshold_json (Y2 — surfaced
    in the UI and the scan summary; never hardcoded in the rules)."""
    s = get_settings()
    return {
        "ANOMALY_UNEXPLAINED_RESIDUAL_PCT": s.anomaly_unexplained_residual_pct,
        "ANOMALY_CLAWBACK_MULTIPLE": s.anomaly_clawback_multiple,
        "ANOMALY_CLAWBACK_MIN_USD": s.anomaly_clawback_min_usd,
        "ANOMALY_LARGE_SWING_PCT": s.anomaly_large_swing_pct,
        "ANOMALY_LARGE_SWING_MIN_USD": s.anomaly_large_swing_min_usd,
        "ANOMALY_FEE_RATE_SHIFT_BPS": s.anomaly_fee_rate_shift_bps,
        "ANOMALY_SINGLE_DRIVER_DOMINANCE_PCT": s.anomaly_single_driver_dominance_pct,
    }


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _attrs(rows_obj: list[dict], key: str) -> list[dict]:
    for obj in rows_obj:
        if key in obj:
            return [r.get("attributes", {}) for r in obj[key]]
    return []


def _run_query(graph, name: str, params: dict) -> list[dict]:
    result = graph.run_query(name, params)
    if not isinstance(result, dict) or result.get("error"):
        raise RuntimeError(f"{name} returned an error envelope")
    return result.get("results", [])


def _month_name(month_id: str) -> str:
    names = ["", "January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    return f"{names[int(month_id[4:6])]} {month_id[:4]}"


# ---------------------------------------------------------------- the six rules
# Each returns None or a dict {rule_id, metrics, cited_driver_ids, impact_amt,
# group_id}. metrics holds BOTH raw figures and display-formatted strings —
# all computed here; the model never adds a number.

def rule_unexplained_residual(ctx: dict) -> dict | None:
    threshold = ctx["thresholds"]["ANOMALY_UNEXPLAINED_RESIDUAL_PCT"]
    total = ctx["total_change"]
    mix_rows = [d for d in ctx["drivers"] if d.get("cause_id") == "MIX"]
    mix_total = sum(_num(d.get("contribution_amt")) for d in mix_rows)
    if abs(total) < 1.0 or abs(mix_total) <= threshold * abs(total):
        return None
    share = abs(mix_total) / abs(total)
    return {
        "rule_id": "UNEXPLAINED_RESIDUAL",
        "impact_amt": round(mix_total, 2),
        "group_id": "",
        "cited_driver_ids": [d["driver_id"] for d in mix_rows],
        "metrics": {
            "mix_total_raw": round(mix_total, 2), "total_change_raw": round(total, 2),
            "mix_share_raw": round(share, 4),
            "mix_total": fmt_money(mix_total), "total_change": fmt_money(total),
            "mix_pct_of_change": fmt_pct(share * 100),
        },
    }


def rule_clawback_concentration(ctx: dict) -> dict | None:
    t = ctx["thresholds"]
    to_month = ctx["to_month"]
    clawback_by_month: dict[str, float] = ctx["clawback_by_month"]
    prior = [m for m in ctx["month_ids"] if m < to_month]
    if not prior:
        return None  # no trailing window in the loaded range
    trailing = [abs(clawback_by_month.get(m, 0.0)) for m in prior]
    trailing_mean = sum(trailing) / len(trailing)
    this_month = abs(clawback_by_month.get(to_month, 0.0))
    if this_month < t["ANOMALY_CLAWBACK_MIN_USD"]:
        return None
    if trailing_mean > 0 and this_month <= t["ANOMALY_CLAWBACK_MULTIPLE"] * trailing_mean:
        return None
    cited = [d["driver_id"] for d in ctx["drivers"] if d.get("cause_id") == "CLAWBACK"]
    return {
        "rule_id": "CLAWBACK_CONCENTRATION",
        "impact_amt": round(-this_month, 2),
        "group_id": "",
        "cited_driver_ids": cited,
        "metrics": {
            "clawback_total_raw": round(-this_month, 2),
            "trailing_mean_raw": round(-trailing_mean, 2),
            "trailing_months": prior,
            "clawback_total": fmt_money(-this_month),
            "trailing_mean": fmt_money(-trailing_mean),
            "month": _month_name(to_month),
        },
    }


def rule_large_swing(ctx: dict) -> dict | None:
    t = ctx["thresholds"]
    total_row = ctx["total_row"]
    change_amt = _num(total_row.get("change_amt"))
    change_pct = _num(total_row.get("change_pct"))
    if abs(change_pct) <= t["ANOMALY_LARGE_SWING_PCT"] or \
       abs(change_amt) <= t["ANOMALY_LARGE_SWING_MIN_USD"]:
        return None
    return {
        "rule_id": "LARGE_SWING",
        "impact_amt": round(change_amt, 2),
        "group_id": "",
        "cited_driver_ids": [],
        "metrics": {
            "change_amt_raw": round(change_amt, 2), "change_pct_raw": round(change_pct, 2),
            "change_amt": fmt_money(change_amt), "change_pct": fmt_pct(change_pct),
        },
    }


def rule_fee_rate_shift(ctx: dict) -> list[dict]:
    """Group-scoped: may fire for more than one recurring group."""
    t = ctx["thresholds"]
    out = []
    for group_id, rates in sorted(ctx["recurring_rates"].items()):
        from_rate = rates.get(ctx["from_month"])
        to_rate = rates.get(ctx["to_month"])
        if not from_rate or not to_rate:
            continue
        shift = to_rate - from_rate
        if abs(shift) <= t["ANOMALY_FEE_RATE_SHIFT_BPS"]:
            continue
        cited = [d["driver_id"] for d in ctx["drivers"]
                 if d.get("cause_id") == "FEE_RATE" and d.get("group_id") == group_id]
        out.append({
            "rule_id": "FEE_RATE_SHIFT",
            "impact_amt": sum(_num(d.get("contribution_amt")) for d in ctx["drivers"]
                              if d.get("cause_id") == "FEE_RATE" and d.get("group_id") == group_id),
            "group_id": group_id,
            "cited_driver_ids": cited,
            "metrics": {
                "from_rate_bps_raw": round(from_rate, 2), "to_rate_bps_raw": round(to_rate, 2),
                "shift_bps_raw": round(shift, 2),
                "from_rate_bps": f"{from_rate:.1f}", "to_rate_bps": f"{to_rate:.1f}",
                "shift_bps": f"({abs(shift):.1f})" if shift < 0 else f"{shift:.1f}",
                "group_name": ctx["group_names"].get(group_id, group_id),
            },
        })
    return out


def rule_single_driver_dominance(ctx: dict) -> dict | None:
    t = ctx["thresholds"]
    total = ctx["total_change"]
    if abs(total) < 1.0:
        return None
    named = [d for d in ctx["drivers"]
             if d.get("cause_id") not in ("MIX", "MARKET", "NET_FLOW")
             and abs(_num(d.get("contribution_amt"))) > 0]
    if not named:
        return None
    top = max(named, key=lambda d: abs(_num(d.get("contribution_amt"))))
    share = abs(_num(top.get("contribution_amt"))) / abs(total) * 100
    if share <= t["ANOMALY_SINGLE_DRIVER_DOMINANCE_PCT"]:
        return None
    return {
        "rule_id": "SINGLE_DRIVER_DOMINANCE",
        "impact_amt": round(_num(top.get("contribution_amt")), 2),
        "group_id": str(top.get("group_id") or ""),
        "cited_driver_ids": [top["driver_id"]],
        "metrics": {
            "contribution_raw": round(_num(top.get("contribution_amt")), 2),
            "share_raw": round(share, 2), "total_change_raw": round(total, 2),
            "contribution": fmt_money(_num(top.get("contribution_amt"))),
            "share_of_change": fmt_pct(share),
            "total_change": fmt_money(total),
            "cause_id": str(top.get("cause_id")),
            "cause_name": ctx["cause_names"].get(str(top.get("cause_id")), str(top.get("cause_id"))),
        },
    }


def rule_baseline_limited_present(ctx: dict) -> dict | None:
    bl = [d for d in ctx["drivers"] if d.get("cause_id") == "BASELINE_LIMITED"]
    if not bl:
        return None
    bl_total = sum(_num(d.get("contribution_amt")) for d in bl)
    return {
        "rule_id": "BASELINE_LIMITED_PRESENT",
        "impact_amt": round(bl_total, 2),
        "group_id": "",
        "cited_driver_ids": [d["driver_id"] for d in bl],
        "metrics": {
            "baseline_limited_amt_raw": round(bl_total, 2),
            "baseline_limited_amt": fmt_money(bl_total),
            "driver_count": len(bl),
        },
    }


# ---------------------------------------------------------------- persistence

def _csv_append(file_rel: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = get_settings().resolved_data_set_dir / file_rel
    with path.open(newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        for r in rows:
            writer.writerow(r)


def _persist(upsert: TigerGraphUpsertClient, entity: str, kind: str,
             rows: list[dict], id_column: str = "") -> None:
    if not rows:
        return
    if kind == "vertex":
        upsert.upsert_vertex_rows(f"phx_dm_v2_{entity}", rows, id_column)
    else:
        upsert.upsert_edge_rows(f"phx_dm_v2_{entity}", rows)
    _csv_append(csv_file_for(kind, entity), rows)


def _next_scan_id(graph) -> str:
    store = getattr(graph, "store", None)
    existing = store.all_vertices(ANOMALY_SCAN) if store is not None else {}
    numbers = [int(str(s).replace("scan", "") or 0) for s in existing
               if str(s).startswith("scan") and str(s)[4:].isdigit()]
    return f"scan{(max(numbers, default=0) + 1):03d}"


# ---------------------------------------------------------------- the scan

def run_scan(notes: str = "") -> dict:
    """Synchronous batch scan (small advisor set) — mirrors the commentary
    workflow: new scan_id every run, prior scans never deleted."""
    with _lock:
        if _status.get("state") == "running":
            return {"error": True, "message": "scan already running"}
        _status.update({"state": "running",
                        "started_at": datetime.now(timezone.utc).isoformat()})
    try:
        summary = _scan(notes)
        with _lock:
            _status.update({"state": "completed", "summary": summary,
                            "finished_at": datetime.now(timezone.utc).isoformat()})
        return summary
    except Exception as exc:  # noqa: BLE001 — recorded and surfaced, never hidden
        _log.error("anomaly scan failed: %s", exc, exc_info=True)
        with _lock:
            _status.update({"state": "failed", "error": str(exc)})
        raise


def _scan(notes: str = "") -> dict:
    from app.agents.nodes.commentary_agent import narrate_anomaly
    from app.llm.client import get_llm_client

    graph = get_graph_client()
    upsert = TigerGraphUpsertClient()
    llm = get_llm_client()
    thresholds = thresholds_in_force()

    advisors = [a.get("advisor_sid") for a in
                _attrs(_run_query(graph, "get_advisors", {}), "advisors")]
    month_ids = sorted(str(m.get("month_id")) for m in
                       _attrs(_run_query(graph, "get_months", {}), "months"))
    transitions = list(zip(month_ids, month_ids[1:]))
    cause_names = {str(c.get("cause_id")): str(c.get("cause_name"))
                   for c in _attrs(_run_query(graph, "get_driver_causes", {}), "causes")}

    scan_id = _next_scan_id(graph)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    anomalies: list[dict] = []
    e_for_advisor, e_in_scan, e_cites = [], [], []
    ai_worded = fallback_worded = 0

    for advisor in advisors:
        changes = _attrs(_run_query(graph, "get_revenue_changes", {
            "advisor_id": advisor, "from_month": month_ids[0], "to_month": month_ids[-1]}),
            "changes")
        mpr = _attrs(_run_query(graph, "get_monthly_revenue_by_product", {
            "advisor_id": advisor, "from_month": month_ids[0], "to_month": month_ids[-1]}),
            "monthly_revenue")
        group_names: dict[str, str] = {}
        recurring_rates: dict[str, dict[str, float]] = {}
        for r in mpr:
            gid = str(r.get("group_id"))
            group_names.setdefault(gid, gid.replace("_", " ").title())
            if str(r.get("class_id")) == "RECURRING" and _num(r.get("avg_rate_bps")) > 0:
                recurring_rates.setdefault(gid, {})[str(r.get("month_id"))] = _num(r.get("avg_rate_bps"))
        # Clawback totals per month: negative credited transactions (stored rows).
        clawback_by_month: dict[str, float] = {}
        for m in month_ids:
            txns = _attrs(_run_query(graph, "get_transactions", {
                "advisor_id": advisor, "month_id": m, "group_id": "",
                "result_limit": 100000}), "transactions")
            clawback_by_month[m] = sum(_num(t.get("credited_amt")) for t in txns
                                       if _num(t.get("credited_amt")) < 0)

        for from_m, to_m in transitions:
            tr_changes = [c for c in changes
                          if str(c.get("from_month_id")) == from_m
                          and str(c.get("to_month_id")) == to_m]
            total_row = next((c for c in tr_changes if c.get("group_id") == "__TOTAL__"), None)
            if total_row is None:
                continue
            drivers = _attrs(_run_query(graph, "get_change_drivers", {
                "advisor_id": advisor, "from_month": from_m, "to_month": to_m,
                "result_limit": 10000}), "drivers")
            ctx = {
                "thresholds": thresholds, "advisor": advisor,
                "from_month": from_m, "to_month": to_m, "month_ids": month_ids,
                "total_row": total_row, "total_change": _num(total_row.get("change_amt")),
                "drivers": drivers, "clawback_by_month": clawback_by_month,
                "recurring_rates": recurring_rates, "group_names": group_names,
                "cause_names": cause_names,
            }
            fired: list[dict] = []
            for rule in (rule_unexplained_residual, rule_clawback_concentration,
                         rule_large_swing, rule_single_driver_dominance,
                         rule_baseline_limited_present):
                hit = rule(ctx)
                if hit:
                    fired.append(hit)
            fired.extend(rule_fee_rate_shift(ctx))

            for hit in fired:
                # Primary id: the spec's advisor|from|to|rule, PREFIXED with the
                # scan id (exactly as commentary ids embed their version) —
                # without it a re-scan would upsert over the prior scan's rows
                # and scans would not be additive. Group-scoped rules append
                # the group so two groups firing the same rule cannot collide.
                # Both deviations recorded in BUILD_REPORT.
                anomaly_id = f"{scan_id}|{advisor}|{from_m}|{to_m}|{hit['rule_id']}"
                if hit["group_id"]:
                    anomaly_id += f"|{hit['group_id']}"
                wording = narrate_anomaly(hit["rule_id"], hit["metrics"], thresholds, llm)
                if wording["ai_generated"]:
                    ai_worded += 1
                else:
                    fallback_worded += 1
                metrics = dict(hit["metrics"])
                metrics["ai_generated"] = wording["ai_generated"]
                metrics["wording_model"] = wording["model"]
                anomalies.append({
                    "anomaly_id": anomaly_id, "advisor_sid": advisor,
                    "from_month_id": from_m, "to_month_id": to_m,
                    "rule_id": hit["rule_id"], "severity": SEVERITY[hit["rule_id"]],
                    "title": wording["title"], "detail_text": wording["detail_text"],
                    "metrics_json": json.dumps(metrics, sort_keys=True),
                    "threshold_json": json.dumps(thresholds, sort_keys=True),
                    "impact_amt": hit["impact_amt"], "group_id": hit["group_id"],
                    "scan_id": scan_id, "detected_at": started_at,
                    "data_source": "DERIVED",
                })
                e_for_advisor.append({"from_id": anomaly_id, "to_id": advisor})
                e_in_scan.append({"from_id": anomaly_id, "to_id": scan_id})
                for did in hit["cited_driver_ids"]:
                    e_cites.append({"from_id": anomaly_id, "to_id": did})

    scan_row = {
        "scan_id": scan_id, "started_at": started_at,
        "advisors_reviewed": len(advisors),
        "transitions_reviewed": len(advisors) * len(transitions),
        "flagged_count": len(anomalies),
        "thresholds_json": json.dumps(thresholds, sort_keys=True),
        "status": "COMPLETED", "data_source": "DERIVED",
    }
    _persist(upsert, "anomaly_scan", "vertex", [scan_row], "scan_id")
    _persist(upsert, "anomaly", "vertex", anomalies, "anomaly_id")
    _persist(upsert, "anomaly_for_advisor", "edge", e_for_advisor)
    _persist(upsert, "anomaly_in_scan", "edge", e_in_scan)
    _persist(upsert, "anomaly_cites_driver", "edge", e_cites)

    summary = {
        "scan_id": scan_id, "started_at": started_at,
        "advisors_reviewed": len(advisors),
        "transitions_reviewed": len(advisors) * len(transitions),
        "flagged": len(anomalies),
        "by_severity": {s: sum(1 for a in anomalies if a["severity"] == s)
                        for s in ("HIGH", "MEDIUM", "LOW", "INFO")},
        "by_rule": {r: sum(1 for a in anomalies if a["rule_id"] == r)
                    for r in SEVERITY},
        "wording": {"ai_generated": ai_worded, "deterministic_fallback": fallback_worded},
        "thresholds": thresholds,
        "notes": notes,
    }
    _log.info("anomaly scan complete: %s", summary)
    return summary


if __name__ == "__main__":  # pragma: no cover
    # Y5 — headless CLI equivalent of the Re-scan button for client
    # environments without a browser:  python -m app.v2.anomalies.detection
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Batch anomaly scan (same as the UI Re-scan button)")
    parser.add_argument("--notes", default="", help="free-text note (recorded in the summary log)")
    args = parser.parse_args()
    result = run_scan(args.notes)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result.get("error") else 0)
