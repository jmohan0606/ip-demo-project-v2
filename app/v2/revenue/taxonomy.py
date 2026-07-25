"""Product taxonomy (FIX_SPEC_R10 A) — THE canonical recurring / non-recurring
hierarchy, transcribed VERBATIM from the client's corrected hierarchy (A1).

The previous taxonomy came from a wrong Figma screen. This module replaces it
and is the SINGLE source both dataset builders (sample + real) seed from.

CRITICAL NUANCE (A2): `Annuities`, `Mutual funds` and `Cash management` each
appear under BOTH recurring and non-recurring. Classification therefore keys
on a product's POSITION IN THIS HIERARCHY (its class -> line -> group path),
NEVER on a name match. Every id below encodes its full path so the dual-name
cases can never collide:

    line_id  = rec_<line>   | nonrec_<line>
    group_id = <line_id>__<group>

Worked cases this module must (and does — see resolve_path) get right:
    Trails -> Mutual funds                RECURRING
    Mutual funds (top level)              NON_RECURRING
    Trails -> Annuities                   RECURRING
    Annuities -> Fixed / Variable         NON_RECURRING
    Cash management -> Money market funds RECURRING
    Cash management -> Brokered CDs       NON_RECURRING
"""
from __future__ import annotations

import re

RECURRING = "RECURRING"
NON_RECURRING = "NON_RECURRING"

# ---------------------------------------------------------------------------
# FIX_SPEC_R10 §A1 — verbatim transcription. Do not paraphrase, infer or
# reorder. A line with no children is a leaf: it gets a single product group
# named after itself (the schema requires product -> group -> line -> class).
# ---------------------------------------------------------------------------
HIERARCHY: list[tuple[str, str, list[str]]] = [
    (RECURRING, "Managed", [
        "Unified Managed Account",
        "JPMCAP",
        "Advisory",
        "Mutual funds advisory portfolio",
        "Customized bond portfolio",
    ]),
    (RECURRING, "Trails", [
        "Mutual funds",
        "Annuities",
        "MAC",
        "529",
    ]),
    (RECURRING, "Cash management", [
        "Money market funds",
        "Premium Deposits",
    ]),
    (NON_RECURRING, "Cash management", [
        "Brokered CDs",
    ]),
    (NON_RECURRING, "Annuities", [
        "Fixed",
        "Variable",
    ]),
    (NON_RECURRING, "Mutual funds", []),
    (NON_RECURRING, "Equities and options", [
        "Equities",
        "Equity Syndicate",
        "Options",
    ]),
    (NON_RECURRING, "Fixed income", [
        "Corporate bonds",
        "Municipal bonds",
        "Government bonds",
        "Fixed Syndicate",
        "Other",
    ]),
    (NON_RECURRING, "Structured products", []),
    (NON_RECURRING, "Insurance", []),
    (NON_RECURRING, "Lending", [
        "Securities-based lending",
        "Margin",
        "Fully Paid Lending",
    ]),
    (NON_RECURRING, "Referrals and revenue share", [
        "Situational partnership",
        "Private Bank referral",
        "Everyday 401K",
        "Other",
        "Donor-advised funds",
        "Defined contribution advisory",
    ]),
]

# Names appearing on BOTH sides of the hierarchy (A2). A hierarchy path whose
# line carries one of these names but whose (line, group) pair is not in A1
# is AMBIGUOUS — resolve_path refuses to classify it (never guess by name).
DUAL_CLASS_LINE_NAMES = frozenset({"annuities", "mutual funds", "cash management"})


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    return s or "unclassified"


def _norm(name: str) -> str:
    """Path-name normalisation for matching extract values against A1
    ('Securities-Based Lending' == 'Securities-based lending')."""
    return re.sub(r"[^a-z0-9]+", " ", str(name).strip().lower()).strip()


def line_id_for(class_id: str, line_name: str) -> str:
    prefix = "rec" if class_id == RECURRING else "nonrec"
    return f"{prefix}_{_slug(line_name)}"


def group_id_for(line_id: str, group_name: str) -> str:
    return f"{line_id}__{_slug(group_name)}"


def classes() -> list[dict]:
    return [
        {"class_id": RECURRING, "class_name": "Recurring", "display_order": 1,
         "data_source": "REAL"},
        {"class_id": NON_RECURRING, "class_name": "Non-recurring", "display_order": 2,
         "data_source": "REAL"},
    ]


def lines() -> list[tuple[str, str, str, int]]:
    """(line_id, line_name, class_id, display_order) in A1 order."""
    out = []
    for order, (cls, line_name, _groups) in enumerate(HIERARCHY, start=1):
        out.append((line_id_for(cls, line_name), line_name, cls, order))
    return out


def groups() -> list[tuple[str, str, str, int]]:
    """(group_id, group_name, line_id, display_order) in A1 order. Leaf lines
    (Mutual funds top-level, Structured products, Insurance) carry one group
    named after the line."""
    out = []
    order = 0
    for cls, line_name, group_names in HIERARCHY:
        lid = line_id_for(cls, line_name)
        for gname in (group_names or [line_name]):
            order += 1
            out.append((group_id_for(lid, gname), gname, lid, order))
    return out


def line_class() -> dict[str, str]:
    return {lid: cls for lid, _n, cls, _o in lines()}


def group_line() -> dict[str, str]:
    return {gid: lid for gid, _n, lid, _o in groups()}


