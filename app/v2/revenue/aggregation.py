"""Monthly aggregation and MoM change (EXTRACTION_SPEC §6).

Pure deterministic Python over transaction dicts — no LLM anywhere near these
numbers (ABSOLUTE RULE 1). Transactions carry: advisor_sid, month_id,
product_id, account_no, credited_amt, client_rate_bps, discount_amt,
concession_type, rev_nature, file_key.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

TOTAL_GROUP = "__TOTAL__"

# rev_nature values (derived at extraction per EXTRACTION_SPEC §4)
RECURRING = "RECURRING"
ONE_TIME = "ONE_TIME"
ADJUSTMENT = "ADJUSTMENT"

FLAT_TOLERANCE = 0.005

# file_key -> nature (EXTRACTION_SPEC §4). trade_description prefixes override.
ONE_TIME_FILE_KEYS = {"twhs", "l_a_ancomm", "pb_rfrrl", "refrl_401k", "sitn_ptnr"}
RECURRING_FILE_KEYS = {"ace", "mf_12b1", "l_a_btr", "529_trails", "money_mkt",
                       "prem_dep", "sbl_prcing", "mrgn_lend"}


def derive_rev_nature(file_key: str, trade_description: str) -> str:
    """rev_nature is derived, not sourced (EXTRACTION_SPEC §4)."""
    desc = (trade_description or "").upper()
    if desc.startswith("ADJUSTMENT") or file_key == "manual_adj":
        return ADJUSTMENT
    if file_key in ONE_TIME_FILE_KEYS or desc.startswith("ANNUITY ISSUED"):
        return ONE_TIME
    return RECURRING


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def aggregate_monthly(
    transactions: Iterable[dict],
    product_group: dict[str, str],
    group_line: dict[str, str],
    line_class: dict[str, str],
) -> list[dict]:
    """Group transactions by (advisor, month, product group) into
    monthly_product_revenue rows. recurring_amt = rev_nature RECURRING;
    one_time_amt = ONE_TIME + ADJUSTMENT (so the split always sums to revenue).
    avg_rate_bps is revenue-weighted."""
    buckets: dict[tuple, dict] = {}
    for t in transactions:
        group_id = product_group.get(str(t.get("product_id")))
        if group_id is None:
            continue
        key = (str(t["advisor_sid"]), str(t["month_id"]), group_id)
        b = buckets.setdefault(key, {
            "revenue": 0.0, "txn_count": 0, "accounts": set(),
            "rate_weight": 0.0, "rate_base": 0.0,
            "recurring_amt": 0.0, "one_time_amt": 0.0,
        })
        amt = _num(t.get("credited_amt"))
        b["revenue"] += amt
        b["txn_count"] += 1
        b["accounts"].add(str(t.get("account_no")))
        rate = _num(t.get("client_rate_bps"))
        if rate > 0 and amt > 0:
            b["rate_weight"] += rate * amt
            b["rate_base"] += amt
        if t.get("rev_nature") == RECURRING:
            b["recurring_amt"] += amt
        else:
            b["one_time_amt"] += amt

    rows = []
    for (advisor_sid, month_id, group_id), b in sorted(buckets.items()):
        line_id = group_line.get(group_id, "")
        rows.append({
            "mpr_id": f"{advisor_sid}|{month_id}|{group_id}",
            "advisor_sid": advisor_sid,
            "month_id": month_id,
            "group_id": group_id,
            "line_id": line_id,
            "class_id": line_class.get(line_id, ""),
            "revenue": round(b["revenue"], 2),
            "txn_count": b["txn_count"],
            "account_count": len(b["accounts"]),
            "avg_rate_bps": round(b["rate_weight"] / b["rate_base"], 4) if b["rate_base"] else 0.0,
            "recurring_amt": round(b["recurring_amt"], 2),
            "one_time_amt": round(b["one_time_amt"], 2),
            "data_source": "DERIVED",
        })
    return rows


def compute_changes(mpr_rows: Iterable[dict], month_ids: list[str]) -> list[dict]:
    """revenue_change rows for each (advisor, consecutive month pair, group),
    plus a __TOTAL__ row per transition. change_pct is 0.0 when from_revenue is 0
    — the UI derives 'n/a' from from_revenue == 0, never a division."""
    ordered = sorted(month_ids)
    by_advisor_month: dict[tuple, dict[str, float]] = defaultdict(dict)
    for r in mpr_rows:
        by_advisor_month[(r["advisor_sid"], r["month_id"])][r["group_id"]] = _num(r["revenue"])

    advisors = sorted({adv for adv, _ in by_advisor_month})
    changes = []
    for advisor in advisors:
        for from_m, to_m in zip(ordered, ordered[1:]):
            from_rev = by_advisor_month.get((advisor, from_m), {})
            to_rev = by_advisor_month.get((advisor, to_m), {})
            groups = sorted(set(from_rev) | set(to_rev))
            if not groups:
                continue
            for group_id in groups + [TOTAL_GROUP]:
                if group_id == TOTAL_GROUP:
                    f = round(sum(from_rev.values()), 2)
                    t = round(sum(to_rev.values()), 2)
                else:
                    f = round(from_rev.get(group_id, 0.0), 2)
                    t = round(to_rev.get(group_id, 0.0), 2)
                change = round(t - f, 2)
                changes.append({
                    "change_id": f"{advisor}|{from_m}|{to_m}|{group_id}",
                    "advisor_sid": advisor,
                    "from_month_id": from_m,
                    "to_month_id": to_m,
                    "group_id": group_id,
                    "from_revenue": f,
                    "to_revenue": t,
                    "change_amt": change,
                    "change_pct": round(change / f * 100, 2) if f else 0.0,
                    "direction": "FLAT" if abs(change) < FLAT_TOLERANCE else ("UP" if change > 0 else "DOWN"),
                    "data_source": "DERIVED",
                })
    return changes
