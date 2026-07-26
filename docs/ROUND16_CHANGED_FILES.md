# ROUND 16 CHANGED FILES — git-derived (c78f67c..HEAD)

Derived from `git diff --name-status c78f67c..HEAD` (round-16 spec commit to
wrap). Operator-local files (`.env`, `data/real/*`, anything gitignored) are
never touched by this round and are excluded. **Conflict risk** flags files an
operator may have patched locally — on the client machine the repo version
supersedes; re-apply local config through `.env`, not code edits.

## A — commentary version key (W-A1/A2/A3)

| File | Change | Conflict risk |
|---|---|---|
| `app/v2/commentary/generation_workflow.py` | `version_id = "v{no}\|{advisor_sid}"`; `_latest_version_no(graph, advisor_sid)` per-advisor (advisor's own + legacy global "", NEVER a global max); supersede + `_supersede_global_versions` read through `get_commentary_versions` (both tiers, no store dependency); module docstring documents the collision | ⚠ HIGH — this file was operator-patched in earlier rounds; the repo version IS the round-16 root-cause fix and supersedes any local copy |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-009_get_commentary.gsql` | header only: R16 id-format note; R15.1 MaxAccum fix KEPT (not reverted); no logic change — NEEDS LIVE REINSTALL (with R15.1) | ⚠ the LIVE install is known-divergent (R15.1 SumAccum copy) — reinstall the repo file, do not merge |
| `frontend/lib/api/v2.ts` | `version_id` URL-encoded in `commentary()` and `evidence()` (ids now contain `\|`) | low |

## B — anomaly scan key (W-B1/B2/B3)

| File | Change | Conflict risk |
|---|---|---|
| `app/v2/anomalies/detection.py` | `scan_id = "scan{n:03d}\|{advisor_sid}"`; `_next_scan_id(graph, advisor_sid)` per-advisor via `get_anomaly_scans` (both tiers — old store-only read always returned scan001 on tier 1); module docstring documents the collision | ⚠ if patched locally — repo supersedes |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-018_get_anomalies.gsql` | header only: per-advisor latest-scan contract (advisor filter in BOTH passes) + scoped id format — NEEDS LIVE REINSTALL | ⚠ verify the installed copy has the advisor filter in both s1 and s2 |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-019_get_anomaly_scans.gsql` | header only: scoped id format note — NEEDS LIVE REINSTALL | low |

## C/D/E — migration, verification, wrap (W-C/W-D/W-E)

| File | Change | Conflict risk |
|---|---|---|
| `docs/ROUND16_ACCEPTANCE.md` | NEW — migration steps (targeted clear + CSV header reset + regenerate-all/rescan-all), no-ALTER confirmation, query-reinstall contract, live acceptance drill | none (new) |
| `docs/tigergraph_foundation/tigergraph/schema/91_clear_commentary_anomalies.gsql` | NEW — one-shot GSQL clear of ALL commentary/anomaly records (6 vertex types + 10 edge types + reverses, dependency-ordered, edges deleted explicitly first); no schema object dropped, no source data touched; NEEDS-LIVE-VERIFICATION | none (new) |
| `scripts/verify_round16.py` | NEW — 43 checks: multi-advisor bulk survival, double generate-all supersede-per-advisor, rescan-all, single-advisor no-clobber, dangling-reference audit, per-advisor sequences | none (new) |
| `docs/ROUND16_CHANGED_FILES.md` | NEW — this file | none (new) |
| `PROGRESS.md` | R16 session row + W-task rows + decisions | low (append-only) |
| `BUILD_REPORT.md` | §22 round-16 section | low (append-only) |

## NOT changed (deliberately)

- `01_vertices.gsql` / schema catalog / loading jobs — PRIMARY_ID columns are
  unchanged (`version_id STRING`, `scan_id STRING`); only the id VALUE format
  changed. **No schema ALTER needed.**
- `data/sample/**` — committed demo state untouched (verification runs in a
  temp copy). Legacy sample versions v1–v24 / scans 001–005 resolve correctly
  under the new per-advisor readers.
- Attribution / taxonomy / eligibility / figures — reconciliation stays $0.00.
- R11 scope model, R14 guardrails, R15 items — all suites re-run PASS.
