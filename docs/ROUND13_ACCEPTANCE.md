# ROUND 13 — OPERATOR ACCEPTANCE (real cdao, client machine)

Round 13 made the cdao client GPT-5-compatible (FIX_SPEC_R13): empty
api_version ⇒ omitted from `openai_azure_client(...)`; temperature configurable
(default 1) on every chat-completions create; max_tokens removed from those
creates; the Env Health per-role probe runs the exact corrected runtime path.
Everything below needs the real cdao subscription, so it is yours. The build
box verified all of it on fixtures (`python scripts/verify_gpt5_compat.py`,
34/34) and re-ran every existing suite (reconciliation $0.00, rounds 9–12
intact).

## How to configure (the config value is the ONLY signal — no model-name detection)

| Deployment series | api_version key | temperature key |
|---|---|---|
| GPT-5.x (incl. mini/nano) | **leave EMPTY** (`CDAO_API_VERSION=` for the main LLM; `WRITER_/JUDGE_/ASSISTANT_API_VERSION=` per role) — the argument is then OMITTED from the cdao client construction | leave at default 1 (GPT-5 rejects < 1) |
| GPT-4.x | set as today (e.g. `2024-02-01`) | default 1 works; set e.g. `JUDGE_TEMPERATURE=0.2` if you want the old behaviour |

Empty inheritance still applies per field (R12): a role with an empty
`*_API_VERSION` inherits `CDAO_API_VERSION`; only when BOTH are empty is the
argument omitted.

## Checks (run after PCL AWS login, `LLM_CLIENT_MODE=cdao_openai`)

1. **GPT-5 main LLM** — `CDAO_API_VERSION=` (empty), `CDAO_MODEL=<gpt-5 deployment>`.
   Restart the backend. Env Health → the main **LLM** card is green and the test
   generation renders.
2. **GPT-5 roles green** — point writer/judge/assistant at GPT-5 deployments
   (e.g. `WRITER_CLIENT_MODE=cdao_openai`, `WRITER_DEPLOYMENT=<gpt-5 deployment>`,
   `WRITER_API_VERSION=` empty; same shape for JUDGE_/ASSISTANT_). Env Health →
   **LLM connectivity**: all three rows show `model-found` with the check text
   "minimal chat.completions.create … via the corrected runtime path (R13)".
   This probe is a one-word completion (discarded) — the previous UNAVAILABLE
   rows came from the old construction, not from your deployments.
3. **GPT-4 role still works** — set one role to a GPT-4 deployment WITH its
   api_version (e.g. `JUDGE_DEPLOYMENT=<gpt-4o deployment>`,
   `JUDGE_API_VERSION=2024-02-01`). Its row is green too; optionally set
   `JUDGE_TEMPERATURE=0.2` and confirm it still answers.
4. **Commentary end-to-end** — Regenerate (this advisor). The run completes,
   commentary PUBLISHED, judge scores present (not "— (unavailable)"), figures
   verbatim, negatives in parentheses, AI chips on wording only.
5. **Assistant** — ask a question on Ask iPerform; a GPT-5-backed primary
   answers without falling back (turn metadata / logs show no FALLBACK
   warning).
6. **Fallback drill unchanged (R12/R9/R7)** — break one role's deployment name;
   its row goes red with the "will fall back" note; a generation run logs the
   WARNING and serves via the default agent LLM. Restore afterwards.

## Not changed (do not expect differences)

- Anthropic/claude adapter: still sends `max_tokens=1024`; api_version handling
  untouched.
- Writer R9 D fallback, judge R9 E advisory/UNAVAILABLE behaviour, assistant
  R7/R12 fallback chain — only the cdao construction/call details changed.
- No computed figure touched; reconciliation stays $0.00.
