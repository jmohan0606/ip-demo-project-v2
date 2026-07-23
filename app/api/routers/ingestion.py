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
def run_all(dry_run: bool = False, batch_size: int | None = None):
    """Start a full-dataset ingestion: every vertex type first, then every edge type,
    in manifest dependency order, in a background worker. Poll /run-all/status.
    batch_size overrides every entity's configured write-batch size for this run."""
    from app.ingestion.run_all import get_run_all_manager

    return ok(data=get_run_all_manager().start(dry_run=dry_run, batch_size=batch_size).model_dump())


@router.get("/run-all/status")
def run_all_status():
    from app.ingestion.run_all import get_run_all_manager

    return ok(data=get_run_all_manager().status().model_dump())


@router.get("/errors")
def errors(entity_name: str | None = None, limit: int = 50):
    """Persisted ingestion errors (newest first), each with a remediation hint —
    they survive page refreshes and backend restarts (R5 B4)."""
    from app.ingestion.checkpoint_repository import CheckpointRepository
    from app.ingestion.remediation import remediation_for

    rows = CheckpointRepository().list_errors(entity_name, limit)
    for row in rows:
        row["remediation"] = remediation_for(row.get("error_message") or "")
    return ok(data=rows)


@router.get("/validation")
def validation():
    """Graph-truth validation per entity (R5 A5/B6): expected CSV count vs LIVE graph
    count plus a sampled non-key-attribute population check. This — not the
    checkpoint table — answers 'did it really load?'. States: VALIDATED / MISMATCH /
    EMPTY_ATTRS / NOT_LOADED / UNVERIFIABLE, with any checkpoint-vs-graph conflict
    spelled out."""
    from app.ingestion.graph_validation import validate_all_entities

    return ok(data=validate_all_entities())


@router.get("/delete-plan")
def delete_plan():
    """The dependency-ordered delete sequence (edges, then vertices, both in
    reverse manifest order) — rendered in the UI's confirm dialog."""
    return ok(data=IngestionService().delete_plan())


@router.post("/delete/{entity_name}")
def delete_entity(entity_name: str):
    return ok(data=IngestionService().delete_entity(entity_name))


@router.post("/delete-all")
def delete_all():
    return ok(data=IngestionService().delete_all_entities())


@router.post("/clear-checkpoints")
def clear_checkpoints(entity_name: str | None = None):
    """Reset ingestion checkpoint state (batch records + row hashes) WITHOUT touching
    the graph — the recovery path when checkpoints and graph disagree (e.g. after a
    manual GSQL drop, R5 A8). One entity when entity_name is given, else every entity.
    The next load then re-writes everything instead of skipping as 'Unchanged'."""
    return ok(data=IngestionService().clear_checkpoints(entity_name))
