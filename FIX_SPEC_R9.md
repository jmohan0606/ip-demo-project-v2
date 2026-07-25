# FIX SPEC — iPerform V2, Round 9 · CLIENT-ENVIRONMENT DEMO FIXES

> **Read completely before starting.** Supersedes earlier specs where they conflict.
> CLAUDE.md §0 (autonomous), §0.1 (PROGRESS), §3 (absolute rules) and rule 8a still apply.
>
> Five defects found running the app in the client environment. All are contained — no
> taxonomy change, no eligibility change, no new drivers (those are round 10). Fix exactly
> these five, correctly, with no regressions.

---

## CONTEXT

The real-data build now runs and reconciles ($0.00 every transition). Rounds 6–8 fixed
attribution, added DEAL_SIZE, seeded driver metadata, and built the assistant + anomalies.
These five issues surfaced only in the client environment (real data, cdao_openai model):

1. LOST_ACCOUNT fires on one-time / adjustment revenue (Annuities case)
2. Account-comparison lists render empty despite a claimed amount
3. The assistant mislabels a single-transition figure as a multi-month span, and blocked
   turns are not visible
4. Commentary is blocked (not shown at all) when the model formats a figure wrongly
5. The judge fails with a 404 and shows "Faithfulness 0.00" as if it were a real score

---

## A — LOST_ACCOUNT / NEW_ACCOUNT MUST EXCLUDE ONE-TIME AND ADJUSTMENT REVENUE

**Problem.** `LOST_ACCOUNT` fired on **Annuities** where every source row is
`l_a_ancomm` / "ANNUITY ISSUED" → `rev_nature = ONE_TIME`. An annuity issued in one month
earns a one-time commission that was never going to repeat — that is one-time revenue ending,
**not** an account being lost. The account-presence test is counting one-time and adjustment
transactions as if they were recurring billing activity.

**Fix — the account-presence test must consider only recurring billing activity.** When
building the per-account monthly presence sets that drive `NEW_ACCOUNT` / `LOST_ACCOUNT`:
- **Filter at the TRANSACTION level, not the account level.** Build each month's presence set
  from only those transactions whose `rev_nature` is neither `ONE_TIME` nor `ADJUSTMENT`. An
  account is "present" in a month if and only if it has at least one *recurring* transaction
  that month.

  **CRITICAL NUANCE — mixed accounts.** A real account is not purely one type. An account may
  have recurring billing AND a one-time annuity commission in the same month. Do NOT exclude
  the whole account because it has a one-time row; exclude only the one-time/adjustment ROWS
  when deciding presence. Worked cases the fix must get right:
  - Account with recurring activity in both months → not new, not lost. ✓
  - Account with ONLY a one-time annuity in a month (the reported bug) → treated as absent
    that month for presence → not counted as lost/new. ✓
  - Account with recurring billing in month A and only a one-time row in month B → present in
    A, absent in B → correctly a candidate for LOST (subject to the persistence rule). ✓
  - Account with recurring billing every month plus an occasional one-time row → present every
    month → never lost/new despite the one-time rows. ✓

- This is ON TOP OF the existing recurring-class gate (the driver already only emits for
  recurring product groups). Both conditions apply: recurring *class* (product line) AND
  recurring *rev_nature* (transaction).
- The revenue of the excluded one-time/adjustment rows is already claimed by the `ONE_TIME` /
  `ADJUSTMENT`-bucket drivers — do not double-count it and do not route it to MIX.

**Verify — the fixture MUST include a mixed account, not just a pure one-time account:**
- an account whose only activity is `ONE_TIME` (annuity issued) → never LOST/NEW; revenue
  claimed by the one-time path;
- **a MIXED account with both recurring billing and a one-time row in the same month** →
  presence decided by the recurring row only (present that month), so the one-time row does
  NOT make it appear or disappear;
- an account recurring in month A, only one-time in month B → correctly a LOST candidate.
Reconciliation stays $0.00 in every case.

---

## B — ACCOUNT-COMPARISON LISTS RENDER EMPTY

**Problem.** A `LOST_ACCOUNT` driver claims e.g. ($55,138) but the evidence "Accounts active
in <from> only / <to> only" lists both show **None**. The claim exists; the supporting
account lists are empty. Reproduces on both `ACCOUNT_ABSENCE_MONTHS=1` and `=2`, so it is not
a threshold issue — it is a real read/write-shape bug.

**Fix — trace the write and the read, and make them agree:**
1. **Write side:** confirm `attribute_group()` actually stores the account keys and their
   revenue into the driver's `inputs_json` (`accounts_present_only_in_from_month`,
   `accounts_present_only_in_to_month`) for **group-level** drivers — not only on the advisor
   `__TOTAL__` row. The most likely bug is that the lists are computed at advisor level but
   the evidence is rendered per group, so the group driver carries empty lists.
