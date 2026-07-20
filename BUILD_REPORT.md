# BUILD REPORT — iPerform V2: Revenue Trends & AI Commentary

Build date: 2026-07-20 · Built autonomously per CLAUDE.md. Status: **in progress — Phase 6**.
(This file is updated as the build proceeds; the final summary lands in Phase 7.)

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
| … | (updated as later commits land) |

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

### Phase 6 — UI (in progress)
Shell (navy top nav, Results sub-nav, sample-data banner, advisor context bar
with persisted selection, honest tier pill) + v2 design tokens + shared
formatter (negatives parenthesised everywhere) committed. Screen builds running
in parallel subagents; verification pending.

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
