from __future__ import annotations

from fastapi import APIRouter

from app.services.tigergraph_foundation_service import TigerGraphFoundationService
from app.shared.responses import ok

router = APIRouter(prefix="/tigergraph-foundation", tags=["TigerGraph Foundation"])


@router.get("/inventory")
def schema_inventory():
    service = TigerGraphFoundationService()
    return ok(data=service.get_schema_inventory().model_dump())


@router.get("/files")
def schema_files():
    service = TigerGraphFoundationService()
    return ok(
        data={
            "schema_files": service.list_schema_files(),
            "v1_query_files": service.list_v1_query_files(),
        }
    )


@router.get("/validate-prefix")
def validate_prefix():
    return ok(data=TigerGraphFoundationService().validate_prefix_convention())
