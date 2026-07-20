# `.store` → `run_query` Migration — BATCH ONE Report

**Date:** 2026-07-10 · **Branch:** `store-migration-batch1` · **Status:** COMPLETE (all 9 Batch One files + prerequisite migrated, verified, committed)

## Top summary

**Mission:** migrate the Batch One readers off `get_graph_client().store` (which always resolves
to the tier-4 in-memory mock, even in real mode) onto `get_graph_client().run_query(...)`, so the
tiered client can serve them from real TigerGraph (tier 2) on the client machine. Mock remains a
LOGGED fallback only. Verified here against the mock tier (tier 4) — tier-2 serving is a
client-machine follow-up by design (no reachable TigerGraph in this Codespace; see
TIGERGRAPH_PREFLIGHT.md — GSE ID-store corrupt, do not attempt local TG).

### Commits (ordered)

| # | Commit | File(s) | Notes |
|---|--------|---------|-------|
| 1 | `1e7aeb3` | `app/graph/queries/common.py` | Shared resolver via GQ-002 + `run_catalog_query` guard helpers |
| 2 | `9388e14` | GQ-051/052/053 gsql + catalog + mocks + validator | 3 new queries — **NEEDS LIVE INSTALL** |
| 3 | `e95badb` | `app/revenue/analytics.py` | Byte-identical output across 7 scope/period cases |
| 4 | `71d7b92` | `app/scope/rollup.py` (+ `scope_advisor_placements` helper in common.py) | Top/bottom via GQ-007, period-windowed, disjoint invariant |
| 5 | `f3d1617` | `app/scope/dashboard.py` | Markets/peers/recent-tx/names via GQ-051/053; period wired to rollup |
| 6 | `5c39f32` | `app/revenue/trend_explorer.py` | Byte-identical output across 6 dimension/granularity cases |
| 7 | `fe88894` | `MIGRATION_REPORT_BATCH1.md` | Interim report |
| 8 | `3182912` | `app/peers/benchmarking.py` | GQ-002/008/053; identical A001/A020 across scopes |
| 9 | `fc4194b` | `app/api/routers/hierarchy.py` | GQ-002/053; tree/entity-names/resolve identical |
| 10 | `3986a3e` | `app/api/routers/advisor360.py` | GQ-024/009; identical A001/A020/A044 |
| 11 | `505b514` | `app/services/pipeline_trace_service.py` | GQ-009/051; traces identical |
| 12 | `9bb03af` | `app/client360/service.py` | GQ-010/011/012/024/029; identical except latent Prediction-lineage fix |
| 13 | *(this commit)* | `MIGRATION_REPORT_BATCH1.md` | Final report |

### Parallelization actually used

- **Step 0 (serial, alone):** `app/graph/queries/common.py` — nothing else started until the
  shared resolver was migrated, verified (7 scope cases, old-vs-new MATCH) and committed.
- **Serial chain (main thread, in order):** GQ-051/052/053 authored first (shared by the whole
  chain, avoids duplicate/conflicting query invention) → `analytics.py` → `rollup.py` →
  `dashboard.py`. `trend_explorer.py` after analytics (depends only on it).
- **Step 2 (parallel):** 5 subagents, one per file (`hierarchy.py`, `benchmarking.py`,
  `advisor360.py`, `client360/service.py`, `pipeline_trace_service.py`), launched concurrently.
  Guardrails: agents may NOT commit, may NOT edit `query_catalog.json` or mock modules, may NOT
  create new queries (they report "NEW QUERY NEEDED" back instead — prevents number collisions
  and hallucinated GSQL). Main thread reviews, re-verifies, and commits each serially.

### New queries created — ALL `NEEDS LIVE INSTALL + VERIFY ON CLIENT MACHINE`

| ID | Name | Why | Reader file(s) served | Flag |
|----|------|-----|----------------------|------|
| GQ-051 | `get_scope_transactions` | No catalog query returned raw per-transaction rows with advisor+product+household context; GQ-004/005 only return pre-aggregated sums, but the readers compute month/channel/business-line/geo/child dimensions from raw rows | analytics.py, trend_explorer.py, dashboard.py (recent transactions) | **NEEDS LIVE INSTALL** |
| GQ-052 | `get_product_category_map` | No catalog query exposes the product→subcategory→category classification chain as a lookup | analytics.py, trend_explorer.py | **NEEDS LIVE INSTALL** |
| GQ-053 | `get_scope_advisor_placements` | No catalog query returns per-advisor ancestor placement (branch/state, market, region, division, firm, ids+names); needed for geography, child-scope grouping, market ranking, peer-sibling resolution, dimension slice maps | analytics.py, rollup.py, dashboard.py, trend_explorer.py | **NEEDS LIVE INSTALL** |

