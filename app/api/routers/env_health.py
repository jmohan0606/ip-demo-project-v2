from __future__ import annotations

from fastapi import APIRouter

from app.services.environment_health_service import EnvironmentHealthService
from app.shared.responses import ok

router = APIRouter(prefix="/env-health", tags=["Connection & Environment Health"])


@router.get("")
@router.get("/")
def env_health():
    """Active setup-verification for the client environment: TigerGraph (reachable, auth/SSL,
    graph, schema, per-vertex-type row counts), LLM (real test generation + latency + response),
    Embedding (real embed + configured dimension), Chroma (reachable + collection count). Each is
    green/red with the real error if red. This is the first screen to open on the client machine."""
    return ok(data=EnvironmentHealthService().report())
