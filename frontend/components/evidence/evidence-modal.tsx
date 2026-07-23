"use client";
/**
 * Evidence modal (UI_SPEC §6, reference 04_evidence_popup.png).
 * Answers "how do we know this is right?" — five numbered sections:
 * Finding · Calculation · Source records · Lineage & checks · Reproduce.
 * Every figure shown is retrieved from the stored evidence record (GQ-012
 * consumer); nothing is computed or generated here.
 */
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  type CommentaryEvaluation,
  type CommentaryVersion,
  type DriverRow,
  type EvidenceRecord,
  type RevenueChangeRow,
  v2Api,
} from "@/lib/api/v2";
import { fmtDate, fmtMoney, monthShort } from "@/lib/v2/format";
import {
  AI_BOUNDARY_TEXT,
  AiGeneratedChip,
  JudgeVerdictPill,
} from "@/components/patterns/ai-generated-chip";
import { AsyncBoundary } from "@/components/patterns/async-state";
import { CauseTag, ProvenanceBadge } from "@/components/patterns/provenance-badge";
import { GlossaryLink } from "@/components/patterns/revenue-driver-glossary";

interface CalcComponent {
  label: string;
  unit?: string; // currency | count | percent | bps | days (R2-1)
  from: number;
  to: number;
  change: number;
  share_of_mom: number;
}
// R4 — deepened evidence blocks. All optional: evidence stored before round 2
// lacks them, and each panel renders only when present.
interface WhyJson {
  rule: string;
  inputs_tested: string[];
  rejected: { cause: string; reason: string }[];
}
interface AttributionJson {
  step: number;
  total_steps: number;
  order: string[];
  earlier_claims: { cause: string; amount: number }[];
}
interface WaterfallJson {
  from_revenue: number;
  steps: { label: string; amount: number }[];
  to_revenue: number;
}
interface RevNatureJson {
  rule: string;
  values: { file_key: string; trade_description: string; rev_nature: string; count: number }[];
}
interface CreditedMonthRow {
  month_id: string;
  total_revenue: number;
  non_credited: number;
  non_credited_detail: { reason_code: string; ui_mapping: string; count: number; amount: number }[];
  excluded: number;
  late_excluded: number;
  credited: number;
}
interface CalcJson {
  components: CalcComponent[];
  formula: string;
  why?: WhyJson;
  attribution?: AttributionJson;
  waterfall?: WaterfallJson;
  rev_nature?: RevNatureJson;
  credited_breakdown?: { months: CreditedMonthRow[] };
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

/** T3-1 — versions generated before this one predate the judge (R5) and the
 * deepened evidence panels (R4); their old driver sets were superseded when
 * the sample data was regenerated, so those sections are genuinely
 * unreconstructable. Every affected panel states this instead of rendering
 * blank. (Data-set specific — the first version generated after the round-2
 * evidence deepening.) */
const DEEP_EVIDENCE_FROM_VERSION = 7;

/** S-A2 — the modal is single-scoped to the clicked driver's product group,
 * and the waterfall is rebuilt for that group only. This order mirrors the
 * backend's deterministic waterfall cause order
 * (app/agents/nodes/explainability_agent._WATERFALL_CAUSE_ORDER) so the bars
 * read the same way everywhere. */
const WATERFALL_CAUSE_ORDER = [
  "NEW_ACCOUNT", "LOST_ACCOUNT", "BASELINE_LIMITED", "ONE_TIME", "ELIGIBILITY", "LATE_PROCESSING",
  "EXCLUDED_CHANGE", "CLAWBACK",
  "TIMING", "FEE_RATE", "DISCOUNT", "BILLABLE_DAYS", "VOLUME",
  "MARKET", "NET_FLOW", "MIX",
];
const causeOrder = (cause: string): number => {
  const i = WATERFALL_CAUSE_ORDER.indexOf(cause);
  return i === -1 ? WATERFALL_CAUSE_ORDER.length : i;
};

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

function SectionHeader({ n, title, extra }: { n: number; title: string; extra?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center gap-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-v2-navy text-[11.5px] font-semibold text-white">
        {n}
      </span>
      <h3 className="text-[14px] font-semibold text-v2-text">{title}</h3>
      {extra}
    </div>
  );
}

/** Sub-panel shell used by the R4 evidence-deepening blocks in section 2. */
function SubPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-3 rounded-[3px] border border-v2-border px-4 py-3">
      <h4 className="mb-2 text-[12px] font-semibold text-v2-text">{title}</h4>
      {children}
    </div>
  );
}

