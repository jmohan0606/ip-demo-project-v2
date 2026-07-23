# BUILD REPORT — iPerform V2: Revenue Trends & AI Commentary

Build date: 2026-07-20 · Built autonomously per CLAUDE.md. Status: **COMPLETE** — all seven phases done; Definition of Done met (see §2 Phase 7).
**Round 2 (2026-07-21): corrections & enhancements per FIX_SPEC.md — see §8.**

---

## 1. Summary

A standalone web application answering *"What is driving the changes in my
month-over-month credited revenue?"* — TigerGraph temporal graph schema +
FastAPI backend (port 8001) + Next.js frontend (port 3001), with deterministic
driver attribution, LLM-narrated (never LLM-computed) commentary, versioned
batch generation, and full per-driver evidence back to source records and a
runnable query.

### Commit list (ordered)
| Hash | What |
|---|---|
| 2fd53f9 | Phase 0 — repair imports, V2 nav, ports 3001/8001 |
| d15b6b6 | Phase 1 — V2 schema (16 vertices, 25 edges) + schema_catalog.json |
| 8d440ab | Phase 2 — GQ-001..015, catalog, installer, local-tier impls, validator |
| b89cf88 | Phase 3 — extraction SQL, sample data, manifest, loading job, delete capability |
| 3bd6ced | Phase 4 — V2 services, /api/v2 router, reconciliation, typed coercion |
| fac5dfc | Phase 5 — four agents, guardrails gate, batch workflow + versioning |
| 1b73430 | Phase 6 — V2 shell, tokens, context bar, tier pill |
| 8508b58 | Phase 6 — Trends screen (pivot + MoM change) |
| e30e174 | Phase 6 — AI Insights (chart, commentary cards, monthly walk) |
| 123acc5 | Phase 6 — evidence modal + transactions drill-down |
| 6a15498 | Phase 6 — ingestion + env-health screens |
| e99499f | Phase 7 — verification suite + this report |

### Parallelisation actually used
- Phases 0–5 ran serially on the main thread (tight data dependencies; the
  sample data's derived CSVs are produced by the Phase-4 computation code, so
  Phase 3 and 4 were interleaved deliberately — recorded in PROGRESS.md).
- Phase 6: shell built serially, then **four parallel subagents**: Trends page ·
  AI Insights (chart + cards + walk table) · Evidence modal + Transactions ·
  Ingestion + Env-health. Subagents did not commit; main thread reviewed,
  verified and committed.

### Deliberately deferred / not built
- Revenue overview screen — stub with an explicit "not in this build" empty
  state (UI_SPEC §2 says Phase 2).
- Region/market roll-ups, household level, ML — out of scope by spec.

---

## 2. Per phase

### Phase 0 — Make it build
Pruned V1 baseline had dangling imports in ~10 backend modules and 8 frontend
files. Repaired: `app/api/main.py` trimmed to retained routers; minimal
`AdapterStatusService`/`RuntimeStatusService`/`TigerGraphFoundationService`
recreated; `app/feature_store/sqlite_manager.py` recreated for checkpoints;
env-health lost its Chroma/embedding probes (V2 has neither); V1-only pattern
components deleted. Ports set across all four touchpoints. Also fixed a latent
crash the import-scan missed at first: `app/graph/queries/__init__.py` imported
nine deleted V1 modules — it now registers only the V2 implementations.
**Verified:** `uvicorn` clean on 8001, `next dev` clean on 3001, all six routes 200.

### Phase 1 — Schema
16 vertex types, 25 edge types (SCHEMA_SPEC's header says 23 but its own edge
tables enumerate 25 — the tables won; recorded in PROGRESS.md decisions), graph
`iperform_v2_revenue`, prefix `phx_dm_v2_`. `schema_catalog.json` generated
programmatically from the DDL so the typed attribute map cannot drift from it.
**Verified:** catalog counts, prefix compliance via the foundation service.

### Phase 2 — Queries
GQ-001..GQ-015 authored per QUERY_SPEC syntax rules; catalogued
(`status: created-v2-NEEDS-LIVE-INSTALL`), installer + `tests/query_cases.json`.
Identical-shape local-tier implementations in `app/graph/queries/v2.py`.
**Verified:** `scripts/validate_v2_queries.py` — type-first params, USE GRAPH,
SYNTAX V1, INSTALL QUERY, one-hop-per-SELECT, every vertex/edge reference exists
in the schema catalog, catalog↔file↔installer↔impl↔case consistency: ALL PASS.
Every query then executed against the sample data via the local tier.

### Phase 3 — Extraction & ingestion
Extraction SQL stored (lineage-only; the app never executes PostgreSQL).
Sample data: 3 advisors (SMPL001–003, obviously synthetic) × Apr–Jun 2026,
205 transactions engineered so **all 12 driver causes** are exercised, derived
CSVs computed by the same Phase-4 code the app uses. Manifest (41 files) in
dependency order; GSQL loading job generated from the schema catalog. Delete
capability added to the client interface on every tier (local store, RESTPP,
pyTigerGraph, tiered dispatch) with checkpoint clearing so stale checkpoints
can never suppress a re-load.
**Verified:** run-all 41 entities → delete-all (2,218 rows, dependency order) →
reload, all clean over the API.

### Phase 4 — Computation
`app/v2/revenue/aggregation.py` (monthly aggregation, MoM change; string
month_ids enforced) and `app/v2/drivers/attribution.py` (11-step sequential
cause attribution; MIX absorbs the remainder so contributions reconcile by
construction; independent `reconcile()` check). Read services + `/api/v2`
router. A store-level typed-coercion fix keeps `month_id` a STRING end to end.
**Verified:** every endpoint smoke-tested; `/api/v2/ops/reconciliation`
recomputes Σ drivers vs `__TOTAL__` change from *stored* graph data — all
transitions reconcile at $0.00 discrepancy (tolerance $1).

### Phase 5 — Agents & commentary
Four agents on the retained framework: `supervisor` (declarative routing;
generation sequence; retrieval-only read), `revenue_agent` (deterministic),
`commentary_agent` (the only LLM user — receives pre-formatted computed figures,
writes language only, deterministic fallback), `explainability_agent`
(five-section evidence; the reproduction GSQL is **actually run** and its result
stored; PostgreSQL SQL attached lineage-only). Guardrails gate
(`app/guardrails/numeric_validation.py`): five blocking checks.
Batch workflow: new version per run, PUBLISHED/SUPERSEDED lifecycle, blocked
commentary persisted with its reason, dual persistence (graph upsert + data-set
CSV append) so stored commentary survives a local-mode restart.
**Verified:** five generation runs (v1–v5). The gate genuinely caught real LLM
misbehaviour during tuning: derived arithmetic ("$14.9k" summed across drivers)
and figures formed by truncation — those runs published with BLOCKED transitions
shown plainly, exactly as specified. v5: 6/6 transitions published, 0 blocked,
85 evidence records. Negative tests confirm invented figures, minus signs and
missing evidence each block.

