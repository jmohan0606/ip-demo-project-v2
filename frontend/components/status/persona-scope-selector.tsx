"use client";

import { useShellContext } from "@/components/layout/shell-context";
import { HierarchyBreadcrumb } from "@/components/status/hierarchy-breadcrumb";
import type { Persona, TimePeriod } from "@/lib/types/navigation";

const personas: Persona[] = ["Advisor", "AGP", "DDW", "MDW"];
const periods: TimePeriod[] = ["MTD", "QTD", "YTD", "LTM"];
const compareOptions: Array<"Prior Period" | "Prior Year" | "Peer Benchmark" | "None"> = [
  "Prior Year", "Prior Period", "Peer Benchmark", "None",
];

const personaLabel: Record<Persona, string> = {
  Advisor: "Advisor",
  AGP: "AGP Program",
  DDW: "DDW · Division Lead",
  MDW: "MDW · Enterprise Lead",
};

/** The real filter bar: Persona · Hierarchy breadcrumb · Time Period.
 * Replaces the old duplicate Advisor/Advisor dropdown pair. */
export function PersonaScopeSelector() {
  const ctx = useShellContext();
  const cls = "h-8 rounded-lg border border-border bg-background px-2 text-[12px] font-semibold";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <label className="flex items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Persona</span>
        <select
          className={cls}
          value={ctx.persona}
          onChange={(e) => ctx.setPersona(e.target.value as Persona)}
        >
          {personas.map((p) => (
            <option key={p} value={p}>{personaLabel[p]}</option>
          ))}
        </select>
      </label>

      <label className="flex min-w-0 items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Hierarchy</span>
        <HierarchyBreadcrumb />
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Period</span>
        <select
          className={cls}
          value={ctx.period}
          onChange={(e) => ctx.setPeriod(e.target.value as TimePeriod)}
        >
          {periods.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Compare To</span>
        <select
          className={cls}
          value={ctx.compareTo}
          onChange={(e) => ctx.setCompareTo(e.target.value as typeof compareOptions[number])}
        >
          {compareOptions.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>

      {/* Reset filters (12.1): back to firm-wide LTM / Prior Year in one click. */}
      <button
        type="button"
        onClick={() => ctx.resetFilters()}
        className="h-8 rounded-lg border border-border bg-background px-2.5 text-[11px] font-semibold text-muted-foreground transition hover:bg-muted"
        title="Reset scope, period and comparison to defaults"
      >
        Reset filters
      </button>
    </div>
  );
}
