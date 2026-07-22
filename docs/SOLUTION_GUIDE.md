# iPerform V2 — Solution Guide

**Revenue Trends & AI Commentary — how the system works, and how to defend it.**

Written for a reader who is smart but new to this system. Every worked example in this
guide uses real numbers from the shipped sample data set (`data/sample/`) — nothing is
invented. Where a value is an assumption or a placeholder, it says so.

Last updated: 2026-07-21 (Round 2 of the build, per `FIX_SPEC.md`).

---

## Chapter 1 — Overview

### What it answers

> **"What is driving the changes in my month-over-month credited revenue?"**

For a financial advisor, the app shows monthly **credited** revenue broken down by
product hierarchy, computes what drove each month-over-month change, narrates that in
plain business language, and can **prove every number** it shows, all the way back to
source records and a runnable query.

### Who it is for

Financial advisors (and the people reviewing on their behalf). Analysis is
**advisor-level only** — no region/market/MDW roll-ups, no household/client-level
analysis (though the model does not make roll-ups impossible later).

### What it is

- A **TigerGraph** temporal graph (`iperform_v2_revenue`, all types prefixed
  `phx_dm_v2_`), with an identical-shape **SQLite/local tier 2** fallback.
- A **FastAPI** backend on port **8001** (`/api/v2/...`).
- A **Next.js** frontend on port **3001**: Trends (pivot + MoM), AI Insights (chart,
  commentary cards, monthly walk), Transactions drill-down, Evidence modal, Data
  Ingestion, Environment Health.
- Data: three months (Apr/May/Jun 2026) for ten advisors, extracted from the client's
  PostgreSQL (`fpicdb`, schema `pcr`). The demo ships a deliberately synthetic sample
  set (3 advisors `SMPL001–003`) engineered so every driver cause is exercised.

### The two non-negotiable principles

1. **The LLM narrates; it never computes.** Every number anywhere in the UI comes from
   deterministic Python over graph data. The model only turns already-computed drivers
   into sentences, and a validation gate blocks any narrative containing a figure that
   is not in the computed driver set. All model-authored wording carries an
   "AI Generated" chip; computed figures never do.
2. **Every fact carries provenance.** `REAL` (client data), `DERIVED` (computed by us
   from real data), `ASSUMED` (uses a stated assumption), `DUMMY` (placeholder, no real
   data yet). The API returns the flag; the UI displays it. A DUMMY or ASSUMED value is
   never rendered as though it were real.

### What it deliberately does not do

No AGP/coaching/CRM/recommendations or any other V1 domain concept, no peer
benchmarking, no predictions or ML training, no what-if. Total and Non-Credited revenue
are computed and stored (the evidence needs them) but are **not** surfaced as screens or
headline figures in this round — the app shows **credited** revenue only (FIX_SPEC R1-9).

House formatting rule: negative numbers appear in parentheses — `($6,290.00)`,
`(45.63%)` — never with a minus sign. Everywhere: charts, tables, commentary, evidence.

---

## Chapter 2 — Business definitions (the client's vocabulary)

Source: the client's Confluence page **"Revenue Summary Data Mapping" (CWM PCR)** — the
authoritative definition of credited revenue. Everything in this chapter restates that
document; interpretations and assumptions we added are flagged as such.

### The four revenue measures

| Measure | Definition |
|---|---|
| **Total Revenue** | Σ `post_split_credited_amt`, regardless of reason code (EXCLUDED rows aside — see below) |
| **Credited Revenue** | Σ `post_split_credited_amt` where the reason code is **not** one of the ineligible codes (9E, 9G, 9C, 9S, 94), the product's grid type is a credited grid type, and the transaction was processed within 90 days |
| **Non-Credited Revenue** | Σ rows whose reason code is one of the ineligible codes (9E, 9G, 9C, 9S, 94). It is still revenue — it counts in Total — but not credited |
| **Adjusted Credited Revenue** | Credited Revenue ± prior-period adjustments (PPA). **The client's own document contradicts itself** — the Pay Type section says *minus* PPA, the Product Type section says *plus*. Unresolved; PPA is not implemented in this round (Chapter 10) |

The identity, verified per pivot cell by the end-to-end suite:

```
credited revenue = total_revenue − non_credited_amt − late_excluded_amt
```

### The reason-code table (seeded verbatim into `phx_dm_v2_reason_code`)

This is data, not code: the seed lives in `app/v2/revenue/eligibility.py`
(`REASON_CODE_SEED`) and is loaded into the graph like any other vertex. The credited
computation **reads** these rows — seeding a new code changes behaviour with no code
change. All 15 rows, `data_source=REAL` (from the client doc):

| reason_code | Description | UI mapping | Owned by | Eligibility | include_in_credited | incentive_eligible |
|---|---|---|---|---|---|---|
| `__NONE__` | No reason code — Grid transaction | Grid | PCE | CREDITED | true | true |
| `91` | Less than Minimum – Equity | Incentive non-eligible > Equity – below minimum | PCE | CREDITED | true | **false** |
| `92` | Less than Minimum – Mutual Fund | Incentive non-eligible > Mutual funds – below minimum | PCE | CREDITED | true | **false** |
| `9L` | Full Month LOA | Incentive non-eligible > LOA | iComp | CREDITED | true | **false** |
| `9E` | Minimum Household Policy | Small households | PCE | NON_CREDITED | false | false |
| `9G` | Inherited Account | Transferred accounts | PCE | NON_CREDITED | false | false |
| `9C` | Personal Transactions | Personal accounts | PCE | NON_CREDITED | false | false |
| `9S` | Account Block – Supervision | Other | PCE | NON_CREDITED | false | false |
| `94` | Account Block – Other | Other | PCE | NON_CREDITED | false | false |
| `9R` | Rep Code Not Found | *(not displayed)* | PCE | EXCLUDED | false | false |
| `98` | Sales After Termination | *(not displayed)* | iComp | EXCLUDED | false | false |
| `99` | Sales During Inactive Period | *(not displayed)* | iComp | EXCLUDED | false | false |
| `9H` | Sales Before Rep Code Assignment | *(not displayed)* | iComp | EXCLUDED | false | false |
| `9X` | A delete of the transaction | *(not displayed)* | PCE | EXCLUDED | false | false |
| `XX` | Transaction removed by the SOR for Annuities | *(not displayed)* | PCE | EXCLUDED | false | false |

Three eligibility states, deliberately:

- **CREDITED** — counts in credited revenue (subject to the grid and 90-day rules).
- **NON_CREDITED** — revenue, but not credited (9E, 9G, 9C, 9S, 94). In Total, out of
  Credited.
- **EXCLUDED** — **not revenue at all**; appears in no total (9R, 98, 99, 9H, 9X, XX).
  The client doc names only two states; EXCLUDED is **our interpretation** of the codes
  with "no UI mapping" (recorded in `BUILD_REPORT.md` as an interpretation to confirm).

Two more classification buckets the app derives on top (they are not reason-code
states):

- **LATE** — otherwise-credited rows with `days_to_process > 90`. In Total, out of
  Credited, tracked as `late_excluded_amt`.
- **OUT_OF_GRID** — the product's `grid_type` is not in the credited-grid config.
  Outside every figure under the current config.

An **unknown** reason code (not in the table) defaults to NON_CREDITED — the honest
default: never credit revenue we cannot classify, but keep it in Total.

**Assumption flagged for client re-confirmation:** 91/92/9L are treated as **credited**
revenue that is merely *incentive-ineligible* (they count in credited revenue but
`incentive_eligible=false`).

### Grid types

