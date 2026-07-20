"use client";
/**
 * Data Ingestion & Sync (UI_SPEC §8, reference 05_data_ingestion.png).
 * Loads V2 vertices and edges into TigerGraph in manifest dependency order;
 * delete cascades in reverse order (edges before vertices, facts before
 * dimensions). Every destructive action confirms first, and the confirm
 * dialog shows the real delete order from GET /ingestion/delete-plan.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronDown, Loader2, Play } from "lucide-react";
import {
  deleteAllEntities,
  deleteEntity,
  fetchBatches,
  fetchDeletePlan,
  fetchIngestionEntities,
  fetchRunAllStatus,
  runIngestion,
  startRunAll,
  type DeletePlanStep,
  type IngestionBatchRow,
  type IngestionEntity,
  type RunAllStatus,
} from "@/lib/api/ingestion";
import { v2Api } from "@/lib/api/v2";
import { AsyncBoundary } from "@/components/patterns/async-state";
import { ProvenanceBadge } from "@/components/patterns/provenance-badge";
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

function dominantFlag(mix: Record<string, number> | undefined): string | null {
  if (!mix) return null;
  let best: string | null = null;
  let bestN = 0;
  for (const [flag, n] of Object.entries(mix)) {
    if (n > bestN) { best = flag; bestN = n; }
  }
  return best;
}

type RowStatus = "loaded" | "awaiting" | "failed" | "running";

const STATUS_STYLE: Record<RowStatus, { label: string; cls: string }> = {
  loaded: { label: "Loaded", cls: "bg-v2-positive-bg text-v2-positive" },
  awaiting: { label: "Awaiting", cls: "bg-v2-warn-bg text-v2-warn" },
  failed: { label: "Failed", cls: "bg-v2-negative-bg text-v2-negative" },
  running: { label: "Running", cls: "bg-v2-header-bg text-v2-navy" },
};

function StatusPill({ status }: { status: RowStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9.5px] font-semibold ${s.cls}`}>
      <span aria-hidden>●</span> {s.label}
    </span>
  );
}

export function DataIngestionWorkspace() {
  const { modes } = useV2Context();
  const [entities, setEntities] = useState<IngestionEntity[]>([]);
  const [counts, setCounts] = useState<OpsCounts | null>(null);
  const [batches, setBatches] = useState<IngestionBatchRow[]>([]);
  const [runAll, setRunAll] = useState<RunAllStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyEntity, setBusyEntity] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dataSetOpen, setDataSetOpen] = useState(false);
  // Confirm dialogs
  const [confirmEntity, setConfirmEntity] = useState<IngestionEntity | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [deletePlan, setDeletePlan] = useState<DeletePlanStep[] | null>(null);
  const [deleting, setDeleting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshCounts = useCallback(async () => {
    const [c, b] = await Promise.allSettled([v2Api.opsCounts(), fetchBatches()]);
    if (c.status === "fulfilled") setCounts(c.value);
    if (b.status === "fulfilled") setBatches(b.value);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

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
    ]).then(([e, c, b, r]) => {
      if (e.status === "fulfilled") setEntities(e.value);
      else setError(String(e.reason));
      if (c.status === "fulfilled") setCounts(c.value);
      if (b.status === "fulfilled") setBatches(b.value);
      if (r.status === "fulfilled") {
        if (r.value.run_id) setRunAll(r.value);
        if (r.value.status === "running") startPolling();
      }
      setLoading(false);
    });
  }, [startPolling]);

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

  const stats = useMemo(() => {
    const vertexTypes = entities.filter((e) => e.kind === "vertex").length;
    const edgeTypes = entities.filter((e) => e.kind === "edge").length;
    const rowsLoaded = counts
      ? Object.values(counts.counts).reduce((s, n) => s + n, 0)
      : null;
    const lastRun = batches.length ? fmtRunTime(batches[0].updated_at) : "—";
    return { vertexTypes, edgeTypes, rowsLoaded, lastRun };
  }, [entities, counts, batches]);

  const runAllActive = runAll?.status === "running";

  function rowStatus(e: IngestionEntity): RowStatus {
    const run = runAll?.entities.find((x) => x.entity_name === e.entity_name);
    const batch = latestBatch.get(e.entity_name);
    if (busyEntity === e.entity_name || run?.status === "running") return "running";
    if (run?.status === "failed" || batch?.status === "failed") return "failed";
    const loaded = counts?.counts[e.tigergraph_vertex] ?? 0;
    if (e.kind === "vertex") return loaded > 0 ? "loaded" : "awaiting";
    // Edges: no per-type count from ops/counts — go by the last load result.
    if (run?.status === "completed" || batch?.status === "completed") return "loaded";
    return "awaiting";
  }

  async function reloadEntity(e: IngestionEntity) {
    setBusyEntity(e.entity_name);
    setActionError(null);
    try {
      await runIngestion(e.entity_name);
      await refreshCounts();
    } catch (err) {
      setActionError(`Reload ${e.entity_name} failed: ${String(err)}`);
    } finally {
      setBusyEntity(null);
    }
  }

  async function confirmDeleteEntity() {
    if (!confirmEntity) return;
    setDeleting(true);
    setActionError(null);
    try {
      await deleteEntity(confirmEntity.entity_name);
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
    try {
      await deleteAllEntities();
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
    try {
      const s = await startRunAll();
      setRunAll(s);
      startPolling();
    } catch (err) {
      setActionError(`Run all failed to start: ${String(err)}`);
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
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Data-set selector: sample is the only loadable set in this build */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setDataSetOpen((o) => !o)}
              className="flex h-8 items-center gap-1.5 rounded-[3px] border border-v2-border bg-v2-card px-3 text-[11.5px] hover:bg-v2-sub-bg"
              aria-haspopup="listbox"
              aria-expanded={dataSetOpen}
            >
              {dataSet === "sample" ? "Sample data" : "Real data"}
              <ChevronDown className="h-3 w-3 text-v2-muted" />
            </button>
            {dataSetOpen && (
              <div
                className="absolute right-0 z-20 mt-1 w-44 rounded-[3px] border border-v2-border bg-v2-card py-1 shadow-md"
                role="listbox"
              >
                <div
                  className={`px-3 py-1.5 text-[11.5px] ${dataSet === "sample" ? "font-semibold text-v2-navy" : ""}`}
                  role="option"
                  aria-selected={dataSet === "sample"}
                >
                  Sample data{dataSet === "sample" ? " ✓" : ""}
                </div>
                <div
                  className="cursor-not-allowed px-3 py-1.5 text-[11.5px] text-v2-faint"
                  role="option"
                  aria-selected={false}
                  aria-disabled
                  title="client CSVs not present"
                >
                  Real data
                </div>
              </div>
            )}
          </div>
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

      {/* Run-all inline progress */}
      {runAll && runAll.run_id && (
        <div className="flex flex-wrap items-center gap-3 rounded-[3px] border border-v2-border bg-v2-card px-5 py-2.5 text-[11.5px]">
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
          {runAll.current_entity && <span className="text-v2-muted">now: {runAll.current_entity}</span>}
          <span className="text-v2-muted">{runAll.total_rows_processed.toLocaleString()} rows processed</span>
          {runAll.failed_entities > 0 && (
            <span className="text-v2-negative">{runAll.failed_entities} failed</span>
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
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Vertex Types" value={loading ? "—" : String(stats.vertexTypes)} />
        <StatCard label="Edge Types" value={loading ? "—" : String(stats.edgeTypes)} />
        <StatCard label="Rows Loaded" value={stats.rowsLoaded == null ? "—" : stats.rowsLoaded.toLocaleString()} />
        <StatCard label="Last Run" value={stats.lastRun} />
      </div>

      {/* Entity manifest */}
      <div className="rounded-[3px] border border-v2-border bg-v2-card">
        <div className="flex items-baseline gap-3 border-b border-v2-border px-5 py-3">
          <h2 className="text-[14px] font-semibold">Entity Manifest</h2>
          <span className="text-[11.5px] text-v2-muted">
            loaded in dependency order — dimensions first, then facts, then analytics
          </span>
        </div>
        <AsyncBoundary loading={loading && entities.length === 0} error={error} onRetry={load}>
          <div className="overflow-x-auto">
            <table className="w-full text-[11.5px]">
              <thead>
                <tr className="bg-v2-header-bg text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                  <th className="px-4 py-1.5">#</th>
                  <th className="px-4 py-1.5">Vertex / Edge</th>
                  <th className="px-4 py-1.5">Kind</th>
                  <th className="px-4 py-1.5">Source File</th>
                  <th className="px-4 py-1.5 text-right">Expected</th>
                  <th className="px-4 py-1.5 text-right">Loaded</th>
                  <th className="px-4 py-1.5">Status</th>
                  <th className="px-4 py-1.5">Data</th>
                  <th className="px-4 py-1.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((e, i) => {
                  const loaded = e.kind === "vertex" ? counts?.counts[e.tigergraph_vertex] ?? 0 : null;
                  const flag = dominantFlag(counts?.source_mix[e.tigergraph_vertex]);
                  const generated = !flag && e.expected_rows == null;
                  const status = rowStatus(e);
                  const busy = busyEntity === e.entity_name;
                  return (
                    <tr key={e.entity_name} className="border-b border-v2-border-subtle last:border-0">
                      <td className="px-4 py-1.5 text-v2-faint">{i + 1}</td>
                      <td className="px-4 py-1.5 font-medium text-v2-purple">{e.tigergraph_vertex}</td>
                      <td className="px-4 py-1.5 text-v2-muted">{e.kind}</td>
                      <td className="px-4 py-1.5 text-v2-muted">
                        {e.csv_file_name || <span className="italic text-v2-faint">— generated —</span>}
                      </td>
                      <td className="px-4 py-1.5 text-right tabular-nums">
                        {e.expected_rows == null ? <span className="text-v2-faint">—</span> : e.expected_rows.toLocaleString()}
                      </td>
                      <td className="px-4 py-1.5 text-right tabular-nums">
                        {loaded == null ? (
                          <span className="text-v2-faint">—</span>
                        ) : loaded === 0 ? (
                          <span className="text-v2-warn">0</span>
                        ) : (
                          loaded.toLocaleString()
                        )}
                      </td>
                      <td className="px-4 py-1.5"><StatusPill status={status} /></td>
                      <td className="px-4 py-1.5">
                        {flag ? (
                          <ProvenanceBadge value={flag} />
                        ) : generated ? (
                          <span className="inline-block rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-navy">
                            Generated
                          </span>
                        ) : (
                          <span className="text-v2-faint">—</span>
                        )}
                      </td>
                      <td className="px-4 py-1.5 text-right">
                        <div className="flex justify-end gap-3">
                          <button
                            type="button"
                            disabled
                            title="drop CSVs into data/<set>/ — file upload not available in this build"
                            className="cursor-not-allowed text-[11.5px] text-v2-faint"
                          >
                            Upload
                          </button>
                          <button
                            type="button"
                            onClick={() => reloadEntity(e)}
                            disabled={busy || runAllActive || deleting}
                            className="text-[11.5px] text-v2-link hover:underline disabled:cursor-not-allowed disabled:text-v2-faint disabled:no-underline"
                          >
                            {busy ? "Loading…" : "Reload"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmEntity(e)}
                            disabled={busy || runAllActive || deleting}
                            className="text-[11.5px] text-v2-negative hover:underline disabled:cursor-not-allowed disabled:text-v2-faint disabled:no-underline"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncBoundary>
        <p className="border-t border-v2-border-subtle px-5 py-3 text-[10.5px] italic text-v2-faint">
          Delete removes edges before vertices and facts before dimensions, so no orphaned edges remain.
          Every destructive action asks for confirmation.
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
            so no orphaned edges remain:
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
