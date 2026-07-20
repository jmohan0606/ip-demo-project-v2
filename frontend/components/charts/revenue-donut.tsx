"use client";

import { Cell, Pie, PieChart, Tooltip } from "recharts";

import { colors, chartSeries, type } from "@/styles/tokens";
import { formatCurrency } from "@/lib/utils";

export interface DonutSlice {
  label: string;
  value: number;
}

/**
 * Categorical revenue donut with the total centered inside the ring (CLAUDE.md
 * 9.5: "donut charts show the total value centered inside the donut"). Rendered
 * at a fixed pixel size — no ResponsiveContainer — so the ring never collapses to
 * a blank measure race (the defect the old Revenue-by-Channel donut hit). Legend
 * carries identity beyond color; fixed categorical hue order per the dataviz rule.
 */
export function RevenueDonut({
  data,
  size = 190,
  centerLabel = "Total",
}: {
  data: DonutSlice[];
  size?: number;
  centerLabel?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const inner = size * 0.3;
  const outer = size * 0.46;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <PieChart width={size} height={size}>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="50%"
            innerRadius={inner}
            outerRadius={outer}
            paddingAngle={2}
            stroke={colors.surface.card}
            strokeWidth={2}
            isAnimationActive={false}
          >
            {data.map((slice, i) => (
              <Cell key={slice.label} fill={chartSeries[i % chartSeries.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ borderRadius: 8, border: `1px solid ${colors.surface.border}`, fontSize: 12 }}
            formatter={(value: number, name: string) => [
              `${formatCurrency(value, { compact: true })} · ${((value / total) * 100).toFixed(0)}%`,
              name,
            ]}
          />
        </PieChart>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className={type.label} style={{ color: colors.text.muted }}>{centerLabel}</span>
          <span className="text-[15px] font-black" style={{ color: colors.text.primary }}>
            {formatCurrency(total, { compact: true })}
          </span>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-1.5 self-stretch">
        {data.map((slice, i) => (
          <li key={slice.label} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: chartSeries[i % chartSeries.length] }}
            />
            <span className={`flex-1 truncate ${type.data}`} style={{ color: colors.text.secondary }}>
              {slice.label}
            </span>
            <span className={`font-mono ${type.data}`} style={{ color: colors.text.primary }}>
              {formatCurrency(slice.value, { compact: true })}
            </span>
            <span className={`w-9 text-right font-mono ${type.data}`} style={{ color: colors.text.muted }}>
              {((slice.value / total) * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
