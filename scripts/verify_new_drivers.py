"""Verify the R10 INHERITANCE / HOUSEHOLD drivers (FIX_SPEC_R10 C / H3+H4).

    python -m scripts.verify_new_drivers

Fixture checks (local, deterministic — no TigerGraph):
  [1] a 9G flip (present from-month, absent to-month) produces INHERITANCE
      with the right sign and magnitude
  [2] a 9E flip produces HOUSEHOLD, right sign/magnitude
  [3] partition exactness: INHERITANCE + HOUSEHOLD + ELIGIBILITY equals the
      total eligibility effect -(Δ non-credited); ELIGIBILITY's inputs exclude
      9G/9E; nothing double-counted; MIX does not absorb the movement
  [4] reconciliation $0.00 on the fixture transition
  [5] the committed sample exercises both drivers and its ELIGIBILITY
      remainder carries no 9G/9E
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.v2.drivers.attribution import attribute_transition, reconcile

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def txn(month, account, amount, reason="", nature="RECURRING"):
    return {"advisor_sid": "FIX01", "month_id": month, "account_no": account,
            "credited_amt": amount, "reason_cd": reason or "__NONE__",
            "rev_nature": nature, "client_rate_bps": 0.0, "discount_amt": 0.0,
            "concession_type": "None", "file_key": "ace", "days_to_process": 1}


GROUP = "rec_trails__mutual_funds"
MONTHS = ["202604", "202605", "202606"]


def run_fixture(cred, nc):
    """cred/nc: {month: [txns]} for one group. Returns (drivers, report)."""
    changes = []
    by_month_total = {m: sum(t["credited_amt"] for t in cred.get(m, [])) for m in MONTHS}
    for f, t in zip(MONTHS, MONTHS[1:]):
        for gid in (GROUP, "__TOTAL__"):
            changes.append({
                "change_id": f"FIX01|{f}|{t}|{gid}", "advisor_sid": "FIX01",
                "from_month_id": f, "to_month_id": t, "group_id": gid,
                "from_revenue": by_month_total[f], "to_revenue": by_month_total[t],
                "change_amt": round(by_month_total[t] - by_month_total[f], 2),
                "change_pct": 0.0, "direction": "UP",
            })
    txns_by = {(GROUP, m): list(cred.get(m, [])) for m in MONTHS}
    nc_by = {(GROUP, m): list(nc.get(m, [])) for m in MONTHS}
    drivers = []
    for f, t in zip(MONTHS, MONTHS[1:]):
        rows = [c for c in changes if c["from_month_id"] == f and c["to_month_id"] == t]
        drivers += attribute_transition(rows, txns_by, {GROUP}, 22, 22,
                                        nc_txns_by_group_month=nc_by,
                                        loaded_month_ids=MONTHS)
    return drivers, reconcile(changes, drivers)


def by_cause(drivers, f, t):
    out = {}
    for d in drivers:
        adv, fm, tm, _g = d["change_id"].split("|")
        if (fm, tm) == (f, t):
            out.setdefault(d["cause_id"], 0.0)
            out[d["cause_id"]] += float(d["contribution_amt"])
    return out


# Steady credited base in all months so the account stays present; ACCT-9G's
# 800 trail is 9G (non-credited) in Apr+May and credited in Jun (cooling ends);
# ACCT-9E's 500 is credited in Apr+May and 9E in Jun; ACCT-9C's 300 is 9C
# non-credited in May+Jun only (the ELIGIBILITY remainder).
cred = {m: [txn(m, "ACCT-BASE", 10000.0)] for m in MONTHS}
cred["202606"].append(txn("202606", "ACCT-9G", 800.0))
cred["202604"].append(txn("202604", "ACCT-9E", 500.0))
cred["202605"].append(txn("202605", "ACCT-9E", 500.0))
cred["202604"].append(txn("202604", "ACCT-9C", 300.0))
cred["202605"].append(txn("202605", "ACCT-9C", 300.0))
nc = {
    "202604": [txn("202604", "ACCT-9G", 800.0, reason="9G")],
    "202605": [txn("202605", "ACCT-9G", 800.0, reason="9G")],
    "202606": [txn("202606", "ACCT-9E", 500.0, reason="9E"),
               txn("202606", "ACCT-9C", 300.0, reason="9C")],
}

drivers, report = run_fixture(cred, nc)
mj = by_cause(drivers, "202605", "202606")

print("[1] 9G flip -> INHERITANCE, right sign and magnitude")
check("INHERITANCE fires on May->Jun", "INHERITANCE" in mj, f"got {sorted(mj)}")
check("INHERITANCE = +800.00 (9G 800 -> 0, revenue back to credited)",
      abs(mj.get("INHERITANCE", 0.0) - 800.0) < 0.01, f"got {mj.get('INHERITANCE')}")
am = by_cause(drivers, "202604", "202605")
check("steady 9G (Apr->May) emits NO INHERITANCE", "INHERITANCE" not in am,
      f"got {am.get('INHERITANCE')}")
inh = next(d for d in drivers if d["cause_id"] == "INHERITANCE")
inputs = json.loads(inh["inputs_json"])
check("INHERITANCE inputs list the flipped account by presence",
      inputs.get("accounts_with_code_in_from_month_only") == ["ACCT-9G"], f"got {inputs}")
check("INHERITANCE provenance DERIVED", inh["data_source"] == "DERIVED")

print("[2] 9E flip -> HOUSEHOLD, right sign and magnitude")
check("HOUSEHOLD fires on May->Jun", "HOUSEHOLD" in mj, f"got {sorted(mj)}")
check("HOUSEHOLD = (500.00) (9E 0 -> 500, revenue leaves credited)",
      abs(mj.get("HOUSEHOLD", 0.0) + 500.0) < 0.01, f"got {mj.get('HOUSEHOLD')}")
hh = next(d for d in drivers if d["cause_id"] == "HOUSEHOLD")
check("HOUSEHOLD provenance DERIVED", hh["data_source"] == "DERIVED")

print("[3] partition exactness — no double-count, MIX untouched")
check("ELIGIBILITY (May->Jun) = (300.00): the 9C remainder only",
      abs(mj.get("ELIGIBILITY", 0.0) + 300.0) < 0.01, f"got {mj.get('ELIGIBILITY')}")
elig_d = [d for d in drivers if d["cause_id"] == "ELIGIBILITY"]
codes = {c for d in elig_d for c in json.loads(d["inputs_json"]).get("reason_codes", [])}
check("ELIGIBILITY inputs carry NO 9G/9E rows", not codes & {"9G", "9E"}, f"got {codes}")
total_elig_effect = -((500.0 + 300.0) - 800.0)  # -(Δ total nc) May->Jun = 0.00
three = mj.get("INHERITANCE", 0) + mj.get("HOUSEHOLD", 0) + mj.get("ELIGIBILITY", 0)
check("INHERITANCE + HOUSEHOLD + ELIGIBILITY == total eligibility effect "
      f"({total_elig_effect:+.2f})", abs(three - total_elig_effect) < 0.01, f"got {three}")
check("MIX does not absorb the reclassification movement (|MIX| < $1)",
      abs(mj.get("MIX", 0.0)) < 1.0, f"got {mj.get('MIX')}")

print("[4] reconciliation $0.00")
check("all transitions reconcile", report["all_reconcile"], json.dumps(report))

print("[5] committed sample exercises both drivers; remainder clean")
drv = list(csv.DictReader(open("data/sample/vertices/phx_dm_v2_revenue_driver.csv")))
s_inh = [d for d in drv if d["cause_id"] == "INHERITANCE"]
s_hh = [d for d in drv if d["cause_id"] == "HOUSEHOLD"]
check("sample INHERITANCE driver present (9G cooling ends May->Jun, +800)",
      any(abs(float(d["contribution_amt"]) - 800.0) < 0.01 for d in s_inh))
check("sample HOUSEHOLD driver present (9E starts in Jun, negative)",
      any(float(d["contribution_amt"]) < 0 for d in s_hh))
s_codes = {c for d in drv if d["cause_id"] == "ELIGIBILITY"
           for c in json.loads(d["inputs_json"]).get("reason_codes", [])}
check("sample ELIGIBILITY remainder carries no 9G/9E", not s_codes & {"9G", "9E"},
      f"got {s_codes}")

print()
if failures:
    print(f"OVERALL FAIL — {failures}")
    sys.exit(1)
print("OVERALL PASS — INHERITANCE/HOUSEHOLD carve-outs exact; ELIGIBILITY remainder clean")
