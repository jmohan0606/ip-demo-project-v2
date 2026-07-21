"use client";
/**
 * Evidence modal (UI_SPEC §6, reference 04_evidence_popup.png).
 * Answers "how do we know this is right?" — five numbered sections:
 * Finding · Calculation · Source records · Lineage & checks · Reproduce.
 * Every figure shown is retrieved from the stored evidence record (GQ-012
 * consumer); nothing is computed or generated here.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  type CommentaryVersion,
  type EvidenceRecord,
  v2Api,
} from "@/lib/api/v2";
import { fmtDate, fmtMoney, monthShort } from "@/lib/v2/format";
import { AsyncBoundary } from "@/components/patterns/async-state";
import { CauseTag, ProvenanceBadge } from "@/components/patterns/provenance-badge";

interface CalcComponent {
  label: string;
  unit?: string; // currency | count | percent | bps | days (R2-1)
  from: number;
  to: number;
  change: number;
  share_of_mom: number;
}
interface CalcJson {
  components: CalcComponent[];
  formula: string;
}
interface SourceRecordRow {
  trade_ref: string;
  date: string;
  product: string;
  account: string;
  type: string;
  credited: number;
  split_pct: number;
}
interface SourceRecordsJson {
  sample: SourceRecordRow[];
  total_contributing: number;
  from_month_count: number;
  to_month_count: number;
}
interface LineageStep {
  vertex: string;
  matches: number | string;
}
interface CheckRow {
  check: string;
  passed: boolean;
  detail: string;
}

function parseJson<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** "structured_products" -> "Structured Products"; "__TOTAL__" -> "Total". */
function humanizeGroup(segment: string): string {
  if (!segment) return "—";
  if (segment === "__TOTAL__") return "Total";
  return segment
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function SectionHeader({ n, title }: { n: number; title: string }) {
  return (
    <div className="mb-2 flex items-center gap-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-v2-navy text-[11.5px] font-semibold text-white">
        {n}
      </span>
      <h3 className="text-[14px] font-semibold text-v2-text">{title}</h3>
    </div>
  );
}

function CopyButton({ text, className = "" }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
      className={`rounded-[3px] bg-white/10 px-2.5 py-1 text-[10.5px] font-semibold text-white hover:bg-white/20 ${className}`}
    >
      {copied ? "Copied" : "⧉ Copy"}
    </button>
  );
}

/** Format the GSQL call: RUN QUERY name(\n  param = "value", ...) */
function gsqlCallText(queryName: string, params: Record<string, unknown>): string {
  const entries = Object.entries(params);
  if (!entries.length) return `RUN QUERY ${queryName}()`;
  const lines = entries.map(
    ([k, v], i) =>
      `  ${k} = ${typeof v === "number" ? String(v) : `"${String(v)}"`}${
        i < entries.length - 1 ? "," : ""
      }`,
  );
  return `RUN QUERY ${queryName}(\n${lines.join("\n")}\n)`;
}

