"use client";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { SidebarNavigation } from "@/components/navigation/sidebar-navigation";
import { TopHeader } from "@/components/layout/top-header";
import { StoryModeProvider } from "@/components/story/story-mode-provider";
import { ShellContext } from "@/components/layout/shell-context";
import { GlobalLoadingOverlay } from "@/components/loading/global-loading-overlay";
import { fetchHierarchyTree } from "@/lib/api/hierarchy";
import { defaultScopeByPersona, findNode } from "@/lib/scope-options";
import type { Persona, ScopeType, TimePeriod } from "@/lib/types/navigation";
import type { HierarchyNode, ShellContextState } from "@/lib/types/shell";

export function AppShell({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState<Persona>("Advisor");
  // Land on Firm scope so the flagship Executive Dashboard (the default route)
  // shows firm-wide rollups immediately; the useEffect below corrects the label
  // once the real hierarchy tree loads. Persona stays Advisor (scope is a
  // separate data-control lens per the hierarchy breadcrumb).
  const [scopeType, setScopeType] = useState<ScopeType>("Firm");
  const [scopeId, setScopeId] = useState("F001");
  const [scopeLabel, setScopeLabel] = useState("Chase Wealth Management");
  const [period, setPeriod] = useState<TimePeriod>("YTD");
  const [compareTo, setCompareTo] = useState<ShellContextState["compareTo"]>("Prior Year");
  const [hierarchy, setHierarchy] = useState<HierarchyNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const refresh = () => setRefreshNonce((n) => n + 1);

  // Reset filters (12.1): return scope + period + compare-to to firm-wide defaults.
  function resetFilters() {
    const root = hierarchy;
    const node = findNode(root, "F001");
    setScope("Firm", "F001", node?.label ?? "Chase Wealth Management");
    setPeriod("LTM");
    setCompareTo("Prior Year");
    setRefreshNonce((n) => n + 1);
  }

  useEffect(() => {
    fetchHierarchyTree()
      .then((tree) => {
        const root = tree.firms[0] ?? null;
        setHierarchy(root);
        const node = findNode(root, scopeId);
        if (node) setScopeLabel(node.label);
      })
      .catch(() => setHierarchy(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setScope(nextType: ScopeType, nextId: string, label: string) {
    setScopeType(nextType);
    setScopeId(nextId);
    setScopeLabel(label);
  }

  function setPersona(value: Persona) {
    setPersonaState(value);
    const nextScope = defaultScopeByPersona[value];
    const node = findNode(hierarchy, nextScope.scopeId);
    setScope(nextScope.scopeType, nextScope.scopeId, node?.label ?? nextScope.scopeId);
  }

  const context = useMemo(
    () => ({
      persona, scopeType, scopeId, scopeLabel, period, compareTo, hierarchy, refreshNonce,
      setPersona, setScope, setScopeType, setScopeId, setPeriod, setCompareTo, setLoading, refresh, resetFilters,
    }),
    [persona, scopeType, scopeId, scopeLabel, period, compareTo, hierarchy, refreshNonce],
  );

  return (
    <ShellContext.Provider value={context}>
      <div className="compact-shell enterprise-shell-bg min-h-screen">
        <GlobalLoadingOverlay active={loading} message="Loading iPerform intelligence..." />
        <div className="flex min-h-screen">
          <SidebarNavigation collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((v) => !v)} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopHeader />
            <StoryModeProvider>
              <main className="flex-1 px-3 py-3 xl:px-4">{children}</main>
            </StoryModeProvider>
          </div>
        </div>
      </div>
    </ShellContext.Provider>
  );
}
