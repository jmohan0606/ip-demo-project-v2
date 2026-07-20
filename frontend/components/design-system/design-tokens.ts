export const designTokens = {
  productName: "iPerform Insights & Coaching",
  layout: { sidebarWidth: 304, contentMaxWidth: 1440, radius: { card: 24, panel: 32 } },
  palette: { primary: "#2563EB", aiAccent: "#4F46E5", cyan: "#06B6D4", emerald: "#10B981", amber: "#F59E0B", rose: "#F43F5E", darkPanel: "#0F172A" },
  pagePrinciples: [
    "Every page must support persona, scope and period context.",
    "Every long-running action must show a loading overlay or status state.",
    "Every AI answer must have evidence and reasoning.",
    "Every recommendation must show compliance and expected impact.",
    "Every graph write must route through MCP-first graph access."
  ]
} as const;
