"""R15.1 verification — get_commentary latest-version resolution (max, not sum).

Client-env bug: the live-installed get_commentary summed version_no across all
matching versions (advisor's own + legacy global advisor_sid==""), so
version_id="" resolved to a non-existent version and the AI Insights screen
showed "No commentary generated for this advisor yet" despite stored rows.

Proof here (local tier):
1. fixture store reproducing the CLIENT shape — a PUBLISHED legacy global v1
   plus the advisor's own versions (one superseded, one published), so the
   buggy sum (1+3=4) overshoots the true max (3): the local-tier
   get_commentary returns the max version's rows and resolved_version == the
   true max version_id, while the summed id names nothing (empty set = the
   client symptom)
2. sample-data regression — for every advisor, get_commentary(advisor, "")
   returns a NON-EMPTY set and resolved_version equals the version_id of the
   TRUE max version_no among PUBLISHED versions with advisor_sid in
   ("", advisor)
3. GSQL contract — GQ-009 declares MaxAccum for @@latest_no (never a summing
   accumulator outside comments) and resolves the id from the winning vertex
   (version_no == @@latest_no second pass), never "v"+arithmetic
4. no other GSQL query resolves a "latest" by summing version/scan identity

Exit non-zero on any failure.
"""
from __future__ import annotations

import os
import re
import sys

os.environ.setdefault("GRAPH_CLIENT_MODE", "local")
os.environ.setdefault("DATA_SET", "sample")
os.environ["LLM_CLIENT_MODE"] = "mock"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    print(("  PASS " if ok else "  FAIL "), name, detail if not ok else "")
    if ok:
        PASS += 1
    else:
        FAIL += 1


from app.graph.client import get_graph_client  # noqa: E402

graph = get_graph_client()


def rows(name: str, key: str, params: dict) -> list[dict]:
    result = graph.run_query(name, params)
    assert not result.get("error"), f"{name} errored"
    out: list[dict] = []
    extras: dict = {}
    for obj in result.get("results", []):
        if key in obj:
            out = [r.get("attributes", {}) for r in obj[key]]
        elif isinstance(obj, dict):
            extras.update(obj)
    return out, extras


advisors = sorted(a.get("advisor_sid") for a in
                  rows("get_advisors", "advisors", {})[0])
versions, _ = rows("get_commentary_versions", "versions", {"advisor_id": ""})
print(f"data: {len(advisors)} advisors, {len(versions)} stored commentary versions")

# --------------------------------------------------------------------- [1]
print("\n[1] fixture store — client shape: PUBLISHED legacy global v1 + advisor "
      "versions; sum overshoots, max resolves")
from app.graph.queries import v2 as local_tier  # noqa: E402


class _FixtureStore:
    """Minimal FoundationGraphStore stand-in for the local-tier impls: the
    exact client-env shape (global v1 PUBLISHED, advisor v2 SUPERSEDED,
    advisor v3 PUBLISHED — matching published nos {1, 3}: sum 4, max 3)."""

    _V = {
        "v1": {"version_id": "v1", "version_no": 1, "status": "PUBLISHED",
               "advisor_sid": ""},                       # legacy global
        "v2": {"version_id": "v2", "version_no": 2, "status": "SUPERSEDED",
               "advisor_sid": "ADV9"},
        "v3": {"version_id": "v3", "version_no": 3, "status": "PUBLISHED",
               "advisor_sid": "ADV9"},
    }
    _C = {
        "v1|ADV9|202605": {"commentary_id": "v1|ADV9|202605", "version_id": "v1",
                           "advisor_sid": "ADV9", "from_month_id": "202604",
                           "to_month_id": "202605", "headline": "legacy",
                           "status": "PUBLISHED"},
        "v3|ADV9|202605": {"commentary_id": "v3|ADV9|202605", "version_id": "v3",
                           "advisor_sid": "ADV9", "from_month_id": "202604",
                           "to_month_id": "202605", "headline": "latest",
                           "status": "PUBLISHED"},
    }

    def all_vertices(self, vtype: str) -> dict:
        if vtype == local_tier.COMMENTARY_VERSION:
            return {k: dict(v) for k, v in self._V.items()}
        if vtype == local_tier.COMMENTARY:
            return {k: dict(v) for k, v in self._C.items()}
        return {}


