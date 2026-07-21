# FIX SPEC — iPerform V2, Round 2

> **Read this file completely before starting.** It supersedes `CLAUDE.md` where they
> conflict; everything in `CLAUDE.md` that this file does not change still applies —
> especially §0 (autonomous working), §0.1 (PROGRESS protocol) and §3 (absolute rules).
>
> The V2 build is complete and verified. This round corrects a **material business-logic
> error**, fixes two defects, deepens the evidence, and prepares the app for client review.

---

## 0. WORKING AGREEMENT (unchanged)

Run autonomously in auto mode. Do not pause, do not ask for approval, do not stop at
natural checkpoints. Use parallel subagents where marked. Commit granularly. Push after
each work-stream. Maintain `PROGRESS.md` exactly as before — **append these new tasks with
the R-prefixed ids below**; do not renumber the existing P-tasks.

At the end, update `BUILD_REPORT.md` with a new "Round 2" section.

---

## R1. CORRECTNESS — credited revenue is currently WRONG (do this first)

### The problem
The client's authoritative definition (Confluence *"Revenue Summary Data Mapping"*, CWM PCR):

```
Total Revenue    = post_split_credited_amt  (regardless of reason code)
Credited Revenue = post_split_credited_amt  WHERE reason code is NOT one of the
                                            ineligible codes (9E, 9G, 9C, 9S, 94)
```

We extract no `reason_cd` at all and sum everything. **Every revenue figure in the app is
therefore Total Revenue mislabelled as Credited Revenue** — pivots, chart, MoM deltas,
driver contributions, and every commentary sentence.

### The design — eligibility must be DATA-DRIVEN, not hardcoded

Two independent, configurable filters. Neither may be a hardcoded SQL `WHERE`.

**R1-1 — New vertex `phx_dm_v2_reason_code`**
```
PRIMARY_ID reason_code STRING     # "9E", "91", ... and "__NONE__" for rows with no code
description STRING                # client wording, e.g. "Minimum Household Policy"
ui_mapping STRING                 # e.g. "Small households"
owned_by STRING                   # PCE | iComp
eligibility STRING                # CREDITED | NON_CREDITED | EXCLUDED
include_in_credited BOOL
incentive_eligible BOOL
display_order INT
data_source STRING                # REAL (seeded from client documentation)
```

Seed exactly this:

| reason_code | description | ui_mapping | owned_by | eligibility | include_in_credited | incentive_eligible |
|---|---|---|---|---|---|---|
| `__NONE__` | No reason code — Grid transaction | Grid | PCE | CREDITED | true | true |
| `91` | Less than Minimum – Equity | Incentive non-eligible > Equity – below minimum | PCE | CREDITED | true | **false** |
| `92` | Less than Minimum – Mutual Fund | Incentive non-eligible > Mutual funds – below minimum | PCE | CREDITED | true | **false** |
| `9L` | Full Month LOA | Incentive non-eligible > LOA | iComp | CREDITED | true | **false** |
| `9E` | Minimum Household Policy | Small households | PCE | NON_CREDITED | false | false |
| `9G` | Inherited Account | Transferred accounts | PCE | NON_CREDITED | false | false |
| `9C` | Personal Transactions | Personal accounts | PCE | NON_CREDITED | false | false |
| `9S` | Account Block – Supervision | Other | PCE | NON_CREDITED | false | false |
| `94` | Account Block – Other | Other | PCE | NON_CREDITED | false | false |
| `9R` | Rep Code Not Found | *(not displayed)* | PCE | EXCLUDED | false | false |
| `98` | Sales After Termination | *(not displayed)* | iComp | EXCLUDED | false | false |
| `99` | Sales During Inactive Period | *(not displayed)* | iComp | EXCLUDED | false | false |
| `9H` | Sales Before Rep Code Assignment | *(not displayed)* | iComp | EXCLUDED | false | false |
| `9X` | A delete of the transaction | *(not displayed)* | PCE | EXCLUDED | false | false |
| `XX` | Transaction removed by the SOR for Annuities | *(not displayed)* | PCE | EXCLUDED | false | false |

Three states, deliberately: `EXCLUDED` rows are **not revenue at all** and must not appear
in Total, Credited or Non-Credited. The client doc only names two states; the third is our
correct reading of "no UI mapping" — record this in `BUILD_REPORT.md` as an interpretation.

**Assumption to record (client-confirmed for now):** 91/92/9L are **credited revenue** that
is merely incentive-ineligible. Flag it in the docs as an assumption to re-confirm.

**R1-2 — New edge** `phx_dm_v2_txn_has_reason` (revenue_transaction → reason_code), with
reverse edge.

