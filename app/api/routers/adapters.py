from fastapi import APIRouter

from app.services.adapter_status_service import AdapterStatusService
from app.shared.responses import ok

router = APIRouter(prefix="/adapters", tags=["Adapters"])


@router.get("/status")
def adapter_status():
    return ok(data=AdapterStatusService().status())
