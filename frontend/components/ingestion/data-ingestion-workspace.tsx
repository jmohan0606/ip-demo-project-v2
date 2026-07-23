"use client";
/**
 * Data Ingestion & Sync (UI_SPEC §8, reference 05_data_ingestion.png; Round 5
 * work-stream B rebuild).
 *
 * The screen's source of truth is the GRAPH, not the checkpoint table: the
 * Validation column shows live graph counts plus a sampled attribute check per
 * entity (VALIDATED / EMPTY_ATTRS / MISMATCH / NOT_LOADED / UNVERIFIABLE), with
 * any checkpoint-vs-graph conflict spelled out. Run All shows the entity
 * currently processing (n/45) with per-entity row progress, polls status async
 * without restarting the run, continues past failing entities, and ends with a
 * remediation summary. Errors are persisted server-side and survive refreshes.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronDown, ChevronRight, Loader2, Play, RefreshCw } from "lucide-react";
import {
  clearCheckpoints,
  deleteAllEntities,
  deleteEntity,
  fetchBatches,
  fetchDeletePlan,
  fetchIngestionEntities,
  fetchIngestionErrors,
  fetchRunAllStatus,
  fetchValidation,
  runIngestion,
  startRunAll,
  type DeleteAllResult,
  type DeletePlanStep,
  type EntityValidation,
  type IngestionBatchRow,
  type IngestionEntity,
  type IngestionErrorRow,
  type RunAllStatus,
  type ValidationReport,
} from "@/lib/api/ingestion";
import { v2Api } from "@/lib/api/v2";
import { AsyncBoundary } from "@/components/patterns/async-state";
import { useV2Context } from "@/components/layout/v2-shell";

type OpsCounts = {
  counts: Record<string, number>;
  source_mix: Record<string, Record<string, number>>;
  served_by_tier: number;
};

/** "2026-07-20 01:52:03" | ISO → "20 Jul · 01:52". */
function fmtRunTime(value: string | null | undefined): string {
  if (!value) return "—";
  const normalised = String(value).replace(" ", "T");
  const d = new Date(normalised.endsWith("Z") ? normalised : `${normalised}Z`);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 16);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} · ${hh}:${mm}`;
}

const VALIDATION_STYLE: Record<string, { label: string; cls: string; title: string }> = {
  VALIDATED: {
    label: "Validated", cls: "bg-v2-positive-bg text-v2-positive",
    title: "Graph count matches the source CSV and sampled rows carry populated non-key attributes",
  },
  EMPTY_ATTRS: {
    label: "Empty attrs", cls: "bg-v2-negative-bg text-v2-negative",
    title: "Row count matches but sampled rows hold ONLY the primary key — attributes did not land",
  },
  MISMATCH: {
    label: "Mismatch", cls: "bg-v2-negative-bg text-v2-negative",
    title: "Graph count differs from the source CSV, or the checkpoint claim disagrees with the graph",
  },
  NOT_LOADED: {
    label: "Not loaded", cls: "bg-v2-header-bg text-v2-muted",
    title: "Nothing in the graph and no checkpoint claim",
  },
  UNVERIFIABLE: {
    label: "Unverifiable", cls: "bg-v2-warn-bg text-v2-warn",
    title: "The graph could not be interrogated — see the conflict detail",
  },
};

function ValidationPill({ v }: { v: EntityValidation | undefined }) {
  if (!v) return <span className="text-v2-faint">—</span>;
  const s = VALIDATION_STYLE[v.state] ?? VALIDATION_STYLE.UNVERIFIABLE;
  return (
    <span
      title={`${s.title}${v.conflict ? ` — ${v.conflict}` : ""} (checked ${fmtRunTime(v.checked_at)})`}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9.5px] font-semibold ${s.cls}`}
    >
      <span aria-hidden>●</span> {s.label}
    </span>
  );
}

