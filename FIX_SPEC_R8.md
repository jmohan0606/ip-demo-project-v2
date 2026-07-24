# FIX SPEC — iPerform V2, Round 8 · DRIVER METADATA, BASELINE LABELLING, ACCOUNT EVIDENCE

> **Read completely before starting.** Supersedes earlier specs where they conflict.
> CLAUDE.md §0 (autonomous), §0.1 (PROGRESS), §3 (absolute rules) and rule 8a still apply.
>
> Four contained changes. No new features, no business-logic changes, no schema redesign.
> The attribution maths is settled — **do not touch `attribute_group()` arithmetic.**

---

## CONTEXT — what changed outside Claude Code

Two fixes were applied directly to `app/v2/drivers/attribution.py` between rounds and are
already in the repo. Read the file before assuming anything about it:

1. **The R6 A3 abort was removed.** It compared `|BASELINE_LIMITED|` against the transition's
   NET change and aborted the build. That constraint is invalid — drivers offset, so a single
   driver can legitimately exceed the net change. It is now a WARNING against gross movement.
2. **A new driver cause `DEAL_SIZE` was added.** The VOLUME step only emitted the count effect
   of a price/volume decomposition; the value effect fell into MIX. Both terms are now emitted
   for all groups, with `DEAL_SIZE` netted against `FEE_RATE` / `BILLABLE_DAYS` on recurring
   groups so the same dollars are not claimed twice. This took MIX on later transitions from
   14–24% down to 0.1–2.3%.

`ACCOUNT_ABSENCE_MONTHS` is set to **2** and stays there.

---

## A — DRIVER METADATA FROM DATA, NOT HARDCODED (the main change)

**Problem.** Driver names and descriptions live in at least two disconnected places: the
`phx_dm_v2_driver_cause` vertex, and hardcoded literals in
`frontend/components/patterns/revenue-driver-glossary.tsx` (verify the current path — it may
have moved). They will drift, and the operator cannot rename a driver without a code change.
This is the same drift class that produced wrong PostgreSQL table names in round 4.

**A1 — Extend `phx_dm_v2_driver_cause`:**
```
display_name STRING     # what the UI shows, e.g. "Charge Back"
description  STRING     # plain-English meaning, shown in the glossary
computation  STRING     # how it is calculated, shown in the glossary
```
Keep `cause_id` unchanged — it is the primary key, it is internal, and it is permanent.
`display_name` is the only thing the operator changes.

**A2 — `GQ-004 get_driver_causes` returns the new attributes.** Update the query file, the
catalog entry, and the local-tier implementation together.

**A3 — The glossary renders from the query.** Delete the hardcoded table in the glossary
component and render from `get_driver_causes`. Same for driver **tags** on the AI-Insights
cards and the evidence modal — every place a driver name appears must read `display_name`,
never a literal.

**A4 — Seed every cause with the three new fields**, using the existing glossary text as the
source (it is correct — it just needs to live in data). Include:

| cause_id | display_name | note |
|---|---|---|
| `DEAL_SIZE` | Average Transaction Value | **NEW — currently unseeded, shows a raw id in the UI** |
| `CLAWBACK` | Charge Back | operator-requested rename; `cause_id` stays `CLAWBACK` |
| `BASELINE_LIMITED` | Baseline Period | see §B |
| all others | as per the existing glossary | |

For `DEAL_SIZE`: *"The same number of transactions at a different average value."*
Computation: *"to_txn_count × (to_avg_value − from_avg_value), net of fee-rate and
billable-day effects on recurring groups so the same dollars are not counted twice."*

**A4b — Propagate the new attributes through the entire chain.** Adding attributes to a vertex
touches more than the DDL. In order:
1. `01_vertices.gsql`
2. **regenerate** `schema_catalog.json` and `load_v2_all.gsql` via
   `scripts/generate_schema_artifacts.py` (they are generated — do not hand-edit)
3. `manifest.json` column map for `phx_dm_v2_driver_cause`
4. the dataset builder that writes `driver_cause.csv` — **both** the sample generator and
   `build_real_data.py`
5. both tier implementations of `GQ-004`

Round 5's `ColumnMismatchError` fails loudly when manifest columns and CSV headers disagree, so
a missed step aborts ingestion rather than silently dropping attributes. **Fix the chain; do not
work around the error.**

**A5 — Verify no driver name is hardcoded anywhere.** Grep the frontend for driver literals
("Clawback", "One-Time", "Billable Days", …) after the change; any hit outside a seed file or
test is a defect.

---

## B — LABEL THE BASELINE TRANSITION (demo-blocking)

**Problem.** April→May is the first transition in the loaded data and shows MIX of 84%–1170%.
Attribution across that boundary has no prior period to work from. Today the UI presents it
identically to clean transitions, so it looks like the system is simply wrong.

**The operator's decision: show it, clearly labelled. Do NOT hide it.**

**B1 — Identify the baseline transition** as the one whose `from_month` is the earliest month
present in the loaded data. Determine it from data, never hardcode a month.

**B2 — Label it wherever it appears** — AI-Insights cards, the monthly walk table, the chart
arrow, and the evidence modal:

> **Baseline period** — April 2026 is the first month in the loaded data, so there is no prior
> period to compare account activity against. Driver attribution for this transition is
> indicative; later transitions are fully attributed.

Use a neutral informational treatment (the `INFO`/amber family), not an error style.

**B3 — Exclude it from quality signals:**
- The MIX self-check (`>15%` warning) must skip the baseline transition — a large residual
  there is expected, not a defect.
