import { useEffect, useState } from "react";
import { useShellContext } from "@/components/layout/shell-context";
import { resolveScope } from "@/lib/api/hierarchy";

/**
 * Shared scope-following hook (CLAUDE.md 9.1 root-cause fix). Any page that renders a single
 * advisor's data derives that advisor from the shell hierarchy scope instead of hardcoding
 * A001: an Advisor scope pins that advisor; a rollup scope (Firm/Division/Region/Market) falls
 * back to the first advisor beneath it. Re-resolves whenever the breadcrumb/advisor selector
 * changes, so the page re-fetches on scope change. This is the ONE place the pattern lives.
 */
export function useScopedAdvisor(): { advisorId: string | null; scopeType: string; scopeId: string; refreshNonce: number } {
  const shell = useShellContext();
  const [advisorId, setAdvisorId] = useState<string | null>(
    shell.scopeType === "Advisor" ? shell.scopeId : null,
  );

  useEffect(() => {
    let active = true;
    if (shell.scopeType === "Advisor") {
      setAdvisorId(shell.scopeId);
      return;
    }
    resolveScope(shell.scopeType, shell.scopeId)
      .then((r) => { if (active) setAdvisorId(r.advisor_ids[0] ?? null); })
      .catch(() => { if (active) setAdvisorId(null); });
    return () => { active = false; };
  }, [shell.scopeType, shell.scopeId]);

  return { advisorId, scopeType: shell.scopeType, scopeId: shell.scopeId, refreshNonce: shell.refreshNonce };
}
