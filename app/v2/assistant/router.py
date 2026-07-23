"""Deterministic intent router for Ask iPerform (FIX_SPEC_R7 A3, stage 1).

A rule/pattern table mapping recognised question shapes onto catalogued
queries + parameters. This runs FIRST on every (guardrail-passed) turn; only
when nothing here matches does the constrained LLM fallback (stage 2,
llm_fallback.py) get a chance — and that fallback can only SELECT a query,
never answer.

The router also extracts entities (months, advisor, product group, measure)
from the question text against the LOADED reference data, so resolution is
honest: a month that is not loaded becomes a NO_DATA answer, never a guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Intent -> the catalogued queries the service will run (A3 table). Names must
# exist in query_catalog.json — verified by scripts/verify_assistant.py.
INTENT_QUERIES: dict[str, list[str]] = {
    "REVENUE_TREND": ["get_monthly_revenue_totals"],
    "REVENUE_BY_PRODUCT": ["get_monthly_revenue_by_product"],
    "MOM_CHANGE": ["get_revenue_changes"],
    "WHY_CHANGE": ["get_revenue_changes", "get_change_drivers"],
    "DRIVER_DETAIL": ["get_revenue_changes", "get_change_drivers", "get_evidence"],
    "TRANSACTIONS": ["get_transactions"],
    "COMPARE_ADVISORS": ["get_advisors", "get_revenue_changes"],
    "ANOMALIES": ["get_anomalies"],
    "COMMENTARY": ["get_commentary"],
    "REFERENCE": ["get_driver_causes", "get_reason_codes"],
}

_MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES) + r")\b(?:\s+(\d{4}))?", re.IGNORECASE)
_MONTH_ID_RE = re.compile(r"\b(20\d{2})(0[1-9]|1[0-2])\b")

_ADVICE_RE = re.compile(
    r"\b(should i|should we|what should|recommend|recommendation|advice|advise|"
    r"suggest|how (?:do|can|should) i (?:improve|fix|grow|recover|win)|"
    r"what would you do)\b", re.IGNORECASE)

# Ordered rule table — first match wins. More specific shapes come first.
_INTENT_RULES: list[tuple[str, re.Pattern]] = [
    ("COMPARE_ADVISORS", re.compile(
        r"\b(which|what|whose)\s+advisor\b|\bacross (all )?(my )?advisors\b|"
        r"\bcompare\b.*\b(advisors?|vs\.?|versus)\b|\badvisors? (had|with) the\b|"
        r"\bwho (had|saw|dropped|gained)\b", re.IGNORECASE)),
    ("ANOMALIES", re.compile(
        r"\b(anything |something )?(unusual|anomal\w*|out of the ordinary|odd|"
        r"irregular|flag(?:ged|s)?)\b", re.IGNORECASE)),
    ("REFERENCE", re.compile(
        r"\bwhat (does|do|is)\b.*\bmean\b|\bmeaning of\b|\bdefine\b|"
        r"\bdefinitions?\b|\bglossary\b", re.IGNORECASE)),
    ("TRANSACTIONS", re.compile(
        r"\b(which|what|show( me)?|list)\b.*\b(accounts?|transactions?|trades?|"
        r"clawbacks?)\b|\bclawbacks?\b|\baccounts? (drove|behind|caused)\b",
        re.IGNORECASE)),
    ("COMMENTARY", re.compile(
        r"\b(summari[sz]e|summary|recap|overview)\b", re.IGNORECASE)),
    ("DRIVER_DETAIL", re.compile(
        r"\b(tell me|more) about\b|\babout the\b.*\b(drop|decline|fall|increase|"
        r"drivers?)\b", re.IGNORECASE)),
    ("WHY_CHANGE", re.compile(
        r"\bwhy\b|\bwhat (drove|was driving|is driving|caused|explains)\b|"
        r"\bdrivers?\b(?! cause)|\bdriving\b|\breasons? (for|behind)\b", re.IGNORECASE)),
    ("REVENUE_BY_PRODUCT", re.compile(
        r"\bby product\b|\bper product\b|\bproduct (mix|breakdown|split)\b|"
        r"\bbreak\s?down\b|\bsplit by\b", re.IGNORECASE)),
    ("MOM_CHANGE", re.compile(
        r"\bhow much did\b.*\bchange\b|\bchange (in|for|from)\b|\bmonth[- ]over[- ]month\b|"
        r"\b(vs\.?|versus|compared? (to|with))\b|\b(drop|fall|fell|decline[d]?|"
        r"decrease[d]?|increase[d]?|rise|rose|up|down)\b.*\b(much|by)\b|"
        r"\bhow much (lower|higher|less|more)\b", re.IGNORECASE)),
    ("REVENUE_TREND", re.compile(
        r"\b(what was|what is|whats|what's|show( me)?|how much)\b.*\brevenue\b|"
        r"\brevenue (in|for|of)\b|\btrend\b|\bhow (am i|did i) do\b", re.IGNORECASE)),
]

# Loose signal that a bare follow-up ("what about May?", "and Alternative
# Investments?") should inherit the previous intent.
_FOLLOWUP_RE = re.compile(r"^\s*(what about|how about|and|also|same for)\b", re.IGNORECASE)


@dataclass
class Reference:
    """Loaded reference data the router extracts entities against."""
    month_ids: list[str]                       # ascending, e.g. ["202604", ...]
    advisors: dict[str, str]                   # sid -> display name
    groups: dict[str, str]                     # group_id -> group name
    causes: dict[str, str] = field(default_factory=dict)   # cause_id -> name
    reasons: dict[str, str] = field(default_factory=dict)  # reason code -> name


@dataclass
class RoutePlan:
    intent: str = ""                 # "" = no deterministic match
    entities: dict = field(default_factory=dict)
    advisory: bool = False
    reference_term: str = ""
    unloaded_month: str = ""         # named month outside the loaded range
    compare_sids: list[str] = field(default_factory=list)
    matched_rule: str = ""           # which rule fired (audit)


def extract_entities(text: str, ref: Reference) -> tuple[dict, str]:
    """Deterministic entity extraction. Returns (entities, unloaded_month) —
    unloaded_month set when the question names a month that is not loaded."""
    entities: dict = {}
    unloaded = ""
    low = text.lower()

    months_found: list[str] = []
    for m in _MONTH_ID_RE.finditer(text):
        months_found.append(m.group(1) + m.group(2))
    for m in _MONTH_RE.finditer(text):
        month_no = _MONTH_NAMES[m.group(1).lower()]
        year = m.group(2)
        if year:
            months_found.append(f"{year}{month_no:02d}")
        else:
            hits = [mid for mid in ref.month_ids if int(mid[4:6]) == month_no]
            months_found.append(hits[-1] if hits
                                else f"????{month_no:02d}")
    loaded = [m for m in months_found if m in ref.month_ids]
    named_unloaded = [m for m in months_found if m not in ref.month_ids]
    if named_unloaded and not loaded:
        unloaded = named_unloaded[0]
    if len(loaded) >= 2:
        entities["from_month"], entities["to_month"] = sorted(loaded)[0], sorted(loaded)[-1]
    elif len(loaded) == 1:
        entities["to_month"] = loaded[0]

    sids = [sid for sid in ref.advisors
            if re.search(rf"\b{re.escape(sid)}\b", text, re.IGNORECASE)]
    for sid, name in ref.advisors.items():
        if name and name.lower() in low and sid not in sids:
            sids.append(sid)
    if len(sids) == 1:
        entities["advisor_sid"] = sids[0]
    if sids:
        entities["_advisor_sids"] = sids

    for gid, gname in ref.groups.items():
        if gname and gname.lower() in low or gid.replace("_", " ") in low:
            entities["group_id"] = gid
            break
    return entities, unloaded


def route(text: str, ref: Reference, last_intent: str = "") -> RoutePlan:
    """Stage 1 — the deterministic rule table. First match wins; a bare
    follow-up with extractable entities inherits the previous intent."""
    plan = RoutePlan()
    plan.advisory = bool(_ADVICE_RE.search(text))
    plan.entities, plan.unloaded_month = extract_entities(text, ref)
    plan.compare_sids = plan.entities.pop("_advisor_sids", [])

    for intent, pattern in _INTENT_RULES:
        m = pattern.search(text)
        if m:
            plan.intent = intent
            plan.matched_rule = f"{intent}:{m.group(0)[:40]}"
            break

    # "tell me about the structured products drop" — a group named together
    # with driver/why language is the drill-down shape.
    if plan.intent in ("WHY_CHANGE", "MOM_CHANGE") and plan.entities.get("group_id"):
        plan.intent = "DRIVER_DETAIL"
    if plan.intent == "REFERENCE":
        plan.reference_term = _reference_term(text, ref)
    if not plan.intent and last_intent and (
            _FOLLOWUP_RE.search(text) or plan.entities):
        plan.intent = last_intent
        plan.matched_rule = f"follow-up:{last_intent}"
        if plan.intent in ("WHY_CHANGE", "MOM_CHANGE") and plan.entities.get("group_id"):
            plan.intent = "DRIVER_DETAIL"
    # An advice-only question with no other shape still deserves the factual
    # part: the latest transition's why-summary (A6 — answer facts, decline
    # the advisory part in the same breath).
    if not plan.intent and plan.advisory:
        plan.intent = "WHY_CHANGE"
        plan.matched_rule = "advice:factual-part"
    return plan


def _reference_term(text: str, ref: Reference) -> str:
    low = text.lower()
    for vocab in (ref.causes, ref.reasons):
        for key, name in vocab.items():
            if key.lower() in low or (name and name.lower() in low):
                return key
    m = re.search(r"what (?:does|do|is)\s+[\"']?([\w &-]+?)[\"']?\s+mean", low)
    return m.group(1).strip() if m else ""