### Phase 6 — UI
Shell (navy top nav, Results sub-nav, sample-data banner, advisor context bar
with persisted selection, honest tier pill — RED on real-mode-local-serve) +
v2 design tokens + one shared formatter. Five screens built by four parallel
subagents against the reference PNGs, then verified on the main thread in
headless Chromium against the live sample-data backend:
- Trends: hierarchical pivot + MoM change (clickable leaves → Transactions,
  n/a on zero base, ≥15% pills).
- AI Insights: stacked chart with MoM connector arrows/pills, one commentary
  card per transition (ranked bullets, provenance badges, cause tags, BLOCKED
  notices, version selector, Regenerate as the only LLM path), monthly walk
  table with the baseline-month note.
- Evidence modal: all five sections including the actually-run GSQL with its
  stored result and the lineage-only PostgreSQL block; Esc/overlay close with
  focus return.
- Transactions: filter chips, sortable columns, pagination, API-computed
  credited total (the pivot-cell equality).
- Ingestion + env-health: manifest table with provenance badges, run-all with
  polling, ordered delete-all with the real plan in the confirm dialog,
  three-way count reconciliation.
**Verified:** every screen screenshot-compared to its reference; ZERO browser
console errors across all five screens; evidence modal opened/closed via
keyboard. Fixes applied during review: split_pct rendered as percent; dollar
vs count components separated in the modal's calculation totals.

### Phase 7 — Verification
`scripts/verify_end_to_end.py` (run on a FRESH process so everything reloads
from disk): reconciliation per advisor/transition all $0.00 · every one of the
85 drivers has a complete latest-version evidence record (425 records total,
all sections populated) · all cited drivers resolve · 6/6 transitions
PUBLISHED, exactly one PUBLISHED version · stored GSQL results byte-identical
to live reruns (10 sampled, 0 mismatches) · data_source set on all 1,022
vertices · all 12 causes exercised. `scripts/validate_v2_queries.py` ALL PASS.
OVERALL: PASS.

---

## 3. Schema inventory (provenance per vertex)

| Vertex | Provenance |
|---|---|
| phx_dm_v2_advisor | REAL |
| phx_dm_v2_month | DERIVED (billable_days DERIVED; index_return DUMMY) |
| phx_dm_v2_revenue_class | REAL (seeded) |
| phx_dm_v2_product_line | REAL |
| phx_dm_v2_product_group | REAL |
| phx_dm_v2_product | REAL |
| phx_dm_v2_account | REAL |
| phx_dm_v2_driver_cause | REAL (seeded reference) |
| phx_dm_v2_revenue_transaction | REAL |
| phx_dm_v2_monthly_product_revenue | DERIVED |
| phx_dm_v2_account_month_balance | **DUMMY** (no billable-assets source) |
| phx_dm_v2_revenue_change | DERIVED |
| phx_dm_v2_revenue_driver | DERIVED (per-driver flag REAL/DERIVED/DUMMY by cause) |
| phx_dm_v2_commentary_version | DERIVED |
| phx_dm_v2_commentary | DERIVED |
| phx_dm_v2_evidence | DERIVED |

25 edge types, all directed with reverse edges (see `02_edges.gsql`).

---

## 4. Queries

| ID | Name | Purpose | Consumer | Tested? |
|---|---|---|---|---|
| GQ-001 | get_advisors | advisor picker | context bar | ✔ local tier vs sample |
| GQ-002 | get_months | period controls, transitions | shell, workflow | ✔ |
| GQ-003 | get_product_hierarchy | pivot row structure | Trends | ✔ |
| GQ-004 | get_driver_causes | cause vocabulary | AI Insights | ✔ |
| GQ-005 | get_monthly_revenue_by_product | Trends pivot cells | /api/v2/trends/revenue | ✔ |
| GQ-006 | get_monthly_revenue_totals | stacked bar chart | /api/v2/insights/chart | ✔ |
| GQ-007 | get_revenue_changes | MoM table + chart arrows | /api/v2/trends/changes | ✔ |
| GQ-008 | get_change_drivers | ranked drivers per transition | /api/v2/insights/drivers | ✔ |
| GQ-009 | get_commentary | stored commentary ('' = latest PUBLISHED) | /api/v2/insights/commentary | ✔ |
| GQ-010 | get_commentary_versions | version selector | /api/v2/insights/versions | ✔ |
| GQ-011 | get_product_revenue_change | evidence "Reproduce this result" | evidence modal §5 | ✔ (run live during evidence assembly) |
| GQ-012 | get_evidence | full evidence record | /api/v2/evidence | ✔ |
| GQ-013 | get_transactions | drill-down rows | /api/v2/transactions | ✔ |
| GQ-014 | get_ingestion_counts | counts + data_source mix | ingestion, env-health | ✔ |
| GQ-015 | get_advisor_month_summary | context bar, sanity checks | /api/v2/ops/advisor-summary | ✔ |

"Tested" = executed via the identical-shape local tier against the sample set;
**none is installed on a live TigerGraph** — every one is flagged
`created-v2-NEEDS-LIVE-INSTALL` (see §7 client-machine follow-ups).

---

## 5. Data provenance

**REAL** — advisor identity, product hierarchy, accounts, revenue transactions
(`post_split_credited_amt` is the revenue figure), cause vocabulary; driver
causes VOLUME / ONE_TIME / TIMING / FEE_RATE / DISCOUNT / NEW_ACCOUNT /
LOST_ACCOUNT / CLAWBACK (computed directly from real fields).

