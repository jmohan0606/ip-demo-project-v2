"use client";
/**
 * Connectivity & Environment Health (UI_SPEC §9). Keeps V1's honesty contract:
 * every dependency is ACTIVELY exercised by the backend, and if
 * GRAPH_CLIENT_MODE=real is being served by the local store, /env-health goes
 * red and this screen shows the real error prominently — never green on a
 * fallback. The reconciliation panel puts ingestion counts, graph counts and
 * manifest expectations side by side and highlights mismatches.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { fetchEnvHealth, type EnvHealthCheck, type EnvHealthReport } from "@/lib/api/env-health";
import {
  fetchBatches,
  fetchIngestionEntities,
  fetchRunAllStatus,
  type IngestionBatchRow,
  type IngestionEntity,
  type RunAllStatus,
} from "@/lib/api/ingestion";
import { v2Api } from "@/lib/api/v2";
import { AsyncBoundary } from "@/components/patterns/async-state";

type OpsCounts = {
  counts: Record<string, number>;
  source_mix: Record<string, Record<string, number>>;
  served_by_tier: number;
};

function OverallPill({ overall }: { overall: "green" | "red" }) {
  const ok = overall === "green";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[10.5px] font-semibold uppercase tracking-[0.5px] ${
        ok ? "bg-v2-positive-bg text-v2-positive" : "bg-v2-negative-bg text-v2-negative"
      }`}
    >
      ● {ok ? "Connected" : "Failed"}
    </span>
  );
}

function CheckPill({ status }: { status: "green" | "red" }) {
  const ok = status === "green";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase ${
        ok ? "bg-v2-positive-bg text-v2-positive" : "bg-v2-negative-bg text-v2-negative"
      }`}
    >
      ● {ok ? "OK" : "Failed"}
    </span>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-0.5 text-[11.5px]">
      <span className="text-v2-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function HealthCard({
  title,
  status,
  latencyMs,
  error,
  children,
}: {
  title: string;
  status: "green" | "red";
  latencyMs?: number | null;
  error?: string | null;
  children?: React.ReactNode;
}) {
  const red = status === "red";
  return (
    <div className={`rounded-[3px] border bg-v2-card ${red ? "border-v2-negative" : "border-v2-border"}`}>
      <div
        className={`flex items-center justify-between border-b px-5 py-2.5 ${
          red ? "border-v2-negative bg-v2-negative-bg" : "border-v2-border-subtle bg-v2-sub-bg"
        }`}
      >
        <h3 className="text-[14px] font-semibold">{title}</h3>
        <div className="flex items-center gap-2">
          {latencyMs != null && <span className="text-[10.5px] text-v2-faint">{latencyMs} ms</span>}
          <CheckPill status={status} />
        </div>
      </div>
      <div className="px-5 py-3">
        {red && error && (
          <p className="mb-2 rounded-[3px] bg-v2-negative-bg px-3 py-2 text-[11.5px] font-semibold text-v2-negative">
            {error}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}

export function EnvHealthWorkspace() {
  const [report, setReport] = useState<EnvHealthReport | null>(null);
  const [counts, setCounts] = useState<OpsCounts | null>(null);
  const [entities, setEntities] = useState<IngestionEntity[]>([]);
  const [batches, setBatches] = useState<IngestionBatchRow[]>([]);
  const [runAll, setRunAll] = useState<RunAllStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.allSettled([
      fetchEnvHealth(),
      v2Api.opsCounts(),
      fetchIngestionEntities(),
      fetchBatches(),
      fetchRunAllStatus(),
    ]).then(([h, c, e, b, r]) => {
      if (h.status === "fulfilled") setReport(h.value);
      else setError(String(h.reason));
      if (c.status === "fulfilled") setCounts(c.value);
      if (e.status === "fulfilled") setEntities(e.value);
      if (b.status === "fulfilled") setBatches(b.value);
      if (r.status === "fulfilled") setRunAll(r.value);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const tg: EnvHealthCheck | undefined = report?.checks.find((c) => c.component === "TigerGraph");
  const llm: EnvHealthCheck | undefined = report?.checks.find((c) => c.component === "LLM");

  const vertexEntities = entities.filter((e) => e.kind === "vertex");
  const failedBatches = batches.filter((b) => b.status === "failed").length;
  const lastBatch = batches[0] ?? null;

  return (
    <div className="space-y-4 font-v2 text-v2-text">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[3px] border border-v2-border bg-v2-card px-5 py-4">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-[16px] font-semibold">Connectivity &amp; Environment Health</h1>
            <p className="mt-0.5 text-[11.5px] text-v2-muted">
              Every dependency is actively exercised on each check — a fallback is reported, never hidden.
            </p>
          </div>
          {report && <OverallPill overall={report.overall} />}
        </div>
        <div className="flex items-center gap-3">
          {report && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(report.modes).map(([k, v]) => (
                <span
                  key={k}
                  className="rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-navy"
                >
                  {k.replace(/_client_mode$|_mode$/, "")}: {v}
                </span>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="flex h-8 items-center gap-1.5 rounded-[3px] bg-v2-navy px-3 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Re-check
          </button>
        </div>
      </div>

      <AsyncBoundary loading={loading && !report} error={report ? null : error} onRetry={load}>
        <div className="grid gap-4 lg:grid-cols-2">
          {/* TigerGraph */}
          {tg && (
            <HealthCard title="TigerGraph" status={tg.status} latencyMs={tg.latency_ms} error={tg.error}>
              <DetailRow label="mode" value={String(tg.mode ?? "—")} />
              <DetailRow label="graph" value={String(tg.graph ?? "—")} />
              <DetailRow
                label="active_tier"
                value={
                  tg.active_tier != null ? (
                    <span className={tg.active_tier === 1 ? "text-v2-positive" : "text-v2-warn"}>
                      {tg.active_tier} · {String(tg.active_tier_name ?? "")}
                    </span>
                  ) : (
                    "—"
                  )
                }
              />
              <DetailRow label="counts_served_by_tier" value={tg.counts_served_by_tier ?? "—"} />
              <DetailRow label="counts_source" value={String(tg.counts_source ?? "—")} />
              <DetailRow
                label="schema_installed"
                value={
                  tg.schema_installed == null ? "—" : tg.schema_installed ? (
                    <span className="text-v2-positive">✓ yes</span>
                  ) : (
                    <span className="text-v2-negative">✗ no</span>
                  )
                }
              />
              <DetailRow label="vertex_type_count" value={tg.vertex_type_count ?? "—"} />
              <DetailRow
                label="total_vertices"
                value={tg.total_vertices != null ? Number(tg.total_vertices).toLocaleString() : "—"}
              />
              {tg.row_counts && Object.keys(tg.row_counts).length > 0 && (
                <div className="mt-2 overflow-x-auto rounded-[3px] border border-v2-border-subtle">
                  <table className="w-full text-[11.5px]">
                    <thead>
                      <tr className="bg-v2-header-bg text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                        <th className="px-3 py-1">Vertex type</th>
                        <th className="px-3 py-1 text-right">Rows</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(tg.row_counts).map(([vt, n]) => (
                        <tr key={vt} className="border-t border-v2-border-subtle">
                          <td className="px-3 py-1 text-v2-purple">{vt}</td>
                          <td className="px-3 py-1 text-right tabular-nums">{Number(n).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </HealthCard>
          )}

          {/* LLM */}
          {llm && (
            <HealthCard title="LLM" status={llm.status} latencyMs={llm.latency_ms} error={llm.error}>
              <DetailRow label="mode" value={String(llm.mode ?? "—")} />
              <DetailRow label="model" value={String(llm.model ?? "—")} />
              <DetailRow label="generation_ms" value={llm.generation_ms != null ? `${llm.generation_ms} ms` : "—"} />
              {llm.response_preview != null && (
                <div className="mt-2 rounded-[3px] bg-v2-sub-bg px-3 py-2 text-[11.5px] text-v2-muted">
                  Test generation: &ldquo;{String(llm.response_preview)}&rdquo;
                </div>
              )}
            </HealthCard>
          )}

          {/* Local store */}
          <HealthCard title="Local store" status={counts ? "green" : "red"} error={counts ? null : "V2 ops counts unavailable — /api/v2/ops/counts did not respond."}>
            {counts && (
              <>
                <DetailRow
                  label="currently serving V2 queries"
                  value={
                    counts.served_by_tier === 2 ? (
                      <span className="text-v2-warn">yes — tier 2 (local store)</span>
                    ) : (
                      <span>no — tier 1 (TigerGraph) is serving</span>
                    )
                  }
                />
                <DetailRow label="vertex types with rows" value={Object.keys(counts.counts).length} />
                <DetailRow
                  label="total rows"
                  value={Object.values(counts.counts).reduce((s, n) => s + n, 0).toLocaleString()}
                />
                <p className="mt-2 text-[10.5px] italic text-v2-faint">
                  The local store implements the same run_query contract as TigerGraph (tier 2 fallback).
                  Counts above come from /api/v2/ops/counts, served by tier {counts.served_by_tier}.
                </p>
              </>
            )}
          </HealthCard>

          {/* Ingestion state */}
          <HealthCard title="Ingestion state" status={failedBatches > 0 ? "red" : "green"} error={failedBatches > 0 ? `${failedBatches} ingestion batch(es) failed — see Data Ingestion for details.` : null}>
            <DetailRow
              label="last full run"
              value={
                runAll?.run_id
                  ? `${runAll.status} · ${runAll.completed_entities}/${runAll.total_entities} entities`
                  : "never run"
              }
            />
            <DetailRow
              label="last batch"
              value={
                lastBatch
                  ? `${lastBatch.entity_name} · ${lastBatch.status} · ${lastBatch.processed_records.toLocaleString()} rows`
                  : "—"
              }
            />
            <DetailRow label="checkpointed batches" value={batches.length} />
            <DetailRow
              label="failed batches"
              value={failedBatches > 0 ? <span className="text-v2-negative">{failedBatches}</span> : "0"}
            />
          </HealthCard>
        </div>

        {/* Reconciliation panel */}
        <div className="mt-4 rounded-[3px] border border-v2-border bg-v2-card">
          <div className="flex items-baseline gap-3 border-b border-v2-border px-5 py-3">
            <h2 className="text-[14px] font-semibold">Count reconciliation</h2>
            <span className="text-[11.5px] text-v2-muted">
              ingestion loaded vs graph counts vs manifest expected — mismatches highlighted
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11.5px]">
              <thead>
                <tr className="bg-v2-header-bg text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                  <th className="px-4 py-1.5">Vertex type</th>
                  <th className="px-4 py-1.5 text-right">Ingestion loaded</th>
                  <th className="px-4 py-1.5 text-right">Graph counts</th>
                  <th className="px-4 py-1.5 text-right">Manifest expected</th>
                  <th className="px-4 py-1.5">Match</th>
                </tr>
              </thead>
              <tbody>
                {vertexEntities.map((e) => {
                  const loaded = counts?.counts[e.tigergraph_vertex] ?? 0;
                  const graphCount = tg?.row_counts?.[e.tigergraph_vertex];
                  const expected = e.expected_rows;
                  const workflowGenerated = expected == null;
                  const mismatch =
                    (!workflowGenerated && loaded !== expected) ||
                    (graphCount != null && graphCount !== loaded);
                  return (
                    <tr
                      key={e.entity_name}
                      className={`border-b border-v2-border-subtle last:border-0 ${mismatch ? "bg-v2-negative-bg" : ""}`}
                    >
                      <td className="px-4 py-1.5 text-v2-purple">{e.tigergraph_vertex}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums">{loaded.toLocaleString()}</td>
                      <td className="px-4 py-1.5 text-right tabular-nums">
                        {graphCount != null ? Number(graphCount).toLocaleString() : <span className="text-v2-faint">—</span>}
                      </td>
                      <td className="px-4 py-1.5 text-right tabular-nums">
                        {workflowGenerated ? <span className="text-v2-faint">—</span> : expected.toLocaleString()}
                      </td>
                      <td className="px-4 py-1.5">
                        {workflowGenerated ? (
                          <span className="text-[10.5px] italic text-v2-faint">workflow-generated</span>
                        ) : mismatch ? (
                          <span className="font-semibold text-v2-negative">✗ mismatch</span>
                        ) : (
                          <span className="text-v2-positive">✓</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {vertexEntities.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-3 text-center text-v2-faint">
                      No entity manifest available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="border-t border-v2-border-subtle px-5 py-3 text-[10.5px] italic text-v2-faint">
            &ldquo;Ingestion loaded&rdquo; and &ldquo;graph counts&rdquo; come from two different probes:
            /api/v2/ops/counts (the query tier serving the app) and the /env-health TigerGraph check
            (getVertexCount / store statistics). When both tiers point at the same store they will agree;
            a divergence means the tiers are not seeing the same data. The env-health row-count table shows
            at most the top 20 types, so &ldquo;—&rdquo; in graph counts means &ldquo;not reported&rdquo;, not zero.
          </p>
        </div>
      </AsyncBoundary>
    </div>
  );
}