2. **Read side:** confirm the evidence modal reads the same keys the writer wrote, with the
   same nesting. Log the exact key path on both sides during development.
3. The lists must carry, per account: account number, revenue in the active month, and product
   group — enough to render §C of FIX_SPEC_R8.

**Verify.** For a fixture LOST_ACCOUNT driver with N lost accounts, the evidence lists render
N accounts with revenue, summing to the driver's contribution. Empty lists with a non-zero
claim is a failure.

---

## C — ASSISTANT: CONTEXT LABELLING, MULTI-MONTH DECOMPOSITION, AND VISIBLE BLOCKS

Three related assistant defects.

**C1 — Advisor-scoped conversations.** A conversation is bound to a single advisor. Store the
advisor on the conversation vertex and scope every query in that conversation to that advisor.
Cross-advisor questions are **out of scope for a scoped conversation** — the assistant says so
plainly (this is also a client-facing security story: one advisor's conversation cannot read
another advisor's data). This replaces the round-7 cross-advisor default.
- The conversation's advisor is set from the screen context when the conversation starts.
- Add `advisor_sid` to `phx_dm_v2_conversation`; filter `get_conversations` by it.

**C2 — Fix context seeding and multi-month handling (the mislabelling bug).** Observed: the
screen seeded context `202604->202607` (a non-adjacent span). `get_revenue_changes` correctly
returned NO_DATA, but a later answer then reported D194202's **April→May** figure ($154,812)
labelled as **"April 2026 to July 2026."** Two fixes:
- **The screen must seed a valid ADJACENT transition** (e.g. the latest available
  from→to pair), never the full loaded span.
- **A figure for one transition must never be labelled as a different or wider span.** The
  answer's label must exactly match the transition the figure came from.
- **Multi-month questions must decompose, not return NO_DATA.** If the user asks about a span
  covering several transitions ("April to July"), answer by composing the adjacent
  transitions in range (sum the changes, or list each), clearly labelled — do not return a
  bare "no stored change row." NO_DATA is only correct when the data genuinely is not loaded.

**C3 — Blocked turns must be VISIBLE (this is a required, demoable feature).** The round-7
spec required this and it is not working in the client env. Every guardrail-blocked turn must
render in the transcript:
- the user's message shows normally,
- the reply is the neutral refusal with a **`⛉ GUARDRAIL`** chip showing **category and
  severity only** (never the matched pattern),
- the row persists with `guardrail_status=BLOCKED`.
A blocked turn must **never** be silently dropped. Add a fixture asserting a blocked input
produces a visible BLOCKED message in the returned transcript.

---

## D — COMMENTARY: FIX THE PROMPT, RETRY, NEVER SHOW AN EMPTY PANEL

**Problem.** Commentary for a transition was **blocked and nothing shown** — the client saw an
empty panel. The guardrail correctly caught a **positive** figure wrapped in parentheses
(parentheses mean negative). This began after switching to `cdao_openai`, which formats
differently. The guardrail is right; the response handling is wrong.

**Fix — three parts, all required:**
1. **Prompt fix (the root cause).** Update the commentary prompt so the model never wraps a
   positive figure in parentheses: parentheses denote negative values ONLY; positive values
   are never parenthesised. State the sign/format convention explicitly with an example of
   correct and incorrect formatting. This is what stops the block happening in the first place.
2. **Bounded retry.** If a generated commentary fails the guardrail, regenerate it — up to
   **3 attempts total** (config `COMMENTARY_MAX_ATTEMPTS`, default 3). Each retry is a fresh
   generation; log each attempt and its failure reason.
3. **Deterministic fallback — never an empty panel.** If all 3 attempts fail the guardrail,
   publish a **deterministic template** commentary built from the computed drivers (no model
   wording), clearly marked as a fallback, so the client always sees a defensible statement.
   A blocked transition must never leave the panel empty.

**Verify.** A fixture where the model returns a parenthesised positive figure: attempt 1
fails, retry succeeds (or the deterministic fallback publishes); the panel is never empty; the
guardrail is never bypassed (a bad figure is never displayed).

---

## E — JUDGE: STANDARD ADAPTER, CONFIGURABLE MODEL, HONEST UNAVAILABLE STATE

**Problem.** The judge failed: `Deployment 'gpt-4o-mini' not found in configuration mapping
for this subscription` (404), and the UI showed **"Faithfulness 0.00"** — which reads as a
terrible score rather than "the judge could not run."

**Fix:**
1. **Route the judge through the same LLM client/adapter the other agents use** (the guarded
   multi-mode client — cdao_openai primary in the client env, claude on the build box), not a
   separate hardcoded deployment. The judge model is selectable via `JUDGE_MODEL` (config),
   defaulting to the same mode the other agents use, so if a specific model is unavailable the
   operator can point it at the proven working model and still demo.
2. **Honest unavailable state.** When the judge cannot run, do NOT display a numeric score of
   0.00. Show **"Judge unavailable — human review recommended"** (as the finding text already
   does) and render the faithfulness metric as **"—" / "unavailable"**, never `0.00`. The
   judge is advisory only; its absence must never look like a failing score or block
   publication.

**Verify.** With an invalid `JUDGE_MODEL`, the evidence shows "unavailable" (not 0.00) and
publication still proceeds (deterministic guardrail remains the only publication gate). With a
valid model, a real faithfulness score renders.

---

## F — GLOSSARY ORDERING (small)

Driver glossary entries currently render in an arbitrary order. Order them by
**`display_order`** on `phx_dm_v2_driver_cause` (which reflects attribution order). Ensure the
seed sets a sensible `display_order` for every cause including DEAL_SIZE, and the glossary
query returns them sorted by it.

---

## G — WHAT NOT TO DO (this round)

- **Do not change the product taxonomy / recurring-vs-non-recurring structure.** The corrected
  hierarchy from the client is round 10.
- **Do not change eligibility rules.** The "all 9X ineligible" change is round 10.
- **Do not add the 9G inheritance or 9E household drivers.** Round 10.
- **Do not change chargeback scope.** Round 10.
- Do not change the credited-revenue definition, the 90-day rule, the schema (beyond adding
  `advisor_sid` to the conversation vertex for C1), or existing queries beyond what A–F
  require.
- Do not touch the ingestion or TigerGraph screens.

---

## H — VERIFICATION

You cannot reach TigerGraph or real data. Verify on fixtures and the local tier; write what
requires operator acceptance separately. Never describe a fixture check as a real-data check.

Extend the verification scripts with:
1. One-time/adjustment account exclusion (A) — an account with only ONE_TIME activity is not
   lost/new; reconciliation $0.00.
2. Account-comparison lists populate for a group-level driver (B).
3. Assistant: context seeds an adjacent transition; a single-transition figure is never
   labelled as a wider span; a multi-month question decomposes; a blocked turn is visible (C).
4. Commentary: parenthesised-positive input → retry → fallback; panel never empty; bad figure
   never displayed (D).
5. Judge: invalid model → "unavailable" not 0.00; publication proceeds (E).
6. Glossary sorted by display_order (F).
7. All existing suites still pass; reconciliation $0.00; zero console errors.

Write `docs/ROUND9_ACCEPTANCE.md` for operator-only checks (real-data run showing: no
LOST_ACCOUNT on annuity-issued rows; populated account lists; scoped conversation; visible
guardrail block; commentary never empty; judge on the working model).

## I — PROGRESS TASKS

| ID | Task |
|----|------|
| N-A | account presence excludes ONE_TIME/ADJUSTMENT rev_nature |
| N-B | account-comparison lists populate for group-level drivers (write+read agree) |
| N-C1 | advisor-scoped conversations (advisor_sid on conversation, queries filtered) |
| N-C2 | context seeds adjacent transition; no mislabelling; multi-month decomposes |
| N-C3 | blocked turns visible with GUARDRAIL chip; fixture proves it |
| N-D | commentary prompt sign-convention fix + 3x retry + deterministic fallback |
| N-E | judge on standard adapter, JUDGE_MODEL configurable, "unavailable" not 0.00 |
| N-F | glossary ordered by display_order |
| N-G | docs/ROUND9_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## J — DEFINITION OF DONE

- [ ] An account whose only activity is one-time/adjustment is never LOST/NEW; reconciliation $0.00
- [ ] Account-comparison lists render populated for group-level account drivers
- [ ] Conversations are advisor-scoped; cross-advisor questions decline plainly
- [ ] A single-transition figure is never labelled as a wider span; multi-month questions
      decompose instead of returning NO_DATA
- [ ] Guardrail-blocked turns are visible in the transcript with category+severity
- [ ] Commentary is never an empty panel: prompt fixed, 3x retry, deterministic fallback; the
      guardrail is never bypassed
- [ ] Judge runs through the standard adapter with a configurable model; unavailable shows
      "unavailable", never 0.00; publication still gated only by the deterministic guardrail
- [ ] Glossary renders in display_order
- [ ] All existing suites pass; reconciliation $0.00; zero console errors
- [ ] `PROGRESS.md` all N-tasks DONE; `BUILD_REPORT.md` Round 9 section separating verified-here
      from operator-pending; `ROUND9_CHANGED_FILES.md` produced
