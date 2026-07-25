"""Revenue eligibility (FIX_SPEC R1, rule replaced by FIX_SPEC_R10 B) — the
credited-revenue definition.

Client's rule as of round 10 (supersedes the prior Confluence-based split):

    Eligible / credited:      reason code NULL, empty, or __NONE__ — ONLY.
    Ineligible / non-credited: ANY reason code starting with 9 (9E, 9G, 9C, 9S,
                               94, 91, 92, 9L, ...), except the excluded set.
    Excluded:                 the reversal/error codes 9R, 98, 99, 9H, 9X, XX —
                              unchanged; outside Total Revenue entirely.

    Credited Revenue additionally requires the product's grid_type to be a
    credited grid type AND days_to_process <= 90 (both unchanged this round).

The ONLY round-10 change: 91/92/9L — previously credited-but-incentive-
ineligible — are now NON_CREDITED like every other 9… code. The three-state
model is preserved; the excluded set is untouched.

Eligibility is DATA-DRIVEN: the reason set is read from phx_dm_v2_reason_code
rows (seeded below, loaded like any other vertex), and the grid-type / 90-day
filters come from settings (CREDITED_GRID_TYPES, MAX_PROCESSING_DAYS). Seeding
a new code or changing config changes behaviour with NO code change.

A genuinely NULL/blank reason code normalises to __NONE__ and is ELIGIBLE
(normalize_reason) — a missing code must never land in a spurious
non-credited bucket.
"""
from __future__ import annotations

from datetime import date, datetime

NO_REASON = "__NONE__"

CREDITED = "CREDITED"
NON_CREDITED = "NON_CREDITED"
EXCLUDED = "EXCLUDED"
# Classification buckets beyond the three reason-code states:
LATE = "LATE"                # otherwise credited but days_to_process > max (90-day rule)
OUT_OF_GRID = "OUT_OF_GRID"  # product grid_type not in CREDITED_GRID_TYPES config

# Seed rows for phx_dm_v2_reason_code — client documentation, data_source REAL.
# (reason_code, description, ui_mapping, owned_by, eligibility,
#  include_in_credited, incentive_eligible, display_order)
REASON_CODE_SEED: list[dict] = [
    {"reason_code": NO_REASON, "description": "No reason code — Grid transaction",
     "ui_mapping": "Grid", "owned_by": "PCE", "eligibility": CREDITED,
     "include_in_credited": True, "incentive_eligible": True, "display_order": 1},
    # R10 B — 91/92/9L flipped Credited -> Non-Credited: every 9… code outside
    # the excluded set is ineligible; only NULL/empty/__NONE__ is credited.
    {"reason_code": "91", "description": "Less than Minimum – Equity",
     "ui_mapping": "Equity – below minimum", "owned_by": "PCE",
     "eligibility": NON_CREDITED, "include_in_credited": False, "incentive_eligible": False,
     "display_order": 2},
    {"reason_code": "92", "description": "Less than Minimum – Mutual Fund",
     "ui_mapping": "Mutual funds – below minimum", "owned_by": "PCE",
     "eligibility": NON_CREDITED, "include_in_credited": False, "incentive_eligible": False,
     "display_order": 3},
    {"reason_code": "9L", "description": "Full Month LOA",
     "ui_mapping": "LOA", "owned_by": "iComp",
     "eligibility": NON_CREDITED, "include_in_credited": False, "incentive_eligible": False,
     "display_order": 4},
    {"reason_code": "9E", "description": "Minimum Household Policy",
     "ui_mapping": "Small households", "owned_by": "PCE", "eligibility": NON_CREDITED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 5},
    {"reason_code": "9G", "description": "Inherited Account",
     "ui_mapping": "Transferred accounts", "owned_by": "PCE", "eligibility": NON_CREDITED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 6},
    {"reason_code": "9C", "description": "Personal Transactions",
     "ui_mapping": "Personal accounts", "owned_by": "PCE", "eligibility": NON_CREDITED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 7},
    {"reason_code": "9S", "description": "Account Block – Supervision",
     "ui_mapping": "Other", "owned_by": "PCE", "eligibility": NON_CREDITED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 8},
    {"reason_code": "94", "description": "Account Block – Other",
     "ui_mapping": "Other", "owned_by": "PCE", "eligibility": NON_CREDITED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 9},
    {"reason_code": "9R", "description": "Rep Code Not Found",
     "ui_mapping": "", "owned_by": "PCE", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 10},
    {"reason_code": "98", "description": "Sales After Termination",
     "ui_mapping": "", "owned_by": "iComp", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 11},
    {"reason_code": "99", "description": "Sales During Inactive Period",
     "ui_mapping": "", "owned_by": "iComp", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 12},
    {"reason_code": "9H", "description": "Sales Before Rep Code Assignment",
     "ui_mapping": "", "owned_by": "iComp", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 13},
    {"reason_code": "9X", "description": "A delete of the transaction",
     "ui_mapping": "", "owned_by": "PCE", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 14},
    {"reason_code": "XX", "description": "Transaction removed by the SOR for Annuities",
     "ui_mapping": "", "owned_by": "PCE", "eligibility": EXCLUDED,
     "include_in_credited": False, "incentive_eligible": False, "display_order": 15},
]


