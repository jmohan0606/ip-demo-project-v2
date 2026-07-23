"""commentary_agent — narration (AGENT_SPEC §3). The only LLM-using agent.

The LLM receives the computed drivers as structured JSON and writes ONLY
language: an explanation sentence per bullet and the flowing narrative
paragraph. Every figure it may mention is already computed and formatted by
code; titles, headline and driver metadata are assembled deterministically.
If the LLM output cannot be parsed, deterministic fallback sentences built
from the cause vocabulary are used — figures are never affected either way.
"""
from __future__ import annotations

import json
import re

from app.agents.core.base_agent import BaseAgent
from app.agents.state.agent_state import AgentWorkflowState
from app.v2.format import fmt_money, fmt_money_k, fmt_pct

PROMPT_VERSION = "v1.0"

# Bullets shown per card (UI shows five drivers ranked by impact).
BULLET_COUNT = 5

_SYSTEM_PROMPT = """You write month-over-month revenue commentary for a financial advisor.
You will be given ALREADY-COMPUTED revenue drivers as JSON. Your job is language only:
- Use ONLY figures that appear in the input JSON, copied VERBATIM in their given format (e.g. "($44.1k)", "(17.7%)").
- NEVER introduce, adjust, round, re-round or infer a number. NEVER compute sums, differences, ratios or combined figures across drivers — if you want to describe a combination, use words ("together", "largely offset"), not a new number.
- If a figure is not in the input, it must not appear in your output.
- Negative amounts are written in parentheses, never with a minus sign.
- Use the client's product vocabulary exactly as given in the input.
- A driver flagged data_source DUMMY or ASSUMED must be described as unavailable/placeholder, never as an established fact.
- A driver with cause BASELINE_LIMITED reflects a limit of the loaded data range: too few months are loaded on one side of this transition to confirm whether accounts were genuinely opened or closed. Say that account-level attribution is unavailable for this transition for that reason. NEVER narrate it as accounts opened/closed, new business, client wins/losses or any other business event.
- NEW_ACCOUNT / LOST_ACCOUNT refer to accounts in recurring product lines with confirmed billing absence/appearance over consecutive months; describe them as accounts that stopped/started billing in recurring product lines — never as clients leaving or joining the practice.
Respond with ONLY a JSON object:
{"narrative_text": "<one flowing paragraph for the transition>",
 "bullet_texts": {"<driver_id>": "<one plain-business-language sentence explaining that driver>"}}"""

_CAUSE_FALLBACK = {
    "VOLUME": "Transaction volume changed at broadly similar rates.",
    "ONE_TIME": "One-time items in one month did not repeat in the other.",
    "ELIGIBILITY": "Revenue moved between credited and non-credited reason codes month over month.",
    "LATE_PROCESSING": "Revenue excluded by the 90-day processing rule changed between the months.",
    "EXCLUDED_CHANGE": "Revenue moved between credited and excluded reason codes (e.g. a deleted booking).",
    "TIMING": "Quarterly billing fell in one month of the pair, not the other.",
    "FEE_RATE": "The effective fee rate on the recurring base moved between the months.",
    "DISCOUNT": "Discounting changed between the months.",
    "BILLABLE_DAYS": "The months have a different number of billable days.",
    "MIX": "The remaining movement reflects shifts between products at different rates.",
    "NEW_ACCOUNT": "Accounts in recurring product lines began billing after consecutive months of no activity.",
    "LOST_ACCOUNT": "Accounts in recurring product lines stopped billing for consecutive months.",
    "CLAWBACK": "Reversal (negative) amounts changed between the months.",
    "MARKET": "Market performance effect is a placeholder — no index-return source is available.",
    "NET_FLOW": "Net client flow effect is a placeholder — the flows feed stops before this period.",
    "BASELINE_LIMITED": "Too few months are loaded on one side of this transition to "
                        "confirm account openings or closures, so account-level "
                        "attribution is unavailable for this transition.",
}


