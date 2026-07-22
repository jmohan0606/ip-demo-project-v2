"use client";
/**
 * Card 3 — "Credited Revenue — Monthly Walk" (UI_SPEC §5c, reference
 * 06_ai_commentary_table.png). Dark two-row header (CHANGE spans $ and %),
 * one row per month, narrative_text as the commentary column, Evidence link
 * per non-baseline row opening the modal for that transition's TOP driver.
 */
import type { EvidenceRequest } from "@/components/ai-insights/types";
import { downloadCsv } from "@/components/ai-insights/export-csv";
import { latestPublished } from "@/components/ai-insights/commentary-cards";
import { AiGeneratedChip } from "@/components/patterns/ai-generated-chip";
import type { CommentaryRow, CommentaryVersion, MonthlyTotals, RevenueChangeRow } from "@/lib/api/v2";
import { fmtMoney, fmtPct, monthFull, monthShort } from "@/lib/v2/format";

export function MonthlyWalkTable({
  totals,
  changes,
  rows,
  versions,
  resolvedVersion,
  onOpenEvidence,
}: {
  totals: MonthlyTotals;
  changes: RevenueChangeRow[];
  rows: CommentaryRow[];
  versions: CommentaryVersion[];
  resolvedVersion: string;
  onOpenEvidence: (req: EvidenceRequest) => void;
}) {
  const monthIds = Object.keys(totals.revenue_by_month).sort();
  const changeByTo = new Map(
    changes.filter((c) => c.group_id === "__TOTAL__").map((c) => [c.to_month_id, c]),
  );
  const commentaryByTo = new Map(rows.map((r) => [r.to_month_id, r]));
  const latest = latestPublished(versions);
  const selectedMeta = versions.find((v) => v.version_id === resolvedVersion) ?? null;
  // T5-4 — the walk INHERITS the top section's version selector; this is
  // static text, not a control (the old lookalike dropdown was dead).
  const versionText = selectedMeta
    ? `Version ${selectedMeta.version_no}${latest && selectedMeta.version_id === latest.version_id ? " (latest)" : ""}`
    : null;

  const exportCsv = () =>
    downloadCsv("monthly-walk.csv", [
      ["month", "total_revenue", "change_amt", "change_pct", "commentary"],
      ...monthIds.map((m, i) => {
        const change = i === 0 ? null : changeByTo.get(m) ?? null;
        const commentary = i === 0 ? null : commentaryByTo.get(m) ?? null;
        return [
          monthShort(m),
          totals.revenue_by_month[m] ?? 0,
          change ? change.change_amt : "",
          change ? change.change_pct : "",
          i === 0 ? "Baseline month — no prior period in the current data set." : commentary?.narrative_text ?? "",
        ];
      }),
      // R7-2 — mark model-authored columns in the export too.
      ["# AI-generated columns: commentary. All other columns are computed from graph data."],
    ]);

  return (
    <div id="monthly-walk" className="rounded-[3px] border border-v2-border bg-v2-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[14px] font-semibold text-v2-text">Credited Revenue — Monthly Walk</h2>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">
            Full month-by-month view with AI commentary on the drivers of each change.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={exportCsv}
            className="h-7 rounded-[3px] border border-v2-border bg-white px-2.5 text-[11.5px] text-v2-navy hover:bg-v2-sub-bg"
          >
            Export ⌄
          </button>
          {versionText && (
            <span
              title="The walk shows the version selected in the commentary section above."
              className="flex h-7 items-center text-[11.5px] font-semibold text-v2-muted"
            >
              {versionText}
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-v2-navy-ink text-white">
              <th rowSpan={2} className="px-3 py-2 text-left align-bottom text-[10px] font-semibold uppercase tracking-[0.5px]">
                Month
              </th>
              <th rowSpan={2} className="px-3 py-2 text-right align-bottom text-[10px] font-semibold uppercase tracking-[0.5px]">
                Total Rev
              </th>
              <th colSpan={2} className="px-3 pt-2 text-center text-[10px] font-semibold uppercase tracking-[0.5px]">
                <span className="block border-b border-white/40 pb-1">Change</span>
              </th>
              <th rowSpan={2} className="px-3 py-2 text-left align-bottom text-[10px] font-semibold uppercase tracking-[0.5px]">
                <span className="flex items-center gap-2">
                  Commentary (Revenue Drivers)
                  <AiGeneratedChip
                    model={selectedMeta?.model}
                    promptVersion={selectedMeta?.prompt_version}
                    versionId={resolvedVersion || selectedMeta?.version_id}
                  />
                </span>
              </th>
              <th rowSpan={2} className="px-3 py-2 text-right align-bottom text-[10px] font-semibold uppercase tracking-[0.5px]">
                Evidence
              </th>
            </tr>
            <tr className="bg-v2-navy-ink text-white">
              <th className="px-3 pb-2 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">$</th>
              <th className="px-3 pb-2 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">%</th>
            </tr>
          </thead>
          <tbody>
            {monthIds.map((m, i) => {
              const baseline = i === 0;
              const change = baseline ? null : changeByTo.get(m) ?? null;
              const commentary = baseline ? null : commentaryByTo.get(m) ?? null;
              const up = (change?.change_amt ?? 0) >= 0;
              const changeCls = up ? "text-v2-positive" : "text-v2-negative";
              return (
                <tr key={m} className={`border-b border-v2-border-subtle align-top ${i % 2 === 1 ? "bg-v2-sub-bg" : ""}`}>
                  <td className="px-3 py-3 text-[12px] font-bold text-v2-text">{monthShort(m)}</td>
                  <td className="num px-3 py-3 text-[11.5px] text-v2-text">
                    {fmtMoney(totals.revenue_by_month[m] ?? 0)}
                  </td>
                  <td className={`num px-3 py-3 text-[12.5px] font-semibold ${baseline || !change ? "text-v2-faint" : changeCls}`}>
                    {baseline || !change ? "—" : fmtMoney(change.change_amt)}
                  </td>
                  <td className={`num px-3 py-3 text-[12.5px] font-semibold ${baseline || !change ? "text-v2-faint" : changeCls}`}>
                    {baseline || !change ? "—" : fmtPct(change.change_pct)}
                  </td>
                  <td className="max-w-[640px] px-3 py-3 text-[11.5px] text-v2-text">
                    {baseline ? (
                      <span className="italic text-v2-faint">Baseline month — no prior period in the current data set.</span>
                    ) : commentary && commentary.status === "BLOCKED" ? (
                      <span className="text-v2-warn">
                        <span className="font-semibold">Commentary blocked: </span>
                        {commentary.blocked_reason || "Validation failed — reason not recorded."}
                      </span>
                    ) : commentary ? (
                      commentary.narrative_text
                    ) : (
                      <span className="italic text-v2-faint">No commentary in the selected version.</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right">
                    {!baseline && commentary && (
                      <button
                        type="button"
                        onClick={() =>
                          // T2-2 — transition-level entry: open at driver 1
                          // with the FULL set for the transition (the modal
                          // loads and pages the whole set, not just the top).
                          onOpenEvidence({
                            versionId: resolvedVersion || commentary.version_id,
                            fromMonthId: commentary.from_month_id,
                            toMonthId: commentary.to_month_id,
                            transitionLabel: `${monthFull(commentary.from_month_id)} → ${monthFull(commentary.to_month_id)}`,
                          })
                        }
                        className="rounded-[3px] border border-v2-border bg-white px-2.5 py-1 text-[11px] text-v2-link hover:bg-v2-sub-bg"
                      >
                        Evidence ›
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[10.5px] italic text-v2-faint">
        Commentary is generated once per version and stored in the graph — it is retrieved, not recalculated, so figures
        are identical on every view.
      </p>
    </div>
  );
}
