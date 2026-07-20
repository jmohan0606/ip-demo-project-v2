from __future__ import annotations

import logging
from collections import defaultdict

from app.graph.client import get_graph_client
from app.graph.queries.common import (
    advisor_transactions,
    resolve_scope_advisor_ids_graph,
    run_catalog_query,
)

logger = logging.getLogger(__name__)

# Wide DATETIME bounds for GQ-051 (the GSQL parameters are required; these cover
# the full data range so "no filter" behaves identically on tier 2 and tier 4).
_DATE_MIN = "1900-01-01 00:00:00"
_DATE_MAX = "2100-01-01 00:00:00"

# one drill-down level: child scope type + parent->child edge + child vertex +
# its name attr (same hierarchy the scope rollup uses).
_CHILDREN = {
    "FIRM": ("Division", "phx_dm_division_in_firm", "phx_dm_division", "division_name"),
    "DIVISION": ("Region", "phx_dm_region_in_division", "phx_dm_region", "region_name"),
    "REGION": ("Market", "phx_dm_market_in_region", "phx_dm_market", "market_name"),
    "MARKET": ("Advisor", "phx_dm_advisor_in_market", "phx_dm_advisor", "advisor_name"),
}


def _shift_month(ym: str, delta_months: int) -> str:
    """Shift a 'YYYY-MM' string by delta_months (can be negative)."""
    y, m = int(ym[:4]), int(ym[5:7])
    idx = (y * 12 + (m - 1)) + delta_months
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


