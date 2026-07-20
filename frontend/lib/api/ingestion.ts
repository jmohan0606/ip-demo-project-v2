import { apiClient } from "@/lib/api/client";

/** Entity config from GET /ingestion/entities — manifest-driven, dependency-ordered
 * (vertices first in manifest order, then edges). */
export interface IngestionEntity {
  entity_name: string;
  csv_file_name: string;
  primary_key: string;
  tigergraph_vertex: string;
  required_columns: string[];
  edge_files: string[];
  kind: "vertex" | "edge" | string;
  order: number;
  expected_rows: number | null;
  batch_size: number;
  from_type?: string | null;
  to_type?: string | null;
  from_column?: string | null;
  to_column?: string | null;
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

/** Row from GET /ingestion/batches (checkpoint table, newest first). */
export interface IngestionBatchRow {
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
  started_at: string | null;
  updated_at: string | null;
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

export async function fetchBatches(): Promise<IngestionBatchRow[]> {
  return apiClient.get<IngestionBatchRow[]>("/ingestion/batches");
}

export async function fetchManifest(): Promise<ManifestSummary> {
  return apiClient.get<ManifestSummary>("/manifest");
}

export async function runIngestion(
  entityName: string,
  resume = false,
): Promise<{ batch_status: IngestionBatchStatus }> {
  return apiClient.post<{ batch_status: IngestionBatchStatus }>("/ingestion/run", {
    entity_name: entityName,
    resume,
  });
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

/** GET /ingestion/run-all/status — status is "pending" (never run) | "running" |
 * "completed" | "failed"; run_id is null until a run has been started. */
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

// ------------------------------------------------------------------ delete

/** One step of GET /ingestion/delete-plan — edges first, then vertices, both in
 * reverse manifest order (facts before dimensions). */
export interface DeletePlanStep {
  entity_name: string;
  kind: string;
  target: string;
}

export async function fetchDeletePlan(): Promise<DeletePlanStep[]> {
  return apiClient.get<DeletePlanStep[]>("/ingestion/delete-plan");
}

export interface DeleteEntityResult {
  entity_name: string;
  kind: string;
  error?: boolean;
  deleted?: number;
  target?: string;
  note?: string;
  [key: string]: unknown;
}

export async function deleteEntity(entityName: string): Promise<DeleteEntityResult> {
  return apiClient.post<DeleteEntityResult>(`/ingestion/delete/${encodeURIComponent(entityName)}`);
}

export interface DeleteAllResult {
  deleted_entities: number;
  total_rows_deleted: number;
  order: string[];
  results: DeleteEntityResult[];
}

export async function deleteAllEntities(): Promise<DeleteAllResult> {
  return apiClient.post<DeleteAllResult>("/ingestion/delete-all");
}
