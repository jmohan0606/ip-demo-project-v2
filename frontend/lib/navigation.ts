import type { NavigationItem } from "@/lib/types/navigation";

// V2 navigation (UI_SPEC §2): one Results section + Operations entries.
export const navigationItems: NavigationItem[] = [
  {
    id: "revenue",
    label: "Revenue",
    description: "Revenue overview (not in this build — Phase 2).",
    href: "/revenue",
    iconName: "BadgeDollarSign",
    group: "Results"
  },
  {
    id: "transactions",
    label: "Transactions",
    description: "Source transactions — the drill-down target for every pivot cell.",
    href: "/transactions",
    iconName: "Receipt",
    group: "Results"
  },
  {
    id: "trends",
    label: "Trends",
    description: "Credited revenue by product hierarchy per month, and month-over-month change.",
    href: "/trends",
    iconName: "LineChart",
    group: "Results",
    status: "ready"
  },
  {
    id: "ai-insights",
    label: "AI Insights",
    description: "Month-over-month walk with AI commentary — every figure computed from graph data.",
    href: "/ai-insights",
    iconName: "Sparkles",
    group: "Results",
    status: "ready"
  },
  {
    id: "data-ingestion",
    label: "Data Ingestion",
    description: "Load V2 vertices and edges into TigerGraph. Dependency order enforced on load and delete.",
    href: "/data-ingestion",
    iconName: "UploadCloud",
    group: "Operations"
  },
  {
    id: "env-health",
    label: "Connectivity & Environment Health",
    description: "Active setup verification: TigerGraph, LLM, local store and ingestion state.",
    href: "/env-health",
    iconName: "PlugZap",
    group: "Operations"
  }
];

export const navigationGroups = ["Results", "Operations"] as const;
