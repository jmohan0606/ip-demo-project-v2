"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, XCircle, RefreshCw, Database, Brain, Sparkles, Boxes } from "lucide-react";
import { fetchEnvHealth, type EnvHealthReport, type EnvHealthCheck } from "@/lib/api/env-health";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { colors } from "@/styles/tokens";

const ICONS: Record<string, typeof Database> = {
  TigerGraph: Database,
  LLM: Brain,
  Embedding: Sparkles,
  Chroma: Boxes,
};

// Fields shown as the primary "headline" line per component (when green).
const HEADLINE: Record<string, (c: EnvHealthCheck) => string> = {
  TigerGraph: (c) => `${c.mode} · ${c.graph} · ${c.vertex_type_count} vertex types · ${Number(c.total_vertices ?? 0).toLocaleString()} rows`,
  LLM: (c) => `${c.mode} · ${c.model} · ${c.generation_ms}ms · "${c.response_preview}"`,
  Embedding: (c) => `${c.mode} · ${c.model} · dim ${c.returned_dim}${c.dim_matches ? " ✓" : " ✗"}`,
  Chroma: (c) => `${c.collection_count} collection(s) · ${c.total_vectors} vectors`,
};

function StatusPill({ status }: { status: "green" | "red" }) {
  const ok = status === "green";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide"
      style={{
        color: ok ? "#0F766E" : colors.negative,
        background: ok ? "#ECFDF5" : "#FEF2F2",
        border: `1px solid ${ok ? "#99F6E4" : "#FECACA"}`,
      }}
    >
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {ok ? "Connected" : "Failed"}
    </span>
  );
}

function DetailRows({ check }: { check: EnvHealthCheck }) {
  const skip = new Set(["component", "status", "latency_ms", "error", "response_preview"]);
  const entries = Object.entries(check).filter(([k, v]) => !skip.has(k) && v !== null && v !== undefined && typeof v !== "object");
  const objects = Object.entries(check).filter(([k, v]) => !skip.has(k) && v && typeof v === "object");
  return (
    <div className="mt-2 space-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4 text-[12px]">
          <span className="text-muted-foreground">{k}</span>
          <span className="font-medium" style={{ color: colors.text.primary }}>{String(v)}</span>
        </div>
      ))}
      {objects.map(([k, v]) => (
        <div key={k} className="text-[12px]">
          <div className="text-muted-foreground">{k}</div>
          <pre className="mt-0.5 overflow-x-auto rounded bg-slate-50 p-2 text-[11px]" style={{ color: colors.text.primary }}>
            {JSON.stringify(v, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

export function EnvHealthWorkspace() {
  const [report, setReport] = useState<EnvHealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchEnvHealth()
      .then((r) => setReport(r))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-bold" style={{ color: colors.text.primary }}>
            Connection &amp; Environment Health
          </h1>
          <p className="text-[12px] text-muted-foreground">
            Actively verifies every external dependency before you use the app — open this first on the client machine.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-[12px] font-semibold shadow-sm disabled:opacity-50"
          style={{ borderColor: colors.surface.border, color: colors.primary }}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Re-check
        </button>
      </div>

      {report && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4 p-3">
            <StatusPill status={report.overall} />
            <span className="text-[12px] text-muted-foreground">
              Overall: {report.overall === "green" ? "all systems connected" : "one or more checks failed"}
            </span>
            <div className="ml-auto flex flex-wrap gap-1.5">
              {Object.entries(report.modes).map(([k, v]) => (
                <Badge key={k} variant="outline" className="text-[10px]">
                  {k.replace(/_client_mode$/, "")}: {v}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card>
          <CardContent className="p-3 text-[12px]" style={{ color: colors.negative }}>
            Failed to load health report: {error}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {report?.checks.map((check) => {
          const Icon = ICONS[check.component] ?? Database;
          const headline = HEADLINE[check.component]?.(check);
          return (
            <Card key={check.component}>
              <CardHeader className="flex flex-row items-center justify-between p-3">
                <CardTitle className="flex items-center gap-2 text-[13px]">
                  <Icon className="h-4 w-4" style={{ color: colors.primary }} /> {check.component}
                </CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground">{check.latency_ms} ms</span>
                  <StatusPill status={check.status} />
                </div>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                {check.status === "green" ? (
                  <p className="text-[12px] font-medium" style={{ color: colors.text.primary }}>{headline}</p>
                ) : (
                  <p className="rounded bg-red-50 p-2 text-[12px]" style={{ color: colors.negative }}>
                    {check.error}
                  </p>
                )}
                <DetailRows check={check} />
              </CardContent>
            </Card>
          );
        })}
      </div>

      {loading && !report && <p className="text-[12px] text-muted-foreground">Running checks…</p>}
    </div>
  );
}
