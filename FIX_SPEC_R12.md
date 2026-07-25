# FIX SPEC — iPerform V2, Round 12 · PER-ROLE LLM CONFIG + AUTO-FALLBACK

> Small, surgical round. CLAUDE.md §0, §0.1, §3 and rule 8a still apply. Do not regress rounds
> 9–11. This round is LLM plumbing ONLY — it touches no computed figure. Reconciliation stays
> $0.00 (attribution is not touched at all).

---

## PROBLEM

The app has **three LLM roles** that may each need to run on a different model:
1. **Commentary writer** (the narrator)
2. **Judge** (independent review, advisory only)
3. **Assistant** ("Ask iPerform", round 7)

Today their model selection is incomplete for the client environment:
- The judge (R9 E) can override only a **model name** via `JUDGE_MODEL`; it cannot use its own
  **deployment name** or **api_version**. In Azure/cdao these three can differ (e.g. gpt-5.4-mini
  needs a newer api_version than the writer's gpt-4o deployment). A bare `JUDGE_MODEL` change
  therefore 404s.
- The assistant likewise cannot be pointed at its own model/deployment/api_version independently.
- There is no **auto-fallback**: if a role's configured model fails to construct or call, the
  operator wants it to fall back to the active agent LLM so the run still completes, rather than
  failing or going UNAVAILABLE.

## GOAL

Give **each of the three roles its own complete, optional LLM configuration** (mode, model,
deployment, api_version), independent of the others, with **automatic fallback to the active
default agent LLM** when a role's config is unset or fails. All-empty = today's behaviour
(no regression).

---

## A — PER-ROLE CONFIG KEYS (.env + settings)

For EACH role prefix — `WRITER_`, `JUDGE_`, `ASSISTANT_` — add these optional keys.

**IMPORTANT — align with keys that ALREADY EXIST; do not create duplicates:**
- `ASSISTANT_LLM_MODE` and `ASSISTANT_LLM_FALLBACK_MODES` **already exist** (R7). Use
  `ASSISTANT_LLM_MODE` as the assistant's `_CLIENT_MODE`; do NOT invent `ASSISTANT_CLIENT_MODE`.
  The new per-role auto-fallback (§C) must BUILD ON `ASSISTANT_LLM_FALLBACK_MODES`, not add a
  competing mechanism — the single-retry-to-default in §C is the *last* link after any
  configured sequential chain.
- `JUDGE_MODEL` and `JUDGE_ENABLED` **already exist** (R9 E) — keep and fold in.
- The WRITER has no prefixed keys today (just `ANTHROPIC_MODEL` / `CDAO_MODEL` per mode). The
  new `WRITER_*` keys, when empty, must resolve to those existing per-mode model defaults so
  nothing changes for an operator who sets none of them.

```
# --- Per-role LLM config (R12) — all optional; empty = inherit the active default ---
# Role prefixes: WRITER_ , JUDGE_ , ASSISTANT_
<ROLE>_CLIENT_MODE=      # empty = same as LLM_CLIENT_MODE; else cdao_openai|azure|claude|mock
<ROLE>_MODEL=            # model identifier for this role
<ROLE>_DEPLOYMENT=       # Azure/cdao DEPLOYMENT name, if different from the model id
<ROLE>_API_VERSION=      # api_version for this role, if different from the default
JUDGE_ENABLED=true       # existing, judge only
```

So concretely, the effective per-role key set (existing keys marked):
- **Writer:** `WRITER_CLIENT_MODE`, `WRITER_MODEL`, `WRITER_DEPLOYMENT`, `WRITER_API_VERSION`
  (all new; empty `WRITER_MODEL` = the mode's existing default, e.g. `ANTHROPIC_MODEL` /
  `CDAO_MODEL`).
- **Judge:** `JUDGE_CLIENT_MODE` (new), `JUDGE_MODEL` (**existing**), `JUDGE_DEPLOYMENT` (new),
  `JUDGE_API_VERSION` (new), `JUDGE_ENABLED` (**existing**).
- **Assistant:** `ASSISTANT_LLM_MODE` (**existing** — this IS its client-mode key),
  `ASSISTANT_MODEL` (new), `ASSISTANT_DEPLOYMENT` (new), `ASSISTANT_API_VERSION` (new),
  `ASSISTANT_LLM_FALLBACK_MODES` (**existing** — its sequential chain, preserved).

Rules (identical for every role):
- **All of a role's keys empty** → that role behaves exactly as today: active `LLM_CLIENT_MODE`
  / adapter, model = the mode's default (or the role's existing default, e.g. the judge's R5
  different-model default in claude mode). No behaviour change for anyone not setting these.
