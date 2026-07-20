"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProductMixPoint } from "@/lib/types/dashboard";
import { formatCurrency } from "@/lib/utils";

export function ProductMixChart({ data }: { data: ProductMixPoint[] }) {
  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.18} />
          <XAxis dataKey="category" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(value) => formatCurrency(Number(value))} tickLine={false} axisLine={false} width={78} />
          <Tooltip formatter={(value) => formatCurrency(Number(value))} />
          <Bar isAnimationActive={false} dataKey="revenue" fill="#4F46E5" radius={[10, 10, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
