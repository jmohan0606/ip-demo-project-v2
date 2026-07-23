"""Write TINY synthetic raw-extract fixtures to data/real/_raw/ (FIX_SPEC_R4 B6).

    python -m scripts.make_test_raw_extracts

Purpose: prove scripts/build_real_data.py end to end WITHOUT a reachable
PostgreSQL or TigerGraph — the fixtures have the exact raw-column shape the
B1 contract expects, small enough to eyeball. They are OBVIOUSLY synthetic
(advisors RTEST01/RTEST02, accounts TESTACCT-*) and land in a gitignored
directory (data/real/ — verify with `git check-ignore data/real/_raw/x`).
NEVER commit these files; on the client machine the same directory holds the
genuine extracts instead.

The rows exercise the interesting paths: FEE_RATE (rate step), CLAWBACK
(negative row), ONE_TIME (twhs syndicate in one month), VOLUME (trade-count
swing), OUT_OF_GRID (PAY_TYPE_SUMMARY product), ELIGIBILITY (9E in June),
LATE_PROCESSING (April row processed 100 days late), EXCLUDED_CHANGE (9X
deleted booking from May), NEW_ACCOUNT (account first trades in June), and a
blank advisor display name (falls back to the id — never invented).
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.build_real_data import RAW_CONTRACT

OUT = Path("data/real/_raw")

ADVISORS = [
    # advisor_sid, rr_nam, rep_code, branch_cd, advisor_name
    ("RTEST01", "TEST REP ONE", "TR01", "TESTBR1", "Test Advisor One"),
    ("RTEST02", "", "TR02", "TESTBR1", ""),  # blank names -> UI shows the id
]

HIERARCHY = [
    # product_code, sub_product_code, level_two_product, level_one_product,
    # grid_type, level_one_pay_type_product_cd, level_two_pay_type_product_cd
    ("UMA", "FEE", "Unified Managed Account", "Managed", "PRODUCT_TYPE", "", ""),
    ("MFT", "12B1", "Mutual Fund Trails", "Trails", "PRODUCT_TYPE", "", ""),
    ("STRP", "SYND", "Structured Products", "Structured Products", "PRODUCT_TYPE", "", ""),
    ("EQ", "COMM", "Equities", "Equities and Options", "PRODUCT_TYPE", "", ""),
    ("UMA", "PAYS", "Unified Managed Account", "Managed", "PAY_TYPE_SUMMARY", "", ""),
]


def txn(n, advisor, month, product_cd, sub_cd, account, day, amount, *,
        rate=0.0, file_key="ace", desc="", concession="None", discount=0.0,
        reason="", proc_days=1):
    trade = f"2026-{month[4:6]}-{day:02d} 00:00:00"
    pm, pd = int(month[4:6]), day + proc_days
    while pd > 28:  # roll into following month(s) — keeps dates valid
        pd -= 28
        pm += 1
    proc = f"2026-{pm:02d}-{pd:02d} 00:00:00"
    return (f"RTESTTRD{n:04d}", 1, advisor, month, product_cd, sub_cd, account,
            trade, proc, amount, amount, 1.0, rate, rate, concession, discount,
            0.0, 0.0, file_key, desc or f"MONTH M{int(month[4:6]):02d}-2026",
            reason, "TESTRM1", "TESTCS1", next(h[4] for h in HIERARCHY
                                               if h[0] == product_cd and h[1] == sub_cd))


def build_txns():
    rows, n = [], 0

    def add(*args, **kwargs):
        nonlocal n
        n += 1
        rows.append(txn(n, *args, **kwargs))

    for month in ("202604", "202605", "202606"):
        # RTEST01 — UMA fee, rate steps 82 -> 88 bps in June (FEE_RATE)
        rate = 88.0 if month == "202606" else 82.0
        add("RTEST01", month, "UMA", "FEE", "TESTACCT-1", 28,
            5500.0 if month == "202606" else 5000.0, rate=rate)
        # RTEST01 — eligibility story: 1200 fee goes 9E (non-credited) in June
        add("RTEST01", month, "UMA", "FEE", "TESTACCT-3", 27, 1200.0, rate=82.0,
            reason="9E" if month == "202606" else "")
        # RTEST01 — MFT trail + a May reversal (CLAWBACK)
        add("RTEST01", month, "MFT", "12B1", "TESTACCT-2", 25, 1000.0, rate=25.0,
            file_key="mf_12b1")
        if month == "202605":
            add("RTEST01", month, "MFT", "12B1", "TESTACCT-2", 26, -100.0, rate=25.0,
                file_key="mf_12b1", desc="MONTH M05-2026 REVERSAL")
        # RTEST01 — ONE_TIME syndicate in May only (file_key twhs)
        if month == "202605":
            add("RTEST01", month, "STRP", "SYND", "TESTACCT-1", 12, 8000.0,
                file_key="twhs", desc="SYNDICATE ALLOCATION")
        # RTEST01 — equity VOLUME swing: 2 -> 1 -> 3 trades
        for k in range({"202604": 2, "202605": 1, "202606": 3}[month]):
            add("RTEST01", month, "EQ", "COMM", "TESTACCT-4", 5 + k * 3, 150.0,
                desc="EQUITY TRADE COMMISSION")
        # RTEST01 — PAY_TYPE_SUMMARY row (OUT_OF_GRID under default config)
        add("RTEST01", month, "UMA", "PAYS", "TESTACCT-1", 28, 20000.0,
            desc="PAY TYPE SUMMARY")
        # RTEST02 — LATE_PROCESSING: April's 900 fee processes 100 days late
        add("RTEST02", month, "UMA", "FEE", "TESTACCT-6", 2, 900.0, rate=82.0,
            proc_days=100 if month == "202604" else 1,
            desc=f"MONTH M{int(month[4:6]):02d}-2026"
                 + (" LATE PROCESS" if month == "202604" else ""))
        # RTEST02 — EXCLUDED_CHANGE: 500 booking credited in Apr, 9X after
        add("RTEST02", month, "MFT", "12B1", "TESTACCT-7", 20, 500.0, rate=25.0,
            file_key="mf_12b1",
            desc="TRAIL BOOKING" + ("" if month == "202604" else " (DELETED)"),
            reason="" if month == "202604" else "9X")
        # RTEST02 — NEW_ACCOUNT: TESTACCT-9 first trades in June
        if month == "202606":
            add("RTEST02", month, "EQ", "COMM", "TESTACCT-9", 10, 600.0,
                desc="EQUITY TRADE COMMISSION")
    return rows


def write(name: str, header: list[str], rows) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {OUT / name} ({len(rows)} rows)")


def main() -> int:
    write("raw_advisor.csv", RAW_CONTRACT["raw_advisor.csv"]["columns"], ADVISORS)
    write("raw_product_hierarchy.csv",
          RAW_CONTRACT["raw_product_hierarchy.csv"]["columns"], HIERARCHY)
    write("raw_revenue_transaction.csv",
          RAW_CONTRACT["raw_revenue_transaction.csv"]["columns"], build_txns())
    print("\nTest fixtures only — gitignored, never commit. Now run:\n"
          "  python -m scripts.build_real_data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
