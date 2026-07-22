"use client";
/**
 * Card 2 — commentary cards (UI_SPEC §5b, reference 03_ai_insights_walk.png).
 * The header title IS the question. One card per month-over-month transition,
 * five ranked driver rows each, provenance badge + cause tag, evidence links.
 * Commentary is retrieved (stored + versioned) — never generated on load.
 */
import { useState } from "react";
import { RefreshCw } from "lucide-react";
import type { EvidenceRequest } from "@/components/ai-insights/types";
import { exportDriversData } from "@/components/ai-insights/export-data";
import { useV2Context } from "@/components/layout/v2-shell";
import {
  AI_BOUNDARY_TEXT,
  AiGeneratedChip,
  JudgeBadge,
} from "@/components/patterns/ai-generated-chip";
import { CauseTag, ProvenanceBadge } from "@/components/patterns/provenance-badge";
import { GlossaryLink } from "@/components/patterns/revenue-driver-glossary";
import type {
  CommentaryBullet,
  CommentaryEvaluation,
  CommentaryRow,
  CommentaryVersion,
  MonthlyTotals,
  RevenueChangeRow,
} from "@/lib/api/v2";
import { monthFull } from "@/lib/v2/format";

const MONTHS_SHORT = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-07-20T12:20:31" -> "20 Jul 12:20" for the version selector. */
export function fmtVersionTime(value: string): string {
  const s = String(value ?? "");
  const day = s.slice(8, 10);
  const month = Number(s.slice(5, 7));
  const time = s.slice(11, 16);
  if (!day || !month) return s;
  return `${Number(day)} ${MONTHS_SHORT[month] ?? ""}${time ? ` ${time}` : ""}`;
}

export function latestPublished(versions: CommentaryVersion[]): CommentaryVersion | null {
  return (
    [...versions]
      .filter((v) => v.status === "PUBLISHED")
      .sort((a, b) => b.version_no - a.version_no)[0] ?? null
  );
}

function parseBullets(row: CommentaryRow): CommentaryBullet[] {
  try {
    const parsed = JSON.parse(row.bullets_json || "[]");
    return Array.isArray(parsed) ? (parsed as CommentaryBullet[]) : [];
  } catch {
    return [];
  }
}

