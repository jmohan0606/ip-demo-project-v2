"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";

interface AdapterStatus {
  graph?: { healthy?: boolean };
  graph_client_mode?: string;
  llm_client_mode?: string;
  embedding_client_mode?: string;
}

/** Real system-status indicator (replaces the ambiguous "Ready" pill). Reads
 * /adapters/status: green "All Systems Operational" when the graph adapter is
 * healthy, amber/degraded otherwise. */
export function SystemStatusPill() {
  const [status, setStatus] = useState<"ok" | "degraded" | "loading">("loading");
  const [detail, setDetail] = useState("");

  useEffect(() => {
    apiClient
      .get<AdapterStatus>("/adapters/status")
      .then((s) => {
        const healthy = s.graph?.healthy !== false;
        setStatus(healthy ? "ok" : "degraded");
        setDetail(
          `graph:${s.graph_client_mode ?? "?"} · llm:${s.llm_client_mode ?? "?"} · embed:${s.embedding_client_mode ?? "?"}`,
        );
      })
      .catch(() => {
        setStatus("degraded");
        setDetail("adapter status unreachable");
      });
  }, []);

  const color = status === "ok" ? "#14B8A6" : status === "loading" ? "#94A3B8" : "#F59E0B";
  const label =
    status === "ok" ? "All Systems Operational" : status === "loading" ? "Checking…" : "Degraded";

  return (
    <div
      className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5"
      style={{ borderColor: "var(--border, #E2E8F0)" }}
      title={detail}
    >
      <span
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: color, boxShadow: `0 0 0 3px ${color}22` }}
      />
      <span className="text-[12px] font-semibold" style={{ color }}>{label}</span>
    </div>
  );
}
