import type { Persona, ScopeType, TimePeriod } from "@/lib/types/navigation";

export type ScopeOption = {
  scopeType: ScopeType;
  scopeId: string;
  label: string;
  parentLabel?: string;
};

export type HierarchyNode = {
  scope_type: ScopeType;
  scope_id: string;
  label: string;
  children?: HierarchyNode[];
};

export type ShellContextState = {
  persona: Persona;
  scopeType: ScopeType;
  scopeId: string;
  scopeLabel: string;
  period: TimePeriod;
  compareTo: "Prior Period" | "Prior Year" | "Peer Benchmark" | "None";
  hierarchy: HierarchyNode | null;
  /** Bumped by the Refresh button; scope-following hooks include it in their fetch deps. */
  refreshNonce: number;
};

export type ShellContextActions = {
  setPersona: (value: Persona) => void;
  setScope: (scopeType: ScopeType, scopeId: string, label: string) => void;
  setScopeType: (value: ScopeType) => void;
  setScopeId: (value: string) => void;
  setPeriod: (value: TimePeriod) => void;
  setCompareTo: (value: ShellContextState["compareTo"]) => void;
  setLoading: (value: boolean) => void;
  /** Re-fetch the current page's data without losing scope (Refresh button). */
  refresh: () => void;
  /** Reset scope + period + compare-to to the firm-wide defaults (Reset filters, 12.1). */
  resetFilters: () => void;
};

export type ShellContextValue = ShellContextState & ShellContextActions;