**DERIVED** (formula recorded in each driver's `inputs_json`):
- monthly_product_revenue: Σ credited_amt grouped by (advisor, month, group);
  `avg_rate_bps` revenue-weighted; recurring/one-time split by `rev_nature`
  (one_time bucket includes ADJUSTMENT so the split sums to revenue).
- revenue_change: `to − from`; pct = change/from×100 (from=0 ⇒ UI shows n/a).
- BILLABLE_DAYS: `from_revenue × (to_days − from_days)/from_days` (business-day
  calendar Mon–Fri, no holiday calendar — client may correct).
- MIX: `change_amt − Σ other causes` (the reconciling remainder).
- rev_nature: derived from file_key + trade_description per EXTRACTION_SPEC §4.
- Recurring vs non-recurring class = product lines Managed + Trails
  (inferred from the client mockup — **flag for confirmation**).

**ASSUMED** — none currently shipped.

**DUMMY** (and what would make it real):
- account_month_balance — needs billable assets per account/month
  (`avg_balance_amt` 0% populated for Managed).
- month.index_return + MARKET driver — needs an index-return source.
- NET_FLOW driver — needs a flows feed (`fpic_daily_adv_flows_tb` stops
  2026-01-30).
Both DUMMY causes are emitted per transition with contribution 0 on the
`__TOTAL__` row so the gap stays visible with its badge.

---

## 6. Known gaps / notes for the reviewer

1. **Edge count discrepancy in the spec**: SCHEMA_SPEC header says 23 edges;
   its own tables list 25. Built 25.
2. **NULL-advisor bucket**: the client extraction excludes a ~$30.5M
   NULL-`advisor_sid` bucket, so firm totals will not tie (per EXTRACTION_SPEC).
3. **June may be a partial month** in the real extract — label it rather than
   narrating an artefact (the sample set is complete months).
4. **Driver decomposition gaps**: Managed billable-assets effect and MARKET /
   NET_FLOW are DUMMY (no source data) — shown as such, never as fact.
5. **Edge bulk-delete on a live TigerGraph** is not possible over
   RESTPP/pyTigerGraph; edges disappear when their endpoint vertices are
   deleted. The ingestion delete reports this rather than pretending.
6. Commentary durability in local mode is via CSV append into the active data
   set (the graph store is in-memory); on a real TigerGraph the upserts are the
   system of record and the CSVs are a redundant journal.
7. The guardrail number-extractor whitelists years/YYYYMM and identifier-embedded
   digits (account/trade refs); tolerance $1.01 plain / $55 for k-form values.

## 7. Client-machine follow-ups (cannot be verified here)

1. Run `01_vertices.gsql`, `02_edges.gsql`, `03_create_graph.gsql` on live
   TigerGraph 4.2.x, then `install_all_queries.gsql` — every GQ file is
   `NEEDS-LIVE-INSTALL`; parse-verified only.
2. Run the three extraction SQL files against `pcr` and drop CSVs into
   `data/real/` matching the manifest column headers; set `DATA_SET=real`.
3. Verify `advisor_sid` on the trade table equals `standard_id` in
   `fpic_prm_rr_tb`; fall back to `(prm_ofc_no, prm_rr_no)` if not.
4. Set `GRAPH_CLIENT_MODE=real` + TG_* env; confirm env-health shows
   TigerGraph · tier 1 green and the tier pill is green.
5. `LLM_CLIENT_MODE=claude` (or client SDK mode) + key; run one generation and
   review a sample of narratives against the guardrail report.
6. pyTigerGraph `delVertices`/`delVerticesById` delete paths — exercised only
   against the local tier here.

---

## 8. Round 2 (FIX_SPEC.md, 2026-07-21)

### 8.1 R1 — Credited revenue corrected (the material fix)

**What was wrong:** the app summed every `post_split_credited_amt` and called it
Credited Revenue. The client's definition (Confluence *"Revenue Summary Data
Mapping"*) excludes ineligible reason codes; we never extracted `reason_cd`.
Every figure in the app was Total Revenue mislabelled.

**The fix — eligibility is data, not code:**
- New vertex `phx_dm_v2_reason_code` (15 codes seeded from the client doc,
  `data_source=REAL`) with three states: CREDITED (`__NONE__`, 91, 92, 9L),
  NON_CREDITED (9E, 9G, 9C, 9S, 94), EXCLUDED (9R, 98, 99, 9H, 9X, XX — not
  revenue at all, in no total). Edge `phx_dm_v2_txn_has_reason` (+reverse).
- Transaction vertex gains `reason_cd, rm_sid, cs_sid, revenue_eligibility,
  incentive_eligible, days_to_process, posting_month_id`; product vertex gains
  `grid_type` (stored, not filtered at extraction).
- `credited_revenue = Σ post_split_credited_amt WHERE reason_code.include_in_credited
  (read from the graph) AND product.grid_type IN CREDITED_GRID_TYPES (config,
  default ['PRODUCT_TYPE']) AND days_to_process <= MAX_PROCESSING_DAYS (config,
  default 90)`. Verified: relaxing the grid config changed the drill-down
  credited total 16,640 → 36,640 with zero code change.
- `monthly_product_revenue` stores the client's own breakdown alongside:
  `total_revenue / non_credited_amt / excluded_amt / late_excluded_amt`, with
  the identity `revenue = total − non_credited − late_excluded` verified on
  every cell by the e2e suite.
- New driver cause **ELIGIBILITY** (REAL), slotted immediately after ONE_TIME:
  `-(Δ non-credited)` per group, with accounts already claimed by
  NEW/LOST_ACCOUNT excluded, and advisor account-presence now counting
  non-credited activity (a household going 9E is an eligibility move, not a
  lost account). 13 causes total.
- Sample data regenerated: every eligibility path exercised (`__NONE__`, 91,
  9E, 9G, 9X, one >90-day row, PAY_TYPE_SUMMARY rows). The 9E story produces a
  visible ($6,290.00) ELIGIBILITY driver for SMPL001 May→Jun. Commentary
  v1–v5 history preserved (regeneration is additive).
- Commentary regenerated as **v6** (6/6 published, 0 blocked, 86 evidence
  records); reconciliation $0.00 on every transition, recomputed from stored
  graph data.

**Interpretations & assumptions recorded (R1):**
- *EXCLUDED third state* — the client doc names two states; codes with no UI
  mapping are read as "not revenue at all". To confirm with the client.
- *91/92/9L are credited but incentive-ineligible* — client-confirmed for now,
  flagged for re-confirmation.
- *posting_month_id = trade month*, `ASSUMED` — prior-period adjustments post
  to the proc_dt month; without the iComp feed closed months cannot be
  identified. PPA logic deliberately not implemented this round.
- *Unknown reason codes → NON_CREDITED* — never credit unclassifiable revenue;
  kept in Total for honesty.
- *LATE (>90d) rows* stay in Total, out of Credited, tracked as
  `late_excluded_amt` ("ignored … not sent to iComp").

### 8.2 R2/R3 — Defects + source catalog
- **R2-1**: evidence calculation components now carry a `unit`
  (currency|count|percent|bps|days) inferred from the input key; the modal
  switches formatter on it, shows "—" share for non-currency rows, and sums
  only currency components. Counts can no longer render as dollars.
- **R2-2/R3**: `docs/data/source_catalog.json` is the single source of truth
  for source-system metadata (tables, grain, full column→vertex mapping). The
  three extraction SQL files are *generated* from it
  (`scripts/generate_extraction_sql.py`) with the corrected table names
  (`pcr.fpic_daily_trade_details_tb_prod`, `pcr.product_hierarchy`), and the
  evidence builder reads `source_table` from it. No PostgreSQL table name
  remains as a Python literal.
- Also hardened: `schema_catalog.json` and `load_v2_all.gsql` are now generated
  from the GSQL DDL (`scripts/generate_schema_artifacts.py`) — the drift class
  behind R2-2 is closed structurally.

### 8.3 R5 schema — LLM-as-judge storage
`phx_dm_v2_commentary_evaluation` vertex + `phx_dm_v2_evaluation_of_commentary`
edge; GQ-017 `get_commentary_evaluations` on both tiers; `JUDGE_MODEL`
(different from the writer) + `JUDGE_ENABLED` settings. Judge is ADVISORY only
— the deterministic guardrail gate (which caught real LLM arithmetic in v2–v4)
remains the blocking control.

### 8.4 R4 — Evidence made convincing
Every evidence record (86 in v7) now carries, inside `calc_json`: **why this
cause** (rule in plain words, inputs tested, competing causes rejected —
sourced from the attribution code so it cannot drift), **attribution order**
(step *n* of 12 with what earlier steps already claimed — the answer to
"how do you know you're not double-counting"), a **reconciliation waterfall**
(from-revenue → each cause → to-revenue, verified to sum exactly on all 86
records), the **rev_nature derivation** (actual file_key/trade_description
values), and the **credited-revenue breakdown** in the client's own vocabulary
(Total, less non-credited itemised by reason code, less excluded, less >90-day,
= Credited). The lineage SQL renders from the source catalog and stays labelled
"not executed by this application", in contrast to the GSQL that was run.

### 8.5 R5 — Judge wiring and first run
Judge runs after the guardrail gate per transition on `claude-sonnet-5` (writer:
`claude-haiku-4-5`), scores faithfulness/hallucination/completeness/clarity,
returns PASS/REVIEW/FAIL + reasoning. Strictly advisory: any failure degrades
to REVIEW "judge unavailable", never blocks or publishes. First run shipped
with v7: 6 evaluations, all PASS. Surfaced as the evidence modal's
"Independent review" line and card badges when not PASS;
`GET /api/v2/insights/evaluations`.

### 8.6 R6 — Screenshot evidence harness
`scripts/capture_evidence.mjs` (Playwright, 1440px, role/text selectors): 8
screens — trends, ai-insights, evidence modal open, filtered transactions,
ingestion, env-health, an empty state, and an HONEST blocked state (v3's real
guardrail-blocked transition selected via the UI version picker). Collects
console errors per page and fails the run on any; the final run captured 8/8
with zero console errors. `docs/qa_screenshots/` is gitignored (harness
committed, artefacts never); the harness writes `index.md` describing what each
shot proves.

### 8.7 R7 — Polish and AI marking
Typography/density only (no palette/layout change): 13px/500 top nav with 2px
active underline, 12.5px sub-nav, `tabular-nums` right-aligned numerics on
every numeric cell, +2px row height, 0.5px header tracking. **AI marking
(R7-2)**: the ✦ AI GENERATED chip (tooltip: model · prompt · commentary
version) appears on exactly four language regions — commentary card headers,
the walk table's commentary column header, evidence §1 Finding, and the judge's
reasoning — and on no computed figure anywhere. Boundary helper text on both
screens: *"Wording is AI-generated. All figures are computed from graph data
and validated before publication — the model never produces or alters a
number."* CSV exports carry an AI-column footer.

### 8.8 R8 — V1 cleanup
22 dead files removed after a read-only consumer-chain analysis (V1 query
contracts incl. `get_advisor_360` et al., V1 MockGraphStore, four unused MCP
adapter/contract modules, schema_inventory, 13 dead V1 model modules, 2 dead
frontend files). Keep-list verified by live consumer chains (graph-access
stack, tiered MCP/REST clients, llm_runtime). Bonus find: `.gitignore`'s
`models/` pattern had been ignoring the whole `app/models` package — live
modules were never in git and a fresh clone would not have booted; pattern
rooted and files committed. App boots and all screens render post-cleanup.

### 8.9 R9 — docs/SOLUTION_GUIDE.md
Ten chapters: overview, business definitions (full reason-code table, client
vocabulary, Confluence-cited), lineage from the source catalog, all 18
vertices/27 edges, GQ-001..017, the calculation reference with a worked
example per cause from the real sample data (running example: SMPL001 May→Jun
($29,745.28) walked driver-by-driver to $0.00), agent architecture (gate first,
judge second), evidence model, operations runbook (Regenerate is the only
commentary trigger), and every gap/assumption from FIX_SPEC R9.10 — including
the honest flag that no ready-made script derives CSVs for `data/real/`.

### 8.10 Round 2 Definition of Done — verified
All R11 boxes checked: eligibility fully data-driven (config flip changes
behaviour with no code change — demonstrated), commentary regenerated (v7,
reconciliation $0.00 everywhere), units fixed, no table-name literals,
evidence shows why/order/waterfall/breakdown, judge advisory + visible, AI
marking with the computed/generated boundary intact, screenshots captured
with zero console errors, app boots clean, SOLUTION_GUIDE complete,
PROGRESS.md all R-tasks DONE.

### Round 2 parallelisation actually used
R1–R3 + all schema/query/catalog/mock authoring ran serially on the main
thread per the working agreement. Then five parallel subagents: R4+R5 backend ·
R4/R5/R7 frontend · R6 Playwright harness · R8 read-only dead-code analysis
(applied by the main thread) · R9 guide draft. Subagents did not commit; the
main thread reviewed, verified, committed, regenerated v7 and re-verified
end-to-end (ALL PASS).

## 9. Round 3 (FIX_SPEC_R3.md, 2026-07-22)

### What was done

**T1 — Correctness: the missing LATE_PROCESSING revenue driver (done first, main thread).**
The credited identity (`credited = in-scope total − non_credited − excluded −
late_excluded − out_of_grid`) had two subtrahends with no driver, so their
month-over-month movement fell into the MIX residual and was narrated as
"product mix" — a wrong explanation with full evidence behind it. Fixes:

- **LATE_PROCESSING** (`-(Δ late_excluded)`, REAL) added symmetric with
  ELIGIBILITY, immediately after it in the attribution order; account-guarded
  against NEW/LOST double-counting; account *presence* now also counts LATE
  activity (a late-processing account is still trading).
- **EXCLUDED_CHANGE** (`-(Δ excluded)`, REAL) added for excluded bookings
  (e.g. reason 9X deleted rows). **OUT_OF_GRID needs no driver by
  construction** — grid_type is a static product attribute and
  CREDITED_GRID_TYPES fixed config, so out-of-grid revenue cannot move into or
  out of credited month over month; the verification suite proves the bucket
  contains only PAY_TYPE_SUMMARY rows and reports its total loudly
  (sample: $59,090.91 of deliberate demo rows; on REAL data expect ~0).
- **MIX self-check**: |MIX| > 15% of a transition's |change| logs a WARNING
  with the full cause breakdown (advisory, never blocks).
- **MIX-magnitude reporting** in `verify_end_to_end.py` — reconciliation at
  $0.00 proves *completeness* only; MIX share proves *attribution quality*.
  After the fix: **MIX ≤ 1.0% on all six sample transitions** (was: late/9X
  swings silently absorbed).
- **Sample data reworked** so both drivers fire on genuine credited movement:
  SMPL003's 900 UMA fee exists all three months with April processed 100 days
  late (Apr→May credited genuinely gains 900); SMPL003's 500 MFT booking is
  credited in Apr and deleted (9X) from May on (Apr→May genuinely loses 500).
- **total_revenue relabelled** in the evidence ledger as "In-scope revenue"
  with the footnote "total within credited product grid types" (field names
  unchanged — presentation-only, same principle as the T4-1 rename).
- **Commentary regenerated**: v9 (post-fix figures; 6/6 published, judge 5
  PASS / 1 advisory REVIEW) and v10 (revenue-driver terminology in evidence
  wording; 6/6 published, judge 6× PASS). The v8 run exposed a real guardrail
  false positive — the no-invented-figures extractor read reason code "(9E)"
  as the figure 9 — fixed with a letter lookahead in the number regex;
  LATE_PROCESSING inputs carry `processing_days_limit` so "90-day" narration
  stays legal. v8 (1 BLOCKED) is retained as history; versions are additive.

**T2/T3 — Evidence UX.** The modal now takes the transition, loads the FULL
ranked driver set (GQ-008), pages with Previous/Next + ←/→ ("Revenue Driver n
of N"), lazy-loads evidence per driver (cached), and its header (title, colored
▲/▼ amount, provenance badge, driver tag, position) tracks the current driver.
Both entry points unified: the walk opens at driver 1, a card bullet opens at
that bullet's driver — both with the full set. Old versions: **labelled, not
backfilled** — v1–v6 driver sets were superseded by data regenerations, so
deepened evidence/judge output cannot be honestly reconstructed; every affected
panel states this explicitly (no blank scaffolding). Waterfall gains the
plain-English lead sentence, green/red driver bars with the paged driver
highlighted, a "How to read this" expander, and the completeness note tying
$0.00 reconciliation to the missing-driver self-check. The double-parenthesis
header is fixed (arrow = direction, fmtMoney = sign) and the repo audited for
other double-wraps (also fixed "prompt vv1.0" in the modal footer).

**T4 — Terminology & glossary.** "Revenue Driver(s)" replaces "cause" in all
labels, panel titles, tooltips and column headers (`cause_id` and every data
field unchanged). Cards carry an explicit "Revenue Drivers" column header.
New glossary dialog (openable via "What do these mean?" from AI-Insights and
the evidence modal) lists **all 15 revenue drivers** — the spec's 14 plus
EXCLUDED_CHANGE born of T1-2 — with plain-English meaning and computation;
Market/Net Flow carry the DUMMY badge. SOLUTION_GUIDE ch. 6 now documents the
14-step attribution order and references the glossary as the shared source.

**T5 — AI-Insights interaction.** Dead T-3 legend dropdown removed. The driver
section has a segmented Single transition (default) / Compare two / All
transitions control with transition dropdowns; chart connector arrows and
change pills are clickable (wide hit areas) and focus that transition in
Single mode with a visible highlight; the walk's lookalike version dropdown is
static text inheriting the top selector ("Version 10 (latest)").

**T6/T7 — Exports & polish.** "Export data" builds CSV from the STORED data
via the API (never the DOM): one row per (transition, revenue driver) with
human headers (Advisor, From/To Month, Total Revenue, Credited Revenue,
Change $ / %, Revenue Driver, Contribution, Direction, Data Source,
Commentary), negatives parenthesised, AI-generated column marked; the walk
exports one row per month with its drivers and commentary. "Export PDF" is a
print stylesheet + `window.print()` (vector, deck-ready) — chrome hidden, a
print footer carries advisor, date, version and the AI boundary note.
Generate/Regenerate take the primary navy fill; exports the secondary outline;
hover/focus/disabled styled throughout. The computed transaction count is
separated from the AI chip by a hairline and labelled "computed from graph
data".

**T8 — Checks.** `.gitignore` is LF (ASCII text); `git check-ignore
data/real/x` prints the path — real client data is protected. `git ls-files
app/models` returns 6 tracked files — a fresh clone boots.

### Verification

`verify_end_to_end.py` (extended this round): **OVERALL PASS** — reconciliation
$0.00 on every transition, all 15 causes exercised, MIX ≤ 1.0% everywhere,
OUT_OF_GRID composition clean, credited identity holds per cell, 861 evidence
records complete, every vertex carries data_source. Playwright evidence
harness: **8/8 screens captured, zero browser console errors** (v10 visible,
paging modal, view modes, themed buttons, static walk version).

### Decisions taken (also in PROGRESS.md)

- Old-version evidence **labelled, not backfilled** — backfilling would attach
  today's numbers to yesterday's narratives (dishonest); the spec's fallback
  applies. The "from version 7 onward" boundary is a documented constant in
  the modal (`DEEP_EVIDENCE_FROM_VERSION`), data-set specific.
- The glossary lists 15 drivers, not the spec table's 14 — EXCLUDED_CHANGE was
  created by T1-2 after the spec was written; omitting it would violate the
  glossary's "every revenue driver" rule.
- ELIGIBILITY remains un-split (status-change vs volume) per T9 — client
  question, not a build decision.
- Prior-period adjustments / iComp sourcing / Adjusted Credited Revenue remain
  open client items (FIX_SPEC R9.10 / SOLUTION_GUIDE ch. 10); untouched.
- LATE_PROCESSING and EXCLUDED_CHANGE inherit the ELIGIBILITY-class
  approximation: a bucket delta is attributed even when the underlying rows
  simply vanish rather than move between buckets (the remainder offsets in
  MIX). Noted for the reviewer; the sample data exercises the genuine-move
  case.

### Commits (round 3, in order)

02b3d2e progress scaffold · 5c4b7bf T1 drivers + checks + relabel ·
7fee0f4 T1-5 v9 + guardrail fix · 76d883d T2/T3 evidence UX ·
960662f T4 terminology/glossary + v10 · d465b29 T5 view modes/arrows ·
1b23d08 T6/T7 exports/theming + T8 · (this) round-3 report + final verify

---

## 10. Round 4 (FIX_SPEC_R4.md, 2026-07-22)

Two work-streams: **(A)** four demo-blocking UI defects found in
client-environment testing, **(B)** the real-data pipeline — the missing
middle between the human-run extraction SQLs and `data/real/`.

### Work-stream A — evidence & insights UI correctness

- **S-A1 (652c212)** — `RevenueDriverGlossaryDialog` now renders through
  `createPortal(document.body)`, so the dialog is never a DOM descendant of
  its trigger; the `<h2>`-inside-`<p>` hydration errors (8, on two screens)
  are gone. Audited for other inline dialogs: `EvidenceModal` renders at page
  level — no other offender.
- **S-A2/S-A3 (5a1a447)** — the evidence modal now holds ONE scope: the
  clicked driver's product group. The reconciliation waterfall is REBUILT for
  that group from stored rows — FROM/TO from the group's `revenue_change` row,
  bars from the group's drivers; attribution runs per group with a per-group
  MIX residual, so the bars sum exactly to the group's change. Header,
  waterfall and credited breakdown now reconcile to the same figure (the
  $98/$25/($165) class of mismatch is structurally impossible). Paging,
  count ("Revenue Driver n of N in <Group>"), ←/→ and the position indicator
  operate over the group's driver list only, with a one-line caption relating
  the card's advisor-wide top-5 to the modal's group walk. Drivers attached to
  `__TOTAL__` (MARKET/NET_FLOW) get an explicitly-labelled
  "Total — all product groups" scope whose waterfall is the whole transition
  (all causes aggregated) — a labelled transition view, never silently mixed.
- **S-A4 (ae7dd90)** — Compare-two: each dropdown disables the transition
  selected in the other; slot B defaults to a different transition (or empty
  with a single transition); card keys are slot-scoped
  (`${slot}-${commentary_id}`) so a duplicate can never crash the render.
- **S-A5 (c7d5fb8)** — regression sweep: 13/13 Playwright shots (8 original +
  5 new round-4 proofs: glossary from both entry points, group-scoped modal
  paging, compare-two, all view modes), **zero console errors**. Group
  waterfall verified numerically against the API for every group of
  SMPL001 202605→202606 (each group's driver sum equals its change exactly;
  the all-group aggregate equals the total change ($29,745.28)).

### Work-stream B — real-data pipeline

- **S-B3 (c23dbe5)** — `app/v2/dataset/provenance.py` is now the single
  authority for `data_source` stamping (REAL/DERIVED/ASSUMED/DUMMY rules per
  artifact, `require_stamped` guard — a row can never be written blank).
  `app/v2/dataset/builder.py` owns everything downstream of the transactions
  (eligibility split, aggregation, MoM, attribution, reconciliation
  stop-condition, all vertex/edge CSVs, manifest). The sample generator was
  refactored onto it — **regenerated sample output is byte-identical**
  (verified via git diff), proving the refactor changed nothing.
- **S-B1/S-B2 (a095acd)** — raw-extract contract codified and validated:
  `data/real/_raw/raw_{revenue_transaction,product_hierarchy,advisor}.csv`
  with exactly the SELECT-list columns of the three generated SQLs; a missing
  file/column fails loudly by name. `scripts/build_real_data.py` maps raw rows
  to the app's transaction shape (post_split_credited_amt → credited_amt,
  rev_nature derived, reason_cd → eligibility via the reason seed,
  days_to_process computed, posting_month_id = trade month **ASSUMED**),
  builds dimensions from the hierarchy/advisor extracts (line = distinct
  level_one_product, group = distinct level_two_product, Managed/Trails →
  RECURRING — the EXTRACTION_SPEC §4 inference, still flagged for
  confirmation), validates referential integrity and month consecutiveness,
  then calls the shared builder. **Reconciliation $0.00 is asserted on every
  transition — a failure stops the build.** Summary prints rows per file,
  eligibility split, OUT_OF_GRID and >90-day counts, and MIX% per transition.
  Commentary is NOT generated by the builder (Regenerate workflow only).
