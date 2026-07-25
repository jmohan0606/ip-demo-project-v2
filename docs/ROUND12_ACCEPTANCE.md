# ROUND 12 ACCEPTANCE — per-role LLM config + auto-fallback (operator checks)

Everything verifiable on the build box has been verified (`scripts/verify_role_llm.py`,
32/32 PASS, plus all pre-existing suites). This document covers ONLY what needs the real
client environment (cdao / Azure), which is unreachable from the build box.

---

## 1. How to configure each role

Each of the three LLM roles — commentary **writer**, **judge** (advisory only), and
**assistant** ("Ask iPerform") — can run on its own model. All keys are optional; a field
left empty inherits the active mode's value **per field**; all fields empty = pre-R12
behaviour exactly.

**The distinction that caused the R9 `gpt-4o-mini` 404:** Azure/cdao route requests by
**DEPLOYMENT NAME** (what you created in the portal — often *not* the model family name),
the **MODEL id** goes in the request, and some models need their own **API_VERSION**.
These three can all differ — set what applies for the role's model.

| Role | Keys | Where to find the real value |
|------|------|------------------------------|
| Writer | `WRITER_CLIENT_MODE`, `WRITER_MODEL`, `WRITER_DEPLOYMENT`, `WRITER_API_VERSION` | Mode: `cdao_openai` in the client env. Deployment: Azure portal → your OpenAI resource → **Deployments** (the *deployment name* column), or the cdao workspace **906313** model listing. api_version: the model's docs / the version that works for it in the notebook. Empty `WRITER_MODEL` = the mode's default (`CDAO_MODEL` / `ANTHROPIC_MODEL`). |
| Judge | `JUDGE_CLIENT_MODE` (new), `JUDGE_MODEL` (existing, R9), `JUDGE_DEPLOYMENT` (new), `JUDGE_API_VERSION` (new), `JUDGE_ENABLED` (existing) | Same sources as the writer. To run the judge on e.g. gpt-5.4-mini: set `JUDGE_MODEL` to the model id, `JUDGE_DEPLOYMENT` to that model's **deployment name**, and `JUDGE_API_VERSION` if it needs a newer one than the writer's deployment. |
| Assistant | `ASSISTANT_LLM_MODE` (existing, R7 — this IS its client-mode key), `ASSISTANT_MODEL`, `ASSISTANT_DEPLOYMENT`, `ASSISTANT_API_VERSION`, `ASSISTANT_LLM_FALLBACK_MODES` (existing, R7 chain — unchanged) | Same sources. The R7 sequential fallback chain still runs after the primary; the R12 retry-with-the-default-agent-LLM is the final link after that chain. |

**Auto-fallback:** if a role's configured model fails to construct or on first call (bad
deployment, missing api_version, 404/400), the app logs a WARNING naming the role and
retries once with the default agent LLM (`LLM_CLIENT_MODE`). The served path is recorded
per role (`role_config` / `fallback_agent_llm` / `unavailable`) and **Env Health shows the
effective config, reachability, and any "will fall back" state for all three roles** —
check it before running anything. Only total failure yields the honest state: judge →
UNAVAILABLE ("—", never 0.00, never blocks publication); writer → deterministic template;
assistant → honest decline. Publication remains gated solely by the deterministic
guardrail; the judge stays advisory.

## 2. Operator checks (real cdao, workspace 906313)

1. **Env Health first.** With your per-role keys set (e.g. `JUDGE_MODEL=gpt-5.4-mini`,
   `JUDGE_DEPLOYMENT=<its deployment name>`, `JUDGE_API_VERSION=<its version>`), open
   Operations → Env Health. Expect: three rows (writer / judge / assistant), each showing
   the **effective** mode, model, deployment and api_version you configured, each
   `model-found`. No key or token appears anywhere on the card.
2. **Roles actually use their config.** Run a single-advisor Regenerate. Expect: the
   commentary metadata (`model` on the version; `llm_path` on the commentary) shows the
   writer's configured model and `role_config`; the judge evaluations carry the judge
   model and `llm_path: role_config`. Ask the assistant a question; the message metadata's
   provider label shows `[served: role_config]` when ASSISTANT_* overrides are set.
3. **Deliberately-wrong deployment falls back, not fails.** Set
   `JUDGE_DEPLOYMENT=does-not-exist`, restart, re-check Env Health: the judge row goes
   red with "configured model unreachable → will fall back to the default agent LLM
   (…)". Run a regenerate: it completes; the app log has a WARNING naming the judge role;
   evaluations carry `llm_path: fallback_agent_llm` (scores real, from the default agent
   model — not 0.00, not UNAVAILABLE). Repeat the same drill for `WRITER_DEPLOYMENT` and
   `ASSISTANT_DEPLOYMENT` if desired — same pattern, run always completes.
4. **All-empty regression.** Remove all per-role keys, restart: behaviour is identical to
   round 11 (writer on `CDAO_MODEL`, judge per `JUDGE_MODEL`/mode default, assistant per
   the R7 chain).
5. **Reconciliation unchanged.** After any regenerate: reconciliation remains $0.00 —
   this round touched no computed figure.