- **Any set** → the role is constructed with its own values, falling back **per-field** to the
  active mode's value for anything left empty (e.g. set only `JUDGE_API_VERSION` +
  `JUDGE_MODEL`, inherit workspace/mode/deployment).
- **`<ROLE>_DEPLOYMENT` vs `<ROLE>_MODEL`:** Azure/cdao route by **deployment**; the model id is
  passed in the request. Support both because they differ. If only one is set, use it for both
  roles best-effort and log which.
- Centralise this so the three roles share ONE resolution helper (role → effective
  {mode, model, deployment, api_version}); do not copy-paste three times.

## B — ROLE-AWARE CLIENT CONSTRUCTION

Extend the client builder so any role can pass its own `api_version` (and deployment), not just
a model override:
- Add optional `api_version_override` and `deployment_override` (where the adapter supports it)
  to the cdao/azure construction path, threaded from the resolved role config.
- `build_cdao_openai_client` / the azure path take the role's `api_version` when building that
  role's client; other roles are unaffected.
- Keep the guarded-import discipline intact (cdao imported only when a cdao mode is selected).
- The writer, judge, and assistant each obtain their client via the shared role-resolution
  helper + builder.

## C — AUTO-FALLBACK TO THE DEFAULT AGENT LLM (every role)

If a role's own configured client fails to construct or first-call (bad deployment, missing
api_version, 404/400):
- **catch it, log a WARNING naming the role and reason, and retry once with the active default
  agent LLM** (`build_llm_client(LLM_CLIENT_MODE)` — i.e. that role's `<ROLE>_*` treated as
  empty).
- **For the assistant specifically:** its existing `ASSISTANT_LLM_FALLBACK_MODES` sequential
  chain runs FIRST (unchanged R7 behaviour); the R12 single-retry-to-default is the final link
  AFTER that chain is exhausted, before the honest-decline state. Do not bypass or duplicate the
  existing chain.
- Record which path served the role: `role_config` (its own) / `fallback_agent_llm` (fell back)
  / `unavailable` (both failed).
- Behaviour on total failure is role-appropriate:
  - **Judge** → honest UNAVAILABLE (R9 E: -1.0 sentinel, "unavailable"/"—", REVIEW verdict,
    never 0.00, never blocks publication).
  - **Writer** → the existing commentary retry/deterministic-fallback path (R9 D) still applies;
    a writer with no working LLM falls to the deterministic template, never an empty panel.
  - **Assistant** → the honest "can't answer right now" path; never a fabricated answer.
- **None of this changes publication gating** — the deterministic guardrail remains the only
  gate; the judge stays advisory.

## D — ENV HEALTH REFLECTS EACH ROLE'S EFFECTIVE CONFIG

