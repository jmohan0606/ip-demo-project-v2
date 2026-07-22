"""Shared dataset builder (FIX_SPEC_R4 B2/B3) — the downstream pipeline both
data-set builders call.

Given transactions + dimensions (fabricated by generate_sample_data.py, or
parsed from real extracts by build_real_data.py), this module runs the SAME
app/v2 transform functions the API serves from:

    month_rows            (app.v2.calendar)
    split_by_eligibility  (app.v2.revenue.aggregation)
    aggregate_monthly     (app.v2.revenue.aggregation)
    compute_changes       (app.v2.revenue.aggregation)
    attribute_transition  (app.v2.drivers.attribution)
    reconcile             (app.v2.drivers.attribution)

then writes data/{sample|real}/{vertices,edges}/*.csv with identical columns
and order, stamps data_source on every row via app.v2.dataset.provenance
(B3 — never blank), and regenerates the ingestion manifest.

Reconciliation is a STOP condition: if any transition's driver contributions
do not sum to its total change, ReconciliationError is raised and nothing
further is written about drivers — a real-data reconciliation failure must
halt the build, never load quietly.

Commentary / evidence / evaluation CSVs are NEVER generated here — they are
the Regenerate workflow's job, created after load. Existing workflow CSVs are
preserved (versions are additive, CLAUDE.md §7).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from app.v2.calendar import month_rows
from app.v2.dataset import provenance
from app.v2.drivers.attribution import attribute_transition, reconcile
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import (
    TOTAL_GROUP,
    EligibilityContext,
    aggregate_monthly,
    compute_changes,
    split_by_eligibility,
)

SCHEMA_CATALOG = Path("docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json")

# Workflow-generated files: preserved if present, created header-only on a
# fresh data set, and never counted as "expected rows" in the manifest.
WORKFLOW_FILES = {
    "commentary_version.csv", "commentary.csv", "evidence.csv",
    "commentary_evaluation.csv",
    "commentary_for_advisor.csv", "commentary_from_month.csv",
    "commentary_to_month.csv", "commentary_in_version.csv",
    "commentary_cites_driver.csv", "evidence_for_driver.csv",
    "evaluation_of_commentary.csv",
}

VERTEX_ORDER = ["advisor", "month", "revenue_class", "product_line", "product_group", "product",
                "account", "driver_cause", "reason_code", "revenue_transaction",
                "monthly_product_revenue", "account_month_balance", "revenue_change",
                "revenue_driver", "commentary_version", "commentary",
                "commentary_evaluation", "evidence"]

EDGE_ORDER = ["product_in_group", "group_in_line", "line_in_class",
              "txn_for_advisor", "txn_in_month", "txn_for_product", "txn_for_account",
              "txn_has_reason",
              "mpr_for_advisor", "mpr_in_month", "mpr_for_group",
              "balance_for_account", "balance_in_month",
              "change_for_advisor", "change_for_group", "change_from_month", "change_to_month",
              "driver_of_change", "driver_has_cause", "driver_for_group",
              "commentary_for_advisor", "commentary_from_month", "commentary_to_month",
              "commentary_in_version", "commentary_cites_driver", "evidence_for_driver",
              "evaluation_of_commentary"]

TXN_COLUMNS = ["txn_id", "trade_ref_no", "split_seq_no", "advisor_sid", "month_id", "product_id",
               "account_no", "trade_dt", "proc_dt", "credited_amt", "pre_split_amt", "split_pct",
               "client_rate_bps", "std_tier_rate", "concession_type", "discount_amt", "eff_disc_pct",
               "avg_balance_amt", "file_key", "trade_description", "rev_nature",
               "reason_cd", "rm_sid", "cs_sid", "revenue_eligibility", "incentive_eligible",
               "days_to_process", "posting_month_id", "data_source"]


class ReconciliationError(RuntimeError):
    """Driver contributions did not sum to the total change (stop condition)."""


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def write_vertex_csv(path: Path, rows: list[dict], columns: list[str], artifact: str) -> int:
    """Vertex write with the B3 guarantee: every row stamped, never blank."""
    if artifact in provenance.ARTIFACT_SOURCE:
        provenance.stamp(rows, artifact)
    provenance.require_stamped(artifact, rows)
    return write_csv(path, rows, columns)


def preserve_or_create(path: Path, columns: list[str]) -> int:
    """Workflow-generated CSVs (commentary/evidence): keep existing content —
    versions are additive and regeneration must not delete history. Returns the
    existing row count, or 0 after creating a header-only file."""
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    return write_csv(path, [], columns)


def build_dataset(
    *,
    out_dir: Path,
    manifest_path: Path,
    month_ids: list[str],
    billable_days: dict[str, int],
    txns: list[dict],
    advisors: list[dict],
    classes: list[dict],
    lines: list[tuple],    # (line_id, line_name, class_id, display_order)
    groups: list[tuple],   # (group_id, group_name, line_id, display_order)
    products: list[tuple], # (product_id, cd, sub_cd, name, group_id, grid_type)
    accounts: list[dict],  # account vertex rows
    ctx: EligibilityContext,
    schema_catalog_path: Path = SCHEMA_CATALOG,
) -> dict:
    """Compute the derived vertices with the app's own transform functions and
    write the full vertex/edge CSV set + manifest. Returns a summary dict:
    counts, reconciliation report, eligibility split sizes, MIX share and
    late/out-of-grid visibility. Raises ReconciliationError on any non-$0.00
    transition."""
    product_group = {p[0]: p[4] for p in products}
    group_line = {g[0]: g[2] for g in groups}
    line_class = {l[0]: l[2] for l in lines}
    recurring_class_groups = {g for g, line in group_line.items()
                              if line_class.get(line) == "RECURRING"}

    months = month_rows(month_ids)
    mpr = aggregate_monthly(txns, product_group, group_line, line_class, ctx)
    changes = compute_changes(mpr, month_ids)

    # Attribution runs on CREDITED transactions; the ELIGIBILITY step reads the
    # NON_CREDITED ones (FIX_SPEC R1-8); LATE and EXCLUDED feed their own
    # drivers (FIX_SPEC_R3 T1).
    split = split_by_eligibility(txns, ctx)
    buckets_by_advisor: dict[str, dict[str, dict[tuple, list[dict]]]] = {}
    for bucket in (elig.CREDITED, elig.NON_CREDITED, elig.LATE, elig.EXCLUDED):
        per_advisor: dict[str, dict[tuple, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for t in split[bucket]:
            per_advisor[t["advisor_sid"]][(product_group[t["product_id"]], t["month_id"])].append(t)
        buckets_by_advisor[bucket] = per_advisor

    drivers: list[dict] = []
    by_transition: dict[tuple, list[dict]] = defaultdict(list)
    for c in changes:
        by_transition[(c["advisor_sid"], c["from_month_id"], c["to_month_id"])].append(c)
    for (advisor, from_m, to_m), rows in sorted(by_transition.items()):
        drivers.extend(attribute_transition(
            rows, buckets_by_advisor[elig.CREDITED][advisor], recurring_class_groups,
            billable_days[from_m], billable_days[to_m],
            nc_txns_by_group_month=buckets_by_advisor[elig.NON_CREDITED][advisor],
            late_txns_by_group_month=buckets_by_advisor[elig.LATE][advisor],
            excl_txns_by_group_month=buckets_by_advisor[elig.EXCLUDED][advisor],
            max_processing_days=ctx.max_processing_days,
        ))

    report = reconcile(changes, drivers)
    if not report["all_reconcile"]:
        raise ReconciliationError(
            "RECONCILIATION FAILED — driver contributions do not sum to the "
            "total change on at least one transition; nothing was published:\n"
            + json.dumps(report, indent=2)
        )

    # ------------------------------------------------ vertex CSVs
    v = out_dir / "vertices"
    counts: dict[str, int] = {}
    counts["advisor.csv"] = write_vertex_csv(v / "advisor.csv", advisors,
        ["advisor_sid", "advisor_name", "rep_code", "branch_cd", "standard_id", "data_source"],
        "advisor")
    counts["month.csv"] = write_vertex_csv(v / "month.csv", months, list(months[0].keys()), "month")
    counts["revenue_class.csv"] = write_vertex_csv(v / "revenue_class.csv", classes,
        ["class_id", "class_name", "display_order", "data_source"], "revenue_class")
    counts["product_line.csv"] = write_vertex_csv(v / "product_line.csv",
        [{"line_id": l, "line_name": n, "display_order": o} for l, n, _c, o in lines],
        ["line_id", "line_name", "display_order", "data_source"], "product_line")
    counts["product_group.csv"] = write_vertex_csv(v / "product_group.csv",
        [{"group_id": g, "group_name": n, "display_order": o} for g, n, _l, o in groups],
        ["group_id", "group_name", "display_order", "data_source"], "product_group")
    counts["product.csv"] = write_vertex_csv(v / "product.csv",
        [{"product_id": pid, "product_cd": cd, "product_sub_cd": sub, "product_name": name,
          "grid_type": grid} for pid, cd, sub, name, _g, grid in products],
        ["product_id", "product_cd", "product_sub_cd", "product_name", "grid_type", "data_source"],
        "product")
    counts["account.csv"] = write_vertex_csv(v / "account.csv", accounts,
        ["account_no", "account_typ", "wrap_flg", "data_source"], "account")
    counts["driver_cause.csv"] = write_vertex_csv(v / "driver_cause.csv",
        [dict(r) for r in _driver_cause_rows()],
        ["cause_id", "cause_name", "cause_description", "default_data_source", "display_order",
         "data_source"], "driver_cause")
    counts["reason_code.csv"] = write_vertex_csv(v / "reason_code.csv", elig.seed_rows(),
        ["reason_code", "description", "ui_mapping", "owned_by", "eligibility",
         "include_in_credited", "incentive_eligible", "display_order", "data_source"],
        "reason_code")
    counts["revenue_transaction.csv"] = write_vertex_csv(
        v / "revenue_transaction.csv", txns, TXN_COLUMNS, "revenue_transaction")
    counts["monthly_product_revenue.csv"] = write_vertex_csv(v / "monthly_product_revenue.csv", mpr,
        ["mpr_id", "advisor_sid", "month_id", "group_id", "line_id", "class_id", "revenue",
         "txn_count", "account_count", "avg_rate_bps", "recurring_amt", "one_time_amt",
         "total_revenue", "non_credited_amt", "excluded_amt", "late_excluded_amt", "data_source"],
        "monthly_product_revenue")
    account_ids = [a["account_no"] for a in accounts]
    balances = [{"balance_id": f"{a}|{m}", "account_no": a, "month_id": m,
                 "avg_billable_assets": 0.0, "effective_fee_bps": 0.0,
                 "billable_days": billable_days[m]}
                for a in account_ids for m in month_ids]
    counts["account_month_balance.csv"] = write_vertex_csv(v / "account_month_balance.csv", balances,
        ["balance_id", "account_no", "month_id", "avg_billable_assets", "effective_fee_bps",
         "billable_days", "data_source"], "account_month_balance")
    counts["revenue_change.csv"] = write_vertex_csv(v / "revenue_change.csv", changes,
        ["change_id", "advisor_sid", "from_month_id", "to_month_id", "group_id", "from_revenue",
         "to_revenue", "change_amt", "change_pct", "direction", "data_source"], "revenue_change")
    # revenue_driver rows are stamped per cause by attribution — validate only.
    provenance.require_stamped("revenue_driver", drivers)
    counts["revenue_driver.csv"] = write_csv(v / "revenue_driver.csv", drivers,
        ["driver_id", "change_id", "cause_id", "group_id", "contribution_amt", "contribution_pct",
         "direction", "rank", "inputs_json", "data_source"])
    # Workflow-generated vertices: PRESERVED if present (versions are additive);
    # created header-only on a fresh data set. NEVER generated here.
    counts["commentary_version.csv"] = preserve_or_create(v / "commentary_version.csv",
        ["version_id", "version_no", "generated_at", "model", "prompt_version", "data_snapshot_dt",
         "status", "advisor_count", "transition_count", "blocked_count", "notes", "data_source"])
    counts["commentary.csv"] = preserve_or_create(v / "commentary.csv",
        ["commentary_id", "version_id", "advisor_sid", "from_month_id", "to_month_id", "headline",
         "narrative_text", "bullets_json", "status", "blocked_reason", "data_source"])
    counts["commentary_evaluation.csv"] = preserve_or_create(v / "commentary_evaluation.csv",
        ["evaluation_id", "commentary_id", "version_id", "judge_model", "faithfulness_score",
         "hallucination_flag", "completeness_score", "clarity_score", "verdict", "reasoning",
         "evaluated_at", "data_source"])
    counts["evidence.csv"] = preserve_or_create(v / "evidence.csv",
        ["evidence_id", "driver_id", "finding_text", "calc_json", "source_records_json",
         "lineage_json", "checks_json", "gsql_query_name", "gsql_params_json", "gsql_result_json",
         "source_sql", "source_table", "source_row_count", "data_source"])

    # ------------------------------------------------ edge CSVs
    e = out_dir / "edges"

    def edge_rows(name: str, pairs: list[tuple[str, str]]) -> int:
        seen, rows = set(), []
        for f_, t_ in pairs:
            if (f_, t_) not in seen:
                seen.add((f_, t_))
                rows.append({"from_id": f_, "to_id": t_})
        return write_csv(e / f"{name}.csv", rows, ["from_id", "to_id"])

    counts["product_in_group.csv"] = edge_rows("product_in_group",
        [(pid, g) for pid, _cd, _sub, _name, g, _grid in products])
    counts["group_in_line.csv"] = edge_rows("group_in_line", [(g, l) for g, _n, l, _o in groups])
    counts["line_in_class.csv"] = edge_rows("line_in_class", [(l, c) for l, _n, c, _o in lines])
    counts["txn_for_advisor.csv"] = edge_rows("txn_for_advisor", [(t["txn_id"], t["advisor_sid"]) for t in txns])
    counts["txn_in_month.csv"] = edge_rows("txn_in_month", [(t["txn_id"], t["month_id"]) for t in txns])
    counts["txn_for_product.csv"] = edge_rows("txn_for_product", [(t["txn_id"], t["product_id"]) for t in txns])
    counts["txn_for_account.csv"] = edge_rows("txn_for_account", [(t["txn_id"], t["account_no"]) for t in txns])
    counts["txn_has_reason.csv"] = edge_rows("txn_has_reason", [(t["txn_id"], t["reason_cd"]) for t in txns])
    counts["mpr_for_advisor.csv"] = edge_rows("mpr_for_advisor", [(r["mpr_id"], r["advisor_sid"]) for r in mpr])
    counts["mpr_in_month.csv"] = edge_rows("mpr_in_month", [(r["mpr_id"], r["month_id"]) for r in mpr])
    counts["mpr_for_group.csv"] = edge_rows("mpr_for_group", [(r["mpr_id"], r["group_id"]) for r in mpr])
    counts["balance_for_account.csv"] = edge_rows("balance_for_account", [(b["balance_id"], b["account_no"]) for b in balances])
    counts["balance_in_month.csv"] = edge_rows("balance_in_month", [(b["balance_id"], b["month_id"]) for b in balances])
    counts["change_for_advisor.csv"] = edge_rows("change_for_advisor", [(c["change_id"], c["advisor_sid"]) for c in changes])
    counts["change_for_group.csv"] = edge_rows("change_for_group",
        [(c["change_id"], c["group_id"]) for c in changes if c["group_id"] != TOTAL_GROUP])
    counts["change_from_month.csv"] = edge_rows("change_from_month", [(c["change_id"], c["from_month_id"]) for c in changes])
    counts["change_to_month.csv"] = edge_rows("change_to_month", [(c["change_id"], c["to_month_id"]) for c in changes])
    counts["driver_of_change.csv"] = edge_rows("driver_of_change", [(d["driver_id"], d["change_id"]) for d in drivers])
    counts["driver_has_cause.csv"] = edge_rows("driver_has_cause", [(d["driver_id"], d["cause_id"]) for d in drivers])
    counts["driver_for_group.csv"] = edge_rows("driver_for_group",
        [(d["driver_id"], d["group_id"]) for d in drivers if d["group_id"] != TOTAL_GROUP])
    # Workflow-generated edges — preserved if present.
    for name in ("commentary_for_advisor", "commentary_from_month", "commentary_to_month",
                 "commentary_in_version", "commentary_cites_driver", "evidence_for_driver",
                 "evaluation_of_commentary"):
        counts[f"{name}.csv"] = preserve_or_create(e / f"{name}.csv", ["from_id", "to_id"])

    # ------------------------------------------------ manifest
    schema = json.load(open(schema_catalog_path))
    files = []
    order = 0
    for name in VERTEX_ORDER:
        target = f"phx_dm_v2_{name}"
        spec = schema["vertices"][target]
        cols = list(spec["attributes"].keys())
        fname = f"{name}.csv"
        order += 1
        files.append({
            "kind": "vertex", "target": target, "file": f"vertices/{fname}", "order": order,
            "id_column": spec["primary_id"]["name"],
            "columns": {c: c for c in cols},
            "required_columns": [spec["primary_id"]["name"], "data_source"],
            "expected_rows": None if fname in WORKFLOW_FILES else counts[fname],
            "workflow_generated": fname in WORKFLOW_FILES,
        })
    for name in EDGE_ORDER:
        target = f"phx_dm_v2_{name}"
        spec = schema["edges"][target]
        fname = f"{name}.csv"
        order += 1
        files.append({
            "kind": "edge", "target": target, "file": f"edges/{fname}", "order": order,
            "from_type": spec["from"], "to_type": spec["to"],
            "from_column": "from_id", "to_column": "to_id",
            "columns": {},
            "expected_rows": None if fname in WORKFLOW_FILES else counts[fname],
            "workflow_generated": fname in WORKFLOW_FILES,
        })
    manifest = {
        "graph": "iperform_v2_revenue",
        "prefix": "phx_dm_v2_",
        "batch_size": 500,
        "note": "Files listed in dependency order: dimensions, facts, analytics, then edges. "
                "Load top-to-bottom; delete bottom-to-top (vertex deletes cascade their edges). "
                "workflow_generated files start header-only and are appended by the commentary workflow.",
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(manifest, open(manifest_path, "w"), indent=2)

    return {
        "counts": counts,
        "report": report,
        "split_sizes": {k: len(rows) for k, rows in split.items()},
        "mix_share": _mix_share(changes, drivers),
        "out_of_grid_count": len(split[elig.OUT_OF_GRID]),
        "late_count": len(split[elig.LATE]),
        "txns": txns, "mpr": mpr, "changes": changes, "drivers": drivers,
    }


def _mix_share(changes: list[dict], drivers: list[dict]) -> dict[str, dict]:
    """MIX residual per transition as a % of the transition's |total change| —
    the honesty metric FIX_SPEC_R3 T1-3/T1-4 tracks (a large MIX means a named
    driver is missing)."""
    total_change: dict[tuple, float] = {}
    for c in changes:
        if c["group_id"] == TOTAL_GROUP:
            total_change[(c["advisor_sid"], c["from_month_id"], c["to_month_id"])] = float(c["change_amt"])
    mix_sum: dict[tuple, float] = defaultdict(float)
    for d in drivers:
        if d["cause_id"] == "MIX":
            key = tuple(d["driver_id"].split("|")[:3])
            mix_sum[key] += float(d["contribution_amt"])
    out = {}
    for key, total in sorted(total_change.items()):
        mix = mix_sum.get(key, 0.0)
        out["|".join(key)] = {
            "total_change": round(total, 2),
            "mix_total": round(mix, 2),
            "mix_pct_of_change": round(abs(mix) / abs(total) * 100, 2) if abs(total) > 0.005 else 0.0,
        }
    return out


def _driver_cause_rows() -> list[dict]:
    """The driver_cause seed — single source shared by sample and real
    (previously inlined in generate_sample_data.py)."""
    causes = [
        ("VOLUME", "Transaction volume", "More or fewer transactions at similar rates", "REAL", 1),
        ("ONE_TIME", "One-time items", "Syndicate allocations, new issues, referrals that don't repeat", "REAL", 2),
        ("ELIGIBILITY", "Credited eligibility", "Revenue moved between credited and non-credited reason codes month over month", "REAL", 3),
        ("LATE_PROCESSING", "Late processing", "Revenue excluded by the 90-day rule (processed more than 90 days after the trade) changed month over month", "REAL", 4),
        ("EXCLUDED_CHANGE", "Excluded bookings", "Revenue moved between credited and excluded reason codes (e.g. deleted bookings) month over month", "REAL", 5),
        ("TIMING", "Billing timing", "Quarterly billing cycle falls in one month not the other", "REAL", 6),
        ("FEE_RATE", "Effective fee rate", "Change in client_rate_bps / std_tier_rate", "REAL", 7),
        ("DISCOUNT", "Discounting", "Change in concession_type / discount_amt / eff_disc_pct", "REAL", 8),
        ("BILLABLE_DAYS", "Billable days", "Different number of billing days between months", "DERIVED", 9),
        ("MIX", "Product mix", "Shift between products at different rates", "DERIVED", 10),
        ("NEW_ACCOUNT", "Accounts opened", "Accounts contributing this month but not last", "REAL", 11),
        ("LOST_ACCOUNT", "Accounts closed", "Accounts contributing last month but not this", "REAL", 12),
        ("CLAWBACK", "Reversals", "Negative credited amounts (chargebacks)", "REAL", 13),
        ("MARKET", "Market performance", "Asset value movement", "DUMMY", 14),
        ("NET_FLOW", "Net client flows", "Inflows less outflows", "DUMMY", 15),
    ]
    return [{"cause_id": c, "cause_name": n, "cause_description": d, "default_data_source": s,
             "display_order": o} for c, n, d, s, o in causes]
