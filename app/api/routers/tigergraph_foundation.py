from __future__ import annotations

from fastapi import APIRouter

from app.services.tigergraph_foundation_service import TigerGraphFoundationService
from app.shared.responses import ok

router = APIRouter(prefix="/tigergraph-foundation", tags=["TigerGraph Foundation"])


@router.get("/inventory")
def schema_inventory():
    return ok(data=TigerGraphFoundationService().get_schema_inventory())


@router.get("/files")
def schema_files():
    service = TigerGraphFoundationService()
    return ok(
        data={
            "schema_files": service.list_schema_files(),
            "query_files": service.list_query_files(),
        }
    )


@router.get("/validate-prefix")
def validate_prefix():
    return ok(data=TigerGraphFoundationService().validate_prefix_convention())
