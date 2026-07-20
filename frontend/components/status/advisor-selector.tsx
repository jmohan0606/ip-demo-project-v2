"use client";

import { useEffect, useState } from "react";
import { UserRound } from "lucide-react";

import { useShellContext } from "@/components/layout/shell-context";
import { useScopedAdvisor } from "@/lib/hooks/use-scoped-advisor";
import { apiClient } from "@/lib/api/client";
import { formatEntity } from "@/lib/utils";

/**
 * Explicit, visible advisor-selector dropdown (CLAUDE.md 12.6) for the pipeline
 * pages (Predictions, Opportunities & Recommendations, Feature Lab, Explainability).
 * The hierarchy breadcrumb already scopes these pages (useScopedAdvisor), but the
 * breadcrumb doesn't read as an advisor picker to someone testing quickly — this
 * removes the ambiguity. Selecting an advisor sets the shell scope to that advisor,
 * so every scope-following page re-fetches. Shows the currently-resolved advisor
 * even when the active scope is a rollup (Firm/Division/…), so the label is never
 * out of sync with the data on screen.
 */
export function AdvisorSelector({ className = "" }: { className?: string }) {
  const shell = useShellContext();
  const { advisorId } = useScopedAdvisor();
  const [advisors, setAdvisors] = useState<Array<{ advisor_id: string; advisor_name: string | null }>>([]);

  useEffect(() => {
    apiClient
      .get<{ advisors: Array<{ advisor_id: string; advisor_name: string | null }> }>("/advisor/list")
      .then((r) => setAdvisors(r.advisors))
      .catch(() => setAdvisors([]));
  }, []);

  const options = advisors.length ? advisors : advisorId ? [{ advisor_id: advisorId, advisor_name: null }] : [];

  return (
    <label className={`inline-flex items-center gap-1.5 ${className}`}>
      <UserRound className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Advisor</span>
      <select
        value={advisorId ?? ""}
        onChange={(e) => {
          const opt = advisors.find((a) => a.advisor_id === e.target.value);
          shell.setScope("Advisor", e.target.value, opt?.advisor_name ?? e.target.value);
        }}
        className="h-8 max-w-[220px] rounded-lg border border-primary/40 bg-primary/5 px-2 text-[12px] font-semibold text-primary"
        title="Select an advisor — scopes this page to their data"
      >
        {options.map((o) => (
          <option key={o.advisor_id} value={o.advisor_id}>
            {formatEntity(o.advisor_id, o.advisor_name)}
          </option>
        ))}
      </select>
    </label>
  );
}
