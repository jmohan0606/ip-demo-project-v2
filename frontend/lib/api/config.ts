import { apiClient } from "@/lib/api/client";

export type RuntimeConfigStatus = {
  app_name: string;
  app_env: string;
  api_base_url: string;
  frontend_url: string;
  graph_access_strategy: string;
  tigergraph_mcp_enabled: boolean;
  tigergraph_rest_enabled: boolean;
  mock_data_enabled: boolean;
  sqlite_db_path: string;
  chroma_persist_dir: string;
  chroma_collection_name: string;
  agent_runtime: string;
  enable_login: boolean;
  default_persona: string;
  default_scope_type: string;
  default_scope_id: string;
};

export async function fetchRuntimeConfigStatus(): Promise<RuntimeConfigStatus> {
  try {
    return await apiClient.get<RuntimeConfigStatus>("/config/status");
  } catch {
    return {
      app_name: "iPerform Insights & Coaching",
      app_env: "local",
      api_base_url: "http://127.0.0.1:8000",
      frontend_url: "http://localhost:3000",
      graph_access_strategy: "mcp_first",
      tigergraph_mcp_enabled: false,
      tigergraph_rest_enabled: false,
      mock_data_enabled: true,
      sqlite_db_path: "data/sqlite/iperform.db",
      chroma_persist_dir: "data/chroma",
      chroma_collection_name: "iperform_knowledge_base",
      agent_runtime: "langgraph",
      enable_login: false,
      default_persona: "Advisor",
      default_scope_type: "Advisor",
      default_scope_id: "ADV0001"
    };
  }
}