- The `UNEXPLAINED_RESIDUAL` anomaly rule must not fire on it.
- The build summary must print it as `baseline` rather than as a MIX failure.

**B4 — Commentary must state the limitation** rather than narrating baseline noise as business
events. If the commentary agent cannot produce a defensible narrative for the baseline
transition, it should say so plainly instead of inventing causes.

---

## C — ACCOUNT COMPARISON IN EVIDENCE

**Problem.** `NEW_ACCOUNT` / `LOST_ACCOUNT` claim amounts, but the client cannot see *which*
accounts. They asked to see the comparison so they can validate the claim.

The data already exists — `inputs_json` on those drivers holds
`accounts_present_only_in_to_month` and `accounts_present_only_in_from_month`. **No new
computation is required; this is rendering only.**

**C1 — New evidence section, shown only for account drivers:** two side-by-side lists —
*Accounts active in <from_month> only* and *Accounts active in <to_month> only* — each with
account number, its revenue in the month where it was active, and the product group.

**C2 — Ranked, with a total.** Sort by absolute revenue descending, show the top 20 with a
"showing 20 of N" footer and a link into Transactions filtered to those accounts. This also
satisfies the client's "top 20 accounts causing the difference" request.

**C3 — State the rule that produced the classification** above the lists, from the driver's
`inputs_json`: *"Accounts with no activity for 2 consecutive months (ACCOUNT_ABSENCE_MONTHS=2),
evaluated at advisor level across recurring product lines."* The operator must be able to point
at the rule and the evidence together.

---

## D — WHAT NOT TO DO

- Do not change `attribute_group()` arithmetic, the credited-revenue definition, the reason
  model, eligibility, the 90-day rule, or `ACCOUNT_ABSENCE_MONTHS`.
- Do not change any `cause_id` value — only `display_name`.
- Do not implement the client's revised driver specification (their eight drivers, "ineligible
  = anything starting with 9", the broader recurring set, chargebacks limited to
  Annuities/Life). **That list conflicts with the CWM PCR Confluence mapping we built to and is
  unresolved.** Record it in the SOLUTION_GUIDE open items; do not code it.
- Do not touch the ingestion or TigerGraph screens — being handled separately.
- Do not build MDW roll-up, book movement, or streaming ingestion.

---

## E — VERIFICATION

You cannot reach TigerGraph or real data. Verify what you can and be explicit about the rest:

1. Glossary renders from `get_driver_causes` on both tiers; changing a seed `display_name`
   changes the UI with no code edit (prove it by changing one in a fixture).
2. No driver-name literal remains in the frontend (grep, per A5).
3. `DEAL_SIZE` appears with its display name, description and computation.
4. The baseline transition is identified from data, labelled in all four places, excluded from
   the MIX check and the `UNEXPLAINED_RESIDUAL` rule, and still **visible**.
5. Account-comparison lists render for account drivers only, ranked, with the rule stated, and
   are absent for non-account drivers.
6. Existing suites still pass: `verify_attribution.py`, `verify_assistant.py`,
   `verify_end_to_end.py`, `validate_v2_queries.py`. Reconciliation stays $0.00.
7. Zero console errors on AI Insights, evidence modal and the glossary.

Write `docs/ROUND8_ACCEPTANCE.md` for what only the operator can confirm (live install of the
updated `GQ-004`, reseeding the cause vertex, and a real-data check that the baseline label
appears on April→May).

## F — PROGRESS TASKS

| ID | Task |
|----|------|
| V-A1 | driver_cause vertex: display_name, description, computation |
| V-A2 | GQ-004 returns them (query file + catalog + local-tier impl) |
| V-A3 | glossary, driver tags and evidence render from the query |
| V-A4 | seed all causes incl. DEAL_SIZE; CLAWBACK display_name = "Charge Back" |
| V-A4b | propagate attributes: DDL, regenerated catalog + loading job, manifest, both builders, both tiers |
| V-A5 | no driver-name literals left in the frontend (grep-verified) |
| V-B1 | baseline transition identified from data |
| V-B2 | labelled in cards, walk table, chart arrow, evidence modal |
| V-B3 | excluded from MIX check, UNEXPLAINED_RESIDUAL, and build-summary failure count |
| V-B4 | commentary states the limitation instead of narrating noise |
| V-C1 | account-comparison section in evidence (account drivers only) |
| V-C2 | ranked top-20 with total and Transactions link |
| V-C3 | classification rule stated from inputs_json |
| V-D1 | `docs/ROUND8_CHANGED_FILES.md` (git-derived, conflict flags, operator-local excluded) |

## G — DEFINITION OF DONE

- [ ] Every driver name in the UI comes from `display_name`; changing a seed value renames it
      everywhere with no code change
- [ ] `DEAL_SIZE` is seeded and displays properly; `CLAWBACK` displays as "Charge Back"
- [ ] The baseline transition is visible, clearly labelled in all four places, and excluded
      from the MIX check and anomaly rule
- [ ] Account drivers show the account comparison, ranked, with the rule stated
- [ ] No driver-name literals remain in the frontend
- [ ] The new attributes propagate end to end: DDL, regenerated schema catalog and loading job,
      manifest columns, both dataset builders, both tiers — sample data loads without a
      ColumnMismatchError
- [ ] All existing verification suites pass; reconciliation $0.00; zero console errors
- [ ] `PROGRESS.md` all V-tasks DONE; `BUILD_REPORT.md` Round 8 section separating verified-here
      from operator-pending; `ROUND8_CHANGED_FILES.md` produced
