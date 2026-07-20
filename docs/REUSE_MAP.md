# REUSE MAP — what already exists in this repo

This repo was created by pruning the V1 codebase down to reusable infrastructure. The
plumbing is proven and running in production-like conditions; **build on it, don't rebuild
it.** V1's domain code was removed entirely.

---

## 1. Build on these — do NOT rewrite

### Graph access — `app/graph/`
The tier system, adapters and the `run_query` contract. This is the single most valuable
thing you inherited: it is already proven against a live TigerGraph 4.2.x.

| File | What it gives you |
|---|---|
| `tiered_client.py` | Tier cascade, dispatch, `served_by_tier` stamping |
| `client.py` | `get_graph_client()` — the entry point every reader uses |
| `queries/common.py` | **`run_catalog_query()`** — runs a catalogued query, returns results or `None`, and does the WARNING logging on error and on mock-served-in-real-mode. Use this; do not reimplement it. |
| `tigergraph/` , `tigergraph_rest_adapter.py` | pyTigerGraph and REST++ adapters |
| `foundation_store.py` | The local in-memory/SQLite store backing tier 2 |
| `artifacts.py` | `upsert_vertex()` / `upsert_edge()` — tier-routed writes |

**You must add:** a **delete** capability. V1 had no real-TigerGraph delete, which left its
reset flow half-writing to the graph and half to the mock. V2 requires
`delete_vertices(type, ids)` and `delete_all(type)` on the client interface, implemented for
both tiers, from day one. The ingestion screen depends on it.

### Ingestion — `app/ingestion/`
`ingestion_service.py`, `run_all.py`, `entity_registry.py`, `checkpoint_repository.py`,
`delta_detector.py`, `validation_engine.py`, `tigergraph_upsert.py`.
Manifest-driven loading with batching, checkpoints, retry and validation. Point it at the
V2 manifest; keep the framework.

Two behaviours V1 fought hard for — preserve them:
- Ingestion **fails loudly** if it is served by the local tier while in real mode
  ("NOT written to TigerGraph"), rather than reporting success.
- Stale checkpoints must not suppress real writes.

### Environment health — `app/services/environment_health_service.py`
Reports the true serving tier. Keep its honesty contract: counts come from
`statistics()`/`getVertexCount`, it reports `active_tier` and `counts_served_by_tier`, and
it **fails red** if the local tier serves while `GRAPH_CLIENT_MODE=real`. Adapt the checks
to V2's vertices; do not weaken the contract.

### Platform
`app/llm/` (LLM + embedding clients, adapters, prompt templates) ·
`app/guardrails/` (**put V2's numeric validation here — §AGENT_SPEC**) ·
`app/observability/` · `app/shared/` (logging, correlation ids, responses, exceptions) ·
`app/config/` (settings, runtime config) · `app/api/` (app factory, middleware,
`routers/{env_health,health,ingestion,config,diagnostics,adapters,manifest,graph_access,observability,guardrails}.py`)

### Agent framework — `app/agents/`
`core/base_agent.py`, `state/agent_state.py`, `registry/{agent_registry,topology}.py`.
The framework stays; V1's agent *nodes* were removed. You author V2's four agents
(§AGENT_SPEC) as new nodes on this framework.

### Frontend
`components/layout/` (app shell, header) · `components/navigation/` (sidebar) ·
`components/design-system/design-tokens.ts` · `components/ui/` (badge, button, card,
skeleton) · `components/status/` · `components/loading/` · `styles/tokens.ts` ·
`lib/api/{client,endpoints,config}.ts` (fetch transport) · `lib/utils.ts` ·
`tailwind.config.ts`

**Directly reusable patterns** — read before writing anything similar:
| Component | Use it for |
|---|---|
| `patterns/delta-indicator.tsx` | MoM +/− values with colour and sign handling |
| `patterns/evidence-trace.tsx` , `patterns/why-trace.tsx` | The evidence modal's lineage section |
| `patterns/async-state.tsx` | Loading / empty / error states — use everywhere |
| `patterns/page-header.tsx` , `patterns/kpi-stat-card.tsx` | Page furniture |
| `patterns/ai-insight-summary.tsx` | AI commentary card layout |
| `charts/revenue-trend-chart.tsx` , `charts/product-mix-chart.tsx` , `charts/revenue-donut.tsx` | Recharts setup, axis/legend/tooltip conventions |
| `components/ingestion/data-ingestion-workspace.tsx` | Adapt for the V2 ingestion screen |
| `components/env-health/env-health-workspace.tsx` | Adapt for the V2 connectivity screen |

---

## 2. Reference only — read, never import

`docs/v1_patterns/` — six curated examples showing patterns that worked. Read its
`README.md` first. **Do not import from it. Do not copy files wholesale. If it disagrees
with the spec pack, the spec wins** (these files may be stale).

---

## 3. Phase 0 — expected breakage

Pruning removed V1 domain modules, so some retained files still reference them. This is
expected. Your first task is to make the app build again:

- **Dangling imports** in `app-shell.tsx`, `top-header.tsx`, `sidebar-navigation.tsx`,
  `header-search-notifications.tsx`, `active-context-bar.tsx`, `hierarchy-breadcrumb.tsx`,
  `persona-scope-selector.tsx`, `lib/hooks/*`, `lib/scope-options.ts` — they may import
  deleted API clients or types. Remove the dead references; keep the shell working.
- **`frontend/lib/navigation.ts`** still declares V1's 25 nav items. Replace with V2's
  (§UI_SPEC §2).
- **`app/api/main.py`** may still register removed routers. Trim to what exists.
- **`app/api/routers/tigergraph_foundation.py`** references V1's schema package — repoint
  at V2's foundation directory or trim it.
- **Delete `frontend/components/patterns/severity-badge.tsx`, `formatted-answer.tsx`** if
  they only serve V1 concepts and nothing in V2 uses them.
- Anything under `app/graph/mock/` and `mock_graph_store.py` that hard-codes V1 vertices
  must be repointed at V2's schema.

Commit this as its own step: `chore: phase 0 — repair imports, V2 nav, ports 3001/8001`.

---

## 4. Do not do these

- Do not reintroduce V1 domain concepts (AGP, coaching, CRM, recommendations, peers,
  predictions, opportunities, what-if, RAG, memory).
- Do not add a second graph engine.
- Do not rewrite the tier contract, `run_catalog_query`, or the ingestion framework.
- Do not modify anything in `docs/v1_patterns/`.
- Do not commit anything to `data/real/` (gitignored — it is client data).