Extend the R10 Env Health "LLM connectivity" section: for EACH of the three roles show the
**effective** config it will use — mode, model/deployment, api_version — and the reachability
result for THAT specific configuration (not the default's). When a role would fall back, show
"configured model unreachable → will fall back to <default agent model>", so the operator sees
the true state of all three before running anything. No secrets — mode, model/deployment name,
api_version only.

## D2 — OPERATOR GUIDANCE (.env.example + completion doc) — REQUIRED

The client operator must know exactly what to put in each key. This is a first-class
deliverable, not an afterthought.

**In `.env.example`:** for every new key, a commented example with a short explanation of what
value goes there and how it differs from the others. Make the deployment-vs-model-vs-apiversion
distinction explicit, because that is the thing that caused the 404. For example:
```
# --- Per-role LLM config (R12) — all optional; empty inherits the active mode's default ---
# Azure/cdao route by DEPLOYMENT NAME (not the model family). The model id goes in the request,
# and some models need a specific api_version. These three can all differ — set what applies.
#
# JUDGE_CLIENT_MODE=cdao_openai        # empty = same mode as LLM_CLIENT_MODE
# JUDGE_MODEL=gpt-5.4-mini             # model identifier sent in the request
# JUDGE_DEPLOYMENT=<your-deployment>   # the Azure/cdao DEPLOYMENT NAME (portal → Deployments) — often NOT the model family
# JUDGE_API_VERSION=2024-12-01-preview # if this model needs a newer api_version than the writer
#   (if the judge model is unreachable it auto-falls back to the default agent model; Env Health shows this)
#
# WRITER_MODEL= / WRITER_DEPLOYMENT= / WRITER_API_VERSION= / WRITER_CLIENT_MODE=   # empty = current behaviour
# ASSISTANT_MODEL= / ASSISTANT_DEPLOYMENT= / ASSISTANT_API_VERSION=                # ASSISTANT_LLM_MODE already exists
```
(Use placeholder values, never real deployment names or secrets.)

**In `docs/ROUND12_ACCEPTANCE.md` (the completion doc):** a short "How to configure each role"
table — role, which keys, where to find the real value (Azure portal Deployments / cdao
workspace 906313), and the note that an unreachable configured model auto-falls back to the
default agent model and shows as such in Env Health. So the operator can fill these in without
guessing.

## E — WHAT NOT TO DO

- Do not touch attribution, taxonomy, eligibility, or any computed figure — LLM plumbing only.
  Reconciliation unaffected, stays $0.00.
- Do not make the judge blocking — advisory only.
- Do not change the credited-revenue definition or any driver.
- Do not print secrets in Env Health or put real deployment names/keys in .env.example (placeholders only).
- Do not regress rounds 9–11 (including R9 D writer fallback, R9 E judge UNAVAILABLE, R7
  assistant honesty).

## F — VERIFICATION (fixtures / local; you cannot reach cdao)

1. All per-role keys empty → all three roles behave exactly as today (regression check).
2. A role configured with a valid mock/claude model → uses it; metadata shows `role_config`.
3. A role configured with an invalid deployment/model → auto-falls back to the default agent
   LLM → still runs; metadata shows `fallback_agent_llm`; a WARNING is logged (test writer,
   judge, and assistant each).
4. Role config invalid AND default agent LLM unavailable (mock) → role-appropriate honest
   failure (judge UNAVAILABLE -1.0/"—"; writer deterministic template; assistant honest decline)
   — never a fabricated result, never 0.00 for the judge, publication proceeds.
5. Env Health shows all three roles' effective configs and any "will fall back" state; no
   secrets.
6. All existing suites pass; reconciliation $0.00; rounds 9–11 intact.

Write `docs/ROUND12_ACCEPTANCE.md` for the operator's real-cdao checks (set JUDGE_* to the real
gpt-5.4-mini deployment/api_version and ASSISTANT_*/WRITER_* as desired; confirm Env Health
shows each reachable; confirm each role uses its config and metadata shows `role_config`;
confirm a deliberately-wrong deployment falls back to the default agent model rather than
failing).

## G — PROGRESS TASKS

| ID | Task |
|----|------|
| Q-A | per-role keys (WRITER_/JUDGE_/ASSISTANT_ × MODE/MODEL/DEPLOYMENT/API_VERSION) + .env.example; shared role-resolution helper |
| Q-B | client builder accepts api_version/deployment overrides; all three roles use the helper+builder |
| Q-C | auto-fallback to default agent LLM on role-config failure; served path recorded (config/fallback/unavailable) per role |
| Q-D | Env Health shows each role's effective config + reachability + "will fall back" state |
| Q-D2 | .env.example: commented examples for every new key incl. deployment-vs-model-vs-apiversion note; completion doc "how to configure each role" table |
| Q-E | docs/ROUND12_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## H — DEFINITION OF DONE

- [ ] Writer, judge, and assistant each have independent optional config (mode, model,
      deployment, api_version), each falling back per-field to the active mode when empty
- [ ] All-empty config behaves exactly as rounds 7/9 (no regression) for all three roles
- [ ] A failing role config auto-falls back to the default agent LLM and still runs; the served
      path is recorded and surfaced; only total failure yields the role-appropriate honest state
      (judge UNAVAILABLE never 0.00; writer deterministic template; assistant honest decline)
- [ ] Judge stays advisory-only; publication gated solely by the deterministic guardrail
- [ ] Env Health shows all three roles' effective configs and reachability, no secrets
- [ ] .env.example documents every new key with an example value and the deployment-vs-model-vs-
      api_version distinction; the completion doc has a "how to configure each role" table
- [ ] Existing keys reused, not duplicated (ASSISTANT_LLM_MODE, ASSISTANT_LLM_FALLBACK_MODES,
      JUDGE_MODEL, JUDGE_ENABLED); the assistant's existing sequential fallback chain is preserved
- [ ] All suites pass; reconciliation $0.00; rounds 9–11 intact
- [ ] `PROGRESS.md` Q-tasks DONE; `BUILD_REPORT.md` Round 12 section; `ROUND12_CHANGED_FILES.md`
      produced
