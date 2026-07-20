from __future__ import annotations

from typing import Any

from app.config.settings import get_settings
from app.graph.tier_log import get_tier_log


class AdapterStatusService:
    """Describes the selected adapters (modes) and per-tier usage counters.

    Descriptive only — /env-health actively exercises the adapters; this endpoint
    reports what is configured and which tier actually served recent requests.
    """

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        return {
            "modes": {
                "graph_client_mode": settings.graph_client_mode,
                "llm_client_mode": settings.llm_client_mode,
                "data_set": settings.data_set,
                "commentary_mode": settings.commentary_mode,
            },
            "graph": {
                "graph_name": settings.tigergraph_graph,
                "host": settings.tg_host,
                "schema_prefix": settings.tigergraph_schema_prefix,
            },
            "tier_usage": get_tier_log().summary(),
        }
