"use client";
/**
 * Card 2 — "Credited Revenue — MoM Change" (UI_SPEC §4b, reference 02).
 * Same row structure as the months pivot; columns are transitions
 * ("Apr → May", "May → Jun"). Each cell shows $ and % together, coloured by
 * direction, with a subtle pill when |%| ≥ 15. from_revenue = 0 → "n/a".
 */
import { useMemo } from "react";
import type { MonthlyRevenueRow, ProductHierarchy, RevenueChangeRow } from "@/lib/api/v2";
import { fmtMoney, fmtPct, isZeroish, monthShort } from "@/lib/v2/format";
import { PivotCard, type PivotColumn } from "./pivot-card";
import { type PivotRow, type Transition, buildRowTree, buildTransitions } from "./pivot-model";

const TOTAL_GROUP_ID = "__TOTAL__";

function monthName(monthId: string): string {
  return monthShort(monthId).split(" ")[0]; // "Apr 2026" -> "Apr"
}

export function MomChangePivot({
  hierarchy,
  revenue,
  changes,
  monthIds,
  advisorId,
}: {
  hierarchy: ProductHierarchy;
  revenue: MonthlyRevenueRow[];
  changes: RevenueChangeRow[];
  monthIds: string[];
  advisorId: string;
}) {
  const transitions = useMemo(() => buildTransitions(monthIds), [monthIds]);
  const monthSet = useMemo(() => new Set(monthIds), [monthIds]);

  // Change rows keyed "group|from>to" (leaf groups) and "from>to" (__TOTAL__).
  const { changeByCell, totalByTransition } = useMemo(() => {
    const byCell = new Map<string, RevenueChangeRow>();
    const totals = new Map<string, RevenueChangeRow>();
    for (const row of changes) {
      const key = `${row.from_month_id}>${row.to_month_id}`;
      if (row.group_id === TOTAL_GROUP_ID) totals.set(key, row);
      else if (!row.group_id.startsWith("__")) byCell.set(`${row.group_id}|${key}`, row);
    }
    return { changeByCell: byCell, totalByTransition: totals };
  }, [changes]);

  // Fallback source for groups a change row does not cover: the revenue rows.
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

  /** from/to revenue for one row over one transition. Group rows come from the
   * change rows; class/line rows sum their groups' from/to then $ and % are
   * recomputed; the Total row uses the "__TOTAL__" change row. */
  const fromTo = (row: PivotRow, t: Transition): { from: number; to: number } => {
    if (row.kind === "total") {
      const total = totalByTransition.get(t.key);
      if (total) return { from: total.from_revenue, to: total.to_revenue };
    }
    let from = 0;
    let to = 0;
    for (const g of row.groupIds) {
      const change = changeByCell.get(`${g}|${t.key}`);
      if (change) {
        from += change.from_revenue;
        to += change.to_revenue;
      } else {
        from += revByCell.get(`${g}|${t.from}`) ?? 0;
        to += revByCell.get(`${g}|${t.to}`) ?? 0;
      }
    }
    return { from, to };
  };

  const columns: PivotColumn[] = transitions.map((t) => ({
    key: t.key,
    header: `${monthName(t.from)} → ${monthName(t.to)}`,
    headerClassName: "normal-case tracking-normal",
  }));
  const transitionByKey = useMemo(
    () => new Map(transitions.map((t) => [t.key, t])),
    [transitions],
  );

  const renderCell = (row: PivotRow, col: PivotColumn) => {
    const t = transitionByKey.get(col.key);
    if (!t) return null;
    const { from, to } = fromTo(row, t);
    if (isZeroish(from) && isZeroish(to)) return <span className="text-v2-faint">—</span>;
    if (isZeroish(from)) return <span className="text-v2-faint">n/a</span>;
    const amt = to - from;
    const pct = (amt / from) * 100;
    const colour =
      amt > 0 ? "text-v2-positive" : amt < 0 ? "text-v2-negative" : "text-v2-muted";
    // Subtle pill on material moves (|%| ≥ 15) — reference 02 shows these on
    // hierarchy rows, not on the Total row.
    const pill =
      row.kind !== "total" && Math.abs(pct) >= 15
        ? amt >= 0
          ? "rounded-full bg-v2-positive-bg px-2 py-0.5"
          : "rounded-full bg-v2-negative-bg px-2 py-0.5"
        : "";
    return (
      <span className={`inline-block ${pill} ${colour}`}>
        {fmtMoney(amt)}&nbsp;&nbsp;{fmtPct(pct)}
      </span>
    );
  };

  return (
    <PivotCard
      title="Credited Revenue — MoM Change"
      subtitle="Month-over-month change in $ and %. Negatives shown in parentheses."
      columns={columns}
      rows={rows}
      renderCell={renderCell}
      cellText={(row, col) => {
        const t = transitionByKey.get(col.key);
        if (!t) return "";
        const { from, to } = fromTo(row, t);
        if (isZeroish(from) && isZeroish(to)) return "";
        if (isZeroish(from)) return "n/a";
        const amt = to - from;
        return `${fmtMoney(amt)} ${fmtPct((amt / from) * 100)}`;
      }}
      footnote="Change is computed from credited (post-split) revenue. Cells shaded where the move is 15% or more."
      exportFileName={`credited-revenue-mom-change-${advisorId}.csv`}
    />
  );
}
