"use client";
import { Fragment, useEffect, useState } from "react";
import { Database, Network, Brain, Sparkles, CheckCircle2, AlertTriangle, Cpu } from "lucide-react";
import { fetchAdapterStatus, fetchIngestionEntityCount, type AdapterStatus } from "@/lib/api/admin";
import { apiClient } from "@/lib/api/client";
import { KpiStatCard } from "@/components/patterns/kpi-stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { colors, type } from "@/styles/tokens";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const compact = (v: number) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);

interface ModelEntry {
  name: string; version: string; algorithm: string; training_date: string; training_data?: string;
  primary_metric?: string; primary_metric_value?: number; quality_gate?: string; quality_floor?: number | null;
  features?: string[]; caveats?: string; label_definition?: string; split?: string; served_by?: string;
  metrics?: Record<string, unknown>;
}

interface LlmCall { seq: number; mode: string; model: string; input_tokens: number; output_tokens: number; total_tokens: number; latency_ms: number; cost_usd: number; estimated: boolean }
function ObservabilityTab() {
  const [calls, setCalls] = useState<LlmCall[]>([]);
  const [sum, setSum] = useState<Record<string, number> | null>(null);
  useEffect(() => {
    apiClient.get<{ calls: LlmCall[]; summary: Record<string, number> }>("/observability/llm-calls?limit=40")
      .then((r) => { setCalls(r.calls ?? []); setSum(r.summary); }).catch(() => setCalls([]));
  }, []);
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {([["LLM Calls", "llm_call_count", ""], ["Total Tokens", "total_tokens", ""], ["Est. Cost", "total_cost_usd", "$"], ["Avg Latency", "avg_latency_ms", "ms"]] as const).map(([label, key, unit]) => (
          <div key={key} className="rounded-xl border bg-white p-3 shadow-sm" style={{ borderColor: colors.surface.border }}>
            <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
            <div className="text-[20px] font-black" style={{ color: colors.text.primary }}>{unit === "$" ? "$" : ""}{sum?.[key] ?? "—"}{unit === "ms" ? " ms" : ""}</div>
          </div>
        ))}
      </div>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between p-3">
          <CardTitle className="flex items-center gap-2 text-[13px]"><Cpu className="h-4 w-4 text-primary" /> LLM Calls (per-call token / cost / latency)</CardTitle>
          <span className="text-[10px] text-muted-foreground">real counts from the Claude adapter · estimated for mock · resets per process</span>
        </CardHeader>
        <CardContent className="p-3">
          {calls.length === 0 ? <p className="text-[12px] text-muted-foreground">No LLM calls recorded yet this session — ask the AI Assistant or run a coaching insight.</p> : (
            <table className="w-full text-[12px]">
              <thead><tr className="border-b text-left text-[11px] uppercase text-muted-foreground">{["#", "Mode", "Model", "In", "Out", "Latency", "Cost"].map((h) => <th key={h} className="px-2 py-1">{h}</th>)}</tr></thead>
              <tbody>
                {calls.map((c) => (
                  <tr key={c.seq} className="border-b last:border-0">
                    <td className="px-2 py-1 font-mono">{c.seq}</td>
                    <td className="px-2 py-1"><Badge variant={c.estimated ? "glass" : "success"}>{c.mode}</Badge></td>
                    <td className="px-2 py-1 font-mono text-[11px]">{c.model}</td>
                    <td className="px-2 py-1 font-mono">{c.input_tokens}</td>
                    <td className="px-2 py-1 font-mono">{c.output_tokens}</td>
                    <td className="px-2 py-1 font-mono">{c.latency_ms} ms</td>
                    <td className="px-2 py-1 font-mono">${c.cost_usd}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

interface StrategyRow { function: string; system: string; served_by: string; kind: string }
interface McpTool { name: string; family: string; description: string }
function ModelStrategyTab() {
  const [rows, setRows] = useState<StrategyRow[]>([]);
  const [systems, setSystems] = useState<Record<string, { label: string; description: string }> | null>(null);
  const [mcp, setMcp] = useState<{ families: Record<string, string[]>; tools: McpTool[]; note?: string } | null>(null);
  useEffect(() => {
    apiClient.get<{ model_strategy: StrategyRow[]; systems: Record<string, { label: string; description: string }> }>("/architecture/model-strategy")
      .then((r) => { setRows(r.model_strategy ?? []); setSystems(r.systems); }).catch(() => setRows([]));
    apiClient.get<{ families: Record<string, string[]>; tools: McpTool[]; note?: string }>("/mcp/tools").then(setMcp).catch(() => setMcp(null));
  }, []);
  const sysColor = (s: string) => s.includes("Coach Q&A") ? "#0F766E" : s === "Both" ? colors.text.muted : colors.aiAccent;
  return (
    <div className="space-y-3">
      {systems ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.values(systems).map((s) => (
            <div key={s.label} className="rounded-lg border p-3" style={{ borderColor: colors.surface.border }}>
              <div className="text-[13px] font-bold" style={{ color: sysColor(s.label) }}>{s.label}</div>
              <div className="text-[11px] text-muted-foreground">{s.description}</div>
            </div>
          ))}
        </div>
      ) : null}
      <Card>
        <CardHeader className="p-3"><CardTitle className="flex items-center gap-2 text-[13px]"><Cpu className="h-4 w-4 text-primary" /> Model Strategy (Per Function) — actually serving now</CardTitle></CardHeader>
        <CardContent className="p-3">
          <table className="w-full text-[12px]">
            <thead><tr className="border-b text-left text-[11px] uppercase text-muted-foreground">{["Function", "System", "Served by", "Kind"].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.function} className="border-b last:border-0">
                  <td className="px-2 py-1.5 font-semibold">{r.function}</td>
                  <td className="px-2 py-1.5" style={{ color: sysColor(r.system) }}>{r.system}</td>
                  <td className="px-2 py-1.5 font-mono">{r.served_by}</td>
                  <td className="px-2 py-1.5"><Badge variant="glass">{r.kind}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      {mcp ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between p-3">
            <CardTitle className="flex items-center gap-2 text-[13px]"><Network className="h-4 w-4 text-primary" /> MCP Tool Registry (Section 11.8)</CardTitle>
            <span className="text-[10px] text-muted-foreground">{mcp.tools?.length ?? 0} tools · {Object.keys(mcp.families ?? {}).length} families</span>
          </CardHeader>
          <CardContent className="p-3">
            {mcp.tools.map((t) => (
              <div key={t.name} className="flex items-baseline gap-3 border-b py-1 text-[12px] last:border-0" style={{ borderColor: colors.surface.border }}>
                <span className="w-52 font-mono font-semibold" style={{ color: colors.text.primary }}>{t.name}</span>
                <Badge variant="glass">{t.family}</Badge>
                <span className="text-muted-foreground">{t.description}</span>
              </div>
            ))}
            {mcp.note ? <p className="mt-2 text-[11px] text-muted-foreground">{mcp.note}</p> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

interface Protection { protection: string; status: string; detail: string }
function AiProtectionsTab() {
  const [items, setItems] = useState<Protection[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  useEffect(() => {
    apiClient.get<{ protections: Protection[]; counts: Record<string, number> }>("/architecture/ai-protections")
      .then((r) => { setItems(r.protections ?? []); setCounts(r.counts ?? {}); }).catch(() => setItems([]));
  }, []);
  const tone = (s: string) => s === "implemented" ? { fg: "#0F766E", bg: "#F0FDFA" } : s === "partial" ? { fg: "#B45309", bg: "#FFFBEB" } : { fg: "#B91C1C", bg: "#FEF2F2" };
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between p-3">
        <CardTitle className="flex items-center gap-2 text-[13px]"><CheckCircle2 className="h-4 w-4 text-primary" /> Top-10 AI Protections</CardTitle>
        <span className="text-[10px] text-muted-foreground">{counts.implemented ?? 0} implemented · {counts.partial ?? 0} partial</span>
      </CardHeader>
      <CardContent className="space-y-1.5 p-3">
        {items.map((p) => {
          const t = tone(p.status);
          return (
            <div key={p.protection} className="rounded-lg border p-2.5" style={{ borderColor: colors.surface.border }}>
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold">{p.protection}</span>
                <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" style={{ color: t.fg, background: t.bg }}>{p.status.replace("_", " ")}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{p.detail}</p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

interface EvalQuestion { id: string; type: string; pass: boolean; found: boolean; groundedness_score: number | null; has_citation: boolean | null; cited_docs: string[]; point_results: Array<{ label: string; in_answer: boolean; in_evidence: boolean }>; answer_excerpt: string }
interface EvalRun { available: boolean; hint?: string; run_id?: string; timestamp_utc?: string; golden_version?: number; llm?: { mode?: string; model?: string }; aggregates?: Record<string, number>; questions?: EvalQuestion[] }
interface EvalHistory { history: Array<{ run_id: string; timestamp_utc: string; groundedness_pct: number; citation_coverage_pct: number; refusal_correctness_pct: number; pass_rate_pct: number }> }

function EvaluationTrustTab() {
  const [latest, setLatest] = useState<EvalRun | null>(null);
  const [history, setHistory] = useState<EvalHistory["history"]>([]);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    apiClient.get<EvalRun>("/evaluation/runs/latest").then(setLatest).catch(() => setLatest(null));
    apiClient.get<EvalHistory>("/evaluation/runs").then((r) => setHistory(r.history ?? [])).catch(() => setHistory([]));
  }, []);
  const kpiColor = (v: number) => v >= 80 ? "#0F766E" : v >= 60 ? "#B45309" : "#B91C1C";
  if (!latest?.available) {
    return <Card><CardContent className="p-4 text-[12px] text-muted-foreground">{latest?.hint ?? "Loading…"}</CardContent></Card>;
  }
  const agg = latest.aggregates ?? {};
  return (
    <div className="space-y-3">
      <div className="rounded-lg border px-3 py-2 text-[11px]" style={{ borderColor: "#C7D2FE", background: "#EEF2FF", color: "#3730A3" }}>
        <b>Hallucination guard:</b> every answer must trace to retrieved evidence — a grounded answer with zero citations is scored FAIL.
        Run {latest.run_id} · {latest.llm?.mode ?? "?"}/{latest.llm?.model ?? "?"} · golden v{latest.golden_version}.
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {([["Groundedness", "groundedness_pct"], ["Citation Coverage", "citation_coverage_pct"], ["Refusal Correctness", "refusal_correctness_pct"], ["Pass Rate", "pass_rate_pct"]] as const).map(([label, key]) => (
          <div key={key} className="rounded-xl border bg-white p-3 shadow-sm" style={{ borderColor: colors.surface.border }}>
            <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
            <div className={type.pageTitle} style={{ color: kpiColor(agg[key] ?? 0) }}>{agg[key] ?? "—"}%</div>
          </div>
        ))}
      </div>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between p-3">
          <CardTitle className="flex items-center gap-2 text-[13px]"><CheckCircle2 className="h-4 w-4 text-primary" /> Golden Q&amp;A — per-question</CardTitle>
          <span className="text-[10px] text-muted-foreground">{agg.pass_count}/{agg.total} pass</span>
        </CardHeader>
        <CardContent className="p-3">
          <table className="w-full text-[12px]">
            <thead><tr className="border-b text-left text-[11px] uppercase text-muted-foreground">{["Q", "Type", "Result", "Ground", "Cited"].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr></thead>
            <tbody>
              {(latest.questions ?? []).map((q) => (
                <Fragment key={q.id}>
                  <tr className="cursor-pointer border-b hover:bg-slate-50" onClick={() => setOpen(open === q.id ? null : q.id)}>
                    <td className="px-2 py-1.5 font-mono font-semibold">{q.id}</td>
                    <td className="px-2 py-1.5"><Badge variant="glass">{q.type}</Badge></td>
                    <td className="px-2 py-1.5"><Badge variant={q.pass ? "success" : "warning"}>{q.pass ? "pass" : "fail"}</Badge></td>
                    <td className="px-2 py-1.5 font-mono">{q.groundedness_score ?? "—"}</td>
                    <td className="px-2 py-1.5 font-mono text-[11px]">{q.cited_docs.slice(0, 2).join(", ") || "—"}</td>
                  </tr>
                  {open === q.id && (
                    <tr className="border-b bg-slate-50/60"><td colSpan={5} className="px-3 py-2">
                      <div className="text-[12px]">
                        {q.point_results.map((p) => (
                          <div key={p.label} className="flex gap-3"><span className="w-56 text-muted-foreground">{p.label}</span>
                            <span style={{ color: p.in_answer ? "#0F766E" : "#B91C1C" }}>in answer: {String(p.in_answer)}</span>
                            <span style={{ color: p.in_evidence ? "#0F766E" : "#B91C1C" }}>in evidence: {String(p.in_evidence)}</span></div>
                        ))}
                        <div className="mt-1.5 rounded border bg-white px-2 py-1 text-[11px]" style={{ borderColor: colors.surface.border }}>{q.answer_excerpt}</div>
                      </div>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      {history.length > 1 ? (
        <Card>
          <CardHeader className="p-3"><CardTitle className="text-[13px]">Trend across runs</CardTitle></CardHeader>
          <CardContent className="p-3">
            <div style={{ width: "100%", height: 200 }}>
              <ResponsiveContainer>
                <LineChart data={history.map((h) => ({ run: h.run_id.replace("run_", "").slice(0, 8), groundedness: h.groundedness_pct, citation: h.citation_coverage_pct, pass: h.pass_rate_pct }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke={colors.surface.border} />
                  <XAxis dataKey="run" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip contentStyle={{ fontSize: 11 }} /><Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line dataKey="groundedness" stroke={colors.primary} dot /><Line dataKey="citation" stroke={colors.aiAccent} dot /><Line dataKey="pass" stroke="#14B8A6" dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function ModelRegistryTab() {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<{ models: ModelEntry[] }>("/admin/models").then((r) => setModels(r.models ?? [])).catch(() => setModels([]));
  }, []);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between p-3">
        <CardTitle className="flex items-center gap-2 text-[13px]"><Cpu className="h-4 w-4 text-primary" /> Model Registry (Section 11.1)</CardTitle>
        <span className="text-[10px] text-muted-foreground">{models.length} models · {models.filter((m) => m.quality_gate === "passed").length} serving</span>
      </CardHeader>
      <CardContent className="p-3">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b text-left text-[11px] uppercase text-muted-foreground">
                {["Model", "Algorithm", "Trained", "Primary metric", "Serving"].map((h) => (
                  <th key={h} className="px-2 py-1.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.map((m) => {
                const serving = m.quality_gate === "passed";
                return (
                  <Fragment key={m.name}>
                    <tr className="cursor-pointer border-b hover:bg-slate-50" onClick={() => setOpen(open === m.name ? null : m.name)}>
                      <td className="px-2 py-1.5 font-mono font-semibold">{m.name}</td>
                      <td className="px-2 py-1.5 text-muted-foreground">{m.algorithm?.split("·")[0]}</td>
                      <td className="px-2 py-1.5 font-mono">{m.training_date}</td>
                      <td className="px-2 py-1.5 font-mono">{m.primary_metric}={m.primary_metric_value}</td>
                      <td className="px-2 py-1.5"><Badge variant={serving ? "success" : "warning"}>{serving ? "serving" : "gated (fallback)"}</Badge></td>
                    </tr>
                    {open === m.name && (
                      <tr className="border-b bg-slate-50/60">
                        <td colSpan={5} className="px-3 py-2">
                          <div className="space-y-1.5 text-[12px]">
                            <div><span className="font-semibold">Algorithm:</span> {m.algorithm}</div>
                            {m.label_definition && <div><span className="font-semibold">Label:</span> {m.label_definition}</div>}
                            <div><span className="font-semibold">Training data:</span> {m.training_data}</div>
                            {m.split && <div><span className="font-semibold">Split:</span> {m.split}</div>}
                            <div><span className="font-semibold">Metrics:</span> <span className="font-mono">{JSON.stringify(m.metrics)}</span></div>
                            <div><span className="font-semibold">Features ({m.features?.length ?? 0}):</span> <span className="font-mono text-[11px]">{(m.features ?? []).join(", ")}</span></div>
                            <div className="rounded-lg border bg-amber-50 px-2 py-1 text-[11px]" style={{ borderColor: "#FDE68A", color: "#92400E" }}>
                              <span className="font-semibold">Caveats:</span> {m.caveats}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {models.length === 0 && <tr><td colSpan={5} className="px-2 py-3 text-center text-muted-foreground">No trained models registered. Run scripts/train/run_all.py.</td></tr>}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function AdapterCard({
  icon,
  name,
  mode,
  healthy,
  rows,
}: {
  icon: React.ReactNode;
  name: string;
  mode: string;
  healthy?: boolean;
  rows: Array<[string, string]>;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between p-3">
        <CardTitle className="flex items-center gap-2 text-[13px]">{icon} {name}</CardTitle>
        <Badge variant={healthy === false ? "warning" : "success"}>{mode}</Badge>
      </CardHeader>
      <CardContent className="p-3">
        <dl className="divide-y rounded-xl border text-[12px]">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 px-3 py-1.5">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="truncate text-right font-mono">{v}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

export function AdminHealthWorkspace() {
  const [status, setStatus] = useState<AdapterStatus | null>(null);
  const [entityCount, setEntityCount] = useState<number>(0);
  const [tab, setTab] = useState<"health" | "models" | "strategy" | "protections" | "eval" | "obs">("health");

  useEffect(() => {
    fetchAdapterStatus().then(setStatus).catch(() => setStatus(null));
    fetchIngestionEntityCount().then(setEntityCount).catch(() => setEntityCount(0));
  }, []);

  const lr = status?.graph.load_report;
  const mismatches = lr?.row_count_mismatches?.length ?? 0;
  const model = (status as unknown as { model?: { mode?: string; serving?: string[]; registered?: number }; model_client_mode?: string }) ?? {};

  return (
    <div className="space-y-3">
      <div>
        <Badge variant="glass">Admin / Data Quality / Runtime Health</Badge>
        <h2 className={`mt-2 ${type.pageTitle}`}>Runtime Adapters &amp; Data Quality</h2>
        <p className="text-[12px] text-muted-foreground">
          Live adapter modes and graph load report from `/adapters/status` — the mock/local/real
          swap-in points, with real vertex/edge row counts and load-integrity checks.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b">
        {([["health", "System Health"], ["models", "Model Registry"], ["strategy", "Model Strategy"], ["protections", "AI Protections"], ["eval", "Evaluation & Trust"], ["obs", "Observability"]] as const).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-[12px] font-semibold ${tab === t ? "border-b-2 border-primary text-primary" : "text-muted-foreground"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "models" ? <ModelRegistryTab /> : tab === "strategy" ? <ModelStrategyTab /> : tab === "protections" ? <AiProtectionsTab /> : tab === "eval" ? <EvaluationTrustTab /> : tab === "obs" ? <ObservabilityTab /> : (
      <div className="space-y-3">

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiStatCard label="Vertex Rows" value={lr ? compact(lr.vertex_rows) : "—"} delta={lr ? `${lr.vertex_types} types` : undefined} deltaPositive />
        <KpiStatCard label="Edge Rows" value={lr ? compact(lr.edge_rows) : "—"} delta={lr ? `${lr.edge_types} types` : undefined} deltaPositive />
        <KpiStatCard label="Row-Count Mismatches" value={String(mismatches)} delta={mismatches === 0 ? "clean" : "check"} deltaPositive={mismatches === 0} />
        <KpiStatCard label="Ingestion Entities" value={String(entityCount)} />
      </div>

      {status && (
        <div className="grid gap-3 xl:grid-cols-3">
          <AdapterCard
            icon={<Network className="h-4 w-4 text-primary" />}
            name="Graph Client"
            mode={status.graph_client_mode}
            healthy={status.graph.healthy}
            rows={[
              ["Graph", status.graph.graph],
              ["Mode", status.graph.mode],
              ["Healthy", status.graph.healthy ? "yes" : "no"],
              ["Vertex types", String(status.graph.load_report?.vertex_types ?? "—")],
              ["Edge types", String(status.graph.load_report?.edge_types ?? "—")],
            ]}
          />
          <AdapterCard
            icon={<Brain className="h-4 w-4 text-primary" />}
            name="LLM Client"
            mode={status.llm_client_mode}
            rows={[
              ["Mode", status.llm.mode],
              ["Model", status.llm.model],
              ["Anthropic key", status.anthropic_configured ? "configured" : "—"],
              ["Azure OpenAI", status.azure_openai_configured ? "configured" : "—"],
            ]}
          />
          <AdapterCard
            icon={<Sparkles className="h-4 w-4 text-primary" />}
            name="Embedding Client"
            mode={status.embedding_client_mode}
            rows={[
              ["Mode", status.embedding.mode],
              ["Model", status.embedding.model],
              ["Dimensions", String(status.embedding.dimensions)],
            ]}
          />
          <AdapterCard
            icon={<Cpu className="h-4 w-4 text-primary" />}
            name="Model Client (11.1)"
            mode={model.model_client_mode ?? "deterministic"}
            rows={[
              ["Tier", model.model?.mode ?? "—"],
              ["Registered", String(model.model?.registered ?? 0)],
              ["Serving", (model.model?.serving ?? []).join(", ") || "none"],
            ]}
          />
        </div>
      )}

      <Card>
        <CardHeader className="p-3">
          <CardTitle className="flex items-center gap-2 text-[13px]">
            <Database className="h-4 w-4 text-primary" /> Data Load Integrity
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-3 text-[12px]">
          <div className="flex items-center gap-2 rounded-xl border p-3">
            {mismatches === 0 ? (
              <CheckCircle2 className="h-4 w-4 text-primary" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-destructive" />
            )}
            <span>
              {mismatches === 0
                ? `All ${lr?.vertex_types ?? 0} vertex types and ${lr?.edge_types ?? 0} edge types loaded with 0 row-count mismatches (${lr ? compact(lr.vertex_rows) : 0} vertices, ${lr ? compact(lr.edge_rows) : 0} edges).`
                : `${mismatches} row-count mismatch(es) detected against manifest expectations.`}
            </span>
          </div>
        </CardContent>
      </Card>
      </div>
      )}
    </div>
  );
}
