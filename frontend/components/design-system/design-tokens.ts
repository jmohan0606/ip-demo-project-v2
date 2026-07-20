/**
 * iPerform V2 design tokens — the exact values used to render the mockups in
 * docs/ui/reference/ (see docs/ui/DESIGN_TOKENS.md). Components use these token
 * names (via the tailwind `v2-*` colors or this object), never raw hex.
 */
export const v2 = {
  color: {
    // brand / chrome
    navy: "#10315B",
    navyDark: "#0B2444",
    navyInk: "#12243B",
    // surface
    page: "#F4F6F9",
    card: "#FFFFFF",
    headerBg: "#E8EDF4",
    groupBg: "#EEF2F7",
    subBg: "#F7F9FC",
    totalBg: "#E3EAF3",
    // text
    text: "#1C2530",
    muted: "#63707F",
    faint: "#8B98A8",
    link: "#1B62B5",
    // semantic
    positive: "#1E7A45",
    positiveBg: "#E8F3EC",
    negative: "#B3261E",
    negativeBg: "#FBEAE8",
    warn: "#B7791F",
    warnBg: "#FDF6E7",
    purple: "#5B3E90",
    // chart
    chartRecurring: "#C2BE9E",
    chartNonrecurring: "#6193BD",
    grid: "#EEF1F5",
    // border
    border: "#D8DEE8",
    borderStrong: "#B9C4D2",
    borderSubtle: "#EDF1F6",
  },
  font: 'Calibri, Carlito, -apple-system, "Segoe UI", sans-serif',
  type: {
    pageTitle: "text-[16px] font-semibold",
    sectionHeader: "text-[15px] font-semibold",
    cardTitle: "text-[14px] font-semibold",
    body: "text-[11.5px]",
    tableHeader: "text-[10px] font-semibold uppercase tracking-[0.5px]",
    metric: "text-[19px] font-semibold",
    delta: "text-[12.5px] font-semibold",
    badge: "text-[9.5px] font-semibold",
    footnote: "text-[10.5px] italic",
  },
} as const;

export type ProvenanceFlag = "REAL" | "DERIVED" | "ASSUMED" | "DUMMY";

/** Provenance badge palette (DESIGN_TOKENS.md). */
export const provenanceStyle: Record<ProvenanceFlag, { color: string; bg: string; tooltip?: string }> = {
  REAL: { color: v2.color.positive, bg: v2.color.positiveBg },
  DERIVED: { color: v2.color.link, bg: "#EEF2F7" },
  ASSUMED: {
    color: v2.color.warn, bg: v2.color.warnBg,
    tooltip: "Depends on a stated assumption — client confirmation would make it real.",
  },
  DUMMY: {
    color: v2.color.warn, bg: v2.color.warnBg,
    tooltip: "Placeholder — no source data exists yet. Supplying the missing feed makes it real.",
  },
};
