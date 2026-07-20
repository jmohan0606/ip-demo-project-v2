"use client";
/**
 * Card 2 — commentary cards (UI_SPEC §5b, reference 03_ai_insights_walk.png).
 * The header title IS the question. One card per month-over-month transition,
 * five ranked driver rows each, provenance badge + cause tag, evidence links.
 * Commentary is retrieved (stored + versioned) — never generated on load.
 */
import { RefreshCw } from "lucide-react";
import type { EvidenceRequest } from "@/components/ai-insights/types";
import { downloadCsv } from "@/components/ai-insights/export-csv";
import { CauseTag, ProvenanceBadge } from "@/components/patterns/provenance-badge";
import type { CommentaryBullet, CommentaryRow, CommentaryVersion, MonthlyTotals } from "@/lib/api/v2";
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

export function exportCommentaryCsv(rows: CommentaryRow[]): void {
  downloadCsv("commentary.csv", [
    ["commentary_id", "version_id", "advisor_sid", "from_month", "to_month", "headline", "narrative_text", "status", "blocked_reason", "data_source"],
    ...rows.map((r) => [
      r.commentary_id, r.version_id, r.advisor_sid, r.from_month_id, r.to_month_id,
      r.headline, r.narrative_text, r.status, r.blocked_reason, r.data_source,
    ]),
  ]);
}

export function CommentaryCards({
  rows,
  totals,
  versions,
  selectedVersion,
  resolvedVersion,
  onSelectVersion,
  onRegenerate,
  busy,
  onOpenEvidence,
}: {
  rows: CommentaryRow[];
  totals: MonthlyTotals | null;
  versions: CommentaryVersion[];
  selectedVersion: string;
  resolvedVersion: string;
  onSelectVersion: (versionId: string) => void;
  onRegenerate: () => void;
  busy: boolean;
  onOpenEvidence: (req: EvidenceRequest) => void;
}) {
  const latest = latestPublished(versions);
  const sorted = [...rows].sort((a, b) => a.from_month_id.localeCompare(b.from_month_id));
  const selectValue = selectedVersion || latest?.version_id || "";

  return (
    <div className="rounded-[3px] border border-v2-border bg-v2-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-semibold text-v2-text">
            What is driving the changes in my month-over-month credited revenue?
          </h2>
          <p className="mt-0.5 text-[11.5px] text-v2-muted">
            One card per month-over-month move · five drivers ranked by impact · every figure computed from graph data
          </p>
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
          <button
            type="button"
            onClick={onRegenerate}
            disabled={busy}
            className="flex h-7 items-center gap-1.5 rounded-[3px] border border-v2-border bg-white px-2.5 text-[11.5px] text-v2-navy hover:bg-v2-sub-bg disabled:opacity-60"
          >
            <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
            {busy ? "Generating…" : "Regenerate"}
          </button>
          <button
            type="button"
            onClick={() => exportCommentaryCsv(sorted)}
            disabled={sorted.length === 0}
            className="h-7 rounded-[3px] border border-v2-border bg-white px-2.5 text-[11.5px] text-v2-navy hover:bg-v2-sub-bg disabled:opacity-60"
          >
            Export ⌄
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
        <div className="mt-4 grid grid-cols-2 gap-4">
          {sorted.map((row) => (
            <TransitionCard
              key={row.commentary_id}
              row={row}
              totals={totals}
              versionId={resolvedVersion || row.version_id}
              onOpenEvidence={onOpenEvidence}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TransitionCard({
  row,
  totals,
  versionId,
  onOpenEvidence,
}: {
  row: CommentaryRow;
  totals: MonthlyTotals | null;
  versionId: string;
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
        <div className="text-[11.5px] text-v2-text">{transitionLabel}</div>
        <div className="mt-0.5 flex items-baseline justify-between">
          <span className={`text-[19px] font-semibold ${up ? "text-v2-positive" : "text-v2-negative"}`}>
            {row.headline}
          </span>
          {txnCount != null && (
            <span className="text-[11px] text-v2-muted">{txnCount.toLocaleString("en-US")} transactions</span>
          )}
        </div>
      </div>

      {row.status === "BLOCKED" ? (
        <div className="m-4 rounded-[3px] bg-v2-warn-bg p-3 text-[11.5px] text-v2-warn">
          <span className="font-semibold">Commentary blocked for this transition. </span>
          {row.blocked_reason || "Validation failed — reason not recorded."}
        </div>
      ) : (
        <div className="flex-1 divide-y divide-v2-border-subtle px-4">
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
                    onOpenEvidence({
                      driverId: b.driver_id,
                      versionId,
                      transitionLabel,
                      driverIndex: i + 1,
                      driverCount: bullets.length,
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
      )}

      {row.status !== "BLOCKED" && (
        <div className="px-4 pb-3 pt-2 text-[10.5px] italic text-v2-muted">
          Contributions reconcile to the total change ✓
        </div>
      )}
    </div>
  );
}
