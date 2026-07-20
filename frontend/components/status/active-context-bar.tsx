"use client";

import { Building2, CalendarDays, GitCompareArrows, UserRound } from "lucide-react";
import { useShellContext } from "@/components/layout/shell-context";
import { getScopeLabel } from "@/lib/scope-options";

export function ActiveContextBar() {
  const context = useShellContext();

  return (
    <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <UserRound className="h-3.5 w-3.5" />
        Persona: <strong className="text-foreground">{context.persona}</strong>
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Building2 className="h-3.5 w-3.5" />
        Scope: <strong className="text-foreground">{context.scopeType} / {getScopeLabel(context.scopeId)}</strong>
      </span>
      <span className="inline-flex items-center gap-1.5">
        <CalendarDays className="h-3.5 w-3.5" />
        Period: <strong className="text-foreground">{context.period}</strong>
      </span>
      <span className="inline-flex items-center gap-1.5">
        <GitCompareArrows className="h-3.5 w-3.5" />
        Compare: <strong className="text-foreground">{context.compareTo}</strong>
      </span>
    </div>
  );
}
