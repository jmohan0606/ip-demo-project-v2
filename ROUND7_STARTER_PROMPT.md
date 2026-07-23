# ROUND 7 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. This round builds ONE feature: the conversational
assistant ("Ask iPerform") — the capability the client asked for by name. Work autonomously
and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R7.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the Z-prefixed tasks from FIX_SPEC_R7 §E; do not renumber
   existing tasks. If any Z-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE Z-task.
4. Open `docs/ui/reference/roadmap/04_chat_overlay.png` (primary design) and
   `01_conversational_assistant.png` (full-page expansion) before building any UI.

THE GOVERNING PRINCIPLE — this is the whole point of the feature:
The assistant CHOOSES WHICH AUDITED QUERY TO RUN and NARRATES THE RESULT. It never computes,
estimates or infers a figure. Every number comes from the same deterministic queries the rest
of the app uses. If a question cannot be answered from loaded data, it says so plainly rather
than guessing. Do not compromise this for conversational smoothness — it is what makes a chat
interface defensible in a bank.

KEY DECISIONS (already settled — implement, don't redesign):
- SCOPE: cross-advisor. "Which advisor had the biggest drop in June?" is a primary use case.
  Advisor-level permission scoping is deferred to a later round.
- PROVIDERS: follow the existing guarded pattern in app/llm/client.py — cdao_openai primary in
  the client environment with sequential fallback; claude on the build box. Log which provider
  served each turn; a fallback must be logged, never silent.
- ROUTING: deterministic intent router FIRST (a rule table mapping question shapes to
  catalogued queries + params). Only if nothing matches, an LLM fallback that returns a
  STRUCTURED {query, params} SELECTION — validated against the catalog before running. The
  model never answers from its own knowledge and never returns a figure.
- CONTEXT: each turn stores its resolved parameters; the next turn inherits unless overridden.
  Screen state seeds context so "why did this drop?" resolves with no parameters. The resolved
  context must be VISIBLE on every answer, with a Pin control to freeze it.
- PERSISTENCE: TigerGraph vertices with the SQLite local tier as fallback; 10-day rehydration
  (ASSISTANT_HISTORY_DAYS, config).
- FACTS ONLY: no advice. When asked for advice, answer the factual part AND decline the
  advisory part in one breath — never a flat refusal, never repeated disclaimers.
- UI: OVERLAY panel (not push) that persists across navigation and collapses to a floating
  button; a full-page expansion sharing the SAME component.

GUARDRAILS — CRITICAL, AND CURRENTLY A GAP:
The V1 guardrail stack is ALREADY in the repo (app/guardrails/client.py: check_input /
check_output, eight categories incl. PROMPT_INJECTION, JAILBREAK, PII with Luhn-validated
card numbers, TOXICITY, plus safe_refusal). NOTHING in app/v2 currently calls it — harmless
until now because V2 had no free-text input, but a chat box is exactly what a bank reviewer
will probe. Wire it in per §A9-A11:
- check_input() runs BEFORE routing, before context resolution, before ANY model call.
  Injection/jailbreak/toxicity/oversize = BLOCK (no routing, no LLM). PII = REDACT before
  storing and before any provider sees it — a pasted SSN must never reach TigerGraph or a log.
- Refusal wording comes from safe_refusal(): neutral and brief. NEVER explain which pattern
  matched (that teaches bypass) and never style it as an application error.
- check_output() runs in addition to numeric validation — it catches PII surfacing from data.
- BLOCKED turns are VISIBLE in the transcript (the operator wants this for the demo): the
  user's message renders, the reply is the refusal with a neutral "⛉ GUARDRAIL" chip showing
  CATEGORY AND SEVERITY ONLY. This turns an attempted probe into a demonstration of control.
- Extend the message vertex with guardrail_status and guardrail_json (no matched text).
- Include ~15 adversarial fixtures AND false-positive checks: benign questions like "why did
  revenue drop" and "show me account 83700968" must NOT trip the guard.

VERIFICATION: you cannot reach TigerGraph or real data. Build `scripts/verify_assistant.py`
with the seven checks in §C — routing across ~25 fixture questions, no-invented-figures,
context inheritance across three turns, out-of-scope/no-data honesty, the advice pattern,
persistence round-trip and rehydration, and zero-console-error UI. Write
`docs/ROUND7_ACCEPTANCE.md` for what only the operator can confirm. Never describe a fixture
check as a real-data verification.

NOT IN SCOPE: advisor permission scoping, RAG or external knowledge, any recommendation
capability, book movement, MDW roll-up, streaming ingestion, or changes to the
credited-revenue definition, reason model, attribution or existing queries.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Also produce `docs/ROUND7_CHANGED_FILES.md` (git-derived, per work-stream, operator-local
files excluded, conflict-risk files flagged).

IF BLOCKED: do not stop. Prefer an honest "I can't answer that from the loaded data" over any
fabricated answer. Record the decision in PROGRESS.md and continue.

Begin with Z-A1. Wire the input guardrail (Z-A10) before the router exists — it is a small
change done first and an awkward retrofit done last.

---
