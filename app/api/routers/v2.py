"""V2 API — everything the four Results screens and the ops screens read.

All numbers come from catalogued GQ queries over graph data. Commentary
endpoints RETRIEVE stored, versioned text (COMMENTARY_MODE=stored — never
generated on read; the generation workflow has its own POST).
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.shared.responses import ok
from app.v2.drivers.service import V2DriverService
from app.v2.revenue.service import V2RevenueService

router = APIRouter(prefix="/api/v2", tags=["V2"])


# ---------------------------------------------------------------- reference

@router.get("/reference/advisors")
def advisors():
    return ok(data=V2RevenueService().advisors())


@router.get("/reference/months")
def months():
    return ok(data=V2RevenueService().months())


@router.get("/reference/product-hierarchy")
def product_hierarchy():
    return ok(data=V2RevenueService().product_hierarchy())


@router.get("/reference/driver-causes")
def driver_causes():
    return ok(data=V2RevenueService().driver_causes())


# ---------------------------------------------------------------- trends

@router.get("/trends/revenue")
def trends_revenue(advisor_id: str, from_month: str, to_month: str):
    return ok(data=V2RevenueService().monthly_revenue(advisor_id, from_month, to_month))


@router.get("/trends/changes")
def trends_changes(advisor_id: str, from_month: str, to_month: str):
    return ok(data=V2RevenueService().revenue_changes(advisor_id, from_month, to_month))


# ---------------------------------------------------------------- insights

@router.get("/insights/chart")
def insights_chart(advisor_id: str, from_month: str, to_month: str):
    return ok(data=V2RevenueService().monthly_totals(advisor_id, from_month, to_month))


@router.get("/insights/drivers")
def insights_drivers(advisor_id: str, from_month: str, to_month: str,
                     result_limit: int = Query(default=100, le=10000)):
    return ok(data=V2DriverService().change_drivers(advisor_id, from_month, to_month, result_limit))


# ---------------------------------------------------------------- drill-down

@router.get("/transactions")
def transactions(advisor_id: str, month_id: str, group_id: str = "",
                 result_limit: int = Query(default=1000, le=10000)):
    return ok(data=V2RevenueService().transactions(advisor_id, month_id, group_id, result_limit))


@router.get("/evidence/reproduce")
def evidence_reproduce(advisor_id: str, product_group: str, from_month: str, to_month: str):
    return ok(data=V2RevenueService().product_revenue_change(
        advisor_id, product_group, from_month, to_month))


# ---------------------------------------------------------------- ops

@router.get("/ops/counts")
def ops_counts():
    return ok(data=V2RevenueService().ingestion_counts())


@router.get("/ops/advisor-summary")
def ops_advisor_summary(advisor_id: str):
    return ok(data=V2RevenueService().advisor_month_summary(advisor_id))


@router.get("/ops/reconciliation")
def ops_reconciliation(advisor_id: str, from_month: str, to_month: str):
    return ok(data=V2DriverService().reconciliation(advisor_id, from_month, to_month))