Each product row in `pcr.product_hierarchy` carries a `grid_type`:
`PRODUCT_TYPE` | `NON_CREDITED_REVENUE` | `PAY_TYPE_SUMMARY`. Since Round 2 it is
**stored as a product attribute, not filtered at extraction**. The credited computation
filters on `CREDITED_GRID_TYPES` config (default `PRODUCT_TYPE`), so the filter can be
relaxed without touching SQL or re-extracting. Verified during the Round-2 build:
adding a grid type to the config changed a drill-down credited total from 16,640.00 to
36,640.00 with zero code change.

### The 90-day rule

From the client doc: *"transactions older than 90 days should be ignored as these
transactions will not be sent to iComp."* Implemented as
`days_to_process = proc_dt − trade_dt` (in days), compared against
`MAX_PROCESSING_DAYS` config (default 90).

Worked example (sample data, real row): `SMPLTRD00138`, advisor SMPL003, UMA fee of
$900.00, `trade_dt` 2026-04-02, `proc_dt` 2026-07-11 → `days_to_process = 100` →
classified **LATE**: the $900.00 stays in April's Total revenue but is out of Credited,
carried as `late_excluded_amt`.

### The credited-revenue formula (FIX_SPEC R1-6)

```
credited_revenue = Σ post_split_credited_amt
  WHERE reason_code.include_in_credited = TRUE     -- read from the graph vertex, never hardcoded
    AND product.grid_type IN CREDITED_GRID_TYPES   -- config, default ['PRODUCT_TYPE']
    AND days_to_process <= MAX_PROCESSING_DAYS     -- config, default 90
```

Implementation: `app/v2/revenue/eligibility.py` (`classify()`), driven by
`app/config/settings.py` (`CREDITED_GRID_TYPES`, `MAX_PROCESSING_DAYS`).

---

## Chapter 3 — Data lineage (source → column → vertex attribute)

Single source of truth: **`docs/data/source_catalog.json`** (FIX_SPEC R3). The three
extraction SQL files in `docs/data/extraction/` are **generated** from it
(`scripts/generate_extraction_sql.py`), and the evidence builder reads table names from
it — no PostgreSQL table name appears as a literal in Python. Source system:
PostgreSQL, database `fpicdb`, schema `pcr` (a production dump used for demo
development). Scope: `2026-04-01 <= trade_dt < 2026-07-01`, ten named advisors.

### `pcr.fpic_daily_trade_details_tb_prod` → `phx_dm_v2_revenue_transaction`

Grain: one row per trade split (`trade_ref_no` + `split_seq_no`).

| Source column | Vertex attribute | Note |
|---|---|---|
| `trade_ref_no` | `trade_ref_no` | |
| `split_seq_no` | `split_seq_no` | |
| `advisor_sid` | `advisor_sid` | |
| `trade_dt` | `trade_dt` | revenue month = `to_char(trade_dt,'YYYYMM')`; `year_month_no` is only ~2% populated — cross-check only |
| `proc_dt` | `proc_dt` | `days_to_process = proc_dt − trade_dt` feeds the 90-day rule |
| `product_cd` + `product_sub_cd` | `product_id` | composite key into the product hierarchy |
| `account_no` | `account_no` | |
| `post_split_credited_amt` | `credited_amt` | **the revenue base field** (`pre_split × split_pct` would double-count across advisors) |
| `pre_split_credited_amt` | `pre_split_amt` | |
| `split_pct` | `split_pct` | |
| `client_rate_bps` | `client_rate_bps` | FEE_RATE driver input |
| `std_tier_rate` | `std_tier_rate` | |
| `concession_type` | `concession_type` | DISCOUNT driver input |
| `discount_amt` | `discount_amt` | DISCOUNT driver input |
| `eff_disc_pct` | `eff_disc_pct` | |
| `avg_balance_amt` | `avg_balance_amt` | 0% populated for Managed — why the balance vertex is DUMMY |
| `file_key` | `file_key` | `rev_nature` is DERIVED from `file_key` + `trade_description` |
| `trade_description` | `trade_description` | |
| `reason_cd` | `reason_cd` | Round 2: drives credited eligibility via `phx_dm_v2_reason_code`; null/blank maps to `__NONE__` |
| `rm_sid` | `rm_sid` | |
| `cs_sid` | `cs_sid` | |

Derived at build time on the same vertex (not sourced): `rev_nature`,
`revenue_eligibility`, `incentive_eligible`, `days_to_process`, and
`posting_month_id` (= trade month, **ASSUMED** — see Chapter 10).

### `pcr.product_hierarchy` → product hierarchy vertices

Grain: one row per (`product_code`, `sub_product_code`, `grid_type`).

| Source column | Vertex attribute |
|---|---|
| `product_code` | `phx_dm_v2_product.product_cd` |
| `sub_product_code` | `phx_dm_v2_product.product_sub_cd` |
| `level_two_product` | `phx_dm_v2_product_group.group_name` |
| `level_one_product` | `phx_dm_v2_product_line.line_name` |
| `grid_type` | `phx_dm_v2_product.grid_type` — pulled as a **column**, not filtered at extraction (R1-4) |
| `level_one/two_pay_type_product_cd` | reference only, not loaded |

### `pcr.fpic_prm_rr_tb` → `phx_dm_v2_advisor`

| Source column | Vertex attribute | Note |
|---|---|---|
| `standard_id` | `advisor_sid` | verify equals `trade_details.advisor_sid`; fall back to (`prm_ofc_no`, `prm_rr_no`) if not |
| `prm_rr_no` | `rep_code` | |
| `cwm_branch_cd` | `branch_cd` | |

### `pcr.fpic_employee_tb` → advisor name

`em_standard_id` joins to `fpic_prm_rr_tb.standard_id`; `em_name_txt` →
`advisor_name` (may be blank → the UI shows the advisor id; names are never invented).

The reason-code reference itself is sourced from the Confluence doc, not from a table
(`reason_codes_source` field of the catalog).

The extraction SQL header records the rest of the lineage rules: the extract is run by a
human against PostgreSQL, dropped as CSV, and **never executed by the app** — the SQL is
shown in the evidence modal for lineage and independent verification only.

---

## Chapter 4 — Graph schema (18 vertices, 27 edges)

Graph `iperform_v2_revenue`, prefix `phx_dm_v2_`. Every vertex carries
`data_source STRING` (REAL | DERIVED | ASSUMED | DUMMY). DDL:
`docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql`, `02_edges.gsql`,
`03_create_graph.gsql`; `schema_catalog.json` is **generated from the DDL**
(`scripts/generate_schema_artifacts.py`) so it cannot drift.

### Vertices

**Dimensions (loaded from extracts or seeded reference data):**

| Vertex | Purpose / key attributes | Provenance | Populated by |
|---|---|---|---|
| `phx_dm_v2_advisor` | advisor identity: `advisor_sid` (PK), `advisor_name`, `rep_code`, `branch_cd`, `standard_id` | REAL | advisor + employee extracts |
| `phx_dm_v2_month` | calendar month: `month_id` "YYYYMM" (PK, STRING), `calendar_days`, `billable_days`, `prior_month_id`, `index_return`, `is_current` | DERIVED (`billable_days` DERIVED — Mon–Fri count, no holiday calendar; `index_return` DUMMY) | generated from the date scope |
| `phx_dm_v2_revenue_class` | two rows: RECURRING, NON_RECURRING | REAL (seeded) | seed |
| `phx_dm_v2_product_line` | `level_one_product` (Managed, Trails, Structured Products, …) | REAL | product-hierarchy extract |
| `phx_dm_v2_product_group` | `level_two_product` — the pivot drill-down level | REAL | product-hierarchy extract |
| `phx_dm_v2_product` | leaf: (`product_cd`, `product_sub_cd`), `product_name`, **`grid_type`** (R1-4, stored not filtered) | REAL | product-hierarchy extract |
| `phx_dm_v2_account` | `account_no`, `account_typ`, `wrap_flg` | REAL | derived from transaction rows |
| `phx_dm_v2_driver_cause` | controlled vocabulary of the 13 causes with descriptions and `default_data_source` | REAL (seeded) | seed |
| `phx_dm_v2_reason_code` | the 15-row eligibility table of Chapter 2: `eligibility`, `include_in_credited`, `incentive_eligible`, `ui_mapping`, `owned_by` | REAL (seeded from the client doc) | seed (`eligibility.py`) |