class RevenueAnalyticsService:
    """Revenue intelligence for a hierarchy scope, computed from the REAL revenue
    transactions in the graph (phx_dm_revenue_transaction -> advisor). Trend,
    channel mix, business-line mix, geographic (by-state) distribution and the
    per-child scope breakdown are all Σ revenue_amount over the scope's resolved
    advisors — no synthetic series. Every dimension links back to real edges:
      channel        = revenue_transaction.transaction_type
      business line  = transaction_for_product -> product_in_subcategory -> subcategory_in_category
      geography      = advisor_in_branch -> branch.state
      scope children = the same hierarchy edges the scope rollup uses
    """

    def __init__(self) -> None:
        self._graph = get_graph_client()
        self._store = self._graph.store  # logged fallback path only — reads go via run_query
        self._tx_product: dict[str, str] = {}  # tx_id -> product_id, filled from GQ-051 rows
        self._cat_by_product = self._load_product_category_map()

    # ---- lookups -----------------------------------------------------------
    def _name(self, vtype: str, vid: str, attr: str) -> str:
        return str((self._store.vertex(vtype, vid) or {}).get(attr) or vid)

    @staticmethod
    def _rev(attrs: dict) -> float:
        return float(attrs.get("revenue_amount") or 0.0)

    def _load_product_category_map(self) -> dict[str, str]:
        """product_id -> business-line category_name via GQ-052 get_product_category_map
        (real graph in real mode); local-store traversal only as the logged fallback."""
        results = run_catalog_query(self._graph, "get_product_category_map", {})
        if results is not None:
            for entry in results:
                products = entry.get("products")
                if products is not None:
                    return {
                        str(p.get("v_id")): str(p.get("attributes", {}).get("category_name") or "Unclassified")
                        for p in products
                    }
        logger.warning("get_product_category_map unavailable — building product map from local store traversal")
        return self._build_product_category_map()

    def _scope_tx_rows(self, scope_type: str, scope_id: str, advisor_ids: list[str]) -> dict[str, list[tuple[str, dict]]]:
        """advisor_id -> [(tx_id, attrs)] for the whole scope via GQ-051
        get_scope_transactions; per-advisor store traversal only as the logged
        fallback. Also fills the tx->product map used for business-line classing."""
        results = run_catalog_query(
            self._graph,
            "get_scope_transactions",
            {"scope_type": scope_type, "scope_id": str(scope_id),
             "start_date": _DATE_MIN, "end_date": _DATE_MAX},
        )
        if results is not None:
            for entry in results:
                txs = entry.get("transactions")
                if txs is not None:
                    adv_rows: dict[str, list[tuple[str, dict]]] = {aid: [] for aid in advisor_ids}
                    for row in txs:
                        attrs = row.get("attributes", {})
                        aid = str(attrs.get("advisor_id") or "")
                        tx_id = str(row.get("v_id"))
                        self._tx_product[tx_id] = str(attrs.get("product_id") or "")
                        adv_rows.setdefault(aid, []).append((tx_id, attrs))
                    return adv_rows
        logger.warning(
            "get_scope_transactions unavailable for %s/%s — falling back to local store traversal",
            scope_type, scope_id,
        )
        return {aid: advisor_transactions(self._store, [aid]) for aid in advisor_ids}

    def _scope_placements(self, scope_type: str, scope_id: str) -> dict[str, dict] | None:
        """advisor_id -> placement attributes (branch/market/region/division ids,
        names, branch_state) via GQ-053; None signals the caller to use the logged
        store-traversal fallback."""
        results = run_catalog_query(
            self._graph,
            "get_scope_advisor_placements",
            {"scope_type": scope_type, "scope_id": str(scope_id)},
        )
        if results is not None:
            for entry in results:
                placements = entry.get("advisor_placements")
                if placements is not None:
                    return {str(p.get("v_id")): p.get("attributes", {}) for p in placements}
        logger.warning(
            "get_scope_advisor_placements unavailable for %s/%s — falling back to local store traversal",
            scope_type, scope_id,
        )
        return None

    def _build_product_category_map(self) -> dict[str, str]:
        """product_id -> business-line category_name, resolved once via
        product_in_subcategory -> subcategory_in_category (64 products)."""
        s = self._store
        cats = s.all_vertices("phx_dm_product_category")
        out: dict[str, str] = {}
        for pid in s.all_vertices("phx_dm_product"):
            name = "Unclassified"
            for sub in s.out_ids("phx_dm_product_in_subcategory", pid):
                for cat in s.out_ids("phx_dm_subcategory_in_category", sub):
                    name = str((cats.get(cat) or {}).get("category_name") or cat)
                    break
                break
            out[pid] = name
        return out

    def _tx_category(self, tx_id: str, attrs: dict | None = None) -> str:
        if tx_id in self._tx_product:  # populated from GQ-051 rows
            pid = self._tx_product[tx_id]
            if pid:
                return self._cat_by_product.get(pid, "Unclassified")
        else:  # fallback rows (store traversal) — resolve the product edge locally
            for pid in self._store.out_ids("phx_dm_transaction_for_product", tx_id):
                return self._cat_by_product.get(pid, "Unclassified")
        # §13.2 impact-ledger transactions carry no product edge — they are the measured
        # consequence of completed recommendations. Label them as what they are.
        if attrs is None:
            attrs = self._store.vertex("phx_dm_revenue_transaction", tx_id) or {}
        if str(attrs.get("transaction_type") or "") == "RECOMMENDATION_IMPACT":
            return "AI-Recommended Actions"
        return "Unclassified"

    # ---- period filtering --------------------------------------------------
    @staticmethod
    def _current_months(all_months: list[str], period: str) -> set[str]:
        """The set of 'YYYY-MM' months included by the Time Period dropdown,
        anchored to the most recent transaction month. LTM = trailing 12."""
        months = sorted({m for m in all_months if m and m != "None"})
        if not months:
            return set()
        ref = months[-1]
        ry, rm = int(ref[:4]), int(ref[5:7])
        p = (period or "ALL").upper()
        if p in ("ALL", "ALLTIME", ""):
            return set(months)
        if p == "MTD":
            return {ref}
        if p == "QTD":
            q = (rm - 1) // 3
            return {m for m in months if int(m[:4]) == ry and ((int(m[5:7]) - 1) // 3) == q}
        if p == "YTD":
            return {m for m in months if int(m[:4]) == ry}
        # LTM: trailing 12 calendar months present in data
        return set(months[-12:])

    # ---- main --------------------------------------------------------------
    def analytics(self, scope_type: str = "FIRM", scope_id: str = "F001", period: str = "ALL") -> dict:
        st = (scope_type or "FIRM").upper()
        advisor_ids = resolve_scope_advisor_ids_graph(self._graph, st, scope_id)

        # single scope-wide query -> keeps advisor identity for the geo map
        adv_rows = self._scope_tx_rows(st, scope_id, advisor_ids)
        placements = self._scope_placements(st, scope_id)
        all_rows = [(tx, a) for rows in adv_rows.values() for tx, a in rows]
        all_months = [str(a.get("transaction_date"))[:7] for _, a in all_rows]

        cur_months = self._current_months(all_months, period)
        prior_months = {_shift_month(m, -12) for m in cur_months}
        # YoY is only honest when every current month has a real prior-year month in the
        # data. ALL (36mo) shifts partly off the start of the series, so its delta is
        # suppressed; MTD/QTD/YTD/LTM stay fully covered.
        data_months = {m for m in all_months if m and m != "None"}
        prior_fully_covered = bool(cur_months) and prior_months.issubset(data_months)

        # Prior *period* (Compare-To = "Prior Period"): the equal-length contiguous
        # window of months immediately preceding the current window. Distinct from the
        # prior-*year* window above.
        sorted_data_months = sorted(data_months)
        prior_period_months: set[str] = set()
        if cur_months:
            earliest_cur = min(cur_months)
            before = [m for m in sorted_data_months if m < earliest_cur]
            prior_period_months = set(before[-len(cur_months):]) if before else set()
        prior_period_covered = len(prior_period_months) == len(cur_months) and bool(prior_period_months)

        def in_cur(a: dict) -> bool:
            return str(a.get("transaction_date"))[:7] in cur_months

        by_month: dict[str, float] = defaultdict(float)
        by_month_prior: dict[str, float] = defaultdict(float)  # prior-year months, keyed by prior month
        by_type: dict[str, float] = defaultdict(float)
        by_line: dict[str, float] = defaultdict(float)
        by_line_prior: dict[str, float] = defaultdict(float)  # same category, prior-year window
        total = 0.0
        kept_count = 0
        prior_total = 0.0
        prior_period_total = 0.0
        for tx, a in all_rows:
            month = str(a.get("transaction_date"))[:7]
            rev = self._rev(a)
            if month in prior_period_months:
                prior_period_total += rev
            if month in prior_months:
                prior_total += rev
                by_month_prior[month] += rev
                by_line_prior[self._tx_category(tx, a)] += rev
            if month not in cur_months:
                continue
            kept_count += 1
            total += rev
            by_month[month] += rev
            by_type[str(a.get("transaction_type") or "OTHER")] += rev
            by_line[self._tx_category(tx, a)] += rev

        monthly_trend = [{"month": m, "revenue": round(v, 2)} for m, v in sorted(by_month.items())]
        # Prior-year comparison line for the trend chart (mockup: solid current + dashed
        # Prior Year). Each current month is paired with its real month-shifted-−12 value;
        # only emitted when the prior window is fully covered (same honesty rule as YoY).
        monthly_trend_prior = (
            [
                {"month": m, "revenue": round(by_month_prior.get(_shift_month(m, -12), 0.0), 2)}
                for m, _ in sorted(by_month.items())
            ]
            if prior_fully_covered else []
        )
        by_channel = sorted(
            ({"channel": t, "revenue": round(v, 2)} for t, v in by_type.items()),
            key=lambda r: r["revenue"], reverse=True,
        )
        by_business_line = sorted(
            ({"category": c, "revenue": round(v, 2)} for c, v in by_line.items()),
            key=lambda r: r["revenue"], reverse=True,
        )

        # Revenue drivers vs prior year (12.1): per business-line current vs prior-window
        # revenue and the $ change — ranked by absolute contribution to the YoY swing so
        # the biggest movers (up or down) surface first. Only honest when the prior-year
        # window is fully present in the data (same rule as the headline YoY).
        revenue_drivers = []
        if prior_fully_covered:
            for cat in set(by_line) | set(by_line_prior):
                cur_v = round(by_line.get(cat, 0.0), 2)
                pri_v = round(by_line_prior.get(cat, 0.0), 2)
                revenue_drivers.append({
                    "category": cat,
                    "revenue": cur_v,
                    "prior_revenue": pri_v,
                    "change": round(cur_v - pri_v, 2),
                    "change_pct": round((cur_v - pri_v) / pri_v * 100, 1) if pri_v else None,
                })
            revenue_drivers.sort(key=lambda r: abs(r["change"]), reverse=True)

        # geographic distribution: advisor -> branch.state (GQ-053 placements;
        # store traversal only on the logged fallback path)
        state_rev: dict[str, float] = defaultdict(float)
        state_adv: dict[str, set[str]] = defaultdict(set)
        for aid, rows in adv_rows.items():
            if placements is not None:
                state = (placements.get(aid) or {}).get("branch_state") or None
            else:
                state = None
                for bid in self._store.out_ids("phx_dm_advisor_in_branch", aid):
                    state = (self._store.vertex("phx_dm_branch", bid) or {}).get("state")
                    if state:
                        break
            if not state:
                continue
            adv_rev = sum(self._rev(a) for _, a in rows if in_cur(a))
            if adv_rev:
                state_rev[state] += adv_rev
                state_adv[state].add(aid)
        by_geography = sorted(
            (
                {"state": st_, "revenue": round(v, 2), "advisor_count": len(state_adv[st_])}
                for st_, v in state_rev.items()
            ),
            key=lambda r: r["revenue"], reverse=True,
        )

        # per-child revenue (transactions summed under each immediate child scope)
        by_child = []
        if st != "ADVISOR" and st in _CHILDREN:
            child_type, edge, child_vtype, name_attr = _CHILDREN[st]
            if placements is not None:
                # group the scope's advisors (and their already-fetched rows) by the
                # immediate child scope each advisor is placed under (GQ-053)
                child_key = {"FIRM": "division", "DIVISION": "region", "REGION": "market"}.get(st)
                groups: dict[str, dict] = {}
                for aid in advisor_ids:
                    p = placements.get(aid) or {}
                    if child_key is None:  # MARKET -> children are the advisors themselves
                        cid, label = aid, str(p.get("advisor_name") or aid)
                    else:
                        cid = str(p.get(f"{child_key}_id") or "")
                        label = str(p.get(f"{child_key}_name") or cid)
                    if not cid:
                        continue
                    g = groups.setdefault(cid, {"label": label, "advisors": [], "revenue": 0.0})
                    g["advisors"].append(aid)
                    g["revenue"] += sum(self._rev(a) for _, a in adv_rows.get(aid, []) if in_cur(a))
                for cid in sorted(groups):
                    g = groups[cid]
                    by_child.append({
                        "scope_type": child_type,
                        "scope_id": cid,
                        "label": g["label"],
                        "revenue": round(g["revenue"], 2),
                        "advisor_count": len(g["advisors"]),
                    })
            else:  # logged fallback: local store traversal (placements warning already emitted)
                for child_id in sorted(self._store.in_ids(edge, scope_id)):
                    child_ids = resolve_scope_advisor_ids_graph(self._graph, child_type, child_id)
                    child_rev = sum(
                        self._rev(attrs)
                        for _, attrs in advisor_transactions(self._store, child_ids)
                        if in_cur(attrs)
                    )
                    by_child.append({
                        "scope_type": child_type,
                        "scope_id": child_id,
                        "label": self._name(child_vtype, child_id, name_attr),
                        "revenue": round(child_rev, 2),
                        "advisor_count": len(child_ids),
                    })
            by_child.sort(key=lambda r: r["revenue"], reverse=True)

        top_channel = by_channel[0]["channel"] if by_channel else None
        top_line = by_business_line[0]["category"] if by_business_line else None
        change_pct = (
            round((total - prior_total) / prior_total * 100, 1)
            if (prior_fully_covered and prior_total > 0)
            else None
        )
        return {
            "scope_type": st,
            "scope_id": scope_id,
            "kpis": {
                "total_revenue": round(total, 2),
                "transaction_count": kept_count,
                "advisor_count": len(advisor_ids),
                "avg_revenue_per_advisor": round(total / len(advisor_ids), 2) if advisor_ids else 0.0,
                "months_covered": len(monthly_trend),
                "top_channel": top_channel,
                "top_business_line": top_line,
                "period": (period or "ALL").upper(),
            },
            "comparison": {
                "prior_revenue": round(prior_total, 2) if prior_fully_covered else None,
                "change_pct": change_pct,
                "basis": "same period, prior year (months shifted -12)",
            },
            "comparison_prior_period": {
                "prior_revenue": round(prior_period_total, 2) if prior_period_covered else None,
                "change_pct": (
                    round((total - prior_period_total) / prior_period_total * 100, 1)
                    if (prior_period_covered and prior_period_total > 0) else None
                ),
                "basis": "immediately preceding equal-length period",
            },
            "monthly_trend": monthly_trend,
            "monthly_trend_prior": monthly_trend_prior,
            "by_channel": by_channel,
            "by_business_line": by_business_line,
            "revenue_drivers": revenue_drivers,
            "by_geography": by_geography,
            "by_child": by_child,
            "evidence": {
                "source": "phx_dm_revenue_transaction vertices via transaction_for_advisor edges",
                "advisor_ids_resolved": len(advisor_ids),
                "computation": (
                    "Σ revenue_amount grouped by month / transaction_type (channel) / "
                    "product→subcategory→category (business line) / advisor→branch.state (geography) / child scope"
                ),
            },
        }
