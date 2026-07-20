import { apiClient } from "@/lib/api/client";

/** One check from GET /env-health. The backend normalises every probe to
 * {component, status, latency_ms, error, ...detail}. Detail fields differ per
 * component; the ones the V2 screens read are typed explicitly. */
export interface EnvHealthCheck {
  component: string;
  status: "green" | "red";
  latency_ms: number;
  error: string | null;
  // TigerGraph detail (green only)
  mode?: string;
  graph?: string;
  use_ssl?: boolean;
  auth?: string;
  schema_installed?: boolean;
  vertex_type_count?: number;
  total_vertices?: number;
  row_counts?: Record<string, number>;
  active_tier?: number;
  active_tier_name?: string;
  counts_served_by_tier?: number;
  counts_source?: string;
  // LLM detail (green only)
  model?: string;
  generation_ms?: number;
  response_preview?: string;
  [key: string]: unknown;
}

export interface EnvHealthReport {
  overall: "green" | "red";
  generated_at: string;
  modes: Record<string, string>;
  checks: EnvHealthCheck[];
}

export function fetchEnvHealth(): Promise<EnvHealthReport> {
  return apiClient.get<EnvHealthReport>("/env-health");
}
