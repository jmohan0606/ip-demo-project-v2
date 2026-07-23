"""Per-intent answer builders for Ask iPerform (FIX_SPEC_R7 §0, A3, A6-A8).

EVERYTHING here is deterministic arrangement of figures returned by catalogued
queries — the same audited queries the rest of the app uses. No builder ever
computes, estimates or infers a figure: values are read from stored rows
(REAL/DERIVED provenance travels with each one), selection/ordering/filtering
is presentation. The ONLY new numbers ever shown are the stored ones.

Each builder returns an AnswerData:
    facts            what the narrator may word (raw + formatted figures)
    figures          [{label, value, formatted, source_query, provenance}] —
                     persisted as figures_json; the no-invented-figures
                     guardrail validates the narrative against THIS list
    text             the deterministic wording (also the guardrail fallback)
    queries_run      [{query, params, rows}] — the visible audit trail
    suggestions      follow-ups derived from the resolved context (never invented)
    links            deep links carrying the resolved parameters
    status           OK | NO_DATA
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.v2.assistant.context import ResolvedContext
from app.v2.format import fmt_money, fmt_pct

TOTAL_GROUP = "__TOTAL__"


@dataclass
class AnswerData:
    facts: dict = field(default_factory=dict)
    figures: list[dict] = field(default_factory=list)
    text: str = ""
    queries_run: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    evidence_driver_id: str = ""
    status: str = "OK"
    no_data_reason: str = ""
    verbatim_stored: bool = False    # stored, already-validated model text (commentary)


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class AnswerEngine:
    """Runs catalogued queries through the active GraphClient and arranges the
    results per intent. `ref_bundle` carries loaded reference data + display
    names resolved by the service."""

    def __init__(self, graph, ref_bundle: dict) -> None:
        self.graph = graph
        self.months: list[str] = ref_bundle["month_ids"]
        self.month_names: dict[str, str] = ref_bundle["month_names"]      # 202606 -> "June 2026"
        self.advisor_names: dict[str, str] = ref_bundle["advisor_names"]
        self.group_names: dict[str, str] = ref_bundle["group_names"]
        self.cause_names: dict[str, str] = ref_bundle["cause_names"]
        self.served_by_tier: int | None = None

    # ------------------------------------------------------------ plumbing

    def _run(self, out: AnswerData, name: str, params: dict, key: str) -> list[dict]:
        from app.graph.queries.common import v2_served_by_tier

        result = self.graph.run_query(name, params)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"{name} returned an error envelope")
        self.served_by_tier = v2_served_by_tier(result)
        rows: list[dict] = []
        maps: dict = {}
        for obj in result.get("results", []):
            if key and key in obj:
                rows = [r.get("attributes", {}) for r in obj[key]]
            elif not key and isinstance(obj, dict):
                maps.update(obj)
        out.queries_run.append({"query": name, "params": params,
                                "rows": len(rows) if key else len(maps)})
        return rows if key else [maps]

    def _fig(self, out: AnswerData, label: str, value: float, formatted: str,
             source_query: str, provenance: str = "DERIVED") -> None:
        out.figures.append({"label": label, "value": value, "formatted": formatted,
                            "source_query": source_query, "provenance": provenance})

    def _mname(self, month_id: str) -> str:
        return self.month_names.get(month_id, month_id)

    def _aname(self, sid: str) -> str:
        name = self.advisor_names.get(sid, "")
        return f"{sid} · {name}" if name else sid

    def _gname(self, gid: str) -> str:
        if gid == TOTAL_GROUP:
            return "Total"
        return self.group_names.get(gid, gid.replace("_", " ").title())

    def _total_change_row(self, out: AnswerData, advisor: str, from_m: str, to_m: str) -> dict | None:
        rows = self._run(out, "get_revenue_changes",
                         {"advisor_id": advisor, "from_month": from_m, "to_month": to_m},
                         "changes")
        return next((r for r in rows
                     if str(r.get("group_id")) == TOTAL_GROUP
                     and str(r.get("from_month_id")) == from_m
                     and str(r.get("to_month_id")) == to_m), None)

    # ------------------------------------------------------------ intents

    def build(self, intent: str, ctx: ResolvedContext, *, question: str = "",
              reference_term: str = "", compare_sids: list[str] | None = None) -> AnswerData:
        builder = {
            "REVENUE_TREND": self.revenue_trend,
            "REVENUE_BY_PRODUCT": self.revenue_by_product,
            "MOM_CHANGE": self.mom_change,
            "WHY_CHANGE": self.why_change,
            "DRIVER_DETAIL": self.driver_detail,
            "TRANSACTIONS": self.transactions,
            "COMPARE_ADVISORS": self.compare_advisors,
            "ANOMALIES": self.anomalies,
            "COMMENTARY": self.commentary,
            "REFERENCE": self.reference,
        }[intent]
        if intent == "TRANSACTIONS":
            return builder(ctx, question=question)
        if intent == "COMPARE_ADVISORS":
            return builder(ctx, compare_sids=compare_sids or [])
        if intent == "REFERENCE":
            return builder(ctx, term=reference_term)
        return builder(ctx)

    def revenue_trend(self, ctx: ResolvedContext) -> AnswerData:
        out = AnswerData()
        sids = [ctx.advisor_sid] if ctx.advisor_sid else sorted(self.advisor_names)
        month = ctx.to_month
        lines = []
        for sid in sids:
            maps = self._run(out, "get_monthly_revenue_totals",
                             {"advisor_id": sid, "from_month": self.months[0],
                              "to_month": self.months[-1]}, "")[0]
            revenue = maps.get("revenue_by_month", {})
            if month not in revenue:
                continue
            value = _num(revenue[month])
            self._fig(out, f"{self._aname(sid)} — {self._mname(month)} credited revenue",
                      value, fmt_money(value), "get_monthly_revenue_totals")
            lines.append(f"{self._aname(sid)}: {fmt_money(value)}")
            if ctx.advisor_sid:
                # single-advisor: show the whole loaded trend, month by month
                for m in self.months:
                    if m == month or m not in revenue:
                        continue
                    v = _num(revenue[m])
                    self._fig(out, f"{self._mname(m)} credited revenue", v,
                              fmt_money(v), "get_monthly_revenue_totals")
        if not out.figures:
            out.status, out.no_data_reason = "NO_DATA", "no revenue rows for that scope"
            return out
        if ctx.advisor_sid:
            trend = " · ".join(f"{self._mname(m)} {f['formatted']}"
                               for m in self.months
                               for f in out.figures if f["label"].startswith(self._mname(m)))
            out.text = (f"{self._aname(ctx.advisor_sid)} credited revenue for "
                        f"{self._mname(month)} was {out.figures[0]['formatted']}."
                        + (f" Loaded months: {trend}." if trend else ""))
        else:
            out.text = (f"{self._mname(month)} credited revenue by advisor: "
                        + "; ".join(lines) + ".")
        out.suggestions = [f"How much did revenue change in {self._mname(month).split()[0]}?",
                           "Revenue by product for that month", "Anything unusual this month?"]
        return out

    def revenue_by_product(self, ctx: ResolvedContext) -> AnswerData:
        out = AnswerData()
        if not ctx.advisor_sid:
            out.status = "NO_DATA"
            out.no_data_reason = "product breakdowns are per advisor — name an advisor"
            out.text = ("I can break revenue down by product for one advisor at a time — "
                        "tell me which advisor.")
            return out
        month = ctx.to_month
        rows = self._run(out, "get_monthly_revenue_by_product",
                         {"advisor_id": ctx.advisor_sid, "from_month": month,
                          "to_month": month}, "monthly_revenue")
        rows = sorted(rows, key=lambda r: -abs(_num(r.get("revenue"))))
        if not rows:
            out.status, out.no_data_reason = "NO_DATA", f"no product rows for {month}"
            return out
        parts = []
        for r in rows[:8]:
            gid = str(r.get("group_id"))
            v = _num(r.get("revenue"))
            self._fig(out, f"{self._gname(gid)} — {self._mname(month)}", v, fmt_money(v),
                      "get_monthly_revenue_by_product", str(r.get("data_source") or "DERIVED"))
            parts.append(f"{self._gname(gid)} {fmt_money(v)}")
        out.text = (f"{self._aname(ctx.advisor_sid)} — {self._mname(month)} credited revenue "
                    f"by product group: " + "; ".join(parts) + ".")
        out.suggestions = ["Why did revenue change?", "Which accounts drove it?"]
        return out

    def mom_change(self, ctx: ResolvedContext) -> AnswerData:
        if not ctx.advisor_sid:
            return self.compare_advisors(ctx, compare_sids=[])
        out = AnswerData()
        total = self._total_change_row(out, ctx.advisor_sid, ctx.from_month, ctx.to_month)
        if total is None:
            out.status = "NO_DATA"
            out.no_data_reason = (f"no stored change row for "
                                  f"{ctx.from_month}->{ctx.to_month}")
            return out
        src = str(total.get("data_source") or "DERIVED")
        amt, pct = _num(total.get("change_amt")), _num(total.get("change_pct"))
        frm, to = _num(total.get("from_revenue")), _num(total.get("to_revenue"))
        q = "get_revenue_changes"
        self._fig(out, f"Change {self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}",
                  amt, fmt_money(amt), q, src)
        self._fig(out, "Change %", pct, fmt_pct(pct), q, src)
        self._fig(out, f"{self._mname(ctx.from_month)} revenue", frm, fmt_money(frm), q, src)
        self._fig(out, f"{self._mname(ctx.to_month)} revenue", to, fmt_money(to), q, src)
        # direction verb + magnitude ("fell $90,685 (17.7%)", mockup style) —
        # the sign lives in the verb; the figures list keeps the parenthesised
        # negative forms.
        verb = "fell" if amt < 0 else "rose"
        out.text = (f"{self._aname(ctx.advisor_sid)} credited revenue {verb} "
                    f"{fmt_money(abs(amt))} ({fmt_pct(abs(pct))}) from {self._mname(ctx.from_month)} "
                    f"({fmt_money(frm)}) to {self._mname(ctx.to_month)} ({fmt_money(to)}).")
        out.suggestions = [f"Why did it {'drop' if amt < 0 else 'increase'}?",
                           "Which accounts drove it?", "Anything unusual this month?"]
        return out

    def why_change(self, ctx: ResolvedContext) -> AnswerData:
        if not ctx.advisor_sid:
            return self.compare_advisors(ctx, compare_sids=[])
        out = AnswerData()
        total = self._total_change_row(out, ctx.advisor_sid, ctx.from_month, ctx.to_month)
        if total is None:
            out.status = "NO_DATA"
            out.no_data_reason = f"no stored change row for {ctx.from_month}->{ctx.to_month}"
            return out
        q = "get_revenue_changes"
        src = str(total.get("data_source") or "DERIVED")
        amt, pct = _num(total.get("change_amt")), _num(total.get("change_pct"))
        self._fig(out, f"Total change {self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}",
                  amt, fmt_money(amt), q, src)
        self._fig(out, "Total change %", pct, fmt_pct(pct), q, src)
        drivers = self._run(out, "get_change_drivers",
                            {"advisor_id": ctx.advisor_sid, "from_month": ctx.from_month,
                             "to_month": ctx.to_month, "result_limit": 100}, "drivers")
        named = [d for d in drivers if str(d.get("cause_id")) != "MIX"]
        top = sorted(named, key=lambda d: -abs(_num(d.get("contribution_amt"))))[:4]
        parts = []
        for d in top:
            c = _num(d.get("contribution_amt"))
            label = self._gname(str(d.get("group_id") or TOTAL_GROUP))
            cause = self.cause_names.get(str(d.get("cause_id")), str(d.get("cause_id")))
            self._fig(out, f"{label} — {cause}", c, fmt_money(c),
                      "get_change_drivers", str(d.get("data_source") or "DERIVED"))
            parts.append(f"{label} {fmt_money(c)} ({cause})")
        if top:
            out.evidence_driver_id = str(top[0].get("driver_id") or "")
        verb = "fell" if amt < 0 else "rose"
        out.text = (f"{self._aname(ctx.advisor_sid)} credited revenue {verb} {fmt_money(abs(amt))} "
                    f"({fmt_pct(abs(pct))}) {self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}. "
                    + (f"Largest drivers: {'; '.join(parts)}." if parts
                       else "No named drivers are stored for this transition."))
        prior = self.months[self.months.index(ctx.from_month) - 1] if (
            ctx.from_month in self.months and self.months.index(ctx.from_month) > 0) else ""
        out.suggestions = ["Which accounts drove it?"]
        if prior:
            out.suggestions.append(f"What about {self._mname(ctx.from_month).split()[0]}?")
        out.suggestions.append("Anything unusual this month?")
        out.links = [{"label": "Open in AI Insights ›", "href": "/ai-insights"}]
        return out

    def driver_detail(self, ctx: ResolvedContext) -> AnswerData:
        out = AnswerData()
        if not ctx.advisor_sid:
            out.status = "NO_DATA"
            out.no_data_reason = "driver detail is per advisor — name an advisor"
            out.text = "Driver detail is per advisor — tell me which advisor."
            return out
        gname = self._gname(ctx.group_id) if ctx.group_id else "Total"
        rows = self._run(out, "get_revenue_changes",
                         {"advisor_id": ctx.advisor_sid, "from_month": ctx.from_month,
                          "to_month": ctx.to_month}, "changes")
        grp = next((r for r in rows
                    if str(r.get("group_id")) == (ctx.group_id or TOTAL_GROUP)
                    and str(r.get("from_month_id")) == ctx.from_month), None)
        drivers = self._run(out, "get_change_drivers",
                            {"advisor_id": ctx.advisor_sid, "from_month": ctx.from_month,
                             "to_month": ctx.to_month, "result_limit": 100}, "drivers")
        mine = [d for d in drivers
                if not ctx.group_id or str(d.get("group_id")) == ctx.group_id]
        mine = sorted(mine, key=lambda d: -abs(_num(d.get("contribution_amt"))))
        if grp is None and not mine:
            out.status = "NO_DATA"
            out.no_data_reason = f"nothing stored for {gname} on this transition"
            return out
        parts = []
        if grp is not None:
            v = _num(grp.get("change_amt"))
            self._fig(out, f"{gname} change {self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}",
                      v, fmt_money(v), "get_revenue_changes",
                      str(grp.get("data_source") or "DERIVED"))
        for d in mine[:4]:
            c = _num(d.get("contribution_amt"))
            cause = self.cause_names.get(str(d.get("cause_id")), str(d.get("cause_id")))
            self._fig(out, f"{gname} — {cause}", c, fmt_money(c), "get_change_drivers",
                      str(d.get("data_source") or "DERIVED"))
            parts.append(f"{cause} {fmt_money(c)}")
        finding = ""
        if mine:
            out.evidence_driver_id = str(mine[0].get("driver_id") or "")
            ev = self._run(out, "get_evidence",
                           {"driver_id": out.evidence_driver_id, "version_id": ""}, "evidence")
            if ev:
                finding = str(ev[-1].get("finding_text") or "")
        head = (f"{gname} moved {out.figures[0]['formatted']} for "
                f"{self._aname(ctx.advisor_sid)} {self._mname(ctx.from_month)}→"
                f"{self._mname(ctx.to_month)}." if grp is not None
                else f"{gname} drivers for {self._aname(ctx.advisor_sid)}:")
        out.text = head + (f" Attribution: {'; '.join(parts)}." if parts else "")
        out.facts["evidence_finding"] = finding
        out.suggestions = ["Which accounts drove it?", "Show the transactions"]
        out.links = [{"label": "Open in Transactions ›",
                      "href": f"/transactions?month={ctx.to_month}&group={ctx.group_id}"}]
        return out

    def transactions(self, ctx: ResolvedContext, question: str = "") -> AnswerData:
        out = AnswerData()
        if not ctx.advisor_sid:
            out.status = "NO_DATA"
            out.no_data_reason = "transactions are per advisor — name an advisor"
            out.text = "Transaction drill-downs are per advisor — tell me which advisor."
            return out
        rows = self._run(out, "get_transactions",
                         {"advisor_id": ctx.advisor_sid, "month_id": ctx.to_month,
                          "group_id": ctx.group_id, "result_limit": 10000}, "transactions")
        clawback_only = "clawback" in (question or "").lower()
        if clawback_only:
            rows = [r for r in rows if _num(r.get("credited_amt")) < 0]
        rows = sorted(rows, key=lambda r: -abs(_num(r.get("credited_amt"))))
        scope = self._gname(ctx.group_id) if ctx.group_id else "all product groups"
        if not rows:
            out.status = "NO_DATA"
            out.no_data_reason = (f"no {'clawback ' if clawback_only else ''}transactions "
                                  f"stored for {self._mname(ctx.to_month)} / {scope}")
            return out
        parts = []
        for r in rows[:6]:
            v = _num(r.get("credited_amt"))
            acct = str(r.get("account_no") or "")
            self._fig(out, f"Account {acct} — {str(r.get('@product_name') or '')}".strip(),
                      v, fmt_money(v), "get_transactions", str(r.get("data_source") or "REAL"))
            parts.append(f"{acct} {fmt_money(v)}")
        kind = "clawback transactions" if clawback_only else "transactions by credited amount"
        out.text = (f"Largest {kind} for {self._aname(ctx.advisor_sid)} in "
                    f"{self._mname(ctx.to_month)} ({scope}): " + "; ".join(parts)
                    + (f". {len(rows)} rows in total." if len(rows) > 6 else "."))
        self._fig(out, "Transaction count", len(rows), f"{len(rows)}", "get_transactions")
        out.links = [{"label": "Open in Transactions ›",
                      "href": f"/transactions?month={ctx.to_month}&group={ctx.group_id}"}]
        out.suggestions = ["Why did revenue change?", "Anything unusual this month?"]
        return out

    def compare_advisors(self, ctx: ResolvedContext, compare_sids: list[str]) -> AnswerData:
        out = AnswerData()
        sids = compare_sids or sorted(self.advisor_names)
        ranked: list[tuple[str, dict]] = []
        for sid in sids:
            total = self._total_change_row(out, sid, ctx.from_month, ctx.to_month)
            if total is not None:
                ranked.append((sid, total))
        if not ranked:
            out.status = "NO_DATA"
            out.no_data_reason = f"no stored change rows for {ctx.from_month}->{ctx.to_month}"
            return out
        ranked.sort(key=lambda kv: _num(kv[1].get("change_amt")))
        parts = []
        for sid, row in ranked:
            amt, pct = _num(row.get("change_amt")), _num(row.get("change_pct"))
            self._fig(out, f"{self._aname(sid)} — change", amt, fmt_money(amt),
                      "get_revenue_changes", str(row.get("data_source") or "DERIVED"))
            self._fig(out, f"{self._aname(sid)} — change %", pct, fmt_pct(pct),
                      "get_revenue_changes", str(row.get("data_source") or "DERIVED"))
            parts.append(f"{self._aname(sid)} {fmt_money(amt)} ({fmt_pct(pct)})")
        worst_sid, worst = ranked[0]
        best_sid, best = ranked[-1]
        out.facts["biggest_drop"] = self._aname(worst_sid)
        out.text = (f"{self._mname(ctx.from_month)}→{self._mname(ctx.to_month)} change by "
                    f"advisor (most negative first): " + "; ".join(parts) + ". "
                    f"Biggest drop: {self._aname(worst_sid)} "
                    f"({fmt_money(_num(worst.get('change_amt')))}); largest gain: "
                    f"{self._aname(best_sid)} ({fmt_money(_num(best.get('change_amt')))}).")
        out.suggestions = [f"Why did {worst_sid} drop?", "Anything unusual this month?"]
        return out

    def anomalies(self, ctx: ResolvedContext) -> AnswerData:
        out = AnswerData()
        rows = self._run(out, "get_anomalies",
                         {"advisor_id": ctx.advisor_sid, "scan_id": "", "severity": "",
                          "result_limit": 1000}, "anomalies")
        mine = [r for r in rows
                if str(r.get("to_month_id")) == ctx.to_month
                and str(r.get("from_month_id")) == ctx.from_month]
        scope = self._aname(ctx.advisor_sid) if ctx.advisor_sid else "all advisors"
        if not mine:
            out.text = (f"The latest stored anomaly scan flags nothing for {scope} on "
                        f"{self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}.")
            out.suggestions = ["Why did revenue change?", "Summarise this month"]
            return out
        parts = []
        for a in sorted(mine, key=lambda r: -abs(_num(r.get("impact_amt"))))[:5]:
            v = _num(a.get("impact_amt"))
            self._fig(out, f"{a.get('severity')} — {a.get('title')}", v, fmt_money(v),
                      "get_anomalies", str(a.get("data_source") or "DERIVED"))
            who = "" if ctx.advisor_sid else f" [{a.get('advisor_sid')}]"
            parts.append(f"{a.get('severity')}: {a.get('title')}{who} ({fmt_money(v)})")
        out.text = (f"Stored anomalies for {scope}, "
                    f"{self._mname(ctx.from_month)}→{self._mname(ctx.to_month)}: "
                    + "; ".join(parts) + ".")
        out.links = [{"label": "Open in Anomalies ›", "href": "/anomalies"}]
        out.suggestions = ["Why did revenue change?", "Which accounts drove it?"]
        return out

    def commentary(self, ctx: ResolvedContext) -> AnswerData:
        out = AnswerData()
        if not ctx.advisor_sid:
            out.status = "NO_DATA"
            out.no_data_reason = "stored commentary is per advisor — name an advisor"
            out.text = "Stored commentary is per advisor — tell me which advisor."
            return out
        rows = self._run(out, "get_commentary",
                         {"advisor_id": ctx.advisor_sid, "version_id": ""}, "commentaries")
        row = next((r for r in rows
                    if str(r.get("from_month_id")) == ctx.from_month
                    and str(r.get("to_month_id")) == ctx.to_month), None)
        if row is None:
            out.status = "NO_DATA"
            out.no_data_reason = ("no published commentary stored for "
                                  f"{ctx.from_month}->{ctx.to_month}")
            return out
        if str(row.get("status")) == "BLOCKED":
            out.status = "NO_DATA"
            out.no_data_reason = ("the stored commentary for this transition is BLOCKED: "
                                  + str(row.get("blocked_reason") or "validation failed"))
            out.text = (f"The stored commentary for {self._mname(ctx.from_month)}→"
                        f"{self._mname(ctx.to_month)} is blocked "
                        f"({row.get('blocked_reason') or 'validation failed'}) — "
                        "I won't paraphrase an unvalidated narrative.")
            return out
        # Verbatim retrieval of ALREADY-validated, versioned commentary
        # (generated in batch, never on read — CLAUDE.md §7). Not re-narrated,
        # so its figures were validated at publication, not here.
        out.verbatim_stored = True
        out.text = str(row.get("narrative_text") or row.get("headline") or "")
        out.facts["version_id"] = str(row.get("version_id") or "")
        out.suggestions = ["Why did revenue change?", "Which accounts drove it?",
                           "Anything unusual this month?"]
        out.links = [{"label": "Open in AI Insights ›", "href": "/ai-insights"}]
        return out

    def reference(self, ctx: ResolvedContext, term: str) -> AnswerData:
        out = AnswerData()
        causes = self._run(out, "get_driver_causes", {}, "causes")
        reasons = self._run(out, "get_reason_codes", {}, "reason_codes")
        low = (term or "").lower()
        for c in causes:
            cid, cname = str(c.get("cause_id")), str(c.get("cause_name"))
            if low and (low == cid.lower() or low in cname.lower() or cid.lower() in low
                        or cname.lower() in low):
                out.text = (f"{cname} ({cid}): "
                            f"{c.get('cause_description') or 'no description stored.'}")
                out.suggestions = ["Why did revenue change?", "What does MIX mean?"]
                return out
        for r in reasons:
            rid, rname = str(r.get("reason_cd") or r.get("code") or ""), str(r.get("reason_name") or r.get("name") or "")
            if low and rid and (low == rid.lower() or (rname and rname.lower() in low)):
                desc = r.get("reason_description") or r.get("description") or rname or "no description stored."
                out.text = f"Reason code {rid}: {desc}"
                return out
        out.status = "OUT_OF_SCOPE" if not low else "NO_DATA"
        out.no_data_reason = f"no stored definition matches '{term}'"
        out.text = (f"I don't have a stored definition for “{term}”. I can explain the "
                    "driver causes and reason codes in the loaded reference data."
                    if term else
                    "Tell me which term you'd like defined — I can explain the driver "
                    "causes and reason codes in the loaded reference data.")
        return out
