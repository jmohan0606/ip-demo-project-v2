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

### Work-stream Y — anomaly detection

**Gate honoured:** Y started only after work-stream A was green — MIX < 15% on every
transition of the bug-reproducing fixture (7.0% / 9.4%) and the sample set (≤ 8.1%).
The real-data gate remains the operator's A4 acceptance.

**Built (commits 768296b, 39f2d84, 02e03d9, 1e1a7ae, ca8a911):**
- **Schema (Y1):** `phx_dm_v2_anomaly` + `phx_dm_v2_anomaly_scan` vertices; edges
  `anomaly_for_advisor`, `anomaly_in_scan`, `anomaly_cites_driver`. All artifacts
  (catalog, loading job, drop script — now 19 queries / 30+30 edges / 20 vertices)
  regenerated, NEEDS-LIVE-VERIFICATION.
- **Rules (Y2):** six deterministic rules in `app/v2/anomalies/detection.py`, all
  thresholds in settings (`ANOMALY_*`, in .env.example, surfaced in the UI and stamped
  into every scan's `thresholds_json`). **BOOK_MOVEMENT deliberately not implemented** —
  it presumes account movement is real, which work-stream A showed is largely trading
  intermittency on this data.
- **Queries (Y3):** GQ-018 `get_anomalies` (advisor/scan/severity filters; `scan_id=""`
  = latest) + GQ-019 `get_anomaly_scans`, with catalog entries, install_all, local-tier
  implementations and query cases; both tiers return rows ordered by `anomaly_id` so
  they stay byte-comparable — the severity display ranking lives in the service layer.
- **Service + trigger (Y4):** batch-only — `POST /api/v2/anomalies/scan`, status GET,
  and a headless CLI (`python -m app.v2.anomalies.detection`). Page loads only
  retrieve. Scans are additive (`scanNNN`), persisted via graph upsert + CSV append
  exactly like commentary versions.
- **Narration (Y5):** `commentary_agent.narrate_anomaly` — the model phrases computed
  metrics only; the payload includes `what_this_rule_means` so wording reflects real
  semantics. `validate_anomaly_text` guardrail: every figure in title/detail must exist
  in metrics_json/threshold_json and negatives must be parenthesised; failures fall
  back to a deterministic per-rule template with NO AI chip.
- **Screen (Y7):** `/anomalies` in the Results sub-nav per
  `docs/ui/reference/roadmap/02_anomaly_detection.png` — review-summary header,
  transition + scan-version selectors, themed Re-scan, four stat cards, severity-
  ordered cards (colored rail, severity pill, rule tag, AI Generated chip on model
  wording only, computed impact, action links), empty state naming the thresholds in
  force, and a visible configurable-thresholds note.

**Verified HERE (`scripts/verify_anomalies.py`, 14/14 PASS with `--rescan`):** each
rule fires once and only once on a crafted context and stays silent below threshold;
the guardrail blocks an invented figure and a minus-signed figure; an LLM that invents
a figure is forced to the deterministic fallback; no stored anomaly contains a figure
absent from its metrics_json; a re-scan creates a new scan_id while the prior scan's
rows remain retrievable byte-identical; `scan_id=""` resolves to the newest scan.
Headless UI sweep: all six screens (including /anomalies and its empty state) render
with zero console errors. Sample scan001: 9 flagged (6 LOW dominance, 3 INFO
baseline-limited; sample-scale data doesn't reach the HIGH/MEDIUM thresholds — the
per-rule fixtures cover those).

**Deliberate deviations from the spec text (recorded, not hidden):**
1. `anomaly_id` is **scan-prefixed** (`scanNNN|advisor|from|to|rule[|group]`), not the
   spec's `advisor|from|to|rule`: with the un-prefixed id a re-scan upserts over the
   prior scan's vertices and scans stop being additive — the very property Y3 requires.
   Commentary ids embed their version the same way. Found by the additive re-scan test.
2. Group-scoped rules (FEE_RATE_SHIFT, and dominance's informative group) append the
   group id so two groups firing the same rule in one transition cannot collide.

**Pending OPERATOR acceptance:** live install of GQ-018/019 and the two new vertices /
three edges; a scan against real data; thresholds review with the client (defaults are
the spec's, deliberately un-tuned to sample data).

## 13. Round 7 (FIX_SPEC_R7.md, 2026-07-23) — CONVERSATIONAL ASSISTANT ("Ask iPerform")

**What was built.** The capability the client asked for by name: a chat assistant over
the loaded revenue data. The governing principle is enforced end-to-end — **the
assistant chooses which audited query to run and narrates the result; it never
computes, estimates or infers a figure.** Every number in every answer is read from
stored rows returned by catalogued GQ queries; selection/ordering/filtering is
presentation. Commits (ordered): `c5846aa` progress · `57073c6` schema + persistence +
GQ-020/021 · `adc3270` engine + API · `1377993` verification · `0f37a8a` UI ·
(this commit) wrap.

**Architecture (A-stream).**
- **Persistence (Z-A1/A12):** `phx_dm_v2_conversation` + `phx_dm_v2_message`
  (message extended with `guardrail_status`, `guardrail_json`), edges
  `message_in_conversation` / `conversation_for_advisor` (nullable for cross-advisor).
  Writes go through TigerGraphUpsertClient (graph = system of record) plus the
  workflow-CSV local tier; reads via GQ-020/021 with `served_by_tier` recorded.
  10-day rehydration window from `ASSISTANT_HISTORY_DAYS`.
- **Providers (Z-A2):** `AssistantLLM` chain — primary `ASSISTANT_LLM_MODE`
  (default: app `LLM_CLIENT_MODE`; cdao_openai primary in the client env, claude on
  the build box), sequential fallback; a fallback that answers is WARNING-logged and
  recorded in the message's `llm_provider` ("azure (after cdao_openai failed)").
- **Routing (Z-A3/A4):** deterministic rule table FIRST — all ten A3 intents plus
  follow-up inheritance ("what about May?"); entity extraction resolves months,
  advisors and product groups against LOADED reference data only. Stage 2 is a
  constrained LLM fallback that returns a structured `{query, params}` selection
  validated against `query_catalog.json` — non-catalogued names and undeclared
  params are rejected; the model never answers directly and never returns a figure.
- **Context (Z-A5):** deterministic resolution, precedence question > pinned >
  inherited > screen > defaults; each turn stores its resolved parameters; the chip
  label is stored with the turn so context is visible on every answer; Pin freezes it.
- **Facts only (Z-A7):** advice questions get the factual answer plus exactly one
  deterministic limit sentence ("…recommendations aren't something I cover yet"),
  appended after narration; the narrator never sees the advisory phrasing.
- **Honesty (Z-A8):** unloaded month → `NO_DATA` naming the loaded range;
  unroutable/non-domain → `OUT_OF_SCOPE`; guardrail rejection → `BLOCKED`. No gap is
  ever filled from model knowledge.
- **Numeric guardrail (Z-A9):** every narration is validated with the same
  no-invented-figures check the anomaly wording uses (figures must appear in
  `figures_json`; negatives parenthesised). A failing narration falls back to the
  deterministic template (built only from stored figures); stored commentary is
  quoted VERBATIM (validated at publication, never re-narrated).

**Input/output guardrails (Z-A10/A11/A13) — the round's security gap, closed.**
`app/guardrails/client.py` (V1 stack: prompt-injection, jailbreak, PII with
Luhn-gated cards, toxicity, oversize) is now wired in front of the assistant:
`check_input()` runs BEFORE routing, context resolution and any model call.
Injection/jailbreak/toxicity/oversize BLOCK with `GuardrailService.neutral_refusal()`
(new method; V1's `safe_refusal` untouched); PII is REDACTED before storage and
before any provider — the verify script asserts the raw SSN/card/email/phone appears
NOWHERE in persisted messages. Blocked turns stay VISIBLE in the transcript with the
neutral ⛉ GUARDRAIL chip; `guardrail_json` stores `[{category, severity, action}]`
only — never the matched text or rule. `check_output()` additionally screens the
narrative for PII surfacing from data.

**UI (B-stream).** One `AssistantPanel` component, two presentations: the overlay
(420px right-edge float per `04_chat_overlay.png` — content keeps full width,
persists across navigation, collapses to a floating button) and the full-page `/ask`
(per `01_conversational_assistant.png` — grouped conversation rail, scope + tier
pills). Rendering per rule 8a: AI Generated chip on wording ONLY; figures list and
tables never AI-marked; `Ran: <queries>` monospace audit trail; Evidence › and
deep links carry resolved parameters; loading/empty/error and all three A7 statuses
render distinctly.

**Verified HERE** (`scripts/verify_assistant.py` 84/84 OVERALL PASS +
`scripts/verify_assistant_ui.mjs` 7/7): 27 routing fixtures incl. follow-ups; every
number in every fixture answer present in `figures_json` (plus a negative control);
3-turn context inheritance; NO_DATA/OUT_OF_SCOPE honesty; the advice pattern
(exactly one limit sentence); persistence round-trip, rehydration with last context,
10-day window; 12 adversarial + 4 false-positive guardrail fixtures with
instrumentation proving blocked inputs never reach the router or an LLM; overlay
persistence across navigation, collapse/expand, full-page sharing, guardrail chip —
zero console errors. `validate_v2_queries.py` ALL CHECKS PASS (21 queries);
`verify_end_to_end.py` OVERALL PASS (no regression). All of this is sample-set /
local-tier / build-box-model evidence — **not** real-data verification.

**Decisions taken (recorded, not hidden).**
1. **ACCOUNT-number PII exemption:** the V1 PII scanner redacts "account <digits>"
   references, but account numbers are this application's subject matter (rendered on
   every screen, present in stored answers) and A11 explicitly requires "show me
   account 83700968" to pass. The assistant gate drops `PII-ACCOUNT` findings (both
   directions); SSN/card/email/phone/secrets remain enforced.
2. **Refusal wording:** `safe_refusal()` (V1) names matched categories and lectures —
   contrary to A9's "neutral and brief". Added `neutral_refusal()` to
   GuardrailService with the spec's exact wording rather than changing V1 behaviour.
3. **Narration failure → deterministic fallback, not BLOCKED:** A8 says BLOCK on
   validation failure; the deterministic template is built exclusively from stored
   figures, so substituting it (marked non-AI, LLM rejection logged) preserves "never
   display an unvalidated answer" without turning a wording failure into a dead turn —
   the same pattern Round 6 established for anomaly wording. BLOCKED is reserved for
   guardrail rejections.
4. **Cross-advisor totals are never summed:** an all-advisor revenue question lists
   per-advisor stored figures instead of a computed sum — summation would create a
   figure no query returned.
5. **Verbatim stored commentary** is exempt from re-validation at answer time (it was
   validated at publication; `verbatim_stored` recorded on the turn).

**Pending OPERATOR acceptance** (`docs/ROUND7_ACCEPTANCE.md`): live install of the 2
vertices / 2 edges / GQ-020-021 (GQ-020's datetime window needs a live syntax check);
a real conversation against real data on tier 1; cdao confirmed as serving provider
with a logged-fallback drill; the live guardrail probe; advisor-permission scoping
remains DEFERRED (A1) and must be stated in any multi-user demo.

## 14. Round 8 (FIX_SPEC_R8.md, 2026-07-24) — DRIVER METADATA, BASELINE LABELLING, ACCOUNT EVIDENCE

**Context fix first.** The two between-round attribution fixes (DEAL_SIZE; A3 abort →
gross-movement WARNING) had been committed to `prompts/` but never installed at the
live path. `prompts/attribution (1).py` (the newer file) was installed verbatim as
`app/v2/drivers/attribution.py` — diff vs the old module removes exactly the two
described changes; arithmetic untouched (settled). `verify_attribution.py` updated to
assert the new behaviour: legacy bug signature = gross misattribution (DEAL_SIZE now
absorbs what MIX carried), and an over-net BASELINE_LIMITED must complete + reconcile
$0.00 rather than abort. `prompts/` copies left as the operator committed them.

**A — driver metadata from data (the main change).** `phx_dm_v2_driver_cause` gained
`display_name` / `description` / `computation` (cause_id unchanged — permanent
internal key). Full chain propagated: DDL → regenerated schema_catalog +
load_v2_all + 90_drop_all → manifest columns (17 rows) → the single seed in
`app/v2/dataset/builder.py` (shared by sample and real builders; legacy
cause_name/cause_description now MIRROR the new fields so they cannot drift) →
GQ-004 (whole-vertex PRINT; catalog updated; NEEDS LIVE REINSTALL) → both tiers
(local tier returns full rows unchanged). Frontend: new
`lib/v2/driver-causes.tsx` single cached fetch; glossary's hardcoded table DELETED
and rendered from the query; CauseTag, waterfall bars, attribution chips,
earlier-claims, export headers and anomaly threshold phrases all read
`display_name`. Seeded: DEAL_SIZE = "Average Transaction Value" (was a raw id in the
UI), CLAWBACK = "Charge Back". A5 grep: zero driver-name literals left outside seed
files. **Rename proof:** editing a seed display_name and re-reading through the
service returned the new name with zero code changes (fixture-tier proof; live = operator).

**B — baseline transition labelled, shown, excluded from quality signals.**
Identified from data everywhere (earliest loaded month via GQ-002 frontend /
get_months backend — never a hardcoded month). Labelled in all four places: card
(tag + full amber note), walk row (tag + limitation line), chart pill (BASELINE
chip), evidence modal (banner) — neutral INFO treatment, still fully visible.
Excluded from: the MIX self-check (logged as informational `baseline`, not a
warning), the UNEXPLAINED_RESIDUAL anomaly rule, and the build summary failure
count (prints `[baseline — indicative attribution]`). B4: prompt v1.1 — commentary
must open with the limitation; deterministic fallback prefixes it; verified in
v16–v19, every baseline narrative states it.

**Guardrail hardening (from B4 verification).** validate_commentary check 5 now also
rejects any parenthesised figure that does not trace to a computed NEGATIVE value —
parentheses mean negative (rule 8), so "(55.4%)" for a rise is a misstatement. The
check immediately caught a real one (v18: TIMING +7,000 written "($7.0k)"); v18 kept
in history with that transition BLOCKED, v19 regenerated clean: 6/6 PUBLISHED.

**C — account comparison in evidence (rendering only).** attribution `inputs_json`
on NEW/LOST/BASELINE_LIMITED now carries per-account revenue maps + the
classification-rule sentence (rendering data; contribution arithmetic untouched —
recorded as a Decision). Evidence modal shows, for account drivers only, two
side-by-side ranked lists (account, revenue in its active month, product group),
top-20 with totals and "showing N of M", the stated rule
(ACCOUNT_ABSENCE_MONTHS=2, advisor level, recurring lines), and a link into
Transactions filtered to those accounts (new `?accounts=` param, chip + filtered
footer).

**Verified here (sample/local tier — NOT real data):** verify_attribution PASS ·
validate_v2_queries ALL PASS · verify_anomalies --rescan PASS · verify_end_to_end
OVERALL PASS (17-cause model, recon $0.00, MIX ≤8.9%) · verify_assistant 84/84 ·
15/15 Playwright shots zero console errors incl. new shots 14 (baseline labelled
end-to-end) and 15 (account-comparison panel) · commentary v15–v19 additive, v19
latest 6/6 PUBLISHED.

**Not done, recorded:** the client's revised driver specification (eight drivers,
"ineligible = anything starting with 9", broader recurring set, chargebacks limited
to Annuities/Life) CONFLICTS with the CWM PCR Confluence mapping and is UNRESOLVED —
recorded in SOLUTION_GUIDE §10.13, deliberately not coded (FIX_SPEC_R8 §D).

**Pending OPERATOR acceptance** (`docs/ROUND8_ACCEPTANCE.md`): live schema change +
GQ-004 reinstall + reseed (17 rows); real-data rebuild confirming the baseline label
on April→May and MIX 0.1–2.3% on later transitions; client validation of the
account-comparison lists; the driver-spec reconciliation decision.

## 15. Round 9 (FIX_SPEC_R9.md, 2026-07-25) — CLIENT-ENVIRONMENT DEMO FIXES

Five contained defects found running the app in the client environment (real
data, cdao_openai). No taxonomy/eligibility/driver changes (round 10). Commits
78cd968..HEAD, tasks N-A..N-G; all suites re-run green after every fix.

**A (45e6e4a) — account presence excludes ONE_TIME/ADJUSTMENT, per transaction.**
LOST_ACCOUNT fired on Annuities because an annuity-issued commission
(rev_nature=ONE_TIME) counted as billing presence. Presence sets (advisor-level
activity map AND group-level sets) are now built from recurring-nature rows
only; a mixed account stays present via its recurring rows; account drivers
claim only the recurring rows of claimed accounts, so one-time deltas stay with
the ONE_TIME step — never double-counted, never in MIX. On top of the
recurring-CLASS gate (both apply). Settled arithmetic (VOLUME/DEAL_SIZE,
netting, reconciliation) untouched. Fixture: pure one-time, MIXED, and
recurring-then-only-one-time accounts — all worked cases pass, recon $0.00.

**B (350c158) — account-comparison lists.** Three-layer fix: the generated GSQL
loading job had no QUOTE="double", shearing inputs_json at its first comma on
the bulk-load path (claim column parses, lists don't — the exact symptom);
the builder now FAILS the build if an account driver's lists are empty or
don't sum to its claim; the evidence modal logs the exact inputs_json key path
on failure and falls back to the legacy `accounts` key. Sample regenerated.

**C1 (1b8f980) — advisor-scoped conversations.** `advisor_sid` on
phx_dm_v2_conversation (the round's only schema change), set from screen
context at creation; the binding outranks a changed screen advisor;
cross-advisor questions/comparisons decline plainly; GQ-020 + local tier filter
on the attribute; history rail scoped; chat-CSV headers migrate additively.

**C2 (be8e827) — no mislabelling; multi-month decomposes.** The shell passed
loaded-range BOUNDS as a transition (202604→202607); driver_detail matched only
from_month against a range query and labelled one transition's figure with the
wider span. Now: the assistant seeds the latest ADJACENT transition (and the
backend snaps screen-sourced wide spans); driver_detail matches both months;
multi-month questions decompose per adjacent transition with per-transition
labels and stored-endpoint revenues (no computed sums); NO_DATA only for
genuinely-unloaded months.

**C3 (c3e6864) — blocked turns visible.** Chip renders category · severity in
text (never the matched pattern); a missing workflow CSV is created instead of
silently skipping the local-tier copy; a failed /ask keeps the turn visible
locally. Fixture proves the blocked pair in the live payload, the stored
transcript, and GET /assistant/conversations/{id}.

**D (b2778ba) — commentary never empty.** Prompt v1.2 states the sign
convention with correct/incorrect examples (root cause); guardrail-failed
wording regenerates up to COMMENTARY_MAX_ATTEMPTS (3), each attempt validated
and each failure logged; after the last failure the deterministic template
(computed drivers + fixed vocabulary) publishes as PUBLISHED_FALLBACK with a
"Deterministic fallback" tag — never the AI chip (rule 8a), never an empty
panel, guardrail never bypassed. Also fixed: the template itself parenthesised
a positive change-%. Live sample regeneration v20 (claude-haiku, v1.2):
5 PUBLISHED + 1 PUBLISHED_FALLBACK, 0 BLOCKED — the mechanism fired on real
model output.

**E (430ce7a) — judge.** build_llm_client factory routes the judge through the
SAME adapters as the agents; JUDGE_MODEL selects the model within the active
mode (empty = mode default; claude mode keeps claude-sonnet-5); unavailable
state stores the −1.0 sentinel and renders "Faithfulness — (unavailable)",
never 0.00; publication gate asserted independent of the judge.

**F (809e0d5) — glossary order.** display_order was already seeded (1–17,
DEAL_SIZE=2) and GQ-004 sorted; the client sort now sends missing/zero orders
LAST with a name tiebreak, and e2e asserts the query returns all 17 sorted.
Root cause in the client env is a stale 6-column driver_cause seed — reseed is
an operator step.

**Verified here (fixtures/sample/local tier only — NOT real data):**
verify_attribution (legacy repro + R6 + R9A + R9B) PASS · verify_assistant
101/101 · verify_commentary_retry 10/10 · verify_judge 9/9 · verify_anomalies
--rescan PASS · validate_v2_queries ALL PASS · verify_end_to_end OVERALL PASS
(recon $0.00, MIX ≤14.2%, glossary sorted) · tsc clean · capture_evidence
15/15 screens zero console errors.

**Known items:** (1) `verify_ingestion_fixes` "delete-all continues past a
failing entity" fails on the build box — pre-existing at the round-8 baseline
(re-verified in a clean worktree), ingestion untouched this round; round-10
item. (2) One UI-walk run showed transient duplicate-key console errors on the
transactions screen from an accumulated server store; unreproducible after
restart (two clean walks + clean API); stored data verified duplicate-free.

**Pending OPERATOR acceptance** (`docs/ROUND9_ACCEPTANCE.md`): live ALTER +
GQ-020 reinstall + driver_cause reseed; real-data rebuild (fix A) with recon
$0.00 and no LOST_ACCOUNT on annuity-issued rows; populated account lists on a
real group driver; scoped conversation + visible guardrail block on cdao;
commentary regeneration on cdao_openai (never-empty panel); judge on the
working model and the unavailable state on a bad JUDGE_MODEL; glossary order
after reseed.

## 16. Round 10 (FIX_SPEC_R10.md, 2026-07-25) — TAXONOMY, ELIGIBILITY, NEW DRIVERS

**What changed.** A foundation round: (A) the recurring/non-recurring product
taxonomy was re-seeded VERBATIM to the client's corrected hierarchy
(`app/v2/revenue/taxonomy.py` — the single canonical source; the prior
taxonomy came from a wrong Figma screen); classification now keys on a
product's POSITION in that hierarchy (path-scoped ids `rec_*`/`nonrec_*__*`),
never on a name — Annuities, Mutual funds and Cash management exist on BOTH
sides and a name match was exactly the bug. (B) The eligibility rule was
replaced: credited = reason code NULL/empty/`__NONE__` ONLY; every `9…` code
is non-credited except the untouched excluded set (9R/98/99/9H/9X/XX); 91/92/9L
flipped Credited→Non-Credited, so THE CREDITED TOTAL CHANGES BY DESIGN. The
evidence ladder's `less excluded` line now shows its reason-code breakdown.
(C) Two reclassification drivers: INHERITANCE (9G) and HOUSEHOLD (9E), computed
FIRST as carve-outs of the eligibility effect, with ELIGIBILITY redefined as
the movement of all OTHER codes — the three sum exactly to −(Δ non-credited);
provenance DERIVED; the ~6-month cooling-period approximation is noted in code
(no inheritance effective date exists in the extract). (D) CLAWBACK is scoped
to Annuities / Insurance / Life by hierarchy position; reversals elsewhere
reconcile unlabelled. (E) Env Health gained an "LLM connectivity" section —
writer/judge/assistant rows, models-lookup only (never a generation), with the
judge's "model not found in subscription" 404 surfaced before a run. (F) The
new causes are seeded (display_order 4/5, before the ELIGIBILITY remainder)
and the glossary renders them in order; no frontend driver-name literals.

**Commits.** 8225cbe (A) · 0ce93ae (B) · 8218f0e (C) · de0f7ea (D) ·
bbe5dca (E) · wrap commit (docs + commentary v21 + assistant fixture ids).

**Verified here (fixtures + sample + local tier — NOT real data):**
verify_taxonomy 33/33 (incl. a fixture with a recurring AND a non-recurring
Annuities product) · verify_eligibility 25/25 (91 flip proven) ·
verify_new_drivers (9G flip → INHERITANCE +800; 9E flip → HOUSEHOLD; partition
exact; MIX clean) · verify_clawback_scope 12/12 (Equities reversal unlabelled;
LIFE|* gate) · verify_attribution PASS · verify_anomalies PASS ·
verify_commentary_retry 10/10 · verify_judge 9/9 · verify_assistant 101/101 ·
verify_end_to_end OVERALL PASS (19 causes, recon $0.00, MIX ≤13.9%, glossary
sorted 1..19) · commentary v21 published 6/6 (0 blocked; v1–v20 preserved) ·
tsc clean · capture_evidence 15/15 screens zero console errors · judge-404
path proven LIVE (JUDGE_MODEL=gpt-4o-mini → "model not found in subscription").

**Operator-pending (docs/ROUND10_ACCEPTANCE.md):** real-hierarchy path
resolution (dual-name lines STOP the build if ambiguous), credited totals vs
iComp after the 91/92/9L flip, INHERITANCE/HOUSEHOLD sanity on a known
account, the ASSUMED `LIFE` product-code identifier, cdao-side LLM
connectivity rows, live reseed of the changed data seeds + commentary
regeneration.

**Decisions taken while blocked:** unknown product lines default to
NON_RECURRING loudly (absence from every recurring path is a position
decision; recurring is the gating class); the quarterly TIMING story moved to
MAC (A1 has no Alternatives line); the "Life" product code could not be
confirmed against the operator-local real hierarchy — recorded as a data gap,
never guessed silently.

## 17. Round 11 (FIX_SPEC_R11.md, 2026-07-25) — PER-ADVISOR SCOPE, ASYNC PROGRESS, TAXONOMY PATCH, SAMPLE COMPLETENESS

**Commits:** `360b19a` (A: ALTI + PRODUCT_TYPE gate) → `d41cda6` (B/C backend:
per-advisor versions/scans + async) → `95877ec` (B/C frontend: two-button scope
+ overlay) → `b14799f` (D: sample completeness + fixes) → wrap.

### Verified HERE (fixtures + local tier + sample set)

- **A — taxonomy.** `Alternative Investments` (ALTI) added as a NON_RECURRING
  leaf — **classification ASSUMED pending client confirmation** (code comment
  marks it). `resolve_path` now refuses non-`PRODUCT_TYPE` rows loudly
  (`NonProductGridRowError` + stderr); `build_real_data` filters
  NON_CREDITED_REVENUE / PAY_TYPE_SUMMARY rows BEFORE classification and
  registers their products under `nongrid_*` holding lines (OUT_OF_GRID by
  config) so no reason/pay-type name can ever become a product line.
  `verify_taxonomy` [7]: a 42-path fixture of the real hierarchy's distinct
  paths — every PRODUCT_TYPE path classifies with no stop, all 7 non-product
  rows excluded. 13 lines / 35 groups seeded.
- **B — per-advisor versions & scans.** `advisor_sid` added to
  `phx_dm_v2_commentary_version` and `phx_dm_v2_anomaly_scan`, propagated
  DDL → schema_catalog + loading job → manifest → both builders → both tiers.
  Every run creates versions/scans scoped to ONE advisor; "supersede prior
  PUBLISHED" applies WITHIN an advisor; legacy pre-R11 global rows
  (advisor_sid "") stay PUBLISHED until a regenerate-all gives every advisor a
  newer scoped version. `version_id`/`version_no` remain globally unique
  (decision: collision-free ids, totally-ordered history; "A on v24 while B on
  v23" satisfies the independence requirement). GQ-009/010/018/019 updated in
  BOTH tiers (byte-identical envelopes) — **NEEDS LIVE REINSTALL**.
  `verify_per_advisor` 33/33 PASS incl. B4 (figures byte-identical around a
  single-advisor run).
- **C — async + overlay.** `start_generation()` / `start_scan()` run in daemon
  threads building on the existing `_status` dict: POST returns a job id
  immediately; GET status reports phase + "advisor N of M" + new version/scan
  ids on completion; polling is GET-only and a POST during a run returns the
  running job (never re-triggers); jobs survive the browser closing. Frontend:
  shared `useAsyncJob` + non-blocking `JobProgressOverlay` on AI Insights and
  Anomalies; auto-refresh to the new latest version/scan on completion;
  failures stay visible until dismissed; reopening mid-run rejoins. TWO
  clearly-labelled buttons per screen (this advisor / all). Proven headless in
  a real browser (async rescan through the UI, zero console errors).
- **D — sample completeness.** Sample extends to Apr–Jul 2026; a rescan-all
  now fires ALL SIX anomaly rules; 92 + 9L join the reason codes (full
  91/92/9L flip visible); INHERITANCE / HOUSEHOLD / CLAWBACK / mixed-account /
  dual-Annuities stories retained; May→Jun MIX-clean for every advisor.
  SMPL002 Jun→Jul is THE deliberately high-residual transition (~41% MIX:
  asset-growth with no source data + a 9E-flip carve-out overlap) so
  UNEXPLAINED_RESIDUAL is demonstrable — exempted by name and asserted >15%
  in the suites. Commentary regenerated per-advisor: v22/v23/v24, 9/9
  PUBLISHED, 221 evidence records, judge 6 PASS / 3 REVIEW; scans 003–005
  committed as per-advisor demo scans (scan001/002 kept as legacy history).
  Standing principle documented (CLAUDE.md rule 10 + SOLUTION_GUIDE).
- **E — Env Health LLM section** verified live: writer / judge / assistant
  rows all `model-found`; no regression, no rebuild.
- **Suites:** taxonomy, attribution, eligibility, clawback-scope, new-drivers,
  anomalies (+ --rescan), assistant 101/101, judge 9/9, commentary-retry
  10/10, per-advisor 33/33, e2e — ALL PASS; reconciliation $0.00; 15/15
  screenshots + passive walk zero console errors.

### Defect found and fixed while verifying

The assistant's no-invented-figures payload was keyed by figure LABEL; two
figures sharing a label (one account, several same-product rows — first
produced by the new July syndicate data) silently collapsed, making the
guardrail REJECT honest figures. Keys are now uniquified in the service (and
mirrored in `verify_assistant`); `figures_json` itself was always complete.

### Decisions

- Serial per-advisor iteration in regenerate-all / rescan-all (was a 4-wide
  thread pool): keeps "advisor N of M" progress honest and each advisor's
  version independent; acceptable at 10-advisor scale.
- Committed sample now ships per-advisor versions/scans as the demo state;
  the R6 "scan001 is the committed demo scan" decision is superseded — scans
  001/002 remain as legacy-global history (additive, never deleted).
- verify_end_to_end / verify_attribution assert "MIX < 15% everywhere EXCEPT
  the named residual-demo transition, which must be > 15%" — the anomaly rule
  is undemonstrable otherwise; the exemption is by exact (advisor, from, to).

### Operator-pending (docs/ROUND11_ACCEPTANCE.md)

Live reinstall of the 4 changed queries + schema attribute additions; real
hierarchy classification run (incl. ALTI class confirmation with the client);
per-advisor + async behaviour under real latency and cdao; sample rescan demo.

## 18. Round 12 (FIX_SPEC_R12.md, 2026-07-25) — PER-ROLE LLM CONFIG + AUTO-FALLBACK

LLM plumbing only: each of the three LLM roles — commentary **writer**, **judge**
(advisory, R9 E), **assistant** (R7) — now has its own complete optional config
(client-mode, model, deployment, api_version) with a single-retry auto-fallback to
the active default agent LLM. No computed figure was touched; reconciliation
remains $0.00 on every transition (re-verified by e2e).

### Commits

| Hash | What |
|------|------|
| 616b887 | Q-A: per-role keys + shared resolution helper (`app/llm/roles.py`) + .env.example guidance |
| b55047c | Q-B: `build_llm_client` + Azure-shaped adapters take deployment/api_version overrides |
| 810a006 | Q-C: all three roles wired via the helper; auto-fallback; served path recorded |
| af79044 | Q-D: Env Health shows each role's effective config + will-fall-back state |
| dcf703a | Q-C: `scripts/verify_role_llm.py` (32 checks) |
| f7359e3 | Q-D2: ROUND12_ACCEPTANCE (config table + operator checks) |
| (wrap) | Q-E: ROUND12_CHANGED_FILES + this section |

### Key points

- **Keys reused, not duplicated** (spec A): `ASSISTANT_LLM_MODE` IS the assistant's
  client-mode key; `JUDGE_MODEL`/`JUDGE_ENABLED` kept. New keys only for genuinely
  new fields. `JUDGE_MODEL` alone (or `ASSISTANT_LLM_MODE` alone) keeps the exact
  R9/R7 code path — those keys predate R12 and participated in the old behaviour,
  so alone they must not change it.
- **One resolution helper** (`resolve_role_config`) shared by writer, judge,
  assistant, and Env Health — per-field inheritance from the active mode; the
  deployment-vs-model best-effort rule (Azure/cdao route by deployment) lives once.
- **Auto-fallback**: `RoleLLM` wraps a configured role's client; construction or
  first-call failure logs a WARNING naming the role and retries ONCE with
  `build_llm_client(LLM_CLIENT_MODE)`. Served path (`role_config` /
  `fallback_agent_llm` / `unavailable`) is recorded: `llm_path` on commentary and
  judge evaluations, `served_path` + provider-label suffix on assistant turns.
- **Assistant chain preserved**: the R7 sequential chain runs first, unchanged;
  the R12 default retry is the FINAL link before the honest decline.
- **Honest total-failure states unchanged**: judge → UNAVAILABLE sentinel (-1.0,
  REVIEW, never 0.00, never blocks); writer → R9 D deterministic template;
  assistant → honest decline. A judge whose fallback would land on mock returns
  UNAVAILABLE (mock cannot judge). Publication stays gated only by the
  deterministic guardrail.
- **Env Health (D)**: per-role EFFECTIVE mode/model/deployment/api_version +
  reachability of that exact config + "configured model unreachable → will fall
  back to <default agent model>" — no secrets (verified programmatically).

### Verification (build box; cdao unreachable — operator checks in ROUND12_ACCEPTANCE)

verify_role_llm 32/32 (all-empty regression ×3 roles, role_config use, fallback w/
WARNING ×3 roles, honest total-failure states, Env Health incl. no-secrets);
existing suites re-run clean: attribution PASS, taxonomy PASS, eligibility PASS,
new_drivers PASS, clawback_scope PASS, per_advisor 33/33, judge 9/9,
commentary_retry 10/10, assistant 101/101, anomalies PASS, e2e OVERALL PASS with
reconciliation $0.00; frontend `tsc --noEmit` clean; .env.example ↔ settings
cross-check 132/132.

### Post-round defect fix (Q-F) — glossary display_order sorted as STRING

The R8/R9 glossary order defect (Volume, Fee Rate, Discount… before Deal Size =
"1","10","11",… lexicographic). Everything in the repo was already INT and
numerically sorted (DDL, schema_catalog, manifest, sample CSVs, seeds, local
tier, e2e) — the surviving exposure was a live graph installed before
display_order became INT: its STRING attribute makes GQ-004's `ORDER BY`
lexicographic, and the service passed that order straight through to the UI.
Fix (type/sort only — no display_order VALUE or display_name changed):
service re-imposes numeric order on every serving path (missing/invalid last,
name tiebreak — R9 F semantics); local-tier `_int` coerces via float so numeric
TEXT sorts numerically; frontend key is an explicit `Number()`; GQ-004 header
documents that a STRING-typed live install must be reinstalled from the current
DDL. Verified: new `scripts/verify_glossary_order.py` 7/7 (incl. a simulated
STRING-typed lexicographic tier-1 result restored to 1..19); e2e OVERALL PASS
(glossary sorted 1..19, reconciliation $0.00); attribution / anomalies /
per_advisor 33/33 / role_llm 32/32 all PASS; `tsc --noEmit` clean.

## 19. Round 13 (FIX_SPEC_R13.md, 2026-07-25) — CDAO GPT-5 COMPATIBILITY

Small surgical round: make the cdao client GPT-5-compatible (gpt-5.x incl.
mini/nano) across the main LLM and all three roles. LLM plumbing only — no
computed figure touched; reconciliation stays $0.00. All switches are
config-driven; the model name is never inspected.

**A — api_version omitted when empty (2772d3f).** `build_cdao_openai_client`
now calls `openai_azure_client(workspace_id=...)` WITHOUT the api_version
argument when the effective api_version is empty/None/blank; non-empty passes
exactly as before (GPT-4 intact). The per-role builder and the embedding
adapter funnel through the same function, so "role override empty AND
CDAO_API_VERSION empty ⇒ omitted" holds everywhere. Empty config is the
operator's GPT-5 signal.

**B — temperature, default 1 (712aea1).** New `CDAO_TEMPERATURE` (main LLM)
and `WRITER_/JUDGE_/ASSISTANT_TEMPERATURE` (float, default 1 — GPT-5 rejects
< 1). `RoleLLMConfig` gains `temperature`; it is always present so it NEVER
counts toward R12 `configured_fields` (all-empty role config stays
byte-identical to R12). Threaded through `build_llm_client` into both
chat-completions adapters (`RealLLMClient`, `CdaoOpenAILLMClient`), the
judge's legacy R9 E path and the assistant chain's primary link; the
unconfigured writer keeps the main singleton (CDAO_TEMPERATURE).

**C — max_tokens removed (8569ff6).** Removed from both chat-completions
creates (the spec's line ~200/202 is `RealLLMClient.generate` — both Azure
OpenAI chat-completions adapters carry identical GPT-5 constraints, so B+C
apply to both; decision recorded in PROGRESS). No token cap reintroduced. The
Anthropic `messages.create` keeps its required `max_tokens=1024` — asserted to
be the only one left in `app/llm/client.py`.

**D — Env Health per-role probe on the corrected path (1eaee0b).** The
UNAVAILABLE role rows came from the probe building the client the old way. It
now constructs through the same corrected path (api_version omitted when
empty, temperature from config) and, on cdao only, probes with a minimal
one-word `chat.completions.create` (no max_tokens, output discarded) — the
only check that proves a GPT-5 deployment actually serves completions.
Non-cdao modes keep the R10 cheap models lookup. Read-only, no secrets.

**Verification (fixtures — cdao unreachable here).** New
`scripts/verify_gpt5_compat.py`: 34/34 PASS via a fake `cdao` module capturing
construction and create kwargs — empty api_version ⇒ workspace_id-only;
non-empty passed; temperature (default 1, per-role override honoured) + NO
max_tokens on main + writer + judge + assistant + real-mode adapter; Anthropic
unchanged; probe on the corrected path; JUDGE_MODEL-alone /
ASSISTANT_LLM_MODE-alone still non-R12. Regression re-run all PASS:
role_llm 32/32, judge 9/9, commentary_retry 10/10, assistant 101/101,
glossary_order 7/7, taxonomy, eligibility, new_drivers, clawback_scope,
per_advisor 33/33, anomalies, e2e (reconciliation $0.00 on all three sample
advisors); frontend `tsc --noEmit` clean; .env.example ↔ settings cross-check
136/136 keys.

**Operator (real cdao):** docs/ROUND13_ACCEPTANCE.md — GPT-5 deployments with
empty `*_API_VERSION` show all three roles green in Env Health; a GPT-4 role
with an api_version set still works; commentary/judge/assistant run end-to-end.

## 20. Round 14 (FIX_SPEC_R14.md, 2026-07-26) — LLM-BASED GUARDRAIL LAYER (DEFENSE IN DEPTH)

Security round: the regex pre-filter alone (R9) misses paraphrased attacks
("what were you told to do", roleplay jailbreaks). Round 14 adds a model-based
intent classifier between the regex layer and the router, hardens the
assistant's own system prompt, and extends the output check — four layers,
each independent. Assistant guardrail plumbing only; no attribution, taxonomy,
eligibility or computed figure touched; reconciliation stays $0.00.

*Session note:* the build session died mid-round (Codespace stop) after
S-A..S-H had landed but before PROGRESS.md was truthed up. Session 15 resumed
per §0.1 (git as truth), committed the pending S-H fixture CSVs, and completed
the round wrap (this section, S-I, ROUND14_ACCEPTANCE.md).

**S-A — `guardrail` LLM role (038980f).** Fourth role in `ROLES` with the full
R12 per-field resolution (`GUARDRAIL_LLM_MODE/MODEL/DEPLOYMENT/API_VERSION/
TEMPERATURE`) and R13 GPT-5 handling inherited unchanged. Env Health gains a
"guardrail classifier" row (effective config + reachability, no secrets); mock
mode is labelled as the deterministic keyword classifier.

**S-B/S-C — input classifier + decision policy (e2050b9).**
`intent_classifier.py` makes ONE constrained guardrail-role call per turn
returning strict JSON `{category, confidence, reason}` (example-rich system
prompt in `system_prompts.py`); any failure raises `ClassifierUnavailable` —
never a guessed classification. `screen_input` runs regex FIRST (PII redacted
before the classifier ever sees the text), then the classifier on the redacted
text, then the config policy: block categories at `confidence >=
GUARDRAIL_BLOCK_THRESHOLD` (default 0.5) BLOCK; `off_scope_use` becomes a
polite OUT_OF_SCOPE decline BEFORE routing. The classifier can only ADD a
block — it never downgrades a regex result. `GUARDRAIL_LLM_ENABLED` gates only
layer 2; `GUARDRAILS_ENABLED` gates the stack (both loud).

**S-D — hardened narrator prompt (e2050b9).** Scope-locked, no instruction
reveal, no arbitrary execution, user/graph content treated as data — the
backstop layer if everything upstream degrades.

**S-E — fail-safe (e2050b9).** Classifier outage ⇒ `CLASSIFIER_DEGRADED`
finding + `GUARDRAIL DEGRADATION` warning; the regex result stands and the
turn proceeds only to the scoped router under the hardened prompt. Never fails
open, never silently.

**S-F — output leak check (e2050b9).** `screen_output` additionally blocks
system-prompt/instruction-fragment leaks (deterministic fragment check — no
LLM needed) on top of the existing numeric/PII gates; leaking text is never
displayed.

**S-G — visibility (e2050b9 + existing R9 chip).** Persisted findings carry
`{category, severity, action}` ONLY — the classifier's `reason` never leaves
the server log. The payload is shape-identical to R9, so the existing
⛉ GUARDRAIL chip renders classifier blocks with category + severity and no
frontend change was needed. Proven by fixture §6 and by the persisted sample
conversations (0c52ad7).

**S-H — verification (3ca2685, 9c2727d, 0c52ad7).** `verify_guardrail_llm.py`:
54/54 — paraphrased attacks BLOCK via the mock classifier, benign revenue
questions PASS, regex layer independent, no-downgrade, PII-before-classifier,
forced-outage fail-safe logged and never open, visibility payload clean,
output leak check, Env Health row, thresholds honored. `verify_role_llm` 5.1
updated for the additive 4th role row (32/32). Live-run fixture conversations
(attack blocked / benign declined / honest NO_DATA) committed to the sample
set per CLAUDE.md §3.10.

**S-I — round wrap (this commit).** `docs/ROUND14_CHANGED_FILES.md`
(git-derived 1550f74..HEAD, additive-config conflict notes, operator-local
excluded) + `docs/ROUND14_ACCEPTANCE.md` (operator real-cdao checks: live
guardrail role config, live paraphrased-attack blocks, Env Health row green,
fail-safe drill, rollback flags).

**Verified here:** verify_guardrail_llm 54/54; assistant 101/101; role_llm
32/32; gpt5_compat 34/34; per_advisor 33/33; taxonomy, eligibility,
new_drivers, anomalies all PASS; end-to-end PASS with reconciliation $0.00 on
every advisor × transition. **Operator-pending:** everything in
ROUND14_ACCEPTANCE.md (real cdao guardrail deployment).

## 21. Round 15 (FIX_SPEC_R15.md, 2026-07-26) — CLASSIFIER TUNING, REGEX TOGGLE, DRIVER-MONTH, PIN REMOVAL

Three live client-environment bugs, fixed without weakening the R14 stack.

**U-A / U-A3 — classifier boundary (da26861).** The real cdao classifier was
blocking "show me the revenue drivers" as prompt_injection. CLASSIFIER_SYSTEM
rewritten with the hard boundary — the classifier polices attacks on the
ASSISTANT (its instructions/scope/safety) and arbitrary data access, and must
NEVER block a request to SEE the loaded revenue data — plus 21 worked examples
pairing the exact bug phrasings with `safe` and the paraphrased attacks with
their categories, and the verbatim when-in-doubt-choose-safe rule.
GUARDRAIL_BLOCK_THRESHOLD untouched (A2: fix the prompt, not the threshold).
The mock classifier holds the same boundary: every/all-advisors blocks only
with a raw-data noun (or dump/export), so "which advisor had the biggest drop"
is safe while "dump every advisor's account rows" blocks; a trailing-\b bug
that let "new instructions: …" through was fixed.

**U-B — GUARDRAIL_REGEX_ENABLED (eceb7e8).** Default true (R14 behaviour
byte-identical). false demotes ONLY the regex PI-*/JB-* pattern BLOCK findings
to FLAG (audit kept) — block decisions become classifier-only. PII REDACTION
STAYS ACTIVE regardless (implemented option (a) of spec B: redaction is cheap
and safe; only the injection/jailbreak pattern matching is bypassed); the
IV-LENGTH oversize check also stays. Fail-safe intact: regex off + classifier
down ⇒ scoped router under the hardened prompt, degradation flagged + logged,
never full-trust. Posture surfaces on the Env Health guardrail row
(`regex_layer`) and in a per-turn log line.

**U-C — single-month driver questions (e009cde).** Drivers need a transition:
WHY_CHANGE/DRIVER_DETAIL naming one LOADED month M now resolves M → next
loaded month (prev → M when M is last) — "revenue drivers for April 2026"
returns April→May drivers; July (last) returns June→July. The transition is
stated in the answer (deterministic text, figure labels, context chip).
NO_DATA remains only for genuinely unloaded months; an absent/ambiguous month
keeps the latest-transition default. Other intents keep prior→M ("what
changed in June" reads May→June). Router additionally learned "what changed
…" and "compare April and May" (they previously fell through to OUT_OF_SCOPE).

**U-D — transition-pinning REMOVED (e009cde).** The pin's lifecycle bug class
is deleted, not repaired. Frontend: pinned state, setPinned, Pin button and
pinned chip removed; honest header "Scoped to <advisor> · Apr 2026–Jul 2026 ·
credited". Backend: resolve() precedence is question > inherited > screen >
default; ask() lost the pinned param; scope_json is written empty — the
COLUMN stays in the schema (no schema change). The R9 advisor binding and
R7/R9 multi-turn inheritance are unchanged and matrix-verified.

**U-F — verification (135731f).** `scripts/verify_round15.py`: 25/25 PASS,
matrix read from the data (3 advisors × 4 months): legit questions 31/31
answered end-to-end + mock/real-template contracts; R14 attack set 14/14
blocked with correct categories; 7/7 near-miss pairs; regex toggle 7 checks
(pattern skip, PII-still-redacted, classifier-blocks, fail-safe, Env Health
posture both ways); driver-month 12/12 + unloaded NO_DATA 3/3; pin removal
statics + one-conversation month walk 12/12 (no stale transition) + scope 3/3
+ advisor switch + R9 decline; inheritance 3/3.

**Verified here:** verify_round15 25/25; assistant 101/101 (multi-turn fixture
moved to the R15 C anchoring); guardrail_llm 54/54; role_llm 32/32;
gpt5_compat 34/34; per_advisor 33/33; judge 9/9; commentary_retry 10/10;
glossary 7/7; attribution, taxonomy, eligibility, new_drivers, clawback,
anomalies all PASS; e2e PASS, reconciliation $0.00 on every advisor ×
transition; tsc clean; headless UI walk 7/7 zero console errors, scope header
renders, no Pin control. Test-run chat CSVs reverted — committed sample demo
state unchanged. **Operator-pending:** docs/ROUND15_ACCEPTANCE.md (real cdao
classifier under the retuned prompt, live UI walk, regex-toggle drill).

### 21.1 R15.1 — get_commentary latest-version resolution (live bug, reinstall required)

Client symptom: commentary rows present (advisor_sid correct, version_id
"v1") but AI Insights shows "No commentary generated for this advisor yet".
Root cause: the LIVE-INSTALLED get_commentary summed version_no across all
matching versions (advisor's own + legacy global advisor_sid=="") when
resolving version_id="", overshooting to a non-existent version. The repo's
GQ-009 has declared MaxAccum since creation (git: 8d440ab, d41cda6) — the
summing copy is an install-side divergence — so the fix (a) documents the
MAX-never-SUM contract in the query header, (b) removes the second latent
fragility by resolving the winning vertex's OWN version_id in a second pass
(GQ-018 pattern; PRIMARY_ID_AS_ATTRIBUTE="true") instead of reconstructing
"v"+to_string(@@latest_no), and (c) mandates the live reinstall
(ROUND15_ACCEPTANCE.md §8). Sibling audit: GQ-010/019 order-by only, GQ-018
MaxAccum two-step, GQ-017 no latest resolution, both local-tier resolvers
strict max — no other summing latest-resolver exists.

Verification: scripts/verify_commentary_version.py 16/16 — fixture store with
the exact client shape (PUBLISHED legacy global v1 + advisor v2 SUPERSEDED +
v3 PUBLISHED; sum 4 overshoots max 3): resolution returns v3's rows and the
summed id v4 matches nothing (the symptom); sample regression: all 3 advisors
non-empty with resolved_version == true max (v22/v23/v24); GQ-009 file
contract (MaxAccum, no summing accumulator, vertex-id second pass);
repo-wide no-summing-latest scan. validate_v2_queries ALL PASS; per_advisor
33/33; assistant 101/101; commentary_retry 10/10; judge 9/9; e2e PASS with
reconciliation $0.00. No figure, version-model or schema change.

## 22. Round 16 (FIX_SPEC_R16.md, 2026-07-26) — CRITICAL: PER-ADVISOR VERSION/SCAN PRIMARY-KEY COLLISION

**Symptom:** after "Generate all advisors" / "Rescan all", AI Insights and
Anomalies showed NOTHING for every advisor except the last (operator confirmed
only 2 version rows in the live graph, both the last advisor's).

**Root cause (confirmed from schema + code, two coordinated layers):**
1. **WRITE (the root cause):** `phx_dm_v2_commentary_version` has
   `PRIMARY_ID version_id` and the workflow wrote `version_id = f"v{no}"`
   from a GLOBAL sequence; `phx_dm_v2_anomaly_scan` identically wrote
   `scan_id = f"scan{n:03d}"`. In a bulk run every advisor received the SAME
   primary id, so each advisor's vertex upsert OVERWROTE the previous — only
   the last advisor's version/scan vertex survived. Commentary/anomaly ROWS
   survived (their ids embed the advisor) but had no version/scan to resolve.
2. **READ (kept, not reverted):** the R15.1 SumAccum→MaxAccum fix in
   get_commentary is correct and KEPT — it was necessary but not sufficient,
   because the write collision starved it of data.

**Fix:**
- `version_id = f"v{version_no}|{advisor_sid}"`, `version_no` a PER-ADVISOR
  sequence (`_latest_version_no(graph, advisor_sid)` = max over the advisor's
  own versions + legacy global ""); `scan_id = f"scan{n:03d}|{advisor_sid}"`,
  scan number per advisor (`_next_scan_id(graph, advisor_sid)` via
  get_anomaly_scans — also fixes the old store-only read that pinned tier 1
  at scan001). Ids can now NEVER collide across advisors, even if a stale
  sequence read repeats a number.
- Every dependent id (commentary_id, evidence_id, evaluation_id "|j1",
  anomaly_id) is BUILT FROM the version/scan id and inherits the scoped
  format with no further change; edges/status payloads/CSV rows carry it
  through the same constructions. Frontend URL-encodes version ids (they now
  contain "|"); anomaly URLs were already encoded.
- Supersede reads versions through get_commentary_versions (works on BOTH
  tiers, previously local-store-only) and supersedes ONLY the advisor's own
  prior PUBLISHED versions; legacy global "" versions still supersede only on
  a regenerate-ALL (R11 semantics preserved).
- GQ-009/010/018/019: per-advisor latest resolution confirmed (filter first,
  MaxAccum second, id read from the winning vertex); headers now state the
  contract and the scoped id formats. NEEDS LIVE REINSTALL (with R15.1).
- **No schema ALTER:** PRIMARY_ID columns stay STRING; only the VALUE format
  changed. Confirmed in ROUND16_ACCEPTANCE §3.

**Migration (operator):** the live graph holds collided vertices — targeted
clear of anomaly/anomaly_scan/commentary_evaluation/commentary/
commentary_version (+ automatic edge removal), CSV header-only reset of the
dual-persistence files, then regenerate-all + rescan-all. Exact steps and a
6-step acceptance drill in docs/ROUND16_ACCEPTANCE.md.

**Verification (fixtures/local — the bug needs a multi-advisor bulk run):**
scripts/verify_round16.py 43/43 PASS on a temp copy of the sample set:
generate-all → 3/3 advisors keep their own PUBLISHED version with distinct
scoped ids and get_commentary returns rows for EVERY advisor; generate-all
twice → 2 versions per advisor (latest PUBLISHED, prior SUPERSEDED,
version_no +1 within the advisor); rescan-all → 3/3 advisors keep their own
scan and get_anomalies resolves per advisor; single-advisor generate/rescan
leaves the others byte-identical; zero dangling references (commentary_in_
version edges, evidence version suffixes, judge evaluations, anomaly_in_scan
edges); scoped ids globally distinct while version numbers repeat across
advisors (the point of per-advisor sequences). All existing suites re-run
PASS: per_advisor 33/33, anomalies, commentary_version 16/16, attribution,
taxonomy, eligibility, new_drivers, clawback, judge 9/9, retry 10/10,
glossary 7/7, assistant 101/101, role 32/32, gpt5 34/34, guardrail 54/54,
round15 25/25, e2e reconciliation $0.00. tsc clean. Committed sample demo
state untouched (verification runs in a temp copy; test chat CSVs reverted).

**Decisions:** (a) legacy sample versions/scans keep their old-format ids —
the readers resolve old and new formats identically (id read from the vertex,
never parsed), so no sample regeneration was needed; (b) commentary_evaluation
is included in the migration clear because its rows reference cleared
commentary/version ids; (c) supersede switched from store-only to query-based
so tier 1 gets the same per-advisor supersede behaviour the local tier always
had.
