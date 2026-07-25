# ROUND 13 CHANGED FILES — cdao GPT-5 compatibility (api_version / temperature / max_tokens)

Git-derived: `git diff --name-status 0427bb8..HEAD` (round-13 spec commit → round-13 wrap).
Operator-local material (data/real/, prompts/, qa_screenshots/, .env) is untouched this
round and excluded by construction. LLM plumbing only — no attribution, taxonomy,
eligibility or computed-figure file changed; reconciliation stays $0.00.

**Conflict-risk flag (⚠):** files the operator may have edited locally — in particular
`app/llm/client.py`, which the operator patched locally on the client machine to get the
main CDAO LLM green. The repo version now contains the complete fix (main + per-role);
**take the repo version and drop the local patch** — re-applying the local patch on top
would duplicate/conflict with R13 A–C.

| File | Status | What changed | Conflict risk |
|------|--------|--------------|---------------|
| `app/llm/client.py` | M | R13 A: `build_cdao_openai_client` omits the api_version arg when empty (workspace_id only). R13 B: `RealLLMClient` + `CdaoOpenAILLMClient` take `temperature_override` (default `CDAO_TEMPERATURE`=1) and pass `temperature` on every create; `build_llm_client` threads it. R13 C: `max_tokens` removed from both chat-completions creates; Anthropic `messages.create` keeps its `max_tokens=1024` | ⚠ **operator patched this locally** — repo version supersedes the local patch |
| `app/config/settings.py` | M | +4 keys: `CDAO_TEMPERATURE`, `WRITER_TEMPERATURE`, `JUDGE_TEMPERATURE`, `ASSISTANT_TEMPERATURE` (float, default 1); comment on `CDAO_API_VERSION` empty ⇒ omit | ⚠ operator may hold local settings edits |
| `.env.example` | M | the 4 new temperature keys + "empty api_version = GPT-5 signal" guidance (per-role block + cdao block) | ⚠ operator's real .env is separate; template may be locally annotated |
| `app/llm/roles.py` | M | `RoleLLMConfig` gains `temperature` (never counts toward R12 `configured_fields`); `resolve_role_config` reads the role's `*_TEMPERATURE`; `build_configured_role_client` passes it through | — |
| `app/v2/commentary/judge.py` | M | legacy R9 E path passes `JUDGE_TEMPERATURE` (call detail only; construction path unchanged) | — |
| `app/v2/assistant/providers.py` | M | primary chain link carries `ASSISTANT_TEMPERATURE` on real/cdao even without R12 config (call detail only; R7/R12 chain unchanged) | — |
| `app/services/llm_connectivity.py` | M | R13 D: probe constructs through the corrected path (temperature threaded, api_version omit-when-empty) and on cdao probes with a minimal one-word create (no max_tokens, output discarded); other modes keep the R10 models lookup | — |
| `app/services/environment_health_service.py` | M | comment only (probe description) | — |
| `frontend/components/env-health/env-health-workspace.tsx` | M | comment + footnote text only: cdao rows are probed by a minimal completion on the corrected runtime path | ⚠ shared screen file across rounds |
| `scripts/verify_gpt5_compat.py` | A | NEW — 34 fixture checks (F1–F6): fake `cdao`/`openai` modules capture construction + create kwargs for main + all three roles + real-mode adapter; Anthropic unchanged; probe path; R12 no-regression | — |
| `docs/ROUND13_ACCEPTANCE.md` | A | operator real-cdao checks + GPT-5 vs GPT-4 config table | — |
| `docs/ROUND13_CHANGED_FILES.md` | A | this file | — |
| `PROGRESS.md` | M | R-task tracking + R13 decisions | — |
| `BUILD_REPORT.md` | M | §19 Round 13 | — |

Not changed (deliberately): Anthropic/claude adapter (`max_tokens`/api_version),
writer R9 D fallback, judge R9 E advisory/UNAVAILABLE behaviour, assistant R7/R12
fallback chain semantics, attribution/taxonomy/eligibility/any figure, guarded cdao
import pattern, `azure` (SmartSDK) adapter, embedding adapter behaviour beyond
inheriting the shared builder's omit-when-empty rule.