**R1-3 — Transaction vertex gains**
`reason_cd STRING` · `rm_sid STRING` · `cs_sid STRING` ·
`revenue_eligibility STRING` (derived: CREDITED | NON_CREDITED | EXCLUDED) ·
`incentive_eligible BOOL` (derived) ·
`days_to_process INT` (derived: `proc_dt − trade_dt` in days) ·
`posting_month_id STRING` (see R1-7).

**R1-4 — Product vertex gains `grid_type STRING`**
(`PRODUCT_TYPE` | `NON_CREDITED_REVENUE` | `PAY_TYPE_SUMMARY`). Stored as an attribute,
**not** filtered at extraction. The revenue computation filters on it via config, so the
filter can be relaxed later without touching SQL or re-extracting.

**R1-5 — Extraction SQL changes** (`docs/data/extraction/`)
- Table names: `pcr.fpic_daily_trade_details_tb_prod` and `pcr.product_hierarchy`
  (see R3 — these must come from the source catalog, not string literals).
- **ADD** to the SELECT: `d.reason_cd, d.rm_sid, d.cs_sid, h.grid_type`
- **REMOVE** `AND h.grid_type = 'PRODUCT_TYPE'` from the WHERE. Pull it as a column.
- Rows whose `reason_cd` is null/blank map to `__NONE__`.

**R1-6 — Credited revenue definition (the core change)**
```
credited_revenue = Σ post_split_credited_amt
  WHERE reason_code.include_in_credited = TRUE            # from the vertex, never hardcoded
    AND product.grid_type IN CREDITED_GRID_TYPES          # config, default ['PRODUCT_TYPE']
    AND days_to_process <= MAX_PROCESSING_DAYS            # config, default 90
```
`CREDITED_GRID_TYPES` and `MAX_PROCESSING_DAYS` live in settings. The eligible reason set is
**read from the graph**, so seeding a new code changes behaviour with no code change.

The 90-day rule comes from the client doc: *"transactions older than 90 days should be
ignored as these transactions will not be sent to iComp."*

**R1-7 — `posting_month_id`** — set equal to the trade month for now, `data_source=ASSUMED`,
with the stated reason: *"Prior-period adjustments post to the proc_dt month; we cannot
identify closed months without the iComp feed, so posting month = trade month."* Structure
ready, assumption visible. Do **not** implement PPA logic in this round.

**R1-8 — New driver cause `ELIGIBILITY`** (REAL): revenue that moved between credited and
non-credited month over month (e.g. a household crossing the minimum-household threshold).
Compute as the change in non-credited revenue for the group, and slot it into the
attribution order immediately after `ONE_TIME`. This is a genuine business explanation and
only becomes possible once reason codes exist.

**R1-9 — Scope: the app shows CREDITED revenue only.** Total and Non-Credited are computed
and stored (they cost nothing extra and the evidence needs them — see R4-5) but are **not**
surfaced as screens or headline figures in this round.

**R1-10 — Regenerate commentary.** Every figure changes, so all stored commentary is now
stale. Run a fresh generation producing a new version; do not edit prior versions. Confirm
reconciliation still passes at $0.00 for every transition afterwards.

**R1-11 — Sample data** must be regenerated to include reason codes: at least one
transaction for each of `__NONE__`, `91`, `9E`, `9G`, `9X`, and at least one with
`days_to_process > 90`, so every eligibility path and the 90-day rule are exercised and
visible in the UI.

---

## R2. TWO CONFIRMED DEFECTS

**R2-1 — Transaction counts render as currency in the evidence modal.**
Root cause: `explainability_agent._calc_components()` pairs *any* `from_*`/`to_*` numeric
key from `inputs_json`, so `from_txn_count`/`to_txn_count` becomes a component row, and the
modal formats every component as money.
Fix: give each component a `unit` field (`currency` | `count` | `percent` | `bps` | `days`),
inferred from the key name (`*_count` → count, `*_pct` → percent, `*_bps` → bps,
`*_days` → days, else currency). The UI switches formatter on `unit`. Totals must only sum
`currency` components. Audit **all** components for the same class of error (`split_pct`,
`avg_rate_bps`, `billable_days`).

**R2-2 — Wrong PostgreSQL table names.**
`pcr.fpic_daily_trade_details_tb` → **`pcr.fpic_daily_trade_details_tb_prod`**
`pcr.fpicdb_pcr_product_hierarchy` → **`pcr.product_hierarchy`**
These appear in `docs/data/extraction/*.sql` **and hardcoded** at
`app/agents/nodes/explainability_agent.py` (`source_table`). Fix via R3, not by editing
both places.

