import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn, deltaMeta, formatSignedPercent } from "@/lib/utils";

/**
 * Shared delta indicator (CLAUDE.md Phase 0 / 9.7): icon + up/down arrow + %/point
 * change, green(positive)/red(negative) color-coded. The ONE component every KPI card
 * and numeric delta in the app uses — never hand-rolled per page.
 *
 * Provide either `changePct` (already computed) or `current`+`prior`. For metrics where
 * lower is better (risk score, overdue counts) pass positiveIsGood={false} so a decrease
 * reads green.
 */
export function DeltaIndicator({
  changePct,
  current,
  prior,
  positiveIsGood = true,
  unit = "%",
  suffix,
  size = "sm",
  className,
}: {
  changePct?: number;
  current?: number;
  prior?: number;
  positiveIsGood?: boolean;
  /** "%" renders the change as a signed percent; "pt" renders signed points. */
  unit?: "%" | "pt";
  /** e.g. "vs prior year" */
  suffix?: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const pct = changePct ?? (current != null && prior != null && prior !== 0 ? ((current - prior) / Math.abs(prior)) * 100 : 0);
  const { direction, positive } = deltaMeta(pct, positiveIsGood);

  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  const tone =
    direction === "flat"
      ? "text-slate-500 bg-slate-100 dark:bg-slate-800/60"
      : positive
      ? "text-teal-700 bg-teal-50 dark:text-teal-300 dark:bg-teal-950/40"
      : "text-red-700 bg-red-50 dark:text-red-300 dark:bg-red-950/40";

  const label = unit === "pt" ? `${pct > 0 ? "+" : ""}${pct.toFixed(1)} pt` : formatSignedPercent(pct);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-semibold",
        size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-1 text-xs",
        tone,
        className,
      )}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {label}
      {suffix ? <span className="font-normal opacity-70">{suffix}</span> : null}
    </span>
  );
}
