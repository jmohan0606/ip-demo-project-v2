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