export function CommentaryCards({
  rows,
  totals,
  versions,
  selectedVersion,
  resolvedVersion,
  evaluations = [],
  onSelectVersion,
  onRegenerate,
  busy,
  onOpenEvidence,
  viewMode = "single",
  onViewMode,
  selectedTo = "",
  onSelectTo,
  changes = [],
}: {
  rows: CommentaryRow[];
  totals: MonthlyTotals | null;
  versions: CommentaryVersion[];
  selectedVersion: string;
  resolvedVersion: string;
  /** R5-4 — judge evaluations for the resolved version (advisory badges). */
  evaluations?: CommentaryEvaluation[];
  onSelectVersion: (versionId: string) => void;
  onRegenerate: () => void;
  busy: boolean;
  onOpenEvidence: (req: EvidenceRequest) => void;
  /** T5-2 — Single transition (default) / Compare two / All transitions. */
  viewMode?: "single" | "compare" | "all";
  onViewMode?: (mode: "single" | "compare" | "all") => void;
  /** to-month of the transition in Single mode ("" = latest). */
  selectedTo?: string;
  onSelectTo?: (toMonthId: string) => void;
  /** T6-1 — stored __TOTAL__ changes; the data export is built from these +
   * the driver API, never from rendered DOM values. */
  changes?: RevenueChangeRow[];
}) {
  const { advisorId, advisor, fromMonth, toMonth } = useV2Context();
  const [exporting, setExporting] = useState(false);
  const latest = latestPublished(versions);
  const sorted = [...rows].sort((a, b) => a.from_month_id.localeCompare(b.from_month_id));
  const selectValue = selectedVersion || latest?.version_id || "";
  const versionMeta =
    versions.find((v) => v.version_id === (resolvedVersion || selectValue)) ?? latest;
  const evaluationFor = (row: CommentaryRow): CommentaryEvaluation | null =>
    evaluations.find(
      (e) =>
        e.commentary_id === row.commentary_id ||
        e.commentary_id.startsWith(`${row.commentary_id}|`),
    ) ?? null;

  return (
    <div className="rounded-[3px] border border-v2-border bg-v2-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-semibold text-v2-text">
            What is driving the changes in my month-over-month credited revenue?
          </h2>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">
            One card per month-over-month move · five revenue drivers ranked by impact · every
            figure computed from graph data · <GlossaryLink />
          </p>
          <p className="mt-1 text-[10.5px] text-v2-faint">{AI_BOUNDARY_TEXT}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-[11px] text-v2-muted">Commentary version</span>
          <select
            value={selectValue}
            onChange={(e) => onSelectVersion(e.target.value)}
            className="h-7 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]"
            aria-label="Commentary version"
          >
            {versions.length === 0 && <option value="">No versions yet</option>}
            {[...versions]
              .sort((a, b) => b.version_no - a.version_no)
              .map((v) => (
                <option key={v.version_id} value={v.version_id}>
                  v{v.version_no} · {fmtVersionTime(v.generated_at)}
                  {latest && v.version_id === latest.version_id ? " (latest)" : ""}
                  {v.status !== "PUBLISHED" ? ` · ${v.status}` : ""}
                </option>
              ))}
          </select>
          {/* T7-1 — main action gets the primary navy fill; exports are
              secondary outline. Hover/focus/disabled states styled. */}
          <button
            type="button"
            onClick={onRegenerate}
            disabled={busy}
            className="flex h-7 items-center gap-1.5 rounded-[3px] bg-v2-navy px-3 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
            {busy ? "Generating…" : "Regenerate"}
          </button>
          {/* T6-3 — two clearly-labelled exports: stored-data CSV + print PDF. */}
          <button
            type="button"
            onClick={() => {
              if (!advisorId || exporting) return;
              setExporting(true);
              void exportDriversData({
                advisorId,
                advisorName: advisor?.advisor_name ?? "",
                fromMonth,
                toMonth,
                commentaries: sorted,
                changes,
                version: versionMeta ?? null,
              }).finally(() => setExporting(false));
            }}
            disabled={sorted.length === 0 || exporting || !advisorId}
            title="CSV built from the stored data — one row per transition and revenue driver"
            className="h-7 rounded-[3px] border border-v2-navy bg-white px-2.5 text-[11.5px] font-semibold text-v2-navy hover:bg-v2-sub-bg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:border-v2-border disabled:text-v2-faint"
          >
            {exporting ? "Exporting…" : "Export data"}
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            disabled={sorted.length === 0}
            title="Print-quality PDF of this view (vector, deck-ready)"
            className="h-7 rounded-[3px] border border-v2-navy bg-white px-2.5 text-[11.5px] font-semibold text-v2-navy hover:bg-v2-sub-bg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:border-v2-border disabled:text-v2-faint"
          >
            Export PDF
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="mt-6 flex flex-col items-center gap-3 py-8">
          <p className="text-[11.5px] text-v2-muted">No commentary generated for this advisor yet.</p>
          <button
            type="button"
            onClick={onRegenerate}
            disabled={busy}
            className="h-7 rounded-[3px] bg-v2-navy px-3.5 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark disabled:opacity-60"
          >
            {busy ? "Generating…" : "Generate commentary"}
          </button>
        </div>
      ) : (
        <TransitionViews
          sorted={sorted}
          totals={totals}
          versionId={resolvedVersion}
          versionMeta={versionMeta ?? null}
          evaluationFor={evaluationFor}
          onOpenEvidence={onOpenEvidence}
          viewMode={viewMode}
          onViewMode={onViewMode}
          selectedTo={selectedTo}
          onSelectTo={onSelectTo}
        />
      )}
    </div>
  );
}

const transitionLabelOf = (r: CommentaryRow) =>
  `${monthFull(r.from_month_id)} → ${monthFull(r.to_month_id)}`;

/** T5-2 — the driver section's view-mode control, built for the 12-month
 * target state: Single transition (default) focuses one month-over-month with
 * full detail; Compare two keeps the side-by-side view; All transitions points
 * at the monthly walk table. */
