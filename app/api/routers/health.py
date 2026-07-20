from __future__ import annotations
from fastapi import APIRouter
from app.models.runtime import RuntimeHealthReport
from app.services.runtime_status_service import RuntimeStatusService

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/runtime", response_model=RuntimeHealthReport)
def runtime_health() -> RuntimeHealthReport:
    return RuntimeStatusService().get_health_report()
