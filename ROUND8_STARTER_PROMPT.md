# ROUND 8 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Four contained changes this round — no new features,
no business-logic changes. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R8.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the V-prefixed tasks from FIX_SPEC_R8 §F; do not renumber
   existing tasks. If any V-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE V-task.
4. **Read `app/v2/drivers/attribution.py` before assuming anything about it** — two fixes were
   applied to it directly, outside Claude Code, between rounds (see below).

CHANGES MADE OUTSIDE CLAUDE CODE, ALREADY IN THE REPO:
- The R6 A3 abort was removed. It compared |BASELINE_LIMITED| against the transition's NET
  change and aborted the build; that constraint is invalid because drivers offset each other,
  so a single driver can legitimately exceed the net change. It is now a WARNING against gross
  movement.
- A new driver cause DEAL_SIZE was added. The VOLUME step emitted only the count effect of a
  price/volume decomposition and the value effect fell into MIX. Both terms are now emitted for
  all groups, with DEAL_SIZE netted against FEE_RATE/BILLABLE_DAYS on recurring groups so the
  same dollars are not claimed twice. MIX on later transitions went from 14-24% to 0.1-2.3%.
DO NOT change the attribution arithmetic. It is settled.

THE FOUR CHANGES:

A. DRIVER METADATA FROM DATA (the main one). Driver names/descriptions are currently hardcoded
   in the frontend glossary component AND held on the driver_cause vertex — they will drift,
   and the operator cannot rename a driver without a code change. Add display_name,
   description and computation to phx_dm_v2_driver_cause; have GQ-004 return them; render the
   glossary, driver tags and evidence from the query; seed every cause. cause_id NEVER changes
   — it is the primary key and is internal. Only display_name changes. Two required seed
   values: DEAL_SIZE (currently unseeded — it shows a raw id in the UI today) and CLAWBACK,
   whose display_name becomes "Charge Back" (its cause_id stays CLAWBACK). Then grep the frontend: any remaining driver-name literal is a
   defect.

B. LABEL THE BASELINE TRANSITION. April->May is the first transition in the loaded data and
   shows MIX of 84%-1170% because there is no prior period for account comparison. The
   operator's decision is SHOW IT, CLEARLY LABELLED — do not hide it. Identify it from data
   (earliest loaded month), label it in the cards, walk table, chart arrow and evidence modal,
   and exclude it from the MIX self-check and the UNEXPLAINED_RESIDUAL anomaly rule (a large
   residual there is expected, not a defect). Commentary must state the limitation rather than
   narrating baseline noise as business events.

C. ACCOUNT COMPARISON IN EVIDENCE. NEW_ACCOUNT/LOST_ACCOUNT claim amounts but the client cannot
   see which accounts. The data already exists in the driver's inputs_json
   (accounts_present_only_in_to_month / _from_month) — this is RENDERING ONLY, no new
   computation. Show two side-by-side ranked lists with revenue per account, top 20 with a
   total and a link into Transactions, and state the classification rule above them.

D. Produce docs/ROUND8_CHANGED_FILES.md (git-derived, conflict-risk files flagged,
   operator-local files excluded).

NOT IN SCOPE: the client's revised driver specification (their eight drivers, "ineligible =
anything starting with 9", broader recurring set, chargebacks limited to Annuities/Life) — it
conflicts with the CWM PCR Confluence mapping we built to and is UNRESOLVED. Record it in
SOLUTION_GUIDE open items; do not code it. Also out: ingestion/TigerGraph screens (handled
separately), MDW roll-up, book movement, streaming ingestion, documentation round.

VERIFICATION: you cannot reach TigerGraph or real data. Prove what you can — changing a seed
display_name renames the driver in the UI with no code edit; no driver-name literals remain;
the baseline transition is labelled and excluded from quality checks but still visible; account
lists render for account drivers only. All existing suites must still pass and reconciliation
must stay $0.00. Write docs/ROUND8_ACCEPTANCE.md for what only the operator can confirm. Never
describe a fixture check as a real-data verification.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Begin with V-A1.

---
