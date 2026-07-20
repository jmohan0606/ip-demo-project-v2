from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware.error_handlers import register_exception_handlers
from app.api.middleware.correlation import CorrelationIdMiddleware
from app.api.routers.adapters import router as adapters_router
from app.api.routers.config import router as config_router
from app.api.routers.health import router as health_router
from app.api.routers.manifest import router as manifest_router
from app.config.constants import GRAPH_NAME, SCHEMA_PREFIX
from app.config.settings import get_settings
from app.models.common import HealthResponse
from app.shared.logging import configure_logging
from app.api.routers.config_status import router as config_status_router
from app.api.routers.graph_access import router as graph_access_router
from app.api.routers.guardrails import router as guardrails_router
from app.api.routers.env_health import router as env_health_router
from app.api.routers.observability import router as observability_router
from app.api.routers.ingestion import router as ingestion_router
from app.api.routers.tigergraph_foundation import router as tigergraph_foundation_router
from app.api.routers.v2 import router as v2_router
configure_logging(); settings=get_settings()


app=FastAPI(title=settings.app_name, version=settings.app_version, description='iPerform V2 — Revenue Trends & AI Commentary API')
register_exception_handlers(app)
# Correlation-id + request logging (added last below via add_middleware so it runs
# outermost — id is bound before any handler/adapter emits a log line).
@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok', app_name=settings.app_name, app_version=settings.app_version, environment=settings.app_env, graph_name=GRAPH_NAME, schema_prefix=SCHEMA_PREFIX)
app.include_router(health_router)
app.include_router(config_router)
app.include_router(adapters_router)
app.include_router(manifest_router)
app.include_router(tigergraph_foundation_router)
app.include_router(v2_router)
app.include_router(ingestion_router)
app.include_router(observability_router)
app.include_router(guardrails_router)
app.include_router(env_health_router)
app.include_router(graph_access_router)
app.include_router(config_status_router)

if settings.enable_diagnostics_routes:
    from app.api.routers.diagnostics import router as diagnostics_router
    app.include_router(diagnostics_router)

app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001","http://127.0.0.1:3001"],
    # Allow the GitHub Codespaces forwarded frontend origin (e.g.
    # https://<codespace>-3001.app.github.dev) so an external browser can reach the API.
    allow_origin_regex=r"https://.*\.app\.github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    # `python -m app.api.main` — env-driven host/port (API_HOST default 0.0.0.0 so the server is
    # reachable through Codespaces port forwarding; API_PORT default 8001).
    import uvicorn

    uvicorn.run("app.api.main:app", host=settings.api_host, port=settings.api_port)