**Facts:**

| Vertex | Purpose | Provenance | Populated by |
|---|---|---|---|
| `phx_dm_v2_revenue_transaction` | one row per trade split — the drill-down and evidence source-record grain. All Chapter-3 columns plus derived `rev_nature`, `reason_cd`, `revenue_eligibility`, `incentive_eligible`, `days_to_process`, `posting_month_id` | REAL (derived columns computed from real fields; `posting_month_id` ASSUMED) | trade-details extract |
| `phx_dm_v2_monthly_product_revenue` | pre-aggregated pivot cell per (advisor, month, group): `revenue` (**credited**), `txn_count`, `account_count`, `avg_rate_bps`, `recurring_amt`, `one_time_amt`, plus the client's breakdown `total_revenue` / `non_credited_amt` / `excluded_amt` / `late_excluded_amt` | DERIVED | `app/v2/revenue/aggregation.py` |
| `phx_dm_v2_account_month_balance` | billable assets per account/month (`avg_billable_assets`, `effective_fee_bps`, `billable_days`) | **DUMMY** — no billable-assets source (`avg_balance_amt` 0% populated for Managed) | zero-valued structural rows |

**Analytics (all DERIVED, produced by the deterministic pipeline):**

| Vertex | Purpose |
|---|---|
| `phx_dm_v2_revenue_change` | one per (advisor, transition, group) + a `__TOTAL__` row per transition: `from_revenue`, `to_revenue`, `change_amt`, `change_pct`, `direction` |
| `phx_dm_v2_revenue_driver` | an attributed contribution to a change: `cause_id`, `contribution_amt`, `contribution_pct`, `direction`, `rank`, `inputs_json` (every number the attribution used), per-driver `data_source` REAL/DERIVED/DUMMY by cause |
| `phx_dm_v2_commentary_version` | one per batch generation run: `version_no`, `generated_at`, `model`, `prompt_version`, `status` (DRAFT/PUBLISHED/SUPERSEDED), `blocked_count` |
| `phx_dm_v2_commentary` | one per (version, advisor, transition): `headline`, `narrative_text`, `bullets_json`, `status` (PUBLISHED/BLOCKED), `blocked_reason` |
| `phx_dm_v2_commentary_evaluation` | LLM-as-judge review of one commentary (R5): `judge_model`, `faithfulness_score`, `hallucination_flag`, `completeness_score`, `clarity_score`, `verdict` (PASS/REVIEW/FAIL), `reasoning`. **Advisory only** |
| `phx_dm_v2_evidence` | one per driver per version: the full five-section evidence record — `finding_text`, `calc_json`, `source_records_json`, `lineage_json`, `checks_json`, `gsql_query_name/params/result`, `source_sql`, `source_table`, `source_row_count` |

### Edges (27, all directed, all with reverse edges)

| Area | Edges |
|---|---|
| Product hierarchy | `product_in_group`, `group_in_line`, `line_in_class` |
| Transaction | `txn_for_advisor`, `txn_in_month`, `txn_for_product`, `txn_for_account`, **`txn_has_reason`** (→ reason_code, R1-2) |
| Monthly aggregate | `mpr_for_advisor`, `mpr_in_month`, `mpr_for_group` |
| Balance (DUMMY) | `balance_for_account`, `balance_in_month` |
| Change | `change_for_advisor`, `change_for_group`, `change_from_month`, `change_to_month` |
| Driver | `driver_of_change`, `driver_has_cause`, `driver_for_group` |
| Commentary | `commentary_for_advisor`, `commentary_from_month`, `commentary_to_month`, `commentary_in_version`, `commentary_cites_driver` |
| Evidence / judge | `evidence_for_driver`, `evaluation_of_commentary` |

---

## Chapter 5 — Query reference (GQ-001..GQ-017)

Every `run_query(name, …)` in the codebase names a query in
`docs/tigergraph_foundation/tigergraph/queries/query_catalog.json`. Each has a GSQL
file (parse-verified, `status: created-v2-NEEDS-LIVE-INSTALL` — none is installed on a
live TigerGraph yet) **and** an identical-shape local-tier implementation in
`app/graph/queries/v2.py`, so tier-2 results genuinely prove tier-1 behaviour. Both
tiers return `{"error": False, "results": [...], "mode": ..., "served_by_tier": 1|2}`
with vertex rows shaped `{"v_id", "v_type", "attributes": {...}}`.

| ID | Name | Parameters | Purpose | Output shape | Consumers |
|---|---|---|---|---|---|
| GQ-001 | `get_advisors` | — | advisor picker | `advisors`: vset rows | advisor context bar, `GET /reference/advisors` |
| GQ-002 | `get_months` | — | months in scope, ordered, with `prior_month_id`, `billable_days` | `months`: vset rows | period controls, `GET /reference/months` |
| GQ-003 | `get_product_hierarchy` | — | class → line → group → product with display order | 4 vsets with `@parent_id` | Trends pivot rows, `GET /reference/product-hierarchy` |
| GQ-004 | `get_driver_causes` | — | the cause vocabulary | `causes`: vset rows | AI Insights legend, `GET /reference/driver-causes` |
| GQ-005 | `get_monthly_revenue_by_product` | `advisor_id`, `from_month`, `to_month` (STRING) | monthly **credited** revenue by group | `monthly_revenue`: vset rows | `GET /api/v2/trends/revenue` |
| GQ-006 | `get_monthly_revenue_totals` | `advisor_id`, `from_month`, `to_month` | per-month totals for the stacked bar chart | one object of month→value maps | `GET /api/v2/insights/chart`; evidence §5 for `__TOTAL__` drivers |
| GQ-007 | `get_revenue_changes` | `advisor_id`, `from_month`, `to_month` | every `revenue_change` incl. `__TOTAL__` rows | `changes`: vset rows | `GET /api/v2/trends/changes` |
| GQ-008 | `get_change_drivers` | `advisor_id`, `from_month`, `to_month`, `result_limit` (INT) | drivers for one transition, ranked by \|contribution\| | `drivers`: vset rows | `GET /api/v2/insights/drivers` |
| GQ-009 | `get_commentary` | `advisor_id`, `version_id` (`''` = latest PUBLISHED) | stored commentary rows | `commentaries` + `resolved_version` | `GET /api/v2/insights/commentary` |
| GQ-010 | `get_commentary_versions` | — | all versions, newest first | `versions`: vset rows | version selector, `GET /api/v2/insights/versions` |
| GQ-011 | `get_product_revenue_change` | `advisor_id`, `product_group`, `from_month`, `to_month` | from/to revenue + change + txn count for one group — **the evidence modal's runnable reproduction query** | one object `{from_revenue, to_revenue, change, txn_count}` | evidence modal §5, `GET /api/v2/evidence/reproduce` |
| GQ-012 | `get_evidence` | `driver_id`, `version_id` (`''` = all versions) | full evidence record | `evidence`: vset rows | evidence modal, `GET /api/v2/evidence` |
| GQ-013 | `get_transactions` | `advisor_id`, `month_id`, `group_id` (`''` = all), `result_limit` | drill-down rows | `transactions`: vset + `@group_id`, `@product_name` | `GET /api/v2/transactions` |
| GQ-014 | `get_ingestion_counts` | — | per V2 vertex type: count + data_source mix | one object: `counts`, `source_mix` | ingestion screen, env-health, `GET /api/v2/ops/counts` |
| GQ-015 | `get_advisor_month_summary` | `advisor_id` | per month: revenue, txns, products, accounts (from the transaction grain) | one object of maps | context bar, reconciliation checks, `GET /api/v2/ops/advisor-summary` |
| GQ-016 | `get_reason_codes` | — | the eligibility reference (Round 2) — data-driven, never hardcoded | `reason_codes` ordered by `display_order` | `GET /api/v2/reference/reason-codes`, drill-down credited classification |
| GQ-017 | `get_commentary_evaluations` | `version_id` | judge evaluations per version (R5) — advisory only | `evaluations`: vset rows | `GET /api/v2/insights/evaluations`, evidence modal "Independent review" |

