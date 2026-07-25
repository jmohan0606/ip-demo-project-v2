# ROUND 9 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Five contained defects found running the app in the
client environment. No taxonomy change, no eligibility change, no new drivers (those are round
10). Fix exactly these five, correctly, no regressions. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R9.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the N-prefixed tasks from FIX_SPEC_R9 §I; do not renumber
   existing tasks. If any N-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE N-task.
4. Read `app/v2/drivers/attribution.py` before changing it — do not alter the settled
   arithmetic (VOLUME/DEAL_SIZE decomposition, netting, reconciliation).

THE FIVE FIXES:

A. LOST_ACCOUNT/NEW_ACCOUNT must exclude ONE_TIME and ADJUSTMENT revenue. It fired on
   Annuities where every row is l_a_ancomm / "ANNUITY ISSUED" -> rev_nature=ONE_TIME. An
   annuity issued earns a one-time commission that never repeats — that is one-time revenue
   ending, NOT a lost account. Filter at the TRANSACTION level, not the account level: build each month's presence set from
   only transactions whose rev_nature is neither ONE_TIME nor ADJUSTMENT; an account is present
   in a month iff it has >=1 recurring transaction that month. CRITICAL NUANCE — mixed accounts:
   a real account may have recurring billing AND a one-time annuity in the same month. Do NOT
   drop the whole account because it has a one-time row; exclude only the one-time/adjustment
   ROWS when deciding presence. So: recurring-in-both-months = not lost/new; only-one-time-in-a-
   month = absent that month; recurring in A then only-one-time in B = LOST candidate; recurring
   every month plus occasional one-time = never lost/new. This is on top of the recurring-CLASS
   gate (both apply). Do not route excluded revenue to MIX (already claimed by the one-time
   path). The fixture MUST include a mixed account, not just a pure one-time account.
   Reconciliation stays $0.00.

B. Account-comparison lists render empty despite a claimed amount (e.g. LOST_ACCOUNT claims
   $55,138 but both lists show "None"). Reproduces on ACCOUNT_ABSENCE_MONTHS=1 AND =2, so it
   is a read/write-shape bug, not a threshold issue. Most likely the account keys are computed
   at advisor level but the evidence renders per group, so the group-level driver carries empty
   lists. Trace the write (attribute_group storing accounts_present_only_in_from/to_month into
   inputs_json for GROUP-level drivers) and the read (evidence modal), log the exact key path
   on both sides, make them agree. Each listed account needs: account number, revenue in the
   active month, product group.

C. Assistant — three related fixes:
   C1: Advisor-scoped conversations. Bind a conversation to one advisor (add advisor_sid to
       phx_dm_v2_conversation, set from screen context, filter all queries by it). Cross-advisor
       questions decline plainly. This is also a client security story (one advisor's
       conversation cannot read another's data). Replaces the round-7 cross-advisor default.
   C2: Fix context seeding + multi-month. Observed: screen seeded 202604->202607 (non-adjacent),
       get_revenue_changes returned NO_DATA, then an answer reported the April->May figure
       ($154,812) labelled "April 2026 to July 2026". The screen must seed a valid ADJACENT
       transition, never the full span. A figure for one transition must NEVER be labelled as a
       different/wider span. Multi-month questions must DECOMPOSE (compose the adjacent
       transitions in range, clearly labelled) — not return a bare NO_DATA. NO_DATA is only for
       genuinely-unloaded data.
   C3: Blocked turns must be VISIBLE (required, demoable — the round-7 spec required this and it
       is not working in the client env). A blocked turn renders: user message shown, reply is
       the neutral refusal with a "⛉ GUARDRAIL" chip showing CATEGORY AND SEVERITY ONLY (never
       the matched pattern), persisted with guardrail_status=BLOCKED. Never silently dropped.

D. Commentary must never show an empty panel. It was blocked (nothing shown) because the model
   wrapped a POSITIVE figure in parentheses (parens = negative) after switching to cdao_openai.
   The guardrail is correct; the handling is wrong. Three parts, all required: (1) fix the
   PROMPT so the model never parenthesises a positive figure — parens denote negatives only,
   state it with correct/incorrect examples; (2) bounded retry up to 3 attempts
   (COMMENTARY_MAX_ATTEMPTS, default 3), each a fresh generation, log each failure; (3) if all 3
   fail, publish a DETERMINISTIC TEMPLATE commentary from the computed drivers, marked as
   fallback, so the panel is never empty. The guardrail is never bypassed — a bad figure is
   never displayed.

E. Judge: it failed with "Deployment 'gpt-4o-mini' not found" (404) and showed "Faithfulness
   0.00" as if it were a real score. Route the judge through the SAME LLM client/adapter the
   other agents use (cdao_openai primary in client env, claude on build box), model selectable
   via JUDGE_MODEL (config) defaulting to the agents' mode, so an unavailable model can fall
   back to the proven one. When the judge cannot run, show "Judge unavailable — human review
   recommended" and render faithfulness as "—"/"unavailable", NEVER 0.00. Judge is advisory
   only; its absence never blocks publication (deterministic guardrail remains the only gate).

F. Glossary ordering: render driver glossary entries sorted by display_order on
   phx_dm_v2_driver_cause (attribution order). Ensure every cause incl. DEAL_SIZE has a sensible
   display_order and the query returns them sorted.

NOT IN SCOPE (all round 10): product taxonomy / recurring-vs-non-recurring restructure,
eligibility rule change (all 9X ineligible), 9G inheritance driver, 9E household driver,
chargeback scope change. Do not touch these. Do not change credited-revenue definition, the
90-day rule, the schema beyond adding advisor_sid to the conversation vertex, or existing
queries beyond what A-F require. Do not touch ingestion/TigerGraph screens.

VERIFICATION: you cannot reach TigerGraph or real data. Verify on fixtures + local tier; add
the checks in §H; all existing suites must still pass and reconciliation stay $0.00. Write
docs/ROUND9_ACCEPTANCE.md for operator-only checks. Never describe a fixture check as a
real-data verification. Produce docs/ROUND9_CHANGED_FILES.md (git-derived, conflict-risk files
flagged, operator-local files excluded).

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Begin with N-A.

---