---

## R3. SOURCE CATALOG — single source of truth for source-system metadata

Table names live in two disconnected places today, which is why they drifted.

Create **`docs/data/source_catalog.json`**:
```json
{
  "system": "PostgreSQL",
  "database": "fpicdb",
  "schema": "pcr",
  "note": "Production dump used for demo development.",
  "tables": {
    "trade_details": {
      "name": "pcr.fpic_daily_trade_details_tb_prod",
      "grain": "one row per trade split (trade_ref_no + split_seq_no)",
      "columns": { "post_split_credited_amt": {"maps_to": "phx_dm_v2_revenue_transaction.credited_amt",
                                               "note": "credited revenue base field"} }
    },
    "product_hierarchy": { "name": "pcr.product_hierarchy", "...": "..." },
    "advisor":           { "name": "pcr.fpic_prm_rr_tb", "...": "..." },
    "employee":          { "name": "pcr.fpic_employee_tb", "...": "..." }
  }
}
```
Include the **column → vertex attribute mapping** for every column we extract. Both the
extraction SQL files and the evidence builder read table names and mappings from here.
No table name may appear as a literal in Python again.

---

## R4. EVIDENCE — make it convincing, not merely correct

The modal currently proves *that* a number was computed. It does not explain *why a cause
was chosen*, which is the first question a sceptical reviewer asks. Add:

**R4-1 — "Why this cause"** panel in section 2. State the rule in plain words, the inputs
tested, and **why competing causes were rejected**. Source it from the attribution code so
it cannot drift. Example for NEW_ACCOUNT: *"Accounts trading in June that did not trade in
May. Evaluated at advisor level, not product level, so an account merely switching products
is not miscounted as a new account."*

**R4-2 — Attribution order** — show that this driver was step *n* of 12, and what earlier
steps had already claimed. This answers "how do you know you're not double-counting."

**R4-3 — Reconciliation waterfall** — a compact visual: from-revenue → each driver
contribution → to-revenue, summing exactly. One picture proving nothing is missing or
double-counted.

**R4-4 — `rev_nature` derivation** — show the actual `file_key` and `trade_description`
values that classified these rows as ONE_TIME/RECURRING/ADJUSTMENT.

**R4-5 — Credited-revenue breakdown** (new, enabled by R1) — for the driver's group and
months:
```
Total revenue                    $57,397.60
less non-credited                ($2,143.20)   9E small households ×12, 9G transferred ×3
less excluded                        $0.00
= Credited revenue               $55,254.40
```
This reproduces the client's own definition in their own vocabulary. It is the single most
persuasive addition in this round.

**R4-6 — Source SQL** must render from the source catalog with real parameters, and stay
clearly labelled *"lineage only — not executed by this application"*, in contrast to the
GSQL which **was** run.

---

## R5. LLM-AS-JUDGE — independent review layer

Deterministic guardrails catch invented numbers. They cannot catch a narrative that cites
correct figures but *characterises* them wrongly. Add a judge.

**R5-1 — New vertex `phx_dm_v2_commentary_evaluation`**
```
PRIMARY_ID evaluation_id STRING   # "<commentary_id>|<judge_run>"
commentary_id STRING
version_id STRING
judge_model STRING
faithfulness_score DOUBLE         # 0-1: does the narrative match the drivers?
hallucination_flag BOOL
completeness_score DOUBLE         # are the top drivers actually covered?
clarity_score DOUBLE
verdict STRING                    # PASS | REVIEW | FAIL
reasoning STRING                  # the judge's own explanation
evaluated_at DATETIME
data_source STRING
```
Edge: `phx_dm_v2_evaluation_of_commentary`.

**R5-2 — Judge runs after generation**, on a **different model** than the writer. It sees
the driver set and the narrative, and answers: is every claim supported? is any driver
mischaracterised? are the top drivers covered? is anything overstated?

**R5-3 — Advisory, not blocking.** Deterministic guardrails stay the blocking gate. The
judge flags `REVIEW`/`FAIL` for human attention. Never let the judge publish or suppress.

**R5-4 — Surface it in the evidence modal** as an "Independent review" line: verdict,
faithfulness score, and the judge's reasoning. And on the AI Insights card as a small badge
when the verdict is not PASS.

> **Lead with the stronger story:** the deterministic gate already caught the writer model
> doing arithmetic in v2–v4 and blocked it. Present the judge as a second layer, not the
> primary control.

---

## R6. PLAYWRIGHT SCREENSHOT EVIDENCE