---

## Chapter 6 — Calculation reference (the most important chapter)

Everything here is **pure deterministic Python** — `app/v2/revenue/aggregation.py` and
`app/v2/drivers/attribution.py`. No LLM touches any of it.

### 6.1 The pipeline

1. **Classify** every transaction (Chapter 2): CREDITED / NON_CREDITED / EXCLUDED /
   LATE / OUT_OF_GRID.
2. **Aggregate** CREDITED rows into `monthly_product_revenue` per (advisor, month,
   product group), carrying the total/non-credited/excluded/late breakdown alongside.
3. **Compute changes**: per (advisor, consecutive month pair, group),
   `change_amt = to_revenue − from_revenue`, plus one `__TOTAL__` row per transition.
   `change_pct = change/from×100`; when `from = 0` the UI shows "n/a", never a division.
4. **Attribute** each group change to causes (below).
5. **Reconcile** independently: Σ driver contributions per transition must equal the
   `__TOTAL__` change within $1.00.

### 6.2 The running worked example: SMPL001, May → June 2026

From `data/sample/vertices/revenue_change.csv` (real stored rows):

```
Total credited revenue   May 2026:  $65,182.42
Total credited revenue   Jun 2026:  $35,437.14
Change:                            ($29,745.28)   (45.63%)  DOWN
```

The stored drivers for this transition (`revenue_driver.csv`), ranked by |contribution|:

| Rank | Group | Cause | Contribution | Provenance |
|---|---|---|---|---|
| 1 | structured_products | ONE_TIME | ($36,600.00) | REAL |
| 2 | alternative_investments | TIMING | $7,000.00 | REAL |
| 3 | unified_managed_account | **ELIGIBILITY** | **($6,290.00)** | REAL |
| 4 | unified_managed_account | NEW_ACCOUNT | $4,450.00 | REAL |
| 5 | unified_managed_account | BILLABLE_DAYS | $840.00 | DERIVED |
| 6 | equities | VOLUME | $737.63 | REAL |
| 7 | mutual_fund_trails | CLAWBACK | ($435.00) | REAL |
| 8 | equities | MIX | $224.82 | DERIVED |
| 9 | jpmcap | BILLABLE_DAYS | $181.82 | DERIVED |
| 10 | advisory | BILLABLE_DAYS | $145.45 | DERIVED |
| 11 | mutual_fund_trails | BILLABLE_DAYS | $102.38 | DERIVED |
| 12 | mutual_fund_trails | MIX | ($102.38) | DERIVED |
| 13 | `__TOTAL__` | MARKET | $0.00 | DUMMY |
| 14 | `__TOTAL__` | NET_FLOW | $0.00 | DUMMY |

Sum of contributions: **($29,745.28)** — exactly the total change. Discrepancy $0.00.

### 6.3 The 14-step attribution order, and why order matters

Per group, steps run in this fixed order (`attribute_group()`); each step **claims**
part of the change and **removes its transactions from all later steps**:

```
 1. NEW_ACCOUNT / LOST_ACCOUNT      (advisor-level account presence)
 2. ONE_TIME                        (rev_nature ONE_TIME delta)
 3. ELIGIBILITY                     (credited <-> non-credited movement)   [Round 2]
 4. LATE_PROCESSING                 (90-day-rule movement, -(Δ late-excluded)) [Round 3]
 5. EXCLUDED_CHANGE                 (credited <-> excluded movement, e.g. 9X)  [Round 3]
 6. CLAWBACK                        (negative-amount rows delta)
 7. TIMING                          (quarterly-billed group in one month only)
 8. FEE_RATE                        (effective bps movement on the remaining base)
 9. DISCOUNT                        (discounting delta on the remainder)
10. BILLABLE_DAYS                   (recurring groups; business-day count)
11. VOLUME                          (transaction-count effect, non-recurring groups)
12. MARKET                          (DUMMY placeholder, $0.00)
13. NET_FLOW                        (DUMMY placeholder, $0.00)
14. MIX                             (the remainder)
```

**The Revenue-Driver glossary is the client-facing form of this list** — the UI's
"What do these mean?" popup and this chapter share one source
(`frontend/components/patterns/revenue-driver-glossary.tsx`): every driver's display
name, plain-English meaning, and how it is computed. Round 3 guarantees every
subtrahend of the credited identity has a named driver (`credited = in-scope total −
non-credited − late-excluded`, with EXCLUDED outside every figure and OUT_OF_GRID
static by construction), and a self-check WARNs whenever |MIX| exceeds 15% of a
transition's change — a large residual means a driver is missing, not "product mix".

Why this matters, in three sentences:

- **Sequential consumption prevents double-counting.** Once a lost account's rows are
  claimed by LOST_ACCOUNT, they cannot also appear in the ONE_TIME or VOLUME deltas;
  once one-time rows are claimed, the fee-rate step only sees the recurring base.
  Ordering runs from the most specific, most factual explanations (an account that
  literally disappeared) to the most residual.
- **MIX reconciles by construction.** `MIX = change_amt − Σ(all attributed causes)`;
  whatever the earlier steps did not explain lands there, labelled honestly as residual
  product-mix movement (DERIVED), so contributions always sum to the change.
- **An independent check still runs.** `reconcile()` recomputes
  Σ contributions vs the `__TOTAL__` change per transition from *stored* data
  (tolerance $1.00) — construction is not trusted on its own; ABSOLUTE RULE 7 is
  verified separately, and `/api/v2/ops/reconciliation` re-verifies it at any time.

The evidence modal's "attribution order" panel shows for any driver *which step it was*
and *what earlier steps had already claimed* — the direct answer to "how do you know
you're not double-counting?".

### 6.4 The 13 causes, one by one

Every worked example below is a real stored driver row from
`data/sample/vertices/revenue_driver.csv`; the inputs shown are its `inputs_json`.

---

**1. NEW_ACCOUNT** — REAL — *"Accounts contributed this month that did not contribute
last month."*

- **Rule:** account presence is judged **at the advisor level**, not per product group,
  and counts credited **and** non-credited activity. An account that merely switches
  products, or whose rows became non-credited, is still trading — that is product
  behaviour or an eligibility move, not a new/lost account.
- **Formula:** `Σ credited_amt (this month) of accounts new to the advisor`.
- **Worked example** (SMPL001 May→Jun, unified_managed_account): account
  `SMPLACCT-1109` first contributes in June — 1 transaction, $4,450.00 →
  contribution **$4,450.00**.
