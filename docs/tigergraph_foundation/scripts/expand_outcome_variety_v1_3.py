"""Section 11.3 Part A — outcome-variety data expansion (bounded, deterministic, append-only).

Adds 144 (feedback, outcome, learning_signal) triples spanning ALL three recommendation
families with a realistic mix of successful AND unsuccessful outcomes — including the first
genuinely-negative outcome_value rows in the dataset ("completed but it hurt"). This gives the
outcome-driven GNN fine-tuning (11.3 Part B) real signal to learn from.

Idempotent (sentinel FB_FL0001). Append-only — never rewrites an existing row, so anchored
advisor figures cannot move (asserted separately). No schema changes; outcome_value is DOUBLE.
"""
import csv
import datetime as dt
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "data/sample/vertices"
E = ROOT / "data/sample/edges"
MANIFEST = ROOT / "data/manifest.json"
EVIDENCE = ROOT.parents[1] / "docs/section11/evidence"

# Live ACTION_SIGNALS (app/feedback/service.py) — reward, ranking weight delta.
SIGNALS = {
    "ACCEPT": (0.6, 0.05), "COMPLETE": (1.0, 0.10), "MODIFY": (0.3, 0.02),
    "IGNORE": (-0.1, -0.02), "REJECT": (-0.5, -0.08),
}
# family -> (new_triples, positive, negative, rec_id_pool_builder)
CRM = [f"REC_A{n:03d}" for n in range(1, 61)]
MANAGED = [f"REC_AC_AC{n:05d}" for n in range(1, 31)]
RETENTION = [f"REC_HH_H{n:04d}" for n in range(1, 31)]
PLAN = [
    ("CRM_EXECUTION", 26, 10, CRM),
    ("MANAGED_MIX", 20, 34, MANAGED),
    ("RETENTION", 34, 20, RETENTION),
]
BASE_DATE = dt.date(2026, 1, 5)   # first Monday; weekly buckets to 2026-06-28
END_DATE = dt.date(2026, 7, 3)


def rng_for(*key):
    import random
    return random.Random(zlib.crc32(":".join(str(k) for k in key).encode()))


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def append(path, header, rows):
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=header).writerows(rows)


def build_events():
    """Deterministic list of 144 event specs, interleaved over time by index."""
    specs = []
    for family, pos, neg, pool in PLAN:
        for _ in range(pos):
            specs.append([family, "positive", pool])
        for _ in range(neg):
            specs.append([family, "negative", pool])
    # deterministic interleave so families + polarities mix across the timeline
    rng_for("interleave").shuffle(specs)
    return specs


