# ROUND 14 CHANGED FILES — LLM-based guardrail layer (defense in depth)

Git-derived: `git diff --name-status 1550f74..HEAD` (round-14 spec commit → round-14 wrap).
Operator-local material (data/real/, prompts/, qa_screenshots/, .env) is untouched this
round and excluded by construction. Assistant guardrail plumbing only — no attribution,
taxonomy, eligibility or computed-figure file changed; reconciliation stays $0.00.

**Conflict-risk flag (⚠):** files the operator may have edited locally on the client
machine. This round adds config KEYS only (new `GUARDRAIL_*` block) — no existing key's
meaning changed — so local settings/.env edits merge cleanly; take the repo version and
re-apply local values.

| File | Status | What changed | Conflict risk |
|------|--------|--------------|---------------|
| `app/llm/roles.py` | M | S-A: `guardrail` added to ROLES with full per-field resolution (mode/model/deployment/api_version/temperature), R13 GPT-5 handling and R12 auto-fallback inherited unchanged | — |
| `app/config/settings.py` | M | S-A/S-C: +7 keys — `GUARDRAIL_LLM_MODE/MODEL/DEPLOYMENT/API_VERSION/TEMPERATURE` (per-role block), `GUARDRAIL_LLM_ENABLED` (gates ONLY the classifier; regex layer 1 always on), `GUARDRAIL_BLOCK_THRESHOLD` (0.0–1.0, default 0.5) | ⚠ operator may hold local settings edits — additive keys, merge cleanly |
| `.env.example` | M | the new R14 guardrail-role block with fail-safe + GPT-5 guidance | ⚠ operator's real .env is separate; template may be locally annotated |
| `app/services/llm_connectivity.py` | M | S-A: Env Health gains a "guardrail classifier" row — effective per-field config + reachability probe through the corrected R13 path; mock mode labelled "deterministic keyword classifier"; no secrets | — |
| `app/v2/assistant/intent_classifier.py` | A | NEW — S-B: one constrained guardrail-role call per turn returning strict JSON `{category, confidence, reason}`; deterministic keyword classifier in mock mode; `ClassifierUnavailable` on ANY failure (never a guess) | — |
| `app/v2/assistant/system_prompts.py` | A | NEW — S-D: hardened narrator system prompt (scope lock, no instruction reveal, no arbitrary execution, input-as-data) + example-rich classifier system prompt + deterministic system-prompt leak-fragment check | — |
| `app/v2/assistant/guardrail_gate.py` | M | S-B/C/E/F: `screen_input` = regex (unchanged, PII redacted FIRST) → classifier on redacted text → threshold policy; never downgrades a regex BLOCK; classifier failure FAILS SAFE (`CLASSIFIER_DEGRADED` finding, logged, never open); `screen_output` blocks system-prompt/instruction leaks; classifier `reason` is log-only — persisted findings carry category+severity+action ONLY (S-G) | — |
| `app/v2/assistant/service.py` | M | S-B/S-D: `off_scope_use` → polite OUT_OF_SCOPE decline BEFORE routing; narrator uses the hardened system prompt; blocked turns persist with `guardrail_status=BLOCKED` exactly as R9 (chip unchanged) | — |
| `data/sample/vertices/phx_dm_v2_conversation.csv` | M | S-H fixture conversations from the verification runs (attack blocked / benign out-of-scope / honest NO_DATA) | — |
| `data/sample/vertices/phx_dm_v2_message.csv` | M | the persisted turns for those conversations — BLOCKED rows carry `[{category, severity, action}]` only, no reason | — |
| `data/sample/edges/phx_dm_v2_conversation_for_advisor.csv` | M | edge for the advisor-scoped fixture conversation | — |
| `data/sample/edges/phx_dm_v2_message_in_conversation.csv` | M | message→conversation edges for the fixtures | — |
| `scripts/verify_guardrail_llm.py` | A | NEW — 54 fixture checks: paraphrased attacks BLOCK, benign PASS, regex layer independent, no-downgrade, PII-before-classifier, fail-safe (forced outage) logged and never open, visibility payload category+severity only, output leak check, Env Health row, config thresholds | — |
| `scripts/verify_role_llm.py` | M | check 5.1 expects the additive 4th (guardrail) role row — 32/32 again | — |
| `docs/ROUND14_ACCEPTANCE.md` | A | operator real-cdao checks (live guardrail role, live paraphrased-attack blocks, Env Health row green) | — |
| `docs/ROUND14_CHANGED_FILES.md` | A | this file | — |
| `PROGRESS.md` | M | S-task tracking + R14 decisions | — |
| `BUILD_REPORT.md` | M | §20 Round 14 | — |

Not changed (deliberately, per FIX_SPEC_R14 §G): the regex pre-filter rules themselves
(layer 1 stays exactly as R9), writer/judge/assistant LLM behaviour beyond the added
guardrail role, `app/llm/client.py` (R13 GPT-5 handling reused as-is),
attribution/taxonomy/eligibility/any computed figure, the frontend guardrail chip
(`assistant-panel.tsx` — the R9 chip already renders category+severity only and the R14
payload is shape-identical), Env Health screen component (new row flows through the
existing per-role table).
