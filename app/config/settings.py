from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="iPerform Insights & Coaching", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="11.0.1", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Structured logging / CloudWatch-ready sink (see app/shared/logging.py docstring) ---
    # log_sink selects WHERE structured JSON logs go, so switching for ECS/Fargate is a
    # config change, not a code change:
    #   file       → RotatingFileHandler to logs/app.log (local default)
    #   stdout     → structured JSON to stdout (Fargate ships stdout straight to CloudWatch)
    #   cloudwatch → watchtower CloudWatchLogHandler (falls back to stdout if unavailable)
    log_sink: str = Field(default="file", alias="LOG_SINK")  # file | stdout | cloudwatch
    log_json: bool = Field(default=True, alias="LOG_JSON")  # JSON when true; human console when false
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    log_file_name: str = Field(default="app.log", alias="LOG_FILE_NAME")
    log_rotate_max_bytes: int = Field(default=10_485_760, alias="LOG_ROTATE_MAX_BYTES")  # 10 MB
    log_rotate_backup_count: int = Field(default=5, alias="LOG_ROTATE_BACKUP_COUNT")
    # CloudWatch (log_sink=cloudwatch) — used only by the watchtower handler.
    log_cloudwatch_group: str = Field(default="/iperform/insights-coaching", alias="LOG_CLOUDWATCH_GROUP")
    log_cloudwatch_stream: str | None = Field(default=None, alias="LOG_CLOUDWATCH_STREAM")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")
    # Register the deliberate-error diagnostics route (/_diagnostics/*). Kept out of prod.
    enable_diagnostics_routes: bool = Field(default=True, alias="ENABLE_DIAGNOSTICS_ROUTES")

    # Adapter selection (Section 2 of the rebuild brief)
    graph_client_mode: str = Field(default="mock", alias="GRAPH_CLIENT_MODE")  # mock | local_real | real
    llm_client_mode: str = Field(default="mock", alias="LLM_CLIENT_MODE")  # mock | claude | real
    embedding_client_mode: str = Field(default="local", alias="EMBEDDING_CLIENT_MODE")  # local | cdao_openai | azure | azure_openai
    # Input/output AI guardrails (Security & Governance poster). local = regex/heuristic (default);
    # smartsdk = JPMC SmartSDK EvaluationService (toxicity/qa_correctness/hallucination) in client env.
    guardrail_client_mode: str = Field(default="local", alias="GUARDRAIL_CLIENT_MODE")  # local | smartsdk
    guardrails_enabled: bool = Field(default=True, alias="GUARDRAILS_ENABLED")
    local_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="LOCAL_EMBEDDING_MODEL"
    )

    # Section 11.1: real model tier (ModelClient) + graph-entity vector storage (VectorClient).
    # Defaults keep the verified deterministic scorers/vectors as the working path; `real`/
    # `tigergraph` are opt-in and always fall back to deterministic when no artifact/engine.
    model_client_mode: str = Field(default="deterministic", alias="MODEL_CLIENT_MODE")  # deterministic | real
    # Durable state persistence (memory, feedback/learning, impact ledger, rec status).
    # tigergraph = graph is the source of truth (writes/reads via GraphClient), with an
    # automatic SQLite fallback on any graph failure; sqlite = SQLite only (legacy).
    state_store_mode: str = Field(default="tigergraph", alias="STATE_STORE_MODE")  # tigergraph | sqlite
    vector_client_mode: str = Field(default="local", alias="VECTOR_CLIENT_MODE")  # local | tigergraph
    ml_artifacts_dir: str = Field(default="models/artifacts", alias="ML_ARTIFACTS_DIR")
    ml_time_box_minutes: int = Field(default=10, alias="ML_TIME_BOX_MINUTES")
    # Section 11.3: apply the outcome-driven-learning affinity as a bounded ±10% confidence
    # modifier on recommendations (evidence is always attached regardless). Priority ranking
    # stays owned by the bandit weight alone.
    fl_affinity_in_confidence: bool = Field(default=True, alias="FL_AFFINITY_IN_CONFIDENCE")

    # Section 11.6: context ranking (rerank) + scope-aware assembly.
    rerank_client_mode: str = Field(default="local", alias="RERANK_CLIENT_MODE")  # local | cohere
    cohere_api_key: str | None = Field(default=None, alias="COHERE_API_KEY")
    cohere_rerank_model: str = Field(default="rerank-english-v3.0", alias="COHERE_RERANK_MODEL")
    context_rerank_top_k: int = Field(default=8, alias="CONTEXT_RERANK_TOP_K")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str = Field(default="gpt-4o-mini", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-3-small", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )
    azure_openai_api_version: str = Field(default="2024-06-01", alias="AZURE_OPENAI_API_VERSION")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001", alias="ANTHROPIC_MODEL")

    # --- cdao OpenAI Azure client (client env: LLM_CLIENT_MODE=cdao_openai — PRIMARY) ---
    # Backs CdaoOpenAILLMClient via `from cdao import openai_azure_client` (cdaosdk-all[openai],
    # client artifactory only; guarded import). Auth comes from the ambient PCL AWS login session
    # — no credentials here. See CLIENT_ENV_SETUP.md §1b.
    cdao_api_version: str = Field(default="2024-02-01", alias="CDAO_API_VERSION")
    cdao_workspace_id: str | None = Field(default=None, alias="CDAO_WORKSPACE_ID")
    cdao_model: str = Field(default="gpt-4o-2024-08-06", alias="CDAO_MODEL")
    # Embedding deployment via the SAME cdao client (EMBEDDING_CLIENT_MODE=cdao_openai — PRIMARY).
    # text-embedding-3-large-1 returns 3072-dim vectors (confirmed by the developer's real run),
    # so EMBEDDING_DIM must be set to 3072 when this model is active (vs local=384). See §1b.
    cdao_embedding_model: str = Field(default="text-embedding-3-large-1", alias="CDAO_EMBEDDING_MODEL")

    # --- SmartSDK / Fusion (client env: LLM_CLIENT_MODE=azure, EMBEDDING_CLIENT_MODE=azure) ---
    # These back AzureOpenAILLMClient / AzureOpenAIEmbeddingClient, which route through JPMC's
    # SmartSDK (smart_sdk.models.Model → _to_langgraph_model). smart_sdk is only in the client
    # artifactory — it is imported ONLY when the azure mode is selected (guarded import), so the
    # app still boots in mock/claude mode without it. See SMARTSDK_REFERENCE.md sections 1-3.
    azure_auth_method: str = Field(default="key", alias="AZURE_AUTH_METHOD")  # key | certificate
    azure_model_name: str = Field(default="gpt-4o-2024-08-06", alias="AZURE_MODEL_NAME")
    azure_deployment_name: str = Field(default="gpt-4o-2024-08-06", alias="AZURE_DEPLOYMENT_NAME")
    azure_api_key: str | None = Field(default=None, alias="AZURE_API_KEY")
    azure_api_version: str = Field(default="2024-02-01", alias="AZURE_API_VERSION")
    azure_endpoint: str | None = Field(default=None, alias="AZURE_ENDPOINT")
    # Fusion multitenancy gateway (key/fusion auth — SMARTSDK_REFERENCE.md section 1)
    fusion_base_url: str | None = Field(default=None, alias="FUSION_BASE_URL")
    fusion_workspace_id: str | None = Field(default=None, alias="FUSION_WORKSPACE_ID")
    fusion_env: str = Field(default="prod", alias="FUSION_ENV")
    # Certificate auth (alternate — SMARTSDK_REFERENCE.md section 2)
    azure_certificate_path: str | None = Field(default=None, alias="AZURE_CERTIFICATE_PATH")
    azure_tenant_id: str | None = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: str | None = Field(default=None, alias="AZURE_CLIENT_ID")
    # Embedding deployment (SmartSDK Model, same construction as the LLM)
    azure_embedding_model_name: str = Field(default="text-embedding-3-small", alias="AZURE_EMBEDDING_MODEL_NAME")
    azure_embedding_deployment_name: str = Field(default="text-embedding-3-small", alias="AZURE_EMBEDDING_DEPLOYMENT_NAME")
    # Embedding vector dimension — Azure text-embedding-3-small=1536 vs sentence-transformers=384.
    # The TigerGraph EMBEDDING attribute DDL and the Chroma collection must use THIS value so the
    # store matches whatever embedding adapter is active. Keep it in sync with the active mode.
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")

    tigergraph_host: str | None = Field(default=None, alias="TIGERGRAPH_HOST")
    tigergraph_username: str | None = Field(default=None, alias="TIGERGRAPH_USERNAME")
    tigergraph_password: str | None = Field(default=None, alias="TIGERGRAPH_PASSWORD")
    tigergraph_secret: str | None = Field(default=None, alias="TIGERGRAPH_SECRET")
    tigergraph_token: str | None = Field(default=None, alias="TIGERGRAPH_TOKEN")
    tigergraph_graph: str = Field(default="iperform_insights_coaching_demo", alias="TIGERGRAPH_GRAPH")
    tigergraph_schema_prefix: str = Field(default="phx_dm_", alias="TIGERGRAPH_SCHEMA_PREFIX")
    tigergraph_restpp_url: str = Field(default="http://localhost:14240/restpp", alias="TIGERGRAPH_RESTPP_URL")
    tigergraph_verify_ssl: bool = Field(default=True, alias="TIGERGRAPH_VERIFY_SSL")
    tigergraph_timeout_seconds: int = Field(default=120, alias="TIGERGRAPH_TIMEOUT_SECONDS")
    graph_load_batch_size: int = Field(default=500, alias="GRAPH_LOAD_BATCH_SIZE")

    # TigerGraph Foundation package (Section 3 — source of truth for schema/data/queries)
    foundation_dir: str = Field(default="docs/tigergraph_foundation", alias="FOUNDATION_DIR")

    # --- Section 9.4: 4-tier GraphClient adapter (MCP → pyTigerGraph → RESTPP → mock) ---
    # TG_* vars use the official tigergraph-mcp naming so the same env drives both the
    # MCP server subprocess (Tier 1) and the direct pyTigerGraph connection (Tier 2).
    # Defaults are mock-friendly: with no live TigerGraph the chain falls to Tier 4.
    tg_host: str = Field(default="http://127.0.0.1", alias="TG_HOST")
    tg_graphname: str | None = Field(default=None, alias="TG_GRAPHNAME")  # None → TIGERGRAPH_GRAPH
    tg_username: str = Field(default="tigergraph", alias="TG_USERNAME")
    tg_password: str = Field(default="tigergraph", alias="TG_PASSWORD")
    tg_api_token: str | None = Field(default=None, alias="TG_API_TOKEN")
    # Auth for a secured remote (e.g. the client's AWS instance). Precedence at connect
    # time: JWT token → static API token → getToken(secret) → username/password only.
    tg_jwt_token: str | None = Field(default=None, alias="TG_JWT_TOKEN")
    tg_secret: str | None = Field(default=None, alias="TG_SECRET")  # → conn.getToken(secret)
    tg_token_lifetime_seconds: int = Field(default=0, alias="TG_TOKEN_LIFETIME_SECONDS")  # 0 = server default
    tg_restpp_port: int = Field(default=9000, alias="TG_RESTPP_PORT")
    tg_gs_port: int = Field(default=14240, alias="TG_GS_PORT")
    tg_ssl_port: int = Field(default=443, alias="TG_SSL_PORT")
    # SSL/TLS for the remote. When the host is https:// this is honored by both the
    # pyTigerGraph tier and the RESTPP tier. Set false only for self-signed dev certs.
    tg_use_ssl: bool = Field(default=False, alias="TG_USE_SSL")
    tg_verify_ssl: bool = Field(default=True, alias="TG_VERIFY_SSL")
    # Tier-1 MCP server subprocess (stdio); see TIGERGRAPH_MCP_COMMAND/ARGS in
    # tigergraph_mcp_stdio_client.py (read via os.getenv for subprocess spawning).
    graph_tier_cooldown_seconds: int = Field(default=60, alias="GRAPH_TIER_COOLDOWN_SECONDS")
    graph_tier_probe_timeout_seconds: int = Field(default=10, alias="GRAPH_TIER_PROBE_TIMEOUT_SECONDS")

    # TigerGraph MCP-first graph access
    graph_access_strategy: str = "mcp_rest_mock"
    tigergraph_mcp_url: str = ""
    tigergraph_mcp_transport: str = "http"
    tigergraph_mcp_api_key: str = ""
    tigergraph_mcp_auth_header: str = "Authorization"
    tigergraph_mcp_auth_scheme: str = "Bearer"
    tigergraph_mcp_timeout_seconds: int = 30
    tigergraph_mcp_tool_health_check: str = "health_check"
    tigergraph_mcp_tool_query_graph: str = "query_graph"
    tigergraph_mcp_tool_run_installed_query: str = "run_installed_query"
    tigergraph_mcp_tool_upsert_vertex: str = "upsert_vertex"
    tigergraph_mcp_tool_upsert_edge: str = "upsert_edge"
    tigergraph_mcp_tool_run_gsql: str = "run_gsql"
    tigergraph_mcp_tool_get_schema: str = "get_schema"

    # TigerGraph MCP library-based integration
    tigergraph_mcp_client_mode: str = "streamable_http"
    tigergraph_mcp_stdio_command: str = "python"
    tigergraph_mcp_stdio_args: str = "-m,tigergraph_mcp"
    tigergraph_mcp_use_library_client: bool = True
    tigergraph_mcp_list_tools_on_health: bool = True


    tigergraph_mcp_url: str | None = Field(default=None, alias="TIGERGRAPH_MCP_URL")
    tigergraph_mcp_token: str | None = Field(default=None, alias="TIGERGRAPH_MCP_TOKEN")
    tigergraph_rest_timeout_seconds: int = Field(default=30, alias="TIGERGRAPH_REST_TIMEOUT_SECONDS")

    sqlite_db_path: str = Field(default="./data/feature_store/iperform_features.db", alias="SQLITE_DB_PATH")
    chroma_path: str = Field(default="./data/chroma", alias="CHROMA_PATH")
    uploads_path: str = Field(default="./data/uploads", alias="UPLOADS_PATH")
    checkpoints_path: str = Field(default="./data/checkpoints", alias="CHECKPOINTS_PATH")
    exports_path: str = Field(default="./data/exports", alias="EXPORTS_PATH")
    documents_path: str = Field(default="./data/documents", alias="DOCUMENTS_PATH")

    # Bind address for uvicorn. Default 0.0.0.0 so the server is reachable through Codespaces
    # port forwarding (a 127.0.0.1-only bind is NOT reachable by the forwarder / an external
    # browser). On a client machine set API_HOST=127.0.0.1 for loopback-only if desired.
    # Binding 0.0.0.0 still accepts loopback (127.0.0.1) connections, so SSR/internal tooling
    # that targets 127.0.0.1:8000 keeps working. See TROUBLESHOOTING.md "Backend unreachable".
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_url: str = Field(default="http://127.0.0.1:8000", alias="API_BASE_URL")
    streamlit_port: int = Field(default=8501, alias="STREAMLIT_PORT")

    enable_openai: bool = Field(default=True, alias="ENABLE_OPENAI")
    enable_chroma: bool = Field(default=True, alias="ENABLE_CHROMA")
    enable_tigergraph_mcp: bool = Field(default=True, alias="ENABLE_TIGERGRAPH_MCP")
    enable_tigergraph_rest_fallback: bool = Field(default=True, alias="ENABLE_TIGERGRAPH_REST_FALLBACK")
    enable_local_mock_fallback: bool = Field(default=True, alias="ENABLE_LOCAL_MOCK_FALLBACK")

    def ensure_local_directories(self) -> None:
        for path in [
            self.sqlite_db_path,
            self.chroma_path,
            self.uploads_path,
            self.checkpoints_path,
            self.exports_path,
            self.documents_path,
            # Log directory — created at startup so a fresh environment never errors
            # writing the first log line to a missing folder (LOG_SINK=file default).
            self.log_dir,
        ]:
            candidate = Path(path)
            if candidate.suffix:
                candidate.parent.mkdir(parents=True, exist_ok=True)
            else:
                candidate.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_local_directories()
    return settings
