import { apiClient } from "@/lib/api/client";

export interface EnvHealthCheck {
  component: string;
  status: "green" | "red";
  latency_ms: number;
  error: string | null;
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
