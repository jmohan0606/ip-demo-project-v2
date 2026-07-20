from __future__ import annotations
import logging
from contextlib import asynccontextmanager
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
from app.api.routers.agentic_ai import router as agentic_ai_router
from app.api.routers.graph_access import router as graph_access_router
from app.api.routers.ai_chat import router as ai_chat_router
from app.api.routers.guardrails import router as guardrails_router
from app.api.routers.env_health import router as env_health_router
from app.api.routers.insights_coaching import router as insights_coaching_router
from app.api.routers.feedback_learning import router as feedback_learning_router
from app.api.routers.recommendations import router as recommendations_router
from app.api.routers.search_notifications import router as search_notifications_router
from app.api.routers.impact_ledger import router as impact_ledger_router
from app.api.routers.opportunities import router as opportunities_router
from app.api.routers.predictions import router as predictions_router
from app.api.routers.graph_insights import router as graph_insights_router
from app.api.routers.models import router as models_router
from app.api.routers.architecture import router as architecture_router
from app.api.routers.evaluation import router as evaluation_router
from app.api.routers.observability import router as observability_router
from app.api.routers.mcp_tools import router as mcp_tools_router
from app.api.routers.embeddings import router as embeddings_router
from app.api.routers.features import router as features_router
from app.api.routers.memory import router as memory_router
from app.api.routers.knowledge import router as knowledge_router
from app.api.routers.ingestion import router as ingestion_router
from app.api.routers.agp import router as agp_router
from app.api.routers.crm import router as crm_router
from app.api.routers.explainability import router as explainability_router
from app.api.routers.advisor360 import router as advisor360_router
from app.api.routers.hierarchy import router as hierarchy_router
from app.api.routers.whatif import router as whatif_router
from app.api.routers.scope import router as scope_router
from app.api.routers.export import router as export_router
from app.api.routers.revenue import router as revenue_router
from app.api.routers.graph_viz import router as graph_viz_router
from app.api.routers.peers import router as peers_router
from app.api.routers.coaching import router as coaching_router
from app.api.routers.client360 import router as client360_router
from app.api.routers.tigergraph_foundation import router as tigergraph_foundation_router
configure_logging(); settings=get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Section 13.2: replay the impact ledger into the (in-memory) graph store on boot,
    # so completed recommendations' injected transactions survive a restart.
    try:
        from app.recommendations.lifecycle import RecommendationLifecycleService
        report = RecommendationLifecycleService().replay_on_boot()
        logging.getLogger("app").info("Section-13 lifecycle boot replay: %s", report)
    except Exception as exc:  # never block startup on replay
        logging.getLogger("app").warning("lifecycle boot replay skipped: %s", exc)
    yield


app=FastAPI(title=settings.app_name, version=settings.app_version, description='Local enterprise demo API for iPerform Insights & Coaching', lifespan=lifespan)
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


app.include_router(ingestion_router)
app.include_router(agp_router)
app.include_router(crm_router)
app.include_router(explainability_router)
app.include_router(advisor360_router)
app.include_router(hierarchy_router)
app.include_router(whatif_router)
app.include_router(scope_router)
app.include_router(export_router)
app.include_router(revenue_router)
app.include_router(graph_viz_router)
app.include_router(peers_router)
app.include_router(coaching_router)
app.include_router(client360_router)

app.include_router(knowledge_router)

app.include_router(memory_router)

app.include_router(features_router)

app.include_router(embeddings_router)

app.include_router(predictions_router)
app.include_router(graph_insights_router)
app.include_router(models_router)
app.include_router(architecture_router)
app.include_router(evaluation_router)
app.include_router(observability_router)
app.include_router(mcp_tools_router)

app.include_router(opportunities_router)

app.include_router(recommendations_router)
app.include_router(search_notifications_router)
app.include_router(impact_ledger_router)

app.include_router(feedback_learning_router)

app.include_router(insights_coaching_router)

app.include_router(ai_chat_router)
app.include_router(guardrails_router)
app.include_router(env_health_router)


app.include_router(graph_access_router)

app.include_router(agentic_ai_router)



app.include_router(config_status_router)

if settings.enable_diagnostics_routes:
    from app.api.routers.diagnostics import router as diagnostics_router
    app.include_router(diagnostics_router)

app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001"],
    # Allow the GitHub Codespaces forwarded frontend origin (e.g.
    # https://<codespace>-3000.app.github.dev) so an external browser can reach the API.
    allow_origin_regex=r"https://.*\.app\.github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    # `python -m app.api.main` — env-driven host/port (API_HOST default 0.0.0.0 so the server is
    # reachable through Codespaces port forwarding; API_PORT default 8000). See run_api.sh and
    # TROUBLESHOOTING.md "Backend unreachable from the browser".
    import uvicorn

    uvicorn.run("app.api.main:app", host=settings.api_host, port=settings.api_port)