- **S-B4 (f2efd02)** — `.env.example` rewritten for V2;
  **all 128 keys `settings.py` reads are present** (programmatic cross-check),
  with client-machine and offline-demo quick-start blocks.
- **S-B5 (84f94c4)** — SOLUTION_GUIDE Chapter 9 is now a nine-step numbered
  runbook (prereqs → schema → queries → extract → build → load → generate →
  verify → ordered reload), each step with the exact command, expected output,
  and failure symptom + first check. Headless commentary CLI added:
  `python -m app.v2.commentary.generation_workflow` (same pipeline and gates
  as the Regenerate button).
- **S-B6** — local proof, without a live TigerGraph:
  `scripts/make_test_raw_extracts.py` writes tiny, obviously-synthetic
  fixtures (RTEST01/RTEST02, TESTACCT-*) in the exact raw shape to the
  gitignored `data/real/_raw/` (`git check-ignore` verified);
  `build_real_data.py` produced `data/real/{vertices,edges}` with the same
  columns as sample, reconciliation $0.00 on all 4 transitions, MIX ≤ 7.14%,
  OUT_OF_GRID=3 and LATE=1 rows correctly bucketed; a backend started with
  `DATA_SET=real` served the fixture data through the SQLite tier
  (advisors/changes/drivers correct, per-cause data_source flags intact) and
  `/api/v2/ops/reconciliation` recomputed **$0.00 discrepancy** for both
  advisors; headless generation then created commentary v1 (4/4 published,
  29 evidence records — one per driver). The committed manifest was
  regenerated back to sample scope afterwards (the manifest reflects the
  active data set; `build_real_data.py` rewrites it on the client machine).

