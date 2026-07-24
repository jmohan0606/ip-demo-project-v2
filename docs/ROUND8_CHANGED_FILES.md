# Round 8 — Changed files (git-derived)

Derived from `git diff --name-status e42622c..HEAD` (end of round 7 → end of round 8).
**Excluded as operator-local:** `prompts/attribution.py` and `prompts/attribution (1).py`
(the operator's own commits fdb67fe / 84b7287 — untouched by this round; their content
was *installed* at `app/v2/drivers/attribution.py`, see stream 0), everything under
`data/real/` (gitignored) and `docs/qa_screenshots/` (gitignored, regenerable via
`node scripts/capture_evidence.mjs`).

**⚠ CONFLICT-RISK** flags files an operator commonly edits locally — diff before pulling.

## Stream 0 — attribution install (context fix)

| File | Change |
|---|---|
| `app/v2/drivers/attribution.py` ⚠ CONFLICT-RISK | Operator's `prompts/attribution (1).py` installed verbatim (DEAL_SIZE for all groups w/ recurring netting; A3 abort → gross-movement WARNING), then R8 additions: per-account revenue + `classification_rule` in NEW/LOST/BASELINE_LIMITED `inputs_json` (rendering data only), baseline transition exempt from the MIX self-check (logged as informational). Arithmetic untouched. |
| `scripts/verify_attribution.py` | Asserts the settled R8 behaviour (legacy bug = gross misattribution; over-net BL completes + reconciles instead of aborting). |

## Stream A — driver metadata from data

| File | Change |
|---|---|
| `docs/…/schema/01_vertices.gsql` | `phx_dm_v2_driver_cause` + `display_name`, `description`, `computation`. |
| `docs/…/schema/schema_catalog.json`, `docs/…/loading/jobs/load_v2_all.gsql`, `docs/…/schema/90_drop_all.gsql` | **Regenerated** by `scripts/generate_schema_artifacts.py` — never hand-edit. |
| `docs/…/data/manifest.json` ⚠ CONFLICT-RISK (rewritten by `build_real_data.py` on the client machine) | driver_cause columns + expected_rows 17. |
| `docs/…/queries/GQ-004_get_driver_causes.gsql`, `query_catalog.json` | Header/outputs describe the new attributes (whole-vertex PRINT carries them; **needs live reinstall**). |
| `app/v2/dataset/builder.py` | Seed = single metadata source, all 17 causes incl. DEAL_SIZE; CLAWBACK display_name "Charge Back"; legacy `cause_name`/`cause_description` mirrored from the new fields; `mix_share` carries `is_baseline`. |
| `frontend/lib/v2/driver-causes.tsx` (new) | Cached GQ-004 fetch + `useDriverCauses()` — the single frontend source of driver names. |
| `frontend/lib/api/v2.ts` ⚠ CONFLICT-RISK | `DriverCause` type + new fields. |
| `frontend/components/patterns/revenue-driver-glossary.tsx` | Hardcoded table **deleted**; renders from the query. |
| `frontend/components/patterns/provenance-badge.tsx` | `CauseTag` shows stored `display_name` (description on hover). |
| `frontend/components/ai-insights/export-data.ts` | Export names read `display_name`. |
| `frontend/app/(dashboard)/anomalies/page.tsx` | Threshold phrases naming a driver resolve its display_name. |
| `app/agents/nodes/revenue_agent.py` | Driver payload carries `cause_display_name`; flags `is_baseline_transition`. |

## Stream B — baseline transition labelled

| File | Change |
|---|---|
| `frontend/components/patterns/baseline-note.tsx` (new) | Identification from GQ-002 (earliest loaded month) + shared note/tag components. |
| `frontend/components/ai-insights/commentary-cards.tsx` | Baseline card: tag + full amber note; edge note retained for the other edge. |
| `frontend/components/ai-insights/monthly-walk-table.tsx` | Baseline row: tag + limitation line before the narrative. |
| `frontend/components/ai-insights/insights-chart-card.tsx` | Baseline arrow pill: BASELINE chip + tooltip. |
| `frontend/components/evidence/evidence-modal.tsx` ⚠ CONFLICT-RISK | Baseline banner (also stream C below). |
| `app/v2/anomalies/detection.py` | `UNEXPLAINED_RESIDUAL` never fires on the baseline transition. |
| `scripts/build_real_data.py` | Summary prints the baseline transition as `[baseline — indicative attribution]`, not a MIX failure. |
| `app/agents/nodes/commentary_agent.py` | Prompt v1.1: states the baseline limitation; deterministic fallback prefixes it; DEAL_SIZE fallback sentence; strict parenthesis rule. |
| `app/guardrails/numeric_validation.py` | Check 5 extended: a parenthesised figure must trace to a computed NEGATIVE value. |

## Stream C — account comparison in evidence

| File | Change |
|---|---|
| `frontend/components/evidence/evidence-modal.tsx` ⚠ CONFLICT-RISK | `AccountComparisonPanel` (account drivers only): rule from `inputs_json`, two ranked side-by-side lists w/ per-account revenue, top-20 + totals, Transactions link. DEAL_SIZE in waterfall order; display names on bars/chips. |
| `frontend/app/(dashboard)/transactions/page.tsx` | New `?accounts=` filter (chip + filtered footer). |
| `app/agents/nodes/explainability_agent.py` | DEAL_SIZE finding/why/waterfall-order entries; VOLUME rule text updated to count-effect-only. |

## Regenerated data + verification

| File | Change |
|---|---|
| `data/sample/vertices/*.csv`, `data/sample/edges/*.csv` | Regenerated: 17-cause seed, DEAL_SIZE drivers, enriched inputs_json; commentary versions **v15–v19 appended** (additive — v1–v14 history preserved; v18 carries one guardrail-BLOCKED transition as history). |
| `scripts/verify_end_to_end.py` | 17-cause assertion. |
| `scripts/capture_evidence.mjs` | Shots 14 (baseline labelled) + 15 (account comparison). |
| `docs/SOLUTION_GUIDE.md` | §10.13 open item: client's revised driver spec (UNRESOLVED, not coded); §6.4 DEAL_SIZE/metadata note. |
| `PROGRESS.md`, `BUILD_REPORT.md`, `docs/ROUND8_ACCEPTANCE.md`, `docs/ROUND8_CHANGED_FILES.md` | Round-8 bookkeeping. |