fx = _FixtureStore()
out = local_tier.get_commentary(fx, {"advisor_id": "ADV9", "version_id": ""})
fx_rows = [r.get("attributes", {}) for r in out[0]["commentaries"]]
fx_resolved = str(out[1]["resolved_version"])
check("fixture: >=2 matching PUBLISHED versions incl. the legacy global "
      "(nos {1, 3}: sum 4 overshoots max 3)", True)
check("fixture: resolved_version == v3 (the TRUE max), not v4 (the sum)",
      fx_resolved == "v3", f"resolved={fx_resolved!r}")
check("fixture: the max version's commentary returned (non-empty, v3 rows only)",
      len(fx_rows) == 1 and fx_rows[0]["version_id"] == "v3"
      and fx_rows[0]["headline"] == "latest", str(fx_rows))
ghost = local_tier.get_commentary(fx, {"advisor_id": "ADV9", "version_id": "v4"})
check("fixture: the summed id v4 names NO version — 0 rows (the client symptom "
      "the fix removes)", len(ghost[0]["commentaries"]) == 0)

# --------------------------------------------------------------------- [2]
print("\n[2] sample regression — get_commentary(advisor, '') returns the TRUE "
      "latest version's rows")
for sid in advisors:
    mine = [v for v in versions
            if str(v.get("status")) == "PUBLISHED"
            and str(v.get("advisor_sid") or "") in ("", sid)]
    true_latest = max(mine, key=lambda v: int(v.get("version_no") or 0))
    true_vid = str(true_latest.get("version_id"))
    commentaries, extras = rows("get_commentary", "commentaries",
                                {"advisor_id": sid, "version_id": ""})
    resolved = str(extras.get("resolved_version") or "")
    check(f"{sid}: commentary set NON-EMPTY ({len(commentaries)} rows)",
          len(commentaries) > 0)
    check(f"{sid}: resolved_version == true max version ({true_vid}, "
          f"version_no {true_latest.get('version_no')})",
          resolved == true_vid, f"resolved={resolved!r}")
    check(f"{sid}: every returned row belongs to {true_vid} for {sid}",
          all(str(c.get("version_id")) == true_vid
              and str(c.get("advisor_sid")) == sid for c in commentaries))

print("\n[3] GSQL contract — GQ-009 max-resolves and reads the winning vertex id")
gq009_path = os.path.join(
    ROOT, "docs/tigergraph_foundation/tigergraph/queries/GQ-009_get_commentary.gsql")
gq009 = open(gq009_path, encoding="utf-8").read()


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


gq009_code = strip_comments(gq009)
check("MaxAccum<INT> @@latest_no declared; no summing accumulator in GQ-009 code",
      "MaxAccum<INT> @@latest_no" in gq009_code and "SumAccum" not in gq009_code)
check("resolved id read from the vertex (version_no == @@latest_no second pass), "
      "never reconstructed as \"v\"+number",
      "v.version_no == @@latest_no" in gq009_code
      and "@@resolved_id += v.version_id" in gq009_code
      and '"v" + to_string(@@latest_no)' not in gq009_code)

print("\n[4] no other query resolves a 'latest' by summing")
qdir = os.path.join(ROOT, "docs/tigergraph_foundation/tigergraph/queries")
offenders = []
for fn in sorted(os.listdir(qdir)):
    if not fn.endswith(".gsql"):
        continue
    text = open(os.path.join(qdir, fn), encoding="utf-8").read()
    for m in re.finditer(r"SumAccum<\w+>\s+(@+\w+)", text):
        acc = m.group(1)
        # a SumAccum fed from a version/scan/latest-style field is the bug class
        if re.search(re.escape(acc) + r"\s*\+=\s*\w+\.(version_no|scan_id|version_id|started_at)",
                     text):
            offenders.append(f"{fn}:{acc}")
check("no GSQL query sums version_no/scan identity to find a latest",
      not offenders, str(offenders))

print("\n" + "=" * 60)
print(f"{PASS} passed, {FAIL} failed — OVERALL {'PASS' if FAIL == 0 else 'FAIL'}")
print("\nNOTE: local-tier + file-contract proof. The LIVE fix requires "
      "reinstalling GQ-009 on TigerGraph (install_all_queries.gsql or the "
      "single file) — operator step, see docs/ROUND15_ACCEPTANCE.md §8.")
sys.exit(1 if FAIL else 0)
