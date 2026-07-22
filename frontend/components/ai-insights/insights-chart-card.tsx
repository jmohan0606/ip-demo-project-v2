"use client";
/**
 * Card 1 — "Credited Revenue — Month over Month" (UI_SPEC §5a, reference
 * 03_ai_insights_walk.png). Stacked bars per month (recurring bottom /
 * non-recurring top), total labelled above each bar, and a connector arrow
 * between consecutive bar tops with a change pill: "▲ $43,430  9.3%".
 *
 * Hand-rolled SVG (spec explicitly allows it) because the arrows + pills need
 * exact bar-top coordinates, which Recharts does not expose cleanly. Axis,
 * gridline and legend conventions follow the design tokens.
 */
import { useEffect, useRef, useState } from "react";
import { v2 } from "@/components/design-system/design-tokens";
import type { MonthlyTotals, RevenueChangeRow } from "@/lib/api/v2";
import { fmtChange, fmtMoney, monthShort } from "@/lib/v2/format";

const MARGIN = { top: 64, right: 24, bottom: 30, left: 60 };
const CHART_HEIGHT = 360;
const MAX_BAR_WIDTH = 250;
const MIN_GAP_FOR_PILL = 90;

/** Nice axis ceiling: step is a "nice" multiple so ticks read $0/$140k/$280k…. */
function niceStep(rawStep: number): number {
  if (rawStep <= 0) return 1;
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const nice = [1, 1.2, 1.4, 1.5, 1.6, 1.8, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 10];
  for (const n of nice) if (n * mag >= rawStep) return n * mag;
  return 10 * mag;
}

function fmtAxis(v: number): string {
  if (v === 0) return "$0";
  return `$${(v / 1000).toLocaleString("en-US", { maximumFractionDigits: 0 })}k`;
}

function useMeasuredWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

export function InsightsChartCard({
  totals,
  changes,
  selectedTo = "",
  onSelectTransition,
}: {
  totals: MonthlyTotals;
  changes: RevenueChangeRow[];
  /** to-month of the transition currently in focus — its arrow highlights (T5-3). */
  selectedTo?: string;
  onSelectTransition?: (toMonthId: string) => void;
}) {
  const [ref, width] = useMeasuredWidth();
  const monthIds = Object.keys(totals.revenue_by_month).sort();
  const totalChanges = changes.filter((c) => c.group_id === "__TOTAL__");
  const changeByTo = new Map(totalChanges.map((c) => [c.to_month_id, c]));

  return (
    <div className="rounded-[3px] border border-v2-border bg-v2-card p-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[14px] font-semibold text-v2-text">Credited Revenue — Month over Month</h2>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">
            Arrows show the change between consecutive months — click an arrow to focus that
            transition&apos;s revenue drivers below. Negative values are shown in parentheses.
          </p>
        </div>
        {/* T5-1 — legend only; the dead range dropdown is gone. */}
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-[11px] text-v2-muted">
            <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: v2.color.chartRecurring }} />
            Recurring
          </span>
          <span className="flex items-center gap-1.5 text-[11px] text-v2-muted">
            <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: v2.color.chartNonrecurring }} />
            Non-recurring
          </span>
        </div>
      </div>

      <div ref={ref} className="relative mt-3 w-full">
        {monthIds.length === 0 ? (
          <p className="py-10 text-center text-[11.5px] text-v2-muted">
            No revenue data for this advisor in the selected period.
          </p>
        ) : width > 0 ? (
          <ChartSvg
            width={width}
            monthIds={monthIds}
            totals={totals}
            changeByTo={changeByTo}
            selectedTo={selectedTo}
            onSelectTransition={onSelectTransition}
          />
        ) : (
          <div style={{ height: CHART_HEIGHT }} />
        )}
      </div>
    </div>
  );
}

