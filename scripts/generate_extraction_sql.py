"""Regenerate docs/data/extraction/*.sql from docs/data/source_catalog.json.

FIX_SPEC R1-5 / R2-2 / R3: table names come from the source catalog, never
string literals, so they cannot drift between the SQL files and the evidence
builder. Run after any catalog change:
    python scripts/generate_extraction_sql.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.source_catalog import scope_advisors, table_name

OUT = Path("docs/data/extraction")

HEADER = (
    "-- GENERATED from docs/data/source_catalog.json by scripts/generate_extraction_sql.py\n"
    "-- (do not edit by hand — edit the catalog and regenerate).\n"
    "-- Source extraction (PostgreSQL, schema pcr, db fpicdb). Run by a human;\n"
    "-- output dropped as CSV into data/real/. NOT executed by the app — shown in\n"
    "-- the evidence modal for lineage and independent verification only.\n"
)


def advisors_in_list(indent: str) -> str:
    ids = scope_advisors()
    lines = []
    for i in range(0, len(ids), 5):
        lines.append(",".join(f"'{a}'" for a in ids[i:i + 5]))
    return f",\n{indent}".join(lines)


def revenue_transaction_sql() -> str:
    trade, hierarchy = table_name("trade_details"), table_name("product_hierarchy")
    return f"""{HEADER}-- Credited revenue = post_split_credited_amt (pre_split x split_pct double-counts across advisors).
-- Month comes from trade_dt (proc_dt runs the day after month-end; year_month_no is 2% populated).
-- R1-5: reason_cd / rm_sid / cs_sid / grid_type are PULLED AS COLUMNS. The grid_type
-- filter was deliberately REMOVED from the WHERE: eligibility (reason codes, grid
-- types, the 90-day rule) is applied by the application from phx_dm_v2_reason_code
-- data + config, never baked into the extract.
SELECT d.trade_ref_no, d.split_seq_no, d.advisor_sid,
       to_char(d.trade_dt,'YYYYMM')          AS month_id,
       d.product_cd, d.product_sub_cd, d.account_no,
       d.trade_dt, d.proc_dt,
       d.post_split_credited_amt, d.pre_split_credited_amt, d.split_pct,
       d.client_rate_bps, d.std_tier_rate,
       d.concession_type, d.discount_amt, d.eff_disc_pct,
       d.avg_balance_amt, d.file_key, d.trade_description,
       d.reason_cd, d.rm_sid, d.cs_sid,
       h.grid_type
FROM   {trade} d
JOIN   {hierarchy} h
       ON  d.product_cd     = h.product_code
       AND d.product_sub_cd = h.sub_product_code
WHERE  d.trade_dt >= DATE '2026-04-01'
  AND  d.trade_dt <  DATE '2026-07-01'
  AND  d.advisor_sid IN ({advisors_in_list(' ' * 25)});
"""


def product_hierarchy_sql() -> str:
    return f"""{HEADER}-- R1-4: grid_type is pulled as a COLUMN (PRODUCT_TYPE | NON_CREDITED_REVENUE |
-- PAY_TYPE_SUMMARY), no longer filtered here. The revenue computation filters on
-- CREDITED_GRID_TYPES config, so relaxing the filter needs no re-extract.
SELECT DISTINCT product_code, sub_product_code,
       level_two_product, level_one_product, grid_type,
       level_one_pay_type_product_cd, level_two_pay_type_product_cd
FROM   {table_name('product_hierarchy')};
"""


def advisor_sql() -> str:
    return f"""{HEADER}-- Verify advisor_sid on the trade table equals standard_id here; if not, fall
-- back to (prm_ofc_no, prm_rr_no). Blank names -> display the advisor id; never
-- invent names.
SELECT r.standard_id AS advisor_sid, r.rr_nam, r.prm_rr_no AS rep_code,
       r.cwm_branch_cd AS branch_cd, e.em_name_txt AS advisor_name
FROM   {table_name('advisor')} r
LEFT   JOIN {table_name('employee')} e ON e.em_standard_id = r.standard_id
WHERE  r.standard_id IN ({advisors_in_list(' ' * 24)});
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, sql in (
        ("extract_revenue_transaction.sql", revenue_transaction_sql()),
        ("extract_product_hierarchy.sql", product_hierarchy_sql()),
        ("extract_advisor.sql", advisor_sql()),
    ):
        (OUT / fname).write_text(sql, encoding="utf-8")
        print(f"wrote {OUT / fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