def seed_rows() -> list[dict]:
    """The reason_code vertex rows (adds data_source=REAL)."""
    return [{**r, "data_source": "REAL"} for r in REASON_CODE_SEED]


def reason_map(rows: list[dict] | None = None) -> dict[str, dict]:
    """reason_code -> row. Defaults to the seed; pass graph-loaded rows at
    runtime so seeding a new code changes behaviour with no code change."""
    return {str(r["reason_code"]): r for r in (rows if rows is not None else seed_rows())}


def normalize_reason(reason_cd: str | None) -> str:
    """Null/blank reason codes map to __NONE__ (a Grid transaction)."""
    value = str(reason_cd or "").strip()
    return value if value else NO_REASON


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def days_to_process(trade_dt, proc_dt) -> int:
    """proc_dt - trade_dt in days (feeds the client's 90-day rule)."""
    t, p = _as_date(trade_dt), _as_date(proc_dt)
    if t is None or p is None:
        return 0
    return (p - t).days


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y", "t")


def reason_eligibility(reason_cd: str | None, reasons: dict[str, dict]) -> str:
    """CREDITED | NON_CREDITED | EXCLUDED for a transaction's reason code.
    An UNKNOWN code is treated as NON_CREDITED (kept in Total, kept out of
    Credited) — the honest default: never credit revenue we cannot classify."""
    row = reasons.get(normalize_reason(reason_cd))
    if row is None:
        return NON_CREDITED
    if str(row.get("eligibility")) == EXCLUDED:
        return EXCLUDED
    return CREDITED if _bool(row.get("include_in_credited")) else NON_CREDITED


def classify(
    reason_cd: str | None,
    grid_type: str | None,
    txn_days_to_process: int,
    reasons: dict[str, dict],
    credited_grid_types: set[str],
    max_processing_days: int,
) -> str:
    """Full classification of one transaction for the credited computation:
    CREDITED | NON_CREDITED | EXCLUDED | LATE | OUT_OF_GRID.

    Only CREDITED rows count in credited revenue. NON_CREDITED and LATE stay in
    Total revenue; EXCLUDED and OUT_OF_GRID rows are outside every figure under
    the current config."""
    if str(grid_type or "PRODUCT_TYPE") not in credited_grid_types:
        return OUT_OF_GRID
    state = reason_eligibility(reason_cd, reasons)
    if state != CREDITED:
        return state
    if int(txn_days_to_process or 0) > max_processing_days:
        return LATE
    return CREDITED


def incentive_eligible(reason_cd: str | None, reasons: dict[str, dict]) -> bool:
    row = reasons.get(normalize_reason(reason_cd))
    return _bool(row.get("incentive_eligible")) if row else False
