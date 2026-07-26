# BUILD PROGRESS — iPerform V2
Last updated: 2026-07-26T01:30:00Z
Current phase: ROUND 14 (FIX_SPEC_R14.md) — LLM-based guardrail layer (defense in depth)
Resume from: (none — round 14 complete)

## Session log
| # | Started | Ended | Resumed from | Notes |
|---|---------|-------|--------------|-------|
| 1 | 2026-07-20 | 2026-07-20 | fresh start | Phases 0-7 complete in one session; DoD met |
| 2 | 2026-07-21 | 2026-07-21 | round 2 fresh start | FIX_SPEC.md round: R1..R9 |
| 3 | 2026-07-22 | 2026-07-22 | round 3 fresh start | FIX_SPEC_R3.md: T1..T8 all DONE; verify OVERALL PASS; 8/8 screens 0 console errors |
| 4 | 2026-07-22 | 2026-07-22 | round 4 fresh start | FIX_SPEC_R4.md: S-A1..A5 + S-B1..B6 all DONE; 13/13 shots 0 console errors; real pipeline proven on local tier; verify OVERALL PASS |
| 5 | 2026-07-23 | 2026-07-23 | round 5 fresh start | FIX_SPEC_R5.md ingestion rescue: A→B→D→E→C all DONE; A9a 25/25 PASS; e2e OVERALL PASS; A9b awaits operator |
| 6 | 2026-07-23 | 2026-07-23 | round 6 fresh start | FIX_SPEC_R6.md: X-A1..A5, X-B1..B2, Y-1..Y-7 all DONE; verify_attribution 12/12, verify_anomalies 14/14, e2e OVERALL PASS; 6 screens 0 console errors; real-data MIX gate + live GSQL = operator |
| 7 | 2026-07-23 | 2026-07-23 | round 7 fresh start | FIX_SPEC_R7.md: Z-A1..A13, Z-B1..B3, Z-C1..C3 all DONE; verify_assistant 84/84, UI walk 7/7 zero console errors, e2e OVERALL PASS; live install + cdao = operator |
| 8 | 2026-07-24 | 2026-07-24 | round 8 fresh start | FIX_SPEC_R8.md: V-A1..A5, V-B1..B4, V-C1..C3, V-D1 all DONE; all suites PASS (attribution, queries, anomalies, e2e 17-cause, assistant 84/84); recon $0.00; 15/15 shots 0 console errors; commentary v19 6/6 PUBLISHED; live reinstall + real-data checks = operator |
| 9 | 2026-07-25 | 2026-07-25 | round 9 fresh start | FIX_SPEC_R9.md: N-A..N-G all DONE; verify_attribution (R9A/R9B) PASS, verify_assistant 101/101, verify_commentary_retry 10/10, verify_judge 9/9, e2e PASS recon $0.00, 15/15 shots zero console errors; commentary v20 = 5 PUBLISHED + 1 PUBLISHED_FALLBACK; live reinstall/reseed/rebuild = operator |
| 10 | 2026-07-25 | 2026-07-25 | round 10 fresh start | FIX_SPEC_R10.md: T-A1..T-G1 all DONE; verify_taxonomy 33/33, verify_eligibility 25/25, verify_new_drivers PASS, verify_clawback_scope 12/12, verify_assistant 101/101, e2e PASS (19 causes, recon $0.00, MIX ≤13.9%); commentary v21 6/6; 15/15 shots zero console errors; real-hierarchy + LIFE code + cdao rows = operator |
| 11 | 2026-07-25 | 2026-07-25 | round 11 fresh start (FIX_SPEC_R11.md) | P-A1..P-F1 all DONE; verify_taxonomy PASS (42-path real-hierarchy fixture), verify_per_advisor 33/33, verify_assistant 101/101, verify_anomalies --rescan PASS, e2e PASS recon $0.00; sample Apr–Jul, all 6 anomaly rules fire; commentary v22–v24 per-advisor 9/9; 15/15 shots + passive walk zero console errors; live reinstall + ALTI confirmation = operator |
| 12 | 2026-07-25 | 2026-07-25 | round 12 fresh start (FIX_SPEC_R12.md) | Q-A..Q-E all DONE; verify_role_llm 32/32; all existing suites re-run PASS (attribution/taxonomy/eligibility/new_drivers/clawback/per_advisor 33/33/judge 9/9/commentary_retry 10/10/assistant 101/101/anomalies/e2e recon $0.00); tsc clean; .env.example 132/132 keys; live per-role cdao checks = operator |
| 14 | 2026-07-26 | 2026-07-26 | round 14 fresh start (FIX_SPEC_R14.md); session died mid-round (Codespace stop), session 15 resumed from git truth | SECURITY round S-A..S-I all DONE: regex → LLM intent classifier → hardened prompt → output leak check; fail-safe never open; verify_guardrail_llm 54/54; suites re-run PASS (assistant 101/101, role_llm 32/32, gpt5_compat 34/34, per_advisor 33/33, taxonomy/eligibility/new_drivers/anomalies, e2e recon $0.00); live guardrail-role cdao checks = operator (ROUND14_ACCEPTANCE.md) |
| 13 | 2026-07-25 | 2026-07-25 | round 13 fresh start (FIX_SPEC_R13.md) | R-A..R-E all DONE; verify_gpt5_compat 34/34; suites re-run PASS (role_llm 32/32, judge 9/9, commentary_retry 10/10, assistant 101/101, glossary 7/7, taxonomy/eligibility/new_drivers/clawback/per_advisor 33/33/anomalies, e2e recon $0.00); tsc clean; .env.example 136/136 keys; live GPT-5 cdao checks = operator |

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
| S-A1 | R4-A | Portal the glossary dialog; fix `<h2>`-in-`<p>` on both screens | DONE | 652c212 | createPortal(document.body) inside RevenueDriverGlossaryDialog — all usages safe; audited: EvidenceModal renders at page level, no other inline dialogs |
| S-A2 | R4-A | Evidence modal single-scoped; waterfall rebuilt per clicked group | DONE | 5a1a447 | scope = clicked driver's group; waterfall rebuilt from group change row + group drivers (per-group MIX residual ⇒ exact); __TOTAL__ scope explicitly labelled "Total — all product groups" |
| S-A3 | R4-A | Driver paging scoped to the clicked group; consistent count + caption | DONE | 5a1a447 | paging/count/←→ over group list; "Driver n of N in <Group>"; caption relates card top-5 vs group walk |
| S-A4 | R4-A | Compare-two: prevent duplicate selection + slot-scoped keys | DONE | ae7dd90 | other slot's choice disabled in each dropdown; keys slot-scoped; slot B defaults to a different transition or empty |
| S-A5 | R4-A | Regression sweep + fresh Playwright screenshots, zero console errors | DONE | c7d5fb8 | 13/13 shots (8 original + 5 new R4 proofs) zero console errors; group waterfall verified numerically vs API for every group |
| S-B1 | R4-B | Raw-extract contract (filenames, location, columns) documented + validated | DONE | a095acd | RAW_CONTRACT in build_real_data.py: 3 files, exact SELECT-list columns; loud validation on missing file/column |
| S-B2 | R4-B | scripts/build_real_data.py reusing app/v2 transform functions | DONE | a095acd | calls shared app/v2/dataset/builder (same month_rows/split/aggregate/attribute/reconcile); reconciliation $0.00 asserted as stop condition; summary prints MIX%/OUT_OF_GRID/>90d |
| S-B3 | R4-B | data_source stamping centralised; sample + real use same helper | DONE | c23dbe5 | provenance.py ARTIFACT_SOURCE + require_stamped (never blank); sample regeneration byte-identical |
| S-B4 | R4-B | .env.example fully populated; cross-checked vs settings.py | DONE | f2efd02 | V2 template; 128/128 settings keys present (programmatic cross-check) |
| S-B5 | R4-B | SOLUTION_GUIDE Chapter 9 operations runbook (numbered, exact) | DONE | 84f94c4 | 9 numbered steps w/ commands, expected output, failure+first-check; headless CLI added to generation_workflow (__main__) and proven |
| S-B6 | R4-B | Prove real pipeline locally with test fixtures; document proven-vs-pending | DONE | (this) | fixtures→build→tier-2 load→recon $0.00→headless commentary v1 all proven; BUILD_REPORT §10 records proven-vs-client-machine table |
| W-A1 | R5-A | attribute-drop fix: pre-flight column validation, absent≠empty, zero-attr assert | DONE | 0f64509 | shared fail-loud mapper all tiers + exact pre-flight header validation |
| W-A2 | R5-A | CSV quoting correct on every read/write path incl. manual upload | DONE | 8ea3140 | csv module everywhere; comma+quote+newline round-trip proven; no naive split existed |
| W-A3 | R5-A | write CSVs with LF; readers BOM-tolerant | DONE | 8ea3140 | LF on all writers; utf-8-sig readers; csv-aware counting |
| W-A4 | R5-A | checkpoint only after confirmed write; failures marked FAILED, no hashes | DONE | 23fe017 | hashes/tallies only after confirmed flush; fallback-tier write fails batch; retry-not-skip proven |
| W-A5 | R5-A | screen source of truth = graph count + attribute validation | DONE | e1f9b06 | fetch_vertices all tiers; GET /ingestion/validation w/ W11 states |
| W-A6 | R5-A | delete-one / delete-all: guarded, non-aborting, CORS-safe errors | DONE | feb169d | guarded non-aborting deletes; CORS-safe 500s w/ real message |
| W-A7 | R5-A | absolute path resolution + startup logging of resolved paths | DONE | 971235f | APP_ROOT anchoring; startup log + env-health resolved_paths |
| W-A8 | R5-A | 90_drop_all.gsql + clear-checkpoints endpoint + runbook procedure | DONE | 6d8a6ef | 90_drop_all.gsql; clear-checkpoints endpoint; RUNBOOK Step 10 |
| W-A9 | R5-A | A9a fixture verification gate passed; A9b operator acceptance doc written | DONE | 4bdc43d | A9a 25/25 PASS (local tier + fixtures); A9b ROUND5_ACCEPTANCE.md written — pending operator acceptance |
| W-B1 | R5-B | screen: live per-entity progress during Run All | DONE | (this) | current entity n/45 + per-entity rows + running tallies |
| W-B2 | R5-B | screen: async status refresh without blocking/restarting the run | DONE | (this) | 2s GET-only polling; run survives tab close (daemon thread) |
| W-B3 | R5-B | screen: batch size visible + configurable | DONE | (this) | batch column + per-run override ?batch_size= |
| W-B4 | R5-B | screen: per-entity error details persisted + remediation | DONE | (this) | GET /ingestion/errors persisted w/ remediation; header failures persisted; expandable rows |
| W-B5 | R5-B | screen: skip-and-continue + end-of-run remediation summary | DONE | (this) | run continues past failures; end-of-run remediation summary panel |
| W-B6 | R5-B | screen: validation proof column (graph count, attr check, state, timestamp) | DONE | (this) | validation proof column from GET /ingestion/validation |
| W-B7 | R5-B | scale: chunked processing, resumable checkpoints, no full-file materialisation | DONE | (this) | chunked batches + resumable checkpoints + streaming DictReader; streaming-at-scale recorded for SOLUTION_GUIDE next steps (E) |
| W-C1 | R5-C | real CSVs named after vertex/edge type | DONE | 3f849fb | 45 CSVs renamed to typed names via git mv; history preserved |
| W-C2 | R5-C | single catalog for target↔file↔columns; all consumers updated | DONE | 3f849fb | csv_file_for() single catalog; manifest/workflow/scripts consume; grep-verified |
| W-D1 | R5-D | baseline-month concept + BASELINE_LIMITED driver | DONE | (this) | BASELINE_LIMITED driver; baseline month from data; NEW/LOST skipped out of baseline |
| W-D2 | R5-D | baseline note in UI + commentary guard | DONE | (this) | prompt+fallback guard; card note on earliest transition; glossary+evidence panels |
| W-D3 | R5-D | MIX <15% on first transition; reconciliation $0.00 | DONE | (this) | MIX <=6.2% first transition; recon $0.00; 16 causes; v13 published; verify PASS |
| W-E1 | R5-E | sample data demoted to tests only | DONE | 53e2289 | sample demoted to test asset in SOLUTION_GUIDE + RUNBOOK + screen chip |
| W-E2 | R5-E | all docs/verification path = DATA_SET=real; honest report split | DONE | f6d467d | real-data path throughout docs; BUILD_REPORT splits verified-here vs operator |
| W-F1 | R5-F | ROUND5_CHANGED_FILES.md maintained per work-stream, git-derived, conflict flags | DONE | (this) | manifest updated after A, B, D, E+C; git-derived; renames + conflict flags listed |
| X-A1 | R6-A | account-presence drivers gated to recurring-class groups | DONE | e08903d | recurring-class groups only; transactional change stays with VOLUME/ONE_TIME/TIMING |
| X-A2 | R6-A | persistence rule (ACCOUNT_ABSENCE_MONTHS, default 2) for new/lost | DONE | e08903d/101c1f3 | activity over full loaded range; config in settings + .env.example; sample stories moved |
| X-A3 | R6-A | BASELINE_LIMITED bounded + assertion \|BL\| ≤ \|total change\| | DONE | e08903d | AttributionError fails the build loudly; build_real_data STOPs |
| X-A4 | R6-A | fixture reproducing the bug; automated checks; MIX <15% everywhere | DONE | c6013b9/2c26b46 | verify_attribution 12/12 PASS (legacy MIX 465%→7.0/9.4%); sample MIX ≤8.1%; v14 published; e2e PASS. Real-data MIX<15% = OPERATOR step |
| X-A5 | R6-A | docs + glossary updated to the precise rule | DONE | 620e8b7/0a3643e | glossary, why-this-cause, prompts, SOLUTION_GUIDE §6.3/6.4, BUILD_REPORT §12 |
| X-B1 | R6-B | 90_drop_all.gsql corrected (queries→graph→reverse→forward→vertices), generated from schema | DONE | (X-B1) | generated by generate_schema_artifacts.py: 17 queries, 27+27 edges, 18 vertices; expected-vs-real-error header; NEEDS-LIVE-VERIFICATION |
| X-B2 | R6-B | BUILD_REPORT note: generated GSQL is NEEDS-LIVE-VERIFICATION | DONE | 0a3643e | BUILD_REPORT §12 work-stream B |
| Y-1 | R6-Y | anomaly vertex/edges + scan vertex | DONE | 768296b | gate honoured: started after MIX <15% on fixture+sample; 20 vertices/30 edges; artifacts regenerated |
| Y-2 | R6-Y | six detection rules, thresholds in config | DONE | 02e03d9 | ANOMALY_* in settings + .env.example; BOOK_MOVEMENT deliberately excluded |
| Y-3 | R6-Y | GQ queries + catalog + local-tier impls | DONE | 39f2d84 | GQ-018/019 + catalog + install_all + cases; validator ALL CHECKS PASS |
| Y-4 | R6-Y | detection service, batch scan endpoint + CLI, additive scans | DONE | 02e03d9/1e1a7ae | scanNNN additive (id scan-prefixed — spec deviation recorded in BUILD_REPORT); POST /scan + status + CLI |
| Y-5 | R6-Y | anomaly narration via commentary_agent + guardrail | DONE | 02e03d9/ca8a911 | narrate_anomaly + rule meanings; validate_anomaly_text; deterministic fallback, no chip |
| Y-6 | R6-Y | /anomalies screen per mockup, empty state, thresholds visible | DONE | ca8a911 | Results sub-nav + sidebar; 0 console errors incl. empty state |
| Y-7 | R6-Y | per-rule fixtures; no-invented-figure assertion; additive re-scan verified | DONE | 1e1a7ae | verify_anomalies --rescan 14/14 PASS |
| Z-A1 | R7 | conversation + message vertices/edges, tiered persistence | DONE | 57073c6 | 22 vertices/32 edges; artifacts + manifest regenerated; AssistantStore via TigerGraphUpsertClient + CSV append |
| Z-A2 | R7 | provider selection (cdao primary in client env, claude on build box), logged fallback | DONE | adc3270/(verify) | AssistantLLM chain; fallback logged + on message metadata |
| Z-A3 | R7 | deterministic intent router covering all A3 intents | DONE | adc3270/(verify) | 10 intents + follow-up inheritance; 27 routing fixtures PASS |
| Z-A4 | R7 | constrained LLM fallback returning a validated {query, params} selection | DONE | adc3270/(verify) | structured selection validated vs catalog; rejects unknown queries/params |
| Z-A5 | R7 | multi-turn context resolution + screen-seeded context + Pin | DONE | adc3270/(verify) | question>pinned>inherited>screen>default; chip label; 3-turn fixture PASS |
| Z-A6 | R7 | GQ queries for conversations/messages + catalog + local-tier impls | DONE | 57073c6 | GQ-020/021 + catalog + install_all + cases; validator ALL CHECKS PASS |
| Z-A7 | R7 | facts-only behaviour incl. the advice response pattern | DONE | adc3270/(verify) | facts + single limit sentence; fixture asserts exactly one decline |
| Z-A8 | R7 | NO_DATA / OUT_OF_SCOPE / BLOCKED statuses | DONE | adc3270/(verify) | unloaded month / non-revenue / blocked fixtures PASS |
| Z-A9 | R7 | numeric guardrail on every answer | DONE | adc3270/(verify) | validate_anomaly_text over figures_json; deterministic fallback on reject |
| Z-A10 | R7 | input guardrails wired BEFORE routing (injection/jailbreak/PII/toxicity/oversize) | DONE | adc3270/(verify) | screen_input before routing; blocked turns never reach router/LLM (instrumented) |
| Z-A11 | R7 | blocked turns visible in transcript with GUARDRAIL chip; category+severity only | DONE | adc3270/(verify) | user msg renders, refusal + category/severity-only finding persisted |
| Z-A12 | R7 | message vertex extended: guardrail_status, guardrail_json | DONE | 57073c6 | in DDL from the start; guardrail_json carries category/severity/action only |
| Z-A13 | R7 | adversarial fixture set (~15) incl. false-positive checks | DONE | adc3270/(verify) | 12 adversarial + 4 false-positive fixtures, all PASS |
| Z-B1 | R7 | overlay panel, persists across navigation, collapses to button | DONE | 0f37a8a | 420px overlay; persists across nav; collapses to iP button; History/expand/collapse header |
| Z-B2 | R7 | full-page view sharing the same component | DONE | 0f37a8a | /ask full page, grouped rail; same AssistantPanel component, variant prop only |
| Z-B3 | R7 | answer rendering: AI chip on wording only, figures unmarked, Ran: trail, evidence links | DONE | 0f37a8a | AI chip wording-only; figures unmarked; Ran: trail; evidence/deep links; GUARDRAIL chip |
| Z-C1 | R7 | scripts/verify_assistant.py — all seven checks | DONE | 1377993/0f37a8a | verify_assistant.py 84/84 + verify_assistant_ui.mjs 7/7, zero console errors |
| Z-C2 | R7 | docs/ROUND7_ACCEPTANCE.md | DONE | (wrap) | operator-only: live install, real conversation, cdao provider drill, guardrail probe |
| Z-C3 | R7 | docs/ROUND7_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived per work-stream; conflict flags on v2.ts/v2-shell/manifest/.env.example |
| V-A1 | R8 | driver_cause vertex: display_name, description, computation | DONE | 8ce2c23 | DDL + 3 attrs; artifacts regenerated |
| V-A2 | R8 | GQ-004 returns them (query file + catalog + local-tier impl) | DONE | 8ce2c23 | whole-vertex PRINT carries attrs; catalog updated; local tier returns full rows; NEEDS LIVE REINSTALL |
| V-A3 | R8 | glossary, driver tags and evidence render from the query | DONE | eb67a2b | lib/v2/driver-causes single source; hardcoded glossary table deleted; CauseTag/waterfall/chips/export/anomaly phrases read display_name |
| V-A4 | R8 | seed all causes incl. DEAL_SIZE; CLAWBACK display_name = "Charge Back" | DONE | 8ce2c23 | 17 causes; legacy cause_name mirrored from display_name (anti-drift); rename proof PASS (data-only edit → API name change) |
| V-A4b | R8 | propagate attributes: DDL, regenerated catalog + loading job, manifest, both builders, both tiers | DONE | 8ce2c23 | full chain; manifest expected_rows 17; both builders share one seed; sample regenerated w/o ColumnMismatchError |
| V-A5 | R8 | no driver-name literals left in the frontend (grep-verified) | DONE | eb67a2b | grep clean; anomalies threshold phrases were the last hit — now resolve display_name |
| V-B1 | R8 | baseline transition identified from data | DONE | eb67a2b | earliest loaded month via GQ-002 (frontend hook) / get_months (revenue_agent); never hardcoded |
| V-B2 | R8 | labelled in cards, walk table, chart arrow, evidence modal | DONE | eb67a2b | tag + amber note in all four; INFO treatment; shot 14 proves |
| V-B3 | R8 | excluded from MIX check, UNEXPLAINED_RESIDUAL, and build-summary failure count | DONE | 8ce2c23 | MIX check logs informational `baseline`; anomaly rule returns None; summary tags [baseline] |
| V-B4 | R8 | commentary states the limitation instead of narrating noise | DONE | 7bc5677 | prompt v1.1 + fallback prefix; v19 all baseline narratives open with the limitation; guardrail also rejects positive-in-parens (caught real v18 misstatement) |
| V-C1 | R8 | account-comparison section in evidence (account drivers only) | DONE | eb67a2b | AccountComparisonPanel; NEW/LOST/BASELINE_LIMITED only; shot 15 proves |
| V-C2 | R8 | ranked top-20 with total and Transactions link | DONE | eb67a2b | abs-revenue ranked; showing N of M; ?accounts= filter on Transactions |
| V-C3 | R8 | classification rule stated from inputs_json | DONE | 8ce2c23/eb67a2b | classification_rule string in inputs_json, rendered above the lists |
| V-D1 | R8 | docs/ROUND8_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived e42622c..HEAD; prompts/ + data/real + qa_screenshots excluded; conflict flags on attribution/manifest/v2.ts/evidence-modal |
| N-A | R9 | account presence excludes ONE_TIME/ADJUSTMENT rev_nature | DONE | 45e6e4a | txn-level filter in activity map + group presence; account drivers claim recurring rows only; R9A fixture (pure one-time, mixed, recurring-then-one-time) PASS; recon $0.00 |
| N-B | R9 | account-comparison lists populate for group-level drivers (write+read agree) | DONE | 350c158 | QUOTE="double" in generated loading job (JSON shear root cause); builder fail-loud contract; modal logs key path + legacy-accounts fallback; R9B checks PASS |
| N-C1 | R9 | advisor-scoped conversations (advisor_sid on conversation, queries filtered) | DONE | 1b8f980 | advisor_sid on vertex + full chain; binding outranks screen; cross-advisor declines; GQ-020 attr filter both tiers; chat-CSV header migration; verify [10] 6 checks, 90/90 PASS |
| N-C2 | R9 | context seeds adjacent transition; no mislabelling; multi-month decomposes | DONE | be8e827 | shell passes month list -> adjacent seed; resolve() snaps screen spans; driver_detail matches both months; span_decompose per-transition labels; verify [11] 6 checks, 96/96 PASS |
| N-C3 | R9 | blocked turns visible with GUARDRAIL chip; fixture proves it | DONE | c3e6864 | chip renders category·severity; missing chat CSV auto-created; failed send keeps turn visible locally; verify [12] 5 checks incl. transcript endpoint; 101/101 PASS |
| N-D | R9 | commentary prompt sign-convention fix + 3x retry + deterministic fallback | DONE | b2778ba | prompt v1.2 w/ examples; COMMENTARY_MAX_ATTEMPTS=3 retry in supervisor; PUBLISHED_FALLBACK status + non-AI marking; verify_commentary_retry 10/10; live v20 = 5 PUBLISHED + 1 FALLBACK, 0 BLOCKED |
| N-E | R9 | judge on standard adapter, JUDGE_MODEL configurable, "unavailable" not 0.00 | DONE | 430ce7a | build_llm_client factory; JUDGE_MODEL within active mode (empty=mode default); -1.0 UNAVAILABLE sentinel; modal renders "—(unavailable)"; verify_judge 9/9 |
| N-F | R9 | glossary ordered by display_order | DONE | 809e0d5 | robust client sort (missing order last + name tiebreak); e2e asserts sorted 17 causes, DEAL_SIZE=2; fixtures regenerated; client reseed = operator |
| N-G | R9 | docs/ROUND9_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived 2f1a13e..HEAD; conflict flags on attribution/builder/workflow/settings/manifest/v2.ts/evidence-modal/v2-shell; data/real + prompts + gitignored dirs excluded; + ROUND9_ACCEPTANCE + BUILD_REPORT §15 |
| T-A1 | R10 | re-seed taxonomy to the verbatim hierarchy (A1) | DONE | 8225cbe | app/v2/revenue/taxonomy.py canonical; 12 lines/34 groups verbatim; verify_taxonomy [1] |
| T-A2 | R10 | classify by hierarchy path, not name; dual-name cases correct | DONE | 8225cbe | path-scoped ids; resolve_path on (level_one, level_two); AmbiguousPathError on name-only dual cases; verify_taxonomy 33/33 PASS |
| T-A3 | R10 | propagate taxonomy through DDL→catalog→loading→manifest→both builders→both tiers | DONE | 8225cbe | no DDL change (ids/data only) — schema artifacts regenerated, zero drift; manifest via builders; both tiers data-driven; real-path proven on B6 fixtures |
| T-B1 | R10 | eligibility: NULL/empty/__NONE__ credited; 91/92/9L flip to non-credited; excluded set unchanged | DONE | 0ce93ae | seed flip only; verify_eligibility 25/25 PASS; recon $0.00 |
| T-B2 | R10 | evidence: annotate the `less excluded` line with its reason-code breakdown | DONE | 0ce93ae | excluded_detail in breakdown (rendering only); modal note like non-credited line; older evidence -> optional field |
| T-C0 | R10 | confirm per-month reason-code availability; report gap if missing | DONE | 8218f0e | CONFIRMED: nc txn rows carry account_no/month_id/reason_cd per month — no gap |
| T-C1 | R10 | INHERITANCE driver (9G flip) + 6-month cooling-period code note | DONE | 8218f0e | -(Δ nc 9G); flip lists in inputs; cooling note in attribution.py; DERIVED |
| T-C2 | R10 | HOUSEHOLD driver (9E flip), not double-counted with ELIGIBILITY | DONE | 8218f0e | -(Δ nc 9E); ELIGIBILITY excludes 9G/9E — three sum exactly to -(Δ total nc) |
| T-C3 | R10 | attribution order + reconciliation with new drivers | DONE | 8218f0e | before ELIGIBILITY remainder; verify_new_drivers PASS; recon $0.00; MIX clean |
| T-D1 | R10 | CLAWBACK scoped to Annuities/Insurance/Life (real hierarchy names confirmed) | DONE | de0f7ea | scope by hierarchy position (taxonomy.clawback_group_ids); verify_clawback_scope 12/12; DATA GAP: 'Life' product code = assumed 'LIFE' — real hierarchy operator-local (see Decisions) |
| T-E1 | R10 | Env Health LLM connectivity section (writer/judge/assistant), cheap ping, no secrets | DONE | bbe5dca | models.retrieve/list only; judge 404 -> "model not found in subscription" proven live; card red on any non-mock-judge UNAVAILABLE |
| T-F1 | R10 | seed + glossary order for INHERITANCE/HOUSEHOLD | DONE | 8218f0e | display_name/description/computation seeded; display_order 4/5 before ELIGIBILITY; e2e asserts sorted 1..19; frontend literal-free (grep: only a V1 search icon label matches "Household") |
| T-G1 | R10 | docs/ROUND10_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived c1b0f72..HEAD; + ROUND10_ACCEPTANCE.md + BUILD_REPORT §16; commentary v21 additive |
| P-A1 | R11 | taxonomy: add Alternative Investments (non-recurring, assumption noted) | DONE | 360b19a | ALTI leaf, NON_RECURRING assumed (comment); sample 13 lines/35 groups; verify_taxonomy [4b] |
| P-A2 | R11 | only PRODUCT_TYPE rows reach resolve_path; guard + loud log otherwise | DONE | 360b19a | grid_type kwarg guard (NonProductGridRowError + stderr); build_real_data filters pre-classification, nongrid_* holding lines; verify_taxonomy [7] 42-path fixture |
| P-B1 | R11 | commentary versions per-advisor (advisor_sid on version, propagated, supersede within advisor) | DONE | d41cda6 | full R8-A4b chain; supersede within advisor; legacy global "" until regenerate-all; version ids stay globally unique (decision) |
| P-B2 | R11 | anomaly scans per-advisor | DONE | d41cda6 | advisor_sid on scan; per-advisor rows persisted additively; GQ-018/019 advisor-aware both tiers |
| P-B3 | R11 | two buttons each (this advisor / all) on both screens, clearly labelled | DONE | 95877ec | "Regenerate/Rescan (this advisor)" navy + "… all" outline; tooltips state scope |
| P-B4 | R11 | per-advisor selectors; other advisors unaffected by single regenerate | DONE | 95877ec | selectors filter to scoped+legacy; verify_per_advisor [2]/[3] proves B untouched, figures byte-identical |
| P-C1 | R11 | async workflows + status endpoint (build on existing _status) | DONE | d41cda6 | start_generation/start_scan daemon threads on the SAME _status; job id + advisor N of M + result ids; POST during run returns running job |
| P-C2 | R11 | progress overlay on both screens; auto-refresh to new version on completion | DONE | 95877ec | shared useAsyncJob + JobProgressOverlay; auto-select latest on done; failure persists until dismissed |
| P-C3 | R11 | poll not hang; mid-run reopen rejoins | DONE | 95877ec | 1.5s GET-only poll; mount-time rejoin of running job; proven headless (browser rescan, 0 console errors) |
| P-D1 | R11 | backfill sample data for every use case (9G/9E flip, dual Annuities, clawback, mixed acct, each anomaly, eligibility flip, clean transitions) | DONE | b14799f | July 2026 added; rescan-all fires ALL 6 rules; 92+9L present; May→Jun clean per advisor; SMPL002 Jun→Jul = crafted residual demo (exempted by name) |
| P-D2 | R11 | sample reconciliation $0.00; per-scenario comments in the generator | DONE | b14799f | recon $0.00 asserted by builder + e2e; every crafted scenario commented with its use case |
| P-D3 | R11 | standing principle documented: new use cases ship with sample data | DONE | b14799f | CLAUDE.md rule 10 + SOLUTION_GUIDE Round-11 standing rule |
| P-E1 | R11 | verify R10 Env Health LLM section | DONE | (verify) | live check: writer/judge/assistant all model-found; no regression, nothing rebuilt |
| P-F1 | R11 | docs/ROUND11_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived ddf1172..HEAD; + ROUND11_ACCEPTANCE.md + BUILD_REPORT §17 |
| Q-A | R12 | per-role keys (WRITER_/JUDGE_/ASSISTANT_ × MODE/MODEL/DEPLOYMENT/API_VERSION) + .env.example; shared role-resolution helper | DONE | 616b887 | app/llm/roles.py resolve_role_config; existing keys reused (ASSISTANT_LLM_MODE = assistant mode key; JUDGE_MODEL kept) |
| Q-B | R12 | client builder accepts api_version/deployment overrides; all three roles use the helper+builder | DONE | b55047c | Real + Cdao adapters take deployment/api_version; claude/mock/azure ignore with log; guarded cdao import intact |
| Q-C | R12 | auto-fallback to default agent LLM on role-config failure; served path recorded (config/fallback/unavailable) per role | DONE | 810a006/dcf703a | RoleLLM single-retry wrapper; llm_path on commentary+evaluations; assistant R7 chain preserved, R12 retry = final link; verify_role_llm 32/32 |
| Q-D | R12 | Env Health shows each role's effective config + reachability + "will fall back" state | DONE | af79044 | per-role mode/model/deployment/api_version + will-fall-back note; no secrets (programmatic check) |
| Q-D2 | R12 | .env.example: commented examples for every new key incl. deployment-vs-model-vs-apiversion note; completion doc "how to configure each role" table | DONE | 616b887/f7359e3 | .env.example block in Q-A; ROUND12_ACCEPTANCE config table + operator drill |
| Q-E | R12 | docs/ROUND12_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived eb9b6a2..HEAD; conflict flags on settings/.env.example/client.py/commentary_agent/generation_workflow/env-health-workspace; + BUILD_REPORT §18 |
| Q-F | R12 | glossary display_order sorted as STRING (R8/R9 defect): numeric order enforced on every path + regression test | DONE | 8d883d6 | DDL already INT; service re-imposes numeric order (covers STRING-typed live graph via tier 1); local-tier _int via float; frontend explicit Number(); GQ-004 header reinstall note; verify_glossary_order 7/7. LIVE-VERIFIED in Codespace 2026-07-25: app restarted (8001/3001), API returns 1..19 ascending, glossary dialog on /ai-insights renders Volume(1)→Average Transaction Value(2)→…→Baseline Period(19), zero console errors (headless Chromium + screenshot) |
| Q-G | R12 | cosmetic: collapsed Ask iPerform launcher = labelled pill (MessageCircle + "Ask iPerform"), icon-only circle on small viewports | DONE | (this) | navy/hover/position/z-40/print:hidden/aria-label unchanged; expanded panel header untouched; no logic change; verified headless both viewports, panel opens, 0 console errors |
| R-A | R13 | build_cdao_openai_client + per-role builder: empty api_version ⇒ omit it (workspace_id only), config-driven | DONE | 2772d3f | empty/None/blank ⇒ workspace_id-only construction; non-empty unchanged; fixture-verified via fake cdao module; per-role + embedding funnel through the same builder |
| R-B | R13 | CDAO_TEMPERATURE + WRITER/JUDGE/ASSISTANT_TEMPERATURE (default 1) threaded via roles.py into every cdao create | DONE | 712aea1 | RoleLLMConfig.temperature (never counts as R12 config); threaded through build_llm_client into Real+Cdao adapters, judge legacy R9 E path, assistant primary link; unconfigured writer = main singleton (CDAO_TEMPERATURE); .env.example 4 new keys |
| R-C | R13 | remove max_tokens from cdao create calls (main + per-role); leave Anthropic untouched | DONE | 8569ff6 | removed from Real+Cdao chat-completions creates; Anthropic messages.create max_tokens=1024 is the only one left in client.py (asserted) |
| R-D | R13 | Env Health per-role probe uses the same corrected construction/call | DONE | 1eaee0b/9f9bb62 | corrected construction + minimal one-word create on cdao (discarded, no secrets); verify_gpt5_compat 34/34; all suites re-run PASS, recon $0.00, tsc clean; ROUND13_ACCEPTANCE.md written |
| R-E | R13 | docs/ROUND13_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived 0427bb8..HEAD; client.py flagged ⚠ operator-patched-locally (repo supersedes); + BUILD_REPORT §19 |
| S-A | R14 | add `guardrail` LLM role (roles.py ROLES + settings + env keys + Env Health row + .env.example) | DONE | 038980f | guardrail role in ROLES; GUARDRAIL_LLM_MODE/MODEL/DEPLOYMENT/API_VERSION/TEMPERATURE via the R12 per-field helper (R13 GPT-5 handling inherited); Env Health "guardrail classifier" row; .env.example block |
| S-B | R14 | LLM input classifier in screen_input, after regex, before routing; strict-JSON {category,confidence,reason}; example-rich system prompt | DONE | e2050b9 | intent_classifier.py: one constrained guardrail-role call, strict JSON {category,confidence,reason}; deterministic keyword classifier in mock mode; ClassifierUnavailable on any failure |
| S-C | R14 | decision policy with config thresholds (GUARDRAIL_BLOCK_THRESHOLD, GUARDRAIL_LLM_ENABLED); combine with regex, never downgrade | DONE | e2050b9 | GUARDRAIL_BLOCK_THRESHOLD + GUARDRAIL_LLM_ENABLED + GUARDRAILS_ENABLED all config; classifier never downgrades a regex BLOCK; off_scope_use -> polite OUT_OF_SCOPE before routing |
| S-D | R14 | hardened assistant system prompt (scope-locked, no-instruction-reveal, no-arbitrary-exec, input-as-data) | DONE | e2050b9 | system_prompts.py hardened narrator prompt: scope lock, no instruction reveal, no arbitrary exec, input-as-data; wired in service.py |
| S-E | R14 | fail-safe: classifier failure never fails open; degradation logged | DONE | e2050b9 | ClassifierUnavailable -> FAILS SAFE: regex result stands, CLASSIFIER_DEGRADED finding, GUARDRAIL DEGRADATION warning logged; never open, never full-trust |
| S-F | R14 | output check: block system-prompt/instruction leak + PII surfacing | DONE | e2050b9 | screen_output blocks system-prompt/instruction leaks (deterministic fragment check) on top of existing numeric/PII checks; leaking text never displayed |
| S-G | R14 | visibility: classifier blocks render ⛉ GUARDRAIL (category+severity only), reason never shown | DONE | e2050b9 | persisted findings carry category+severity+action ONLY (reason is log-only); existing R9 chip renders them unchanged — payload shape identical, no frontend change needed; proven by fixture 6.x + persisted sample conversations |
| S-H | R14 | mock guardrail LLM + fixtures: paraphrased attacks blocked, benign pass, regex intact, fail-safe, output leak | DONE | 3ca2685/0c52ad7 | verify_guardrail_llm.py 54/54 (attacks block, benign pass, regex independent, no-downgrade, PII-before-classifier, fail-safe, visibility, output leak, Env Health, thresholds); + 9c2727d role_llm 5.1 additive row (32/32); fixture conversations committed 0c52ad7 |
| S-I | R14 | docs/ROUND14_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) | DONE | (wrap) | git-derived 1550f74..HEAD; additive-config conflict notes; operator-local excluded; + ROUND14_ACCEPTANCE.md + BUILD_REPORT §20 |

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
| 2026-07-22 | Evidence modal __TOTAL__-scoped drivers get an explicit "Total — all product groups" scope whose waterfall aggregates ALL causes | FIX_SPEC_R4 A2 allows a transition-level view only if explicitly labelled; MARKET/NET_FLOW attach to __TOTAL__ and a total-only waterfall could not reconcile |
| 2026-07-22 | Group waterfall REBUILT in the modal from stored rows (group change row + group drivers), not re-stored per version | Stored evidence keeps the transition waterfall; per-group attribution with per-group MIX residual makes the group walk exact from data already stored — arranging stored numbers is presentation, not computation |
| 2026-07-22 | Shared ingestion manifest reflects the ACTIVE data set; repo keeps sample scope | build_real_data.py rewrites it with real counts on the client machine; after the local fixture proof the sample manifest was regenerated so the committed state stays sample-scoped |
| 2026-07-22 | Real product_name = "product_cd sub_cd"; account_typ/wrap_flg blank; blank advisor names -> id shown | The extracts carry no display names/types — never invent data (CLAUDE.md §11) |
| 2026-07-22 | Fixture GENERATOR committed (make_test_raw_extracts.py); fixture DATA gitignored under data/real/_raw | Reviewers can reproduce the B6 proof; FIX_SPEC_R4 forbids committing anything under data/real/ |

