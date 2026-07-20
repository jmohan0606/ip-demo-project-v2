"use client";
/**
 * Trends — /trends (UI_SPEC §4). Two stacked cards on one route:
 *   1. Credited Revenue — Months (hierarchical pivot, reference 01)
 *   2. Credited Revenue — MoM Change (transition pivot, reference 02)
 * Data: product hierarchy + GQ-005 (monthly revenue) + GQ-007 (changes),
 * refetched when the selected advisor changes. The served tier is reported to
 * the context bar so the tier pill never misrepresents the source.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type MonthlyRevenueRow,
  type ProductHierarchy,
  type RevenueChangeRow,
  v2Api,
} from "@/lib/api/v2";
import { useV2Context } from "@/components/layout/v2-shell";
import { ErrorState, LoadingState } from "@/components/patterns/async-state";
import { RevenuePivot } from "@/components/trends/revenue-pivot";
import { MomChangePivot } from "@/components/trends/mom-change-pivot";

interface TrendsData {
  hierarchy: ProductHierarchy;
  revenue: MonthlyRevenueRow[];
  changes: RevenueChangeRow[];
}

export default function TrendsPage() {
  const { advisorId, fromMonth, toMonth, months, reportTier, loaded } = useV2Context();
  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const monthIds = useMemo(
    () =>
      months
        .map((m) => m.month_id)
        .filter((id) => id >= fromMonth && id <= toMonth)
        .sort(),
    [months, fromMonth, toMonth],
  );

  const retry = useCallback(() => setReload((n) => n + 1), []);

  useEffect(() => {
    if (!advisorId || !fromMonth || !toMonth) return;
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      v2Api.productHierarchy(),
      v2Api.trendsRevenue(advisorId, fromMonth, toMonth),
      v2Api.trendsChanges(advisorId, fromMonth, toMonth),
    ])
      .then(([hierarchy, revenue, changes]) => {
        if (!active) return;
        setData({
          hierarchy,
          revenue: revenue.monthly_revenue,
          changes: changes.changes,
        });
        reportTier(revenue.served_by_tier);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : "Failed to load trends data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [advisorId, fromMonth, toMonth, reload, reportTier]);

  if (loaded && !advisorId) {
    return (
      <div className="rounded-[3px] border border-v2-border bg-v2-card p-8 text-center text-[11.5px] text-v2-muted">
        No advisor available — load reference data via Data Ingestion, then select an advisor.
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={retry} />;
  }

  if (loading || !data || !loaded || !advisorId) {
    return <LoadingState label="Loading credited revenue…" />;
  }

  if (data.revenue.length === 0) {
    return (
      <div className="rounded-[3px] border border-v2-border bg-v2-card p-8 text-center text-[11.5px] text-v2-muted">
        No credited revenue found for this advisor in the selected period. Load transaction
        data via Data Ingestion, or choose another advisor.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <RevenuePivot
        hierarchy={data.hierarchy}
        revenue={data.revenue}
        monthIds={monthIds}
        advisorId={advisorId}
      />
      <MomChangePivot
        hierarchy={data.hierarchy}
        revenue={data.revenue}
        changes={data.changes}
        monthIds={monthIds}
        advisorId={advisorId}
      />
    </div>
  );
}
