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


@router.get("/reference/reason-codes")
def reason_codes():
    """Eligibility reference (R1): the reason-code rows that define credited
    revenue, straight from the graph."""
    return ok(data=V2RevenueService().reason_codes())


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


# ---------------------------------------------------------------- commentary (stored — never generated on read)

@router.get("/insights/commentary")
def insights_commentary(advisor_id: str, version_id: str = ""):
    from app.agents.nodes.supervisor_agent import SupervisorAgent

    return ok(data=SupervisorAgent().read_commentary(advisor_id, version_id))


@router.get("/insights/versions")
def insights_versions():
    from app.graph.client import get_graph_client
    from app.graph.queries.common import v2_served_by_tier

    result = get_graph_client().run_query("get_commentary_versions", {})
    rows = []
    for obj in result.get("results", []):
        rows = [r.get("attributes", {}) for r in obj.get("versions", [])]
    return ok(data={"versions": rows, "served_by_tier": v2_served_by_tier(result)})


@router.get("/insights/evaluations")
def insights_evaluations(version_id: str = ""):
    """LLM-as-judge verdicts (R5) for a commentary version ("" = all versions).
    Advisory only — surfaced in the UI, never a publication gate."""
    return ok(data=V2RevenueService().commentary_evaluations(version_id))


@router.post("/insights/generate")
def insights_generate(notes: str = ""):
    """Trigger the batch generation workflow — a NEW version every run; prior
    versions are never deleted. The ONLY path that reaches the LLM."""
    from app.v2.commentary.generation_workflow import run_generation

    return ok(data=run_generation(notes))


@router.get("/insights/generate/status")
def insights_generate_status():
    from app.v2.commentary.generation_workflow import get_status

    return ok(data=get_status())


@router.get("/evidence")
def evidence(driver_id: str, version_id: str = ""):
    from app.graph.client import get_graph_client
    from app.graph.queries.common import v2_served_by_tier

    result = get_graph_client().run_query(
        "get_evidence", {"driver_id": driver_id, "version_id": version_id})
    rows = []
    for obj in result.get("results", []):
        rows = [r.get("attributes", {}) for r in obj.get("evidence", [])]
    return ok(data={"evidence": rows, "served_by_tier": v2_served_by_tier(result)})


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
