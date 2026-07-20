"""Commentary validation gate (AGENT_SPEC §5). Deliberately NOT an agent.

Five blocking checks between commentary_agent and publication:
  1. no invented figures  2. reconciliation  3. evidence completeness
  4. provenance honesty   5. negative-number format
On failure the transition's commentary is persisted as BLOCKED with the reason —
never discarded, never silently omitted.
"""
from __future__ import annotations

import re
from typing import Any

RECONCILE_TOLERANCE = 1.0

# The lookbehind keeps digits inside identifiers (account "SMPLACCT-1109",
# trade "SMPLTRD00048") from being read as figures.
_NUMBER_RE = re.compile(r"(?<![\w-])\$?\(?\s*\d[\d,]*\.?\d*\s*k?\)?%?")
# A minus applied to a figure ("-$44.1k", "- 17.7%"). The lookbehind excludes
# intra-word hyphens and date/month ranges like "202604-202605" or "one-time".
_MINUS_FIGURE_RE = re.compile(r"(?<![\w])[-−]\s*\$?\d")


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_allowed(revenue_output: dict) -> set[float]:
    """Every figure the commentary is allowed to mention: the transition totals,
    every driver's contribution/share, and every numeric inside inputs_json."""
    allowed: set[float] = set()

    def add(v) -> None:
        f = _num(v)
        if f is not None:
            allowed.add(abs(f))

    for key in ("from_revenue", "to_revenue", "change_amt", "change_pct", "txn_count"):
        add(revenue_output.get(key))
    for d in revenue_output.get("drivers", []):
        add(d.get("contribution_amt"))
        add(d.get("contribution_pct"))

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)
            else:
                add(obj)

        walk(d.get("inputs") or {})
    return allowed


def _extract_numbers(text: str) -> list[tuple[float, bool]]:
    """(value, is_thousands) for every numeric token in the text. Years and
    YYYYMM month ids are calendar context, not figures — skipped."""
    out: list[tuple[float, bool]] = []
    for raw in _NUMBER_RE.findall(text or ""):
        token = raw.strip()
        is_k = token.rstrip(")%").endswith("k")
        cleaned = token.strip("$()%k ").replace(",", "")
        f = _num(cleaned)
        if f is None:
            continue
        if not is_k and f == int(f) and (1990 <= f <= 2100 or 190001 <= f <= 210012):
            continue  # year / YYYYMM
        out.append((f * 1000 if is_k else f, is_k))
    return out


def _matches(value: float, allowed: set[float], is_k: bool) -> bool:
    tolerance = 55.0 if is_k else 1.01  # k-form rounds to $100s; plain to whole dollars (round or truncate)
    return any(abs(abs(value) - a) <= tolerance for a in allowed)


def validate_commentary(
    revenue_output: dict,
    commentary: dict,
    evidence_driver_ids: set[str],
) -> dict:
    """Run all five checks. Returns {passed, blocked_reason, checks:[...]}."""
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    # 1. No invented figures.
    allowed = _collect_allowed(revenue_output)
    texts = [commentary.get("narrative_text") or "", commentary.get("headline") or ""]
    texts += [f"{b.get('title') or ''} {b.get('text') or ''}" for b in commentary.get("bullets", [])]
    orphans = []
    for text in texts:
        for value, is_k in _extract_numbers(text):
            if not _matches(value, allowed, is_k):
                orphans.append(f"{value:g}{'k-form' if is_k else ''}")
    check("no_invented_figures", not orphans,
          "every figure traces to a computed driver value" if not orphans
          else f"figures not present in the driver set: {sorted(set(orphans))[:8]}")

    # 2. Reconciliation.
    reconciled = bool(revenue_output.get("reconciled"))
    residual = _num(revenue_output.get("residual")) or 0.0
    check("reconciliation", reconciled and abs(residual) <= RECONCILE_TOLERANCE,
          f"sum(contributions) vs change_amt residual = ${residual:,.2f} (tolerance ${RECONCILE_TOLERANCE:,.2f})")

    # 3. Evidence completeness.
    cited = {b.get("driver_id") for b in commentary.get("bullets", []) if b.get("driver_id")}
    missing = sorted(d for d in cited if d not in evidence_driver_ids)
    check("evidence_completeness", not missing,
          "every cited driver has a complete evidence record" if not missing
          else f"drivers cited without evidence: {missing[:5]}")

    # 4. Provenance honesty.
    driver_sources = {d.get("driver_id"): d.get("data_source") for d in revenue_output.get("drivers", [])}
    dishonest = [
        b.get("driver_id") for b in commentary.get("bullets", [])
        if driver_sources.get(b.get("driver_id")) in ("DUMMY", "ASSUMED")
        and b.get("data_source") not in ("DUMMY", "ASSUMED")
    ]
    check("provenance_honesty", not dishonest,
          "DUMMY/ASSUMED drivers are flagged as such" if not dishonest
          else f"bullets present DUMMY/ASSUMED figures as fact: {dishonest[:5]}")

    # 5. Format: negatives parenthesised, no minus signs on figures.
    minus_hits = [t[:40] for t in texts if _MINUS_FIGURE_RE.search(t)]
    check("negative_format", not minus_hits,
          "negatives parenthesised" if not minus_hits
          else f"minus sign used on a figure: {minus_hits[:3]}")

    failed = [c for c in checks if not c["passed"]]
    return {
        "passed": not failed,
        "blocked_reason": "; ".join(f"{c['check']}: {c['detail']}" for c in failed) or None,
        "checks": checks,
    }
