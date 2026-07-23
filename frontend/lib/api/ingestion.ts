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
  batch_size: number;
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
  current_entity_index: number | null;
  batch_size_override: number | null;
  message: string | null;
  entities: RunAllEntityResult[];
}

export async function startRunAll(batchSize?: number): Promise<RunAllStatus> {
  const qs = batchSize ? `?batch_size=${batchSize}` : "";
  return apiClient.post<RunAllStatus>(`/ingestion/run-all${qs}`, {});
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
  failed_entities?: number;
  failed?: { entity_name: string; reason: string | null }[];
  total_rows_deleted: number;
  order: string[];
  results: DeleteEntityResult[];
}

export async function deleteAllEntities(): Promise<DeleteAllResult> {
  return apiClient.post<DeleteAllResult>("/ingestion/delete-all");
}

// ------------------------------------------------------- validation (R5 A5/B6)

/** Per-entity graph-truth validation from GET /ingestion/validation.
 * state: VALIDATED | EMPTY_ATTRS | MISMATCH | NOT_LOADED | UNVERIFIABLE. */
export interface EntityValidation {
  entity_name: string;
  kind: string;
  target: string;
  expected_count: number | null;
  graph_count: number | null;
  checkpoint: { status: string | null; created: number; updated: number; skipped: number };
  attr_check: "populated" | "empty" | "n/a" | "unavailable" | null;
  attr_sample_size: number;
  state: "VALIDATED" | "EMPTY_ATTRS" | "MISMATCH" | "NOT_LOADED" | "UNVERIFIABLE" | string;
  conflict: string | null;
  checked_at: string;
}

export interface ValidationReport {
  generated_at: string;
  data_set: string;
  summary: Record<string, number>;
  entities: EntityValidation[];
}

export async function fetchValidation(): Promise<ValidationReport> {
  return apiClient.get<ValidationReport>("/ingestion/validation");
}

// ------------------------------------------------------------ errors (R5 B4)

/** Persisted ingestion error from GET /ingestion/errors — survives page refresh. */
export interface IngestionErrorRow {
  error_id: string;
  batch_id: string;
  entity_name: string;
  row_number: number | null;
  primary_key: string | null;
  error_message: string;
  raw_record_json: string | null;
  created_at: string;
  remediation: string;
}

export async function fetchIngestionErrors(entityName?: string): Promise<IngestionErrorRow[]> {
  const qs = entityName ? `?entity_name=${encodeURIComponent(entityName)}` : "";
  return apiClient.get<IngestionErrorRow[]>(`/ingestion/errors${qs}`);
}

export async function clearCheckpoints(entityName?: string): Promise<{ cleared_entities: number }> {
  const qs = entityName ? `?entity_name=${encodeURIComponent(entityName)}` : "";
  return apiClient.post<{ cleared_entities: number }>(`/ingestion/clear-checkpoints${qs}`);
}
