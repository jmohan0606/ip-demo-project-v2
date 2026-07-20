"use client";
/**
 * Card 1 — "Credited Revenue — Months" (UI_SPEC §4a, reference 01).
 * Hierarchical pivot: rows = product hierarchy, columns = months. Leaf (group)
 * figures are link-coloured and open Transactions filtered to that month +
 * product group; class/line/total figures are not clickable.
 */
import { useMemo } from "react";
import { useRouter } from "next/navigation";
import type { MonthlyRevenueRow, ProductHierarchy } from "@/lib/api/v2";
import { fmtMoney, isZeroish, monthHeader } from "@/lib/v2/format";
import { PivotCard, type PivotColumn } from "./pivot-card";
import { type PivotRow, buildRowTree } from "./pivot-model";

export function RevenuePivot({
  hierarchy,
  revenue,
  monthIds,
  advisorId,
}: {
  hierarchy: ProductHierarchy;
  revenue: MonthlyRevenueRow[];
  monthIds: string[];
  advisorId: string;
}) {
  const router = useRouter();
  const monthSet = useMemo(() => new Set(monthIds), [monthIds]);

  // revenue by "group|month" — real leaf groups only (aggregate rows such as
  // "__TOTAL__", if present, are excluded so sums never double-count).
  const revByCell = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of revenue) {
      if (row.group_id.startsWith("__") || !monthSet.has(row.month_id)) continue;
      const key = `${row.group_id}|${row.month_id}`;
      map.set(key, (map.get(key) ?? 0) + row.revenue);
    }
    return map;
  }, [revenue, monthSet]);

  const rows = useMemo(() => {
    const dataGroupIds = new Set<string>();
    for (const key of revByCell.keys()) dataGroupIds.add(key.split("|")[0]);
    return buildRowTree(hierarchy, dataGroupIds);
  }, [hierarchy, revByCell]);

  const valueFor = (row: PivotRow, monthId: string): number =>
    row.groupIds.reduce((sum, g) => sum + (revByCell.get(`${g}|${monthId}`) ?? 0), 0);

  const columns: PivotColumn[] = monthIds.map((id) => ({ key: id, header: monthHeader(id) }));

  const renderCell = (row: PivotRow, col: PivotColumn) => {
    const value = valueFor(row, col.key);
    if (isZeroish(value)) return <span className="text-v2-faint">—</span>;
    if (row.kind === "group" && row.groupId) {
      const groupId = row.groupId;
      return (
        <button
          type="button"
          onClick={() =>
            router.push(
              `/transactions?advisor=${encodeURIComponent(advisorId)}&month=${col.key}&group=${encodeURIComponent(groupId)}`,
            )
          }
          className="text-v2-link hover:underline"
          title={`Open transactions — ${row.label}, ${monthHeader(col.key)}`}
        >
          {fmtMoney(value)}
        </button>
      );
    }
    return <span>{fmtMoney(value)}</span>;
  };

  return (
    <PivotCard
      title="Credited Revenue — Months"
      subtitle="Revenue by product hierarchy. Click any figure to open transactions."
      columns={columns}
      rows={rows}
      renderCell={renderCell}
      cellText={(row, col) => {
        const value = valueFor(row, col.key);
        return isZeroish(value) ? "" : String(Math.round(value * 100) / 100);
      }}
      footnote="Figures are credited (post-split) revenue. Blue values open the Transactions view filtered to that month and product."
      exportFileName={`credited-revenue-months-${advisorId}.csv`}
    />
  );
}
