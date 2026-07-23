/**
 * Typed fetchers for the V2 API (/api/v2/*). Every payload carries
 * served_by_tier: 1 = TigerGraph, 2 = local store — the context-bar tier pill
 * reads it so the UI never misrepresents where a number came from.
 */
import { apiClient } from "@/lib/api/client";

export type Provenance = "REAL" | "DERIVED" | "ASSUMED" | "DUMMY";

export interface Advisor {
  advisor_sid: string;
  advisor_name: string;
  rep_code: string;
  branch_cd: string;
  data_source: Provenance;
}

export interface MonthRow {
  month_id: string;
  year: number;
  month_no: number;
  month_name: string;
  quarter: number;
  start_dt: string;
  end_dt: string;
  calendar_days: number;
  billable_days: number;
  prior_month_id: string;
  index_return: number;
  is_current: boolean;
  data_source: Provenance;
}

export interface HierarchyNode {
  parent_id: string;
  data_source: Provenance;
  class_id?: string;
  class_name?: string;
  line_id?: string;
  line_name?: string;
  group_id?: string;
  group_name?: string;
  product_id?: string;
  product_name?: string;
  display_order?: number;
}

export interface ProductHierarchy {
  classes: HierarchyNode[];
  lines: HierarchyNode[];
  groups: HierarchyNode[];
  products: HierarchyNode[];
  served_by_tier: number;
}

export interface DriverCause {
  cause_id: string;
  cause_name: string;
  cause_description: string;
  default_data_source: Provenance;
  display_order: number;
}

export interface MonthlyRevenueRow {
  mpr_id: string;
  advisor_sid: string;
  month_id: string;
  group_id: string;
  line_id: string;
  class_id: string;
  revenue: number;
  txn_count: number;
  account_count: number;
  avg_rate_bps: number;
  recurring_amt: number;
  one_time_amt: number;
  /** R1-6 credited-definition breakdown carried on every mpr row. */
  total_revenue?: number;
  non_credited_amt?: number;
  excluded_amt?: number;
  late_excluded_amt?: number;
  data_source: Provenance;
}

export interface RevenueChangeRow {
  change_id: string;
  advisor_sid: string;
  from_month_id: string;
  to_month_id: string;
  group_id: string;
  from_revenue: number;
  to_revenue: number;
  change_amt: number;
  change_pct: number;
  direction: "UP" | "DOWN" | "FLAT";
  data_source: Provenance;
}

export interface DriverRow {
  driver_id: string;
  change_id: string;
  cause_id: string;
  group_id: string;
  contribution_amt: number;
  contribution_pct: number;
  direction: "UP" | "DOWN";
  rank: number;
  inputs_json: string;
  data_source: Provenance;
}

export interface CommentaryBullet {
  driver_id: string;
  direction: "UP" | "DOWN";
  title: string;
  text: string;
  cause_id: string;
  group_id: string;
  data_source: Provenance;
}

export interface CommentaryRow {
  commentary_id: string;
  version_id: string;
  advisor_sid: string;
  from_month_id: string;
  to_month_id: string;
  headline: string;
  narrative_text: string;
  bullets_json: string;
  status: "PUBLISHED" | "BLOCKED";
  blocked_reason: string;
  data_source: Provenance;
}

export interface CommentaryVersion {
  version_id: string;
  version_no: number;
  generated_at: string;
  model: string;
  prompt_version: string;
  data_snapshot_dt: string;
  status: "DRAFT" | "PUBLISHED" | "SUPERSEDED";
  advisor_count: number;
  transition_count: number;
  blocked_count: number;
  notes: string;
}

/** Independent LLM-judge review of one commentary (FIX_SPEC R5). Advisory —
 * deterministic guardrails remain the blocking gate. */
export interface CommentaryEvaluation {
  evaluation_id: string;
  commentary_id: string;
  version_id: string;
  judge_model: string;
  faithfulness_score: number; // 0-1
  hallucination_flag: boolean;
  completeness_score: number;
  clarity_score: number;
  verdict: "PASS" | "REVIEW" | "FAIL";
  reasoning: string;
  evaluated_at: string;
  data_source: Provenance;
}

export interface EvidenceRecord {
  evidence_id: string;
  driver_id: string;
  finding_text: string;
  calc_json: string;
  source_records_json: string;
  lineage_json: string;
  checks_json: string;
  gsql_query_name: string;
  gsql_params_json: string;
  gsql_result_json: string;
  source_sql: string;
  source_table: string;
  source_row_count: number;
  data_source: Provenance;
}

export interface TransactionRow {
  txn_id: string;
  trade_ref_no: string;
  trade_dt: string;
  product_id: string;
  product_name: string;
  group_id: string;
  account_no: string;
  credited_amt: number;
  split_pct: number;
  file_key: string;
  rev_nature: string;
  month_id: string;
  /** R1/R3 — credited-eligibility classification of the row. */
  eligibility_bucket: "CREDITED" | "NON_CREDITED" | "EXCLUDED" | "LATE" | "OUT_OF_GRID";
  reason_cd: string; // "__NONE__" when the row carries no reason code
  grid_type: string;
  data_source: Provenance;
}

export interface MonthlyTotals {
  revenue_by_month: Record<string, number>;
  recurring_by_month: Record<string, number>;
  non_recurring_by_month: Record<string, number>;
  txn_count_by_month: Record<string, number>;
  served_by_tier: number;
}