- **Why competing causes are rejected:** these rows are removed before ONE_TIME,
  FEE_RATE, VOLUME etc. run, so a new account's revenue cannot be re-explained as a
  volume or rate effect. Evaluating presence at advisor level stops a mere
  product-switch from being miscounted as an account opening.

**2. LOST_ACCOUNT** — REAL — *"Accounts that contributed last month did not contribute
this month."*

- **Rule:** mirror of NEW_ACCOUNT, advisor-level presence including non-credited rows.
- **Formula:** `−(Σ credited_amt (last month) of accounts gone from the advisor)`.
- **Worked example** (SMPL001 Apr→May, unified_managed_account): account
  `SMPLACCT-1104` stops after April — $6,420.00 of April revenue → contribution
  **($6,420.00)**. For SMPL003 Apr→May the same account (`SMPLACCT-3104`) produces two
  LOST_ACCOUNT drivers, ($7,820.00) in UMA and ($7,400.00) in annuities — the account
  is judged once at advisor level, then its revenue is attributed per group.
- **Rejection of competitors:** because presence counts non-credited activity, a
  household whose rows went 9E is **not** a lost account — it flows to ELIGIBILITY
  (see below), which is the true business story.

**3. ONE_TIME** — REAL — *"One-time items in one month did not repeat in the other."*

- **Rule:** among rows not already claimed, compare revenue with
  `rev_nature = ONE_TIME` (derived from `file_key` + `trade_description` — Chapter 6.5).
- **Formula:** `to_one_time − from_one_time`.
- **Worked example** (SMPL001 Apr→May, structured_products): 3 syndicate rows with
  `file_key "twhs"` land in May only — from $0, to $36,600.00 → contribution
  **$36,600.00** (and the mirror ($36,600.00) in May→Jun when they don't repeat).
- **Rejection of competitors:** without this step, a syndicate allocation would corrupt
  VOLUME (txn counts) or FEE_RATE (weighted bps) for the month it lands in. It runs
  before them and consumes its rows.

**4. ELIGIBILITY** — REAL — *(Round 2, FIX_SPEC R1-8)* — *"Revenue moved between
credited and non-credited reason codes month over month."*

- **Rule:** the group's NON_CREDITED transactions (9E small households, 9G transferred
  accounts, …) are tracked alongside the credited ones. If non-credited revenue rises,
  credited revenue fell by that amount, and vice versa. Accounts already claimed by
  NEW/LOST_ACCOUNT are excluded.
- **Formula:** `−(to_non_credited − from_non_credited)`.
- **Worked example** (SMPL001 May→Jun, unified_managed_account): account
  `SMPLACCT-1103`'s UMA fee — transaction `SMPLTRD00040`, $6,290.00 — carries reason
  code **9E (Minimum Household Policy, "Small households")** in June. Inputs:
  `from_non_credited = 0`, `to_non_credited = 6,290.00`, `reason_codes = ["9E"]` →
  contribution **($6,290.00)**. The household crossed the minimum-household threshold;
  its revenue still exists (June UMA `total_revenue` is $22,930.00) but left the
  credited figure ($16,640.00).
- **Rejection of competitors:** the account still trades, so it is *not* LOST_ACCOUNT
  (advisor presence counts non-credited activity precisely for this reason); the rows
  are recurring fees, so not ONE_TIME; and by claiming the movement here it never
  reaches MIX as an unexplained residual.
- **Known approximation (Chapter 10):** the formula is the *net Δ of non-credited
  revenue*, per the spec — a change in the size of already-non-credited revenue,
  without any boundary crossing, also lands here (offset in MIX).

**5. CLAWBACK** — REAL — *"Reversal (negative) amounts changed between the months."*

- **Rule:** among remaining rows, compare the totals of negative-`credited_amt` rows.
- **Formula:** `to_negative_total − from_negative_total`.
- **Worked example** (SMPL001 May→Jun, mutual_fund_trails): May reversals ($295.00)
  across 2 rows; June ($730.00) across 4 rows → contribution
  `(−730.00) − (−295.00)` = **($435.00)**.
- **Rejection of competitors:** negative rows are then removed, so reversals cannot
  distort the FEE_RATE weighting or the VOLUME average-transaction-value that follow.

**6. TIMING** — REAL — *"Quarterly billing fell in only one month of the pair."*

- **Rule:** for groups known to bill quarterly (`QUARTERLY_BILLED_GROUPS`, currently
  alternative_investments), if the remaining rows exist in exactly one of the two
  months, the whole remaining swing is billing timing.
- **Formula:** `to_revenue − from_revenue` (of the remainder), then both sides are
  consumed.
- **Worked example** (SMPL001 Apr→May, alternative_investments): April bills $7,000.00,
  May bills nothing → contribution **($7,000.00)**; Apr and Jun bill, May doesn't, so
  May→Jun shows the mirror **$7,000.00**.
- **Rejection of competitors:** without this step a quarterly cycle would read as
  revenue appearing/disappearing (VOLUME or MIX). It only fires on the
  all-or-nothing pattern in a known quarterly group — a partial decline in a quarterly
  group falls through to the later steps instead.

**7. FEE_RATE** — REAL — *"The effective fee rate on the recurring base moved."*

- **Rule:** on the rows still remaining (recurring base), compare the
  revenue-weighted `client_rate_bps` between months; requires a positive rate on both
  sides.
- **Formula:** `assets_proxy × (to_avg_rate_bps − from_avg_rate_bps) / 10000`, where
  `assets_proxy = from_revenue / (from_avg_rate_bps/10000)` — the asset base implied by
  last month's revenue at last month's rate.
- **Worked example** (SMPL002 May→Jun, unified_managed_account): rate steps 82.0 →
  88.0 bps on a from-revenue of $19,644.54 → `assets_proxy = 2,395,675.61` →
  `2,395,675.61 × 6 / 10000` = **$1,437.41**.
- **Rejection of competitors:** it runs after one-time/clawback/new-account rows are
  gone, so the bps comparison is genuinely like-for-like on the recurring base. It is a
  proxy (implied assets, not true balances — those are the DUMMY balance vertex);
  the implied-assets growth portion falls to MIX rather than being overstated here.

**8. DISCOUNT** — REAL — *"Discounting changed between the months."*

- **Rule:** compare total `discount_amt` on the remaining rows (row counts of
  `concession_type = "Discount"` are recorded as context).
- **Formula:** `from_discount_total − to_discount_total` (growth in discounting reduces
  revenue, hence the reversed sign).
- **Worked example** (SMPL003 May→Jun, unified_managed_account): May has no discounts;
  June has 2 discount rows totalling $1,798.80 → contribution
  `0 − 1,798.80` = **($1,798.80)**.
- **Rejection of competitors:** measured on the surviving recurring rows only, so a
  discount on a one-time item (already consumed) cannot be counted twice.

**9. BILLABLE_DAYS** — **DERIVED** — *"The months have a different number of billable
days."*

- **Rule:** recurring-class groups only (lines Managed + Trails). Business-day counts
  come from the month vertex (Mon–Fri; **no holiday calendar** — the client may
  correct): Apr 2026 = 22, May = 21, Jun = 22.
- **Formula:** `from_revenue × (to_days − from_days) / from_days` on the remaining
  rows.
- **Worked example** (SMPL001 Apr→May, unified_managed_account):
  `18,480.00 × (21 − 22) / 22` = **($840.00)** — one fewer billing day in May. (The
  $18,480.00 base is April UMA revenue after the lost account `SMPLACCT-1104`'s
  $6,420.00 was consumed by step 1: 24,900.00 − 6,420.00.)