def main():
    header_fb, fb_rows = read(V / "phx_dm_feedback_event.csv")
    if any(r["feedback_id"] == "FB_FL0001" for r in fb_rows):
        print("11.3 Part A: already applied (FB_FL0001 present), skipping.")
        return

    header_out, _ = read(V / "phx_dm_outcome_event.csv")
    header_ls, _ = read(V / "phx_dm_learning_signal.csv")
    edge_h = ["from_id", "to_id"]

    specs = build_events()
    n = len(specs)
    fb, out, ls = [], [], []
    e_fbrec, e_outfb, e_lsout, e_lsrec = [], [], [], []
    completed_neg = 0
    modify_used = 0
    dist = {}  # (family, polarity, action) -> count

    for i, (family, polarity, pool) in enumerate(specs):
        g = rng_for("fl", i, family, polarity)
        fid, oid, lid = f"FB_FL{i+1:04d}", f"OUT_FL{i+1:04d}", f"LS_FL{i+1:04d}"
        rec = pool[i % len(pool)]

        if polarity == "positive":
            # ~40/60 ACCEPT/COMPLETE, with a few MODIFY (capped at 8 total)
            if modify_used < 8 and g.random() < 0.06:
                action = "MODIFY"; modify_used += 1
            else:
                action = "ACCEPT" if g.random() < 0.4 else "COMPLETE"
            outcome_type = "REVENUE_IMPACT"
            outcome_value = round(g.uniform(1500, 45000), 2)
            reward, delta = SIGNALS[action]
        else:
            # negatives: ~30% completed-with-negative-impact, ~55% REJECT, ~15% IGNORE
            roll = g.random()
            if completed_neg < 20 and roll < 0.30:
                action = "COMPLETE"; completed_neg += 1
                outcome_type = "REVENUE_IMPACT"
                outcome_value = round(g.uniform(-25000, -2000), 2)
                base_reward, delta = SIGNALS["COMPLETE"]
                reward = round(max(-1.0, base_reward - 0.20), 4)  # outcome adjustment (service.py)
            elif roll < 0.80:
                action = "REJECT"; outcome_type = "ACTION_TAKEN"; outcome_value = 0.0
                reward, delta = SIGNALS[action]
            else:
                action = "IGNORE"; outcome_type = "ACTION_TAKEN"; outcome_value = 0.0
                reward, delta = SIGNALS[action]

        created = BASE_DATE + dt.timedelta(weeks=int(i * 26 / n), days=g.randint(0, 4))
        if created > END_DATE:
            created = END_DATE
        observed = min(created + dt.timedelta(days=g.randint(3, 21)), END_DATE)
        adv_num = (i % 60) + 1
        user = f"U_ADV{adv_num:03d}"

        fb.append({"feedback_id": fid, "action": action, "reason_code": "OUTCOME_RECORDED",
                   "reason_text": "Seeded outcome-history feedback event.",
                   "created_at": created.isoformat(), "user_id": user})
        out.append({"outcome_id": oid, "outcome_type": outcome_type,
                    "outcome_value": outcome_value, "outcome_unit": "USD",
                    "observed_at": observed.isoformat(), "notes": "Seeded recorded outcome."})
        ls.append({"learning_signal_id": lid, "signal_type": "RECOMMENDATION_FEEDBACK",
                   "reward": reward, "score_delta": delta,
                   "signal_json": json.dumps({"action": action, "family": family,
                                              "outcome_value": outcome_value, "label": polarity,
                                              "source": "SEEDED_OUTCOME_HISTORY"}),
                   "created_at": created.isoformat()})
        e_fbrec.append({"from_id": fid, "to_id": rec})
        e_outfb.append({"from_id": oid, "to_id": fid})
        e_lsout.append({"from_id": lid, "to_id": oid})
        e_lsrec.append({"from_id": lid, "to_id": rec})
        dist[(family, polarity, action)] = dist.get((family, polarity, action), 0) + 1

    append(V / "phx_dm_feedback_event.csv", header_fb, fb)
    append(V / "phx_dm_outcome_event.csv", header_out, out)
    append(V / "phx_dm_learning_signal.csv", header_ls, ls)
    append(E / "phx_dm_feedback_for_recommendation.csv", edge_h, e_fbrec)
    append(E / "phx_dm_outcome_for_feedback.csv", edge_h, e_outfb)
    append(E / "phx_dm_learning_from_outcome.csv", edge_h, e_lsout)
    append(E / "phx_dm_learning_updates_recommendation.csv", edge_h, e_lsrec)

    # bump manifest expected_rows 36 -> 180 for the 7 files
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest["files"] if isinstance(manifest, dict) and "files" in manifest else manifest
    targets = {"phx_dm_feedback_event", "phx_dm_outcome_event", "phx_dm_learning_signal",
               "phx_dm_feedback_for_recommendation", "phx_dm_outcome_for_feedback",
               "phx_dm_learning_from_outcome", "phx_dm_learning_updates_recommendation"}
    bumped = 0
    for entry in files:
        stem = Path(entry.get("file", "")).stem
        if stem in targets and entry.get("expected_rows") == 36:
            entry["expected_rows"] = 180
            bumped += 1
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # distribution report
    pos = sum(v for (f, p, a), v in dist.items() if p == "positive")
    neg = sum(v for (f, p, a), v in dist.items() if p == "negative")
    report = {"new_triples": n, "positive": pos, "negative": neg,
              "completed_negative": completed_neg, "modify": modify_used,
              "manifest_bumped": bumped,
              "by_family": {}, "by_action": {}}
    for (f, p, a), v in sorted(dist.items()):
        report["by_family"].setdefault(f, {"positive": 0, "negative": 0})[p] += v
        report["by_action"][a] = report["by_action"].get(a, 0) + v
    print(json.dumps(report, indent=2))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "outcome_variety_distribution.json").write_text(json.dumps(report, indent=2))
    print(f"\nAppended 144 triples; 7 files 36->180; manifest bumped {bumped}/7.")


if __name__ == "__main__":
    main()
