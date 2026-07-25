# ROUND 10 CHANGED FILES (git-derived: c1b0f72..HEAD)

Derived from `git diff --name-status c1b0f72..HEAD` plus the wrap commit.
Operator-local artefacts (`data/real/**`, `prompts/**`, gitignored
`docs/qa_screenshots/*.png`) are excluded — nothing under them is touched by
this round's code, but `build_real_data.py` output will differ on rebuild
(new taxonomy ids, new eligibility totals, new drivers).

**CONFLICT-RISK** marks files the operator may have edited locally — diff
before overwriting.

## Work-stream A — taxonomy
| File | Change |
|---|---|
| `app/v2/revenue/taxonomy.py` | NEW — canonical A1 hierarchy, path-based classification, clawback scope |
| `scripts/generate_sample_data.py` | taxonomy from the module; dual-name products both sides; MAC timing story; 9G-flip story; annuity reversals | CONFLICT-RISK
| `scripts/build_real_data.py` | dimensions from A1; path resolution; ambiguity STOP; unknown-line warning | **CONFLICT-RISK**
| `app/v2/drivers/attribution.py` | QUARTERLY_BILLED_GROUPS += rec_trails__mac (see also C/D below) | **CONFLICT-RISK**
| `scripts/verify_taxonomy.py` | NEW — 33 checks |
| `data/sample/**` (non-workflow CSVs) | regenerated under the A1 taxonomy + R10 rules |
| `docs/tigergraph_foundation/data/manifest.json` | regenerated (sample-scoped counts) | **CONFLICT-RISK**

## Work-stream B — eligibility
| File | Change |
|---|---|
| `app/v2/revenue/eligibility.py` | 91/92/9L -> NON_CREDITED; rule restated; excluded set untouched |
| `app/agents/nodes/explainability_agent.py` | excluded_detail on the credited breakdown (see also C) |
| `frontend/components/evidence/evidence-modal.tsx` | `less excluded` annotation | **CONFLICT-RISK**
| `scripts/verify_eligibility.py` | NEW — 25 checks |

## Work-stream C — new drivers
| File | Change |
|---|---|
| `app/v2/drivers/attribution.py` | INHERITANCE/HOUSEHOLD carve-outs before the ELIGIBILITY remainder; cooling-period note | **CONFLICT-RISK**
| `app/v2/dataset/builder.py` | driver_cause seed: 19 causes, INHERITANCE 4 / HOUSEHOLD 5 | **CONFLICT-RISK**
| `app/agents/nodes/explainability_agent.py` | findings/order/steps/why panels for both; ELIGIBILITY carve-out text |
| `scripts/verify_new_drivers.py` | NEW |
| `scripts/verify_end_to_end.py` | 17 -> 19 cause expectations |
| `scripts/verify_assistant.py` | two routing fixtures updated to path-scoped group ids |

## Work-stream D — chargeback scope
| File | Change |
|---|---|
| `app/v2/revenue/taxonomy.py` | clawback_group_ids() + CLAWBACK_PRODUCT_CODES ("LIFE" assumed — operator check) |
| `app/v2/drivers/attribution.py` | CLAWBACK gated; out-of-scope reversals stay unlabelled in ordinary buckets |
| `app/v2/dataset/builder.py` | passes the taxonomy-derived scope |
| `scripts/verify_clawback_scope.py` | NEW — 12 checks |

## Work-stream E — LLM connectivity
| File | Change |
|---|---|
| `app/services/llm_connectivity.py` | NEW — per-role rows, models-lookup only, secret-stripped |
| `app/services/environment_health_service.py` | report carries llm_connectivity |
| `frontend/lib/api/env-health.ts` | LlmConnectivityRow type |
| `frontend/components/env-health/env-health-workspace.tsx` | "LLM connectivity" card | CONFLICT-RISK

## Wrap
| File | Change |
|---|---|
| `data/sample/**` (workflow CSVs) | commentary v21 appended (additive; v1–v20 preserved) |
| `PROGRESS.md`, `BUILD_REPORT.md`, `docs/ROUND10_ACCEPTANCE.md`, this file | round bookkeeping |
| `ROUND10_STARTER_PROMPT.md` | round input, committed for the record |
