"use client";
/**
 * Anomalies — /anomalies (FIX_SPEC_R6 Y7, mockup
 * docs/ui/reference/roadmap/02_anomaly_detection.png).
 *
 * The screen RETRIEVES stored anomalies (GQ-018/019) — detection is batch-only
 * (the Re-scan button / POST /api/v2/anomalies/scan / CLI); a page load never
 * detects. Rules are deterministic Python over computed drivers; only the
 * WORDING is AI (marked with the AI Generated chip). Every card carries the
 * computed impact figure and links to the existing evidence / transactions
 * screens. Scans are additive: the scan selector reaches every prior scan.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useV2Context } from "@/components/layout/v2-shell";
import { AsyncBoundary } from "@/components/patterns/async-state";
import { AiGeneratedChip } from "@/components/patterns/ai-generated-chip";
import { JobProgressOverlay, useAsyncJob } from "@/components/patterns/job-progress";
import { type AnomaliesResponse, type AnomalyRow, type AnomalyScan, v2Api } from "@/lib/api/v2";
import { fmtMoney, monthShort } from "@/lib/v2/format";
import { useDriverCauses } from "@/lib/v2/driver-causes";

const SEVERITY_STYLE: Record<AnomalyRow["severity"], { rail: string; pill: string }> = {
  HIGH: { rail: "bg-v2-negative", pill: "bg-v2-negative-bg text-v2-negative" },
  MEDIUM: { rail: "bg-v2-warn", pill: "bg-v2-warn-bg text-v2-warn" },
  LOW: { rail: "bg-v2-navy", pill: "bg-v2-header-bg text-v2-navy" },
  INFO: { rail: "bg-v2-border-strong", pill: "bg-v2-header-bg text-v2-muted" },
};

const RULE_TAG: Record<string, string> = {
  UNEXPLAINED_RESIDUAL: "UNEXPLAINED",
  CLAWBACK_CONCENTRATION: "CLAWBACK",
  LARGE_SWING: "LARGE SWING",
  FEE_RATE_SHIFT: "FEE RATE",
  SINGLE_DRIVER_DOMINANCE: "DOMINANCE",
  BASELINE_LIMITED_PRESENT: "BASELINE",
};

// Threshold display: config key -> human phrasing (values interpolated live).
// FIX_SPEC_R8 A3/A5 — phrases that name a driver resolve its display_name
// from GQ-004 via the passed resolver; driver names are never hardcoded.
const THRESHOLD_LABELS: [string, (v: number, name: (causeId: string) => string) => string][] = [
  ["ANOMALY_UNEXPLAINED_RESIDUAL_PCT", (v, name) => `Unexplained residual: ${name("MIX")} above ${(v * 100).toFixed(0)}% of the change`],
  ["ANOMALY_CLAWBACK_MULTIPLE", (v, name) => `${name("CLAWBACK")} concentration: over ${v}× the trailing mean`],
  ["ANOMALY_CLAWBACK_MIN_USD", (v) => `… with a floor of ${fmtMoney(v)}`],
  ["ANOMALY_LARGE_SWING_PCT", (v) => `Large swing: beyond ${v}%`],
  ["ANOMALY_LARGE_SWING_MIN_USD", (v) => `… and beyond ${fmtMoney(v)}`],
  ["ANOMALY_FEE_RATE_SHIFT_BPS", (v, name) => `${name("FEE_RATE")} shift: more than ${v} bps on a recurring group`],
  ["ANOMALY_SINGLE_DRIVER_DOMINANCE_PCT", (v) => `Single-driver dominance: above ${v}% of the change`],
];

function actionFor(a: AnomalyRow): { label: string; href: string } {
  if (a.rule_id === "CLAWBACK_CONCENTRATION") {
    return { label: "View transactions ›", href: "/transactions" };
  }
  return { label: "Open evidence ›", href: "/ai-insights" };
}

export default function AnomaliesPage() {
  const { advisors, advisorId, advisor, loaded, reportTier } = useV2Context();

  const [data, setData] = useState<AnomaliesResponse | null>(null);
  const [scans, setScans] = useState<AnomalyScan[]>([]);
  const [selectedScan, setSelectedScan] = useState(""); // "" = latest for this advisor
  const [transition, setTransition] = useState(""); // "" = all, else "from|to"
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  // R11 B2 — the screen is scoped to the advisor selected in the context bar:
  // anomalies AND the scan selector show that advisor's history (plus legacy
  // global scans). Advisor switch resets to "latest for this advisor".
  useEffect(() => { setSelectedScan(""); setTransition(""); }, [advisorId]);

  useEffect(() => {
    if (!loaded || !advisorId) return;
    let active = true;
    setError(null);
    Promise.all([v2Api.anomalies(advisorId, selectedScan), v2Api.anomalyScans(advisorId)])
      .then(([a, s]) => {
        if (!active) return;
        setData(a);
        setScans(s.scans);
        reportTier(a.served_by_tier);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : "Failed to load anomalies.");
      });
    return () => { active = false; };
  }, [loaded, advisorId, selectedScan, fetchKey, reportTier]);

  // R11 C — async Rescan with a progress overlay; on completion the page
  // refreshes to the new latest scan automatically (no manual reload).
  const job = useAsyncJob(
    v2Api.anomalyScanStatus,
    useCallback(() => {
      setSelectedScan(""); // jump to the new latest scan
      setFetchKey((k) => k + 1);
    }, []),
  );
  const rescanThis = useCallback(() => {
    if (advisorId) job.start(() => v2Api.anomalyScan(advisorId));
  }, [advisorId, job]);
  const rescanAll = useCallback(() => {
    job.start(() => v2Api.anomalyScan(""));
  }, [job]);
  const busy = job.running;

  const advisorName = useCallback(
    (sid: string) => advisors.find((a) => a.advisor_sid === sid)?.advisor_name || sid,
    [advisors],
  );

  const transitions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const a of data?.anomalies ?? []) {
      const key = `${a.from_month_id}|${a.to_month_id}`;
      seen.set(key, `${monthShort(a.from_month_id)} → ${monthShort(a.to_month_id)}`);
    }
    return [...seen.entries()].sort();
  }, [data]);

  const rows = useMemo(
    () => (data?.anomalies ?? []).filter(
      (a) => !transition || `${a.from_month_id}|${a.to_month_id}` === transition),
    [data, transition],
  );

  const scan = data?.scan;
  const unexplained = (data?.anomalies ?? []).filter((a) => a.rule_id === "UNEXPLAINED_RESIDUAL").length;
  const { name: causeName } = useDriverCauses();
  const thresholdLines = THRESHOLD_LABELS
    .filter(([k]) => data?.thresholds_in_force?.[k] != null)
    .map(([k, f]) => f(data!.thresholds_in_force[k], causeName));
  const selectCls = "h-7 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]";

  const stat = (label: string, value: number | string, accent = "") => (
    <div className="rounded-[4px] border border-v2-border bg-white px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">{label}</div>
      <div className={`mt-1 text-[22px] font-bold tabular-nums ${accent || "text-v2-text"}`}>{value}</div>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* header — what was reviewed, transition selector, Re-scan, scan selector */}
      <div className="rounded-[4px] border border-v2-border bg-white px-4 py-3.5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-[17px] font-bold text-v2-text">Revenue Anomalies</h1>
            <p className="mt-0.5 text-[12px] text-v2-muted">
              {scan?.scan_id
                ? `Scan ${scan.scan_id} · ${scan.advisor_sid ? `advisor ${advisorName(String(scan.advisor_sid))}` : `${scan.advisors_reviewed} advisors (legacy all-advisor scan)`} · ${scan.transitions_reviewed} month-over-month transitions reviewed · ${scan.flagged_count} flagged. Showing ${advisor?.advisor_name || advisorId}.`
                : "No scan has been run yet for this advisor — use Rescan to run the first one."}
            </p>
          </div>
          <select
            aria-label="Transition"
            className={selectCls}
            value={transition}
            onChange={(e) => setTransition(e.target.value)}
          >
            <option value="">All transitions</option>
            {transitions.map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <select
            aria-label="Scan version"
            className={selectCls}
            value={selectedScan}
            onChange={(e) => setSelectedScan(e.target.value)}
          >
            <option value="">Latest scan (this advisor)</option>
            {scans.map((s) => (
              <option key={s.scan_id} value={s.scan_id}>
                {s.scan_id} · {s.advisor_sid || "all advisors (legacy)"} · {s.started_at?.slice(0, 10)} · {s.flagged_count} flagged
              </option>
            ))}
          </select>
          {/* R11 B3 — TWO buttons, scope always explicit: the old single
              "Re-scan" silently ran ALL advisors. */}
          <button
            type="button"
            onClick={rescanThis}
            disabled={busy}
            title={`Scan ${advisor?.advisor_name || advisorId} only — other advisors keep their current scans`}
            className="flex h-7 items-center gap-1.5 rounded-[3px] bg-v2-navy px-3 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:opacity-60"
          >
            ⟳ {busy ? "Scanning…" : "Rescan (this advisor)"}
          </button>
          <button
            type="button"
            onClick={rescanAll}
            disabled={busy}
            title="Scan every advisor — each advisor gets its own new scan (use after a fresh data load)"
            className="h-7 rounded-[3px] border border-v2-navy bg-white px-2.5 text-[11.5px] font-semibold text-v2-navy hover:bg-v2-sub-bg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:border-v2-border disabled:text-v2-faint"
          >
            Rescan all
          </button>
        </div>
      </div>

      <AsyncBoundary loading={!data && !error} error={!data ? error : null}
        onRetry={() => setFetchKey((k) => k + 1)} loadingLabel="Loading anomalies…">
        {/* stat cards */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {stat("Advisors reviewed", scan?.advisors_reviewed ?? 0)}
          {stat("Transitions", scan?.transitions_reviewed ?? 0)}
          {stat("Flagged", scan?.flagged_count ?? 0, "text-v2-warn")}
          {stat("Unexplained (MIX>threshold)", unexplained, unexplained ? "text-v2-negative" : "")}
        </div>

        {/* severity-ordered cards */}
        {rows.length === 0 ? (
          <div className="rounded-[4px] border border-v2-border bg-white px-5 py-6">
            <div className="text-[13px] font-semibold text-v2-text">
              No anomalies above the current thresholds
              {transition ? " for this transition" : ""}.
            </div>
            <div className="mt-2 text-[11.5px] text-v2-muted">
              Thresholds in force:
              <ul className="mt-1 list-disc pl-5">
                {thresholdLines.map((line) => <li key={line}>{line}</li>)}
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {rows.map((a) => {
              const style = SEVERITY_STYLE[a.severity] ?? SEVERITY_STYLE.INFO;
              const metrics = safeParse(a.metrics_json);
              const aiWorded = metrics?.ai_generated !== false;
              const action = actionFor(a);
              const negative = a.impact_amt < 0;
              return (
                <div key={a.anomaly_id}
                  className="relative overflow-hidden rounded-[4px] border border-v2-border bg-white">
                  <span aria-hidden className={`absolute inset-y-0 left-0 w-1 ${style.rail}`} />
                  <div className="flex flex-wrap items-start gap-3 py-3.5 pl-5 pr-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-[0.4px] ${style.pill}`}>
                          {a.severity}
                        </span>
                        <span className="text-[13.5px] font-bold text-v2-text">{a.title}</span>
                        <span className="rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.4px] text-v2-muted">
                          {RULE_TAG[a.rule_id] ?? a.rule_id}
                        </span>
                        {aiWorded && <AiGeneratedChip model={String(metrics?.wording_model ?? "")} />}
                      </div>
                      <div className="mt-1 text-[11px] text-v2-muted">
                        {a.advisor_sid} · {advisorName(a.advisor_sid)} · {monthShort(a.from_month_id)} → {monthShort(a.to_month_id)}
                        {a.group_id ? ` · ${a.group_id.replace(/_/g, " ")}` : ""}
                      </div>
                      <p className="mt-1.5 max-w-[900px] text-[12px] leading-5 text-v2-text">
                        {a.detail_text}
                        {!aiWorded && (
                          <span className="ml-1.5 text-[10.5px] text-v2-muted">
                            (deterministic wording — the AI phrasing failed validation)
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <div>
                        <div className={`text-right text-[16px] font-bold tabular-nums ${negative ? "text-v2-negative" : "text-v2-positive"}`}>
                          {fmtMoney(a.impact_amt)}
                        </div>
                        <div className="text-right text-[10px] uppercase tracking-[0.4px] text-v2-muted">impact</div>
                      </div>
                      <Link href={action.href}
                        className="rounded-[3px] border border-v2-border px-2.5 py-1 text-[11px] font-semibold text-v2-navy hover:bg-v2-header-bg">
                        {action.label}
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* boundary + thresholds note */}
        <div className="space-y-1 px-1 text-[10.5px] italic text-v2-muted">
          <p>
            Anomalies are detected by deterministic rules over computed drivers. The wording is
            AI-generated (marked); every figure is computed and validated against the stored
            metrics before publication.
          </p>
          <p>
            Thresholds are configurable (ANOMALY_* settings). In force for this scan:{" "}
            {thresholdLines.join(" · ") || "—"}.
          </p>
        </div>
      </AsyncBoundary>

      {/* R11 C2 — non-blocking progress overlay for the async Rescan. */}
      <JobProgressOverlay
        job={job}
        title="Scanning for anomalies"
        doneLabel="Scan complete — showing the latest scan"
      />
    </div>
  );
}

function safeParse(json: string): Record<string, unknown> | null {
  try {
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}
