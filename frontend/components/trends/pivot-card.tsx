"use client";
/**
 * Shared card + hierarchical table shell for the two Trends pivots (UI_SPEC §4).
 * Owns expand/collapse state, the "Expand all" control, and client-side CSV
 * export built from the already-loaded data (no fake behaviour).
 */
import { type ReactNode, useMemo, useState } from "react";
import { type PivotRow, flattenRows } from "./pivot-model";

export interface PivotColumn {
  key: string;
  header: string;
  /** e.g. "normal-case tracking-normal" for "Apr → May" transition headers. */
  headerClassName?: string;
}

const ROW_BG: Record<PivotRow["kind"], string> = {
  total: "bg-v2-total-bg font-bold",
  class: "bg-v2-group-bg font-semibold",
  line: "bg-v2-sub-bg",
  group: "bg-white",
};

function csvField(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function PivotCard({
  title,
  subtitle,
  columns,
  rows,
  renderCell,
  cellText,
  footnote,
  exportFileName,
}: {
  title: string;
  subtitle: string;
  columns: PivotColumn[];
  rows: PivotRow[];
  renderCell: (row: PivotRow, col: PivotColumn) => ReactNode;
  /** Raw text for the CSV export of one cell. */
  cellText: (row: PivotRow, col: PivotColumn) => string;
  footnote: string;
  exportFileName: string;
}) {
  // Expandable = has children. Collapsed set is the state; default all expanded.
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const allRows = useMemo(() => flattenRows(rows), [rows]);
  const expandableIds = useMemo(
    () => allRows.filter((r) => r.children.length > 0).map((r) => r.id),
    [allRows],
  );
  const allExpanded = collapsedIds.size === 0;

  const toggle = (id: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // A row is visible when no ancestor is collapsed. Depth-first walk that skips
  // the subtree of any collapsed row.
  const visibleRows = useMemo(() => {
    const out: PivotRow[] = [];
    const walk = (row: PivotRow) => {
      out.push(row);
      if (!collapsedIds.has(row.id)) row.children.forEach(walk);
    };
    rows.forEach(walk);
    return out;
  }, [rows, collapsedIds]);

  const exportCsv = () => {
    const lines = [
      ["Product", ...columns.map((c) => c.header)].map(csvField).join(","),
      ...allRows.map((row) =>
        [row.label, ...columns.map((c) => cellText(row, c))].map(csvField).join(","),
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="rounded-[3px] border border-v2-border bg-v2-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[14px] font-semibold text-v2-text">{title}</h2>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">{subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={exportCsv}
            className="rounded-[3px] border border-v2-border bg-white px-3 py-1 text-[11.5px] text-v2-text hover:bg-v2-sub-bg"
          >
            Export ⌄
          </button>
          <button
            type="button"
            onClick={() =>
              setCollapsedIds(allExpanded ? new Set(expandableIds) : new Set())
            }
            className="rounded-[3px] border border-v2-border bg-white px-3 py-1 text-[11.5px] text-v2-link hover:bg-v2-sub-bg"
          >
            {allExpanded ? "Collapse all" : "Expand all"}
          </button>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse text-[11.5px]">
          <thead>
            <tr className="bg-v2-header-bg">
              <th className="px-3 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-v2-navy">
                Product
              </th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-1.5 text-right text-[10px] font-semibold uppercase tracking-wide text-v2-navy ${col.headerClassName ?? ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id} className={`border-b border-v2-border-subtle ${ROW_BG[row.kind]}`}>
                <td className="py-1 pr-3" style={{ paddingLeft: 12 + row.indent }}>
                  {row.children.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => toggle(row.id)}
                      aria-expanded={!collapsedIds.has(row.id)}
                      aria-label={`${collapsedIds.has(row.id) ? "Expand" : "Collapse"} ${row.label}`}
                      className="mr-1 inline-block w-3 text-[9px] text-v2-muted"
                    >
                      {collapsedIds.has(row.id) ? "▸" : "▾"}
                    </button>
                  ) : (
                    <span className="mr-1 inline-block w-3" />
                  )}
                  {row.label}
                </td>
                {columns.map((col) => (
                  <td key={col.key} className="whitespace-nowrap px-3 py-1 text-right">
                    {renderCell(row, col)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[10.5px] italic text-v2-faint">{footnote}</p>
    </section>
  );
}