def _month_name(month_id: str) -> str:
    names = ["", "January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    return f"{names[int(month_id[4:6])]} {month_id[:4]}"


def _driver_payload(d: dict) -> dict:
    """What the LLM sees for one driver — figures pre-formatted by code."""
    return {
        "driver_id": d["driver_id"],
        "rank": d["rank"],
        "product_group": d["group_name"],
        "cause": d["cause_id"],
        "direction": d["direction"],
        "contribution": fmt_money_k(d["contribution_amt"]),
        "contribution_exact": fmt_money(d["contribution_amt"]),
        "share_of_change": fmt_pct(d["contribution_pct"]),
        "data_source": d["data_source"],
        "inputs": d.get("inputs") or {},
    }


def build_headline(revenue_output: dict) -> str:
    arrow = "▲" if revenue_output["change_amt"] >= 0 else "▼"
    return (f"{arrow} {fmt_money(revenue_output['change_amt'])}  "
            f"{fmt_pct(revenue_output['change_pct'])}")


def narrate(revenue_output: dict, llm) -> dict:
    """Commentary output contract from the revenue_agent output. `llm` is the
    active LLM client (claude or mock)."""
    top = [d for d in revenue_output["drivers"]][:BULLET_COUNT]
    payload = {
        "transition": f"{_month_name(revenue_output['from_month'])} -> {_month_name(revenue_output['to_month'])}",
        "total_change": fmt_money(revenue_output["change_amt"]),
        "total_change_pct": fmt_pct(revenue_output["change_pct"]),
        "from_revenue": fmt_money(revenue_output["from_revenue"]),
        "to_revenue": fmt_money(revenue_output["to_revenue"]),
        "drivers": [_driver_payload(d) for d in top],
    }
    llm_model = "unavailable"
    narrative = ""
    bullet_texts: dict[str, str] = {}
    try:
        raw = llm.generate(json.dumps(payload, indent=2), {"system_prompt": _SYSTEM_PROMPT})
        llm_model = llm.describe().get("model", llm.describe().get("mode", "unknown"))
        match = re.search(r"\{.*\}", raw or "", re.S)
        if match:
            parsed = json.loads(match.group(0))
            narrative = str(parsed.get("narrative_text") or "")
            bullet_texts = {str(k): str(v) for k, v in (parsed.get("bullet_texts") or {}).items()}
    except Exception:  # noqa: BLE001 — deterministic fallback below; never fabricates figures
        pass

    if not narrative:
        llm_model = f"{llm_model} (deterministic fallback)"
        direction = "up" if revenue_output["change_amt"] >= 0 else "down"
        parts = [
            f"Credited revenue moved {direction} {fmt_money(revenue_output['change_amt'])} "
            f"({fmt_pct(revenue_output['change_pct'])[1:-1] if revenue_output['change_pct'] < 0 else fmt_pct(revenue_output['change_pct'])}) "
            f"from {_month_name(revenue_output['from_month'])} to {_month_name(revenue_output['to_month'])}."
        ]
        for d in top[:3]:
            parts.append(f"{d['group_name']} contributed {fmt_money_k(d['contribution_amt'])} "
                         f"({_CAUSE_FALLBACK.get(d['cause_id'], d['cause_id']).lower().rstrip('.')}).")
        narrative = " ".join(parts)

    bullets = []
    for d in top:
        bullets.append({
            "driver_id": d["driver_id"],
            "direction": d["direction"],
            # "Structured Products ($44.1k)" — the parentheses ARE the sign (rule 8);
            # positive contributions read "Managed $12.3k".
            "title": f"{d['group_name']} {fmt_money_k(d['contribution_amt'])}",
            "text": bullet_texts.get(d["driver_id"]) or _CAUSE_FALLBACK.get(d["cause_id"], ""),
            "cause_id": d["cause_id"],
            "group_id": d["group_id"],
            "data_source": d["data_source"],
        })
    return {
        "headline": build_headline(revenue_output),
        "narrative_text": narrative,
        "bullets": bullets,
        "model": llm_model,
        "prompt_version": PROMPT_VERSION,
    }


# ---------------------------------------------------------------- anomaly mode (R6 Y6)
# The same boundary as commentary: rules are computed in Python; the model only
# PHRASES the finding. Every figure it may mention is already in the metrics /
# thresholds payload, pre-formatted by code.

_ANOMALY_SYSTEM_PROMPT = """You phrase already-computed anomaly findings for a financial advisor's revenue dashboard.
You will be given the rule that fired, the computed metrics that triggered it, and the thresholds in force, as JSON. Your job is language only:
- Use ONLY figures that appear in the input JSON, copied VERBATIM in their given format (e.g. "($44.1k)", "17.7%").
- NEVER introduce, adjust, round, re-round, sum or infer a number.
- Negative amounts are written in parentheses, never with a minus sign.
- State what was observed and why it crossed the threshold, in plain business language. Never speculate about causes the metrics do not show; never give advice.
Respond with ONLY a JSON object: {"title": "<short finding, max 12 words>", "detail_text": "<2-3 sentences>"}"""

# What each rule MEANS, passed to the model so its wording reflects the actual
# business semantics (a model guessing from a rule name writes plausible
# nonsense — e.g. reading BASELINE_LIMITED as a "baseline calculation limit").
_ANOMALY_MEANING = {
    "UNEXPLAINED_RESIDUAL": "part of the month-over-month change could not be attributed "
        "to any named driver (the MIX residual is above threshold) — a driver may be "
        "missing or the period may be a data boundary",
    "CLAWBACK_CONCENTRATION": "reversals (negative credited amounts) in this month are "
        "far above the advisor's trailing monthly average",
    "LARGE_SWING": "the total month-over-month credited-revenue change is unusually "
        "large in both percentage and dollar terms",
    "FEE_RATE_SHIFT": "the effective fee rate on a recurring (fee-based) product group "
        "moved by more basis points than the threshold — worth confirming whether a "
        "discount or repricing was applied",
    "SINGLE_DRIVER_DOMINANCE": "one named revenue driver accounts for more than the "
        "threshold share of the total change — the movement rests on a single explanation",
    "BASELINE_LIMITED_PRESENT": "this transition sits at the edge of the loaded data "
        "range, so account openings/closures cannot be confirmed on one side of it; the "
        "unclassifiable recurring-line account movement is reported as a Baseline period "
        "limit driver instead of being attributed — this is a data-range limitation, "
        "not a business event",
}

# Deterministic fallback templates per rule — used when the model's wording
# fails the no-invented-figures guardrail or cannot be parsed. `m` is the
# display-formatted metrics dict built by the detection service.
_ANOMALY_FALLBACK = {
    "UNEXPLAINED_RESIDUAL": lambda m: (
        "Unexplained residual above threshold",
        f"The MIX residual of {m['mix_total']} is {m['mix_pct_of_change']} of the total "
        f"change {m['total_change']}, above the configured threshold. A residual this "
        "large means part of the movement is not explained by any named driver."),
    "CLAWBACK_CONCENTRATION": lambda m: (
        "Clawbacks concentrated well above trailing average",
        f"Clawbacks of {m['clawback_total']} in {m['month']} compare with a trailing "
        f"monthly average of {m['trailing_mean']}. This concentration exceeds the "
        "configured multiple of the advisor's normal reversal level."),
    "LARGE_SWING": lambda m: (
        "Large month-over-month revenue swing",
        f"Credited revenue moved {m['change_amt']} ({m['change_pct']}) between the two "
        "months, exceeding both the percentage and dollar thresholds for a normal swing."),
    "FEE_RATE_SHIFT": lambda m: (
        "Effective fee rate shifted on a recurring group",
        f"The effective rate on {m['group_name']} moved from {m['from_rate_bps']} bps to "
        f"{m['to_rate_bps']} bps ({m['shift_bps']} bps), above the configured threshold "
        "for a recurring product group."),
    "SINGLE_DRIVER_DOMINANCE": lambda m: (
        "One driver dominates the change",
        f"The {m['cause_name']} driver contributes {m['contribution']} — "
        f"{m['share_of_change']} of the total change {m['total_change']}, above the "
        "configured dominance threshold. The movement rests on a single explanation."),
    "BASELINE_LIMITED_PRESENT": lambda m: (
        "Part of this change cannot be classified",
        f"A Baseline period limit driver of {m['baseline_limited_amt']} is present: too "
        "few months are loaded on one side of this transition to confirm account "
        "openings or closures, so that portion is reported as unclassifiable rather "
        "than attributed."),
}


def narrate_anomaly(rule_id: str, metrics: dict, thresholds: dict, llm) -> dict:
    """Title + detail_text for one fired rule. AI wording is validated by the
    no-invented-figures guardrail (app/guardrails/numeric_validation
    .validate_anomaly_text); on any failure the deterministic template is used
    instead — unverified wording is never published. Returns
    {title, detail_text, model, ai_generated, guardrail}."""
    from app.guardrails.numeric_validation import validate_anomaly_text

    payload = {"rule": rule_id,
               "what_this_rule_means": _ANOMALY_MEANING.get(rule_id, ""),
               "metrics": metrics, "thresholds": thresholds}
    title, detail, llm_model = "", "", "unavailable"
    try:
        raw = llm.generate(json.dumps(payload, indent=2), {"system_prompt": _ANOMALY_SYSTEM_PROMPT})
        llm_model = llm.describe().get("model", llm.describe().get("mode", "unknown"))
        match = re.search(r"\{.*\}", raw or "", re.S)
        if match:
            parsed = json.loads(match.group(0))
            title = str(parsed.get("title") or "").strip()
            detail = str(parsed.get("detail_text") or "").strip()
    except Exception:  # noqa: BLE001 — deterministic fallback below; never fabricates figures
        pass

    guardrail = {"passed": False, "blocked_reason": "no model output"}
    if title and detail:
        guardrail = validate_anomaly_text(metrics, thresholds, [title, detail])
    if not (title and detail and guardrail["passed"]):
        fallback = _ANOMALY_FALLBACK[rule_id]
        title, detail = fallback(metrics)
        return {"title": title, "detail_text": detail,
                "model": f"{llm_model} (deterministic fallback)",
                "ai_generated": False, "guardrail": guardrail}
    return {"title": title, "detail_text": detail, "model": llm_model,
            "ai_generated": True, "guardrail": guardrail}


class CommentaryAgent(BaseAgent):
    name = "commentary_agent"
    description = "Narrates already-computed drivers into commentary. Language only — never computes."

    def run(self, state: AgentWorkflowState) -> AgentWorkflowState:
        from app.llm.client import get_llm_client

        task = self.create_task("narrate computed drivers")
        try:
            revenue_output = state.context["revenue_output"]
            state.context["commentary"] = narrate(revenue_output, get_llm_client())
            state.tasks.append(self.complete_task(task, {"bullets": len(state.context["commentary"]["bullets"])}))
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"commentary_agent: {exc}")
            state.tasks.append(self.fail_task(task, exc))
        return state