### Proven locally vs. remaining client-machine steps

| Proven here (local tier, fixtures) | Still requires the client machine |
|---|---|
| Raw contract validation, loud failures | Running the 3 SQLs against real PostgreSQL |
| Extract → data/real build, $0.00 reconciliation asserted | Reconciliation behaviour on real-volume data (a failure is a designed STOP) |
| data_source stamping identical to sample (shared helper) | — |
| SQLite-tier load + serve with DATA_SET=real | TigerGraph schema install, query install (all GQ still `created-v2-NEEDS-LIVE-INSTALL`), graph load, tier-1 green env-health |
| Headless commentary generation on the real set | Claude-mode generation with the client's key; judge on real narratives |
| Ordered delete/reload on the local tier | pyTigerGraph delete path on live TigerGraph |

### Decisions taken (also in PROGRESS.md)

- The shared ingestion manifest reflects the ACTIVE data set (build_real_data
  rewrites it with real counts on the client machine); the repo keeps the
  sample-scoped manifest, regenerated after the local fixture proof.
- Real `product_name` = the `product_cd product_sub_cd` pair — the source
  hierarchy has no display-name column and names are never invented. Same for
  `account_typ`/`wrap_flg` (blank, not in the extracts) and blank advisor
  names (UI shows the id).
- The fixture GENERATOR is committed (`scripts/make_test_raw_extracts.py`);
  the fixtures themselves stay uncommitted under gitignored `data/real/_raw/`.