function TransitionViews({
  sorted,
  totals,
  versionId,
  versionMeta,
  evaluationFor,
  onOpenEvidence,
  viewMode,
  onViewMode,
  selectedTo,
  onSelectTo,
}: {
  sorted: CommentaryRow[];
  totals: MonthlyTotals | null;
  versionId: string;
  versionMeta: CommentaryVersion | null;
  evaluationFor: (row: CommentaryRow) => CommentaryEvaluation | null;
  onOpenEvidence: (req: EvidenceRequest) => void;
  viewMode: "single" | "compare" | "all";
  onViewMode?: (mode: "single" | "compare" | "all") => void;
  selectedTo: string;
  onSelectTo?: (toMonthId: string) => void;
}) {
  const single =
    sorted.find((r) => r.to_month_id === selectedTo) ?? sorted[sorted.length - 1];
  const [compareA, setCompareA] = useState(sorted[0]?.to_month_id ?? "");
  const [compareB, setCompareB] = useState(sorted[1]?.to_month_id ?? sorted[0]?.to_month_id ?? "");
  const byTo = (to: string) => sorted.find((r) => r.to_month_id === to) ?? null;
  const compareRows = [byTo(compareA), byTo(compareB)].filter(
    (r): r is CommentaryRow => r != null,
  );

  const modes: { key: "single" | "compare" | "all"; label: string }[] = [
    { key: "single", label: "Single transition" },
    { key: "compare", label: "Compare two" },
    { key: "all", label: "All transitions" },
  ];
  const selectCls = "h-7 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]";

  const card = (row: CommentaryRow) => (
    <TransitionCard
      key={row.commentary_id}
      row={row}
      totals={totals}
      versionId={versionId || row.version_id}
      versionMeta={versionMeta}
      evaluation={evaluationFor(row)}
      onOpenEvidence={onOpenEvidence}
    />
  );

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-3">
        <div
          role="tablist"
          aria-label="Transition view mode"
          className="flex overflow-hidden rounded-[3px] border border-v2-border"
        >
          {modes.map((m) => (
            <button
              key={m.key}
              type="button"
              role="tab"
              aria-selected={viewMode === m.key}
              onClick={() => onViewMode?.(m.key)}
              className={`h-7 px-3 text-[11.5px] font-semibold ${
                viewMode === m.key
                  ? "bg-v2-navy text-white"
                  : "bg-white text-v2-navy hover:bg-v2-sub-bg"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        {viewMode === "single" && (
          <select
            value={single?.to_month_id ?? ""}
            onChange={(e) => onSelectTo?.(e.target.value)}
            aria-label="Transition"
            className={selectCls}
          >
            {sorted.map((r) => (
              <option key={r.to_month_id} value={r.to_month_id}>
                {transitionLabelOf(r)}
              </option>
            ))}
          </select>
        )}
        {viewMode === "compare" && (
          <>
            <select value={compareA} onChange={(e) => setCompareA(e.target.value)} aria-label="First transition" className={selectCls}>
              {sorted.map((r) => (
                <option key={r.to_month_id} value={r.to_month_id}>{transitionLabelOf(r)}</option>
              ))}
            </select>
            <span className="text-[11px] text-v2-muted">vs</span>
            <select value={compareB} onChange={(e) => setCompareB(e.target.value)} aria-label="Second transition" className={selectCls}>
              {sorted.map((r) => (
                <option key={r.to_month_id} value={r.to_month_id}>{transitionLabelOf(r)}</option>
              ))}
            </select>
          </>
        )}
        {viewMode === "single" && (
          <span className="text-[10.5px] text-v2-faint">
            Tip: click a chart arrow above to focus that transition.
          </span>
        )}
      </div>

      {viewMode === "single" && single && (
        <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)]">{card(single)}</div>
      )}
      {viewMode === "compare" && (
        <div className="mt-3 grid grid-cols-2 gap-4">{compareRows.map(card)}</div>
      )}
      {viewMode === "all" && (
        <div className="mt-3 rounded-[3px] border border-v2-border bg-v2-sub-bg px-4 py-3 text-[11.5px] text-v2-text">
          All {sorted.length} transitions are listed in the{" "}
          <a href="#monthly-walk" className="font-semibold text-v2-link hover:underline">
            Credited Revenue — Monthly Walk
          </a>{" "}
          table below — one row per month with its change, commentary and evidence.
        </div>
      )}
    </div>
  );
}

function TransitionCard({
  row,
  totals,
  versionId,
  versionMeta,
  evaluation,
  onOpenEvidence,
}: {
  row: CommentaryRow;
  totals: MonthlyTotals | null;
  versionId: string;
  versionMeta: CommentaryVersion | null;
  evaluation: CommentaryEvaluation | null;
  onOpenEvidence: (req: EvidenceRequest) => void;
}) {
  const up = row.headline.trim().startsWith("▲");
  const bullets = parseBullets(row);
  const transitionLabel = `${monthFull(row.from_month_id)} → ${monthFull(row.to_month_id)}`;
  const txnByMonth = totals?.txn_count_by_month ?? {};
  const fromTxn = txnByMonth[row.from_month_id];
  const toTxn = txnByMonth[row.to_month_id];
  const txnCount = fromTxn == null && toTxn == null ? null : (fromTxn ?? 0) + (toTxn ?? 0);

  return (
    <div className="flex flex-col overflow-hidden rounded-[3px] border border-v2-border">
      <div className={`px-4 py-3 ${up ? "bg-v2-positive-bg" : "bg-v2-negative-bg"}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11.5px] text-v2-text">{transitionLabel}</span>
          <span className="flex shrink-0 items-center gap-1.5">
            <AiGeneratedChip
              model={versionMeta?.model}
              promptVersion={versionMeta?.prompt_version}
              versionId={versionId}
            />
            {evaluation && <JudgeBadge verdict={evaluation.verdict} />}
          </span>
        </div>
        <div className="mt-0.5">
          <span className={`text-[19px] font-semibold ${up ? "text-v2-positive" : "text-v2-negative"}`}>
            {row.headline}
          </span>
        </div>
        {/* T7-2 — the transaction count is COMPUTED, not AI-generated; it sits
            on its own line behind a hairline so it never reads as covered by
            the AI chip above (which marks the narrative wording only). */}
        {txnCount != null && (
          <div className="num mt-1.5 border-t border-black/10 pt-1 text-[10.5px] text-v2-muted">
            {txnCount.toLocaleString("en-US")} transactions · computed from graph data
          </div>
        )}
      </div>

      {row.status === "BLOCKED" ? (
        <div className="m-4 rounded-[3px] bg-v2-warn-bg p-3 text-[11.5px] text-v2-warn">
          <span className="font-semibold">Commentary blocked for this transition. </span>
          {row.blocked_reason || "Validation failed — reason not recorded."}
        </div>
      ) : (
        <div className="flex-1 px-4">
          {/* T4-2 — the ✓/✗ rows are the transition's revenue drivers; a
              first-time viewer gets an explicit column header saying so. */}
          <div className="flex items-center justify-between border-b border-v2-border pb-1.5 pt-2.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
              Revenue Drivers
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
              Source · Driver
            </span>
          </div>
          <div className="divide-y divide-v2-border-subtle">
          {bullets.map((b, i) => (
            <div key={b.driver_id || i} className="flex items-start gap-2.5 py-2.5">
              <span
                className={`mt-0.5 text-[12px] font-semibold ${b.direction === "UP" ? "text-v2-positive" : "text-v2-negative"}`}
                aria-label={b.direction === "UP" ? "Positive driver" : "Negative driver"}
              >
                {b.direction === "UP" ? "✓" : "✗"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-bold text-v2-text">{b.title}</div>
                <div className="mt-0.5 text-[11.5px] text-v2-muted">{b.text}</div>
                <button
                  type="button"
                  onClick={() =>
                    // T2-2 — open at THIS driver, with the transition's full
                    // set loaded so the user can page to the others.
                    onOpenEvidence({
                      versionId,
                      fromMonthId: row.from_month_id,
                      toMonthId: row.to_month_id,
                      transitionLabel,
                      initialDriverId: b.driver_id,
                    })
                  }
                  className="mt-1 text-[11px] text-v2-link hover:underline"
                >
                  View evidence ›
                </button>
              </div>
              <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
                <ProvenanceBadge value={b.data_source} />
                <CauseTag causeId={b.cause_id} />
              </div>
            </div>
          ))}
          </div>
        </div>
      )}

      {row.status !== "BLOCKED" && (
        <div className="px-4 pb-3 pt-2 text-[10.5px] italic text-v2-muted">
          Contributions reconcile to the total change ✓
        </div>
      )}
    </div>
  );
}