- **Rejection of competitors:** flagged DERIVED because it is a pro-rata model, not a
  sourced fact; it applies only to fee-accruing (recurring) groups — transaction
  groups get VOLUME instead.

**10. VOLUME** — REAL — *"Transaction volume changed at broadly similar rates."*

- **Rule:** non-recurring-class groups only. If the remaining transaction count moved,
  value the count change at last month's average transaction value.
- **Formula:** `(to_txn_count − from_txn_count) × from_avg_txn_value`.
- **Worked example** (SMPL001 Apr→May, equities): 8 trades → 5 trades at an April
  average of $137.47 → `(5 − 8) × 137.47` = **($412.41)**. The May→Jun mirror: 5 → 11
  trades × $122.94 = **$737.63**.
- **Rejection of competitors:** runs almost last, so the count only reflects ordinary
  trades — new/lost-account rows, one-time items and reversals were consumed earlier.
  The price/size component of the swing (not the count component) falls to MIX.

**11. MARKET** — **DUMMY** — *"Market performance effect."*

- No index-return source exists (`month.index_return` is 0.0). Emitted once per
  transition on the `__TOTAL__` row with **contribution $0.00** and
  `reason: "no index-return source"`, so the gap stays visible with its DUMMY badge
  instead of silently disappearing. **No attribution formula is written** — see
  Chapter 10.

**12. NET_FLOW** — **DUMMY** — *"Net client flows."*

- The flows feed (`fpic_daily_adv_flows_tb`) stops 2026-01-30. Same treatment:
  $0.00 on `__TOTAL__`, `reason: "flows feed stops 2026-01-30"`, DUMMY badge.

**13. MIX** — **DERIVED** — *"Residual movement from shifts between products at
different rates."*

- **Formula:** `change_amt − Σ(all attributed causes)` for the group.
- **Worked example** (SMPL001 May→Jun, mutual_fund_trails): group change ($435.00);
  claimed so far: CLAWBACK ($435.00) + BILLABLE_DAYS $102.38 = ($332.62); MIX =
  `(435.00) − (332.62)` = **($102.38)**.
- **Why it exists:** it is the honest name for "everything the specific models above
  did not explain" — and it is what makes the decomposition reconcile *by
  construction*. A large MIX is a signal the earlier models are missing something; in
  the sample set MIX rows are small (largest: $224.82).

### 6.5 `rev_nature` derivation (feeds ONE_TIME)

`rev_nature` is **derived, not sourced** (`derive_rev_nature()` in `aggregation.py`):

- `trade_description` starts with "ADJUSTMENT", or `file_key = manual_adj` → **ADJUSTMENT**
- `file_key` ∈ {`twhs`, `l_a_ancomm`, `pb_rfrrl`, `refrl_401k`, `sitn_ptnr`}, or
  description starts "ANNUITY ISSUED" → **ONE_TIME**
- otherwise (incl. `ace`, `mf_12b1`, `l_a_btr`, `529_trails`, `money_mkt`, `prem_dep`,
  `sbl_prcing`, `mrgn_lend`) → **RECURRING**

In monthly aggregates, `one_time_amt` includes ADJUSTMENT so
`recurring_amt + one_time_amt = credited revenue` always. The evidence modal shows the
actual `file_key`/`trade_description` values behind a classification (R4-4).

### 6.6 The credited breakdown, in the client's own vocabulary (R4-5)

For SMPL001, June 2026, unified_managed_account (stored `monthly_product_revenue` row):

```
Total revenue                    $22,930.00
less non-credited                ($6,290.00)   9E Minimum Household Policy × 1
less late (>90 days)                  $0.00
= Credited revenue               $16,640.00
```

(EXCLUDED rows — e.g. SMPL003's 9X deleted trade of $500.00 in May — appear in **no**
line of this breakdown; they are not revenue at all, tracked only as `excluded_amt`
for visibility.)

---

## Chapter 7 — Agent architecture

### The story to lead with: the deterministic gate caught a real model misbehaving

During Phase-5 tuning, the guardrail gate **caught the writer model doing arithmetic**:
in generation runs v2–v4 it summed figures across drivers ("$14.9k") and formed
figures by truncation. Those transitions were **BLOCKED and published as blocked, with
the reason shown plainly in the UI** — exactly as designed (see `BUILD_REPORT.md`
Phase 5; the v2–v4 rows in `commentary_version.csv` still show `blocked_count = 2`).
That is the primary control: a deterministic, code-level gate between the model and
publication. The LLM-as-judge (below) is a **second, advisory layer** on top — not the
control itself.

### The four agents (`app/agents/nodes/`)

| Agent | LLM? | Role |
|---|---|---|
| `supervisor_agent` | no | Orchestration. Workflow A (generation, batch/offline): per advisor × transition, sequences revenue_agent → commentary_agent → explainability_agent → guardrails validation. Workflow B (read, online): **retrieval only** — never invokes the commentary agent; missing commentary returns an empty state telling the user to run generation |
| `revenue_agent` | no | Deterministic: assembles the transition's changes, drivers, inputs and reconciliation status (`analyze_transition`) |
| `commentary_agent` | **the only LLM user** | Receives the computed drivers as JSON with every figure **pre-formatted by code** (`($44.1k)`, `(17.7%)`); writes language only — one explanation sentence per bullet and the narrative paragraph. The system prompt forbids introducing, adjusting or combining numbers. If output can't be parsed, deterministic fallback sentences from the cause vocabulary are used — figures are never affected either way. `PROMPT_VERSION = "v1.0"` |
| `explainability_agent` | no | Assembles the complete five-section evidence record per driver. The reproduction GSQL is **actually run** and its result stored verbatim; the PostgreSQL SQL is attached lineage-only |

### The guardrail gate — five blocking checks (`app/guardrails/numeric_validation.py`)

Deliberately **not** an agent. Runs between commentary and publication; failure
persists the transition as **BLOCKED** with the reason — never discarded, never
silently omitted.

1. **No invented figures** — every numeric token in the narrative/bullets must match a
   value in the computed driver set (transition totals, contributions, every numeric in
   `inputs_json`). Tolerance $1.01 plain / $55 for `$44.1k`-form; years, YYYYMM ids and
   identifier-embedded digits (account/trade refs) are whitelisted as non-figures.
2. **Reconciliation** — the transition must reconcile (residual ≤ $1.00).
3. **Evidence completeness** — every driver cited by a bullet must have a complete
   evidence record.
4. **Provenance honesty** — a DUMMY/ASSUMED driver may not be presented as fact.
5. **Negative-number format** — parentheses, never minus signs.

Negative tests confirm each check blocks. Current published version **v7** (Round 2
regeneration with deepened evidence and the first judge run): 6/6 transitions
published, 0 blocked, 86 evidence records, reconciliation $0.00 everywhere, judge
verdicts 6× PASS.

### The LLM-as-judge — advisory second layer (Round 2, FIX_SPEC R5)

Deterministic checks catch invented numbers; they cannot catch a narrative that cites
correct figures but *characterises* them wrongly (e.g. calling a one-time windfall
"steady growth"). The judge fills that gap:

- Runs **after** generation, on a **different model** than the writer
  (`JUDGE_MODEL` setting, default `claude-sonnet-5`, vs the writer's
  `claude-haiku-4-5`; `app/llm/client.py` supports the model override).
- Sees the driver set and the narrative; scores **faithfulness**, **hallucination**,
  **completeness**, **clarity**; returns a verdict **PASS | REVIEW | FAIL** with its
  reasoning.
