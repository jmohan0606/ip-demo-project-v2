import { AiContentCard } from "@/components/patterns/ai-content-card";
import { SeverityBadge } from "@/components/patterns/severity-badge";
import { colors, type } from "@/styles/tokens";

export interface InsightKeyDriver { label: string; value: number | string | null; detail?: string; source?: string }
export interface InsightWatchOut { title: string; summary: string; severity: string; confidence?: number }
export interface AiInsightData {
  headline?: string | null;
  executive_summary?: string;
  confidence?: number;
  key_drivers: InsightKeyDriver[];
  watch_outs: InsightWatchOut[];
  what_to_monitor: string[];
}

const fmtVal = (v: number | string | null) => {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Math.abs(v) >= 1000 ? `$${Math.round(v).toLocaleString()}` : `${v}`;
  return String(v);
};

/** AI Insight Summary card — Key Drivers / Watch Outs / What to Monitor
 * (CLAUDE.md 9.5). Structured, color-coded sections; grounded in the insight
 * engine's real evidence. Reused on Dashboard / Advisor 360 / Client 360. */
export function AiInsightSummary({ data, title = "AI Insight Summary" }: { data: AiInsightData; title?: string }) {
  return (
    <AiContentCard
      title={title}
      footer={
        <span className={type.data} style={{ color: colors.text.muted }}>
          Confidence {Math.round((data.confidence ?? 0) * 100)}% · grounded in the Phase-5..9 insight engine (features, predictions, opportunities, recommendations).
        </span>
      }
    >
      <div className="space-y-3">
        {(data.headline || data.executive_summary) && (
          <section className="rounded-lg px-3 py-2.5" style={{ backgroundColor: "#F8FAFC" }}>
            {data.headline && (
              <h3 className="text-[15px] font-bold leading-snug" style={{ color: colors.text.primary }}>
                {data.headline}
              </h3>
            )}
            {data.executive_summary && (
              <p className="mt-1 text-[12px] leading-relaxed" style={{ color: colors.text.secondary }}>
                {data.executive_summary}
              </p>
            )}
          </section>
        )}
        <section>
          <div className={type.label} style={{ color: colors.positive }}>Key Drivers</div>
          <div className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
            {data.key_drivers.map((d) => (
              <div key={d.label} className="flex items-baseline justify-between rounded-lg border px-2.5 py-1.5" style={{ borderColor: colors.surface.border }}>
                <span className={type.data} style={{ color: colors.text.secondary }}>{d.label}</span>
                <span className={`font-mono ${type.data} font-semibold`} style={{ color: colors.text.primary }}>{fmtVal(d.value)}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className={type.label} style={{ color: colors.warning }}>Watch Outs</div>
          <ul className="mt-1.5 space-y-1.5">
            {data.watch_outs.map((w) => (
              <li key={w.title} className="flex items-start gap-2">
                <SeverityBadge value={w.severity} />
                <div className="min-w-0">
                  <div className={`${type.data} font-semibold`} style={{ color: colors.text.primary }}>{w.title}</div>
                  <div className={type.data} style={{ color: colors.text.secondary }}>{w.summary}</div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <div className={type.label} style={{ color: colors.primary }}>What to Monitor</div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {data.what_to_monitor.map((m) => (
              <span key={m} className="rounded-full border px-2 py-0.5 text-[11px] font-medium" style={{ borderColor: colors.surface.border, color: colors.text.secondary, backgroundColor: colors.surface.canvas }}>
                {m}
              </span>
            ))}
          </div>
        </section>
      </div>
    </AiContentCard>
  );
}
