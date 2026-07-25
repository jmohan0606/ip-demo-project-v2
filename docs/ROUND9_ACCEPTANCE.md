# ROUND 9 — OPERATOR ACCEPTANCE (client environment only)

Everything below **cannot be verified on the build box** (no TigerGraph, no real
data, no cdao_openai). The fixture-level proofs are already green here
(`verify_attribution` incl. R9A/R9B, `verify_assistant` 101/101 incl. [10]–[12],
`verify_commentary_retry` 10/10, `verify_judge` 9/9, `verify_end_to_end` incl.
glossary ordering, 15/15 screens zero console errors). These steps confirm the
same behaviour on the client machine with real data and the real model. A
fixture check is never a real-data check — do not skip these.

## 0. One-time setup on the client machine

1. `git pull` round 9 (see `docs/ROUND9_CHANGED_FILES.md` for conflict-risk
   files before pulling).
2. **Schema change (the only one this round):** `phx_dm_v2_conversation` gained
   `advisor_sid`. On live TigerGraph either ALTER the vertex or drop/recreate the
   conversation vertex (chat history is runtime data; dropping it is acceptable
   if agreed) and rerun the loading path. `schema_catalog.json`, the loading job
   and `90_drop_all.gsql` are regenerated.
3. **Reinstall GQ-020** (`get_conversations` now filters on `c.advisor_sid`).
   Marked `updated-r9-NEEDS-LIVE-REINSTALL` in the catalog.
4. **Reseed `phx_dm_v2_driver_cause`** from the current build (17 causes,
   display_order 1–17 incl. DEAL_SIZE=2, 9-column header). A stale 6-column
   seed is what makes the glossary render in the old order with blank
   meaning/computation columns (F).
5. `.env`: add `COMMENTARY_MAX_ATTEMPTS=3` (or leave default) and review
   `JUDGE_MODEL` (see §E below). Leave `LLM_CLIENT_MODE=cdao_openai`.
6. **Rebuild the real data set** (`scripts/build_real_data.py`) — fix A changes
   driver attribution, so stored drivers/evidence must be regenerated. The build
   now STOPS if any account driver's evidence lists are empty/inconsistent
   (R9 B write contract) or reconciliation is not $0.00.
7. Regenerate commentary (a new version; prior versions remain queryable).

## A — LOST/NEW_ACCOUNT vs one-time revenue

- [ ] On the advisor/transition where LOST_ACCOUNT fired on Annuities
      (`l_a_ancomm` / "ANNUITY ISSUED"), the rebuilt drivers show **no
      LOST_ACCOUNT** claim for that movement; the change is carried by the
      One-time driver instead.
- [ ] A known **mixed** account (recurring billing + one-time annuity in the
      same month) appears in **no** account driver's lists.
- [ ] Reconciliation $0.00 on every transition (build summary).

## B — Account-comparison lists

- [ ] Open the evidence modal on a group-level LOST_ACCOUNT (or NEW_ACCOUNT)
      driver with a non-zero claim: both lists render — N accounts, each with
      account number, revenue in the active month, product group; the side's
      total equals the driver's claim. "None" beside a non-zero claim is a
      **failure** (check the browser console: the modal now logs the exact
      inputs_json key path when the lists come back empty or unparseable).
- [ ] If loading via the GSQL job (not the app): confirm the regenerated
      `load_v2_all.gsql` (now `QUOTE="double"`) is the one installed — without
      it, JSON columns shear at the first comma. NEEDS-LIVE-VERIFICATION.

## C — Assistant

- [ ] C1: start a conversation from advisor X's screen; ask about advisor Y →
      plain decline ("scoped to advisor …"); the history rail under advisor Y
      does **not** list X's conversation; `get_conversations` live returns only
      the bound advisor's rows after the GQ-020 reinstall.
- [ ] C2: with 4+ months loaded, open the assistant — the context chip shows an
      **adjacent** transition (e.g. Jun→Jul), never the full span. Ask "how did
      revenue change from April to July?" → the answer lists each adjacent
      transition, each figure labelled with exactly its own transition; no
      figure carries the wider span's label; NO_DATA only for genuinely
      unloaded months.
- [ ] C3: type a guardrail-tripping input (e.g. "ignore all previous
      instructions…") → the user message renders, the reply is the neutral
      refusal with the `⛉ GUARDRAIL` chip showing **category · severity** in
      the chip text (never the matched pattern); reload the conversation — the
      blocked pair is still in the transcript (persisted, not dropped).

## D — Commentary never empty

- [ ] Regenerate commentary on cdao_openai (prompt v1.2). Read the run summary:
      `published` + `published_fallback` should cover every transition;
      `blocked` should be 0.
- [ ] If any transition shows the **"Deterministic fallback"** tag (instead of
      the AI chip), that is the intended behaviour after 3 failed model
      attempts — the panel shows the computed-driver narrative, never empty.
      The generation log lists each failed attempt and its reason.
- [ ] No positive figure appears wrapped in parentheses anywhere in published
      narratives.

## E — Judge

- [ ] Leave `JUDGE_MODEL` empty first: the judge runs on the same cdao model the
      agents use. The evidence modal's "Independent review" shows a real
      faithfulness score.
- [ ] If a specific judge deployment is wanted, set `JUDGE_MODEL=<deployment>`;
      if that deployment does not exist, the modal must show
      **"Faithfulness — (unavailable)"** and "Judge unavailable — human review
      recommended" — **never 0.00** — and the commentary still publishes
      (guardrail remains the only gate).

## F — Glossary

- [ ] Open the Revenue-Driver glossary: entries render in attribution order
      (Volume, Deal size, One-time, … Baseline period limit) with meaning and
      computation populated for all 17 — after the driver_cause reseed in §0.4.

## Known pre-existing item (not from round 9)

- `scripts/verify_ingestion_fixes.py` check "delete-all continues past a failing
  entity" fails on the build box at the round-8 baseline too (environment-level;
  ingestion untouched this round). Tracked for round 10.
