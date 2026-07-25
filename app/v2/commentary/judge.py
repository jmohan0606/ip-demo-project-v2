"""LLM-as-judge (FIX_SPEC R5) — independent review of stored commentary.

The judge runs AFTER the deterministic guardrails, on a DIFFERENT model than
the writer (settings.judge_model vs settings.anthropic_model). It sees the same
pre-formatted driver payload the writer saw plus the narrative and bullets, and
scores faithfulness / completeness / clarity with a PASS | REVIEW | FAIL
verdict.

ADVISORY ONLY (R5-3): deterministic guardrails remain the blocking gate. The
caller must never publish or suppress commentary based on the judge — its
verdict is surfaced for human attention and nothing else.

If the judge model is unavailable (mock mode, missing API key, invalid
JUDGE_MODEL, call/parse failure) the fallback is an honest REVIEW verdict with
UNAVAILABLE scores (stored as the -1.0 sentinel, rendered as "unavailable" /
"—", NEVER 0.00 — a 0.00 reads as a terrible real score; R9 E) and never a
fabricated PASS. Publication is never affected either way.

R9 E — the judge runs through the SAME LLM client/adapters the other agents
use (build_llm_client: mock|claude|real|cdao_openai|azure), never a separate
hardcoded deployment. JUDGE_MODEL selects its model within the active mode;
empty means the mode's own default model (claude mode keeps the R5 different-
model default), so an operator can always point the judge at the proven
working model and still demo.
"""
from __future__ import annotations

import json
import re

from app.agents.nodes.commentary_agent import BULLET_COUNT, _driver_payload, _month_name
from app.config.settings import get_settings
from app.shared.logging import get_logger
from app.v2.format import fmt_money, fmt_pct

_log = get_logger("app.v2.commentary.judge")

_VERDICTS = {"PASS", "REVIEW", "FAIL"}

_JUDGE_SYSTEM_PROMPT = """You are an independent reviewer of month-over-month revenue commentary.
You receive (a) the COMPUTED driver set the writer was given and (b) the commentary it wrote.
Judge the LANGUAGE against the computed facts. Answer four questions:
- faithfulness: is every claim in the narrative and bullets supported by the driver set, with no
  driver mischaracterised (wrong direction, wrong cause, overstated certainty)?
- hallucination: does the commentary assert anything (figure, driver, cause, event) that is not
  present in the driver set?
- completeness: are the top drivers by impact actually covered?
- clarity: is the language plain, unambiguous business English?
You do NOT verify arithmetic — deterministic guardrails already did. You judge characterisation.
Respond with ONLY a JSON object, no prose before or after:
{"faithfulness_score": <0-1>, "hallucination_flag": <true|false>, "completeness_score": <0-1>,
 "clarity_score": <0-1>, "verdict": "PASS|REVIEW|FAIL", "reasoning": "<short paragraph>"}"""


# R9 E — sentinel for "the judge could not run". Stored in the DOUBLE score
# columns (schema unchanged) and rendered as "unavailable" / "—", never 0.00.
SCORE_UNAVAILABLE = -1.0


def get_judge_llm():
    """The judge's LLM client — the SAME multi-mode adapters the other agents
    use (R9 E), on JUDGE_MODEL when set. Empty JUDGE_MODEL = the active mode's
    default model, except claude mode which keeps the R5 different-model
    default (claude-sonnet-5 vs the haiku writer). Returns None when no judge
    can run (mock mode, construction failure): judge_commentary then produces
    the honest UNAVAILABLE fallback.

    R12 — when any NEW judge key is set (JUDGE_CLIENT_MODE / JUDGE_DEPLOYMENT /
    JUDGE_API_VERSION), the judge gets its own client from the shared role
    helper, wrapped with the single-retry auto-fallback to the default agent
    LLM. JUDGE_MODEL alone keeps the exact R9 path (no regression)."""
    settings = get_settings()
    from app.llm.roles import RoleLLM, resolve_role_config

    cfg = resolve_role_config("judge", settings)
    if cfg.mode == "mock":
        # The judge never runs on the mock adapter — deterministic template
        # output cannot judge language. Honest UNAVAILABLE instead (R9 E).
        return None
    if cfg.configured:
        role_llm = RoleLLM(cfg)
        if not role_llm.available:
            # Both the configured client AND the default agent LLM failed to
            # construct → honest UNAVAILABLE (the WARNINGs are already logged).
            return None
        if role_llm.served_path == "fallback_agent_llm" and \
                settings.llm_client_mode.lower() == "mock":
            # The fallback landed on the mock adapter, which cannot judge —
            # honest UNAVAILABLE, never a deterministic pseudo-verdict (F4).
            _log.warning("judge: configured LLM unusable and the default agent "
                         "LLM is mock — judge UNAVAILABLE")
            return None
        return role_llm

    # No R12 config — the exact R9 E path.
    mode = cfg.mode
    model = (settings.judge_model or "").strip()
    if not model and mode == "claude":
        model = "claude-sonnet-5"  # R5: a different model than the writer
    try:
        from app.llm.client import build_llm_client

        # R13 B — JUDGE_TEMPERATURE (default 1) applies on the exact R9 E
        # path too: a cdao/real call detail, not a construction-path change.
        return build_llm_client(mode, model_override=model or None,
                                temperature_override=cfg.temperature)
    except Exception as exc:  # noqa: BLE001 — judge is advisory; never blocks the run
        _log.warning("judge LLM unavailable (%s); using UNAVAILABLE fallback", exc)
        return None


