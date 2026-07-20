from __future__ import annotations

from app.config.constants import GRAPH_NAME, SCHEMA_PREFIX
from app.config.settings import get_settings
from app.models.enums import RuntimeComponentStatus
from app.models.runtime import ComponentHealth, RuntimeHealthReport


class RuntimeStatusService:
    """Lightweight runtime report: configured modes as components. For active
    probes (real graph query, real LLM generation) use /env-health instead."""

    def get_health_report(self) -> RuntimeHealthReport:
        settings = get_settings()
        components = [
            ComponentHealth(
                component_name="graph_client",
                status=RuntimeComponentStatus.HEALTHY,
                detail=f"mode={settings.graph_client_mode}",
                configured=True,
            ),
            ComponentHealth(
                component_name="llm_client",
                status=RuntimeComponentStatus.HEALTHY,
                detail=f"mode={settings.llm_client_mode}",
                configured=True,
            ),
        ]
        overall = (
            RuntimeComponentStatus.HEALTHY
            if all(c.status == RuntimeComponentStatus.HEALTHY for c in components)
            else RuntimeComponentStatus.DEGRADED
        )
        return RuntimeHealthReport(
            application=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
            graph_name=GRAPH_NAME,
            schema_prefix=SCHEMA_PREFIX,
            overall_status=overall,
            components=components,
        )