function ChartSvg({
  width,
  monthIds,
  totals,
  changeByTo,
  selectedTo = "",
  onSelectTransition,
}: {
  width: number;
  monthIds: string[];
  totals: MonthlyTotals;
  changeByTo: Map<string, RevenueChangeRow>;
  selectedTo?: string;
  onSelectTransition?: (toMonthId: string) => void;
}) {
  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
  const n = monthIds.length;
  const slot = n > 0 ? innerW / n : innerW;
  const barW = Math.min(MAX_BAR_WIDTH, slot * 0.55);

  const monthTotal = (m: string) => totals.revenue_by_month[m] ?? 0;
  const maxTotal = Math.max(0, ...monthIds.map(monthTotal));
  const step = niceStep(maxTotal / 4 || 1);
  const yMax = step * 4;
  const y = (v: number) => MARGIN.top + innerH * (1 - Math.min(v, yMax) / yMax);
  const cx = (i: number) => MARGIN.left + slot * i + slot / 2;
  const ticks = [0, 1, 2, 3, 4].map((i) => i * step);

  interface Pill {
    left: number;
    text: string;
    up: boolean;
    toId: string;
    selected: boolean;
  }
  const pills: Pill[] = [];

  // T5-3 — each connector arrow is CLICKABLE: clicking selects its transition
  // and focuses the driver section below in Single mode. A wide invisible hit
  // line makes the target easy; the selected arrow draws heavier.
  const arrows = monthIds.slice(0, -1).map((fromId, i) => {
    const toId = monthIds[i + 1];
    const change = changeByTo.get(toId);
    if (!change) return null;
    const up = change.change_amt >= 0;
    const selected = toId === selectedTo;
    const color = up ? v2.color.positive : v2.color.negative;
    const x1 = cx(i) + barW / 2 + 8;
    const x2 = cx(i + 1) - barW / 2 - 8;
    const y1 = y(monthTotal(fromId)) - 26;
    const y2 = y(monthTotal(toId)) - 26;
    const label = fmtChange(change.change_amt, change.change_pct);
    const showPill = x2 - x1 >= MIN_GAP_FOR_PILL;
    if (showPill) pills.push({ left: (x1 + x2) / 2, text: label, up, toId, selected });
    return (
      <g
        key={toId}
        onClick={onSelectTransition ? () => onSelectTransition(toId) : undefined}
        style={onSelectTransition ? { cursor: "pointer" } : undefined}
        role={onSelectTransition ? "button" : undefined}
        aria-label={`Focus transition ending ${toId}: ${label}`}
      >
        {/* invisible wide hit area */}
        <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="transparent" strokeWidth={18} />
        <line
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={color}
          strokeWidth={selected ? 3 : 1.6}
          markerEnd={up ? "url(#v2-arrow-up)" : "url(#v2-arrow-down)"}
        />
        <title>{onSelectTransition ? `${label} — click to focus this transition` : label}</title>
      </g>
    );
  });

  return (
    <>
      <svg width={width} height={CHART_HEIGHT} role="img" aria-label="Credited revenue by month, stacked recurring and non-recurring">
        <defs>
          <marker id="v2-arrow-up" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={v2.color.positive} />
          </marker>
          <marker id="v2-arrow-down" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={v2.color.negative} />
          </marker>
        </defs>

        {/* gridlines + y labels */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={MARGIN.left} y1={y(t)} x2={width - MARGIN.right} y2={y(t)} stroke={v2.color.grid} strokeWidth={1} />
            <text x={MARGIN.left - 8} y={y(t) + 3.5} textAnchor="end" fontSize={10.5} fill={v2.color.faint}>
              {fmtAxis(t)}
            </text>
          </g>
        ))}

        {/* bars */}
        {monthIds.map((m, i) => {
          const rec = totals.recurring_by_month[m] ?? 0;
          const non = totals.non_recurring_by_month[m] ?? 0;
          const total = monthTotal(m);
          const x = cx(i) - barW / 2;
          const yRecTop = y(Math.max(0, rec));
          const yStackTop = y(Math.max(0, rec) + Math.max(0, non));
          return (
            <g key={m}>
              {rec > 0 && (
                <rect x={x} y={yRecTop} width={barW} height={y(0) - yRecTop} fill={v2.color.chartRecurring}>
                  <title>{`${monthShort(m)} recurring: ${fmtMoney(rec)}`}</title>
                </rect>
              )}
              {non > 0 && (
                <rect x={x} y={yStackTop} width={barW} height={yRecTop - yStackTop} fill={v2.color.chartNonrecurring}>
                  <title>{`${monthShort(m)} non-recurring: ${fmtMoney(non)}`}</title>
                </rect>
              )}
              <text x={cx(i)} y={y(total) - 10} textAnchor="middle" fontSize={12.5} fontWeight={600} fill={v2.color.text}>
                {fmtMoney(total)}
              </text>
              <text x={cx(i)} y={CHART_HEIGHT - 8} textAnchor="middle" fontSize={11.5} fill={v2.color.muted}>
                {monthShort(m)}
              </text>
            </g>
          );
        })}

        {/* connector arrows */}
        {arrows}
      </svg>

      {/* change pills above the arrows — clickable like the arrows (T5-3) */}
      {pills.map((p) => (
        <button
          key={`${p.left}-${p.text}`}
          type="button"
          onClick={onSelectTransition ? () => onSelectTransition(p.toId) : undefined}
          disabled={!onSelectTransition}
          title={onSelectTransition ? "Click to focus this transition below" : undefined}
          className="absolute whitespace-nowrap rounded-full border px-3 py-0.5 text-[11.5px] font-semibold disabled:cursor-default"
          style={{
            left: p.left,
            top: 14,
            transform: "translateX(-50%)",
            color: p.up ? v2.color.positive : v2.color.negative,
            borderColor: p.up ? v2.color.positive : v2.color.negative,
            backgroundColor: p.up ? v2.color.positiveBg : v2.color.negativeBg,
            boxShadow: p.selected ? `0 0 0 2px ${p.up ? v2.color.positive : v2.color.negative}` : undefined,
            cursor: onSelectTransition ? "pointer" : undefined,
          }}
        >
          {p.text}
        </button>
      ))}
    </>
  );
}
