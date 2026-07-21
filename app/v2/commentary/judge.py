"""LLM-as-judge (FIX_SPEC R5) — independent review of stored commentary.

The judge runs AFTER the deterministic guardrails, on a DIFFERENT model than
the writer (settings.judge_model vs settings.anthropic_model). It sees the same
pre-formatted driver payload the writer saw plus the narrative and bullets, and
scores faithfulness / completeness / clarity with a PASS | REVIEW | FAIL
verdict.

ADVISORY ONLY (R5-3): deterministic guardrails remain the blocking gate. The
caller must never publish or suppress commentary based on the judge — its
verdict is surfaced for human attention and nothing else.

If the judge model is unavailable (mock mode, missing API key, call/parse
failure) the fallback is an honest REVIEW verdict with zero scores — never a
fabricated PASS.
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


def get_judge_llm():
    """The judge's LLM client, on settings.judge_model — a DIFFERENT model than
    the writer. Returns None when no real judge model can run in this mode
    (mock, or any non-claude transport): judge_commentary then produces the
    deterministic REVIEW fallback."""
    settings = get_settings()
    if settings.llm_client_mode.lower() != "claude":
        return None
    try:
        from app.llm.client import ClaudeLLMClient

        return ClaudeLLMClient(model_override=settings.judge_model)
    except Exception as exc:  # noqa: BLE001 — judge is advisory; never blocks the run
        _log.warning("judge LLM unavailable (%s); using REVIEW fallback", exc)
        return None


def _fallback(why: str, judge_model: str) -> dict:
    return {
        "faithfulness_score": 0.0,
        "hallucination_flag": False,
        "completeness_score": 0.0,
        "clarity_score": 0.0,
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
    return {
        "faithfulness_score": _score(parsed.get("faithfulness_score")),
        "hallucination_flag": bool(parsed.get("hallucination_flag")),
        "completeness_score": _score(parsed.get("completeness_score")),
        "clarity_score": _score(parsed.get("clarity_score")),
        "verdict": verdict,
        "reasoning": str(parsed.get("reasoning") or "")[:2000],
        "judge_model": judge_model,
    }
