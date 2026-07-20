// The four personas from the architecture's User Experience layer.
export type Persona = "Advisor" | "AGP" | "DDW" | "MDW";
export type ScopeType = "Firm" | "Division" | "Region" | "Market" | "Advisor";
export type TimePeriod = "MTD" | "QTD" | "YTD" | "LTM";
export type NavigationItem = {
  id: string;
  label: string;
  description: string;
  href: string;
  iconName: string;
  group: "Executive" | "Advisor" | "AI" | "Graph" | "Operations" | "Admin";
  status?: "ready" | "new" | "audit";
};
