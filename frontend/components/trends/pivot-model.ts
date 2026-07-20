/**
 * Row-tree model shared by the two Trends pivots (UI_SPEC §4).
 * Rows: Total → class (Recurring / Non-recurring) → line (Managed, Trails, …)
 * → leaf GROUP rows. Built from the product-hierarchy reference data; groups
 * with no data in the selected range are omitted, and lines/classes with no
 * surviving children are omitted with them.
 */
import type { HierarchyNode, ProductHierarchy } from "@/lib/api/v2";

export type RowKind = "total" | "class" | "line" | "group";

export interface PivotRow {
  id: string;
  kind: RowKind;
  label: string;
  /** Left indent in px: 0 / 18 / 38 per UI_SPEC §4a. */
  indent: number;
  /** Leaf rows only — the product group this row represents. */
  groupId?: string;
  /** Every leaf group id under this row (self for leaves) — aggregation key. */
  groupIds: string[];
  children: PivotRow[];
}

export interface Transition {
  from: string;
  to: string;
  key: string;
}

/** Consecutive month pairs — the FIRST month has no transition column. */
export function buildTransitions(monthIds: string[]): Transition[] {
  const out: Transition[] = [];
  for (let i = 1; i < monthIds.length; i += 1) {
    out.push({ from: monthIds[i - 1], to: monthIds[i], key: `${monthIds[i - 1]}>${monthIds[i]}` });
  }
  return out;
}

function byOrder(a: HierarchyNode, b: HierarchyNode): number {
  const ao = a.display_order ?? 0;
  const bo = b.display_order ?? 0;
  if (ao !== bo) return ao - bo;
  return (a.class_name ?? a.line_name ?? a.group_name ?? "").localeCompare(
    b.class_name ?? b.line_name ?? b.group_name ?? "",
  );
}

/**
 * Build [Total, ...classes] from the hierarchy, keeping only groups whose id
 * appears in `dataGroupIds` (i.e. groups with at least one revenue row in the
 * selected range).
 */
export function buildRowTree(hierarchy: ProductHierarchy, dataGroupIds: Set<string>): PivotRow[] {
  const linesByClass = new Map<string, HierarchyNode[]>();
  for (const line of hierarchy.lines) {
    const list = linesByClass.get(line.parent_id) ?? [];
    list.push(line);
    linesByClass.set(line.parent_id, list);
  }
  const groupsByLine = new Map<string, HierarchyNode[]>();
  for (const group of hierarchy.groups) {
    const list = groupsByLine.get(group.parent_id) ?? [];
    list.push(group);
    groupsByLine.set(group.parent_id, list);
  }

  const classRows: PivotRow[] = [];
  for (const cls of [...hierarchy.classes].sort(byOrder)) {
    const classId = cls.class_id ?? "";
    const lineRows: PivotRow[] = [];
    for (const line of (linesByClass.get(classId) ?? []).sort(byOrder)) {
      const lineId = line.line_id ?? "";
      const groupRows: PivotRow[] = [];
      for (const group of (groupsByLine.get(lineId) ?? []).sort(byOrder)) {
        const groupId = group.group_id ?? "";
        if (!dataGroupIds.has(groupId)) continue; // no data in range → omit
        groupRows.push({
          id: `group:${groupId}`,
          kind: "group",
          label: group.group_name ?? groupId,
          indent: 38,
          groupId,
          groupIds: [groupId],
          children: [],
        });
      }
      if (groupRows.length === 0) continue; // line with no data → omit
      lineRows.push({
        id: `line:${lineId}`,
        kind: "line",
        label: line.line_name ?? lineId,
        indent: 18,
        groupIds: groupRows.flatMap((g) => g.groupIds),
        children: groupRows,
      });
    }
    if (lineRows.length === 0) continue; // class with no data → omit
    classRows.push({
      id: `class:${classId}`,
      kind: "class",
      label: cls.class_name ?? classId,
      indent: 0,
      groupIds: lineRows.flatMap((l) => l.groupIds),
      children: lineRows,
    });
  }

  const total: PivotRow = {
    id: "total",
    kind: "total",
    label: "Total",
    indent: 0,
    groupIds: classRows.flatMap((c) => c.groupIds),
    children: [],
  };
  return [total, ...classRows];
}

/** Depth-first flatten of the tree in display order (Total, class, lines, groups…). */
export function flattenRows(rows: PivotRow[]): PivotRow[] {
  const out: PivotRow[] = [];
  const walk = (row: PivotRow) => {
    out.push(row);
    row.children.forEach(walk);
  };
  rows.forEach(walk);
  return out;
}