export function EvidenceModal({
  driverId,
  versionId,
  advisorId,
  advisorName,
  transitionLabel,
  driverIndex,
  driverCount,
  onClose,
}: {
  driverId: string;
  versionId: string;
  advisorId: string;
  advisorName: string;
  transitionLabel: string;
  driverIndex: number;
  driverCount: number;
  onClose: () => void;
}) {
  const router = useRouter();
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [version, setVersion] = useState<CommentaryVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  // driverId shape: "advisor|from|to|group|CAUSE|seq"
  const parts = driverId.split("|");
  const fromMonthId = parts[1] ?? "";
  const toMonthId = parts[2] ?? "";
  const groupSegment = parts[3] ?? "";
  const causeSegment = parts[4] ?? "";
  const groupLabel = humanizeGroup(groupSegment);

  // Focus management: remember the trigger, refocus it on unmount. Esc closes.
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      trigger?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.allSettled([v2Api.evidence(driverId, versionId), v2Api.versions()]).then(
      ([ev, vs]) => {
        if (!active) return;
        if (ev.status === "fulfilled") {
          const record = ev.value.evidence[0] ?? null;
          if (record) setEvidence(record);
          else setError("No evidence record exists for this driver in this version.");
        } else {
          setError(ev.reason instanceof Error ? ev.reason.message : "Failed to load evidence.");
        }
        if (vs.status === "fulfilled") {
          setVersion(vs.value.versions.find((v) => v.version_id === versionId) ?? null);
        }
        setLoading(false);
      },
    );
    return () => {
      active = false;
    };
  }, [driverId, versionId, retryKey]);

  const calc = useMemo(
    () => parseJson<CalcJson>(evidence?.calc_json, { components: [], formula: "" }),
    [evidence],
  );
  const sourceRecords = useMemo(
    () =>
      parseJson<SourceRecordsJson>(evidence?.source_records_json, {
        sample: [],
        total_contributing: 0,
        from_month_count: 0,
        to_month_count: 0,
      }),
    [evidence],
  );
  const lineage = useMemo(() => parseJson<LineageStep[]>(evidence?.lineage_json, []), [evidence]);
  const checks = useMemo(() => parseJson<CheckRow[]>(evidence?.checks_json, []), [evidence]);
  const gsqlParams = useMemo(
    () => parseJson<Record<string, unknown>>(evidence?.gsql_params_json, {}),
    [evidence],
  );
  const gsqlResult = useMemo(
    () => parseJson<Record<string, unknown>>(evidence?.gsql_result_json, {}),
    [evidence],
  );

  // Component units (R2-1): the backend stamps each component with a unit and
  // the formatter switches on it. Only `currency` components may be summed.
  // The label heuristic remains as a fallback for evidence stored before units.
  const unitOf = (c: CalcComponent): string => {
    if (c.unit) return c.unit;
    if (/count|rows|accounts/i.test(c.label)) return "count";
    if (/bps|rate/i.test(c.label)) return "bps";
    if (/days/i.test(c.label)) return "days";
    if (/pct|percent/i.test(c.label)) return "percent";
    return "currency";
  };
  const fmtUnit = (value: number, unit: string): string => {
    switch (unit) {
      case "count":
        return Math.round(value).toLocaleString("en-US");
      case "percent":
        return `${value.toFixed(1)}%`;
      case "bps":
        return `${value.toFixed(1)} bps`;
      case "days":
        return `${Math.round(value)} days`;
      default:
        return fmtMoney(value);
    }
  };
  const dollarComponents = calc.components.filter((c) => unitOf(c) === "currency");
  const netChange = dollarComponents.reduce((sum, c) => sum + (c.change ?? 0), 0);
  const gsqlCall = evidence ? gsqlCallText(evidence.gsql_query_name, gsqlParams) : "";
  const resultText = evidence ? JSON.stringify(gsqlResult) : "";

  const openInTransactions = () => {
    onClose();
    const group = groupSegment === "__TOTAL__" ? "" : groupSegment;
    router.push(
      `/transactions?advisor=${encodeURIComponent(advisorId)}&month=${encodeURIComponent(toMonthId)}&group=${encodeURIComponent(group)}`,
    );
  };

  const fromLabel = fromMonthId ? monthShort(fromMonthId) : "From";
  const toLabel = toMonthId ? monthShort(toMonthId) : "To";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-8"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Evidence — ${groupLabel}`}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-[1120px] overflow-y-auto rounded-[3px] bg-white font-v2 text-v2-text shadow-2xl outline-none"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-v2-border bg-white px-6 py-4">
          <div>
            <h2 className="text-[16px] font-semibold">
              Evidence — {groupLabel}
              {evidence && calc.components.length > 0 ? ` (${fmtMoney(netChange)})` : ""}
            </h2>
            <p className="mt-0.5 text-[11.5px] text-v2-muted">
              {transitionLabel} · Advisor {advisorId}
              {advisorName ? ` · ${advisorName}` : ""} · Driver {driverIndex} of {driverCount}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {evidence && <ProvenanceBadge value={evidence.data_source} />}
            {causeSegment && <CauseTag causeId={causeSegment} />}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close evidence"
              className="ml-1 flex h-7 w-7 items-center justify-center rounded-[3px] text-[16px] text-v2-muted hover:bg-v2-header-bg hover:text-v2-text"
            >
              ×
            </button>
          </div>
        </div>

        <div className="px-6 py-5">
          <AsyncBoundary
            loading={loading}
            error={error}
            onRetry={() => setRetryKey((k) => k + 1)}
            loadingLabel="Loading evidence…"
          >
            {evidence && (
              <div className="space-y-7">
                {/* 1 — Finding */}
                <section>
                  <SectionHeader n={1} title="Finding" />
                  <div className="rounded-[3px] border border-v2-border bg-v2-sub-bg px-4 py-3 text-[12px] leading-relaxed">
                    {evidence.finding_text}
                  </div>
                </section>

                {/* 2 — Calculation */}
                <section>
                  <SectionHeader n={2} title="Calculation" />
                  <p className="mb-2 text-[11.5px] text-v2-muted">
                    Each component is aggregated directly from transaction records in the graph.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-[11.5px]">
                      <thead>
                        <tr className="bg-v2-header-bg text-left">
                          <th className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.5px]">Component</th>
                          <th className="px-3 py-1.5 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">{fromLabel}</th>
                          <th className="px-3 py-1.5 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">{toLabel}</th>
                          <th className="px-3 py-1.5 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">Change</th>
                          <th className="px-3 py-1.5 text-right text-[10px] font-semibold uppercase tracking-[0.5px]">Share of MoM</th>
                        </tr>
                      </thead>
                      <tbody>
                        {calc.components.map((c) => (
                          <tr key={c.label} className="border-b border-v2-border-subtle">
                            <td className="px-3 py-1.5">{c.label}</td>
                            <td className="px-3 py-1.5 text-right">{fmtUnit(c.from, unitOf(c))}</td>
                            <td className="px-3 py-1.5 text-right">{fmtUnit(c.to, unitOf(c))}</td>
                            <td
                              className={`px-3 py-1.5 text-right ${
                                c.change < 0 ? "text-v2-negative" : c.change > 0 ? "text-v2-positive" : "text-v2-faint"
                              }`}
                            >
                              {fmtUnit(c.change, unitOf(c))}
                            </td>
                            <td className="px-3 py-1.5 text-right">
                              {unitOf(c) === "currency" ? `${c.share_of_mom}%` : "—"}
                            </td>
                          </tr>
                        ))}
                        <tr className="bg-v2-total-bg font-semibold">
                          <td className="px-3 py-1.5">{groupLabel} — net change</td>
                          <td className="px-3 py-1.5 text-right">
                            {fmtMoney(dollarComponents.reduce((s, c) => s + (c.from ?? 0), 0))}
                          </td>
                          <td className="px-3 py-1.5 text-right">
                            {fmtMoney(dollarComponents.reduce((s, c) => s + (c.to ?? 0), 0))}
                          </td>
                          <td
                            className={`px-3 py-1.5 text-right ${
                              netChange < 0 ? "text-v2-negative" : netChange > 0 ? "text-v2-positive" : "text-v2-faint"
                            }`}
                          >
                            {fmtMoney(netChange)}
                          </td>
                          <td className="px-3 py-1.5 text-right">
                            {dollarComponents.reduce((s, c) => s + (c.share_of_mom ?? 0), 0).toFixed(1)}%
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  {calc.formula && (
                    <div className="mt-3 rounded-[3px] border border-v2-border border-l-2 border-l-v2-warn bg-v2-warn-bg px-4 py-2.5 text-[11.5px] text-v2-text">
                      {calc.formula}
                    </div>
                  )}
                </section>

                {/* 3 — Source records */}
                <section>
                  <SectionHeader n={3} title="Source records" />
                  <p className="mb-2 text-[11.5px] text-v2-muted">
                    The underlying transactions — open the full list to inspect every row.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-[11.5px]">
                      <thead>
                        <tr className="bg-v2-header-bg text-left">
                          {["Trade ref", "Date", "Product", "Account", "Type", "Credited", "Split"].map((h, i) => (
                            <th
                              key={h}
                              className={`px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.5px] ${i >= 5 ? "text-right" : ""}`}
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sourceRecords.sample.map((r) => (
                          <tr key={r.trade_ref} className="border-b border-v2-border-subtle">
                            <td className="px-3 py-1.5 font-mono text-[11px] text-v2-link">{r.trade_ref}</td>
                            <td className="px-3 py-1.5">{fmtDate(r.date)}</td>
                            <td className="px-3 py-1.5">{r.product}</td>
                            <td className="px-3 py-1.5 font-mono text-[11px]">{r.account}</td>
                            <td className="px-3 py-1.5">{r.type}</td>
                            <td className={`px-3 py-1.5 text-right ${r.credited < 0 ? "text-v2-negative" : ""}`}>
                              {fmtMoney(r.credited)}
                            </td>
                            <td className="px-3 py-1.5 text-right">{Math.round((r.split_pct ?? 0) * 100)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-[10.5px] italic text-v2-faint">
                      Showing {sourceRecords.sample.length} of {sourceRecords.total_contributing} contributing transactions
                    </span>
                    <button
                      type="button"
                      onClick={openInTransactions}
                      className="text-[11.5px] font-semibold text-v2-link hover:underline"
                    >
                      Open all {sourceRecords.total_contributing} in Transactions ›
                    </button>
                  </div>
                </section>

                {/* 4 — Data lineage and integrity checks */}
                <section>
                  <SectionHeader n={4} title="Data lineage and integrity checks" />
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className="rounded-[3px] border border-v2-border px-4 py-3">
                      <h4 className="mb-2.5 text-[12px] font-semibold">Graph path traversed</h4>
                      <ol className="ml-1.5 border-l border-v2-border pl-4">
                        {lineage.map((step, i) => (
                          <li key={`${step.vertex}-${i}`} className="relative pb-3 last:pb-0">
                            <span className="absolute -left-[21.5px] top-1 h-2 w-2 rounded-full bg-v2-purple" />
                            <span className="font-semibold text-v2-purple">{step.vertex}</span>
                            <span className="ml-3 text-[11px] text-v2-muted">
                              {typeof step.matches === "number"
                                ? `${step.matches} records matched`
                                : step.matches}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                    <div className="rounded-[3px] border border-v2-border px-4 py-3">
                      <h4 className="mb-2.5 text-[12px] font-semibold">Automated checks</h4>
                      <ul className="space-y-2">
                        {checks.map((c, i) => (
                          <li key={`${c.check}-${i}`} className="flex items-start gap-2 text-[11.5px]">
                            <span className={`mt-px font-semibold ${c.passed ? "text-v2-positive" : "text-v2-negative"}`}>
                              {c.passed ? "✓" : "✗"}
                            </span>
                            <span className="flex-1">{c.check}</span>
                            <span className="text-right text-[11px] text-v2-muted">{c.detail}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </section>

                {/* 5 — Reproduce this result */}
                <section>
                  <SectionHeader n={5} title="Reproduce this result" />
                  <p className="mb-2 text-[11.5px] text-v2-muted">
                    Run the same query we ran. It returns the figures above, unchanged.
                  </p>
                  <div className="relative rounded-[3px] bg-v2-navy-ink px-4 py-3">
                    <CopyButton text={gsqlCall} className="absolute right-3 top-3" />
                    <pre className="overflow-x-auto whitespace-pre font-mono text-[12px] leading-relaxed text-emerald-100">
                      {gsqlCall}
                    </pre>
                  </div>
                  <div className="mt-2 flex items-start gap-3">
                    <span className="pt-1.5 text-[10.5px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                      Returned
                    </span>
                    <pre className="flex-1 overflow-x-auto rounded-[3px] bg-v2-positive-bg px-3 py-1.5 font-mono text-[11.5px] text-v2-text">
                      {resultText}
                    </pre>
                  </div>
                  <p className="mb-2 mt-4 text-[11.5px] text-v2-muted">
                    Source extraction (PostgreSQL) — shown for lineage; not executed by this application.
                  </p>
                  <div className="relative rounded-[3px] bg-v2-navy-ink px-4 py-3">
                    <CopyButton text={evidence.source_sql} className="absolute right-3 top-3" />
                    <pre className="overflow-x-auto whitespace-pre font-mono text-[12px] leading-relaxed text-white">
                      {evidence.source_sql}
                    </pre>
                  </div>
                  <p className="mt-1.5 text-[10.5px] text-v2-faint">
                    source_table: {evidence.source_table} · source_row_count: {evidence.source_row_count}
                  </p>
                </section>
              </div>
            )}
          </AsyncBoundary>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 flex items-center justify-between border-t border-v2-border bg-white px-6 py-3">
          <span className="text-[10.5px] text-v2-faint">
            {version
              ? `Commentary v${version.version_no} · model ${version.model} · prompt v${version.prompt_version} · generated ${fmtDate(version.generated_at)} · data snapshot ${fmtDate(version.data_snapshot_dt)}`
              : `Commentary ${versionId}`}
            {evidence ? ` · query ${evidence.gsql_query_name}` : ""}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[3px] bg-v2-navy px-5 py-1.5 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