export function DataIngestionWorkspace() {
  const { modes } = useV2Context();
  const [entities, setEntities] = useState<IngestionEntity[]>([]);
  const [counts, setCounts] = useState<OpsCounts | null>(null);
  const [batches, setBatches] = useState<IngestionBatchRow[]>([]);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [validating, setValidating] = useState(false);
  const [errors, setErrors] = useState<IngestionErrorRow[]>([]);
  const [runAll, setRunAll] = useState<RunAllStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyEntity, setBusyEntity] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [batchOverride, setBatchOverride] = useState<string>("");
  const [deleteReport, setDeleteReport] = useState<DeleteAllResult | null>(null);
  // Confirm dialogs
  const [confirmEntity, setConfirmEntity] = useState<IngestionEntity | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [deletePlan, setDeletePlan] = useState<DeletePlanStep[] | null>(null);
  const [deleting, setDeleting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshValidation = useCallback(async () => {
    setValidating(true);
    try {
      setValidation(await fetchValidation());
    } catch {
      /* endpoint failure is shown as missing pills; conflicts stay visible */
    } finally {
      setValidating(false);
    }
  }, []);

  const refreshCounts = useCallback(async () => {
    const [c, b, er] = await Promise.allSettled([
      v2Api.opsCounts(),
      fetchBatches(),
      fetchIngestionErrors(),
    ]);
    if (c.status === "fulfilled") setCounts(c.value);
    if (b.status === "fulfilled") setBatches(b.value);
    if (er.status === "fulfilled") setErrors(er.value);
    void refreshValidation();
  }, [refreshValidation]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // B2: poll status only — GET /run-all/status never restarts or blocks the run,
  // and the run continues server-side if this tab is closed.
  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await fetchRunAllStatus();
        setRunAll(s);
        if (s.status !== "running") {
          stopPolling();
          void refreshCounts();
        }
      } catch {
        /* transient — keep polling */
      }
    }, 2000);
  }, [refreshCounts, stopPolling]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.allSettled([
      fetchIngestionEntities(),
      v2Api.opsCounts(),
      fetchBatches(),
      fetchRunAllStatus(),
      fetchIngestionErrors(),
    ]).then(([e, c, b, r, er]) => {
      if (e.status === "fulfilled") setEntities(e.value);
      else setError(String(e.reason));
      if (c.status === "fulfilled") setCounts(c.value);
      if (b.status === "fulfilled") setBatches(b.value);
      if (er.status === "fulfilled") setErrors(er.value);
      if (r.status === "fulfilled") {
        if (r.value.run_id) setRunAll(r.value);
        if (r.value.status === "running") startPolling();
      }
      setLoading(false);
      void refreshValidation();
    });
  }, [startPolling, refreshValidation]);

  useEffect(() => {
    load();
    return stopPolling;
  }, [load, stopPolling]);

  // Latest checkpoint batch per entity (list is newest-first).
  const latestBatch = useMemo(() => {
    const map = new Map<string, IngestionBatchRow>();
    for (const b of batches) if (!map.has(b.entity_name)) map.set(b.entity_name, b);
    return map;
  }, [batches]);

  const validationByEntity = useMemo(() => {
    const map = new Map<string, EntityValidation>();
    for (const v of validation?.entities ?? []) map.set(v.entity_name, v);
    return map;
  }, [validation]);

  const errorsByEntity = useMemo(() => {
    const map = new Map<string, IngestionErrorRow[]>();
    for (const e of errors) {
      const list = map.get(e.entity_name) ?? [];
      list.push(e);
      map.set(e.entity_name, list);
    }
    return map;
  }, [errors]);

  const stats = useMemo(() => {
    const vertexTypes = entities.filter((e) => e.kind === "vertex").length;
    const edgeTypes = entities.filter((e) => e.kind === "edge").length;
    const rowsInGraph = validation
      ? validation.entities.reduce((s, v) => s + (v.graph_count ?? 0), 0)
      : null;
    const validated = validation?.summary["VALIDATED"] ?? null;
    const lastRun = batches.length ? fmtRunTime(batches[0].updated_at) : "—";
    return { vertexTypes, edgeTypes, rowsInGraph, validated, lastRun };
  }, [entities, validation, batches]);

  const runAllActive = runAll?.status === "running";
  const runAllCurrent = runAllActive && runAll?.current_entity
    ? runAll.entities.find((x) => x.entity_name === runAll.current_entity)
    : null;
  const runAllFailed = useMemo(
    () => (runAll && runAll.status !== "running"
      ? runAll.entities.filter((x) => x.status === "failed")
      : []),
    [runAll],
  );
  const runTally = useMemo(() => {
    if (!runAll) return null;
    return runAll.entities.reduce(
      (acc, x) => ({
        created: acc.created + x.created_records,
        updated: acc.updated + x.updated_records,
        skipped: acc.skipped + x.skipped_records,
        failed: acc.failed + x.failed_records,
      }),
      { created: 0, updated: 0, skipped: 0, failed: 0 },
    );
  }, [runAll]);

  async function reloadEntity(e: IngestionEntity) {
    setBusyEntity(e.entity_name);
    setActionError(null);
    try {
      await runIngestion(e.entity_name);
      await refreshCounts();
    } catch (err) {
      setActionError(`Reload ${e.entity_name} failed: ${String(err)}`);
      await refreshCounts(); // persisted error + validation state still refresh
    } finally {
      setBusyEntity(null);
    }
  }

  async function confirmDeleteEntity() {
    if (!confirmEntity) return;
    setDeleting(true);
    setActionError(null);
    try {
      const res = await deleteEntity(confirmEntity.entity_name);
      if ((res as { outcome?: string }).outcome === "failed") {
        setActionError(
          `Delete ${confirmEntity.entity_name} failed: ${String((res as { reason?: string }).reason ?? "see server log")}`,
        );
      }
      await refreshCounts();
      setConfirmEntity(null);
    } catch (err) {
      setActionError(`Delete ${confirmEntity.entity_name} failed: ${String(err)}`);
    } finally {
      setDeleting(false);
    }
  }

  async function openDeleteAll() {
    setConfirmAll(true);
    setDeletePlan(null);
    try {
      setDeletePlan(await fetchDeletePlan());
    } catch (err) {
      setActionError(`Could not fetch the delete plan: ${String(err)}`);
      setConfirmAll(false);
    }
  }

  async function confirmDeleteAll() {
    setDeleting(true);
    setActionError(null);
    setDeleteReport(null);
    try {
      const report = await deleteAllEntities();
      setDeleteReport(report);
      await refreshCounts();
      setConfirmAll(false);
    } catch (err) {
      setActionError(`Delete all failed: ${String(err)}`);
    } finally {
      setDeleting(false);
    }
  }

  async function runAllNow() {
    setActionError(null);
    setDeleteReport(null);
    try {
      const override = batchOverride.trim() ? Number(batchOverride.trim()) : undefined;
      const s = await startRunAll(
        override && Number.isFinite(override) && override > 0 ? override : undefined,
      );
      setRunAll(s);
      startPolling();
    } catch (err) {
      setActionError(`Run all failed to start: ${String(err)}`);
    }
  }

  async function clearAllCheckpoints() {
    setActionError(null);
    try {
      await clearCheckpoints();
      await refreshCounts();
    } catch (err) {
      setActionError(`Clear checkpoints failed: ${String(err)}`);
    }
  }

  const dataSet = modes?.data_set ?? "sample";

  return (
    <div className="space-y-4 font-v2 text-v2-text">
      {/* Header card */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[3px] border border-v2-border bg-v2-card px-5 py-4">
        <div>
          <h1 className="text-[16px] font-semibold">Data Ingestion &amp; Sync</h1>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">
            Load V2 vertices and edges into TigerGraph. Dependency order is enforced on both load and delete.
            The Validation column reads the graph itself — not the checkpoint table.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Active data set comes from .env DATA_SET — real is the demo path */}
          <span
            className="inline-flex h-8 items-center gap-1.5 rounded-[3px] border border-v2-border bg-v2-sub-bg px-3 text-[11.5px]"
            title="Set DATA_SET in .env and restart the backend to change"
          >
            Data set: <span className="font-semibold">{dataSet}</span>
            {dataSet === "sample" && (
              <span className="text-[10px] text-v2-warn" title="Sample is a test asset only — demos and acceptance use DATA_SET=real">
                test asset
              </span>
            )}
          </span>
          {/* B3: per-run batch-size override */}
          <label className="flex h-8 items-center gap-1.5 rounded-[3px] border border-v2-border px-2 text-[11.5px] text-v2-muted">
            batch
            <input
              type="number"
              min={1}
              value={batchOverride}
              onChange={(e) => setBatchOverride(e.target.value)}
              placeholder="per-entity"
              disabled={runAllActive}
              className="w-20 bg-transparent text-right text-[11.5px] text-v2-text outline-none placeholder:text-v2-faint"
            />
          </label>
          <button
            type="button"
            onClick={clearAllCheckpoints}
            disabled={runAllActive || deleting}
            title="Reset batch records + row hashes (graph untouched) — the next load re-writes everything"
            className="h-8 rounded-[3px] border border-v2-border px-3 text-[11.5px] hover:bg-v2-sub-bg disabled:opacity-50"
          >
            Clear checkpoints
          </button>
          <button
            type="button"
            onClick={openDeleteAll}
            disabled={runAllActive || deleting}
            className="h-8 rounded-[3px] border border-v2-negative px-3 text-[11.5px] font-semibold text-v2-negative hover:bg-v2-negative-bg disabled:opacity-50"
          >
            Delete all
          </button>
          <button
            type="button"
            onClick={runAllNow}
            disabled={runAllActive}
            className="flex h-8 items-center gap-1.5 rounded-[3px] bg-v2-navy px-3.5 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark disabled:opacity-60"
          >
            {runAllActive ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3 w-3 fill-current" />}
            {runAllActive ? "Running…" : "Run All Ingestion"}
          </button>
        </div>
      </div>

      {actionError && (
        <div className="rounded-[3px] border border-v2-negative bg-v2-negative-bg px-4 py-2 text-[11.5px] text-v2-negative">
          {actionError}
        </div>
      )}

      {/* Run-all inline progress (B1: live per-entity position + tallies) */}
      {runAll && runAll.run_id && (
        <div className="space-y-1.5 rounded-[3px] border border-v2-border bg-v2-card px-5 py-2.5 text-[11.5px]">
          <div className="flex flex-wrap items-center gap-3">
            {runAllActive ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-v2-navy" />
            ) : runAll.status === "failed" ? (
              <span className="text-v2-negative">✗</span>
            ) : (
              <span className="text-v2-positive">✓</span>
            )}
            <span className="font-semibold">
              Full graph load · {runAll.completed_entities + runAll.failed_entities}/{runAll.total_entities} entities
            </span>
            {runTally && (
              <span className="text-v2-muted">
                {runTally.created.toLocaleString()} created · {runTally.updated.toLocaleString()} updated ·{" "}
                {runTally.skipped.toLocaleString()} skipped
                {runTally.failed > 0 && <span className="text-v2-negative"> · {runTally.failed} failed rows</span>}
              </span>
            )}
            {runAll.batch_size_override && (
              <span className="text-v2-faint">batch override: {runAll.batch_size_override}</span>
            )}
            {runAll.failed_entities > 0 && (
              <span className="text-v2-negative">{runAll.failed_entities} entities failed</span>
            )}
            {runAll.message && !runAllActive && <span className="text-v2-muted">{runAll.message}</span>}
            <div className="ml-auto h-1.5 w-48 overflow-hidden rounded-full bg-v2-header-bg">
              <div
                className={`h-full transition-all ${runAll.failed_entities ? "bg-v2-warn" : "bg-v2-navy"}`}
                style={{
                  width: `${runAll.total_entities ? Math.round(((runAll.completed_entities + runAll.failed_entities) / runAll.total_entities) * 100) : 0}%`,
                }}
              />
            </div>
          </div>
          {runAllActive && runAllCurrent && (
            <div className="flex flex-wrap items-center gap-3 pl-6 text-v2-muted">
              <span>
                now: <span className="font-medium text-v2-purple">{runAllCurrent.entity_name}</span>{" "}
                ({runAll.current_entity_index ?? "?"}/{runAll.total_entities})
              </span>
              <span className="tabular-nums">
                rows {runAllCurrent.processed_records.toLocaleString()}
                {runAllCurrent.total_records ? ` / ${runAllCurrent.total_records.toLocaleString()}` : ""}
              </span>
              <span className="text-v2-faint">batch {runAllCurrent.batch_size}</span>
            </div>
          )}
        </div>
      )}

      {/* B5: end-of-run remediation summary */}
      {runAllFailed.length > 0 && (
        <div className="rounded-[3px] border border-v2-negative bg-v2-negative-bg px-5 py-3 text-[11.5px]">
          <div className="font-semibold text-v2-negative">
            {runAllFailed.length} entit{runAllFailed.length === 1 ? "y" : "ies"} failed — the run continued past them.
            Fix and re-run only these:
          </div>
          <ol className="mt-1.5 space-y-1">
            {runAllFailed.map((f, i) => (
              <li key={f.entity_name} className="flex gap-2">
                <span className="w-4 text-right tabular-nums text-v2-muted">{i + 1}.</span>
                <div>
                  <span className="font-medium text-v2-purple">{f.entity_name}</span>{" "}
                  <span className="text-v2-text">{f.message ?? "see the row's error detail"}</span>
                  <div className="text-v2-muted">
                    → expand the row below for the persisted error and its remediation, fix the cause,
                    then click <span className="font-medium">Reload</span> on this entity only.
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Delete-all per-entity report (A6) */}
      {deleteReport && (
        <div
          className={`rounded-[3px] border px-5 py-2.5 text-[11.5px] ${deleteReport.failed_entities ? "border-v2-negative bg-v2-negative-bg" : "border-v2-border bg-v2-card"}`}
        >
          <span className="font-semibold">
            Delete all: {deleteReport.deleted_entities} entities deleted
            ({deleteReport.total_rows_deleted.toLocaleString()} rows)
          </span>
          {(deleteReport.failed_entities ?? 0) > 0 && (
            <span className="text-v2-negative">
              {" "}· {deleteReport.failed_entities} failed:{" "}
              {(deleteReport.failed ?? []).map((f) => `${f.entity_name} (${f.reason})`).join("; ")}
            </span>
          )}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <StatCard label="Vertex Types" value={loading ? "—" : String(stats.vertexTypes)} />
        <StatCard label="Edge Types" value={loading ? "—" : String(stats.edgeTypes)} />
        <StatCard label="Rows in Graph" value={stats.rowsInGraph == null ? "—" : stats.rowsInGraph.toLocaleString()} />
        <StatCard
          label="Validated"
          value={stats.validated == null ? "—" : `${stats.validated}/${entities.length || "—"}`}
        />
        <StatCard label="Last Run" value={stats.lastRun} />
      </div>

      {/* Entity manifest */}
      <div className="rounded-[3px] border border-v2-border bg-v2-card">
        <div className="flex items-center gap-3 border-b border-v2-border px-5 py-3">
          <h2 className="text-[14px] font-semibold">Entity Manifest</h2>
          <span className="text-[11.5px] text-v2-muted">
            loaded in dependency order — dimensions first, then facts, then analytics
          </span>
          <button
            type="button"
            onClick={() => void refreshValidation()}
            disabled={validating}
            title="Re-check every entity against the live graph"
            className="ml-auto flex h-7 items-center gap-1.5 rounded-[3px] border border-v2-border px-2.5 text-[11px] hover:bg-v2-sub-bg disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${validating ? "animate-spin" : ""}`} />
            {validating ? "Validating…" : "Re-validate"}
          </button>
          {validation && (
            <span className="text-[10.5px] text-v2-faint">checked {fmtRunTime(validation.generated_at)}</span>
          )}
        </div>
        <AsyncBoundary loading={loading && entities.length === 0} error={error} onRetry={load}>
          <div className="overflow-x-auto">
            <table className="w-full text-[11.5px]">
              <thead>
                <tr className="bg-v2-header-bg text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                  <th className="px-2 py-1.5" aria-label="expand" />
                  <th className="px-3 py-1.5">#</th>
                  <th className="px-3 py-1.5">Vertex / Edge</th>
                  <th className="px-3 py-1.5">Kind</th>
                  <th className="px-3 py-1.5">Source File</th>
                  <th className="px-3 py-1.5 text-right">Expected</th>
                  <th className="px-3 py-1.5 text-right">In graph</th>
                  <th className="px-3 py-1.5 text-right">Batch</th>
                  <th className="px-3 py-1.5">Validation</th>
                  <th className="px-3 py-1.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((e, i) => {
                  const v = validationByEntity.get(e.entity_name);
                  const run = runAll?.entities.find((x) => x.entity_name === e.entity_name);
                  const entityErrors = errorsByEntity.get(e.entity_name) ?? [];
                  const busy = busyEntity === e.entity_name;
                  const isRunning = busy || run?.status === "running";
                  const isOpen = expanded === e.entity_name;
                  const hasDetail = entityErrors.length > 0 || v?.conflict || run?.message;
                  return (
                    <EntityRow
                      key={e.entity_name}
                      index={i}
                      entity={e}
                      validationRow={v}
                      runRow={run}
                      entityErrors={entityErrors}
                      latest={latestBatch.get(e.entity_name)}
                      isRunning={!!isRunning}
                      isOpen={isOpen}
                      hasDetail={!!hasDetail}
                      onToggle={() => setExpanded(isOpen ? null : e.entity_name)}
                      actionsDisabled={busy || runAllActive || deleting}
                      busy={busy}
                      onReload={() => reloadEntity(e)}
                      onDelete={() => setConfirmEntity(e)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncBoundary>
        <p className="border-t border-v2-border-subtle px-5 py-3 text-[10.5px] italic text-v2-faint">
          Validation = graph count vs source CSV plus a sampled non-key-attribute check, read live from the graph.
          Delete removes edges before vertices and facts before dimensions; every destructive action asks for confirmation.
        </p>
      </div>

      {/* Confirm: delete one entity */}
      {confirmEntity && (
        <ConfirmDialog
          title={`Delete ${confirmEntity.tigergraph_vertex}?`}
          busy={deleting}
          confirmLabel="Delete"
          onCancel={() => setConfirmEntity(null)}
          onConfirm={confirmDeleteEntity}
        >
          <p className="text-[11.5px] text-v2-muted">
            All rows of <span className="font-medium text-v2-purple">{confirmEntity.tigergraph_vertex}</span>{" "}
            ({confirmEntity.kind}) will be removed from the graph and its ingestion checkpoints cleared.
            This cannot be undone; reload it from{" "}
            {confirmEntity.csv_file_name ? (
              <span className="font-medium">{confirmEntity.csv_file_name}</span>
            ) : (
              "a workflow re-run"
            )}{" "}
            afterwards.
          </p>
        </ConfirmDialog>
      )}

      {/* Confirm: delete all, showing the real ordered plan */}
      {confirmAll && (
        <ConfirmDialog
          title="Delete all loaded data?"
          busy={deleting}
          confirmLabel="Delete all"
          confirmDisabled={!deletePlan}
          onCancel={() => setConfirmAll(false)}
          onConfirm={confirmDeleteAll}
        >
          <p className="text-[11.5px] text-v2-muted">
            Every entity is deleted in dependency order — edges before vertices, facts before dimensions —
            so no orphaned edges remain. A failing entity is reported and does not abort the rest:
          </p>
          {deletePlan ? (
            <ol className="mt-2 max-h-56 overflow-y-auto rounded-[3px] border border-v2-border bg-v2-sub-bg px-3 py-2">
              {deletePlan.map((step, i) => (
                <li key={step.entity_name} className="flex gap-2 py-0.5 text-[11.5px]">
                  <span className="w-6 text-right tabular-nums text-v2-faint">{i + 1}.</span>
                  <span className="text-v2-purple">{step.target}</span>
                  <span className="text-v2-faint">({step.kind})</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-2 text-[11.5px] text-v2-faint">Loading delete order…</p>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}

function EntityRow({
  index,
  entity,
  validationRow,
  runRow,
  entityErrors,
  latest,
  isRunning,
  isOpen,
  hasDetail,
  onToggle,
  actionsDisabled,
  busy,
  onReload,
  onDelete,
}: {
  index: number;
  entity: IngestionEntity;
  validationRow: EntityValidation | undefined;
  runRow: import("@/lib/api/ingestion").RunAllEntityResult | undefined;
  entityErrors: IngestionErrorRow[];
  latest: IngestionBatchRow | undefined;
  isRunning: boolean;
  isOpen: boolean;
  hasDetail: boolean;
  onToggle: () => void;
  actionsDisabled: boolean;
  busy: boolean;
  onReload: () => void;
  onDelete: () => void;
}) {
  const failed = runRow?.status === "failed" || latest?.status === "failed" || entityErrors.length > 0;
  return (
    <>
      <tr
        className={`border-b border-v2-border-subtle last:border-0 ${isOpen ? "bg-v2-sub-bg" : ""}`}
      >
        <td className="px-2 py-1.5">
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={isOpen}
            aria-label={`details for ${entity.entity_name}`}
            className={`text-v2-muted hover:text-v2-text ${hasDetail || isOpen ? "" : "opacity-30"}`}
          >
            {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </td>
        <td className="px-3 py-1.5 text-v2-faint">{index + 1}</td>
        <td className="px-3 py-1.5 font-medium text-v2-purple">
          {entity.tigergraph_vertex}
          {isRunning && <Loader2 className="ml-1.5 inline h-3 w-3 animate-spin text-v2-navy" />}
          {failed && !isRunning && <span className="ml-1.5 text-v2-negative" title="has errors — expand">●</span>}
        </td>
        <td className="px-3 py-1.5 text-v2-muted">{entity.kind}</td>
        <td className="px-3 py-1.5 text-v2-muted">
          {entity.csv_file_name || <span className="italic text-v2-faint">— generated —</span>}
        </td>
        <td className="px-3 py-1.5 text-right tabular-nums">
          {validationRow?.expected_count == null ? (
            <span className="text-v2-faint">—</span>
          ) : (
            validationRow.expected_count.toLocaleString()
          )}
        </td>
        <td className="px-3 py-1.5 text-right tabular-nums">
          {validationRow?.graph_count == null ? (
            <span className="text-v2-faint">—</span>
          ) : validationRow.graph_count === 0 ? (
            <span className="text-v2-warn">0</span>
          ) : (
            validationRow.graph_count.toLocaleString()
          )}
        </td>
        <td className="px-3 py-1.5 text-right tabular-nums text-v2-muted">
          {(runRow?.batch_size || entity.batch_size).toLocaleString()}
        </td>
        <td className="px-3 py-1.5">
          <ValidationPill v={validationRow} />
        </td>
        <td className="px-3 py-1.5 text-right">
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onReload}
              disabled={actionsDisabled}
              className="text-[11.5px] text-v2-link hover:underline disabled:cursor-not-allowed disabled:text-v2-faint disabled:no-underline"
            >
              {busy ? "Loading…" : "Reload"}
            </button>
            <button
              type="button"
              onClick={onDelete}
              disabled={actionsDisabled}
              className="text-[11.5px] text-v2-negative hover:underline disabled:cursor-not-allowed disabled:text-v2-faint disabled:no-underline"
            >
              Delete
            </button>
          </div>
        </td>
      </tr>
      {isOpen && (
        <tr className="border-b border-v2-border-subtle bg-v2-sub-bg last:border-0">
          <td />
          <td colSpan={9} className="px-3 pb-3 pt-0.5">
            <div className="space-y-2 rounded-[3px] border border-v2-border bg-v2-card px-4 py-3 text-[11px]">
              {validationRow?.conflict && (
                <div className="text-v2-negative">
                  <span className="font-semibold">Validation conflict:</span> {validationRow.conflict}
                </div>
              )}
              {validationRow && (
                <div className="text-v2-muted">
                  Graph {validationRow.graph_count ?? "?"} vs CSV {validationRow.expected_count ?? "?"} · attribute
                  sample: {validationRow.attr_check ?? "—"}
                  {validationRow.attr_sample_size ? ` (${validationRow.attr_sample_size} rows)` : ""} · checkpoint says{" "}
                  {validationRow.checkpoint.status ?? "never run"} ({validationRow.checkpoint.created} created,{" "}
                  {validationRow.checkpoint.updated} updated, {validationRow.checkpoint.skipped} skipped) · checked{" "}
                  {fmtRunTime(validationRow.checked_at)}
                </div>
              )}
              {runRow?.message && <div className="text-v2-muted">Last run: {runRow.message}</div>}
              {entityErrors.length > 0 ? (
                <div className="space-y-2">
                  <div className="font-semibold text-v2-negative">
                    Persisted errors ({entityErrors.length}):
                  </div>
                  {entityErrors.slice(0, 5).map((er) => (
                    <div key={er.error_id} className="rounded-[3px] border border-v2-border-subtle px-3 py-2">
                      <div className="text-v2-text">
                        {er.row_number != null && <span className="font-medium">row {er.row_number}</span>}
                        {er.primary_key && <span className="text-v2-muted"> · key {er.primary_key}</span>}
                        <span className="text-v2-faint"> · {fmtRunTime(er.created_at)}</span>
                      </div>
                      <div className="mt-0.5 break-all text-v2-negative">{er.error_message}</div>
                      <div className="mt-1 text-v2-muted">
                        <span className="font-semibold">Next step:</span> {er.remediation}
                      </div>
                    </div>
                  ))}
                  {entityErrors.length > 5 && (
                    <div className="text-v2-faint">…{entityErrors.length - 5} older errors kept server-side</div>
                  )}
                </div>
              ) : (
                !validationRow?.conflict && <div className="text-v2-faint">No stored errors for this entity.</div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[3px] border border-v2-border bg-v2-card px-5 py-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">{label}</div>
      <div className="mt-1 text-[19px] font-semibold">{value}</div>
    </div>
  );
}

function ConfirmDialog({
  title,
  children,
  confirmLabel,
  confirmDisabled = false,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  confirmDisabled?: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-md rounded-[3px] border border-v2-border bg-v2-card p-5 font-v2 text-v2-text shadow-lg">
        <h3 className="text-[14px] font-semibold">{title}</h3>
        <div className="mt-2">{children}</div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="h-8 rounded-[3px] border border-v2-border px-3 text-[11.5px] hover:bg-v2-sub-bg disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
            className="flex h-8 items-center gap-1.5 rounded-[3px] bg-v2-negative px-3 text-[11.5px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-3 w-3 animate-spin" />}
            {busy ? "Deleting…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
