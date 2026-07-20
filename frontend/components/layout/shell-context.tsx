"use client";
import { createContext, useContext } from "react";
import type { ShellContextValue } from "@/lib/types/shell";

export const ShellContext = createContext<ShellContextValue | null>(null);

export function useShellContext() {
  const value = useContext(ShellContext);
  if (!value) throw new Error("useShellContext must be used inside AppShell");
  return value;
}
export function useApiContextPayload() {
  const context = useShellContext();
  return {
    persona: context.persona,
    scope_type: context.scopeType,
    scope_id: context.scopeId,
    period: context.period,
    compare_to: context.compareTo
  };
}