All three: written to `docs/tigergraph_foundation/tigergraph/queries/`, follow SYNTAX V1 rules
(type-first params, vertex-type traversal targets with edge aliases, one hop per SELECT), reuse
the exact scope-resolution block from the already-live-verified GQ-005, added to
`query_catalog.json` with status `created-batch1-NEEDS-LIVE-INSTALL`, added to
`install_all_queries.gsql` and `tests/query_cases.json`, mock implementations registered via
`@mock_query` with the same aliased-attribute row shape the GSQL `PRINT vset[... AS alias]`
produces. `docs/tigergraph_foundation/scripts/validate_package.py` updated (query count 50→53;
the new status accepted alongside the existing one) — **STATUS PASS** after the change.

### Client-machine follow-ups (cannot be verified in this Codespace)

1. Install GQ-051, GQ-052, GQ-053 on the live graph (`install_all_queries.gsql` includes them)
   and run each once (test params in `tests/query_cases.json`).
2. Confirm `served_by_tier == 2` for the migrated pages (Executive Dashboard, Revenue Analytics,
   Revenue Trend Explorer + the Step-2 pages) — in the Codespace everything is served by tier 4
   by design, and the rule-4 "served by MOCK tier while GRAPH_CLIENT_MODE=real" warnings firing
   here is expected, not a failure.
3. Re-check the A001 top/bottom acceptance test against live data (passes against mock data —
   see below).
4. Known real-vs-mock membership nuance in existing GQ-007: the GSQL only ranks advisors that
   HAVE ≥1 transaction in the window (edge traversal); the mock scores all resolved advisors
   (zero-revenue advisors included). Shape is identical; membership can differ for advisors with
   no transactions in the window. Existing behavior, not introduced by this migration — noted
   for the reviewer.
5. Known mock-shape nuance in existing GQ-007 mock: it returns flat row dicts
   (`{advisor_id, advisor_name, revenue, transaction_count}`) where the real tier prints vset
   rows (`{v_id, attributes:{...}}`). Readers migrated in this batch normalize with
   `row.get("attributes", row)` so both shapes work. Flagged rather than "fixed" to avoid
   touching a mock that other verified code may rely on.

### Acceptance test — the A001 top/bottom bug (§7)

**Where top/bottom is actually computed:** traced to `app/scope/rollup.py`
`ScopeRollupService._top_advisors` (the Executive Dashboard consumes `rollup["top_advisors"]` /
`["bottom_advisors"]` via `app/scope/dashboard.py`).

**Root cause:** ranking was computed over per-advisor **feature snapshots** (`SnapshotStore`),
skipping advisors with no snapshot. On a machine where only some advisors have snapshots (e.g.
only A001), top-8 and bottom-8 collapse onto the same tiny set → A001 in both. (In this
Codespace all 60 advisors have snapshots, so the overlap didn't reproduce at FIRM scope here —
the fix removes the dependency entirely.)

