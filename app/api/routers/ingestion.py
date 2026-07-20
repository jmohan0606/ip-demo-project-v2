from __future__ import annotations

from fastapi import APIRouter

from app.ingestion.ingestion_service import IngestionService
from app.models.ingestion import IngestionRunRequest
from app.shared.responses import ok

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.get("/entities")
def entities():
    return ok(data=IngestionService().list_entities())


@router.get("/batches")
def batches():
    return ok(data=IngestionService().list_batches())


@router.post("/run")
def run_ingestion(request: IngestionRunRequest):
    response = IngestionService().run_entity_ingestion(request)
    return ok(data=response.model_dump())


@router.post("/run-all")
def run_all(dry_run: bool = False):
    """Start a full-dataset ingestion: every vertex type first, then every edge type,
    in manifest dependency order, in a background worker. Poll /run-all/status."""
    from app.ingestion.run_all import get_run_all_manager

    return ok(data=get_run_all_manager().start(dry_run=dry_run).model_dump())


@router.get("/run-all/status")
def run_all_status():
    from app.ingestion.run_all import get_run_all_manager

    return ok(data=get_run_all_manager().status().model_dump())