/** R6 Y — stored anomaly row (detection is batch; the screen only retrieves). */
export interface AnomalyRow {
  anomaly_id: string;
  advisor_sid: string;
  from_month_id: string;
  to_month_id: string;
  rule_id: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  title: string;
  detail_text: string;
  metrics_json: string;
  threshold_json: string;
  impact_amt: number;
  group_id: string;
  scan_id: string;
  detected_at: string;
  data_source: Provenance;
}

export interface AnomalyScan {
  scan_id: string;
  started_at: string;
  advisors_reviewed: number;
  transitions_reviewed: number;
  flagged_count: number;
  thresholds_json: string;
  status: string;
}

export interface AnomaliesResponse {
  scan_id_used: string;
  scan: Partial<AnomalyScan>;
  anomalies: AnomalyRow[];
  thresholds_in_force: Record<string, number>;
  served_by_tier: number;
}

export const v2Api = {
  advisors: () => apiClient.get<{ advisors: Advisor[]; served_by_tier: number }>("/api/v2/reference/advisors"),
  months: () => apiClient.get<{ months: MonthRow[]; served_by_tier: number }>("/api/v2/reference/months"),
  productHierarchy: () => apiClient.get<ProductHierarchy>("/api/v2/reference/product-hierarchy"),
  driverCauses: () => apiClient.get<{ causes: DriverCause[]; served_by_tier: number }>("/api/v2/reference/driver-causes"),

  trendsRevenue: (advisorId: string, fromMonth: string, toMonth: string) =>
    apiClient.get<{ monthly_revenue: MonthlyRevenueRow[]; served_by_tier: number }>(
      `/api/v2/trends/revenue?advisor_id=${advisorId}&from_month=${fromMonth}&to_month=${toMonth}`),
  trendsChanges: (advisorId: string, fromMonth: string, toMonth: string) =>
    apiClient.get<{ changes: RevenueChangeRow[]; served_by_tier: number }>(
      `/api/v2/trends/changes?advisor_id=${advisorId}&from_month=${fromMonth}&to_month=${toMonth}`),

  insightsChart: (advisorId: string, fromMonth: string, toMonth: string) =>
    apiClient.get<MonthlyTotals>(
      `/api/v2/insights/chart?advisor_id=${advisorId}&from_month=${fromMonth}&to_month=${toMonth}`),
  insightsDrivers: (advisorId: string, fromMonth: string, toMonth: string, limit = 100) =>
    apiClient.get<{ drivers: DriverRow[]; served_by_tier: number }>(
      `/api/v2/insights/drivers?advisor_id=${advisorId}&from_month=${fromMonth}&to_month=${toMonth}&result_limit=${limit}`),
  commentary: (advisorId: string, versionId = "") =>
    apiClient.get<{ commentaries: CommentaryRow[]; resolved_version: string; served_by_tier: number; empty_state: string | null }>(
      `/api/v2/insights/commentary?advisor_id=${advisorId}&version_id=${versionId}`),
  versions: () =>
    apiClient.get<{ versions: CommentaryVersion[]; served_by_tier: number }>("/api/v2/insights/versions"),
  evaluations: (versionId: string) =>
    apiClient.get<{ evaluations: CommentaryEvaluation[]; served_by_tier: number }>(
      `/api/v2/insights/evaluations?version_id=${encodeURIComponent(versionId)}`),
  generate: (notes = "") => apiClient.post<Record<string, unknown>>(`/api/v2/insights/generate?notes=${encodeURIComponent(notes)}`),

  evidence: (driverId: string, versionId = "") =>
    apiClient.get<{ evidence: EvidenceRecord[]; served_by_tier: number }>(
      `/api/v2/evidence?driver_id=${encodeURIComponent(driverId)}&version_id=${versionId}`),

  transactions: (advisorId: string, monthId: string, groupId = "", limit = 1000) =>
    apiClient.get<{ transactions: TransactionRow[]; row_count: number; credited_total: number; served_by_tier: number }>(
      `/api/v2/transactions?advisor_id=${advisorId}&month_id=${monthId}&group_id=${encodeURIComponent(groupId)}&result_limit=${limit}`),

  opsCounts: () =>
    apiClient.get<{ counts: Record<string, number>; source_mix: Record<string, Record<string, number>>; served_by_tier: number }>(
      "/api/v2/ops/counts"),
  reconciliation: (advisorId: string, fromMonth: string, toMonth: string) =>
    apiClient.get<{ all_reconcile: boolean; transitions: Record<string, { total_change: number; attributed: number; discrepancy: number; reconciles: boolean }>; served_by_tier: number }>(
      `/api/v2/ops/reconciliation?advisor_id=${advisorId}&from_month=${fromMonth}&to_month=${toMonth}`),

  anomalies: (advisorId = "", scanId = "", severity = "", limit = 500) =>
    apiClient.get<AnomaliesResponse>(
      `/api/v2/anomalies?advisor_id=${encodeURIComponent(advisorId)}&scan_id=${encodeURIComponent(scanId)}&severity=${encodeURIComponent(severity)}&result_limit=${limit}`),
  anomalyScans: () =>
    apiClient.get<{ scans: AnomalyScan[]; served_by_tier: number }>("/api/v2/anomalies/scans"),
  anomalyScan: (notes = "") =>
    apiClient.post<Record<string, unknown>>(`/api/v2/anomalies/scan?notes=${encodeURIComponent(notes)}`),

  adapterStatus: () =>
    apiClient.get<{ modes: { graph_client_mode: string; llm_client_mode: string; data_set: string; commentary_mode: string } }>(
      "/adapters/status"),
};
