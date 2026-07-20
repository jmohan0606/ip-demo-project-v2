import type { Persona, ScopeType } from "@/lib/types/navigation";
import type { HierarchyNode } from "@/lib/types/shell";

// Default scope entry point per persona (real graph ids). Advisors land on one
// advisor; leadership personas land at their rollup level. Labels are filled in
// once the real hierarchy tree loads.
export const defaultScopeByPersona: Record<Persona, { scopeType: ScopeType; scopeId: string }> = {
  Advisor: { scopeType: "Advisor", scopeId: "A001" },
  AGP: { scopeType: "Firm", scopeId: "F001" },
  DDW: { scopeType: "Division", scopeId: "D01" },
  MDW: { scopeType: "Firm", scopeId: "F001" },
};

export const SCOPE_LEVELS: ScopeType[] = ["Firm", "Division", "Region", "Market", "Advisor"];

/** Depth-first search for a node in the hierarchy tree. */
export function findNode(root: HierarchyNode | null, scopeId: string): HierarchyNode | null {
  if (!root) return null;
  if (root.scope_id === scopeId) return root;
  for (const child of root.children ?? []) {
    const found = findNode(child, scopeId);
    if (found) return found;
  }
  return null;
}

/** Ancestor path from the firm down to (and including) the target node. */
export function pathTo(root: HierarchyNode | null, scopeId: string): HierarchyNode[] {
  if (!root) return [];
  if (root.scope_id === scopeId) return [root];
  for (const child of root.children ?? []) {
    const sub = pathTo(child, scopeId);
    if (sub.length) return [root, ...sub];
  }
  return [];
}

/** Immediate children of the node at the given scopeId (its selectable descendants). */
export function childrenOf(root: HierarchyNode | null, scopeId: string): HierarchyNode[] {
  return findNode(root, scopeId)?.children ?? [];
}

export function getScopeLabel(scopeId: string): string {
  return scopeId;
}
