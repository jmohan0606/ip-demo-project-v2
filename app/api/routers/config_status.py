from __future__ import annotations

from fastapi import APIRouter

from app.config import get_runtime_config
from app.shared.responses import ok

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/status")
def config_status():
    config = get_runtime_config()
    return ok(
        data={
            "app_name": config.app_name,
            "app_env": config.app_env,
            "api_base_url": config.api_base_url,
            "frontend_url": config.frontend_url,
            "graph_access_strategy": config.graph_access_strategy,
            "tigergraph_mcp_enabled": config.tigergraph_mcp_enabled,
            "tigergraph_rest_enabled": config.tigergraph_rest_enabled,
            "mock_data_enabled": config.mock_data_enabled,
            "sqlite_db_path": config.sqlite_db_path,
            "chroma_persist_dir": config.chroma_persist_dir,
            "chroma_collection_name": config.chroma_collection_name,
            "agent_runtime": config.agent_runtime,
            "enable_login": config.enable_login,
            "default_persona": config.default_persona,
            "default_scope_type": config.default_scope_type,
            "default_scope_id": config.default_scope_id,
        }
    )
