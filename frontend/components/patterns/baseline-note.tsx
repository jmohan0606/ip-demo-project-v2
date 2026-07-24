"use client";
/**
 * Baseline-transition labelling — FIX_SPEC_R8 B. The FIRST transition in the
 * loaded data (the one whose from-month is the earliest loaded month) has no
 * prior period to compare account activity against, so its driver attribution
 * is indicative. The operator's decision: SHOW it, clearly labelled — never
 * hide it. This module is the single source of both the identification
 * (from data via GQ-002 get_months, never a hardcoded month) and the label
 * wording, shared by the AI-Insights cards, the monthly walk table, the chart
 * arrow and the evidence modal. Neutral informational (amber/INFO) treatment,
 * not an error style.
 */
import { useEffect, useState } from "react";
import { v2Api } from "@/lib/api/v2";
import { monthFull } from "@/lib/v2/format";

let cachedEarliest: string | null | undefined; // undefined = not fetched yet
let inflight: Promise<string | null> | null = null;

async function fetchEarliestMonth(): Promise<string | null> {
  if (cachedEarliest !== undefined) return cachedEarliest;
  if (!inflight) {
    inflight = v2Api
      .months()
      .then((res) => {
        const ids = res.months.map((m) => m.month_id).sort();
        cachedEarliest = ids[0] ?? null;
        return cachedEarliest;
      })
      .catch(() => {
        inflight = null; // retry on next consumer; never label on a guess
        return null;
      });
  }
  return inflight;
}

/** Earliest loaded month_id (null while loading / if unavailable). A
 * transition is THE baseline transition iff its from_month equals this. */
export function useBaselineFromMonth(): string | null {
  const [earliest, setEarliest] = useState<string | null>(cachedEarliest ?? null);
  useEffect(() => {
    if (cachedEarliest !== undefined) return;
    let alive = true;
    void fetchEarliestMonth().then((m) => alive && setEarliest(m));
    return () => {
      alive = false;
    };
  }, []);
  return earliest;
}

/** The full labelled note (cards, walk table, evidence modal). */
export function BaselineTransitionNote({
  fromMonthId,
  className = "",
}: {
  fromMonthId: string;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[3px] border border-v2-warn/40 bg-v2-warn-bg px-3 py-2 text-[11px] leading-relaxed text-v2-text ${className}`}
    >
      <span className="font-semibold text-v2-warn">Baseline period</span> —{" "}
      {monthFull(fromMonthId)} is the first month in the loaded data, so there is no prior
      period to compare account activity against. Driver attribution for this transition is
      indicative; later transitions are fully attributed.
    </div>
  );
}

/** Compact chip for tight spots (chart arrow, walk-table row). */
export function BaselineTag({ className = "" }: { className?: string }) {
  return (
    <span
      title="Baseline period — the first transition in the loaded data has no prior period for account comparison; driver attribution is indicative."
      className={`inline-block rounded-full bg-v2-warn-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-warn ${className}`}
    >
      Baseline
    </span>
  );
}