def group_class() -> dict[str, str]:
    lc = line_class()
    return {gid: lc[lid] for gid, lid in group_line().items()}


def recurring_group_ids() -> set[str]:
    return {gid for gid, cls in group_class().items() if cls == RECURRING}


# ------------------------------------------------------------------ matching
# Lookup tables keyed on NORMALISED (line, group) path pairs — the shape the
# real hierarchy extract provides (level_one_product, level_two_product).
_PAIR: dict[tuple[str, str], tuple[str, str, str]] = {}
_LEAF: dict[str, tuple[str, str, str]] = {}          # leaf line -> ids
_UNIQUE_LINE: dict[str, tuple[str, str]] = {}        # unambiguous line -> (class, line_id)
for _cls, _line, _groups in HIERARCHY:
    _lid = line_id_for(_cls, _line)
    _lkey = _norm(_line)
    if _groups:
        for _g in _groups:
            _PAIR[(_lkey, _norm(_g))] = (_cls, _lid, group_id_for(_lid, _g))
    else:
        _LEAF[_lkey] = (_cls, _lid, group_id_for(_lid, _line))
    if _lkey in DUAL_CLASS_LINE_NAMES:
        continue
    if _lkey in _UNIQUE_LINE and _UNIQUE_LINE[_lkey][0] != _cls:
        raise AssertionError(f"line {_line!r} ambiguous but not in DUAL_CLASS_LINE_NAMES")
    _UNIQUE_LINE[_lkey] = (_cls, _lid)


# ------------------------------------------------------------- clawback scope
# FIX_SPEC_R10 D — the CLAWBACK ("Charge Back") driver applies ONLY to
# Annuities, Insurance (product), and Life (product code). Confirmed against
# the corrected A1 hierarchy: Annuities = the non-recurring Annuities line
# (Fixed/Variable) AND the Trails -> Annuities trail group; Insurance = the
# non-recurring Insurance line. "Life" is a PRODUCT CODE gate — the REAL
# product hierarchy extract is operator-local, so the exact code value could
# not be verified here; "LIFE" (case-insensitive) is the assumed identifier,
# recorded as a data gap in PROGRESS.md. Reversals on any other product still
# reconcile through the ordinary buckets but are NOT labelled CLAWBACK.
CLAWBACK_LINE_NAMES = frozenset({"annuities", "insurance"})
CLAWBACK_PRODUCT_CODES = frozenset({"LIFE"})


def clawback_group_ids(lines_rows=None, groups_rows=None) -> set[str]:
    """Group ids in CLAWBACK scope, computed from hierarchy POSITION: every
    group under an Annuities or Insurance line, plus the Trails -> Annuities
    trail group. Pass the actual built dimensions (they may contain
    dynamically-created groups under those lines); defaults to the A1 seed."""
    lines_rows = lines_rows if lines_rows is not None else lines()
    groups_rows = groups_rows if groups_rows is not None else groups()
    scope_lines = {lid for lid, name, _cls, _o in lines_rows
                   if _norm(name) in CLAWBACK_LINE_NAMES}
    out = {gid for gid, _name, lid, _o in groups_rows if lid in scope_lines}
    out |= {gid for gid, name, lid, _o in groups_rows
            if _norm(name) == "annuities"}  # Trails -> Annuities (recurring side)
    return out


class AmbiguousPathError(ValueError):
    """The (line, group) path cannot be classified without guessing by name —
    the caller must STOP and report (FIX_SPEC_R10 A2), never default."""


def resolve_path(level_one: str, level_two: str = "") -> dict | None:
    """Classify a hierarchy path from the extract into the A1 taxonomy.

    Returns {class_id, line_id, group_id, line_name, group_name, known_group}
    or None when the line name is entirely unknown to A1 (the caller decides
    the honest default and must do so LOUDLY). Raises AmbiguousPathError when
    the line name exists on BOTH sides of A1 and the group does not pin the
    side down — classification by name alone is exactly the round-10 bug.
    """
    l1, l2 = _norm(level_one), _norm(level_two)
    hit = _PAIR.get((l1, l2))
    if hit:
        cls, lid, gid = hit
        return {"class_id": cls, "line_id": lid, "group_id": gid,
                "known_group": True}
    # Leaf lines: any (or no) sub-name still belongs to the leaf group — the
    # line itself is unambiguous in A1, so the class comes from its position.
    if l1 in _LEAF:
        cls, lid, gid = _LEAF[l1]
        return {"class_id": cls, "line_id": lid, "group_id": gid,
                "known_group": True}
    if l1 in DUAL_CLASS_LINE_NAMES:
        raise AmbiguousPathError(
            f"hierarchy path ({level_one!r}, {level_two!r}): line {level_one!r} exists "
            f"under BOTH recurring and non-recurring in the corrected hierarchy and the "
            f"group name does not identify the side — refusing to classify by name "
            f"(FIX_SPEC_R10 A2). Fix the extract path or extend the A1 mapping.")
    if l1 in _UNIQUE_LINE:
        # Known, single-class line with a group name A1 does not list: the
        # class still follows from the line's position; the group is created
        # under that line by the caller.
        cls, lid = _UNIQUE_LINE[l1]
        return {"class_id": cls, "line_id": lid,
                "group_id": group_id_for(lid, level_two or level_one),
                "known_group": False}
    return None
