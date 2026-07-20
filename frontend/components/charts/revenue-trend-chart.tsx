"use client";

import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PerformancePoint } from "@/lib/types/dashboard";
import { formatCurrency } from "@/lib/utils";

/** Revenue trend — solid current line + (mockup) dashed gray Prior Year line when a
 * real month-shifted −12 series exists. `prior` must align 1:1 with `data`'s months. */
export function RevenueTrendChart({ data, prior }: { data: PerformancePoint[]; prior?: number[] }) {
  const merged = data.map((d, i) => ({
    ...d,
    prior_revenue: prior && prior.length === data.length ? prior[i] : undefined,
  }));
  const hasPrior = prior !== undefined && prior.length === data.length && prior.some((v) => v > 0);
  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={merged} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="revenueGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor="#2563EB" stopOpacity={0.38} />
              <stop offset="95%" stopColor="#2563EB" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" opacity={0.18} />
          <XAxis dataKey="period" tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(value) => formatCurrency(Number(value))} tickLine={false} axisLine={false} width={78} />
          <Tooltip formatter={(value, name) => [formatCurrency(Number(value)), name === "prior_revenue" ? "Prior Year" : "Total Revenue"]} />
          {hasPrior && <Legend formatter={(v) => (v === "prior_revenue" ? "Prior Year" : "Total Revenue")} wrapperStyle={{ fontSize: 11 }} />}
          <Area isAnimationActive={false} type="monotone" dataKey="revenue" stroke="#2563EB" strokeWidth={3} fill="url(#revenueGradient)" />
          {hasPrior && (
            <Area
              isAnimationActive={false} type="monotone" dataKey="prior_revenue"
              stroke="#94A3B8" strokeWidth={2} strokeDasharray="6 4" fill="transparent"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
