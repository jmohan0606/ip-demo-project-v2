# ROUND 6 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Round 5's ingestion fixes worked — the real-data
build now runs and reconciles. This round fixes an attribution correctness bug that the first
real-data run exposed. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R6.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the X-prefixed tasks from FIX_SPEC_R6 §D; do not renumber
   existing tasks. If any X-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE X-task.

THE PROBLEM (from the first real-data build — real numbers):
Reconciliation is $0.00 everywhere, but MIX is 92.6%, 172%, 343%, 1061%, 2197%, 193% on
first transitions, and BASELINE_LIMITED over-claims (-$267,500 against a -$154,812 total
change) with MIX swinging +$143,310 to compensate. On non-baseline transitions LOST_ACCOUNT
(-$291,801) and NEW_ACCOUNT (+$150,001) are large and symmetric every month.

ROOT CAUSE: `app/v2/drivers/attribution.py` computes account presence as a two-month test
(`advisor_new = to_all - from_all`, `advisor_lost = from_all - to_all`) over 19,694 accounts
and 73,324 transactions. On real data most accounts do NOT trade every month — an equities
account that trades in May and not June has not been lost, that is ordinary trading
intermittency. So NEW/LOST_ACCOUNT (and BASELINE_LIMITED, which inherits the same sets)
massively over-claim and MIX absorbs the error. The sample data hid this because its accounts
traded consistently every month.

This is NOT a baseline-month bug. BASELINE_LIMITED correctly stopped MIX absorbing the first
transition, but it inherited the same faulty sets, so it over-claims instead. Fix both.

THE FIX (detail in the spec):
- Gate NEW_ACCOUNT/LOST_ACCOUNT to RECURRING-class groups only (Managed, Trails), where an
  account genuinely should bill every month. For transactional groups, VOLUME/ONE_TIME/TIMING
  already explain the change — do not route the amount to MIX instead.
- Require persistence: an account is lost only after ACCOUNT_ABSENCE_MONTHS (config, default
  2) consecutive months of no activity; symmetric for new.
- Bound BASELINE_LIMITED to what genuinely cannot be determined, and assert
  |BASELINE_LIMITED| <= |total change| — fail the build loudly if violated.

ACCEPTANCE: MIX < 15% on EVERY transition, reconciliation still $0.00, account drivers only
on recurring groups. Build a real-shaped fixture that REPRODUCES the bug (accounts trading
intermittently in transactional products, consistently in Managed) and prove MIX drops from
>90% to <15% on it. Add automated checks.

ALSO IN SCOPE (small carry-overs):
- `90_drop_all.gsql` is broken and was never executable-tested. It drops the graph before the
  queries (TigerGraph refuses), and it assumes reverse edges drop with their parent — they do
  not; `reverse_phx_dm_v2_*` are separate objects needing explicit DROP EDGE. Correct order:
  queries → graph → reverse edges → forward edges → vertices. Generate it from the schema
  files so it cannot drift.
- Record in BUILD_REPORT that generated GSQL is parse-reasoned, not executed, and must be
  flagged NEEDS-LIVE-VERIFICATION until the operator runs it.

SECOND WORK-STREAM (Y) — ANOMALY DETECTION, only after A is green:
Do NOT start Y until MIX is under 15% on every transition. Anomaly rules consume driver
attribution; built on today's numbers they would flag advisors for losing accounts that never
left. Then build: six deterministic rules (unexplained residual, clawback concentration,
large swing, fee-rate shift, single-driver dominance, baseline-limited present) with all
thresholds in config; a phx_dm_v2_anomaly vertex plus scan vertex with additive versioned
scans; GQ queries; a batch scan endpoint + CLI (never detect on page load); AI wording only
via commentary_agent under the same no-invented-figures guardrail; and the /anomalies screen
per docs/ui/reference/roadmap/02_anomaly_detection.png. Do NOT implement the BOOK_MOVEMENT
rule — it depends on account movement being real, which work-stream A may disprove.

NOT IN SCOPE: the conversational assistant (round 7 — it needs a full session). Do not change
the credited-revenue definition, reason model, eligibility, 90-day rule, schema, or any GSQL
query other than 90_drop_all.gsql and the new anomaly queries.

DO NOT widen the MIX threshold to make the check pass, and do not route unexplained amounts
into BASELINE_LIMITED to keep MIX low — that is the bug this round exists to remove.

VERIFICATION HONESTY: you cannot reach TigerGraph and have no real client data. Verify on
fixtures and sample; write what requires operator acceptance separately in BUILD_REPORT.
Never describe a fixture check as a real-data verification.

Also produce `docs/ROUND6_CHANGED_FILES.md` (git-derived, per work-stream, operator-local
files excluded, conflict-risk files flagged) — the operator copies only changed files to a
separate client environment.

Begin with A1.

---
