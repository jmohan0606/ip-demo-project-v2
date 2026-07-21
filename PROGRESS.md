# BUILD PROGRESS — iPerform V2
Last updated: 2026-07-21T00:00:00Z
Current phase: ROUND 2 (FIX_SPEC.md)
Resume from: R1-1

## Session log
| # | Started | Ended | Resumed from | Notes |
|---|---------|-------|--------------|-------|
| 1 | 2026-07-20 | 2026-07-20 | fresh start | Phases 0-7 complete in one session; DoD met |
| 2 | 2026-07-21 | | round 2 fresh start | FIX_SPEC.md round: R1..R9 |

## Tasks
| ID | Phase | Task | Status | Commit | Notes |
|----|-------|------|--------|--------|-------|
| P0-1 | 0 | Repair dangling imports | DONE | 2fd53f9 | backend+frontend dangling imports repaired |
| P0-2 | 0 | Replace navigation.ts with V2 nav | DONE | 2fd53f9 | V2 nav: Results + Operations |
| P0-3 | 0 | Set ports 3001/8001 (4 touchpoints) | DONE | 2fd53f9 | 3001/8001 across package.json, run scripts, env, CORS |
| P0-4 | 0 | Backend + frontend both start clean | DONE | 2fd53f9 | uvicorn /health ok; next dev all 6 routes 200 |
| P1-1 | 1 | 01_vertices.gsql (16 vertices) | DONE | d15b6b6 | 16 vertices, all with data_source |
| P1-2 | 1 | 02_edges.gsql (23 edges) | DONE | d15b6b6 | 25 edges (spec tables; header said 23 — tables win) |
| P1-3 | 1 | 03_create_graph.gsql + schema_catalog.json | DONE | d15b6b6 | catalog generated from DDL; constants→iperform_v2_revenue |
| P2-1 | 2 | GQ-001..004 reference queries | DONE | 8d440ab | GQ-001..004 authored + validated |
| P2-2 | 2 | GQ-005..007 trends queries | DONE | 8d440ab | GQ-005..007 authored + validated |
| P2-3 | 2 | GQ-008..010 driver/commentary queries | DONE | 8d440ab | GQ-008..010 authored + validated |
| P2-4 | 2 | GQ-011..013 evidence/drill-down queries | DONE | 8d440ab | GQ-011..013 authored + validated |
| P2-5 | 2 | GQ-014..015 ops queries | DONE | 8d440ab | GQ-014..015 authored + validated |
| P2-6 | 2 | query_catalog.json + install_all + query_cases | DONE | 8d440ab | catalog(15) + install_all + query_cases; validator script |
| P2-7 | 2 | Local-tier implementations for all queries | DONE | 8d440ab | v2.py impls registered; execution check vs sample data in P3 |
| P3-1 | 3 | Extraction SQL files | DONE | b89cf88 | 3 SQL files (lineage-only) |
| P3-2 | 3 | manifest.json + loading jobs | DONE | b89cf88 | manifest 41 files + load_v2_all.gsql |
| P3-3 | 3 | Sample data set (exercises every cause) | DONE | b89cf88 | SMPL001-3; all 12 causes; reconciles to $0 |
| P3-4 | 3 | Delete capability on client interface (both tiers) | DONE | b89cf88 | both tiers + tiered dispatch; verified via delete-all |
| P3-5 | 3 | Ingestion screen wired: load/reload/ordered delete | DONE | 6a15498 | screen wired: load/reload/ordered delete verified |
| P4-1 | 4 | app/v2/revenue — monthly aggregation + MoM | DONE | 3bd6ced | aggregation+MoM in app/v2/revenue; service + endpoints |
| P4-2 | 4 | app/v2/drivers — attribution + causes | DONE | 3bd6ced | 11-step attribution in app/v2/drivers; service + endpoints |
| P4-3 | 4 | Reconciliation check | DONE | 3bd6ced | /api/v2/ops/reconciliation recomputes from stored graph data; passes |
| P5-1 | 5 | supervisor_agent | DONE | fac5dfc | routing + generation sequence + retrieval-only read |
| P5-2 | 5 | revenue_agent | DONE | fac5dfc | thin node over app/v2; contract implemented |
| P5-3 | 5 | commentary_agent | DONE | fac5dfc | Claude narration, verbatim-figures prompt, fallback |
| P5-4 | 5 | explainability_agent (evidence) | DONE | fac5dfc | 5-section evidence; GQ actually run + result stored |
| P5-5 | 5 | Guardrails validation (5 checks) | DONE | fac5dfc | 5 checks; caught real LLM arithmetic in v2-v4; negative-tested |
| P5-6 | 5 | Batch generation workflow + versioning | DONE | fac5dfc | v1..v5 generated; supersede + blocked persistence verified |
| P6-1 | 6 | Shell, V2 nav, design tokens, advisor context bar | DONE | 1b73430 | shell, tokens, context bar, tier pill, banner |
| P6-2 | 6 | Trends pivot (01) | DONE | 8508b58 | pivot verified headless, 0 console errors |
| P6-3 | 6 | Trends MoM (02) | DONE | 8508b58 | MoM card same page; n/a + >=15% pills |
| P6-4 | 6 | AI Insights chart + cards (03) | DONE | e30e174 | SVG chart w/ arrows + driver cards |
| P6-5 | 6 | Commentary table (06) | DONE | e30e174 | monthly walk table w/ baseline note |
| P6-6 | 6 | Evidence modal (04) | DONE | 123acc5 | 5 sections incl. runnable GSQL + result; Esc/focus ok |
| P6-7 | 6 | Transactions drill-down | DONE | 123acc5 | filters, sort, pagination, API credited total |
| P6-8 | 6 | Ingestion screen (05) | DONE | 6a15498 | manifest table, run-all polling, ordered delete-all |
| P6-9 | 6 | Env health screen | DONE | 6a15498 | probes, tier detail, 3-way reconciliation |
| P7-1 | 7 | End-to-end verification with sample data | DONE | e99499f | verify_end_to_end.py OVERALL PASS; headless UI verified, 0 console errors |
| P7-2 | 7 | BUILD_REPORT.md complete | DONE | e99499f | BUILD_REPORT.md complete |
| R1-1 | R1 | reason_code vertex + seed data | TODO | | |
| R1-2 | R1 | txn_has_reason edge | TODO | | |
| R1-3 | R1 | transaction vertex new attributes | TODO | | |
| R1-4 | R1 | product vertex grid_type attribute | TODO | | |
| R1-5 | R1 | extraction SQL: reason_cd/rm_sid/cs_sid/grid_type, remove WHERE filter | TODO | | |
| R1-6 | R1 | credited-revenue definition (data-driven eligibility + 90-day rule) | TODO | | |
| R1-7 | R1 | posting_month_id (ASSUMED) | TODO | | |
| R1-8 | R1 | ELIGIBILITY driver cause | TODO | | |
| R1-9 | R1 | queries + services updated for credited-only | TODO | | |
| R1-10 | R1 | regenerate commentary; reconciliation re-verified | TODO | | |
| R1-11 | R1 | sample data regenerated with reason codes | TODO | | |
| R2-1 | R2 | component units — counts/percent/bps no longer rendered as currency | TODO | | |
| R2-2 | R2 | table names corrected via source catalog | TODO | | |
| R3-1 | R3 | source_catalog.json + both consumers read from it | TODO | | |
| R4-1 | R4 | evidence: why-this-cause panel | TODO | | |
| R4-2 | R4 | evidence: attribution order | TODO | | |
| R4-3 | R4 | evidence: reconciliation waterfall | TODO | | |
| R4-4 | R4 | evidence: rev_nature derivation | TODO | | |
| R4-5 | R4 | evidence: credited-revenue breakdown | TODO | | |
| R4-6 | R4 | evidence: source SQL rendered from catalog | TODO | | |
| R5-1 | R5 | commentary_evaluation vertex + edge | TODO | | |
| R5-2 | R5 | judge runs after generation on different model | TODO | | |
| R5-3 | R5 | judge advisory-only | TODO | | |
| R5-4 | R5 | judge surfaced in evidence modal + card badge | TODO | | |
| R6-1 | R6 | Playwright evidence capture + gitignore + index | TODO | | |
| R7-1 | R7 | UI typography/density polish | TODO | | |
| R7-2 | R7 | "AI Generated" chips + boundary helper text | TODO | | |
| R8-1 | R8 | V1 dead-reference cleanup | TODO | | |
| R9-1 | R9 | SOLUTION_GUIDE.md | TODO | | |

## Decisions
| When | Decision | Why |
|------|----------|-----|
| 2026-07-20 | Created 25 edge types, not 23 | SCHEMA_SPEC header count conflicts with its own edge tables; the tables are the detailed authority |
| 2026-07-20 | Deleted ai-insight-summary.tsx (with severity-badge, formatted-answer) | It imported deleted ai-content-card and V1 severity concepts; Phase 6 builds commentary cards fresh from the reference PNGs |

## Blocked / deferred
| Task | Reason | What would unblock it |
|------|--------|----------------------|
