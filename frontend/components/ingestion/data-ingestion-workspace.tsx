"use client";
import { type } from "@/styles/tokens";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Database, PlayCircle, GitBranch, CheckCircle2, AlertTriangle, Rocket, Loader2 } from "lucide-react";
import {
  fetchIngestionEntities,
  fetchManifest,
  runIngestion,
  startRunAll,
  fetchRunAllStatus,
  type IngestionEntity,
  type IngestionBatchStatus,
  type ManifestSummary,
  type RunAllStatus,
} from "@/lib/api/ingestion";
import { KpiStatCard } from "@/components/patterns/kpi-stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "glass"> = {
  completed: "success",
  running: "warning",
  failed: "destructive",
  pending: "glass",
};

export function DataIngestionWorkspace() {
  const [entities, setEntities] = useState<IngestionEntity[]>([]);
  const [manifest, setManifest] = useState<ManifestSummary | null>(null);
  const [selected, setSelected] = useState<string>("advisor");
  const [kindFilter, setKindFilter] = useState<"all" | "vertex" | "edge">("all");
  const [batch, setBatch] = useState<IngestionBatchStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [runAll, setRunAll] = useState<RunAllStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchIngestionEntities().then(setEntities).catch(() => setEntities([]));
    fetchManifest().then(setManifest).catch(() => setManifest(null));
    // resume showing an in-flight run-all after navigation
    fetchRunAllStatus()
      .then((s) => {
        if (s.run_id) setRunAll(s);
        if (s.status === "running") startPolling();
      })
      .catch(() => null);
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const kpis = useMemo(() => {
    const vertices = entities.filter((e) => e.kind === "vertex").length;
    const edges = entities.filter((e) => e.kind === "edge").length;
    const rows = entities.reduce((s, e) => s + (e.expected_rows ?? 0), 0);
    return { entities: entities.length, vertices, edges, rows };
  }, [entities]);

  const visibleEntities = useMemo(
    () => (kindFilter === "all" ? entities : entities.filter((e) => e.kind === kindFilter)),
    [entities, kindFilter],
  );

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await fetchRunAllStatus();
        setRunAll(s);
        if (s.status !== "running") stopPolling();
      } catch {
        /* keep polling; transient */
      }
    }, 1500);
  }, []);

  async function run() {
    setBusy(true);
    try {
      const r = await runIngestion(selected);
      setBatch(r.batch_status);
    } finally {
      setBusy(false);
    }
  }

  async function runAllNow() {
    const s = await startRunAll();
    setRunAll(s);
    startPolling();
  }

  const runAllActive = runAll?.status === "running";
  const runAllProgress = runAll && runAll.total_entities > 0
    ? Math.round(((runAll.completed_entities + runAll.failed_entities) / runAll.total_entities) * 100)
    : 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Badge variant="glass">Data Ingestion &amp; Sync</Badge>
          <h2 className={`mt-2 ${type.pageTitle}`}>Manifest-Driven Ingestion &amp; Checkpointing</h2>
          <p className="text-[12px] text-muted-foreground">
            Complete source-of-truth manifest (docs/tigergraph_foundation) — every vertex and edge type,
            upsert with batch/checkpoint/retry.
            {manifest && ` Graph ${manifest.graph_name}.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-8 rounded-lg border border-border bg-background px-2 text-[12px]"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {entities.map((e) => (
              <option key={e.entity_name} value={e.entity_name}>
                {e.kind === "edge" ? "edge · " : ""}{e.entity_name}
              </option>
            ))}
          </select>
          <Button variant="outline" className="h-8 gap-2 text-[12px]" onClick={run} disabled={busy || runAllActive}>
            <PlayCircle className="h-4 w-4" /> {busy ? "Running…" : "Run Ingestion"}
          </Button>
          <Button variant="premium" className="h-8 gap-2 text-[12px]" onClick={runAllNow} disabled={runAllActive}>
            {runAllActive ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
            {runAllActive ? "Loading Full Graph…" : "Run All Ingestion"}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiStatCard label="Vertex Types" value={String(kpis.vertices)} />
        <KpiStatCard label="Edge Types" value={String(kpis.edges)} />
        <KpiStatCard label="Manifest Files" value={String(kpis.entities)} />
        <KpiStatCard label="Seed Rows" value={kpis.rows.toLocaleString()} />
      </div>

      {runAll && runAll.run_id && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between p-3">
            <CardTitle className="flex items-center gap-2 text-[13px]">
              {runAll.status === "failed" ? (
                <AlertTriangle className="h-4 w-4 text-destructive" />
              ) : runAll.status === "running" ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              )}
              Full Graph Load · {runAll.completed_entities}/{runAll.total_entities} entities ·{" "}
              {runAll.total_rows_processed.toLocaleString()} rows
              {runAll.current_entity && ` · now: ${runAll.current_entity}`}
            </CardTitle>
            <Badge variant={STATUS_VARIANT[runAll.status] ?? "glass"}>{runAll.status}</Badge>
          </CardHeader>
          <CardContent className="space-y-2 p-3">
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full transition-all ${runAll.failed_entities ? "bg-amber-500" : "bg-primary"}`}
                style={{ width: `${runAllProgress}%` }}
              />
            </div>
            {runAll.message && (
              <div className="text-[11px] text-muted-foreground">
                {runAll.message}
                {runAll.failed_entities > 0 && ` · ${runAll.failed_entities} entities failed (see below)`}
              </div>
            )}
            <div className="max-h-64 overflow-y-auto rounded-lg border">
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 bg-background">
                  <tr className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-2 py-1.5">Entity</th>
                    <th className="px-2 py-1.5">Kind</th>
                    <th className="px-2 py-1.5 text-right">Rows</th>
                    <th className="px-2 py-1.5 text-right">Created</th>
                    <th className="px-2 py-1.5 text-right">Updated</th>
                    <th className="px-2 py-1.5 text-right">Skipped</th>
                    <th className="px-2 py-1.5 text-right">Failed</th>
                    <th className="px-2 py-1.5">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runAll.entities.map((e) => (
                    <tr key={e.entity_name} className="border-b last:border-0">
                      <td className="px-2 py-1 font-mono">{e.entity_name}</td>
                      <td className="px-2 py-1 text-muted-foreground">{e.kind}</td>
                      <td className="px-2 py-1 text-right font-mono">
                        {e.processed_records.toLocaleString()}/{e.total_records.toLocaleString()}
                      </td>
                      <td className="px-2 py-1 text-right font-mono">{e.created_records.toLocaleString()}</td>
                      <td className="px-2 py-1 text-right font-mono">{e.updated_records.toLocaleString()}</td>
                      <td className="px-2 py-1 text-right font-mono">{e.skipped_records.toLocaleString()}</td>
                      <td className={`px-2 py-1 text-right font-mono ${e.failed_records ? "text-destructive" : ""}`}>
                        {e.failed_records}
                      </td>
                      <td className="px-2 py-1">
                        <Badge variant={STATUS_VARIANT[e.status] ?? "glass"} className="text-[9px]">
                          {e.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {batch && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between p-3">
            <CardTitle className="flex items-center gap-2 text-[13px]">
              {batch.status === "failed" ? (
                <AlertTriangle className="h-4 w-4 text-destructive" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-primary" />
              )}
              Last Run · {batch.entity_name} ({batch.file_name})
            </CardTitle>
            <Badge variant={STATUS_VARIANT[batch.status] ?? "glass"}>{batch.status}</Badge>
          </CardHeader>
          <CardContent className="space-y-2 p-3">
            <div className="grid grid-cols-2 gap-2 text-[12px] sm:grid-cols-4">
              <Stat label="Total" value={batch.total_records} />
              <Stat label="Processed" value={batch.processed_records} />
              <Stat label="Created" value={batch.created_records} />
              <Stat label="Updated" value={batch.updated_records} />
              <Stat label="Skipped" value={batch.skipped_records} />
              <Stat label="Failed" value={batch.failed_records} />
              <Stat label="Last Row" value={batch.last_processed_row} />
              <Stat label="Progress" value={`${batch.progress_percent.toFixed(0)}%`} />
            </div>
            {batch.message && (
              <div className="rounded-lg border bg-muted/40 px-3 py-2 font-mono text-[11px] text-muted-foreground">
                {batch.message} · checkpoint {batch.batch_id}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between p-3">
          <CardTitle className="flex items-center gap-2 text-[13px]">
            <Database className="h-4 w-4 text-primary" /> Entity Manifest ({visibleEntities.length})
          </CardTitle>
          <div className="flex gap-1">
            {(["all", "vertex", "edge"] as const).map((k) => (
              <Button
                key={k}
                variant={kindFilter === k ? "secondary" : "ghost"}
                className="h-6 px-2 text-[11px] capitalize"
                onClick={() => setKindFilter(k)}
              >
                {k === "all" ? `All (${entities.length})` : k === "vertex" ? `Vertices (${kpis.vertices})` : `Edges (${kpis.edges})`}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="max-h-[28rem] overflow-x-auto overflow-y-auto">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 bg-background">
                <tr className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">Entity</th>
                  <th className="px-3 py-2">Kind</th>
                  <th className="px-3 py-2">CSV</th>
                  <th className="px-3 py-2">Target Type</th>
                  <th className="px-3 py-2">Key</th>
                  <th className="px-3 py-2 text-right">Expected Rows</th>
                  <th className="px-3 py-2 text-right">Batch</th>
                </tr>
              </thead>
              <tbody>
                {visibleEntities.map((e) => (
                  <tr
                    key={e.entity_name}
                    className={`cursor-pointer border-b last:border-0 hover:bg-muted/40 ${selected === e.entity_name ? "bg-muted/40" : ""}`}
                    onClick={() => setSelected(e.entity_name)}
                  >
                    <td className="px-3 py-2 font-medium">{e.entity_name}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                        {e.kind === "edge" ? <GitBranch className="h-3 w-3" /> : <Database className="h-3 w-3" />}
                        {e.kind}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">{e.csv_file_name}</td>
                    <td className="px-3 py-2 font-mono text-[11px]">{e.tigergraph_vertex}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">{e.primary_key}</td>
                    <td className="px-3 py-2 text-right font-mono">{(e.expected_rows ?? 0).toLocaleString()}</td>
                    <td className="px-3 py-2 text-right font-mono">{e.batch_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border bg-background/70 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-mono text-[15px] font-bold">{value}</div>
    </div>
  );
}
