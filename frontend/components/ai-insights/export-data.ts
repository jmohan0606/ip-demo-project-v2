/**
 * T6-1 — real data exports, built from STORED data via the API (never scraped
 * from the DOM). Human column headers, one row per (transition, revenue
 * driver), negatives parenthesised, AI-generated columns marked (rule 8a).
 * The numbers are the same stored figures the month-over-month section and
 * monthly walk render — same drivers, same values.
 */
import { downloadCsv } from "@/components/ai-insights/export-csv";
import {
  type CommentaryRow,
  type DriverRow,
  type CommentaryVersion,
  type RevenueChangeRow,
  v2Api,
} from "@/lib/api/v2";
import { fmtMoney, fmtPct, monthFull } from "@/lib/v2/format";

const AI_FOOTER =
  "# AI-generated columns: Commentary. Every other column is computed from graph data — the model never produces or alters a number.";

/** Stored display name per cause_id (phx_dm_v2_driver_cause), with a humanised
 * fallback so an unknown id still exports readably. */
async function causeNames(): Promise<Record<string, string>> {
  try {
    const res = await v2Api.driverCauses();
    return Object.fromEntries(res.causes.map((c) => [c.cause_id, c.cause_name]));
  } catch {
    return {};
  }
}

const humanCause = (names: Record<string, string>, causeId: string) =>
  names[causeId] ?? causeId.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

function totalChangeRow(changes: RevenueChangeRow[], toMonth: string): RevenueChangeRow | null {
  return (
    changes.find((c) => c.group_id === "__TOTAL__" && c.to_month_id === toMonth) ?? null
  );
}

/** In-scope (total) revenue per month, summed from the stored per-group rows.
 * Falls back to null (exported as em dash) if the fetch fails. */
async function inScopeByMonth(
  advisorId: string,
  fromMonth: string,
  toMonth: string,
): Promise<Record<string, number> | null> {
  try {
    const res = await v2Api.trendsRevenue(advisorId, fromMonth, toMonth);
    const by: Record<string, number> = {};
    for (const r of res.monthly_revenue) {
      by[r.month_id] = (by[r.month_id] ?? 0) + (r.total_revenue ?? 0);
    }
    return by;
  } catch {
    return null;
  }
}

/** One row per (transition, revenue driver) — the month-over-month section's
 * stored data in spreadsheet form. */
export async function exportDriversData(opts: {
  advisorId: string;
  advisorName: string;
  fromMonth: string;
  toMonth: string;
  commentaries: CommentaryRow[];
  changes: RevenueChangeRow[];
  version: CommentaryVersion | null;
}): Promise<void> {
  const { advisorId, advisorName, fromMonth, toMonth, commentaries, changes, version } = opts;
  const names = await causeNames();
  const inScope = await inScopeByMonth(advisorId, fromMonth, toMonth);
  const sorted = [...commentaries].sort((a, b) => a.from_month_id.localeCompare(b.from_month_id));

  const header = [
    "Advisor", "From Month", "To Month", "Total Revenue", "Credited Revenue",
    "Change ($)", "Change (%)", "Revenue Driver", "Driver Contribution ($)",
    "Direction", "Data Source", "Commentary",
  ];
  const rows: (string | number)[][] = [header];
  for (const c of sorted) {
    const change = totalChangeRow(changes, c.to_month_id);
    let drivers: DriverRow[] = [];
    try {
      const res = await v2Api.insightsDrivers(advisorId, c.from_month_id, c.to_month_id);
      drivers = [...res.drivers].sort((a, b) => a.rank - b.rank);
    } catch {
      drivers = [];
    }
    const base = [
      `${advisorId}${advisorName ? ` — ${advisorName}` : ""}`,
      monthFull(c.from_month_id),
      monthFull(c.to_month_id),
      inScope?.[c.to_month_id] != null ? fmtMoney(inScope[c.to_month_id], 2) : "—",
      change ? fmtMoney(change.to_revenue, 2) : "—",
      change ? fmtMoney(change.change_amt, 2) : "—",
      change ? fmtPct(change.change_pct) : "—",
    ];
    const commentaryText =
      c.status === "BLOCKED"
        ? `[BLOCKED] ${c.blocked_reason || "validation failed"}`
        : c.narrative_text;
    if (drivers.length === 0) {
      rows.push([...base, "—", "—", "—", "—", commentaryText]);
    }
    for (const d of drivers) {
      rows.push([
        ...base,
        humanCause(names, d.cause_id),
        fmtMoney(d.contribution_amt, 2),
        d.direction,
        d.data_source,
        commentaryText,
      ]);
    }
  }
  rows.push([`# Commentary version: ${version ? `v${version.version_no} (${version.model})` : "n/a"}`]);
  rows.push(["# Total Revenue = in-scope revenue (total within credited product grid types)."]);
  rows.push([AI_FOOTER]);
  downloadCsv(`revenue-drivers_${advisorId}.csv`, rows);
}

/** Monthly-walk export — one row per month with its commentary and drivers. */
export async function exportWalkData(opts: {
  advisorId: string;
  advisorName: string;
  monthIds: string[];
  revenueByMonth: Record<string, number>;
  commentaries: CommentaryRow[];
  changes: RevenueChangeRow[];
  version: CommentaryVersion | null;
}): Promise<void> {
  const { advisorId, advisorName, monthIds, revenueByMonth, commentaries, changes, version } = opts;
  const names = await causeNames();
  const byTo = new Map(commentaries.map((r) => [r.to_month_id, r]));

  const rows: (string | number)[][] = [
    ["Advisor", "Month", "Credited Revenue", "Change ($)", "Change (%)", "Revenue Drivers", "Commentary"],
  ];
  for (let i = 0; i < monthIds.length; i++) {
    const m = monthIds[i];
    const change = i === 0 ? null : totalChangeRow(changes, m);
    const commentary = i === 0 ? null : byTo.get(m) ?? null;
    let driverText = "—";
    if (i > 0 && commentary) {
      try {
        const res = await v2Api.insightsDrivers(advisorId, commentary.from_month_id, m);
        driverText = [...res.drivers]
          .sort((a, b) => a.rank - b.rank)
          .filter((d) => Math.abs(d.contribution_amt) >= 0.005)
          .map((d) => `${humanCause(names, d.cause_id)} ${fmtMoney(d.contribution_amt, 2)}`)
          .join("; ") || "—";
      } catch {
        driverText = "—";
      }
    }
    rows.push([
      `${advisorId}${advisorName ? ` — ${advisorName}` : ""}`,
      monthFull(m),
      fmtMoney(revenueByMonth[m] ?? 0, 2),
      change ? fmtMoney(change.change_amt, 2) : "—",
      change ? fmtPct(change.change_pct) : "—",
      driverText,
      i === 0
        ? "Baseline month — no prior period in the current data set."
        : commentary?.status === "BLOCKED"
          ? `[BLOCKED] ${commentary.blocked_reason || "validation failed"}`
          : commentary?.narrative_text ?? "—",
    ]);
  }
  rows.push([`# Commentary version: ${version ? `v${version.version_no} (${version.model})` : "n/a"}`]);
  rows.push([AI_FOOTER]);
  downloadCsv(`monthly-walk_${advisorId}.csv`, rows);
}
