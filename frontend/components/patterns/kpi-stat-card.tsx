import type { LucideIcon } from "lucide-react";
import { DeltaIndicator } from "@/components/patterns/delta-indicator";
import { WhyTrace, type TraceInfo } from "@/components/patterns/why-trace";
import { colors, type } from "@/styles/tokens";

/**
 * Shared KPI stat card (CLAUDE.md 9.5/9.12): optional colored icon in a soft-colored circle on
 * the left, a bold value, and a prior-period delta badge. Prefer `changePct` (renders the shared
 * DeltaIndicator: arrow + signed %, green/red, positiveIsGood for lower-is-better metrics). The
 * legacy `delta`/`deltaPositive` string props are kept for callers not yet migrated.
 */
export function KpiStatCard({
  label,
  value,
  delta,
  deltaPositive,
  changePct,
  positiveIsGood = true,
  deltaSuffix,
  icon: Icon,
  iconColor = colors.primary,
  priorLine,
  trace,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaPositive?: boolean;
  changePct?: number;
  positiveIsGood?: boolean;
  deltaSuffix?: string;
  icon?: LucideIcon;
  iconColor?: string;
  /** mockup's "vs PY: $4.28M" absolute prior line — only pass when a REAL prior exists */
  priorLine?: string;
  /** REQ-2: the real computation/model that produced this figure */
  trace?: TraceInfo;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border bg-white px-4 py-3 shadow-sm" style={{ borderColor: colors.surface.border }}>
      {Icon ? (
        <span
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: `${iconColor}14`, color: iconColor }}
        >
          <Icon className="h-4.5 w-4.5" style={{ width: 18, height: 18 }} />
        </span>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-1">
          <div className={type.label} style={{ color: colors.text.muted }}>{label}</div>
          {trace && <WhyTrace trace={trace} />}
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className={type.kpiValue} style={{ color: colors.text.primary }}>{value}</span>
          {changePct !== undefined ? (
            <DeltaIndicator changePct={changePct} positiveIsGood={positiveIsGood} suffix={deltaSuffix} />
          ) : delta ? (
            <span
              className="rounded-full px-1.5 py-0.5 text-[11px] font-semibold"
              style={{
                color: deltaPositive ? colors.positive : colors.negative,
                backgroundColor: deltaPositive ? "#F0FDFA" : "#FEF2F2",
              }}
            >
              {delta}
            </span>
          ) : null}
        </div>
        {priorLine && (
          <div className="mt-0.5 text-[11px]" style={{ color: colors.text.muted }}>{priorLine}</div>
        )}
      </div>
    </div>
  );
}
