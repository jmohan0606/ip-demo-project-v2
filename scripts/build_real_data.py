"""Build data/real/ from the client's raw extracts (FIX_SPEC_R4 B1/B2).

    python -m scripts.build_real_data [--raw data/real/_raw] [--out data/real]

THE MISSING MIDDLE of the real-data path: a human runs the three SQLs in
docs/data/extraction/ against the client's PostgreSQL and saves the results as
CSV; this script turns those raw extracts into the vertex/edge CSV set the
ingestion screen loads — by calling the SAME shared pipeline the sample
generator uses (app/v2/dataset/builder.py → app/v2 transform functions). The
only thing that differs from the sample path is where the transactions and
dimensions come from: parsed here from real extracts instead of fabricated.

## Raw-extract contract (B1)

data/real/_raw/
  raw_revenue_transaction.csv   <- output of extract_revenue_transaction.sql
  raw_product_hierarchy.csv     <- output of extract_product_hierarchy.sql
  raw_advisor.csv               <- output of extract_advisor.sql

Expected columns mirror the SELECT lists of the generated SQL (see
RAW_CONTRACT below). Save with a header row, comma-separated, UTF-8 — the
default CSV export of psql/DBeaver/pgAdmin. Presence and column names are
validated on load; a missing file or column fails loudly with its name —
never a silent partial build.

## What it computes

Dimensions from the hierarchy/advisor extracts (product_line = distinct
level_one_product, product_group = distinct level_two_product, class =
Managed/Trails -> RECURRING per EXTRACTION_SPEC §4), transactions mapped per
EXTRACTION_SPEC (post_split_credited_amt -> credited_amt, rev_nature derived,
reason_cd -> revenue_eligibility via the reason-code seed, days_to_process
computed, posting_month_id = trade month ASSUMED), then the shared builder
runs eligibility / aggregation / attribution and ASSERTS $0.00 reconciliation
on every transition — a failure is a STOP, nothing further should be loaded.

Every written row carries data_source via app/v2/dataset/provenance (B3).
Commentary/evidence are NOT generated here — that is the Regenerate workflow's
job, run after the data is loaded.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import get_settings
from app.v2.dataset.builder import ReconciliationError, build_dataset
from app.v2.calendar import month_rows
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import EligibilityContext, derive_rev_nature

MANIFEST = Path("docs/tigergraph_foundation/data/manifest.json")

# ---------------------------------------------------------------- B1 contract
# file -> (source SQL, required columns — the SELECT list of that SQL)
RAW_CONTRACT: dict[str, dict] = {
    "raw_revenue_transaction.csv": {
        "sql": "extract_revenue_transaction.sql",
        "columns": ["trade_ref_no", "split_seq_no", "advisor_sid", "month_id",
                    "product_cd", "product_sub_cd", "account_no",
                    "trade_dt", "proc_dt",
                    "post_split_credited_amt", "pre_split_credited_amt", "split_pct",
                    "client_rate_bps", "std_tier_rate",
                    "concession_type", "discount_amt", "eff_disc_pct",
                    "avg_balance_amt", "file_key", "trade_description",
                    "reason_cd", "rm_sid", "cs_sid", "grid_type"],
    },
    "raw_product_hierarchy.csv": {
        "sql": "extract_product_hierarchy.sql",
        "columns": ["product_code", "sub_product_code",
                    "level_two_product", "level_one_product", "grid_type",
                    "level_one_pay_type_product_cd", "level_two_pay_type_product_cd"],
    },
    "raw_advisor.csv": {
        "sql": "extract_advisor.sql",
        "columns": ["advisor_sid", "rr_nam", "rep_code", "branch_cd", "advisor_name"],
    },
}

# Recurring vs non-recurring class: Recurring = product lines Managed and
# Trails; everything else Non-recurring (EXTRACTION_SPEC §4 — inferred from
# the client mockup, flagged for confirmation).
RECURRING_LINE_NAMES = {"managed", "trails"}


def fail(msg: str) -> "sys.NoReturn":
    print(f"\nBUILD FAILED — {msg}", file=sys.stderr)
    sys.exit(1)


def read_raw(raw_dir: Path, filename: str) -> list[dict]:
    """Read one raw extract, validating the B1 contract loudly."""
    spec = RAW_CONTRACT[filename]
    path = raw_dir / filename
    if not path.exists():
        fail(f"missing raw extract {path} — run docs/data/extraction/{spec['sql']} "
             f"in your Postgres client and save the result as this file (with a header row).")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in spec["columns"] if c not in header]
        if missing:
            fail(f"{path} is missing required column(s) {missing}. Expected the SELECT "
                 f"list of docs/data/extraction/{spec['sql']}: {spec['columns']}. Found: {header}")
        rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    if not rows:
        fail(f"{path} contains a header but no data rows.")
    return rows


def _num(value: str, *, context: str) -> float:
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except ValueError:
        fail(f"non-numeric value {value!r} in {context}")


def slug(name: str) -> str:
    """'Unified Managed Account' -> 'unified_managed_account' (stable id)."""
    s = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    return s or "unclassified"


def build_dimensions(hier_rows: list[dict], adv_rows: list[dict]) -> dict:
    """product_line / product_group / product / class structures in the exact
    tuple shapes the shared builder takes, from the raw hierarchy extract."""
    lines_seen: dict[str, str] = {}    # line_id -> display name
    groups_seen: dict[str, tuple[str, str]] = {}  # group_id -> (name, line_id)
    products: list[tuple] = []
    seen_products: set[str] = set()
    for r in hier_rows:
        line_name = r["level_one_product"] or "Unclassified"
        group_name = r["level_two_product"] or "Unclassified"
        line_id, group_id = slug(line_name), slug(group_name)
        lines_seen.setdefault(line_id, line_name)
        groups_seen.setdefault(group_id, (group_name, line_id))
        product_id = f"{r['product_code']}|{r['sub_product_code']}"
        if product_id in seen_products:
            continue
        seen_products.add(product_id)
        # The source hierarchy has no display-name column — the product code
        # pair IS the honest name (never invent one).
        products.append((product_id, r["product_code"], r["sub_product_code"],
                         f"{r['product_code']} {r['sub_product_code']}".strip(),
                         group_id, r["grid_type"] or "PRODUCT_TYPE"))

    classes = [
        {"class_id": "RECURRING", "class_name": "Recurring", "display_order": 1},
        {"class_id": "NON_RECURRING", "class_name": "Non-recurring", "display_order": 2},
    ]
    lines = [(lid, lname, "RECURRING" if lid in RECURRING_LINE_NAMES else "NON_RECURRING", i)
             for i, (lid, lname) in enumerate(sorted(lines_seen.items()), start=1)]
    groups = [(gid, gname, line_id, i)
              for i, (gid, (gname, line_id)) in enumerate(sorted(groups_seen.items()), start=1)]

    advisors = []
    for r in sorted(adv_rows, key=lambda x: x["advisor_sid"]):
        if not r["advisor_sid"]:
            fail("raw_advisor.csv has a row with blank advisor_sid")
        advisors.append({
            "advisor_sid": r["advisor_sid"],
            # Blank names -> display the advisor id; never invent names.
            "advisor_name": r["advisor_name"] or r["rr_nam"] or r["advisor_sid"],
            "rep_code": r["rep_code"],
            "branch_cd": r["branch_cd"],
            "standard_id": r["advisor_sid"],
        })
    return {"classes": classes, "lines": lines, "groups": groups,
            "products": products, "advisors": advisors}


def build_transactions(txn_rows: list[dict], reasons: dict[str, dict]) -> list[dict]:
    """Map raw extract rows into the same in-memory shape the sample
    generator's _mk_txn produces — the contract the shared builder consumes."""
    txns = []
    for i, r in enumerate(txn_rows):
        ctx_label = f"raw_revenue_transaction.csv row {i + 2}"  # 1-based + header
        if not r["trade_ref_no"] or not r["advisor_sid"]:
            fail(f"{ctx_label}: blank trade_ref_no or advisor_sid")
        month_id = r["month_id"] or (r["trade_dt"][:4] + r["trade_dt"][5:7])
        if not re.fullmatch(r"\d{6}", month_id):
            fail(f"{ctx_label}: month_id {month_id!r} is not YYYYMM (and trade_dt "
                 f"{r['trade_dt']!r} could not supply it)")
        reason_cd = elig.normalize_reason(r["reason_cd"])
        credited = _num(r["post_split_credited_amt"], context=f"{ctx_label} post_split_credited_amt")
        txns.append({
            "txn_id": f"{r['trade_ref_no']}|{r['split_seq_no'] or 1}",
            "trade_ref_no": r["trade_ref_no"],
            "split_seq_no": int(_num(r["split_seq_no"] or "1", context=f"{ctx_label} split_seq_no")),
            "advisor_sid": r["advisor_sid"],
            "month_id": month_id,
            "product_id": f"{r['product_cd']}|{r['product_sub_cd']}",
            "account_no": r["account_no"],
            "trade_dt": r["trade_dt"],
            "proc_dt": r["proc_dt"],
            # Credited revenue = post_split_credited_amt (pre_split x split_pct
            # double-counts across advisors — EXTRACTION_SPEC §1).
            "credited_amt": round(credited, 2),
            "pre_split_amt": round(_num(r["pre_split_credited_amt"], context=ctx_label), 2),
            "split_pct": _num(r["split_pct"], context=ctx_label),
            "client_rate_bps": _num(r["client_rate_bps"], context=ctx_label),
            "std_tier_rate": _num(r["std_tier_rate"], context=ctx_label),
            "concession_type": r["concession_type"] or "None",
            "discount_amt": round(_num(r["discount_amt"], context=ctx_label), 2),
            "eff_disc_pct": _num(r["eff_disc_pct"], context=ctx_label),
            "avg_balance_amt": _num(r["avg_balance_amt"], context=ctx_label),
            "file_key": r["file_key"],
            "trade_description": r["trade_description"],
            # rev_nature is DERIVED, not sourced (EXTRACTION_SPEC §4).
            "rev_nature": derive_rev_nature(r["file_key"], r["trade_description"]),
            "reason_cd": reason_cd,
            "rm_sid": r["rm_sid"],
            "cs_sid": r["cs_sid"],
            "revenue_eligibility": elig.reason_eligibility(reason_cd, reasons),
            "incentive_eligible": elig.incentive_eligible(reason_cd, reasons),
            "days_to_process": elig.days_to_process(r["trade_dt"], r["proc_dt"]),
            # posting_month_id = trade month — ASSUMED (R1-7): no iComp feed
            # identifies closed months, so no prior-period-adjustment logic.
            "posting_month_id": month_id,
            "data_source": "REAL",
        })
    return txns