- Stored on `phx_dm_v2_commentary_evaluation` (edge `evaluation_of_commentary`),
  queryable via GQ-017; surfaced in the evidence modal as an "Independent review"
  line and as a card badge when the verdict is not PASS.
- **Advisory, never blocking.** The judge cannot publish or suppress anything — the
  deterministic gate remains the only gate. A FAIL verdict flags a human, full stop.

The first judge run shipped with version **v7**: 6 evaluations stored (one per
transition), all PASS, `judge_model=claude-sonnet-5` vs writer
`claude-haiku-4-5-20251001` — visible in the evidence modal's "Independent review"
line.

### Batch generation and versioning

Commentary is generated **once, stored, and retrieved** (`COMMENTARY_MODE=stored`) —
never on page load. Each run of `app/v2/commentary/generation_workflow.py` creates a
new `commentary_version` (v1, v2, …), generates for every advisor × transition
(parallel across advisors, serial within one), persists commentary + evidence attached
to that version, publishes it and marks the prior PUBLISHED version SUPERSEDED.
**Regeneration is additive** — previous versions are never deleted and stay selectable
in the UI version picker (v1–v6 remain queryable alongside v7). Persistence is dual:
graph upsert + append to the data-set CSVs, so stored commentary survives a local-mode
restart.

---

## Chapter 8 — Evidence model

Every driver has one `phx_dm_v2_evidence` record per version — a driver without
complete evidence must not be published (guardrail check 3 enforces it). The evidence
modal renders five sections plus the Round-2 additions:

| Section | What it proves | Where it comes from |
|---|---|---|
| **1. Finding** | The claim in one sentence: group, contribution, % of total change, cause. Wording template is code; the sentence carries an "AI Generated" chip only where model-authored | `finding_text` — assembled deterministically by `explainability_agent` |
| **2. Calculation** | The arithmetic: component rows (from → to → change) taken verbatim from the attribution's `inputs_json`, plus the formula string. Since R2-1 every component carries a **`unit`** (currency \| count \| percent \| bps \| days) inferred from the key name — a txn count can never render as dollars, and only currency components sum into totals | `calc_json` |
| **3. Source records** | The underlying trade rows: a sample of the contributing transactions (trade ref, date, product, account, nature, credited amount) and the total contributing count | `source_records_json` — pulled live from the transaction grain at assembly time |
| **4. Lineage & checks** | The graph path advisor → transaction → monthly_product_revenue → revenue_change → revenue_driver with match counts, plus automated checks (reconciliation, figures-traced-to-source, coverage, product mapping) | `lineage_json`, `checks_json` |
| **5. Reproduce this result** | A **runnable GSQL query** (GQ-011, or GQ-006 for `__TOTAL__` drivers) with its exact parameters — and the result it returned when it was **actually executed** during evidence assembly, stored verbatim. The e2e suite re-runs a sample and byte-compares | `gsql_query_name/params/result_json` |

**The run-GSQL vs lineage-SQL distinction — worth stating precisely.** Section 5's
GSQL **was run by this application** against the graph, and its stored result can be
re-run and compared at any time. The PostgreSQL block is the opposite: the extraction
SQL from `docs/data/extraction/` (generated from the source catalog, with this
driver's real parameters substituted, and `source_table` read from the catalog — never
a literal), attached **"lineage only — not executed by this application"** so a
reviewer can independently verify against the source system. One is proof of
reproduction; the other is a map back to the system of record.

**Round-2 additions (FIX_SPEC R4):**

- **Why this cause** — the rule in plain words, the inputs tested, and why competing
  causes were rejected (Chapter 6.4's logic, sourced from the attribution code so it
  cannot drift). E.g. for NEW_ACCOUNT: evaluated at advisor level so a product switch
  is not miscounted as a new account.
- **Attribution order** — this driver was step *n* of 12, and what earlier steps had
  already claimed (the double-counting answer).
- **Reconciliation waterfall** — from-revenue → each driver contribution →
  to-revenue, summing exactly; one picture proving nothing is missing or
  double-counted ($65,182.42 → … → $35,437.14 for the running example).
- **`rev_nature` derivation** — the actual `file_key`/`trade_description` values that
  classified the rows (Chapter 6.5).
- **Credited-revenue breakdown** — Total, less non-credited (with reason codes and
  counts), less excluded, = Credited (Chapter 6.6) — the client's own definition in
  their own vocabulary, fed by the stored
  `total_revenue/non_credited_amt/excluded_amt/late_excluded_amt` columns.
- **Independent review** — the judge's verdict, faithfulness score and reasoning
  (Chapter 7), marked "AI Generated".

---

## Chapter 9 — Operations runbook

### 9.1 Environment & modes (`.env`)

```
GRAPH_CLIENT_MODE = real | local     # real = TigerGraph (tier 1); local = SQLite/in-memory (tier 2)
LLM_CLIENT_MODE   = claude | mock    # (client env also supports cdao_openai / azure)
DATA_SET          = sample | real    # which CSV set the ingestion screen loads
COMMENTARY_MODE   = stored           # never generate on read
CREDITED_GRID_TYPES = PRODUCT_TYPE   # comma-separated; relaxing it needs no code change
MAX_PROCESSING_DAYS = 90
JUDGE_MODEL       = claude-sonnet-5  # must differ from the writer model
```

