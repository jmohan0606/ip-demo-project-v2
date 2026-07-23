"""Multi-turn context resolution for Ask iPerform (FIX_SPEC_R7 A4).

Deterministic code, not model memory. Each turn stores its RESOLVED parameters
(advisor_sid, from_month, to_month, group_id, measure); the next turn inherits
them unless the new question overrides. Screen state seeds the context — so
"why did this drop?" with no parameters resolves correctly — and a Pin freezes
the context so it stops following the screen.

Precedence per field (highest wins):
    1. entities extracted from THIS question
    2. the pinned context (when pinned)
    3. the previous turn's resolved context (inheritance)
    4. the current screen state (when not pinned)
    5. defaults: latest loaded transition; advisor from the screen

Every resolved field carries WHERE it came from, so the UI can show the
context chip honestly (invisible context is where chat assistants lose trust).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResolvedContext:
    advisor_sid: str = ""      # "" = across all advisors
    from_month: str = ""
    to_month: str = ""
    group_id: str = ""
    measure: str = "credited"
    sources: dict = field(default_factory=dict)  # field -> question|pinned|inherited|screen|default

    def as_dict(self) -> dict:
        return {
            "advisor_sid": self.advisor_sid,
            "from_month": self.from_month,
            "to_month": self.to_month,
            "group_id": self.group_id,
            "measure": self.measure,
            "sources": self.sources,
        }


_FIELDS = ("advisor_sid", "from_month", "to_month", "group_id", "measure")


def resolve(*, entities: dict, screen: dict | None, previous: dict | None,
            pinned: dict | None, month_ids: list[str], intent: str) -> ResolvedContext:
    """Merge the four context layers by precedence. `entities` comes from the
    router's extraction over THIS question only; `month_ids` is the loaded
    month list (ascending) used for transition defaults."""
    ctx = ResolvedContext()
    layers = [
        ("default", _defaults(month_ids, screen)),
        ("screen", {} if pinned else (screen or {})),
        ("inherited", previous or {}),
        ("pinned", pinned or {}),
        ("question", entities or {}),
    ]
    for source, values in layers:
        for f in _FIELDS:
            v = values.get(f)
            if v not in (None, ""):
                setattr(ctx, f, str(v))
                ctx.sources[f] = source

    # A month named alone ("what about May?") re-anchors the transition:
    # to_month = that month, from_month = the prior loaded month.
    if entities.get("to_month") and not entities.get("from_month"):
        prior = _prior_month(str(entities["to_month"]), month_ids)
        if prior:
            ctx.from_month = prior
            ctx.sources["from_month"] = "question"

    # Cross-advisor intents drop the single-advisor scope.
    if intent == "COMPARE_ADVISORS" and not entities.get("advisor_sid"):
        ctx.advisor_sid = ""
        ctx.sources["advisor_sid"] = "question"

    # A question that names a NEW subject clears a group carried from a
    # previous drill-down unless this question (or pin) named the group.
    if intent in ("REVENUE_TREND", "MOM_CHANGE", "COMPARE_ADVISORS", "ANOMALIES",
                  "COMMENTARY") and ctx.sources.get("group_id") == "inherited":
        ctx.group_id = ""
        ctx.sources.pop("group_id", None)
    return ctx


def _defaults(month_ids: list[str], screen: dict | None) -> dict:
    out: dict = {"measure": "credited"}
    if month_ids:
        out["to_month"] = month_ids[-1]
        out["from_month"] = month_ids[-2] if len(month_ids) > 1 else month_ids[-1]
    if screen and screen.get("advisor_sid"):
        out["advisor_sid"] = screen["advisor_sid"]
    return out


def _prior_month(month_id: str, month_ids: list[str]) -> str:
    try:
        i = month_ids.index(month_id)
    except ValueError:
        return ""
    return month_ids[i - 1] if i > 0 else ""


def chip_label(ctx: ResolvedContext, advisor_names: dict[str, str],
               month_names: dict[str, str], group_names: dict[str, str]) -> str:
    """The human-readable context chip ("V236209 · May→Jun · credited")."""
    parts = []
    parts.append(advisor_names.get(ctx.advisor_sid, ctx.advisor_sid) if ctx.advisor_sid
                 else "All advisors")
    if ctx.from_month and ctx.to_month and ctx.from_month != ctx.to_month:
        parts.append(f"{month_names.get(ctx.from_month, ctx.from_month)}→"
                     f"{month_names.get(ctx.to_month, ctx.to_month)}")
    elif ctx.to_month:
        parts.append(month_names.get(ctx.to_month, ctx.to_month))
    if ctx.group_id:
        parts.append(group_names.get(ctx.group_id, ctx.group_id))
    parts.append(ctx.measure)
    return " · ".join(parts)
