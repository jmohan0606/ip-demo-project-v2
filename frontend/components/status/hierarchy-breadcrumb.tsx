"use client";

import { ChevronRight } from "lucide-react";

import { useShellContext } from "@/components/layout/shell-context";
import { childrenOf, pathTo } from "@/lib/scope-options";
import type { HierarchyNode } from "@/lib/types/shell";

/** Real hierarchy breadcrumb: Firm › Division › Region › Market › Advisor.
 * Each level is a dropdown of that level's siblings; selecting it re-scopes the
 * page data (drives the shell scope every page reads). A trailing "drill-in"
 * dropdown lets you descend one more level. */
export function HierarchyBreadcrumb() {
  const ctx = useShellContext();
  const root = ctx.hierarchy;
  if (!root) {
    return <div className="h-8 w-64 animate-pulse rounded-lg bg-muted" />;
  }

  const path = pathTo(root, ctx.scopeId);
  // The chain of nodes to render as selects; each select shows siblings under
  // the previous node's parent.
  const drillChildren = childrenOf(root, ctx.scopeId);

  const select = (node: HierarchyNode, siblings: HierarchyNode[], isLast: boolean) => (
    <div key={node.scope_id} className="flex items-center gap-1">
      {node !== path[0] ? <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" /> : null}
      <select
        value={node.scope_id}
        onChange={(e) => {
          const next = siblings.find((s) => s.scope_id === e.target.value)!;
          ctx.setScope(next.scope_type, next.scope_id, next.label);
        }}
        className={`h-8 max-w-[190px] rounded-lg border px-2 text-[12px] font-semibold ${
          isLast ? "border-primary/40 bg-primary/5 text-primary" : "border-border bg-background"
        }`}
        title={`${node.scope_type}: ${node.label}`}
      >
        {siblings.map((s) => (
          <option key={s.scope_id} value={s.scope_id}>
            {s.scope_type === "Firm" ? s.label : `${s.scope_type}: ${s.label}`}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className="flex flex-wrap items-center gap-1">
      {path.map((node, i) => {
        const parent = i === 0 ? null : path[i - 1];
        const siblings = parent ? parent.children ?? [node] : [node];
        return select(node, siblings, i === path.length - 1);
      })}
      {drillChildren.length > 0 ? (
        <div className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          <select
            value=""
            onChange={(e) => {
              const next = drillChildren.find((s) => s.scope_id === e.target.value);
              if (next) ctx.setScope(next.scope_type, next.scope_id, next.label);
            }}
            className="h-8 rounded-lg border border-dashed border-border bg-background px-2 text-[12px] text-muted-foreground"
          >
            <option value="">Drill into {drillChildren[0].scope_type}…</option>
            {drillChildren.map((s) => (
              <option key={s.scope_id} value={s.scope_id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
    </div>
  );
}
