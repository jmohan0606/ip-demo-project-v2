import { useShellContext } from "@/components/layout/shell-context";

/**
 * Shared scope-following hook. V2 is advisor-level only: an Advisor scope pins
 * that advisor; any other scope resolves to no advisor (pages show their empty
 * state until an advisor is selected in the context bar).
 */
export function useScopedAdvisor(): { advisorId: string | null; scopeType: string; scopeId: string; refreshNonce: number } {
  const shell = useShellContext();
  const advisorId = shell.scopeType === "Advisor" ? shell.scopeId : null;
  return { advisorId, scopeType: shell.scopeType, scopeId: shell.scopeId, refreshNonce: shell.refreshNonce };
}