`scripts/capture_evidence.mjs` — walks every screen at 1440×n against the running sample
data set and writes PNGs to `docs/qa_screenshots/`:
trends (both cards) · ai-insights (chart + cards + walk table) · evidence modal (open) ·
transactions (filtered) · data-ingestion · env-health · plus one empty state and one
BLOCKED-commentary state.

**`docs/qa_screenshots/` must be gitignored** — commit the harness, never the artefacts
(V1's screenshots ballooned that repo to 70 MB). Write an `index.md` listing what each shot
proves, so the folder is reviewable when generated.

---

## R7. UI POLISH — no theme or colour changes

Typography and density only:
- **Top nav**: 13px / weight 500, letter-spacing ~0.2px, more horizontal padding; active
  item gets a 2px bottom border in addition to the background shift.
- **Sub-nav**: 12.5px, clearer active underline.
- **All numeric cells**: `font-variant-numeric: tabular-nums` and right-aligned. This single
  change does more for a financial UI's credibility than anything else here.
- **Table rows**: +2px height; header letter-spacing 0.5px.
- Ensure consistent vertical rhythm between cards (16px) and consistent card padding (20px).

Do not alter the palette, the chart colours, or the layout structure.

### R7-2 — "AI Generated" marking (transparency requirement)

Every piece of **language produced by a model** must be visibly marked in the UI. This is a
governance requirement for the client, and it also strengthens our story rather than
weakening it — see the boundary rule below.

**Chip design** — small, neutral, non-alarming. `header-bg` background, `navy` text, 9.5px,
uppercase, with a small sparkle/AI glyph: **`✦ AI GENERATED`**. It sits inline with other
metadata chips (cause tags, provenance badges), never as a warning banner.

**MARK these (model-authored language):**
| Where | What |
|---|---|
| AI Insights commentary card | Card-level chip in the header — covers all bullets in that card |
| Bullet explanation text | Covered by the card chip; no per-bullet chip (too noisy) |
| Monthly walk table | Chip in the `COMMENTARY (REVENUE DRIVERS)` column header |
| Evidence modal §1 Finding | Chip beside the section heading |
| Evidence modal — judge reasoning (R5-4) | Chip on the "Independent review" line |

**Do NOT mark these (deterministic, computed):**
figures in any table or chart · driver contributions, ranks and percentages · revenue,
MoM change and reconciliation values · the calculation table (§2) · source records (§3) ·
lineage and integrity checks (§4) · the GSQL query, its parameters and its result (§5) ·
cause tags and provenance badges.

**The boundary is the point.** Add one line of helper text under the AI Insights section
header and in the evidence modal:

> *"Wording is AI-generated. All figures are computed from graph data and validated before
> publication — the model never produces or alters a number."*

That converts the chip from a disclaimer into a demonstration of control: the client sees
exactly where the model is used and, more importantly, where it is not. Pair it with the
existing reconciliation footer and the guardrail record.

**Hover/tooltip on the chip:** the generating model, prompt version and commentary version
(e.g. *"claude-sonnet · prompt v1.2 · commentary v6"*) — this data already exists on the
version vertex.

**Also mark in exports** (R6 CSV export and any PDF/print view): a footer line stating which
columns are AI-generated. Do not let the marking disappear when content leaves the screen.

---

## R8. V1 CLEANUP

Remove dead V1 references so nobody wires them up later:
- V1 query-name constants in `app/graph/tigergraph_mcp_contracts.py`, `app/graph/client.py`,
  `app/graph/mock_graph_store.py` (`get_advisor_360`, `get_org_hierarchy`,
  `get_graph_explorer`, `get_memory_timeline`, `get_revenue_summary`,
  `get_recommendation_context`, `get_advisor_context`).
- Unused MCP adapters/contracts if nothing in V2 imports them.
- `app/graph/access/` if unused.
- Any remaining V1 frontend patterns/types with no V2 consumer.

**Rule:** delete only what has no V2 consumer. Verify with a grep before each removal, and
confirm the app still boots and all screens render afterwards.

---

## R9. FINAL DOCUMENTATION — `docs/SOLUTION_GUIDE.md`

A single document someone can read to understand and defend the whole system. Chapters:

1. **Overview** — what it answers, who for, what it does not do.
2. **Business definitions** — Total / Credited / Non-Credited / Adjusted Credited, the
   reason-code table, grid types, the 90-day rule — in the client's own vocabulary, citing
   the Confluence source.
3. **Data lineage** — source table → column → vertex attribute, end to end, from the source
   catalog.
4. **Graph schema** — every vertex and edge: purpose, attributes, provenance, how populated.
5. **Query reference** — every GQ: purpose, parameters, output shape, consumers.
6. **Calculation reference** — *the most important chapter.* For **every driver cause**:
   the rule in plain words, the formula, the inputs, a **worked example with real numbers**,
   and why competing causes are rejected. Plus the attribution order and why order matters.
7. **Agent architecture** — the four agents, what each does, the "narrates never computes"
   rule, the guardrail checks, the judge.
8. **Evidence model** — what each of the five sections proves and where it comes from.
9. **Operations runbook** — install schema/queries, extract data, load, **generate
   commentary (the Regenerate button is the only trigger — a fresh environment has no
   commentary until it is run)**, verify, and the ordered-delete reload path.
10. **Known gaps, assumptions and roadmap** — must include, explicitly:
    - **DUMMY items are structure without maths.** `account_month_balance`, `MARKET` and
      `NET_FLOW` have vertices, edges and zero-valued rows, but **no attribution formulas
      are written**. Supplying data is necessary but not sufficient — the maths must be
      built. Give an honest estimate of that work.
    - **iComp megadata** — the client uses Trade Details for open periods and the iComp
      megadata table for closed periods. We use Trade Details only. If Apr–Jun 2026 are
      closed, the sanctioned source may differ. Open question for the client.
    - **Adjusted Credited Revenue = Credited ± PPA** — the client's own document
      contradicts itself (Pay Type section says minus, Product Type section says plus).
      Needs resolution.
    - **Prior-period adjustments** are not implemented; `posting_month_id` = trade month,
      flagged ASSUMED.
    - **91/92/9L treated as credited** (incentive-ineligible only) — assumption to confirm.
    - **Recurring vs non-recurring** = Managed + Trails, inferred from the client mockup —
      assumption to confirm.
    - Partial-June risk, the NULL-advisor bucket, no automated test suite, unmeasured
      performance at real data volume.

Write for a reader who is smart but new to the system. Prefer worked examples over prose.

---

## R10. PROGRESS TASKS — append these to `PROGRESS.md`

| ID | Task |
|----|------|
| R1-1 | reason_code vertex + seed data |
| R1-2 | txn_has_reason edge |
| R1-3 | transaction vertex new attributes |
| R1-4 | product vertex grid_type attribute |
| R1-5 | extraction SQL: reason_cd/rm_sid/cs_sid/grid_type, remove WHERE filter |
| R1-6 | credited-revenue definition (data-driven eligibility + 90-day rule) |
| R1-7 | posting_month_id (ASSUMED) |
| R1-8 | ELIGIBILITY driver cause |
| R1-9 | queries + services updated for credited-only |
| R1-10 | regenerate commentary; reconciliation re-verified |
| R1-11 | sample data regenerated with reason codes |
| R2-1 | component units — counts/percent/bps no longer rendered as currency |
| R2-2 | table names corrected via source catalog |
| R3-1 | source_catalog.json + both consumers read from it |
| R4-1..6 | evidence: why-this-cause, attribution order, waterfall, rev_nature, credited breakdown, source SQL from catalog |
| R5-1..4 | LLM-as-judge: vertex, judge run, advisory verdict, UI surfacing |
| R6-1 | Playwright evidence capture + gitignore + index |
| R7-1 | UI typography/density polish |
| R7-2 | "AI Generated" chips on all model-authored language + boundary helper text |
| R8-1 | V1 dead-reference cleanup |
| R9-1 | SOLUTION_GUIDE.md |

## R11. DEFINITION OF DONE (round 2)

- [ ] Credited revenue excludes 9E/9G/9C/9S/94, excludes 9R/98/99/9H/9X/XX entirely, and
      respects the 90-day rule — all driven by the reason vertex, not hardcoded
- [ ] Removing the `grid_type` filter from config changes behaviour without a code change
- [ ] Commentary regenerated; reconciliation $0.00 on every transition
- [ ] No count/percent/bps value renders as currency anywhere
- [ ] No PostgreSQL table name appears as a literal in Python
- [ ] Evidence modal shows why-this-cause, attribution order, waterfall, and the credited
      breakdown
- [ ] Judge runs, is advisory only, and is visible in the UI
- [ ] Every model-authored text region carries an "AI Generated" chip; no computed figure
      is marked as AI-generated; the boundary helper text is present on both screens
- [ ] Playwright captures every screen; artefacts gitignored
- [ ] App boots, all screens render, zero console errors
- [ ] `SOLUTION_GUIDE.md` complete, including every gap and assumption in R9.10
- [ ] `PROGRESS.md` all R-tasks DONE; `BUILD_REPORT.md` has a Round 2 section
