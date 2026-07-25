# FIX SPEC — iPerform V2, Round 13 · CDAO GPT-5 COMPATIBILITY (api_version / temperature / max_tokens)

> Small, surgical round. CLAUDE.md §0, §0.1, §3 and rule 8a still apply. LLM plumbing ONLY —
> touches no computed figure. Reconciliation stays $0.00 (attribution untouched).
> Do not regress rounds 9–12.

---

## PROBLEM (confirmed by operator testing against real cdao)

The GPT-5 series (gpt-5.x, incl. mini/nano) on cdao has three incompatibilities the current
code does not handle. The main CDAO LLM was patched locally and now shows green, but the
per-role (writer/judge/assistant) paths still fail because they build the client and call
`.create()` through construction that was not given the same fixes.

1. **`api_version` must be OMITTED for GPT-5.** `openai_azure_client(...)` for a GPT-5
   deployment must be called with `workspace_id` only — passing any `api_version` fails. GPT-4
   still needs `api_version`. **Signal: config value.** No model-name detection.
2. **`temperature` must be `1`.** These models reject any temperature < 1. Needs to be a
   configurable value (default 1) per role AND for the main CDAO LLM, and passed to
   `.chat.completions.create(...)`.
3. **`max_tokens` must be removed entirely** from the cdao `.create()` call — the GPT-5 series
   rejects it.

## GOAL

Make the cdao client construction and completion call GPT-5-compatible, uniformly across the
main LLM and all three roles, driven by config (never by model-name checks).

---

## A — `api_version`: empty config ⇒ omit it (workspace_id only)

- In `build_cdao_openai_client` (app/llm/client.py:14): if the effective `api_version` is empty
  / None / blank, call `openai_azure_client(workspace_id=workspace_id)` **without** the
  `api_version` argument. If a non-empty `api_version` is present, call it exactly as today
  (`openai_azure_client(api_version=..., workspace_id=...)`) so GPT-4 and other series still work.
- **This is a config-driven switch, NOT a model-name check.** Leaving `CDAO_API_VERSION` /
  `<ROLE>_API_VERSION` empty is the operator's signal "this is a GPT-5-style deployment — omit
  api_version." Do not inspect the model string.
- Apply this to EVERY cdao construction path: the main LLM AND the per-role builder
  (the CdaoOpenAI client `__init__` at ~line 359–364 which currently does
  `api_version=api_version_override or settings.cdao_api_version`). When both the override and
  `settings.cdao_api_version` resolve to empty, the api_version must be omitted, not passed as
  empty string.

## B — `temperature`: per-role + main CDAO setting, default 1

- Add `CDAO_TEMPERATURE` (default `1`) for the main CDAO LLM, and `WRITER_TEMPERATURE`,
  `JUDGE_TEMPERATURE`, `ASSISTANT_TEMPERATURE` (each default `1`) for the roles. Type: float.
- Thread temperature through the shared `roles.py` resolver (RoleLLMConfig gains `temperature`),
  so all four flow into the same construction/call path.
- Pass `temperature` into **every** cdao `.chat.completions.create(...)` call (both the main
  path ~line 200 and the per-role CdaoOpenAI create call). Default 1 means GPT-5 works out of
  the box; overridable per role for GPT-4 testing.

## C — `max_tokens`: remove from the cdao create call

- **Remove `max_tokens=1024` entirely** from the cdao `.chat.completions.create(...)` calls
  (line ~202 and the per-role create). The GPT-5 series rejects it.
- Leave the Anthropic path's `max_tokens` (line ~151/153, `messages.create`) UNCHANGED — that
  is the claude adapter, not cdao, and Anthropic requires max_tokens.
- Do not reintroduce a token cap on the cdao path.

## D — ENV HEALTH ROLE CHECK MUST USE THE SAME CONSTRUCTION (the current red)

The main "LLM" panel is green but the per-role "LLM connectivity" rows are UNAVAILABLE because
the role reachability check builds/calls the client the OLD way (with api_version, with
max_tokens, temperature < 1). Route the per-role Env Health probe through the SAME corrected
construction and create call (A + B + C) so a GPT-5 role that actually works shows green. The
probe stays read-only (a minimal `.create()` — no max_tokens, temperature from config,
api_version omitted when empty); no secrets; nothing mutated.

## E — WHAT NOT TO DO

- No model-name / "startswith gpt-5" detection anywhere — config value is the only signal.
- Do not touch attribution, taxonomy, eligibility, or any figure — reconciliation stays $0.00.
- Do not change the Anthropic/claude adapter's max_tokens or api_version handling.
- Do not change the writer's R9 D fallback, the judge's R9 E advisory/UNAVAILABLE behaviour, or
  the assistant's R7/R12 fallback chain — only the cdao construction/call details.
- Do not print secrets in Env Health.
- Do not regress rounds 9–12.

## F — VERIFICATION (fixtures / local; you cannot reach cdao)

1. `build_cdao_openai_client` with empty api_version → constructs with workspace_id only, no
   api_version arg (assert via the guarded shim / a fake `openai_azure_client` capturing kwargs).
2. With non-empty api_version → still passes api_version (GPT-4 path intact).
3. cdao `.create()` calls pass `temperature` (default 1) and carry NO `max_tokens`
   (assert the kwargs of a fake client for main + all three roles).
4. Anthropic path still sends max_tokens (unchanged).
5. Per-role Env Health probe uses the corrected construction (same code path as runtime).
6. All-empty per-role config still behaves as R12 (no regression); temperature defaults to 1.
7. All existing suites pass; reconciliation $0.00; rounds 9–12 intact.

Write `docs/ROUND13_ACCEPTANCE.md` for the operator's real-cdao checks: with GPT-5 deployments
and empty `*_API_VERSION`, Env Health shows all three roles green; a GPT-4 role with an
api_version set also works; commentary/judge/assistant all run.

## G — PROGRESS TASKS

| ID | Task |
|----|------|
| R-A | build_cdao_openai_client + per-role builder: empty api_version ⇒ omit it (workspace_id only), config-driven |
| R-B | CDAO_TEMPERATURE + WRITER/JUDGE/ASSISTANT_TEMPERATURE (default 1) threaded via roles.py into every cdao create |
| R-C | remove max_tokens from cdao create calls (main + per-role); leave Anthropic untouched |
| R-D | Env Health per-role probe uses the same corrected construction/call |
| R-E | docs/ROUND13_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## H — DEFINITION OF DONE

- [ ] Empty api_version (main or any role) ⇒ cdao client built with workspace_id only, api_version
      omitted; non-empty still passed — config-driven, no model-name checks
- [ ] temperature configurable per role and for the main CDAO LLM, default 1, passed to every cdao create
- [ ] max_tokens removed from all cdao create calls; Anthropic path unchanged
- [ ] Env Health per-role rows use the corrected construction and go green when the deployment works
- [ ] All-empty per-role config behaves as R12; all suites pass; reconciliation $0.00; rounds 9–12 intact
- [ ] PROGRESS.md R-tasks DONE; BUILD_REPORT.md Round 13 section; ROUND13_CHANGED_FILES.md produced