### Commits (round 4, in order)

652c212 S-A1 glossary portal · 5a1a447 S-A2/A3 group-scoped evidence modal ·
ae7dd90 S-A4 compare-two guard · c7d5fb8 S-A5 sweep 13/13 zero errors ·
c23dbe5 shared builder + provenance · a095acd real-data builder + fixtures ·
f2efd02 .env.example 128/128 · 84f94c4 runbook + headless CLI · (this) report

## 11. Round 5 (FIX_SPEC_R5.md, 2026-07-23) — INGESTION RESCUE

The first real load against live TigerGraph exposed that ingestion reported success
while writing nothing: attributes silently dropped (id-only vertices), checkpoints
recorded success for writes that never landed (then hash-skipped forever as
"Unchanged"), and delete/reset paths threw 500s whose missing CORS headers masked
the real errors. This round made ingestion trustworthy.

### Commits (in order)

| Commit | What |
|---|---|
| d98d825 | W-tasks appended to PROGRESS; round-5 session record |
| 0f64509 | W-A1 attribute drop impossible: shared fail-loud mapper (all tiers) + exact pre-flight header validation |
| 23fe017 | W-A4 checkpoint honesty: hashes/tallies only after confirmed flush; fallback-tier write fails the batch |
| 8ea3140 | W-A2/A3 CSV correctness: LF everywhere, BOM-tolerant reads, csv-aware counting |
| feb169d | W-A6 deletes guarded + non-aborting; CORS-safe JSON 500s with the real message |
| 971235f | W-A7 repo-root path anchoring (.env, SQLite, data dir, manifest, logs) + startup logging + env-health resolved_paths |
| 3d5bd3c/6d8a6ef | W-A8 90_drop_all.gsql + POST /ingestion/clear-checkpoints + RUNBOOK Step 10 clean-slate |
| e1f9b06 | W-A5 graph-truth validation: fetch_vertices on every tier; GET /ingestion/validation (VALIDATED/EMPTY_ATTRS/MISMATCH/NOT_LOADED/UNVERIFIABLE) |
| 4bdc43d | W-A9 fixture harness (data/fixtures, gitignored) + verify_ingestion_fixes.py 25/25 PASS + docs/ROUND5_ACCEPTANCE.md |
| a5fc7c3, d82494c | W-B1..B7 ingestion screen rebuilt: validation column, live n/45 progress, async polling, batch-size override, persisted errors + remediation, skip-and-continue summary |
| 71b78c5 | W-D1..D3 baseline month: BASELINE_LIMITED driver, commentary guard, UI note; sample v13; MIX ≤6.2%, recon $0.00 |
| 53e2289, f6d467d | W-E1/E2 real data is the only demo path; sample demoted to test asset; §10.12 streaming next-step |
| 3f849fb | W-C1/C2 CSVs named after their vertex/edge type; csv_file_for() is the single naming catalog |

