import { apiClient } from "@/lib/api/client";

export interface IngestionEntity {
  entity_name: string;
  csv_file_name: string;
  primary_key: string;
  tigergraph_vertex: string;
  required_columns: string[];
  edge_files: string[];
  kind: string;
  expected_rows: number | null;
  batch_size: number;
}

export interface IngestionBatchStatus {
  batch_id: string;
  entity_name: string;
  file_name: string;
  status: string;
  total_records: number;
  processed_records: number;
  created_records: number;
  updated_records: number;
  skipped_records: number;
  failed_records: number;
  last_processed_row: number;
  progress_percent: number;
  message: string | null;
}

export interface ManifestSummary {
  application: string;
  graph_name: string;
  schema_prefix: string;
  package_stage: string;
  foundation_status: string;
  capabilities_locked: string[];
  next_part: string;
}

export async function fetchIngestionEntities(): Promise<IngestionEntity[]> {
  return apiClient.get<IngestionEntity[]>("/ingestion/entities");
}

export async function fetchManifest(): Promise<ManifestSummary> {
  return apiClient.get<ManifestSummary>("/manifest");
}

export async function runIngestion(entityName: string): Promise<{ batch_status: IngestionBatchStatus }> {
  return apiClient.post<{ batch_status: IngestionBatchStatus }>("/ingestion/run", { entity_name: entityName });
}

export interface RunAllEntityResult {
  entity_name: string;
  kind: string;
  file_name: string;
  status: string;
  total_records: number;
  processed_records: number;
  created_records: number;
  updated_records: number;
  skipped_records: number;
  failed_records: number;
  message: string | null;
}

export interface RunAllStatus {
  run_id: string | null;
  status: string;
  dry_run: boolean;
  started_at: string | null;
  finished_at: string | null;
  total_entities: number;
  completed_entities: number;
  failed_entities: number;
  total_rows_processed: number;
  current_entity: string | null;
  message: string | null;
  entities: RunAllEntityResult[];
}

export async function startRunAll(): Promise<RunAllStatus> {
  return apiClient.post<RunAllStatus>("/ingestion/run-all", {});
}

export async function fetchRunAllStatus(): Promise<RunAllStatus> {
  return apiClient.get<RunAllStatus>("/ingestion/run-all/status");
}