/** R4-3 / T3-2 — reconciliation waterfall: from-revenue → each revenue
 * driver's step → to-revenue, summing exactly. Plain-English lead sentence,
 * neutral anchor bars, green/red driver bars, focus highlight tied to the
 * driver currently paged in the modal, a "how to read this" expander and a
 * completeness note. Pure divs, existing tokens only. */
function ReconciliationWaterfall({
  data,
  fromLabel,
  toLabel,
  scopeLabel,
  focusCause,
}: {
  data: WaterfallJson;
  fromLabel: string;
  toLabel: string;
  /** S-A2 — the scope every number in this waterfall belongs to (a product
   * group, or "Total — all product groups"). */
  scopeLabel: string;
  /** cause_id of the driver currently in focus — its bar highlights (T3-2). */
  focusCause?: string;
}) {
  const [showHow, setShowHow] = useState(false);
  let running = data.from_revenue;
  const cols: { label: string; lo: number; hi: number; kind: "anchor" | "up" | "down"; amount: number }[] = [
    { label: "From", lo: 0, hi: data.from_revenue, kind: "anchor", amount: data.from_revenue },
  ];
  for (const s of data.steps) {
    const next = running + s.amount;
    cols.push({
      label: s.label,
      lo: Math.min(running, next),
      hi: Math.max(running, next),
      kind: s.amount >= 0 ? "up" : "down",
      amount: s.amount,
    });
    running = next;
  }
  cols.push({ label: "To", lo: 0, hi: data.to_revenue, kind: "anchor", amount: data.to_revenue });

  const min = Math.min(0, ...cols.map((c) => c.lo));
  const max = Math.max(0, ...cols.map((c) => c.hi));
  const range = max - min || 1;
  const CHART_H = 110; // px — the whole visual stays well under 200px tall
  const y = (v: number) => ((max - v) / range) * CHART_H;

  const stepSum = data.steps.reduce((s, x) => s + x.amount, 0);
  const reconciles = Math.abs(data.from_revenue + stepSum - data.to_revenue) < 0.01;

  const barCls = (kind: "anchor" | "up" | "down") =>
    kind === "anchor" ? "bg-v2-navy" : kind === "up" ? "bg-v2-positive" : "bg-v2-negative";
  const amtCls = (kind: "anchor" | "up" | "down") =>
    kind === "anchor" ? "text-v2-text" : kind === "up" ? "text-v2-positive" : "text-v2-negative";

  return (
    <div>
      {/* T3-2 — plain-English lead sentence. */}
      <p className="mb-2 text-[11.5px] leading-relaxed text-v2-text">
        This shows how {scopeLabel}&apos;s credited revenue of {fmtMoney(data.from_revenue)} in{" "}
        {fromLabel} became {fmtMoney(data.to_revenue)} in {toLabel}. Each bar is one revenue
        driver&apos;s contribution within {scopeLabel}; because every dollar of change is
        attributed, the bars sum exactly to {scopeLabel}&apos;s change.
      </p>
      <div className="overflow-x-auto">
        <div className="flex items-stretch gap-2" style={{ minWidth: cols.length * 96 }}>
          {cols.map((c, i) => {
            const focused = c.kind !== "anchor" && !!focusCause && c.label === focusCause;
            return (
              <div
                key={`${c.label}-${i}`}
                className={`flex w-24 shrink-0 flex-col rounded-[3px] px-0.5 pt-0.5 ${
                  focused ? "bg-v2-header-bg ring-1 ring-v2-navy" : ""
                }`}
              >
                <span className={`num mb-0.5 text-[10px] font-semibold ${amtCls(c.kind)}`}>
                  {fmtMoney(c.amount)}
                </span>
                <div className="relative rounded-[2px] bg-v2-sub-bg" style={{ height: CHART_H }}>
                  <div
                    className={`absolute left-1 right-1 rounded-[2px] ${barCls(c.kind)} ${
                      focusCause && !focused && c.kind !== "anchor" ? "opacity-45" : ""
                    }`}
                    style={{ top: y(c.hi), height: Math.max(2, y(c.lo) - y(c.hi)) }}
                  />
                </div>
                <span
                  className={`mt-1 truncate text-[9.5px] uppercase tracking-[0.3px] ${
                    focused ? "font-semibold text-v2-navy" : "text-v2-muted"
                  }`}
                  title={c.label}
                >
                  {c.label.replace(/_/g, "-")}
                  {focused ? " ◂" : ""}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-2 text-[11px] text-v2-muted">
        {fmtMoney(data.from_revenue)} + {fmtMoney(stepSum)} = {fmtMoney(data.to_revenue)}{" "}
        {reconciles ? (
          <span className="font-semibold text-v2-positive">✓ sums exactly — nothing missing, nothing double-counted</span>
        ) : (
          <span className="font-semibold text-v2-negative">✗ does not reconcile</span>
        )}
      </p>
      {/* T3-2 — how to read + completeness note (the honesty self-check). */}
      <button
        type="button"
        onClick={() => setShowHow((s) => !s)}
        aria-expanded={showHow}
        className="mt-1.5 text-[11px] font-semibold text-v2-link hover:underline"
      >
        {showHow ? "▾ How to read this" : "▸ How to read this"}
      </button>
      {showHow && (
        <p className="mt-1 rounded-[3px] bg-v2-sub-bg px-3 py-2 text-[11px] leading-relaxed text-v2-muted">
          Start at the left bar ({scopeLabel}&apos;s credited revenue in {fromLabel}) and walk
          right: each green bar adds revenue, each red bar removes it, and the highlighted bar is
          the driver you are reading now. The right bar is {scopeLabel}&apos;s credited revenue in{" "}
          {toLabel} — the walk always lands exactly on it.
        </p>
      )}
      <p className="mt-1.5 text-[10.5px] italic text-v2-faint">
        The bars reconcile to $0.00, confirming every dollar of change is accounted for. A large
        unexplained (MIX) bar would indicate a missing driver.
      </p>
    </div>
  );
}

/** R4-5 ledger amount: two decimals, zero shown as $0.00, negatives in parentheses. */
function ledgerAmt(value: number): string {
  if (value === 0) return "$0.00";
  return fmtMoney(value, 2);
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
  versionId,
  advisorId,
  advisorName,
  fromMonthId,
  toMonthId,
  transitionLabel,
  initialDriverId,
  onClose,
}: {
  versionId: string;
  advisorId: string;
  advisorName: string;
  fromMonthId: string;
  toMonthId: string;
  transitionLabel: string;
  /** Open at this driver of the transition; defaults to the top-ranked one. */
  initialDriverId?: string;
  onClose: () => void;
}) {
  const router = useRouter();
  // S-A2/S-A3 — ONE scope per modal: the clicked driver's product group.
  // `drivers` holds that GROUP's ordered driver set and paging moves through
  // it only; `allDrivers` keeps the whole transition (needed to rebuild the
  // waterfall when the scope group is __TOTAL__). Evidence stays lazy-loaded
  // per driver (T2-1/T2-3).
  const [drivers, setDrivers] = useState<DriverRow[] | null>(null);
  const [allDrivers, setAllDrivers] = useState<DriverRow[]>([]);
  const [scopeGroupId, setScopeGroupId] = useState("");
  const [changes, setChanges] = useState<RevenueChangeRow[]>([]);
  const [index, setIndex] = useState(0);
  const [evidenceByDriver, setEvidenceByDriver] = useState<
    Record<string, { record: EvidenceRecord | null; error: string | null }>
  >({});
  const [version, setVersion] = useState<CommentaryVersion | null>(null);
  // R5-4 — independent LLM-judge review. null until loaded; "missing" is a
  // valid, explicitly-rendered state.
  const [evaluation, setEvaluation] = useState<CommentaryEvaluation | null>(null);
  const [evaluationLoaded, setEvaluationLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  const driver = drivers?.[index] ?? null;
  const driverId = driver?.driver_id ?? initialDriverId ?? "";
  const cached = driverId ? evidenceByDriver[driverId] : undefined;
  const evidence = cached?.record ?? null;
  const evidenceError = cached?.error ?? null;
  const driverCount = drivers?.length ?? 0;

  // driverId shape: "advisor|from|to|group|CAUSE|seq"
  const parts = driverId.split("|");
  const groupSegment = scopeGroupId || driver?.group_id || parts[3] || "";
  const causeSegment = driver?.cause_id ?? parts[4] ?? "";
  const groupLabel = humanizeGroup(groupSegment);
  const isTotalScope = groupSegment === "__TOTAL__";
  const scopeLabel = isTotalScope ? "Total — all product groups" : groupLabel;

  const page = useCallback(
    (delta: number) => {
      setIndex((i) => {
        const n = drivers?.length ?? 0;
        if (!n) return i;
        return Math.min(n - 1, Math.max(0, i + delta));
      });
    },
    [drivers],
  );

  // Focus management: remember the trigger, refocus it on unmount. Esc closes;
  // ←/→ page through the drivers (T2-1).
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") page(-1);
      else if (e.key === "ArrowRight") page(1);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      trigger?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  // T2-3 — load the transition's driver set (GQ-008) + version metadata + the
  // judge evaluation once; evidence (GQ-012) is fetched per driver as the user
  // pages, never all up front.
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setEvaluationLoaded(false);
    Promise.allSettled([
      v2Api.insightsDrivers(advisorId, fromMonthId, toMonthId),
      v2Api.versions(),
      v2Api.evaluations(versionId),
      v2Api.trendsChanges(advisorId, fromMonthId, toMonthId),
    ]).then(([dr, vs, evals, ch]) => {
      if (!active) return;
      if (dr.status === "fulfilled") {
        const list = [...dr.value.drivers].sort((a, b) => a.rank - b.rank);
        if (list.length) {
          setAllDrivers(list);
          // S-A2 — resolve the modal's single scope: the clicked driver's
          // product group (walk entry has no initial driver → the top-ranked
          // driver's group). Everything in the modal holds this scope.
          const initial = initialDriverId
            ? list.find((d) => d.driver_id === initialDriverId)
            : undefined;
          const group =
            initial?.group_id ??
            (initialDriverId ? initialDriverId.split("|")[3] : undefined) ??
            list[0].group_id;
          const groupList = list.filter((d) => d.group_id === group);
          // A superseded initial driver whose group no longer exists falls
          // back to the current top driver's group — never an empty modal.
          const scoped = groupList.length ? groupList : list.filter((d) => d.group_id === list[0].group_id);
          setScopeGroupId(scoped[0]?.group_id ?? group);
          setDrivers(scoped);
          const start = initialDriverId
            ? scoped.findIndex((d) => d.driver_id === initialDriverId)
            : 0;
          setIndex(start >= 0 ? start : 0);
        } else {
          setError("No drivers are stored for this transition.");
        }
      } else {
        setError(dr.reason instanceof Error ? dr.reason.message : "Failed to load the driver set.");
      }
      setChanges(ch.status === "fulfilled" ? ch.value.changes : []);
      if (vs.status === "fulfilled") {
        setVersion(vs.value.versions.find((v) => v.version_id === versionId) ?? null);
      }
      if (evals.status === "fulfilled") {
        // The judge evaluates the transition's commentary, whose id is
        // "<version>|<advisor>|<from>|<to>" — match on that prefix.
        const commentaryId = `${versionId}|${advisorId}|${fromMonthId}|${toMonthId}`;
        setEvaluation(
          evals.value.evaluations.find(
            (e) => e.commentary_id === commentaryId || e.commentary_id.startsWith(`${commentaryId}|`),
          ) ?? null,
        );
      } else {
        setEvaluation(null);
      }
      setEvaluationLoaded(true);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [advisorId, fromMonthId, toMonthId, versionId, initialDriverId, retryKey]);

  // Lazy per-driver evidence fetch, cached for the modal's lifetime.
  useEffect(() => {
    const id = drivers?.[index]?.driver_id;
    if (!id || evidenceByDriver[id]) return;
    let active = true;
    v2Api
      .evidence(id, versionId)
      .then((ev) => {
        if (!active) return;
        const record = ev.evidence[0] ?? null;
        setEvidenceByDriver((m) => ({
          ...m,
          [id]: {
            record,
            error: record ? null : "No evidence record exists for this driver in this version.",
          },
        }));
      })
      .catch((e: unknown) => {
        if (!active) return;
        setEvidenceByDriver((m) => ({
          ...m,
          [id]: { record: null, error: e instanceof Error ? e.message : "Failed to load evidence." },
        }));
      });
    return () => {
      active = false;
    };
  }, [drivers, index, versionId, evidenceByDriver]);

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

  // S-A2 — the waterfall is rebuilt for the modal's scope group from stored
  // rows: FROM/TO come from the group's revenue_change row and each bar is
  // one of the group's revenue drivers. Attribution runs per group with a
  // per-group MIX residual, so the bars sum exactly to the group's change —
  // header, waterfall and credited breakdown now all describe the same
  // group-level change. For the __TOTAL__ scope (MARKET/NET_FLOW attach
  // there) the waterfall is the whole transition — all causes aggregated
  // across groups — and is explicitly labelled as such. Stored rows are only
  // arranged here; nothing is computed beyond ordering and rounding.
  const groupWaterfall = useMemo<WaterfallJson | null>(() => {
    if (!scopeGroupId) return null;
    const changeRow = changes.find((c) => c.group_id === scopeGroupId);
    if (!changeRow) return null;
    let steps: { label: string; amount: number }[];
    if (scopeGroupId === "__TOTAL__") {
      const byCause = new Map<string, number>();
      for (const d of allDrivers) {
        byCause.set(d.cause_id, (byCause.get(d.cause_id) ?? 0) + d.contribution_amt);
      }
      steps = [...byCause.entries()].map(([label, amount]) => ({ label, amount }));
    } else {
      steps = (drivers ?? []).map((d) => ({ label: d.cause_id, amount: d.contribution_amt }));
    }
    steps = steps
      .map((s) => ({ label: s.label, amount: Math.round(s.amount * 100) / 100 }))
      .sort((a, b) => causeOrder(a.label) - causeOrder(b.label));
    return {
      from_revenue: Math.round(changeRow.from_revenue * 100) / 100,
      steps,
      to_revenue: Math.round(changeRow.to_revenue * 100) / 100,
    };
  }, [scopeGroupId, changes, allDrivers, drivers]);

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
        {/* Header — reflects the CURRENT driver and updates as the user pages
            (T2-4). The amount is never re-wrapped in parentheses: the arrow
            carries direction and fmtMoney already parenthesises negatives
            (T3-3 — no double-parenthesis, ever). */}
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-v2-border bg-white px-6 py-4">
          <div>
            <h2 className="text-[16px] font-semibold">
              Evidence — {scopeLabel}
              {driver && (
                <span className={`ml-2 ${driver.contribution_amt < 0 ? "text-v2-negative" : "text-v2-positive"}`}>
                  {driver.contribution_amt < 0 ? "▼" : "▲"} {fmtMoney(driver.contribution_amt)}
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-[11.5px] text-v2-muted">
              {transitionLabel} · Advisor {advisorId}
              {advisorName ? ` · ${advisorName}` : ""}
              {driverCount > 0 ? ` · Revenue Driver ${index + 1} of ${driverCount} in ${groupLabel}` : ""}
            </p>
            {/* S-A3 — the one-line caption relating the card's advisor-wide
                top 5 to this modal's group-scoped walk. */}
            {driverCount > 0 && (
              <p className="mt-0.5 text-[10.5px] text-v2-faint">
                The AI-Insights card ranks the top 5 revenue drivers across all product groups;
                this modal walks all {driverCount} driver{driverCount === 1 ? "" : "s"} within{" "}
                {groupLabel}.
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {(evidence || driver) && (
              <ProvenanceBadge value={evidence?.data_source ?? driver?.data_source ?? ""} />
            )}
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
            loading={loading || (!error && !cached)}
            error={error}
            onRetry={() => setRetryKey((k) => k + 1)}
            loadingLabel="Loading evidence…"
          >
            {/* T3-1 — a version with no evidence for this driver states why
                plainly instead of rendering empty scaffolding. */}
            {!evidence && evidenceError && (
              <div className="rounded-[3px] border border-v2-border bg-v2-sub-bg px-4 py-3 text-[12px] leading-relaxed text-v2-text">
                <p className="font-semibold">Evidence is not available for this driver in {versionId}.</p>
                <p className="mt-1 text-v2-muted">
                  {evidenceError} Driver sets are recomputed when the underlying data changes, so
                  older commentary versions can reference a superseded driver set. Independent
                  review and detailed evidence are available from version {DEEP_EVIDENCE_FROM_VERSION}{" "}
                  onward — select the latest version for the full evidence record.
                </p>
              </div>
            )}
            {evidence && (
              <div className="space-y-7">
                {/* 1 — Finding */}
                <section>
                  <SectionHeader
                    n={1}
                    title="Finding"
                    extra={
                      <AiGeneratedChip
                        model={version?.model}
                        promptVersion={version?.prompt_version}
                        versionId={versionId}
                      />
                    }
                  />
                  <div className="rounded-[3px] border border-v2-border bg-v2-sub-bg px-4 py-3 text-[12px] leading-relaxed">
                    {evidence.finding_text}
                  </div>
                  <p className="mt-1.5 text-[10.5px] text-v2-faint">{AI_BOUNDARY_TEXT}</p>

                  {/* R5-4 — Independent review (LLM-as-judge, advisory) */}
                  {evaluationLoaded && (
                    <div className="mt-3 rounded-[3px] border border-v2-border px-4 py-3">
                      {evaluation ? (
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-[11px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                              Independent review
                            </span>
                            <JudgeVerdictPill verdict={evaluation.verdict} />
                            <span className="text-[11px] text-v2-muted">
                              Faithfulness {evaluation.faithfulness_score.toFixed(2)} · Judge{" "}
                              {evaluation.judge_model}
                            </span>
                            <AiGeneratedChip
                              model={evaluation.judge_model}
                              promptVersion={version?.prompt_version}
                              versionId={versionId}
                            />
                          </div>
                          <p className="mt-1.5 text-[11.5px] leading-relaxed text-v2-text">
                            {evaluation.reasoning}
                          </p>
                          <p className="mt-1 text-[10.5px] text-v2-faint">
                            Advisory only — deterministic guardrails remain the blocking gate for publication.
                          </p>
                        </div>
                      ) : (
                        <p className="text-[11.5px] text-v2-muted">
                          No independent review is recorded for this version — independent review and
                          detailed evidence are available from version {DEEP_EVIDENCE_FROM_VERSION} onward.
                        </p>
                      )}
                    </div>
                  )}
                </section>

                {/* 2 — Calculation */}
                <section>
                  <SectionHeader n={2} title="Calculation" extra={<GlossaryLink />} />
                  <p className="mb-2 text-[11.5px] text-v2-muted">
                    Each component is aggregated directly from transaction records in the graph.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-[11.5px]">
                      <thead>
                        <tr className="bg-v2-header-bg text-left">
                          <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Component</th>
                          <th className="num px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">{fromLabel}</th>
                          <th className="num px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">{toLabel}</th>
                          <th className="num px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Change</th>
                          <th className="num px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Share of MoM</th>
                        </tr>
                      </thead>
                      <tbody>
                        {calc.components.map((c) => (
                          <tr key={c.label} className="border-b border-v2-border-subtle">
                            <td className="px-3 py-[7px]">{c.label}</td>
                            <td className="num px-3 py-[7px]">{fmtUnit(c.from, unitOf(c))}</td>
                            <td className="num px-3 py-[7px]">{fmtUnit(c.to, unitOf(c))}</td>
                            <td
                              className={`num px-3 py-[7px] ${
                                c.change < 0 ? "text-v2-negative" : c.change > 0 ? "text-v2-positive" : "text-v2-faint"
                              }`}
                            >
                              {fmtUnit(c.change, unitOf(c))}
                            </td>
                            <td className="num px-3 py-[7px]">
                              {unitOf(c) === "currency" ? `${c.share_of_mom}%` : "—"}
                            </td>
                          </tr>
                        ))}
                        <tr className="bg-v2-total-bg font-semibold">
                          <td className="px-3 py-[7px]">{groupLabel} — net change</td>
                          <td className="num px-3 py-[7px]">
                            {fmtMoney(dollarComponents.reduce((s, c) => s + (c.from ?? 0), 0))}
                          </td>
                          <td className="num px-3 py-[7px]">
                            {fmtMoney(dollarComponents.reduce((s, c) => s + (c.to ?? 0), 0))}
                          </td>
                          <td
                            className={`num px-3 py-[7px] ${
                              netChange < 0 ? "text-v2-negative" : netChange > 0 ? "text-v2-positive" : "text-v2-faint"
                            }`}
                          >
                            {fmtMoney(netChange)}
                          </td>
                          <td className="num px-3 py-[7px]">
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

                  {/* T3-1 — older evidence records lack the deepened panels;
                      say so plainly instead of leaving a gap. */}
                  {!calc.why && !calc.attribution && (
                    <p className="mt-3 rounded-[3px] border border-v2-border bg-v2-sub-bg px-4 py-2.5 text-[11.5px] text-v2-muted">
                      Detailed evidence panels (why this revenue driver, attribution order,
                      credited breakdown) are available from version{" "}
                      {DEEP_EVIDENCE_FROM_VERSION} onward — this version predates them and they
                      cannot be honestly reconstructed for its superseded driver set.
                    </p>
                  )}

                  {/* R4-1 — Why this revenue driver */}
                  {calc.why && (
                    <SubPanel title="Why this revenue driver">
                      <p className="text-[11.5px] leading-relaxed text-v2-text">{calc.why.rule}</p>
                      {calc.why.inputs_tested.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                            Inputs tested
                          </span>
                          {calc.why.inputs_tested.map((input) => (
                            <span
                              key={input}
                              className="rounded-full bg-v2-sub-bg px-2 py-0.5 text-[10px] text-v2-text"
                            >
                              {input}
                            </span>
                          ))}
                        </div>
                      )}
                      {calc.why.rejected.length > 0 && (
                        <div className="mt-2.5">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
                            Competing revenue drivers rejected
                          </span>
                          <ul className="mt-1 space-y-1">
                            {calc.why.rejected.map((r) => (
                              <li key={r.cause} className="flex items-start gap-2 text-[11.5px]">
                                <CauseTag causeId={r.cause} className="mt-px shrink-0" />
                                <span className="text-v2-muted">{r.reason}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </SubPanel>
                  )}

                  {/* R4-2 — Attribution order (no double-counting) */}
                  {calc.attribution && (
                    <SubPanel
                      title={`Attribution order — step ${calc.attribution.step} of ${calc.attribution.total_steps}`}
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        {calc.attribution.order.map((cause, i) => (
                          <span key={cause} className="flex items-center gap-1.5">
                            {i > 0 && <span className="text-[10px] text-v2-faint">›</span>}
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                                i + 1 === calc.attribution?.step
                                  ? "bg-v2-navy text-white"
                                  : i + 1 < (calc.attribution?.step ?? 0)
                                    ? "bg-v2-header-bg text-v2-navy"
                                    : "bg-v2-sub-bg text-v2-faint"
                              }`}
                            >
                              {cause.replace(/_/g, "-")}
                            </span>
                          </span>
                        ))}
                      </div>
                      {calc.attribution.earlier_claims.length > 0 && (
                        <p className="mt-2 text-[11px] text-v2-muted">
                          Already claimed by earlier steps:{" "}
                          {calc.attribution.earlier_claims
                            .map((c) => `${c.cause.replace(/_/g, "-")} ${fmtMoney(c.amount)}`)
                            .join(", ")}
                          . Each transaction is attributed once, in this fixed order — later steps
                          cannot re-claim it.
                        </p>
                      )}
                    </SubPanel>
                  )}

                  {/* R4-3 / S-A2 — reconciliation waterfall, rebuilt for the
                      modal's scope group so it ties to the header and the
                      credited breakdown. Never the transition-wide walk
                      unless the scope IS the total, in which case it says so. */}
                  {groupWaterfall && (
                    <SubPanel title={`Reconciliation waterfall — ${scopeLabel}`}>
                      <ReconciliationWaterfall
                        data={groupWaterfall}
                        fromLabel={fromLabel}
                        toLabel={toLabel}
                        scopeLabel={scopeLabel}
                        focusCause={causeSegment}
                      />
                    </SubPanel>
                  )}

                  {/* R4-4 — rev_nature derivation */}
                  {calc.rev_nature && (
                    <SubPanel title="Revenue-nature derivation">
                      <p className="mb-2 text-[11.5px] leading-relaxed text-v2-text">
                        {calc.rev_nature.rule}
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-[11px]">
                          <thead>
                            <tr className="bg-v2-header-bg text-left">
                              <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">File key</th>
                              <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Trade description</th>
                              <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Rev nature</th>
                              <th className="num px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Rows</th>
                            </tr>
                          </thead>
                          <tbody>
                            {calc.rev_nature.values.map((v, i) => (
                              <tr key={`${v.file_key}-${v.trade_description}-${i}`} className="border-b border-v2-border-subtle">
                                <td className="px-3 py-[7px] font-mono text-[10.5px]">{v.file_key}</td>
                                <td className="px-3 py-[7px]">{v.trade_description}</td>
                                <td className="px-3 py-[7px] font-semibold">{v.rev_nature}</td>
                                <td className="num px-3 py-[7px]">{v.count.toLocaleString("en-US")}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </SubPanel>
                  )}

                  {/* R4-5 — Credited-revenue breakdown (the client's own definition) */}
                  {calc.credited_breakdown && calc.credited_breakdown.months.length > 0 && (
                    <SubPanel title="Credited revenue breakdown">
                      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        {calc.credited_breakdown.months.map((m) => {
                          const annotation = m.non_credited_detail
                            .map((d) => `${d.reason_code} ${d.ui_mapping} ×${d.count}`)
                            .join(", ");
                          const lines: { label: string; amount: string; note?: string; total?: boolean }[] = [
                            { label: "In-scope revenue", amount: ledgerAmt(m.total_revenue), note: "total within credited product grid types" },
                            { label: "less non-credited", amount: ledgerAmt(-m.non_credited), note: annotation || undefined },
                            { label: "less excluded", amount: ledgerAmt(-m.excluded) },
                            { label: "less >90-day processing", amount: ledgerAmt(-m.late_excluded) },
                            { label: "= Credited revenue", amount: ledgerAmt(m.credited), total: true },
                          ];
                          return (
                            <div key={m.month_id} className="rounded-[3px] border border-v2-border-subtle px-3 py-2.5">
                              <div className="mb-1.5 text-[11px] font-semibold text-v2-text">
                                {monthShort(m.month_id)}
                              </div>
                              <table className="w-full border-collapse text-[11.5px]">
                                <tbody>
                                  {lines.map((line) => (
                                    <tr
                                      key={line.label}
                                      className={line.total ? "border-t border-v2-border font-semibold" : ""}
                                    >
                                      <td className="py-[3px] pr-3">{line.label}</td>
                                      <td className={`num w-28 py-[3px] ${line.amount.startsWith("(") ? "text-v2-negative" : ""}`}>
                                        {line.amount}
                                      </td>
                                      <td className="py-[3px] pl-3 text-[10.5px] text-v2-muted">
                                        {line.note ?? ""}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })}
                      </div>
                    </SubPanel>
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
                              className={`px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px] ${i >= 5 ? "text-right" : ""}`}
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sourceRecords.sample.map((r) => (
                          <tr key={r.trade_ref} className="border-b border-v2-border-subtle">
                            <td className="px-3 py-[7px] font-mono text-[11px] text-v2-link">{r.trade_ref}</td>
                            <td className="px-3 py-[7px]">{fmtDate(r.date)}</td>
                            <td className="px-3 py-[7px]">{r.product}</td>
                            <td className="px-3 py-[7px] font-mono text-[11px]">{r.account}</td>
                            <td className="px-3 py-[7px]">{r.type}</td>
                            <td className={`num px-3 py-[7px] ${r.credited < 0 ? "text-v2-negative" : ""}`}>
                              {fmtMoney(r.credited)}
                            </td>
                            <td className="num px-3 py-[7px]">{Math.round((r.split_pct ?? 0) * 100)}%</td>
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
                    <pre className="flex-1 overflow-x-auto rounded-[3px] bg-v2-positive-bg px-3 py-[7px] font-mono text-[11.5px] text-v2-text">
                      {resultText}
                    </pre>
                  </div>
                  <p className="mb-2 mt-4 text-[11.5px] text-v2-muted">
                    Source extraction (PostgreSQL) — lineage only; this SQL was <span className="font-semibold">not executed by this application</span>. The GSQL above <span className="font-semibold">was</span> run.
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

        {/* Footer — Previous/Next page through the transition's full driver
            set (T2-1); ←/→ do the same. */}
        <div className="sticky bottom-0 flex items-center justify-between gap-4 border-t border-v2-border bg-white px-6 py-3">
          <span className="min-w-0 truncate text-[10.5px] text-v2-faint">
            {version
              ? `Commentary v${version.version_no} · model ${version.model} · prompt ${version.prompt_version} · generated ${fmtDate(version.generated_at)} · data snapshot ${fmtDate(version.data_snapshot_dt)}`
              : `Commentary ${versionId}`}
            {evidence ? ` · query ${evidence.gsql_query_name}` : ""}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => page(-1)}
              disabled={index <= 0}
              aria-label="Previous revenue driver"
              className="rounded-[3px] border border-v2-navy bg-white px-3 py-1.5 text-[11.5px] font-semibold text-v2-navy hover:bg-v2-sub-bg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:border-v2-border disabled:text-v2-faint"
            >
              ‹ Previous
            </button>
            <span className="num whitespace-nowrap text-[11px] text-v2-muted">
              {driverCount > 0 ? `Revenue Driver ${index + 1} of ${driverCount} in ${groupLabel}` : "—"}
            </span>
            <button
              type="button"
              onClick={() => page(1)}
              disabled={!drivers || index >= drivers.length - 1}
              aria-label="Next revenue driver"
              className="rounded-[3px] border border-v2-navy bg-white px-3 py-1.5 text-[11.5px] font-semibold text-v2-navy hover:bg-v2-sub-bg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy disabled:cursor-not-allowed disabled:border-v2-border disabled:text-v2-faint"
            >
              Next ›
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-[3px] bg-v2-navy px-5 py-1.5 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-v2-navy"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