def month_scope(txns: list[dict]) -> list[str]:
    """Distinct months, validated CONSECUTIVE — a gap would make compute_changes
    pair non-adjacent months and every 'MoM' figure would be wrong."""
    months = sorted({t["month_id"] for t in txns})
    if len(months) < 2:
        fail(f"only {months} in the extract — at least two consecutive months are "
             "needed to compute a month-over-month transition.")
    for a, b in zip(months, months[1:]):
        ya, ma, yb, mb = int(a[:4]), int(a[4:6]), int(b[:4]), int(b[4:6])
        if (ya * 12 + ma) + 1 != (yb * 12 + mb):
            fail(f"months in the extract are not consecutive: {a} -> {b}. Extract the "
                 "missing month(s) or restrict the date range.")
    return months


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default="data/real/_raw", type=Path,
                        help="directory holding the three raw extract CSVs (B1 contract)")
    parser.add_argument("--out", default="data/real", type=Path,
                        help="dataset output directory (vertices/ + edges/)")
    args = parser.parse_args(argv)

    txn_rows = read_raw(args.raw, "raw_revenue_transaction.csv")
    hier_rows = read_raw(args.raw, "raw_product_hierarchy.csv")
    adv_rows = read_raw(args.raw, "raw_advisor.csv")

    dims = build_dimensions(hier_rows, adv_rows)
    reasons = elig.reason_map()
    txns = build_transactions(txn_rows, reasons)

    # Referential checks — fail loudly, never drop rows silently.
    known_products = {p[0] for p in dims["products"]}
    unknown = sorted({t["product_id"] for t in txns} - known_products)
    if unknown:
        fail(f"transactions reference product(s) missing from raw_product_hierarchy.csv: "
             f"{unknown[:10]}{' …' if len(unknown) > 10 else ''} — re-run the hierarchy "
             "extract (it must cover every (product_cd, product_sub_cd) in the trade extract).")
    known_advisors = {a["advisor_sid"] for a in dims["advisors"]}
    orphan = sorted({t["advisor_sid"] for t in txns} - known_advisors)
    if orphan:
        fail(f"transactions reference advisor(s) missing from raw_advisor.csv: {orphan} — "
             "verify advisor_sid on the trade table equals standard_id (EXTRACTION_SPEC §3).")

    months = month_scope(txns)
    billable_days = {m["month_id"]: m["billable_days"] for m in month_rows(months)}

    accounts = [{"account_no": a, "account_typ": "", "wrap_flg": ""}
                for a in sorted({t["account_no"] for t in txns})]
    # account_typ / wrap_flg are NOT in the extracts — left blank, never invented.

    settings = get_settings()
    ctx = EligibilityContext(
        reasons=reasons,
        product_grid_type={p[0]: p[5] for p in dims["products"]},
        credited_grid_types=frozenset(settings.credited_grid_type_set),
        max_processing_days=int(settings.max_processing_days),
    )

    try:
        summary = build_dataset(
            out_dir=args.out, manifest_path=MANIFEST,
            month_ids=months, billable_days=billable_days,
            txns=txns, advisors=dims["advisors"], classes=dims["classes"],
            lines=dims["lines"], groups=dims["groups"], products=dims["products"],
            accounts=accounts, ctx=ctx,
        )
    except ReconciliationError as exc:
        # A real-data reconciliation failure is a STOP condition (B2.4): do not
        # load, do not generate commentary — investigate the discrepancy first.
        fail(str(exc))

    # ------------------------------------------------ summary (B2.7)
    print(f"\nBuilt {args.out} from {args.raw} — months {months[0]}..{months[-1]}, "
          f"{len(dims['advisors'])} advisors\n")
    print("Rows per file:")
    for fname, n in summary["counts"].items():
        print(f"  {fname:38s} {n:>7}")
    print("\nEligibility split:", summary["split_sizes"])
    print(f"OUT_OF_GRID rows (grid_type outside CREDITED_GRID_TYPES={settings.credited_grid_types}):",
          summary["out_of_grid_count"])
    print(f">{settings.max_processing_days}-day processing rows (LATE, in Total not Credited):",
          summary["late_count"])
    print("\nReconciliation: $0.00 on every transition ✓  (asserted — a failure aborts the build)")
    print("MIX share per transition (a large value means a named driver is missing):")
    for key, m in summary["mix_share"].items():
        print(f"  {key:28s} total change {m['total_change']:>14,.2f}   "
              f"MIX {m['mix_total']:>12,.2f}  ({m['mix_pct_of_change']:.2f}%)")
    print("\nNext steps: load via the ingestion screen with DATA_SET=real, then run the "
          "Regenerate workflow to create commentary + evidence (never generated here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
