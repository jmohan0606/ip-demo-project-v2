# BUILD PROGRESS — iPerform V2
Last updated: 2026-07-20T00:00:00Z
Current phase: 4
Resume from: P4-1

## Session log
| # | Started | Ended | Resumed from | Notes |
|---|---------|-------|--------------|-------|
| 1 | 2026-07-20 | | fresh start | |

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
| P3-5 | 3 | Ingestion screen wired: load/reload/ordered delete | IN_PROGRESS | b89cf88 | backend endpoints + checkpoint clearing done; UI screen lands in P6-8 |
| P4-1 | 4 | app/v2/revenue — monthly aggregation + MoM | TODO | | |
| P4-2 | 4 | app/v2/drivers — attribution + causes | TODO | | |
| P4-3 | 4 | Reconciliation check | TODO | | |
| P5-1 | 5 | supervisor_agent | TODO | | |
| P5-2 | 5 | revenue_agent | TODO | | |
| P5-3 | 5 | commentary_agent | TODO | | |
| P5-4 | 5 | explainability_agent (evidence) | TODO | | |
| P5-5 | 5 | Guardrails validation (5 checks) | TODO | | |
| P5-6 | 5 | Batch generation workflow + versioning | TODO | | |
| P6-1 | 6 | Shell, V2 nav, design tokens, advisor context bar | TODO | | |
| P6-2 | 6 | Trends pivot (01) | TODO | | |
| P6-3 | 6 | Trends MoM (02) | TODO | | |
| P6-4 | 6 | AI Insights chart + cards (03) | TODO | | |
| P6-5 | 6 | Commentary table (06) | TODO | | |
| P6-6 | 6 | Evidence modal (04) | TODO | | |
| P6-7 | 6 | Transactions drill-down | TODO | | |
| P6-8 | 6 | Ingestion screen (05) | TODO | | |
| P6-9 | 6 | Env health screen | TODO | | |
| P7-1 | 7 | End-to-end verification with sample data | TODO | | |
| P7-2 | 7 | BUILD_REPORT.md complete | TODO | | |

## Decisions
| When | Decision | Why |
|------|----------|-----|
| 2026-07-20 | Created 25 edge types, not 23 | SCHEMA_SPEC header count conflicts with its own edge tables; the tables are the detailed authority |
| 2026-07-20 | Deleted ai-insight-summary.tsx (with severity-badge, formatted-answer) | It imported deleted ai-content-card and V1 severity concepts; Phase 6 builds commentary cards fresh from the reference PNGs |

## Blocked / deferred
| Task | Reason | What would unblock it |
|------|--------|----------------------|