### VERIFIED HERE (local tier + real-shaped fixtures — NOT a real-data verification)

All via `scripts/verify_ingestion_fixes.py` (25/25 PASS after every work-stream) plus
targeted checks:

1. Attribute integrity — stored rows carry populated non-PK attributes, never id-only.
2. Fail-loud mismatch — a renamed column fails the entity naming missing AND extra columns; nothing written; error persisted with remediation.
3. Quoting — a value with comma + quote + newline round-trips into the right columns; empty optional values load.
4. LF + BOM — writers emit LF only; a BOM-prefixed file parses cleanly.
5. Checkpoint honesty — real mode with the engine unreachable: batch FAILED, 0 hashes, 0 created; reload RETRIES (does not skip); a write served by the mock fallback tier fails the batch with remediation.
6. Screen truth — /ingestion/validation detects VALIDATED, MISMATCH (count drift AND checkpoint-vs-graph conflict) and EMPTY_ATTRS (id-only rows) from actual stored rows.
7. Deletes — delete-one/-all never raise; delete-all continues past an injected failure (44 deleted, 1 reported); 500s carry CORS headers + real message.
8. Paths — all resolved paths absolute and launch-dir independent (verified from cwd=/).
9. Idempotency — full load twice: identical counts, second run all-skipped, no false skips.

Also: end-to-end suite OVERALL PASS (reconciliation $0.00 every transition, MIX ≤6.2%
< 15% incl. the first transition, all 16 causes incl. BASELINE_LIMITED), query
validation ALL PASS, frontend typechecks, screens verified headless with zero console
errors (ingestion: 45 rows, 45 VALIDATED pills, run-all to completion; AI-insights:
baseline note on the Apr→May card).

### REQUIRES OPERATOR ACCEPTANCE (live TigerGraph, real data — NOT run here)

The build environment has no TigerGraph and no client data (`data/real/` gitignored).
`docs/ROUND5_ACCEPTANCE.md` is the numbered checklist: drop/recreate schema, clear
checkpoints (confirm resolved DB path), build_real_data (recon $0.00, first-transition
MIX < 15% with BASELINE_LIMITED), Run All to all-45-VALIDATED, GSQL spot-check of
populated attributes, delete-one/-all without 500, idempotent re-run. Work-stream A is
DONE **pending operator acceptance** of exactly those steps.

### Decisions taken

- A write served by the local fallback tier while GRAPH_CLIENT_MODE is a real mode now
  FAILS the batch (this was the root of "created=2, 100%, graph empty" — the tiered
  fallback made a lost write look successful).
- Delete failure keeps the entity's checkpoints (state stays consistent with the graph);
  only a confirmed delete clears them.
