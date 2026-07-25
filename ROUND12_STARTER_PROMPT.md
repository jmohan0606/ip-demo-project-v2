# ROUND 12 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Small surgical round: give each of the three LLM roles
its own independent, optional configuration with auto-fallback. This is LLM plumbing ONLY — it
touches no computed figure. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R12.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the Q-prefixed tasks from FIX_SPEC_R12 §G; do not renumber
   existing tasks. If any Q-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE Q-task.
4. Read app/config/settings.py, app/llm/client.py, app/v2/commentary/judge.py, and the
   assistant's LLM construction before changing anything.

THE THREE ROLES: commentary WRITER, JUDGE (advisory only, R9 E), ASSISTANT ("Ask iPerform",
R7). Each may need a different model in the client env, and Azure/cdao route by DEPLOYMENT with
a model id and an api_version that can all differ — a single model-name override is not enough
(that is why setting JUDGE_MODEL=gpt-4o-mini 404'd: it could not carry a different api_version).

WHAT TO BUILD (detail in the spec):
A. Per-role optional keys, prefixes WRITER_ / JUDGE_ / ASSISTANT_, each with (client-mode,
   model, deployment, api_version). CRITICAL — REUSE EXISTING KEYS, DO NOT DUPLICATE: the code
   ALREADY has ASSISTANT_LLM_MODE and ASSISTANT_LLM_FALLBACK_MODES (R7) and JUDGE_MODEL /
   JUDGE_ENABLED (R9 E). Use ASSISTANT_LLM_MODE as the assistant's client-mode (do NOT invent
   ASSISTANT_CLIENT_MODE); keep JUDGE_MODEL/JUDGE_ENABLED. New keys: WRITER_CLIENT_MODE/
   WRITER_MODEL/WRITER_DEPLOYMENT/WRITER_API_VERSION; JUDGE_CLIENT_MODE/JUDGE_DEPLOYMENT/
   JUDGE_API_VERSION; ASSISTANT_MODEL/ASSISTANT_DEPLOYMENT/ASSISTANT_API_VERSION. Empty WRITER_
   keys resolve to the existing per-mode defaults (ANTHROPIC_MODEL/CDAO_MODEL) so nothing
   changes for an operator who sets none. All empty for a role = today's behaviour (no
   regression). Any set = build that role
   with its own values, falling back PER-FIELD to the active mode for empties. DEPLOYMENT vs
   MODEL: Azure/cdao route by deployment, model id goes in the request — support both. Put the
   role→effective-config resolution in ONE shared helper, not copied three times.
B. Extend the client builder to accept api_version and deployment overrides (not just model),
   threaded from the resolved role config; keep the guarded cdao import; all three roles obtain
   their client via the shared helper + builder.
C. AUTO-FALLBACK: if a role's own configured client fails to construct or first-call (bad
   deployment / missing api_version / 404/400), catch it, log a WARNING naming the role and
   reason, and retry ONCE with the active default agent LLM (that role's keys treated as empty).
   For the ASSISTANT specifically: its existing ASSISTANT_LLM_FALLBACK_MODES sequential chain
   runs FIRST (unchanged R7); the R12 single-retry-to-default is the FINAL link after that chain,
   before the honest-decline state. Build on the existing chain, do not duplicate it.
   Record the served path per role: role_config / fallback_agent_llm / unavailable. Only total
   failure yields the role-appropriate honest state: judge → UNAVAILABLE (R9 E: -1.0 sentinel,
   "unavailable"/"—", REVIEW, never 0.00, never blocks publication); writer → the R9 D
   deterministic-template fallback (never an empty panel); assistant → honest "can't answer"
   (never fabricated). Publication stays gated only by the deterministic guardrail; judge stays
   advisory.
CO. OPERATOR GUIDANCE (required deliverable): in .env.example, add a commented example for
   every new key with a short explanation, making the DEPLOYMENT-vs-MODEL-vs-API_VERSION
   distinction explicit (that distinction is what caused the gpt-4o-mini 404) — placeholders
   only, never real deployment names or secrets. In docs/ROUND12_ACCEPTANCE.md add a "how to
   configure each role" table: role, which keys, where to find the real value (Azure portal
   Deployments / cdao workspace 906313), and the note that an unreachable configured model
   auto-falls back to the default agent model and shows as such in Env Health.

D. Env Health: extend the R10 LLM connectivity section to show, for EACH of the three roles, the
   EFFECTIVE config (mode, model/deployment, api_version) and reachability for THAT config; when
   a role would fall back, show "configured model unreachable → will fall back to <default
   model>". No secrets — mode/model/deployment/api_version only.

NOT IN SCOPE / DO NOT: touch attribution, taxonomy, eligibility, or any computed figure (this is
plumbing only — reconciliation stays $0.00); make the judge blocking; change the credited-revenue
definition or any driver; print secrets; regress rounds 9–11 (R9 D writer fallback, R9 E judge
UNAVAILABLE, R7 assistant honesty).

VERIFICATION: you cannot reach cdao. Verify on fixtures + local (mock/claude) per §F: all-empty =
no regression for all three roles; a valid role config is used (metadata role_config); an invalid
role config auto-falls back to the default agent LLM and still runs (metadata fallback_agent_llm,
WARNING logged) — test writer, judge, AND assistant; total failure gives the role-appropriate
honest state (never fabricated, judge never 0.00); Env Health shows all three effective configs
and "will fall back" states with no secrets. All existing suites pass; reconciliation $0.00;
rounds 9–11 intact. Write docs/ROUND12_ACCEPTANCE.md (operator real-cdao checks) and
docs/ROUND12_CHANGED_FILES.md (git-derived, conflict-risk flagged, operator-local excluded).

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Begin with Q-A.

---
