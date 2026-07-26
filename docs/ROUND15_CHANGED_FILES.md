# ROUND 15 CHANGED FILES — git-derived (eb418a3..HEAD)

Derived from `git diff --name-status eb418a3..HEAD` (round-15 spec commit to
wrap). Operator-local files (`.env`, `data/real/*`, anything gitignored) are
never touched by this round and are excluded. **Conflict risk** flags files an
operator may have patched locally — on the client machine the repo version
supersedes; re-apply local config through `.env`, not code edits.

## A — classifier boundary (U-A / U-A3)

| File | Change | Conflict risk |
|---|---|---|
| `app/v2/assistant/system_prompts.py` | CLASSIFIER_SYSTEM rewritten: hard boundary, 21 worked examples, when-in-doubt-safe rule | ⚠ if the operator hand-tuned the prompt locally — repo version supersedes (it IS the round-15 fix) |
| `app/v2/assistant/intent_classifier.py` | mock rules to the same boundary: every/all-advisors requires a raw-data noun or dump/export; `ignore your scope`; `new instructions:` trailing-\b fix | low |

## B — regex toggle (U-B)

| File | Change | Conflict risk |
|---|---|---|
| `app/config/settings.py` | + `guardrail_regex_enabled` (GUARDRAIL_REGEX_ENABLED, default true) | ⚠ additive — merge trivially if patched locally |
| `app/v2/assistant/guardrail_gate.py` | `_demote_pattern_blocks` (PI-*/JB-* → FLAG when disabled); per-turn posture log; PII redaction + IV-LENGTH untouched | low |
| `app/services/llm_connectivity.py` | guardrail row + `regex_layer` posture field; unavailable-note states the regex posture | low |
| `.env.example` | + GUARDRAIL_REGEX_ENABLED block | ⚠ operators keep their own .env — example only |

## C / D — driver-month + pin removal (U-C / U-D)

| File | Change | Conflict risk |
|---|---|---|
| `app/v2/assistant/context.py` | single loaded month on WHY_CHANGE/DRIVER_DETAIL → M→next (prev→M when last); `pinned` layer/param REMOVED (question > inherited > screen > default) | ⚠ callers of `resolve()` must drop the `pinned` kwarg |
| `app/v2/assistant/service.py` | `ask()` loses `pinned`; scope_json written empty (column kept — NO schema change); no `pinned` in resolved context | ⚠ API callers passing `pinned` will get a 422-free ignore (field gone from AskBody) |
| `app/v2/assistant/router.py` | MOM_CHANGE also matches "what changed …", "changed in/for/from", "compare …" | low |
| `app/api/routers/v2.py` | AskBody: `pinned` field removed | low |
| `frontend/components/assistant/assistant-context.tsx` | pinned state/setPinned removed; `monthIds` exposed for the scope header | ⚠ if locally patched — repo supersedes |
| `frontend/components/assistant/assistant-panel.tsx` | Pin button + pinned chip removed; honest "Scoped to <advisor> · <range> · credited" header; context chip no longer says "pinned" | ⚠ same |
| `frontend/lib/api/v2.ts` | AskRequest: `pinned` removed (scope_json stays on ConversationRow — schema column kept) | low |

## Verification / docs / progress

| File | Change |
|---|---|
| `scripts/verify_round15.py` | NEW — checks 1–7 across the full advisor×transition matrix, per-check counts, exit non-zero |
| `scripts/verify_assistant.py` | multi-turn fixture updated to the R15 C anchoring (May→Jun); `pinned=None` kwargs dropped |
| `scripts/verify_guardrail_llm.py` | GUARDRAIL_REGEX_ENABLED added to the env-reset key list |
| `.gitignore` | + ROUND15_STARTER_PROMPT.md (operator-local, never committed) |
| `PROGRESS.md`, `BUILD_REPORT.md` | round-15 task table + §21 |
| `docs/ROUND15_ACCEPTANCE.md`, `docs/ROUND15_CHANGED_FILES.md` | NEW — this round's operator docs |

## NOT changed (deliberately)

- No schema change: `scope_json` stays on `phx_dm_v2_conversation` (written
  empty). No GSQL/query/catalog/manifest change. No attribution, taxonomy,
  eligibility or figure change — reconciliation stays $0.00.
- `GUARDRAIL_BLOCK_THRESHOLD` default unchanged (0.5) — the prompt is the fix.
- The R9 advisor binding and R7/R9 multi-turn inheritance are untouched.
