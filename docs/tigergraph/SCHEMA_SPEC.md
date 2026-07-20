# TIGERGRAPH SCHEMA SPEC — iPerform V2

Graph name: **`iperform_v2_revenue`**
Prefix: **`phx_dm_v2_`** · 16 vertex types · 23 edge types

Deliverables (Phase 1):
- `docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql`
- `docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql`
- `docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql`
- `docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json` (typed attribute map,
  used by the ingestion upsert to cast values correctly)

**Every vertex carries `data_source STRING`** — one of `REAL`, `DERIVED`, `ASSUMED`,
`DUMMY`. It is returned by the API and displayed in the UI. No exceptions.

---

## 1. DIMENSIONS

### `phx_dm_v2_advisor` — REAL
The ten advisors in the demo set.
```
PRIMARY_ID advisor_sid STRING
advisor_name STRING      # from fpic_employee_tb.em_name_txt (may be blank -> show id)
rep_code STRING
branch_cd STRING
standard_id STRING
data_source STRING
```

### `phx_dm_v2_month` — DERIVED
One per calendar month in scope. `month_id` is `YYYYMM` as a string, e.g. `"202604"`.
```
PRIMARY_ID month_id STRING
year INT
month_no INT             # 1-12  (V1 had a bug where this was always 1 — populate it properly)
month_name STRING        # "April 2026"
quarter INT
start_dt DATETIME
end_dt DATETIME
calendar_days INT
billable_days INT        # business days; DERIVED — client may correct later
prior_month_id STRING    # "" for the first month in scope
index_return DOUBLE      # market return for the month. DUMMY until sourced.
is_current BOOL
data_source STRING
```
> `billable_days` is `DERIVED`; `index_return` is `DUMMY`. Where a month vertex mixes
> provenance, set `data_source = "DERIVED"` and let the driver-level flag carry the truth.

### `phx_dm_v2_revenue_class` — REAL
Two rows: `RECURRING`, `NON_RECURRING`.
```
PRIMARY_ID class_id STRING
class_name STRING        # "Recurring" / "Non-recurring"
display_order INT
data_source STRING
```

### `phx_dm_v2_product_line` — REAL
`level_one_product` from the client's product hierarchy (Managed, Trails, Annuities,
Structured Products, Alternative Investments, Fixed Income, Equities and Options,
Mutual Funds, Cash Management, Lending, Insurance, Referrals and Revenue Share,
Defined Contribution Advisory, Donor Advised Funds).
```
PRIMARY_ID line_id STRING       # slug of level_one_product
line_name STRING
display_order INT
data_source STRING
```

