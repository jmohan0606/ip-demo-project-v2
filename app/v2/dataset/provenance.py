"""Centralised data_source stamping (FIX_SPEC_R4 B3).

ONE place decides which provenance flag every written row carries, so the
sample generator and the real-data builder tag identically-shaped data
identically. The rules (CLAUDE.md §3.3):

  REAL     straight from Postgres columns — advisor, product hierarchy,
           account identity, transaction rows (credited_amt, reason_cd,
           grid_type, …), the reason-code / driver-cause reference seeds
           (client documentation).
  DERIVED  computed by us from real data — month calendar (billable_days),
           monthly_product_revenue, revenue_change, and revenue_driver rows
           for causes whose maths runs on real inputs (attribution stamps
           these per cause via CAUSE_DATA_SOURCE).
  ASSUMED  rests on a stated assumption — `posting_month_id` on each
           transaction (= trade month; no iComp feed identifies closed
           months). This is a FIELD-level assumption inside a row that is
           otherwise REAL: the row keeps data_source=REAL and the assumption
           is stated in the schema, the evidence and the report. A row-level
           ASSUMED flag is reserved for rows whose primary figure is assumed.
  DUMMY    placeholder awaiting a data source — account_month_balance rows,
           and the MARKET / NET_FLOW drivers (attribution stamps those).

`revenue_driver` rows are deliberately absent from ARTIFACT_SOURCE: their flag
is per-cause, stamped by app/v2/drivers/attribution.CAUSE_DATA_SOURCE — this
module only validates that the stamp arrived.
"""
from __future__ import annotations

from typing import Iterable

REAL = "REAL"
DERIVED = "DERIVED"
ASSUMED = "ASSUMED"
DUMMY = "DUMMY"
VALID_SOURCES = frozenset({REAL, DERIVED, ASSUMED, DUMMY})

# artifact (vertex CSV stem) -> the data_source every row of it carries.
ARTIFACT_SOURCE: dict[str, str] = {
    # straight from Postgres columns / client documentation seeds
    "advisor": REAL,
    "revenue_class": REAL,
    "product_line": REAL,
    "product_group": REAL,
    "product": REAL,
    "account": REAL,
    "driver_cause": REAL,
    "reason_code": REAL,
    "revenue_transaction": REAL,
    # computed by us from real data
    "month": DERIVED,
    "monthly_product_revenue": DERIVED,
    "revenue_change": DERIVED,
    # placeholder awaiting billable-assets data
    "account_month_balance": DUMMY,
    # "revenue_driver" — per-cause, stamped by attribution (see docstring)
}


def source_for(artifact: str) -> str:
    """The data_source rows of this artifact must carry."""
    try:
        return ARTIFACT_SOURCE[artifact]
    except KeyError:
        raise KeyError(
            f"No provenance rule for artifact '{artifact}' — add it to "
            "app/v2/dataset/provenance.ARTIFACT_SOURCE (never guess a flag)."
        ) from None


def stamp(rows: Iterable[dict], artifact: str) -> list[dict]:
    """Set data_source on every row per the artifact's rule (in place).
    Rows that already carry a valid flag keep it — attribution and the
    calendar stamp their own rows; this is the single fallback authority."""
    flag = source_for(artifact)
    out = []
    for r in rows:
        if not r.get("data_source"):
            r["data_source"] = flag
        out.append(r)
    return out


def require_stamped(artifact: str, rows: Iterable[dict]) -> None:
    """A row must NEVER be written with a blank or invalid data_source."""
    for i, r in enumerate(rows):
        value = r.get("data_source")
        if value not in VALID_SOURCES:
            raise ValueError(
                f"{artifact} row {i} has data_source={value!r} — every written "
                f"row must carry one of {sorted(VALID_SOURCES)} (FIX_SPEC_R4 B3)."
            )