| 2026-07-23 | Fallback-tier write in real mode FAILS the batch | root cause of 'created=2, graph empty' — a lost write must never checkpoint as success |
| 2026-07-23 | Failed delete keeps the entity's checkpoints | screen state must stay consistent with the graph |
| 2026-07-23 | Sample LOST_ACCOUNT story moved to May->Jun + Apr-only account added | Apr->May is baseline-limited after D1; both causes must stay exercised |
| 2026-07-23 | verify_end_to_end cause check 15->16 | script asserted the pre-D1 cause model (old behaviour), per W14 |
| 2026-07-23 | Sample CSVs git-mv'd BEFORE regeneration (C1) | preserve_or_create looks for new names; renaming first kept commentary v1-v13 history |
| 2026-07-23 | R6: BASELINE_LIMITED generalised to BOTH edges of the loaded range (not just the first transition) | the persistence test is unevaluable wherever too few months are loaded on one side; last-transition stops are equally unconfirmable |
| 2026-07-23 | R6: legacy_two_month_presence kept as an explicit TEST-ONLY parameter | verify_attribution proves the bug and the fix on the same fixture; documented never-in-production |
| 2026-07-23 | R6: anomaly_id scan-prefixed, deviating from spec's advisor\|from\|to\|rule | un-prefixed ids made re-scans upsert over prior scans, breaking Y3's additivity; commentary ids embed version the same way |
| 2026-07-23 | R6: sample anomaly scan001 committed as the stored demo scan | screen renders real stored data out of the box; re-scan adds scan002+ additively |
| 2026-07-23 | R7: assistant gate drops PII-ACCOUNT findings (both directions) | account numbers are the app's subject matter; A11 requires "show me account 83700968" to pass; SSN/card/email/phone stay enforced |
| 2026-07-23 | R7: added GuardrailService.neutral_refusal() instead of changing safe_refusal | A9 wording must be neutral/brief; V1 surfaces keep their existing message |
| 2026-07-23 | R7: rejected narration falls back to the deterministic template (non-AI), not BLOCKED | template is built only from stored figures — unvalidated text still never displays; same pattern as R6 anomaly wording |
| 2026-07-23 | R7: cross-advisor questions list per-advisor stored figures, never a computed sum | a sum would be a figure no query returned |
| 2026-07-23 | R7: stored commentary quoted verbatim, exempt from answer-time re-validation | validated at publication (R5 judge + guardrail); re-narration would risk drift |
| 2026-07-24 | R8: operator's attribution edits were committed to prompts/ (fdb67fe, 84b7287) but never installed at app/v2/drivers/attribution.py — installed `prompts/attribution (1).py` (the later one) verbatim as the live module | diff vs live module removes only the two described changes (VOLUME-only step, R6 A3 abort); FIX_SPEC_R8 says the fixes are "already in the repo" and the arithmetic is settled — installing the operator's file is applying, not changing, it. prompts/ copies left untouched |
| 2026-07-24 | R8: per-account revenue maps + classification_rule added to NEW/LOST/BASELINE_LIMITED inputs_json | C says "the data already exists in inputs_json" but per-account revenue did not — adding RENDERING data to inputs (module contract: "every number an attribution used lands in inputs_json") is not an arithmetic change; contributions untouched; sample regenerated anyway for DEAL_SIZE |
| 2026-07-24 | R8: guardrail check 5 extended — a parenthesised figure must trace to a computed NEGATIVE value | rule 8 makes parens MEAN negative; v18 proved the model can write "($7.0k)" for a +7,000 TIMING offset. v18 kept in history (1 BLOCKED), v19 regenerated clean 6/6 |
| 2026-07-24 | R8: legacy cause_name/cause_description seeded as mirrors of display_name/description | keeping two independently-editable name fields would recreate the exact drift class this round removes; the legacy columns stay only for schema compatibility |
| 2026-07-24 | R8: baseline label = FIRST transition only; the other edge keeps the R6 edge-note | FIX_SPEC_R8 B defines THE baseline transition as earliest from_month; the last transition's unevaluable-stop case is a different (persistence) limitation and keeps its existing wording |
| 2026-07-24 | R8: client's revised driver spec recorded in SOLUTION_GUIDE §10.13, NOT coded | conflicts with the CWM PCR Confluence mapping (FIX_SPEC_R8 §D); needs operator/client reconciliation first |

