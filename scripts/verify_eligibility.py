"""Verify the R10 eligibility rule (FIX_SPEC_R10 B / H2).

    python -m scripts.verify_eligibility

  [1] NULL / empty / __NONE__ are credited (a missing code is eligible)
  [2] every 9… code is NOT credited; 91/92/9L flipped from the prior rule
  [3] the excluded set (9R/98/99/9H/9X/XX) is unchanged and outside Total
  [4] only __NONE__ carries include_in_credited=TRUE in the seed
  [5] the committed sample reflects the rule and its credited identity holds
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.revenue import eligibility as elig

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


reasons = elig.reason_map()

print("[1] NULL / empty / __NONE__ credited")
for code in (None, "", "   ", "__NONE__"):
    check(f"reason {code!r} -> CREDITED",
          elig.reason_eligibility(code, reasons) == elig.CREDITED)

print("[2] every 9… code not credited (91/92/9L flipped this round)")
for code in ("91", "92", "9L", "9E", "9G", "9C", "9S", "94"):
    check(f"reason {code!r} -> NON_CREDITED",
          elig.reason_eligibility(code, reasons) == elig.NON_CREDITED)
check("unknown 9-code '9Q' -> NON_CREDITED (never credit the unclassifiable)",
      elig.reason_eligibility("9Q", reasons) == elig.NON_CREDITED)

print("[3] excluded set unchanged, outside Total Revenue")
for code in ("9R", "98", "99", "9H", "9X", "XX"):
    check(f"reason {code!r} -> EXCLUDED",
          elig.reason_eligibility(code, reasons) == elig.EXCLUDED)
seed = {r["reason_code"]: r for r in elig.seed_rows()}
check("exactly 6 excluded codes in the seed",
      sorted(c for c, r in seed.items() if r["eligibility"] == elig.EXCLUDED)
      == ["98", "99", "9H", "9R", "9X", "XX"])

print("[4] only __NONE__ is include_in_credited=TRUE in the seed")
credited_codes = [c for c, r in seed.items() if r["include_in_credited"]]
check("credited seed codes == ['__NONE__']", credited_codes == [elig.NO_REASON],
      f"got {credited_codes}")

print("[5] committed sample reflects the rule")
txns = list(csv.DictReader(open("data/sample/vertices/phx_dm_v2_revenue_transaction.csv")))
bad = [t["txn_id"] for t in txns
       if (t["reason_cd"] == elig.NO_REASON) != (t["revenue_eligibility"] == "CREDITED")
       and t["revenue_eligibility"] != "EXCLUDED"]
check("every sample txn: credited iff reason __NONE__ (excluded aside)", not bad, f"{bad[:5]}")
n91 = [t for t in txns if t["reason_cd"] == "91"]
check("sample carries 91 rows and ALL are NON_CREDITED (flip visible)",
      bool(n91) and all(t["revenue_eligibility"] == "NON_CREDITED" for t in n91))
mpr = list(csv.DictReader(open("data/sample/vertices/phx_dm_v2_monthly_product_revenue.csv")))
ident = [r["mpr_id"] for r in mpr
         if abs(float(r["revenue"]) - (float(r["total_revenue"]) - float(r["non_credited_amt"])
                                       - float(r["late_excluded_amt"]))) > 0.02]
check("credited identity holds on every mpr cell (excluded outside Total)", not ident,
      f"{ident[:5]}")

print()
if failures:
    print(f"OVERALL FAIL — {failures}")
    sys.exit(1)
print("OVERALL PASS — R10 eligibility rule in force; excluded set untouched")
