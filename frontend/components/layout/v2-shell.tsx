"use client";
/**
 * iPerform V2 shell (UI_SPEC §1-3): navy top nav -> sub-nav -> sample-data
 * banner -> advisor context bar -> content. Advisor selection persists across
 * the Results screens (localStorage) and every screen reads it from context.
 * The tier pill is honest: green TigerGraph tier 1, amber Local store tier 2,
 * RED when GRAPH_CLIENT_MODE=real is being served by the local store.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ReactNode, createContext, useContext, useEffect, useMemo, useState,
} from "react";
import { Settings } from "lucide-react";
import { type Advisor, type MonthRow, v2Api } from "@/lib/api/v2";
import { fmtDate } from "@/lib/v2/format";

interface V2ContextValue {
  advisors: Advisor[];
  months: MonthRow[];
  advisorId: string | null;
  advisor: Advisor | null;
  setAdvisorId: (id: string) => void;
  fromMonth: string;
  toMonth: string;
  modes: { graph_client_mode: string; data_set: string } | null;
  servedByTier: number | null;
  reportTier: (tier: number) => void;
  loaded: boolean;
}

const V2Context = createContext<V2ContextValue | null>(null);

export function useV2Context(): V2ContextValue {
  const ctx = useContext(V2Context);
  if (!ctx) throw new Error("useV2Context outside V2Shell");
  return ctx;
}

const RESULTS_TABS = [
  { label: "Revenue", href: "/revenue" },
  { label: "Transactions", href: "/transactions" },
  { label: "Trends", href: "/trends" },
  { label: "AI Insights", href: "/ai-insights" },
];

const OPS_TABS = [
  { label: "Data Ingestion", href: "/data-ingestion" },
  { label: "Env Health", href: "/env-health" },
];

export function V2Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [months, setMonths] = useState<MonthRow[]>([]);
  const [advisorId, setAdvisorIdState] = useState<string | null>(null);
  const [modes, setModes] = useState<V2ContextValue["modes"]>(null);
  const [servedByTier, setServedByTier] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.allSettled([v2Api.advisors(), v2Api.months(), v2Api.adapterStatus()]).then(
      ([a, m, s]) => {
        if (!active) return;
        if (a.status === "fulfilled") {
          setAdvisors(a.value.advisors);
          setServedByTier(a.value.served_by_tier);
          const stored = window.localStorage.getItem("v2.advisorId");
          const valid = a.value.advisors.some((x) => x.advisor_sid === stored);
          setAdvisorIdState(valid ? stored : a.value.advisors[0]?.advisor_sid ?? null);
        }
        if (m.status === "fulfilled") setMonths(m.value.months);
        if (s.status === "fulfilled") setModes(s.value.modes);
        setLoaded(true);
      },
    );
    return () => { active = false; };
  }, []);

  const value = useMemo<V2ContextValue>(() => {
    const monthIds = months.map((m) => m.month_id).sort();
    return {
      advisors,
      months,
      advisorId,
      advisor: advisors.find((a) => a.advisor_sid === advisorId) ?? null,
      setAdvisorId: (id: string) => {
        window.localStorage.setItem("v2.advisorId", id);
        setAdvisorIdState(id);
      },
      fromMonth: monthIds[0] ?? "",
      toMonth: monthIds[monthIds.length - 1] ?? "",
      modes,
      servedByTier,
      reportTier: setServedByTier,
      loaded,
    };
  }, [advisors, months, advisorId, modes, servedByTier, loaded]);

  const isResults = RESULTS_TABS.some((t) => pathname?.startsWith(t.href));

  return (
    <V2Context.Provider value={value}>
      <div className="min-h-screen bg-v2-page font-v2 text-v2-text">
        <TopNav pathname={pathname ?? ""} />
        <SubNav pathname={pathname ?? ""} />
        {modes?.data_set === "sample" && (
          <div className="border-b border-v2-border bg-v2-warn-bg px-6 py-1.5 text-[11px] font-semibold text-v2-warn">
            Sample data — not client figures.
          </div>
        )}
        {isResults && <AdvisorContextBar />}
        <main className="px-6 py-4">{children}</main>
      </div>
    </V2Context.Provider>
  );
}

function TopNav({ pathname }: { pathname: string }) {
  const opsActive = OPS_TABS.some((t) => pathname.startsWith(t.href));
  return (
    <div className="flex h-12 items-center bg-v2-navy px-6 text-white">
      <Link href="/trends" className="mr-8 text-[17px] font-bold tracking-tight">iPerform</Link>
      <div className={`flex h-12 items-center px-5 text-[13px] ${opsActive ? "" : "bg-v2-navy-dark font-semibold"}`}>
        Results
      </div>
      <div className="ml-auto flex items-center gap-4">
        <Link
          href="/data-ingestion"
          className={`flex items-center gap-1.5 text-[12px] ${opsActive ? "font-semibold text-white" : "text-white/75 hover:text-white"}`}
        >
          <Settings className="h-3.5 w-3.5" /> Operations
        </Link>
      </div>
    </div>
  );
}

function SubNav({ pathname }: { pathname: string }) {
  const opsActive = OPS_TABS.some((t) => pathname.startsWith(t.href));
  const tabs = opsActive ? OPS_TABS : RESULTS_TABS;
  return (
    <div className="flex items-center gap-8 border-b border-v2-border bg-v2-card px-6">
      {tabs.map((t) => {
        const active = pathname.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`border-b-2 py-3 text-[13px] ${
              active
                ? "border-v2-navy font-semibold text-v2-navy"
                : "border-transparent text-v2-muted hover:text-v2-text"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}

export function TierPill() {
  const { modes, servedByTier } = useV2Context();
  if (servedByTier == null) return null;
  const realMode = modes?.graph_client_mode === "real";
  const tier1 = servedByTier === 1;
  const red = realMode && !tier1;
  const label = tier1 ? "TigerGraph · tier 1" : "Local store · tier 2";
  const cls = red
    ? "bg-v2-negative-bg text-v2-negative"
    : tier1
      ? "bg-v2-positive-bg text-v2-positive"
      : "bg-v2-warn-bg text-v2-warn";
  return (
    <span
      className={`rounded-full px-3 py-1 text-[10.5px] font-semibold ${cls}`}
      title={red ? "GRAPH_CLIENT_MODE=real but the LOCAL store is serving — TigerGraph is NOT serving." : undefined}
    >
      ● {red ? `${label} — real mode NOT served by TigerGraph` : label}
    </span>
  );
}

function AdvisorContextBar() {
  const { advisors, advisor, advisorId, setAdvisorId, months } = useV2Context();
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => { setPending(advisorId); }, [advisorId]);
  const asOf = months.length ? fmtDate(months[months.length - 1].end_dt) : "—";
  const label = advisor
    ? advisor.advisor_name
      ? `${advisor.advisor_sid} · ${advisor.advisor_name}`
      : advisor.advisor_sid
    : "—";
  return (
    <div className="border-b border-v2-border bg-v2-card px-6 py-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-bold">{label}</span>
          <span className="rounded-full bg-v2-header-bg px-2.5 py-0.5 text-[10.5px] text-v2-navy">
            AGP 2.0 · {months.length} months
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11.5px] text-v2-muted">As of {asOf}</span>
          <TierPill />
        </div>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="text-[11px] text-v2-muted">Advisor</span>
        <select
          value={pending ?? ""}
          onChange={(e) => setPending(e.target.value)}
          className="h-6 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]"
          aria-label="Select advisor"
        >
          {advisors.map((a) => (
            <option key={a.advisor_sid} value={a.advisor_sid}>
              {a.advisor_sid}{a.advisor_name ? ` · ${a.advisor_name}` : ""}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => pending && setAdvisorId(pending)}
          className="h-6 rounded-[3px] bg-v2-navy px-3.5 text-[11.5px] font-semibold text-white hover:bg-v2-navy-dark"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