- Zero-attribute records refuse to write even when the header matched (all-empty row) —
  per spec A1.3; a legitimately all-blank optional row is treated as a data defect.
- Sample's LOST_ACCOUNT story moved to May→Jun and a new Apr-only account added, so both
  LOST_ACCOUNT and BASELINE_LIMITED stay exercised after D1 (Apr→May is baseline-limited).
- verify_end_to_end's cause assertion updated 15→16: it asserted the pre-D1 cause model.
- Sample CSVs renamed via git mv BEFORE regeneration so commentary history v1–v13
  survived the C1 renaming.

### Known gaps

- The MCP tier's `fetch_vertices` uses the `get_nodes` tool name; if a given
  tigergraph-mcp version does not expose it, validation sampling falls through to the
  pyTigerGraph tier (by design) — unverifiable here.
- Attribute validation samples N=5 rows per vertex type; edge entities (no declared
  attribute columns) validate on count only.
- Streaming ingestion for multi-million-row loads deliberately deferred
  (SOLUTION_GUIDE §10.12).
- LOST_ACCOUNT + BASELINE_LIMITED interplay on real data (10 advisors) is exactly what
  ROUND5_ACCEPTANCE step 3 checks — MIX < 15% on the first transition must be confirmed
  on real data, not only on sample.

### File-change manifest

`docs/ROUND5_CHANGED_FILES.md` — git-derived per work-stream, with operator-local
exclusions, conflict-risk flags, and the full C1 rename list.

---

## 12. Round 6 (FIX_SPEC_R6.md, 2026-07-23) — ATTRIBUTION CORRECTNESS + ANOMALY DETECTION

### Work-stream A — the account-presence fix

**The bug (from the first real-data build):** `attribution.py` judged account presence
with a two-month test (`traded this month XOR last month`) over 19,694 accounts. On real
data most accounts do not trade every month, so NEW/LOST_ACCOUNT — and BASELINE_LIMITED,
which inherited the same sets — massively over-claimed (BL −$267,500 against a −$154,812
total change; LOST −$291,801 / NEW +$150,001 large and symmetric every month) and MIX
absorbed the error (92.6% … 2197.5% on first transitions). Reconciliation stayed $0.00
throughout — completeness holds no matter how wrong a named driver is, which is exactly
why the MIX self-check exists.

**The fix (X-A1..A3):**
- **A1 — recurring gate:** NEW/LOST_ACCOUNT (and BASELINE_LIMITED) are computed **only
  for recurring-class groups** (product lines Managed, Trails). Transactional groups
  leave their change to VOLUME/ONE_TIME/TIMING as before — the amount is NOT routed to
  MIX.
- **A2 — persistence:** an account is lost only after `ACCOUNT_ABSENCE_MONTHS`
  (config, **default 2**; settings + .env.example) consecutive loaded months with no
  activity (credited + non-credited + late all count); symmetric for new. Activity is
  now evaluated over the FULL loaded month range, not just the two transition months.
- **A3 — bounded BASELINE_LIMITED:** BL only carries recurring-group account movement
  whose presence test **cannot be evaluated** (too few loaded months on that side of
  the transition — first transitions for NEW, last transitions for LOST), and
  `|BL| ≤ |total change|` is asserted per transition: violation raises
  `AttributionError` and **fails the build loudly** (build_real_data STOPs).
- The build summary now prints, per transition: total change, MIX %, accounts
  classified new/lost, and the BL amount (A4.5).

**The precise client-facing rule (A5, everywhere):** *"accounts in recurring product
lines with no billing activity for ACCOUNT_ABSENCE_MONTHS (default 2) consecutive
months"* — stated in the Revenue-Driver glossary, the evidence modal's why-this-cause
panels, the commentary prompt + fallbacks, the driver_cause seed, and SOLUTION_GUIDE
§6.3/§6.4. Never "accounts leaving the advisor".

**Verified HERE (fixtures + sample only — no real data in this environment):**
- `scripts/verify_attribution.py` (12/12 PASS): a real-shaped fixture (equities accounts
  trading intermittently with month-to-month composition shift; Managed billing
  consistently) REPRODUCES the bug under the pre-R6 rules kept as a test-only
  `legacy_two_month_presence` path — MIX 465.1% of the first transition, BL −$24,300
  vs total −$4,300, symmetric NEW/LOST ±$40–55k on the transactional group — and under
  the R6 rules the SAME fixture gives MIX 7.0% / 9.4%, reconciliation $0.00, account
  drivers on recurring groups only, the one-month-quiet account claimed by NO account
  driver, and `AttributionError` proven to raise on a crafted over-claim.
- Sample set regenerated: MIX ≤ 8.1% on all 6 transitions, all 16 causes exercised,
  commentary v14 published 6/6 (judge 6× PASS, 92 evidence records),
  `verify_end_to_end.py` OVERALL PASS.

**Pending OPERATOR acceptance (real data, client machine):** run
`scripts/build_real_data.py` and confirm from its summary: MIX < 15% on EVERY
transition, reconciliation $0.00, plausible new/lost counts, and no
`AttributionError`. A fixture check is not a real-data verification; this round's
acceptance test is A4.1 on the client's own extract.

**Known limitation (recorded deliberately):** the A3 assertion `|BL| ≤ |total change|`
can in principle fire on a legitimately-small total change offset by large opposing
drivers (BL is signed and bounded by the transition's NET change, not by gross
movement). Per spec this fails the build loudly for investigation rather than
publishing — an honest stop, not a silent pass. If the operator hits it on data where
BL is genuinely legitimate, raise it back to us before touching the assertion.

### Work-stream B — carry-overs

- **B1 — `90_drop_all.gsql` corrected and generated:** the previous script dropped the
  graph before the queries (TigerGraph refuses) and assumed reverse edges drop with
  their parent (they do not — `reverse_phx_dm_v2_*` are separate schema objects).
  Now generated from the schema files by `scripts/generate_schema_artifacts.py` in the
  correct order **queries → graph → reverse edges → forward edges → vertices**, with a
  header explaining that "does not exist" errors are expected and safe while "still in
  use" is a real failure.
- **B2 — lesson recorded:** GSQL authored in this environment is **parse-reasoned, not
  executed** — there is no TigerGraph here to run it against. Every generated `.gsql`
  artifact (schema DDL, loading jobs, queries, and especially `90_drop_all.gsql`) is
  flagged **NEEDS-LIVE-VERIFICATION** until the operator has run it on the live box,
  and running `90_drop_all.gsql` end-to-end is part of the operator acceptance
  checklist. Round 5 shipped a drop script that had never been executable-tested; that
  class of gap is now labelled instead of implied-verified.
