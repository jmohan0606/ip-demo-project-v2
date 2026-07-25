# ROUND 10 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. This is a FOUNDATION round: it corrects the
recurring/non-recurring product taxonomy that every driver computes on, changes the
eligibility rule that determines the credited-revenue total, adds two new drivers, and
rescopes chargebacks. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R10.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the T-prefixed tasks from FIX_SPEC_R10 §I; do not renumber
   existing tasks. If any T-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE T-task.
4. Read `app/v2/drivers/attribution.py` before changing it — do not alter the settled
   VOLUME/DEAL_SIZE decomposition or its netting.

STRICT ORDERING (each depends on the previous): A taxonomy → B eligibility → C new drivers →
D chargeback → E LLM health → F glossary/verify. Do not start B until A reconciles; do not
start C until B reconciles.

THE CREDITED-REVENUE TOTAL WILL CHANGE THIS ROUND (eligibility change). That is intended, not a
regression. Reconciliation ($0.00 per transition) must still hold at every step.

A. TAXONOMY (do first — everything sits on it). The current recurring/non-recurring taxonomy is
   WRONG (built from a bad Figma screen). Re-seed to the EXACT hierarchy in §A1 — transcribe
   verbatim, do not paraphrase or reorder. CRITICAL NUANCE: Annuities, Mutual funds, and Cash
   management each appear under BOTH recurring and non-recurring. Classifying by product-group
   NAME is therefore WRONG and is the current bug. Decide recurring-vs-non-recurring by the
   product's POSITION IN THE HIERARCHY (product line / parent path), never by a name match. If
   the source data cannot distinguish the dual-name cases by product code / hierarchy path,
   STOP and report in PROGRESS.md — do not guess by name. Propagate the re-seed through the full
   chain (DDL→regenerate schema_catalog+load_v2_all→manifest→both builders→both tiers).

B. ELIGIBILITY (after A reconciles). New rule replacing the current seed: eligible/credited =
   reason code NULL, empty, or __NONE__; ineligible/not-credited = ANY code starting with 9
   (including 91, 92, 9L which were previously credited — they now flip to non-credited).
   Forget the prior Confluence split. THREE-STATE MODEL IS PRESERVED, do not collapse it:
   Credited = NULL/empty/__NONE__ only; Non-Credited = every 9… code EXCEPT the excluded set;
   Excluded = the existing reversal/error codes (9R/98/99/9H/9X/XX) stay excluded and OUTSIDE
   Total Revenue, untouched. The ONLY change is 91/92/9L move Credited→Non-Credited. Example:
   none $100k=Credited, 9E $8k + 91 $5k=Non-Credited, 9X $3k=Excluded → Credited $100k,
   Total Revenue $113k, Excluded $3k shown as its own line outside Total. Also annotate the
   evidence "less excluded" line with its reason-code breakdown (rendering, not new compute).
   A NULL reason code is eligible — map missing codes to the eligible bucket. Reconciliation
   $0.00.

C. TWO NEW DRIVERS (after B reconciles). Both are reclassification drivers needing this month's
   AND last month's reason code per account. C0 FIRST: confirm per-account per-month reason-code
   presence is available; if not, implement what's possible and report the gap — do not
   fabricate.
   - C1 INHERITANCE (9G): detect accounts with 9G present in one month and absent in the
     adjacent month; attribute the revenue delta to a new INHERITANCE driver. No inheritance
     effective date exists in the extract (confirmed) — add a code comment that the business
     rule is a ~6-month cooling period and this approximates it by 9G presence/absence, to be
     refined when a date is available. Provenance DERIVED.
   - C2 HOUSEHOLD (9E): detect accounts with 9E present in one month and absent in the adjacent
     month; attribute the delta to a new HOUSEHOLD driver. Must NOT double-count with the
     aggregate ELIGIBILITY driver — HOUSEHOLD claims the 9E-transition portion, ELIGIBILITY the
     remainder. Provenance DERIVED.
   - PARTITION MECHANISM (exact): 9G and 9E are themselves non-credited codes, so their
     movement is already part of what aggregate ELIGIBILITY would claim. INHERITANCE and
     HOUSEHOLD do not add new dollars — they carve specific codes out of the eligibility effect.
     Compute INHERITANCE (9G) and HOUSEHOLD (9E) FIRST, then compute ELIGIBILITY as the
     non-credited movement of all OTHER 9… codes EXCLUDING 9G and 9E. The three then sum to the
     total eligibility effect with nothing double-counted. Place INHERITANCE/HOUSEHOLD before
     the ELIGIBILITY remainder. Reconciliation $0.00; MIX must not absorb this movement.

D. CHARGEBACK SCOPE. CLAWBACK/"Charge Back" applies ONLY to Annuities, Insurance (product), and
   Life (product code). Verify the exact identifiers against the REAL product hierarchy
   (raw_product_hierarchy.csv / phx_dm_v2_product/_product_group) before coding — record the
   confirmed identifiers in a comment. Reversals on other products still reconcile but are not
   labelled CLAWBACK.

E. ENV HEALTH LLM SECTION. Add an "LLM connectivity" section showing one row per role
   (commentary writer, judge, assistant): provider/mode, resolved model, and reachable/
   model-found/UNAVAILABLE via the CHEAPEST possible check (ping or models-list lookup, NOT a
   real generation). The judge row must specifically flag "model not found in subscription" (the
   gpt-4o-mini 404) so a bad JUDGE_MODEL shows red before commentary runs. Never print secrets —
   provider and model name only. Read-only; mutates nothing.

F. Seed display_name/description/computation/display_order for INHERITANCE and HOUSEHOLD;
   glossary renders in display_order with the new causes in the right position; no frontend
   driver-name literals.

NOT IN SCOPE / DO NOT: regress round 9's five fixes; change the VOLUME/DEAL_SIZE arithmetic or
its netting; change the 90-day rule or credited grid-type filter; classify recurring by NAME;
fabricate reason-code history or inheritance dates; touch ingestion/TigerGraph screens.

VERIFICATION: you cannot reach TigerGraph or real data. Verify on fixtures + local tier per §H —
including a fixture with BOTH a recurring Annuities product and a non-recurring Annuities product
(assert each classifies correctly), a 91 flipping to non-credited, a 9G flip producing
INHERITANCE, a 9E flip producing HOUSEHOLD not double-counted, CLAWBACK only on
Annuities/Insurance/Life, and the LLM health rows. All existing suites must pass; reconciliation
$0.00; round-9 behaviour intact. Write docs/ROUND10_ACCEPTANCE.md for operator-only checks and
docs/ROUND10_CHANGED_FILES.md (git-derived, conflict-risk flagged, operator-local excluded).
Report any data gaps in PROGRESS.md rather than guessing.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Begin with T-A1. Report any data gaps rather than guessing.

---
