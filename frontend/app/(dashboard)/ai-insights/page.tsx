"use client";
/**
 * AI Insights — /ai-insights (UI_SPEC §5). Three cards:
 *   1. chart (stacked bars + MoM connector arrows)  — GQ-006 + GQ-007 totals
 *   2. commentary cards (stored, versioned)         — GQ-009 + drivers
 *   3. monthly walk table                           — same data, table form
 * Commentary is retrieved, never generated on load; Regenerate / Generate is
 * the only path that calls the LLM (batch, via the backend workflow).
 */
import { useCallback, useEffect, useState } from "react";
import { CommentaryCards } from "@/components/ai-insights/commentary-cards";
import { InsightsChartCard } from "@/components/ai-insights/insights-chart-card";
import { MonthlyWalkTable } from "@/components/ai-insights/monthly-walk-table";
import type { EvidenceRequest } from "@/components/ai-insights/types";
import { EvidenceModal } from "@/components/evidence/evidence-modal";
import { useV2Context } from "@/components/layout/v2-shell";
import { AsyncBoundary, CardSkeleton } from "@/components/patterns/async-state";
import {
  type CommentaryEvaluation,
  type CommentaryRow,
  type CommentaryVersion,
  type MonthlyTotals,
  type RevenueChangeRow,
  v2Api,
} from "@/lib/api/v2";

export default function AiInsightsPage() {
  const { advisorId, advisor, fromMonth, toMonth, loaded, reportTier } = useV2Context();

  const [chart, setChart] = useState<MonthlyTotals | null>(null);
  const [changes, setChanges] = useState<RevenueChangeRow[] | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartKey, setChartKey] = useState(0);

  const [versions, setVersions] = useState<CommentaryVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState(""); // "" = latest PUBLISHED (backend resolves)
  const [commentary, setCommentary] = useState<CommentaryRow[] | null>(null);
  const [resolvedVersion, setResolvedVersion] = useState("");
  const [commentaryError, setCommentaryError] = useState<string | null>(null);
  const [commentaryKey, setCommentaryKey] = useState(0);
  const [busy, setBusy] = useState(false);

  // R5-4 — judge evaluations for the resolved version (advisory badges).
  const [evaluations, setEvaluations] = useState<CommentaryEvaluation[]>([]);

  const [modal, setModal] = useState<EvidenceRequest | null>(null);

  const ready = loaded && !!advisorId && !!fromMonth && !!toMonth;

  // Card 1 data — chart totals + __TOTAL__ changes.
  useEffect(() => {
    if (!ready || !advisorId) return;
    let active = true;
    setChart(null);
    setChanges(null);
    setChartError(null);
    Promise.all([
      v2Api.insightsChart(advisorId, fromMonth, toMonth),
      v2Api.trendsChanges(advisorId, fromMonth, toMonth),
    ])
      .then(([c, ch]) => {
        if (!active) return;
        setChart(c);
        setChanges(ch.changes);
        reportTier(c.served_by_tier);
      })
      .catch((e: unknown) => {
        if (active) setChartError(e instanceof Error ? e.message : "Failed to load chart data.");
      });
    return () => { active = false; };
  }, [ready, advisorId, fromMonth, toMonth, chartKey, reportTier]);

  // Versions list (also refetched after Regenerate).
  const fetchVersions = useCallback(() => {
    v2Api.versions()
      .then((v) => setVersions(v.versions))
      .catch(() => setVersions([]));
  }, []);
  useEffect(() => { fetchVersions(); }, [fetchVersions]);

  // Commentary for the selected version — retrieved, never generated here.
  useEffect(() => {
    if (!ready || !advisorId) return;
    let active = true;
    setCommentary(null);
    setCommentaryError(null);
    v2Api.commentary(advisorId, selectedVersion)
      .then((c) => {
        if (!active) return;
        setCommentary(c.commentaries);
        setResolvedVersion(c.resolved_version);
        reportTier(c.served_by_tier);
      })
      .catch((e: unknown) => {
        if (active) setCommentaryError(e instanceof Error ? e.message : "Failed to load commentary.");
      });
    return () => { active = false; };
  }, [ready, advisorId, selectedVersion, commentaryKey, reportTier]);

  // Judge evaluations for whichever version the commentary resolved to.
  // Advisory only — a fetch failure simply hides the badges.
  useEffect(() => {
    if (!resolvedVersion) {
      setEvaluations([]);
      return;
    }
    let active = true;
    v2Api.evaluations(resolvedVersion)
      .then((e) => { if (active) setEvaluations(e.evaluations); })
      .catch(() => { if (active) setEvaluations([]); });
    return () => { active = false; };
  }, [resolvedVersion, commentaryKey]);

  const regenerate = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      await v2Api.generate();
      fetchVersions();
      setSelectedVersion(""); // jump to the new latest PUBLISHED version
      setCommentaryKey((k) => k + 1);
    } catch (e: unknown) {
      setCommentaryError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }, [busy, fetchVersions]);

  return (
    <div className="space-y-4">
      <AsyncBoundary
        loading={!ready || (!chart && !chartError)}
        error={chartError}
        onRetry={() => setChartKey((k) => k + 1)}
        skeleton={<div className="rounded-[3px] border border-v2-border bg-v2-card p-5"><CardSkeleton bodyHeight="h-72" /></div>}
      >
        {chart && changes && <InsightsChartCard totals={chart} changes={changes} />}
      </AsyncBoundary>

      <AsyncBoundary
        loading={!ready || (!commentary && !commentaryError)}
        error={commentaryError}
        onRetry={() => setCommentaryKey((k) => k + 1)}
        skeleton={<div className="rounded-[3px] border border-v2-border bg-v2-card p-5"><CardSkeleton bodyHeight="h-64" /></div>}
      >
        {commentary && (
          <CommentaryCards
            rows={commentary}
            totals={chart}
            versions={versions}
            selectedVersion={selectedVersion}
            resolvedVersion={resolvedVersion}
            evaluations={evaluations}
            onSelectVersion={setSelectedVersion}
            onRegenerate={() => void regenerate()}
            busy={busy}
            onOpenEvidence={setModal}
          />
        )}
      </AsyncBoundary>

      <AsyncBoundary
        loading={!ready || ((!chart || !commentary) && !chartError && !commentaryError)}
        error={chartError ?? commentaryError}
        onRetry={() => { setChartKey((k) => k + 1); setCommentaryKey((k) => k + 1); }}
        skeleton={<div className="rounded-[3px] border border-v2-border bg-v2-card p-5"><CardSkeleton bodyHeight="h-48" /></div>}
      >
        {chart && changes && commentary && (
          <MonthlyWalkTable
            totals={chart}
            changes={changes}
            rows={commentary}
            versions={versions}
            resolvedVersion={resolvedVersion}
            onOpenEvidence={setModal}
          />
        )}
      </AsyncBoundary>

      {modal && advisorId && (
        <EvidenceModal
          versionId={modal.versionId}
          advisorId={advisorId}
          advisorName={advisor?.advisor_name ?? ""}
          fromMonthId={modal.fromMonthId}
          toMonthId={modal.toMonthId}
          transitionLabel={modal.transitionLabel}
          initialDriverId={modal.initialDriverId}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}
