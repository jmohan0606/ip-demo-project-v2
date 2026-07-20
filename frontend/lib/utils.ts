import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

/**
 * Canonical currency formatter (CLAUDE.md Section 9.7: every dollar figure shows a $).
 * Compact ($1.2M) at/above 1M by default; pass compact:false to force standard grouping.
 */
export function formatCurrency(value: number, opts: { compact?: boolean; decimals?: number } = {}): string {
  const compact = opts.compact ?? value >= 1_000_000;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: opts.decimals ?? (compact ? 1 : 0),
  }).format(value);
}

/** Percent with a fixed number of decimals (no sign). e.g. formatPercent(14.37) -> "14.4%" */
export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

/** Signed percent for deltas. e.g. formatSignedPercent(-4.2) -> "-4.2%", (3) -> "+3.0%" */
export function formatSignedPercent(value: number, decimals = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Canonical "ID · Name" entity label (item 3: never show a bare ID like D01/A001).
 * Returns "D01 · Eastern Division" when a name is known, else the id alone. Pass the
 * name directly when you already have it, or use the useEntityLabel() hook to resolve.
 */
export function formatEntity(id: string | null | undefined, name?: string | null): string {
  if (!id) return name || "—";
  if (!name || name === id) return id;
  return `${id} · ${name}`;
}

export type DeltaDirection = "up" | "down" | "flat";

export interface DeltaMeta {
  direction: DeltaDirection;
  /** true when this movement should read as good (green), applying positiveIsGood/invert. */
  positive: boolean;
  changePct: number;
}

/**
 * Shared delta semantics used by the DeltaIndicator component and any KPI card.
 * positiveIsGood=false for metrics where lower is better (risk, overdue counts).
 */
export function deltaMeta(changePct: number, positiveIsGood = true): DeltaMeta {
  const direction: DeltaDirection = changePct > 0.05 ? "up" : changePct < -0.05 ? "down" : "flat";
  const isRise = direction === "up";
  const positive = direction === "flat" ? true : positiveIsGood ? isRise : !isRise;
  return { direction, positive, changePct };
}

/** % change from a prior value, guarding divide-by-zero. */
export function pctChange(current: number, prior: number): number {
  if (!prior) return 0;
  return ((current - prior) / Math.abs(prior)) * 100;
}
