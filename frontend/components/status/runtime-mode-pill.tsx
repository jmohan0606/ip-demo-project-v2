"use client";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { GraphHealth } from "@/lib/types/api";
export function RuntimeModePill() {
  const [mode, setMode] = useState<string>("MOCK");
  useEffect(() => { apiClient.get<GraphHealth>(endpoints.graphHealth).then((health) => setMode(health.active_mode.toUpperCase())).catch(() => setMode("MOCK")); }, []);
  const variant = mode === "MCP" ? "success" : mode === "REST" ? "warning" : "glass";
  return <Badge variant={variant}>Graph: {mode}</Badge>;
}