def _fallback(why: str, judge_model: str) -> dict:
    """Honest UNAVAILABLE state (R9 E): scores carry the -1.0 sentinel so no
    reader can mistake 'the judge could not run' for a 0.00 score."""
    return {
        "faithfulness_score": SCORE_UNAVAILABLE,
        "hallucination_flag": False,
        "completeness_score": SCORE_UNAVAILABLE,
        "clarity_score": SCORE_UNAVAILABLE,
        "verdict": "REVIEW",
        "reasoning": f"Judge unavailable ({why}) — human review recommended",
        "judge_model": judge_model,
    }


def _score(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _writer_payload(revenue_output: dict) -> dict:
    """EXACTLY the pre-formatted payload the writer saw (commentary_agent.narrate)
    — same figures, same formatting — so the judge compares against the same
    facts, not a re-derivation."""
    top = list(revenue_output["drivers"])[:BULLET_COUNT]
    return {
        "transition": f"{_month_name(revenue_output['from_month'])} -> {_month_name(revenue_output['to_month'])}",
        "total_change": fmt_money(revenue_output["change_amt"]),
        "total_change_pct": fmt_pct(revenue_output["change_pct"]),
        "from_revenue": fmt_money(revenue_output["from_revenue"]),
        "to_revenue": fmt_money(revenue_output["to_revenue"]),
        "drivers": [_driver_payload(d) for d in top],
    }


def judge_commentary(revenue_output: dict, commentary: dict, llm) -> dict:
    """Evaluate one transition's commentary. Never raises; never blocks.

    Returns {faithfulness_score, hallucination_flag, completeness_score,
    clarity_score, verdict, reasoning, judge_model}. `llm` is the judge client
    from get_judge_llm() (None => deterministic REVIEW fallback)."""
    settings = get_settings()
    if llm is None:
        label = ("mock (deterministic)" if settings.llm_client_mode.lower() == "mock"
                 else f"{settings.llm_client_mode} (deterministic)")
        return _fallback("no judge model in this LLM mode", label)

    judge_model = llm.describe().get("model", settings.judge_model)
    prompt = json.dumps({
        "computed_drivers": _writer_payload(revenue_output),
        "commentary": {
            "headline": commentary.get("headline") or "",
            "narrative_text": commentary.get("narrative_text") or "",
            "bullets": [{"driver_id": b.get("driver_id"), "title": b.get("title"),
                         "text": b.get("text"), "cause": b.get("cause_id"),
                         "data_source": b.get("data_source")}
                        for b in commentary.get("bullets", [])],
        },
    }, indent=2)

    try:
        raw = llm.generate(prompt, {"system_prompt": _JUDGE_SYSTEM_PROMPT})
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            return _fallback("judge response contained no JSON", judge_model)
        parsed = json.loads(match.group(0))
    except Exception as exc:  # noqa: BLE001 — advisory only; fall back honestly
        return _fallback(f"{type(exc).__name__}: {exc}", judge_model)

    verdict = str(parsed.get("verdict") or "").upper()
    if verdict not in _VERDICTS:
        verdict = "REVIEW"
    result = {
        "faithfulness_score": _score(parsed.get("faithfulness_score")),
        "hallucination_flag": bool(parsed.get("hallucination_flag")),
        "completeness_score": _score(parsed.get("completeness_score")),
        "clarity_score": _score(parsed.get("clarity_score")),
        "verdict": verdict,
        "reasoning": str(parsed.get("reasoning") or "")[:2000],
        "judge_model": llm.describe().get("model", judge_model),
    }
    # R12 C — served path (role_config / fallback_agent_llm) when the judge
    # runs on a RoleLLM; absent on the unconfigured R9 path. The describe() is
    # re-read AFTER generate() because a first-call fallback swaps the client.
    path = llm.describe().get("served_path", "")
    if path:
        result["llm_path"] = path
    return result
