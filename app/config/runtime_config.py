from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class RuntimeConfig:
    app_name: str = os.getenv("APP_NAME", "iPerform Insights & Coaching")
    app_env: str = os.getenv("APP_ENV", "local")
    app_debug: bool = _bool("APP_DEBUG", True)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = _int("API_PORT", 8000)
    api_base_url: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    cors_allowed_origins: str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    openai_timeout_seconds: int = _int("OPENAI_TIMEOUT_SECONDS", 60)

    graph_access_strategy: str = os.getenv("GRAPH_ACCESS_STRATEGY", "mcp_first")
    graph_fallback_order: str = os.getenv("GRAPH_FALLBACK_ORDER", "mcp,rest,mock")

    tigergraph_mcp_enabled: bool = _bool("TIGERGRAPH_MCP_ENABLED", False)
    tigergraph_mcp_server_url: str = os.getenv("TIGERGRAPH_MCP_SERVER_URL", "")
    tigergraph_mcp_transport: str = os.getenv("TIGERGRAPH_MCP_TRANSPORT", "http")
    tigergraph_mcp_timeout_seconds: int = _int("TIGERGRAPH_MCP_TIMEOUT_SECONDS", 30)

    tigergraph_rest_enabled: bool = _bool("TIGERGRAPH_REST_ENABLED", False)
    tigergraph_host: str = os.getenv("TIGERGRAPH_HOST", "")
    tigergraph_graph: str = os.getenv("TIGERGRAPH_GRAPH", "iperform_insights_coaching_demo")
    tigergraph_username: str = os.getenv("TIGERGRAPH_USERNAME", "")
    tigergraph_password: str = os.getenv("TIGERGRAPH_PASSWORD", "")
    tigergraph_secret: str = os.getenv("TIGERGRAPH_SECRET", "")
    tigergraph_token: str = os.getenv("TIGERGRAPH_TOKEN", "")
    tigergraph_use_token: bool = _bool("TIGERGRAPH_USE_TOKEN", True)
    tigergraph_timeout_seconds: int = _int("TIGERGRAPH_TIMEOUT_SECONDS", 30)

    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "data/sqlite/iperform.db")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
    chroma_collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "iperform_knowledge_base")
    documents_dir: str = os.getenv("DOCUMENTS_DIR", "data/documents")

    feature_store_backend: str = os.getenv("FEATURE_STORE_BACKEND", "sqlite")
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "chroma")
    graph_embedding_backend: str = os.getenv("GRAPH_EMBEDDING_BACKEND", "mock")
    similarity_top_k: int = _int("SIMILARITY_TOP_K", 10)

    agent_runtime: str = os.getenv("AGENT_RUNTIME", "langgraph")
    langgraph_enabled: bool = _bool("LANGGRAPH_ENABLED", True)
    agent_trace_enabled: bool = _bool("AGENT_TRACE_ENABLED", True)
    memory_write_enabled: bool = _bool("MEMORY_WRITE_ENABLED", True)
    feedback_write_enabled: bool = _bool("FEEDBACK_WRITE_ENABLED", True)

    mock_data_enabled: bool = _bool("MOCK_DATA_ENABLED", True)
    demo_mode: bool = _bool("DEMO_MODE", True)
    load_preloaded_demo_data: bool = _bool("LOAD_PRELOADED_DEMO_DATA", True)

    auth_mode: str = os.getenv("AUTH_MODE", "persona_simulation")
    enable_login: bool = _bool("ENABLE_LOGIN", False)
    default_persona: str = os.getenv("DEFAULT_PERSONA", "Advisor")
    default_scope_type: str = os.getenv("DEFAULT_SCOPE_TYPE", "Advisor")
    default_scope_id: str = os.getenv("DEFAULT_SCOPE_ID", "ADV0001")

    ingestion_batch_size: int = _int("INGESTION_BATCH_SIZE", 500)
    ingestion_retry_enabled: bool = _bool("INGESTION_RETRY_ENABLED", True)
    ingestion_checkpoint_enabled: bool = _bool("INGESTION_CHECKPOINT_ENABLED", True)
    ingestion_upload_dir: str = os.getenv("INGESTION_UPLOAD_DIR", "data/uploads")

    enable_observability: bool = _bool("ENABLE_OBSERVABILITY", True)
    enable_runtime_validation: bool = _bool("ENABLE_RUNTIME_VALIDATION", True)
    enable_deep_hardening: bool = _bool("ENABLE_DEEP_HARDENING", True)

    def ensure_local_dirs(self) -> None:
        for path in [
            self.sqlite_db_path,
            self.chroma_persist_dir,
            self.documents_dir,
            self.ingestion_upload_dir,
        ]:
            p = Path(path)
            if p.suffix:
                p.parent.mkdir(parents=True, exist_ok=True)
            else:
                p.mkdir(parents=True, exist_ok=True)


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig()
