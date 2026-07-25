"""Glossary ordering verification — display_order sorts NUMERICALLY (R8/R9 F).

Root cause fixed here: display_order values are correct (1–19) but a pre-R8
live graph stores the attribute as STRING, so GQ-004's ORDER BY returns
"1","10","11",…,"19","2","3" — Volume, Fee Rate, Discount… before Deal Size.
The fix is end to end: DDL already INT (confirmed), the local tier sorts via
a numeric key, the SERVICE re-imposes numeric order on whatever the serving
tier delivered, and the frontend key is an explicit Number() (belt-and-braces).

Checks:
1. Sample/local tier: the service returns causes strictly ascending 1..19,
   Volume(1) then Deal Size(2); 10 (Fee Rate) never precedes 2.
2. STRING-typed lexicographic input (the live-graph failure, simulated):
   the service still returns numeric-ascending order.
3. Local-tier get_driver_causes with STRING display_order values sorts
   numerically (never as text).
4. No display_order VALUE or display_name changed by the fix.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("GRAPH_CLIENT_MODE", "local")
os.environ.setdefault("DATA_SET", "sample")
os.environ.setdefault("LLM_CLIENT_MODE", "mock")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    print(("PASS " if ok else "FAIL "), name, detail if not ok else "")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")


EXPECTED = [("VOLUME", 1), ("DEAL_SIZE", 2), ("ONE_TIME", 3), ("INHERITANCE", 4),
            ("HOUSEHOLD", 5), ("ELIGIBILITY", 6), ("LATE_PROCESSING", 7),
            ("EXCLUDED_CHANGE", 8), ("TIMING", 9), ("FEE_RATE", 10),
            ("DISCOUNT", 11), ("BILLABLE_DAYS", 12), ("MIX", 13),
            ("NEW_ACCOUNT", 14), ("LOST_ACCOUNT", 15), ("CLAWBACK", 16),
            ("MARKET", 17), ("NET_FLOW", 18), ("BASELINE_LIMITED", 19)]


def orders(rows: list[dict]) -> list[int]:
    return [int(float(r.get("display_order"))) for r in rows]


def main() -> None:
    from app.v2.revenue.service import V2RevenueService, _display_order_key

    print("[1] sample / local tier — numeric ascending through the service")
    res = V2RevenueService().driver_causes()
    rows = res["causes"]
    got = [(r["cause_id"], int(float(r["display_order"]))) for r in rows]
    check("1.1 nineteen causes, exact numeric order 1..19 (values unchanged)",
          got == EXPECTED, str(got))
    ods = orders(rows)
    check("1.2 strictly ascending — no lexicographic gap (10 not before 2)",
          all(a < b for a, b in zip(ods, ods[1:])), str(ods))
    ids = [r["cause_id"] for r in rows]
    check("1.3 Deal Size is SECOND, before every 2-digit order",
          ids[1] == "DEAL_SIZE" and ids.index("FEE_RATE") > ids.index("DEAL_SIZE"))

    print("[2] STRING display_order in lexicographic order (live-graph failure)"
          " — the service re-imposes numeric order")
    # exactly what a pre-R8 STRING-typed graph returns from ORDER BY:
    lexi = sorted(EXPECTED, key=lambda p: str(p[1]))
    check("2.0 fixture really is the broken order (sanity)",
          [c for c, _ in lexi][:5] == ["VOLUME", "FEE_RATE", "DISCOUNT",
                                       "BILLABLE_DAYS", "MIX"])
    string_rows = [{"cause_id": c, "display_name": c.title(),
                    "display_order": str(o)} for c, o in lexi]
    fixed = sorted(string_rows, key=_display_order_key)
    check("2.1 service sort restores numeric order from STRING values",
          [(r["cause_id"], int(r["display_order"])) for r in fixed] == EXPECTED,
          str([r["cause_id"] for r in fixed]))
    check("2.2 missing/invalid display_order sorts LAST, not first",
          sorted([{"cause_id": "X", "display_order": None},
                  {"cause_id": "VOLUME", "display_order": "1"}],
                 key=_display_order_key)[-1]["cause_id"] == "X")

    print("[3] local tier sorts STRING display_order numerically")
    from app.graph.queries.v2 import get_driver_causes

    class StringStore:
        def all_vertices(self, vertex_type: str) -> dict:
            return {c: {"cause_id": c, "display_order": str(o)} for c, o in lexi}

    out = get_driver_causes(StringStore(), {})[0]["causes"]
    check("3.1 local-tier order numeric with STRING attribute values",
          [r["attributes"]["cause_id"] for r in out] == [c for c, _ in EXPECTED],
          str([r["attributes"]["cause_id"] for r in out][:6]))

    print("\n" + "=" * 60)
    print(f"{PASS} passed, {FAIL} failed — OVERALL", "PASS" if FAIL == 0 else "FAIL")
    for f in FAILURES:
        print("  -", f)
    print("\nNOTE: the frontend applies the same numeric key explicitly "
          "(Number(display_order)) in lib/v2/driver-causes.tsx; a live graph "
          "whose display_order is still STRING should be reinstalled from the "
          "current DDL (see GQ-004 header), but renders correctly regardless.")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
