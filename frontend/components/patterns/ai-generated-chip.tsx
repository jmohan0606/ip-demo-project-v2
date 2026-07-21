/**
 * "AI Generated" marking (FIX_SPEC R7-2). Marks model-authored LANGUAGE only —
 * never figures, tables, charts, cause tags or provenance badges. The chip is
 * small, neutral and non-alarming; it sits inline with other metadata chips.
 */

/** Exact boundary helper text (FIX_SPEC R7-2) — rendered under the AI Insights
 * section header and in the evidence modal. */
export const AI_BOUNDARY_TEXT =
  "Wording is AI-generated. All figures are computed from graph data and validated before publication — the model never produces or alters a number.";

export function AiGeneratedChip({
  model,
  promptVersion,
  versionId,
  className = "",
}: {
  model?: string;
  promptVersion?: string;
  versionId?: string;
  className?: string;
}) {
  const tooltip = [
    model || null,
    promptVersion ? `prompt ${promptVersion}` : null,
    versionId ? `commentary ${versionId}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.3px] text-v2-navy ${className}`}
      title={tooltip || undefined}
    >
      ✦ AI Generated
    </span>
  );
}

/** Judge verdict pill (FIX_SPEC R5-4). PASS is neutral; REVIEW / FAIL use the
 * existing warn tokens — advisory, never alarming, never a new colour. */
export function JudgeVerdictPill({ verdict, className = "" }: { verdict: string; className?: string }) {
  const ok = verdict === "PASS";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase ${
        ok ? "bg-v2-header-bg text-v2-navy" : "bg-v2-warn-bg text-v2-warn"
      } ${className}`}
    >
      {verdict}
    </span>
  );
}

/** Small card badge shown on AI Insights commentary cards when the independent
 * judge verdict is not PASS (FIX_SPEC R5-4). */
export function JudgeBadge({ verdict, className = "" }: { verdict: string; className?: string }) {
  if (verdict !== "REVIEW" && verdict !== "FAIL") return null;
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full bg-v2-warn-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-warn ${className}`}
      title="Independent LLM judge flagged this commentary for human attention — open any evidence record for the reasoning."
    >
      Judge: {verdict}
    </span>
  );
}
