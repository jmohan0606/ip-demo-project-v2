# ROUND 13 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Small surgical round: make the cdao client GPT-5
compatible across the main LLM and all three roles. LLM plumbing ONLY — touches no computed
figure. Work autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R13.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the R-prefixed tasks from FIX_SPEC_R13 §G; do not renumber. If any
   R-task is DONE, this is a RESUME — verify against `git log --oneline` and continue.
4. Read app/llm/client.py (build_cdao_openai_client ~line 14, the main cdao create ~line 200 with
   max_tokens=1024 ~line 202, and the per-role CdaoOpenAI __init__ ~line 359 that does
   api_version=api_version_override or settings.cdao_api_version), app/llm/roles.py, and
   app/config/settings.py before changing anything.

PROBLEM (confirmed against real cdao): the GPT-5 series (gpt-5.x incl. mini/nano) on cdao has
three incompatibilities. The main CDAO LLM was patched locally and shows green, but the per-role
writer/judge/assistant paths still fail because they build/call the client the old way.

THE THREE FIXES (all config-driven — NO model-name / startswith checks anywhere):
A. api_version: in build_cdao_openai_client, if the effective api_version is empty/blank, call
   openai_azure_client(workspace_id=workspace_id) WITHOUT the api_version arg; if non-empty, pass
   it as today (GPT-4 keeps working). Apply to the main path AND the per-role builder — when both
   the override and settings.cdao_api_version resolve empty, OMIT api_version, do not pass "".
   Empty config is the operator's signal for a GPT-5 deployment.
B. temperature: add CDAO_TEMPERATURE (default 1) for the main LLM and WRITER_TEMPERATURE /
   JUDGE_TEMPERATURE / ASSISTANT_TEMPERATURE (each default 1, float). Thread through roles.py
   (RoleLLMConfig gains temperature) and pass temperature into EVERY cdao
   .chat.completions.create(...) (main + per-role). GPT-5 rejects temperature < 1; default 1
   makes it work, overridable for GPT-4 testing.
C. max_tokens: REMOVE max_tokens=1024 entirely from the cdao create calls (main + per-role). GPT-5
   rejects it. Leave the Anthropic/claude adapter's messages.create max_tokens UNCHANGED
   (Anthropic requires it). Do not reintroduce a token cap on the cdao path.
D. Env Health per-role probe (the current red): the "LLM connectivity" rows are UNAVAILABLE
   because the role reachability check builds/calls the client the OLD way. Route the per-role
   probe through the SAME corrected construction/create (A+B+C) so a working GPT-5 role shows
   green. Keep it read-only (minimal create, no max_tokens, temperature from config, api_version
   omitted when empty), no secrets, nothing mutated.

NOT IN SCOPE / DO NOT: any model-name detection (config value is the ONLY signal); touch
attribution/taxonomy/eligibility/any figure (reconciliation stays $0.00); change the
Anthropic/claude adapter's max_tokens or api_version; change the writer R9 D fallback, judge R9 E
advisory/UNAVAILABLE behaviour, or assistant R7/R12 fallback chain (only the cdao construction/
call details); print secrets; regress rounds 9–12.

VERIFICATION (fixtures/local — you cannot reach cdao): use a fake openai_azure_client capturing
kwargs to assert — empty api_version ⇒ constructed with workspace_id only (no api_version arg);
non-empty ⇒ api_version passed; every cdao create passes temperature (default 1) and carries NO
max_tokens, for main AND all three roles; Anthropic path still sends max_tokens; the per-role Env
Health probe uses the corrected path; all-empty per-role config still behaves as R12. All suites
pass; reconciliation $0.00; rounds 9–12 intact. Write docs/ROUND13_ACCEPTANCE.md (operator
real-cdao checks) and docs/ROUND13_CHANGED_FILES.md (git-derived, conflict-risk flagged,
operator-local excluded).

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name · every
fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in parentheses
· model-authored language carries an AI-generated chip and computed figures never.

Begin with R-A.

---