### `phx_dm_v2_product_group` — REAL
`level_two_product` — the drill-down level shown in the pivot (e.g. "Unified Managed
Account", "JPMCAP", "Advisory", "Structured Products", "Equities", "Options").
```
PRIMARY_ID group_id STRING      # slug of level_two_product
group_name STRING
display_order INT
data_source STRING
```

### `phx_dm_v2_product` — REAL
Leaf: the `(product_cd, sub_product_code)` pair from the source.
```
PRIMARY_ID product_id STRING    # "<product_cd>|<product_sub_cd>", e.g. "OISC|PMP"
product_cd STRING
product_sub_cd STRING
product_name STRING
data_source STRING
```

### `phx_dm_v2_account` — REAL
```
PRIMARY_ID account_no STRING
account_typ STRING
wrap_flg STRING
data_source STRING
```

### `phx_dm_v2_driver_cause` — REAL (reference data)
The controlled vocabulary of *why* revenue changed. Seeded, not extracted.

| cause_id | cause_name | Meaning | Typical provenance |
|---|---|---|---|
| `VOLUME` | Transaction volume | More/fewer transactions at similar rates | REAL |
| `ONE_TIME` | One-time items | Syndicate allocations, new issues, referrals that don't repeat | REAL |
| `TIMING` | Billing timing | Quarterly billing cycle falls in one month not the other | REAL |
| `FEE_RATE` | Effective fee rate | Change in `client_rate_bps` / `std_tier_rate` | REAL |
| `DISCOUNT` | Discounting | Change in `concession_type` / `discount_amt` / `eff_disc_pct` | REAL |
| `BILLABLE_DAYS` | Billable days | Different number of billing days between months | DERIVED |
| `MIX` | Product mix | Shift between products at different rates | DERIVED |
| `NEW_ACCOUNT` | Accounts opened | Accounts contributing this month but not last | REAL |
| `LOST_ACCOUNT` | Accounts closed | Accounts contributing last month but not this | REAL |
| `CLAWBACK` | Reversals | Negative credited amounts (chargebacks) | REAL |
| `MARKET` | Market performance | Asset value movement | DUMMY (needs index returns) |
| `NET_FLOW` | Net client flows | Inflows less outflows | DUMMY (flows feed stops Jan 2026) |

```
PRIMARY_ID cause_id STRING
cause_name STRING
cause_description STRING
default_data_source STRING
display_order INT
data_source STRING
```

---

## 2. FACTS

### `phx_dm_v2_revenue_transaction` — REAL
**Grain: one trade split.** This is what makes the clickable drill-down and the evidence
"source records" table possible. Do not aggregate it away.
```
PRIMARY_ID txn_id STRING        # "<trade_ref_no>|<split_seq_no>"
trade_ref_no STRING
split_seq_no INT
advisor_sid STRING
month_id STRING
product_id STRING
account_no STRING
trade_dt DATETIME
proc_dt DATETIME
credited_amt DOUBLE             # post_split_credited_amt — THE revenue figure
pre_split_amt DOUBLE
split_pct DOUBLE
client_rate_bps DOUBLE
std_tier_rate DOUBLE
concession_type STRING          # "None" / "Discount"
discount_amt DOUBLE
eff_disc_pct DOUBLE
avg_balance_amt DOUBLE          # 0 for Managed — see §5
file_key STRING                 # source feed: ace, twhs, l_a_ancomm, mf_12b1, manual_adj...
trade_description STRING        # "MONTH M04-2026" / "ANNUITY ISSUED ..." / "ADJUSTMENT ..."
rev_nature STRING               # RECURRING | ONE_TIME | ADJUSTMENT  (derived from file_key + description)
data_source STRING
```

### `phx_dm_v2_monthly_product_revenue` — DERIVED
The pivot cells. Pre-aggregated so the Trends screen is a lookup, not a scan.
```
PRIMARY_ID mpr_id STRING        # "<advisor_sid>|<month_id>|<group_id>"
advisor_sid STRING
month_id STRING
group_id STRING
line_id STRING
class_id STRING
revenue DOUBLE
txn_count INT
account_count INT
avg_rate_bps DOUBLE
recurring_amt DOUBLE
one_time_amt DOUBLE
data_source STRING
```

### `phx_dm_v2_account_month_balance` — **DUMMY**
Billable assets and effective fee per account per month. **No source data exists today**
(`avg_balance_amt` is 0% populated for Managed). Create the vertex and edges, load with
placeholder rows flagged `DUMMY`, and surface it as such. When the client provides billable
assets, this becomes REAL with no schema change.
```
PRIMARY_ID balance_id STRING    # "<account_no>|<month_id>"
account_no STRING
month_id STRING
avg_billable_assets DOUBLE
effective_fee_bps DOUBLE
billable_days INT
data_source STRING              # "DUMMY" until sourced
```

---

## 3. ANALYTICS

### `phx_dm_v2_revenue_change` — DERIVED
One per (advisor, month-transition, product group), plus a `__TOTAL__` group row per
transition carrying the headline number.
```
PRIMARY_ID change_id STRING     # "<advisor_sid>|<from_month>|<to_month>|<group_id>"
advisor_sid STRING
from_month_id STRING
to_month_id STRING
group_id STRING                 # "__TOTAL__" for the advisor-level headline
from_revenue DOUBLE
to_revenue DOUBLE
change_amt DOUBLE
change_pct DOUBLE
direction STRING                # UP | DOWN | FLAT
data_source STRING
```

### `phx_dm_v2_revenue_driver` — DERIVED
An attributed contribution to a change, classified by cause. Ranked by |contribution|.
```
PRIMARY_ID driver_id STRING     # "<change_id>|<cause_id>|<seq>"
change_id STRING
cause_id STRING
group_id STRING
contribution_amt DOUBLE
contribution_pct DOUBLE         # share of the transition's total change
direction STRING                # UP | DOWN
rank INT                        # 1 = largest absolute contribution
inputs_json STRING              # the numbers the attribution used (JSON) — feeds evidence
data_source STRING              # REAL | DERIVED | ASSUMED | DUMMY
```

### `phx_dm_v2_commentary_version` — DERIVED
```
PRIMARY_ID version_id STRING    # "v<version_no>"
version_no INT
generated_at DATETIME
model STRING
prompt_version STRING
data_snapshot_dt DATETIME
status STRING                   # DRAFT | PUBLISHED | SUPERSEDED
advisor_count INT
transition_count INT
blocked_count INT
notes STRING
data_source STRING
```

### `phx_dm_v2_commentary` — DERIVED
One per (version, advisor, transition).
```
PRIMARY_ID commentary_id STRING # "<version_id>|<advisor_sid>|<from_month>|<to_month>"
version_id STRING
advisor_sid STRING
from_month_id STRING
to_month_id STRING
headline STRING                 # "($90,685)  (17.7%)"
narrative_text STRING           # the prose paragraph for the table view
bullets_json STRING             # ordered bullets: {direction, title, text, cause_id, driver_id, data_source}
status STRING                   # PUBLISHED | BLOCKED
blocked_reason STRING
data_source STRING
```

### `phx_dm_v2_evidence` — DERIVED
One per driver. **A driver without evidence must not be published.**
```
PRIMARY_ID evidence_id STRING   # "<driver_id>|<version_id>"
driver_id STRING
finding_text STRING             # section 1 of the modal
calc_json STRING                # section 2: component rows + formula
source_records_json STRING      # section 3: sample txn rows + total count
lineage_json STRING             # section 4a: vertex path with match counts
checks_json STRING              # section 4b: automated checks and pass/fail
gsql_query_name STRING          # section 5: the query we ran
gsql_params_json STRING
gsql_result_json STRING
source_sql STRING               # PostgreSQL extraction SQL — lineage only, NOT executed live
source_table STRING
source_row_count INT
data_source STRING
```

---

## 4. EDGES

All directed, all with `REVERSE_EDGE`. Naming: `phx_dm_v2_<subject>_<relation>_<object>`.

**Hierarchy**
| Edge | From → To |
|---|---|
| `phx_dm_v2_product_in_group` | product → product_group |
| `phx_dm_v2_group_in_line` | product_group → product_line |
| `phx_dm_v2_line_in_class` | product_line → revenue_class |

**Transaction facts**
| Edge | From → To |
|---|---|
| `phx_dm_v2_txn_for_advisor` | revenue_transaction → advisor |
| `phx_dm_v2_txn_in_month` | revenue_transaction → month |
| `phx_dm_v2_txn_for_product` | revenue_transaction → product |
| `phx_dm_v2_txn_for_account` | revenue_transaction → account |

**Monthly aggregates**
| Edge | From → To |
|---|---|
| `phx_dm_v2_mpr_for_advisor` | monthly_product_revenue → advisor |
| `phx_dm_v2_mpr_in_month` | monthly_product_revenue → month |
| `phx_dm_v2_mpr_for_group` | monthly_product_revenue → product_group |

**Balances (dummy today)**
| Edge | From → To |
|---|---|
| `phx_dm_v2_balance_for_account` | account_month_balance → account |
| `phx_dm_v2_balance_in_month` | account_month_balance → month |

**Change & drivers**
| Edge | From → To |
|---|---|
| `phx_dm_v2_change_for_advisor` | revenue_change → advisor |
| `phx_dm_v2_change_for_group` | revenue_change → product_group |
| `phx_dm_v2_change_from_month` | revenue_change → month |
| `phx_dm_v2_change_to_month` | revenue_change → month |
| `phx_dm_v2_driver_of_change` | revenue_driver → revenue_change |
| `phx_dm_v2_driver_has_cause` | revenue_driver → driver_cause |
| `phx_dm_v2_driver_for_group` | revenue_driver → product_group |

**Commentary & evidence**
| Edge | From → To |
|---|---|
| `phx_dm_v2_commentary_for_advisor` | commentary → advisor |
| `phx_dm_v2_commentary_from_month` | commentary → month |
| `phx_dm_v2_commentary_to_month` | commentary → month |
| `phx_dm_v2_commentary_in_version` | commentary → commentary_version |
| `phx_dm_v2_commentary_cites_driver` | commentary → revenue_driver |
| `phx_dm_v2_evidence_for_driver` | evidence → revenue_driver |

---

## 5. PROVENANCE — the honest position

State this plainly in `BUILD_REPORT.md` and surface it in the UI.

| Capability | Status | Why |
|---|---|---|
| Revenue by product, per month | **REAL** | `post_split_credited_amt` + product hierarchy, both fully populated |
| MoM change $ and % | **REAL** | Arithmetic on real revenue |
| Volume, one-time, timing, clawback attribution | **REAL** | `file_key`, `trade_description`, transaction counts |
| Fee-rate and discount attribution | **REAL** | `client_rate_bps`, `concession_type`, `discount_amt`, `eff_disc_pct` |
| Billable-days effect | **DERIVED** | Business-day calendar computed by us; client can correct |
| Product-mix effect | **DERIVED** | Computed from real revenue and rates |
| New / lost account effect | **REAL** | Account presence per month, from transactions |
| **Billable-assets effect (Managed)** | **DUMMY** | `avg_balance_amt` is **0% populated** for Managed |
| **Market performance** | **DUMMY** | No index-return source |
| **Net client flows** | **DUMMY** | `fpic_daily_adv_flows_tb` stops at 2026-01-30 |

Balance-driven categories (Cash Management 98%, Annuities 97%, Lending 100%, Insurance 91%,
Donor Advised 98%) **do** have `avg_balance_amt`, so their asset effect can be REAL. Use it
there. Managed is the notable gap — show it as DUMMY rather than hiding it.

---

## 6. RULES

1. Ingest **only** the attributes above. The source table has ~130 columns; take these.
2. `month_id` is a **string** `"YYYYMM"`. Never an int, never a date.
3. Every vertex sets `data_source`. Never leave it blank.
4. Deletes must run edges-before-vertices and facts-before-dimensions — the ingestion
   screen's ordered delete depends on it.
5. `schema_catalog.json` must give every attribute's type so the upsert casts correctly
   (V1 hit REST-30200 errors from passing raw strings into INT/BOOL fields).