**Fix:** ranking now comes from **GQ-007 `get_top_bottom_advisors`** — real transaction revenue
over the full resolved advisor universe on the graph, windowed by the selected Period (the Period
control is now wired through `dashboard() → rollup.summary(period=...)` → a real
start/end DATETIME window anchored to the scope's data months). Display fields are enriched from
snapshots (`revenue_ltm`, AUM, AGP status — anchored values untouched); a new `period_revenue`
field carries the actual ranking basis. A disjointness invariant is enforced: if the scope holds
fewer advisors than two full lists, the ranked universe is split in half rather than showing the
same advisors in both lists.

**Verified against mock data** (real command output in the per-file section):
FIRM/F001 (ALL and LTM), DIVISION/D01 (YTD), MARKET/M01, ADVISOR/A001 — overlap NONE in every
case; A001 never in both. Mock data was sufficient to confirm the invariant and the period
wiring (LTM vs YTD produce different period_revenue figures); confirming against live-graph
data volumes is client-machine follow-up #3.

### Deferred writes

`app/recommendations/lifecycle.py` is **not in Batch One** (§5 file list) — nothing was touched
there. Its `.store.remove_vertex(...)` writes remain as-is per rule 5 (no real-TigerGraph delete
path exists yet); they are Batch Two scope.

---

## Per-file sections

### 0. `app/graph/queries/common.py` — shared resolver (prerequisite) — commit `1e7aeb3` (+ helper in `71d7b92`)

- **`.store` usage found:** `resolve_scope_advisor_ids(store, ...)` — the shared traversal helper
  (FIRM→divisions→regions→markets→advisors, BRANCH/MARKET via in-edges) called by many services
  with `get_graph_client().store`.
- **Mapping:** new graph-facing entry point `resolve_scope_advisor_ids_graph(graph, scope_type,
  scope_id)` → existing **GQ-002 `get_scope_descendants`** (`entity_type="ADVISOR"`), parsing
  `advisor_descendants[].v_id`. The original store-based function is intentionally kept unchanged:
  (a) it IS the logged fallback, (b) the tier-4 mock implementations themselves use it —
  rewiring those would recurse (mock query → resolver → run_query → same mock query).
- **New shared helpers:** `run_catalog_query(graph, name, params)` — returns `results` or `None`;
  logs WARNING on raise/error-envelope (fallback never silent) and WARNING when
  `served_by_tier == 4` while `GRAPH_CLIENT_MODE != mock` (rule 4). `graph_fallback_store(graph)`;
  `scope_advisor_placements(graph, ...)` (GQ-053, added with the rollup commit).
- **Fallback log lines:** `"run_query(%s) raised %s: %s — falling back to local store traversal"`,
  `"run_query(%s) returned an error envelope (%s) — falling back to local store traversal"`,
  `"run_query(%s) served by MOCK tier (4) while GRAPH_CLIENT_MODE=%s — expected in the Codespace..."`.
- **Verification:** old vs new resolver for FIRM/F001, DIVISION/D01, REGION/R01, MARKET/M01,
  BRANCH/B001, ADVISOR/A001, ALL → counts 60/24/12/6/3/1/60, **MATCH** on every scope
  (sorted-set order). GQ-002 gsql checked against the three V1 defect classes: clean.
- **GQ-002 V1 check:** type-first params ✓, vertex-type targets with edge aliases ✓ (set
  variables appear only as traversal *sources*, which is valid V1), one hop per SELECT ✓.

### 1. `app/revenue/analytics.py` — commit `e95badb`

- **`.store` calls found → mapping:**
  - `resolve_scope_advisor_ids(self._store, st, scope_id)` (×2: main + per-child) → GQ-002 via
    `resolve_scope_advisor_ids_graph`.
  - `advisor_transactions(self._store, [aid])` (per advisor) + per-tx
    `out_ids("phx_dm_transaction_for_product", tx)` + `vertex("phx_dm_revenue_transaction", tx)`
    → **GQ-051 `get_scope_transactions`** (one scope-wide call; rows carry advisor_id/product_id;
    tx→product map filled from the same rows).
  - `_build_product_category_map` (`all_vertices` product/category + `out_ids`
    product_in_subcategory / subcategory_in_category) → **GQ-052 `get_product_category_map`**.
  - geography walk (`out_ids advisor_in_branch` + `vertex branch .state`) → **GQ-053
    `get_scope_advisor_placements`** (`branch_state`).
  - by_child walk (`in_ids` division_in_firm / region_in_division / market_in_region /
    advisor_in_market + `vertex` name lookups) → GQ-053 grouping (advisors grouped by their
    placement's immediate-child id/name).
- **Output keys unchanged:** `scope_type, scope_id, kpis{total_revenue, transaction_count,
  advisor_count, avg_revenue_per_advisor, months_covered, top_channel, top_business_line,
  period}, comparison{prior_revenue, change_pct, basis}, comparison_prior_period{...},
  monthly_trend, monthly_trend_prior, by_channel, by_business_line, revenue_drivers,
  by_geography, by_child, evidence{source, advisor_ids_resolved, computation}`.
- **Fallback:** every graph read has the original store path behind a `logger.warning`
  (`"...unavailable ... falling back to local store traversal"`); `_tx_category` falls back to
  the store product-edge lookup for rows not sourced from GQ-051.
- **Verification:** old module (git `HEAD` version) vs new, 7 cases — FIRM/F001 ALL+LTM,
  DIVISION/D01 YTD, REGION/R01 QTD, MARKET/M01 LTM, ADVISOR/A001 ALL+LTM — **IDENTICAL** JSON
  in all 7. Confirmed zero fallback warnings fired (run_query path served everything).
  `py_compile` clean.

### 2. `app/scope/rollup.py` — commit `71d7b92`

- **`.store` calls found → mapping:**
  - `resolve_scope_advisor_ids` (×2) → GQ-002 via `resolve_scope_advisor_ids_graph`.
  - `_child_breakdown` traversal (`in_ids` child edges + `vertex` name lookups) → GQ-053
    placements grouping.
  - `_top_advisors` advisor-name `vertex` lookups → GQ-007 row `advisor_name` /GQ-053 placements.
  - **Ranking itself** (previously SnapshotStore-ordered) → **GQ-007 `get_top_bottom_advisors`**
    (direction TOP/BOTTOM, result_limit, real DATETIME window from the selected period). GQ-007
    gsql checked against the V1 defect classes: clean.
- **Output keys:** summary keys unchanged (`scope_type, scope_id, totals, comparison,
  child_breakdown, top_advisors, bottom_advisors, evidence`); top/bottom row keys preserved
  (`advisor_id, advisor_name, revenue_ltm, aum_total, goal_attainment, agp_risk_score, status,
  reason`) **plus** new `period_revenue` (the honest ranking basis). `summary()` gained an
  optional `period` parameter (default None = ALL window; existing callers unaffected).
- **Snapshot totals (`totals`, `comparison`) are untouched** — SnapshotStore is not a graph read.
  Anchored advisor figures not modified (A001 `revenue_ltm` still comes from its snapshot).
- **Fallback:** `_top_advisors_from_snapshots` (the exact old ranking) behind
  `"get_top_bottom_advisors unavailable ... falling back to snapshot ranking"`; child breakdown
  store path behind `"child breakdown ... using local store traversal fallback"`.
- **Verification:** old vs new — `totals`/`comparison`/`child_breakdown`/`evidence` identical;
  only top/bottom differ (intended). Acceptance test output:
  `FIRM F001 (None|LTM)`, `DIVISION D01 YTD`, `MARKET M01`, `ADVISOR A001` → overlap **NONE**
  everywhere, A001 never in both; LTM vs YTD rank over different windows (top1 period_revenue
  840,009.06 vs 521,543.14). `py_compile` clean, zero fallback warnings.

### 3. `app/scope/dashboard.py` — commit `f3d1617`

- **`.store` calls found → mapping:**
  - `resolve_scope_advisor_ids` (×2: `_per_advisor_rev`, main) → GQ-002 helper.
  - `_firm_id` (`all_vertices phx_dm_firm`) → firm_id from GQ-053 placements (store fallback).
  - `_markets_under` + `_market_row` (hierarchy `in_ids` walks + name lookups) → GQ-053
    placements grouped by market.
  - `_peer_scope_ids` sibling walks (`in_ids`/`out_ids` on firm/division/region/market edges) →
    parent located from current scope's GQ-053 rows; siblings enumerated from the parent scope's
    GQ-053 rows.
  - `_advisor_benchmark` peer advisor name/market lookups → GQ-053 (ADVISOR scope) per peer.
  - `_recent_transactions` (per-advisor `in_ids transaction_for_advisor` + tx/household/product
    vertex+edge lookups) → **GQ-051** (rows already carry household_name/product_name).
  - `_name_for_scope` vertex lookups → label cache built from GQ-053 rows (store fallback).
- **Output keys unchanged** (dashboard payload and each sub-structure; recent-transaction rows
  keep `transaction_id, date, household, household_id, product, revenue_impact, type,
  advisor_name`).
- **Period wiring (§7):** `dashboard(period=...)` now passes `period` into
  `ScopeRollupService().summary(...)` so top/bottom follow the Time Period control.
- **Fallbacks:** every migrated read keeps the original store body behind a `logger.warning`
  (`"...using local store traversal fallback"` / `"recent transactions ... fallback"`).
- **Verification:** old vs new for FIRM/F001, DIVISION/D01, REGION/R01, MARKET/M01, ADVISOR/A001
  — every key identical **except** `top_advisors`/`bottom_advisors` (intended rollup change).
  FIRM LTM top/bottom overlap NONE. Zero fallback warnings. `py_compile` clean.

### 4. `app/revenue/trend_explorer.py` — commit `5c39f32`

- **`.store` calls found → mapping:**
  - `resolve_scope_advisor_ids` → GQ-002 helper.
  - `advisor_transactions` per advisor + per-tx `out_ids transaction_for_product` → **GQ-051**
    (scope-wide; tx→product map from rows).
  - `_advisor_slice_map` hierarchy walks (advisor_in_branch / advisor_in_market /
    market_in_region / region_in_division + name lookups) → **GQ-053** placements
    (`{dimension}_name` per advisor).
  - `_product_category_map` walks → **GQ-052**.
- **Output keys unchanged:** `scope_type, scope_id, dimension, granularity, start, end,
  available_months, slices, periods, evidence` (and all nested period/slice keys).
- **Fallbacks:** original store bodies behind `logger.warning` lines (`"...falling back to local
  store traversal"`, `"slice map ... fallback"`, `"get_product_category_map unavailable ..."`).
- **Verification:** old vs new across 6 cases (division/monthly FIRM, region/quarterly FIRM,
  market/monthly DIVISION, branch/monthly FIRM, advisor/monthly MARKET, business_line/quarterly
  FIRM) — **IDENTICAL** in all 6 (LLM_CLIENT_MODE=mock so driver text is deterministic). Zero
  fallback warnings. `py_compile` clean.

### 5. `app/api/routers/hierarchy.py` — commit `fc4194b`

- **`.store` calls found → mapping:**
  - `/tree`: `all_vertices(phx_dm_firm)` + `in_ids` down the whole chain + `vertex` name lookups
    → **GQ-053** with `scope_type="ALL"` (each advisor's ancestor chain reconstructs the identical
    nested tree; verified against the data that no hierarchy node is advisor-less, so nothing is
    lost vs the top-down walk — caveat recorded below).
  - `/entity-names`: `all_vertices` × 7 types → **GQ-053 (ALL)** for
    firm/division/region/market/branch/advisor names + **GQ-002** (`entity_type=HOUSEHOLD`) for
    household names (coverage verified complete, count 466).
  - `/resolve`: resolver → **GQ-002** via `resolve_scope_advisor_ids_graph`.
- **Output keys unchanged:** `/tree {firms:[{scope_type, scope_id, label, children:[...]}]}`,
  `/entity-names {names, count}`, `/resolve {scope_type, scope_id, advisor_count, advisor_ids}`.
- **Fallbacks:** `_tree_from_store` / `_entity_names_from_store` preserved verbatim behind
  `logger.warning` lines; `/resolve` fallback lives in the shared helper.
- **Verification (agent + independent main-thread re-check):** old vs new `.data` payloads
  IDENTICAL for tree, entity-names, and resolve at FIRM/DIVISION/ADVISOR/ALL; zero fallback
  warnings; `py_compile` clean. (Full-envelope comparison differs only in per-call
  `trace_id`/`generated_at`, which differ between any two calls including old-vs-old.)
- **Caveat for the reviewer:** the query path rebuilds the tree from advisor placements, so a
  hierarchy node with zero advisors beneath it (none exist in current data) would be omitted.
  If such nodes are ever seeded, a "list all hierarchy vertices" query would be needed (GQ-001
  can't serve it — it needs a concrete scope_id and returns flat vsets with no parent linkage).

### 6. `app/peers/benchmarking.py` — commit `3182912`

- **`.store` calls found → mapping:** resolver → **GQ-002**; advisor display names
  (`vertex phx_dm_advisor .advisor_name`) → **GQ-053** for the scope (one call), similarity peers
  outside the scope via **GQ-008 `get_peer_benchmark`** (`peer_method="SIMILARITY"`, open window)
  then per-advisor GQ-053; store lookup only as the final logged fallback (`_name_store`).
  SnapshotStore features and `EmbeddingSimilarityService` untouched (not graph reads).
- **Output keys unchanged:** `advisor_id, advisor_name, scope_type, scope_id, peer_group_size,
  dimensions[{metric, feature, advisor_percentile, peer_median_percentile, advisor_value,
  peer_median_value}], nearest_peers[{advisor_id, advisor_name, similarity_score, reasons,
  revenue_ltm}], evidence{source, peer_ids_resolved}`.
- **Fallback log lines:** shared-helper warnings + `"advisor name for %s not resolved via
  catalogued queries — falling back to local store traversal"` +
  `"get_scope_advisor_placements unavailable for %s/%s — advisor names will use the logged
  local store fallback"`.
- **Verification (agent + independent re-check):** old vs new IDENTICAL for A001/A020 at
  FIRM/F001, A001 at DIVISION/D01 (agent additionally: A005 MARKET/M01, A020 ADVISOR/A020);
  zero fallback warnings; `py_compile` clean.
- **GQ-008 nuance (existing, reported not fixed):** the GSQL drops zero-transaction peers from
  its `peers` output while the mock includes them with revenue=0 — here GQ-008 is only a
  secondary name source with per-advisor GQ-053 behind it, so membership drift cannot change
  this reader's output.

### 7. `app/api/routers/advisor360.py` — commit `3986a3e`

- **`.store` calls found → mapping:** one `graph.store` handle feeding four reads inside
  `advisor_360()`:
  - `_embeddings_by_entity(store, "HOUSEHOLD"/"ACCOUNT")` (embedding-existence probe for the
    similar-entities focus) → **GQ-024 `get_embeddings_for_entity`**, probed highest-value-first
    per candidate (equivalence with the old attribute scan verified 60/60 for both entity types).
  - `vertex(household).total_aum` / `vertex(account).current_value` (focus ranking) → read from
    the vertex attributes already returned by the existing **GQ-009 `get_advisor_360`** call —
    no new query needed.
- **Output keys unchanged:** data keys `graph, feature_snapshot, agp_track, crm_summary,
  crm_opportunities, revenue_trend, account_mix, segment_mix, similar` (+ envelope).
- **Fallback:** pre-migration store scan preserved verbatim behind
  `"get_embeddings_for_entity unavailable — falling back to local store embedding scan for
  advisor %s similar-entity focus"`; agent additionally proved the fallback path produces
  identical output under a simulated tier failure.
- **Verification (agent + independent re-check):** old vs new `.data` IDENTICAL for A001, A020,
  A044; zero fallback warnings; `py_compile` clean.
- **Noted for Batch Two:** `app/embeddings/similar_entities.py` (used by `similar_entities()`)
  still reads `graph.store` internally — out of scope for this file per the one-file rule; its
  full-type embedding scan has no catalog fit (GQ-024 is per-entity; GQ-025 uses precomputed
  matches, not live cosine). Candidate for a new query in Batch Two.

### 8. `app/services/pipeline_trace_service.py` — commit `505b514`

- **`.store` calls found → mapping** (all in Stage 1 "Data" of the pipeline trace):
  - `vertex(phx_dm_advisor)` + `out_ids(advisor_serves_household)` + per-household
    `out_ids(household_owns_account)` → **GQ-009 `get_advisor_360`** (advisor attributes,
    households, accounts from one call).
  - `len(in_ids(transaction_for_advisor))` → **GQ-051 `get_scope_transactions`**
    (`scope_type=ADVISOR`, all-time window) → `len(transactions)`.
  - Not migrated (correctly): SnapshotStore, PredictionService, RecommendationService,
    RecommendationLifecycleService, observability spans — non-graph or other-file scope.
    No writes existed in this file.
- **Output keys unchanged:** `recommendation_id, advisor_id, total_ms, timing_basis,
  stages[{key, label, summary, artifact, ms}]`.
- **Fallbacks:** shared-helper warnings + `"get_advisor_360 returned no advisor/households entry
  for %s — falling back to local store traversal"`, `"get_scope_transactions returned no
  transactions entry for advisor %s — falling back to local store traversal"` (exact original
  traversal preserved via `graph_fallback_store`).
- **Verification (agent: REC_A001..REC_A005; independent re-check: REC_A001, REC_A020):**
  IDENTICAL (timing fields excluded — nondeterministic between any two runs); zero fallback
  warnings; `py_compile` clean. Pre-existing, unrelated: household-scoped rec ids (e.g.
  REC_HH_H0030) crash identically on old and new code.

### 9. `app/client360/service.py` — commit `9bb03af`

- **`.store` calls found → mapping:**
  - recommendation lineage (`out_ids` addresses_opportunity / based_on_prediction /
    uses_feature_snapshot / uses_playbook + `in_ids` reasoning_for_recommendation + vertices)
    → **GQ-029 `get_recommendation_detail`**.
  - `households_for_advisor` (`out_ids advisor_serves_household` + household vertices) →
    **GQ-010 `get_advisor_book_of_business`** (`result_limit=100000`, old code had no limit).
  - household profile (household vertex, serving advisor, accounts, recommendations) →
    **GQ-011 `get_household_360`**.
  - per-account holdings (`out_ids account_holds_product` + product vertices) and household
    transactions → **GQ-012 `get_account_holdings_and_activity`** per account; household
    transactions = union of the accounts' transaction sets — equivalence verified empirically
    for all 360/360 households (0 mismatches), including ordering.
  - embedding-existence checks → **GQ-024 `get_embeddings_for_entity`** (equivalence verified
    for all 360 households + 720 accounts).
- **Output keys unchanged** (households rows + full profile structure incl.
  `summary`, `accounts[…holdings…]`, `transactions`, `recommendations[…lineage…]`, `similar`).
- **One intentional value enrichment (latent bug fixed, reported openly):** the old lineage code
  looked up predictions under vertex type `phx_dm_prediction`, which does not exist (real type:
  `phx_dm_prediction_result`) — so Prediction sources were silently always absent. GQ-029
  returns the real prediction vertices, so the migrated path now emits them (verified as the
  ONLY difference: with Prediction sources stripped, outputs are JSON-identical; independent
  re-check H0001 identical-except-Prediction, H0100/H0360 fully identical, A001/A020 household
  lists identical).
- **Fallbacks:** per-path `logger.warning` "falling back to local store traversal" lines for
  GQ-029/010/011/012/024 unavailability; original traversals preserved.
- **Verification:** agent full sweep — 360/360 profiles, 60/60 advisors, 0 mismatches, 0
  fallback warnings; `py_compile` clean.

---

## Final verification (Codespace, mock tier)

- **Backend boots:** `app.api.main:app` imports cleanly (`LLM_CLIENT_MODE=mock`),
  **146 OpenAPI paths** — matches the documented route count.
- **Acceptance test (§7), end-to-end through the dashboard service:**
  `dashboard('FIRM','F001',period='LTM')` → top = A049, A048, A047, A044, A050, A046, A045,
  A059; bottom = A001, A002, A004, A003, A011, A005, A012, A013 — **overlap NONE, A001 in at
  most one list**; Period control drives the ranking window (LTM vs YTD produce different
  period_revenue values). Mock data was sufficient to confirm the invariant and period wiring;
  live-data confirmation is client-machine follow-up #3.
- **Every migrated file:** `python -m py_compile` clean; old-vs-new output comparison performed
  against the pre-migration `git show HEAD:<file>` version (results per section above); zero
  unexpected fallback warnings on the query paths.
- **Foundation validator:** `docs/tigergraph_foundation/scripts/validate_package.py` → STATUS
  PASS (53 queries; validator's expected count and allowed-status list updated as part of the
  GQ-051..053 commit — same practice as the prior 43→50 extension).

## What was intentionally NOT done

- No writes/mutations migrated anywhere (rule 5); `app/recommendations/lifecycle.py` is Batch
  Two and untouched.
- `app/graph/client.py`, `app/graph/tiered_client.py`, `app/graph/foundation_store.py` untouched
  (rule 6) apart from nothing — the mock-query registrations live in `app/graph/queries/*.py`.
- No attempt to start/repair/connect to any local or remote TigerGraph (per TIGERGRAPH_PREFLIGHT
  verdict); tier-2 serving is unverifiable here by design.
- Batch Two files untouched; branch not merged.

---

## Verification environment

`GRAPH_CLIENT_MODE=mock` in this Codespace (tier 4). Per §12 of the task: every `run_query` here
serves from the mock tier by design; the mock and real tiers return identical result shapes, so
wiring + shape correctness is what is proven here. Tier-2 serving, live-graph counts, and new
query installation are client-machine follow-ups, flagged above.