Backend: `./scripts/run_api.sh` (uvicorn, port **8001**). Frontend: `npm run dev` in
`frontend/` (port **3001**, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001`).

Fallback is logged, never silent: in real mode, a query TigerGraph does not serve
falls back to the local store with a WARNING, and the env-health screen / tier pill go
**RED** whenever the local tier serves while `GRAPH_CLIENT_MODE=real`.

### 9.2 Install schema + queries on live TigerGraph

1. Run, in order, against TigerGraph 4.2.x:
   `docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql`,
   `02_edges.gsql`, `03_create_graph.gsql` (graph `iperform_v2_revenue`).
2. Install all queries:
   `docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql`.
   Every GQ file is flagged `created-v2-NEEDS-LIVE-INSTALL` — parse-verified here,
   **never yet installed on a live TigerGraph**.
3. Set `GRAPH_CLIENT_MODE=real` + the `TG_*` connection env vars.

### 9.3 Extract real data

1. Run the three generated extraction SQL files in `docs/data/extraction/`
   (`extract_advisor.sql`, `extract_product_hierarchy.sql`,
   `extract_revenue_transaction.sql`) against PostgreSQL `pcr`. If the scope (months,
   advisor list) changes, edit `docs/data/source_catalog.json` and regenerate with
   `scripts/generate_extraction_sql.py` — do not hand-edit the SQL.
2. Verify `advisor_sid` on the trade table equals `standard_id` in `fpic_prm_rr_tb`;
   fall back to (`prm_ofc_no`, `prm_rr_no`) if not.
3. Drop the output CSVs into `data/real/` matching the manifest column headers
   (`docs/tigergraph_foundation/data/manifest.json`, 45 files, dependency-ordered).
4. Set `DATA_SET=real`.

> **Flag — derived CSVs for the real set.** The manifest also loads the DERIVED
> entities (`monthly_product_revenue`, `revenue_change`, `revenue_driver`, months,
> reason codes, edges). For the sample set these are produced by
> `scripts/generate_sample_data.py`, which runs the same `app/v2` aggregation and
> attribution code the app uses — but that script is **sample-only** (it also invents
> the synthetic transactions). **There is currently no ready-made script that takes
> real extracted transaction CSVs and produces the derived CSVs for `data/real/`.**
> One must be written (a thin wrapper over `aggregate_monthly` / `compute_changes` /
> `attribute_transition` + the edge writers) before a real-data load; the maths must
> be the same app code, never a re-implementation.

### 9.4 Load via the ingestion screen

Data Ingestion screen (or `POST /api/v2-foundation/ingestion/run-all`): loads every
manifest entity **in dependency order**, with polling status, per-entity provenance
badges and a three-way count reconciliation (manifest vs store vs API). Checkpoints
are cleared on delete so a stale checkpoint can never suppress a re-load.

### 9.5 Generate commentary — the Regenerate button is the only trigger

**A fresh environment has no commentary until generation is run.** Page loads
retrieve stored commentary only; the AI Insights screen shows an explicit empty state
("No commentary generated for this advisor yet. Run generation to create a version.")
until then. The **only** trigger is the Regenerate button on AI Insights
(`POST /api/v2/insights/generate`; poll `/api/v2/insights/generate/status`). Each run
creates a new version; prior versions are never deleted. For real narrative text set
`LLM_CLIENT_MODE=claude` + key; `mock` produces deterministic sentences through the
identical pipeline and gate.

### 9.6 Verify

- **Env-health screen** — true serving tier per subsystem; must show
  TigerGraph · tier 1 green in real mode. RED means the local store is serving in
  real mode — investigate before trusting anything else.
- **`GET /api/v2/ops/reconciliation`** — recomputes Σ driver contributions vs the
  stored `__TOTAL__` change for every transition; expect discrepancy $0.00
  (tolerance $1.00) on all.
- **`python scripts/verify_end_to_end.py`** (fresh process): reconciliation per
  transition, evidence completeness for every driver, cited-driver resolution,
  exactly one PUBLISHED version, stored GSQL results byte-identical to live re-runs,
  `data_source` set on every vertex, all causes exercised. Expect `OVERALL: PASS`.
- `python scripts/validate_v2_queries.py` — catalog ↔ file ↔ installer ↔ impl ↔ case
  consistency.

### 9.7 Ordered delete / reload

`GET /api/v2-foundation/ingestion/delete-plan` shows the real dependency-ordered
plan (reverse of load order; the confirm dialog displays it), then
`POST .../delete-all` executes it; individual entities via `POST /delete/{entity}`.
Reload with run-all. Caveat on live TigerGraph: RESTPP/pyTigerGraph cannot bulk-delete
edges — edges disappear when their endpoint vertices are deleted; the delete report
says so rather than pretending. The pyTigerGraph delete paths have been exercised only
against the local tier (client-machine follow-up).

---

## Chapter 10 — Known gaps, assumptions and roadmap

Nothing here is hidden in the UI: DUMMY/ASSUMED badges, $0.00 placeholder drivers and
blocked-state notices surface each item where it occurs. This chapter is the complete
list a reviewer or the client must know.

### 10.1 DUMMY items are structure without maths

`phx_dm_v2_account_month_balance`, and the **MARKET** and **NET_FLOW** causes, have
vertices, edges, seeds and zero-valued rows — but **no attribution formulas are
written**. Supplying the data is necessary but **not sufficient**: the maths must be
designed and built. What each needs:

- **account_month_balance** — a billable-assets-per-account-month feed
  (`avg_balance_amt` is 0% populated for Managed in the source). With it, FEE_RATE's
  `assets_proxy` becomes true assets and a real balance-effect driver becomes possible.
- **MARKET** — an index-return source per month (`month.index_return`), plus a model
  attributing balance movement × rate to market performance, and its interaction with
  NET_FLOW.
- **NET_FLOW** — a flows feed (the client's `fpic_daily_adv_flows_tb` stops
  2026-01-30), plus the companion decomposition of balance change into flows vs
  market.

**Honest effort estimate:** roughly 1–2 weeks each of engineering *after* the data
exists — the harder half is agreeing the decomposition model (market vs flow vs rate on
a shared balance base must itself reconcile) with the client, plus re-testing the whole
attribution order so the new steps consume rows without disturbing the existing
causes. Call it 3–5 weeks for all three as a package, dominated by
definition-and-validation, not code.

### 10.2 iComp megadata — open question for the client

The client uses Trade Details for **open** periods and the iComp megadata table for
**closed** periods. We use Trade Details only. If Apr–Jun 2026 are closed periods, the
sanctioned source for those months may differ from what we extracted. Needs a client
answer before real-data sign-off.

### 10.3 Adjusted Credited Revenue — the client doc contradicts itself

Adjusted Credited = Credited ± PPA: the Pay Type section of the client document says
**minus** PPA, the Product Type section says **plus**. Unresolvable from our side;
needs the client to state the sign convention before Adjusted Credited is surfaced.

### 10.4 Prior-period adjustments are not implemented

`posting_month_id` = trade month, `data_source=ASSUMED`, with the stated reason:
prior-period adjustments post to the `proc_dt` month, and we cannot identify closed
months without the iComp feed. The structure is ready; the assumption is visible on
every transaction row.

### 10.5 91/92/9L treated as credited — assumption to confirm

Treated as credited revenue that is merely incentive-ineligible
(`include_in_credited=true`, `incentive_eligible=false`). Client-confirmed for now;
flagged for written re-confirmation.

### 10.6 Recurring vs non-recurring = Managed + Trails — assumption to confirm

The RECURRING class covers product lines Managed and Trails (everything else
NON_RECURRING), **inferred from the client mockup**, not from a stated rule. It drives
which groups get BILLABLE_DAYS vs VOLUME treatment, so a correction would shift those
attributions.

### 10.7 Partial-June risk

June may be a partial month in a real extract. The correct response is to **label** it
(the month vertex has `is_current`) rather than let the commentary narrate a data
artefact as a business decline. The sample set is complete months.

### 10.8 NULL-advisor bucket — firm totals will not tie

The client extraction excludes a **~$30.5M** bucket of rows with NULL `advisor_sid`
(per EXTRACTION_SPEC). Advisor-level figures are unaffected, but any attempt to tie
the app's totals to firm-level revenue will be off by that bucket. State it up front
in any review.

### 10.9 No automated test suite

Verification is by the two scripts (`verify_end_to_end.py`,
`validate_v2_queries.py`), negative guardrail tests and screenshot comparison — there
is no pytest/CI suite. Regressions rely on re-running the verification scripts
manually.

### 10.10 Unmeasured performance at real volume

Everything has run against 3 advisors × 3 months (213 transactions in the sample
set). Ten advisors of real data is still small, but query latency, evidence-assembly
time and generation wall-clock at genuine client volumes are unmeasured.

### 10.11 Round-2-specific interpretations (recorded, to confirm)

- **EXCLUDED third eligibility state** — the client doc names only two states
  (credited / non-credited). We read "no UI mapping" as "not revenue at all" and
  created the third state so those rows appear in **no** total. Interpretation, not
  client-stated fact.
- **Unknown reason codes default to NON_CREDITED** — any code not in the 15-row table
  stays in Total but out of Credited. The honest default: never credit revenue we
  cannot classify.
- **ELIGIBILITY = −(Δ non-credited), per spec** — the driver measures the *net change*
  in the group's non-credited revenue, which is exactly right when revenue crosses the
  credited/non-credited boundary (the 9E worked example). But a change in the *size*
  of revenue that was already non-credited in both months — no boundary crossing —
  also moves the delta, and will show as an ELIGIBILITY entry offset by an opposite
  MIX entry. Steady non-credited revenue (e.g. SMPL002's 9G inherited-account trail,
  present in all three months) correctly produces no driver. A finer formula would
  track per-account eligibility transitions; deferred.
