"""Month vertex generation (EXTRACTION_SPEC §5).

Pure deterministic calendar arithmetic. billable_days = business days Mon-Fri
(no holiday calendar available) — DERIVED, trivially replaceable by the client's
billing calendar. index_return = 0.0, DUMMY until an index source exists.
"""
from __future__ import annotations

import calendar
from datetime import date


MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def business_days(year: int, month: int) -> int:
    days = calendar.monthrange(year, month)[1]
    return sum(1 for d in range(1, days + 1) if date(year, month, d).weekday() < 5)


def month_row(month_id: str, prior_month_id: str, is_current: bool) -> dict:
    year, month_no = int(month_id[:4]), int(month_id[4:6])
    days = calendar.monthrange(year, month_no)[1]
    return {
        "month_id": month_id,
        "year": year,
        "month_no": month_no,
        "month_name": f"{MONTH_NAMES[month_no]} {year}",
        "quarter": (month_no - 1) // 3 + 1,
        "start_dt": f"{year:04d}-{month_no:02d}-01 00:00:00",
        "end_dt": f"{year:04d}-{month_no:02d}-{days:02d} 00:00:00",
        "calendar_days": days,
        "billable_days": business_days(year, month_no),
        "prior_month_id": prior_month_id,
        "index_return": 0.0,
        "is_current": is_current,
        "data_source": "DERIVED",
    }


def month_rows(month_ids: list[str]) -> list[dict]:
    """Ordered month vertices for the given YYYYMM ids. prior_month_id is '' for
    the first month IN SCOPE (even if a calendar-prior month exists)."""
    ordered = sorted(month_ids)
    rows = []
    for i, mid in enumerate(ordered):
        rows.append(month_row(mid, ordered[i - 1] if i > 0 else "", i == len(ordered) - 1))
    return rows