| 2026-07-25 | R9: account drivers claim only the RECURRING rows of claimed accounts; their one-time/adjustment rows stay in the pool for the ONE_TIME step | FIX_SPEC_R9 A: excluded rows' revenue "is already claimed by the one-time path — do not double-count and do not route to MIX"; removing whole accounts would have dropped a lost account's one-time to-month row into MIX |
| 2026-07-25 | R9: PUBLISHED_FALLBACK introduced as a commentary status VALUE (data, not schema); rendered with a "Deterministic fallback" tag, never the AI chip | marks the D3 template without a schema change (G forbids); rule 8a is one-directional — non-model text must never carry the AI chip |
| 2026-07-25 | R9: judge unavailable state stored as -1.0 sentinel in the DOUBLE score columns | schema unchanged (G); UI renders "— (unavailable)" for negative scores — 0.00 can no longer mean "could not run" |
| 2026-07-25 | R9: JUDGE_MODEL default changed "claude-sonnet-5" -> "" (= active mode's default model; claude mode still resolves to claude-sonnet-5 in code) | the old default was a Claude model name that 404s on cdao — exactly the client-env failure |
| 2026-07-25 | R9: verify_ingestion_fixes "delete-all continues past failing entity" FAILS pre-existing at the round-8 baseline (verified in clean worktree) | not a round-9 regression; ingestion out of scope this round (G); recorded for round 10 |
| 2026-07-25 | R9: anomaly rescan artifacts (scan002) reverted before wrap commit | committed sample state stays deterministic at the scan001 demo scan (R6 decision) |

| 2026-07-25 | R10: unknown product lines (absent from every A1 path) default to NON_RECURRING with a loud stderr warning listing them | class by ABSENCE from the recurring paths is a position decision, not a name match; non-recurring is the conservative class (no account-presence gating); dual-name lines still STOP the build |
| 2026-07-25 | R10: quarterly TIMING story moved from Alternative Investments (not in A1) to MAC under Trails; legacy group ids kept in QUARTERLY_BILLED_GROUPS for pre-R10 fixtures | A1 is authoritative and has no Alternatives line; TIMING group membership is config, not the settled VOLUME/DEAL_SIZE arithmetic |
| 2026-07-25 | R10 DATA GAP: the REAL raw_product_hierarchy.csv is operator-local — dual-name distinguishability is proven on the extract SHAPE ((level_one, level_two) path) and fixtures; if the client extract carries a dual-name line with a group A1 does not list, build_real_data STOPS with the exact paths | never guess by name (A2); the operator sees the ambiguous paths verbatim |

| 2026-07-25 | R10 DATA GAP (D): the "Life" product-code identifier could not be verified against the real product hierarchy (operator-local); coded as case-insensitive product_cd == "LIFE" in taxonomy.CLAWBACK_PRODUCT_CODES with a code comment | spec D requires confirming identifiers against raw_product_hierarchy.csv — unavailable in this environment; the Annuities/Insurance group scope IS confirmed against the A1 hierarchy positions |

| 2026-07-25 | R11: Alternative Investments (ALTI) classified NON_RECURRING as an ASSUMPTION pending client confirmation | FIX_SPEC_R11 A1; code comment in taxonomy.py marks the revisit point |
| 2026-07-25 | R11: non-PRODUCT_TYPE hierarchy rows register their products under nongrid_* holding lines instead of being dropped | their transactions need a product home; CREDITED_GRID_TYPES config already keeps them OUT_OF_GRID; dropping them would default unknown products to PRODUCT_TYPE and wrongly credit them |
| 2026-07-25 | R11: version_id/version_no remain GLOBALLY unique; per-advisor scope lives in advisor_sid only | collision-free ids, totally-ordered history, minimal ripple through commentary/evidence id formats; "A on v24 while B on v23" satisfies B1's independence requirement |
| 2026-07-25 | R11: legacy global versions/scans (advisor_sid "") stay PUBLISHED/current until a regenerate-all supersedes them | a single-advisor run must not tear down the version other advisors still resolve to |
| 2026-07-25 | R11: regenerate-all / rescan-all iterate advisors SERIALLY (was a 4-wide pool) | honest "advisor N of M" progress for the C2 overlay; each advisor's version independent; fine at 10-advisor scale |
| 2026-07-25 | R11: SMPL002 Jun→Jul is a DELIBERATE >15%-MIX transition (asset growth with no source data + 9E carve-out overlap); e2e/attribution exempt exactly that key and assert >15% on it | UNEXPLAINED_RESIDUAL cannot be demonstrated on sample data any other way (the rule's threshold IS the MIX gate) |
| 2026-07-25 | R11: committed sample demo state = per-advisor commentary v22–v24 + scans 003–005; scan001/002 kept as legacy-global history | supersedes the R6 "scan001 is the committed demo scan" decision; versions/scans are additive, never deleted |
| 2026-07-25 | R11 DEFECT FIX: assistant figures payload keyed by label collapsed duplicate labels (several same-product rows on one account) and the guardrail rejected honest figures | keys uniquified in service + verify_assistant; figures_json was always complete; surfaced by the July syndicate rows |

| 2026-07-25 | R12: JUDGE_MODEL alone (or ASSISTANT_LLM_MODE alone) does NOT count as R12 role config — the exact R9/R7 code paths are kept; only a NEW key engages RoleLLM + auto-fallback | those keys predate R12 and participated in the old behaviour; treating them as R12 config would change R9/R7 semantics (regression) |
| 2026-07-25 | R12: a judge whose auto-fallback would land on the MOCK adapter returns None (honest UNAVAILABLE) instead of a RoleLLM | mock's deterministic template cannot judge language; a pseudo-verdict would be fabricated (F4: judge never 0.00, never a fake PASS) |
| 2026-07-25 | R12: on the Azure-shaped adapters the single OpenAI-SDK `model=` request param IS the deployment routing name — a role's DEPLOYMENT (when set) takes precedence over its MODEL id for the request, logged when they differ | the SDK offers one field; spec A says route by deployment, best-effort single value when only one is set |
| 2026-07-25 | R12: assistant turns surface "[served: …]" in llm_provider only when R12 config is set or a fallback actually happened | unconfigured clean turns keep byte-identical R7 labels (no regression); served_path is always on the generate() result |
| 2026-07-25 | R13: the spec's "main cdao create ~line 200 / max_tokens ~line 202" is RealLLMClient.generate (direct Azure OpenAI chat-completions) — B+C applied to BOTH chat-completions adapters (RealLLMClient + CdaoOpenAILLMClient); its temperature default is the same CDAO_TEMPERATURE | the spec's line refs match client.py exactly (14, 151/153, 359-364), so line 200/202 was intended; both adapters are Azure OpenAI chat-completions with identical GPT-5 constraints; Anthropic untouched |
| 2026-07-25 | R13: *_TEMPERATURE never counts toward R12 configured_fields (always present, default 1); an unconfigured writer keeps the main singleton, so WRITER_TEMPERATURE applies only when the writer is R12-configured — judge (legacy R9 E path) and assistant (primary link) DO get their role temperature without R12 config, as a call-detail-only change | all-empty role config must stay byte-identical to R12 (spec F6); the shared main singleton must not take one role's temperature; judge/assistant build their own clients so threading their temperature there changes no construction path |
| 2026-07-25 | R13: Env Health cdao probe = minimal one-word completion via the adapter's generate() (discarded), replacing the models lookup ONLY for cdao_openai; other modes keep the R10 cheap lookup | spec D mandates the probe use the same corrected create; a models lookup cannot prove a GPT-5 deployment serves completions; claude/real probes stay proven-live R10 behaviour |
| 2026-07-25 | Q-F: glossary order fixed by ENFORCING numeric sort at the service layer (both tiers) rather than only reinstalling the live graph's schema | repo DDL/catalog/CSVs/local tier were already INT and correct — the lexicographic order can only come from a pre-R8 STRING-typed live graph via GQ-004's ORDER BY; the service guard fixes rendering regardless of the installed schema, and the GQ-004 header directs the schema reinstall. No display_order VALUE or display_name changed |

| 2026-07-26 | R14 session-15 resume: git established as truth over stale PROGRESS.md (S-A..S-H code already committed 038980f..9c2727d); the 4 dirty sample CSVs identified as the intended S-H fixture conversations and committed (0c52ad7), not discarded; ROUND14_STARTER_PROMPT.md gitignored, never committed | Codespace died mid-round-14 before the progress file was truthed up; §0.1 protocol — git is the truth, the progress file is the claim |

## Blocked / deferred
| Task | Reason | What would unblock it |
|------|--------|----------------------|
