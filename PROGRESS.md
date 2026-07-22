# BUILD PROGRESS — iPerform V2
Last updated: 2026-07-22T00:00:00Z
Current phase: ROUND 3 (FIX_SPEC_R3.md)
Resume from: T1-1

## Session log
| # | Started | Ended | Resumed from | Notes |
|---|---------|-------|--------------|-------|
| 1 | 2026-07-20 | 2026-07-20 | fresh start | Phases 0-7 complete in one session; DoD met |
| 2 | 2026-07-21 | 2026-07-21 | round 2 fresh start | FIX_SPEC.md round: R1..R9 |
| 3 | 2026-07-22 | | round 3 fresh start | FIX_SPEC_R3.md: T1..T8 |

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
| R1-1 | R1 | reason_code vertex + seed data | DONE | cf6fd3e | 15 codes, 3 states; seed in eligibility.py |
| R1-2 | R1 | txn_has_reason edge | DONE | cf6fd3e | + reverse edge; sample edges written |
| R1-3 | R1 | transaction vertex new attributes | DONE | cf6fd3e | 7 new attrs incl. derived eligibility |
| R1-4 | R1 | product vertex grid_type attribute | DONE | cf6fd3e | stored as data; filtered via config |
| R1-5 | R1 | extraction SQL: reason_cd/rm_sid/cs_sid/grid_type, remove WHERE filter | DONE | d60a7c1 | generated from source_catalog.json |
| R1-6 | R1 | credited-revenue definition (data-driven eligibility + 90-day rule) | DONE | cba797e | reasons from graph; CREDITED_GRID_TYPES + MAX_PROCESSING_DAYS config |
| R1-7 | R1 | posting_month_id (ASSUMED) | DONE | cf6fd3e | = trade month; assumption stated in schema + txn rows |
| R1-8 | R1 | ELIGIBILITY driver cause | DONE | cba797e | after ONE_TIME; -(Δ non-credited); NEW/LOST double-count guard |
| R1-9 | R1 | queries + services updated for credited-only | DONE | b7abbc7 | GQ-016; drill-down classification; pivot equality verified |
| R1-10 | R1 | regenerate commentary; reconciliation re-verified | DONE | (this) | v6 published 6/6, 86 evidence records; verify suite ALL PASS |
| R1-11 | R1 | sample data regenerated with reason codes | DONE | 2b353fc | all buckets + >90d + pay-type rows; v1-v5 history preserved |
| R2-1 | R2 | component units — counts/percent/bps no longer rendered as currency | DONE | f92f783 | unit field + UI formatter switch; currency-only totals |
| R2-2 | R2 | table names corrected via source catalog | DONE | d60a7c1 | via R3, no literal edit |
| R3-1 | R3 | source_catalog.json + both consumers read from it | DONE | d60a7c1 | SQL generated; evidence builder reads table_name() |
| R4-1 | R4 | evidence: why-this-cause panel | DONE | e8d403e/a40815f | rule + inputs + rejected causes, sourced from attribution code |
| R4-2 | R4 | evidence: attribution order | DONE | e8d403e/a40815f | step n of 12 + earlier claims |
| R4-3 | R4 | evidence: reconciliation waterfall | DONE | e8d403e/a40815f | from + Σ = to verified exactly on all 86 v7 records |
| R4-4 | R4 | evidence: rev_nature derivation | DONE | e8d403e/a40815f | actual file_key/description values |
| R4-5 | R4 | evidence: credited-revenue breakdown | DONE | e8d403e/a40815f | client-vocabulary ledger w/ reason-code detail |
| R4-6 | R4 | evidence: source SQL rendered from catalog | DONE | d60a7c1/a40815f | generated SQL + 'not executed' labeling |
| R5-1 | R5 | commentary_evaluation vertex + edge | DONE | cefca07 | + GQ-017 both tiers, manifest files |
| R5-2 | R5 | judge runs after generation on different model | DONE | e8d403e | claude-sonnet-5 vs haiku writer; ran in v7: 6× PASS |
| R5-3 | R5 | judge advisory-only | DONE | e8d403e | degrades to REVIEW, never raises/blocks/publishes |
| R5-4 | R5 | judge surfaced in evidence modal + card badge | DONE | a40815f | Independent review line + JUDGE badges |
| R6-1 | R6 | Playwright evidence capture + gitignore + index | DONE | (this) | 8/8 screens, zero console errors on rerun; artefacts gitignored |
| R7-1 | R7 | UI typography/density polish | DONE | a40815f | tabular-nums, nav/ subnav, row height, tracking |
| R7-2 | R7 | "AI Generated" chips + boundary helper text | DONE | a40815f | 4 marked regions, no computed figure marked; CSV footers |
| R8-1 | R8 | V1 dead-reference cleanup | DONE | 076df02 | 22 dead files removed; app/models gitignore bug fixed |
| R9-1 | R9 | SOLUTION_GUIDE.md | DONE | (this) | 10 chapters, worked examples from sample data |
| T1-1 | T1 | LATE_PROCESSING driver cause + seed | DONE | 5c4b7bf | -(Δ late_excluded), after ELIGIBILITY; fires on sample (Apr late fee credited from May) |
| T1-2 | T1 | audit identity subtrahends for missing drivers | DONE | 5c4b7bf | EXCLUDED_CHANGE added (9X deleted bookings); OUT_OF_GRID needs none by construction (static grid_type + fixed config), verified |
| T1-3 | T1 | MIX >15% self-check (WARNING) | DONE | 5c4b7bf | attribute_transition logs WARNING w/ breakdown; MIX_WARNING_FRACTION=0.15 |
| T1-4 | T1 | MIX-magnitude in verification/report | DONE | 5c4b7bf | verify suite prints MIX share per transition; all ≤1.0% |
| T1-5 | T1 | regenerate commentary; reconcile $0.00 + MIX small | DONE | (this) | v9 published 6/6, 88 evidence; verify OVERALL PASS. v8 had 1 BLOCKED from guardrail reading reason code "9E" as figure "9" — regex fixed (lookahead), kept as history |
| T1-6 | T1 | relabel total_revenue → in_scope; OUT_OF_GRID near-empty check | DONE | 5c4b7bf/(this) | UI ledger label "In-scope revenue" + grid-type footnote (field name unchanged — presentation change per T4-1 principle); OUT_OF_GRID composition check loud in verify |
| T2-1 | T2 | evidence modal takes driver SET + Prev/Next | DONE | (this) | modal loads full ranked set via GQ-008; Prev/Next + ←/→; Esc closes |
| T2-2 | T2 | unify walk + card entry points | DONE | (this) | walk opens at driver 1; card bullet opens at that driver; both carry full set |
| T2-3 | T2 | efficient full-set load | DONE | (this) | driver set once per open; evidence lazy per driver, cached |
| T2-4 | T2 | header reflects current driver | DONE | (this) | title/amount/badge/tag + "Revenue Driver n of N" update on page |
| T3-1 | T3 | old-version evidence: backfill or explicit label | DONE | (this) | LABEL (not backfill): v1-v6 driver sets superseded by data regenerations — honest backfill impossible; explicit notices, no blank panels |
| T3-2 | T3 | reconciliation waterfall overhaul + focus highlight | DONE | (this) | plain-English lead, focus highlight follows paging, how-to-read expander, completeness note |
| T3-3 | T3 | fix double-parenthesis header | DONE | (this) | header now ▲/▼ + single-parens colored; audited repo — no other double-wrap |
| T4-1 | T4 | rename cause → Revenue Driver(s) in UI | DONE | (this) | labels/panel titles/tooltips + evidence wording maps; cause_id fields untouched; v10 generated with new wording |
| T4-2 | T4 | drivers as a titled column in cards | DONE | (this) | "Revenue Drivers" column header + Source·Driver header on card rows |
| T4-3 | T4 | Revenue-Driver glossary popup | DONE | (this) | 15 drivers (spec's 14 + EXCLUDED_CHANGE from T1-2) w/ meaning+computation; DUMMY badges on Market/Net Flow; links on AI-Insights + evidence modal; SOLUTION_GUIDE ch.6 references it |
| T5-1 | T5 | remove dead legend dropdown | DONE | (this) | T-3 dead control removed entirely |
| T5-2 | T5 | view-mode control (single / compare two / all) | DONE | (this) | segmented control; single default w/ transition dropdown; compare 2 dropdowns; all → walk anchor |
| T5-3 | T5 | clickable chart arrows → single view | DONE | (this) | arrows + pills clickable (wide hit area); selected arrow heavier + pill ring |
| T5-4 | T5 | static walk version selector | DONE | (this) | walk inherits top selector; static "Version N (latest)" text |
| T6-1 | T6 | real data export (CSV/Excel) from stored data | DONE | (this) | export-data.ts: API-built, human headers, row per (transition, driver); walk export per month w/ drivers; negatives parenthesised |
| T6-2 | T6 | presentation PDF export | DONE | (this) | print stylesheet + window.print(); chrome print:hidden; print footer w/ advisor/version/date/AI note |
| T6-3 | T6 | two themed export buttons + AI marking in output | DONE | (this) | "Export data" + "Export PDF" outline-navy; AI footer in CSVs + print footer |
| T7-1 | T7 | button theming | DONE | (this) | Regenerate/Generate navy fill; exports outline; hover/focus/disabled styled |
| T7-2 | T7 | AI-chip adjacency on card header | DONE | (this) | computed count on own line behind hairline: "N transactions · computed from graph data" |
| T8-1 | T8 | .gitignore CRLF / data/real protection | DONE | (this) | .gitignore is LF (ASCII); `git check-ignore data/real/x` prints path — protected |
| T8-2 | T8 | app/models tracked | DONE | (this) | `git ls-files app/models` → 6 files tracked |

## Decisions
| When | Decision | Why |
|------|----------|-----|
| 2026-07-20 | Created 25 edge types, not 23 | SCHEMA_SPEC header count conflicts with its own edge tables; the tables are the detailed authority |
| 2026-07-20 | Deleted ai-insight-summary.tsx (with severity-badge, formatted-answer) | It imported deleted ai-content-card and V1 severity concepts; Phase 6 builds commentary cards fresh from the reference PNGs |
| 2026-07-21 | Unknown reason codes classify as NON_CREDITED | Never credit revenue we cannot classify; kept in Total for honesty |
| 2026-07-21 | LATE (>90d) rows stay in Total revenue, out of Credited, tracked as late_excluded_amt | Client doc says "ignored ... not sent to iComp"; keeping them visible in Total + a named bucket is the honest reading |
| 2026-07-21 | EXCLUDED third state interpreted from "no UI mapping" in client doc | Recorded in BUILD_REPORT as an interpretation to confirm |
| 2026-07-21 | ELIGIBILITY computed as -(Δ non-credited) per spec; steady non-credited yields no driver | Follows FIX_SPEC R1-8 formula; approximation noted in SOLUTION_GUIDE gaps |
| 2026-07-21 | Sample-data regeneration PRESERVES workflow CSVs (commentary v1-v5) | Versions are additive (CLAUDE.md §7); regeneration must not delete history |
| 2026-07-21 | schema_catalog.json + load_v2_all.gsql + extraction SQL now GENERATED by scripts | Single-source-of-truth: DDL and source_catalog.json respectively; prevents drift class of R2-2 |
| 2026-07-22 | total_revenue kept as data field name; UI label changed to "In-scope revenue" + footnote | FIX_SPEC_R3 T1-6 offers rename OR footnote; renaming the field would ripple through schema/queries/CSVs for a presentation concern — same labels-only principle as T4-1 |
| 2026-07-22 | Sample late/deleted stories persist across months (late fee recurs on time; 9X marker persists) | Makes LATE_PROCESSING/EXCLUDED_CHANGE fire on genuine credited movement instead of a phantom delta offset by MIX |
| 2026-07-22 | v8 (1 BLOCKED) retained in history; v9 is the published version | Versions are additive (CLAUDE.md §7); the v8 block was a guardrail false positive (reason code 9E read as figure 9), fixed in the extractor regex |
| 2026-07-22 | EXCLUDED_CHANGE/LATE_PROCESSING guard NEW/LOST-claimed accounts; presence counts credited+non-credited+late | Prevents double-counting between account-presence drivers and bucket-delta drivers; excluded (deleted) rows are not evidence of trading |

## Blocked / deferred
| Task | Reason | What would unblock it |
|------|--------|----------------------|
