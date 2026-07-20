import { apiClient } from "@/lib/api/client";

export interface AdapterStatus {
  graph_client_mode: string;
  graph: {
    healthy: boolean;
    mode: string;
    graph: string;
    active_tier?: number;
    active_tier_name?: string;
    tiers?: Array<{ tier: number; name: string; healthy?: boolean; error?: string }>;
    load_report: {
      vertex_types: number;
      edge_types: number;
      vertex_rows: number;
      edge_rows: number;
      row_count_mismatches: unknown[];
    };
  };
  llm_client_mode: string;
  llm: { mode: string; model: string };
  embedding_client_mode: string;
  embedding: { mode: string; model: string; dimensions: number };
  anthropic_configured: boolean;
  azure_openai_configured: boolean;
}

export async function fetchAdapterStatus(): Promise<AdapterStatus> {
  return apiClient.get<AdapterStatus>("/adapters/status");
}

export async function fetchIngestionEntityCount(): Promise<number> {
  const d = await apiClient.get<unknown[]>("/ingestion/entities");
  return Array.isArray(d) ? d.length : 0;
}
