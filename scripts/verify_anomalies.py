"""Round 6 anomaly-detection verification (FIX_SPEC_R6 Y8).

1. PER-RULE FIXTURES — crafted contexts make each of the six rules fire once
   and only once, plus a below-threshold twin that must NOT fire.
2. GUARDRAIL — wording with an invented figure is blocked and falls back to the
   deterministic template; stored anomalies contain no figure absent from
   metrics_json/threshold_json.
3. ADDITIVE RE-SCAN — a second scan creates a new scan_id while the prior scan
   and all its anomalies remain retrievable, byte-identical.

Run AFTER at least one scan exists (python -m app.v2.anomalies.detection).
NOTE: --rescan actually runs a new scan (LLM calls); without it the additive
check only verifies that existing scans are individually retrievable.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.guardrails.numeric_validation import validate_anomaly_text
from app.v2.anomalies import detection as det

THRESHOLDS = {
    "ANOMALY_UNEXPLAINED_RESIDUAL_PCT": 0.15,
    "ANOMALY_CLAWBACK_MULTIPLE": 5.0,
    "ANOMALY_CLAWBACK_MIN_USD": 10000.0,
    "ANOMALY_LARGE_SWING_PCT": 25.0,
    "ANOMALY_LARGE_SWING_MIN_USD": 50000.0,
    "ANOMALY_FEE_RATE_SHIFT_BPS": 10.0,
    "ANOMALY_SINGLE_DRIVER_DOMINANCE_PCT": 70.0,
}


def base_ctx(**over) -> dict:
    ctx = {
        "thresholds": THRESHOLDS, "advisor": "DFIX001",
        "from_month": "202605", "to_month": "202606",
        "month_ids": ["202604", "202605", "202606"],
        "total_row": {"change_amt": 10000.0, "change_pct": 5.0},
        "total_change": 10000.0,
        "drivers": [], "clawback_by_month": {},
        "recurring_rates": {}, "group_names": {"managed": "Managed"},
        "cause_names": {"ONE_TIME": "One-time items"},
    }
    ctx.update(over)
    return ctx


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS" if cond else "FAIL"), name, detail)
        if not cond:
            failures.append(name)

    # ---------------------------------------------------------------- 1. rules
    print("— per-rule fixtures: each fires once and only once —")
    d = lambda cause, amt, group="managed", i=[0]: (  # noqa: E731
        i.__setitem__(0, i[0] + 1) or
        {"driver_id": f"c|{cause}|{i[0]}", "cause_id": cause,
         "contribution_amt": amt, "group_id": group})

    hit = det.rule_unexplained_residual(base_ctx(
        drivers=[d("MIX", 2000.0)], total_change=10000.0))
    miss = det.rule_unexplained_residual(base_ctx(
        drivers=[d("MIX", 1000.0)], total_change=10000.0))
    check("UNEXPLAINED_RESIDUAL fires at 20%, not at 10%",
          hit is not None and hit["rule_id"] == "UNEXPLAINED_RESIDUAL" and miss is None,
          str(hit and hit["metrics"]["mix_pct_of_change"]))

    hit = det.rule_clawback_concentration(base_ctx(
        clawback_by_month={"202604": -2000.0, "202605": -2000.0, "202606": -15000.0}))
    miss_floor = det.rule_clawback_concentration(base_ctx(
        clawback_by_month={"202604": -100.0, "202605": -100.0, "202606": -9000.0}))
    miss_mult = det.rule_clawback_concentration(base_ctx(
        clawback_by_month={"202604": -8000.0, "202605": -8000.0, "202606": -15000.0}))
    check("CLAWBACK_CONCENTRATION fires at 7.5x/$15k; not under floor; not under multiple",
          hit is not None and miss_floor is None and miss_mult is None,
          str(hit and hit["metrics"]["clawback_total"]))

    hit = det.rule_large_swing(base_ctx(
        total_row={"change_amt": -80000.0, "change_pct": -30.0}))
    miss_pct = det.rule_large_swing(base_ctx(
        total_row={"change_amt": -80000.0, "change_pct": -20.0}))
    miss_amt = det.rule_large_swing(base_ctx(
        total_row={"change_amt": -40000.0, "change_pct": -30.0}))
    check("LARGE_SWING fires at (30%, $80k); not at 20%; not at $40k",
          hit is not None and miss_pct is None and miss_amt is None,
          str(hit and hit["metrics"]["change_amt"]))

    hits = det.rule_fee_rate_shift(base_ctx(
        recurring_rates={"managed": {"202605": 80.0, "202606": 95.0}}))
    misses = det.rule_fee_rate_shift(base_ctx(
        recurring_rates={"managed": {"202605": 80.0, "202606": 88.0}}))
    check("FEE_RATE_SHIFT fires at 15bps, not at 8bps",
          len(hits) == 1 and hits[0]["group_id"] == "managed" and not misses,
          str(hits and hits[0]["metrics"]["shift_bps"]))

    hit = det.rule_single_driver_dominance(base_ctx(
        drivers=[d("ONE_TIME", 8000.0), d("VOLUME", 2000.0)], total_change=10000.0))
    miss = det.rule_single_driver_dominance(base_ctx(
        drivers=[d("ONE_TIME", 6000.0), d("VOLUME", 4000.0)], total_change=10000.0))
    check("SINGLE_DRIVER_DOMINANCE fires at 80%, not at 60%",
          hit is not None and miss is None, str(hit and hit["metrics"]["share_of_change"]))

    hit = det.rule_baseline_limited_present(base_ctx(
        drivers=[d("BASELINE_LIMITED", -1500.0)]))
    miss = det.rule_baseline_limited_present(base_ctx(drivers=[d("VOLUME", 500.0)]))
    check("BASELINE_LIMITED_PRESENT fires when BL present, else not",
          hit is not None and miss is None, str(hit and hit["metrics"]["baseline_limited_amt"]))

    check("exactly six rules; BOOK_MOVEMENT not implemented",
          set(det.SEVERITY) == {"UNEXPLAINED_RESIDUAL", "CLAWBACK_CONCENTRATION",
                                "LARGE_SWING", "FEE_RATE_SHIFT",
                                "SINGLE_DRIVER_DOMINANCE", "BASELINE_LIMITED_PRESENT"},
          str(sorted(det.SEVERITY)))

    # ---------------------------------------------------------------- 2. guardrail
    print("\n— no-invented-figures guardrail —")
    metrics = {"mix_total_raw": 2000.0, "mix_total": "$2,000",
               "mix_pct_of_change": "20.0%", "total_change": "$10,000"}
    good = validate_anomaly_text(metrics, THRESHOLDS,
                                 ["Residual 20.0% of $10,000", "MIX of $2,000 is unexplained."])
    bad = validate_anomaly_text(metrics, THRESHOLDS,
                                ["Residual 20.0%", "MIX of $3,750 is unexplained."])
    minus = validate_anomaly_text(metrics, THRESHOLDS, ["Change of -$2,000 observed."])
    check("guardrail passes verbatim figures, blocks invented $3,750, blocks minus sign",
          good["passed"] and not bad["passed"] and not minus["passed"],
          str(bad["blocked_reason"]))

    class InventingLLM:
        def generate(self, prompt, opts):  # noqa: ARG002
            return json.dumps({"title": "Made-up $9,750 issue",
                               "detail_text": "A figure of $9,750 appeared."})

        def describe(self):
            return {"model": "test-inventor"}

    from app.agents.nodes.commentary_agent import narrate_anomaly
    w = narrate_anomaly("UNEXPLAINED_RESIDUAL",
                        {"mix_total": "$2,000", "mix_pct_of_change": "20.0%",
                         "total_change": "$10,000"}, THRESHOLDS, InventingLLM())
    check("invented wording falls back to the deterministic template (no AI chip)",
          not w["ai_generated"] and "$2,000" in w["detail_text"]
          and "9,750" not in w["detail_text"],
          w["model"])

    # ---------------------------------------------------------------- 3. stored
    print("\n— stored anomalies (current data set) —")
    from app.v2.anomalies.service import V2AnomalyService
    svc = V2AnomalyService()
    scans = svc.scans()["scans"]
    check("at least one scan stored", len(scans) >= 1,
          str([s.get("scan_id") for s in scans]))
    dirty = []
    for s in scans:
        rows = svc.anomalies(scan_id=str(s["scan_id"]))["anomalies"]
        for a in rows:
            v = validate_anomaly_text(json.loads(a["metrics_json"]),
                                      json.loads(a["threshold_json"]),
                                      [a["title"], a["detail_text"]])
            if not v["passed"]:
                dirty.append(f"{a['anomaly_id']}: {v['blocked_reason']}")
    check("no stored anomaly contains a figure absent from metrics_json", not dirty,
          str(dirty[:3]))

    # ---------------------------------------------------------------- 4. additive
    if "--rescan" in sys.argv:
        print("\n— additive re-scan —")
        before = {s["scan_id"]: svc.anomalies(scan_id=str(s["scan_id"]))["anomalies"]
                  for s in scans}
        summary = det.run_scan("verify_anomalies additive re-scan")
        new_id = summary["scan_id"]
        after_scans = [s["scan_id"] for s in svc.scans()["scans"]]
        check("re-scan created a NEW scan_id", new_id not in before and new_id in after_scans,
              new_id)
        intact = all(svc.anomalies(scan_id=sid)["anomalies"] == rows
                     for sid, rows in before.items())
        check("prior scans remain retrievable and unchanged", intact, str(list(before)))
        latest = svc.anomalies()["scan_id_used"]
        check("scan_id='' resolves to the newest scan", latest == new_id, latest)
    else:
        print("\n(skipping live re-scan — pass --rescan to run it)")

    print("\nOVERALL:", "PASS" if not failures else f"FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
