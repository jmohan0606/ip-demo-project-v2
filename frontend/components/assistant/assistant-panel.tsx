"use client";
/**
 * Ask iPerform — the conversation surface (FIX_SPEC_R7 B1-B4).
 *
 * ONE component, two presentations (B2): variant="overlay" renders inside the
 * right-edge floating panel; variant="page" renders wider inside /ask. All
 * behaviour (transcript, context chip + Pin, suggestions, guardrail chip,
 * figures, audit trail) is shared — never forked.
 *
 * Rendering rules (B3, ABSOLUTE RULE 8a):
 *  - narrative wording carries the AI Generated chip — WORDING ONLY;
 *  - figures render as a compact list below, NEVER marked AI-generated;
 *  - `Ran: <query names>` in small monospace — the visible audit trail;
 *  - Evidence › / deep links carry the resolved parameters;
 *  - BLOCKED turns render the refusal with a neutral ⛉ GUARDRAIL chip whose
 *    tooltip shows CATEGORY AND SEVERITY ONLY (A10) — never the pattern.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AiGeneratedChip } from "@/components/patterns/ai-generated-chip";
import { type AssistantFigure, type MessageRow } from "@/lib/api/v2";
import { useAssistant } from "@/components/assistant/assistant-context";

const STARTERS = [
  "Why did revenue drop this month?",
  "Which advisor had the biggest drop?",
  "Anything unusual this month?",
  "Revenue by product for this month",
];

function parse<T>(json: string | undefined, fallback: T): T {
  if (!json) return fallback;
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

function GuardrailChip({ message }: { message: MessageRow }) {
  const findings = parse<{ category: string; severity: string }[]>(
    message.guardrail_json, []);
  const seen = new Set<string>();
  const label = findings
    .map((f) => `${f.category.replace(/_/g, " ").toLowerCase()} · ${f.severity}`)
    .filter((t) => !seen.has(t) && seen.add(t))
    .join(", ");
  return (
    <span
      className="inline-block whitespace-nowrap rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.3px] text-v2-navy"
      title={label || "guardrail"}
    >
      ⛉ Guardrail
    </span>
  );
}

function ContextChip({ message }: { message: MessageRow }) {
  const ctx = parse<{ chip?: string; pinned?: boolean }>(message.resolved_context_json, {});
  if (!ctx.chip) return null;
  return (
    <span className="inline-block whitespace-nowrap rounded-full bg-v2-warn-bg px-2 py-0.5 text-[9.5px] font-medium text-v2-warn">
      ↩ {ctx.pinned ? "pinned" : "context"}: {ctx.chip}
    </span>
  );
}

function Figures({ message }: { message: MessageRow }) {
  const figures = parse<AssistantFigure[]>(message.figures_json, []);
  if (!figures.length) return null;
  return (
    <div className="mt-2 border-t border-v2-border">
      {figures.slice(0, 8).map((f, i) => (
        <div key={i} className="flex items-baseline justify-between gap-3 border-b border-v2-border py-1">
          <span className="min-w-0 truncate text-[11px] text-v2-muted" title={f.label}>
            {f.label}
            {f.provenance !== "REAL" && f.provenance !== "DERIVED" && (
              <span className="ml-1 rounded bg-v2-warn-bg px-1 text-[9px] font-semibold text-v2-warn">
                {f.provenance}
              </span>
            )}
          </span>
          <span className={`whitespace-nowrap text-[12px] font-semibold tabular-nums ${
            f.formatted.startsWith("(") ? "text-v2-negative" : "text-v2-text"}`}>
            {f.formatted}
          </span>
        </div>
      ))}
    </div>
  );
}

function AssistantTurn({ message }: { message: MessageRow }) {
  const { extras } = useAssistant();
  const extra = extras[message.message_id];
  const queries = parse<{ query: string }[]>(message.queries_run_json, []);
  const provider = message.llm_provider ?? "";
  const aiWorded = message.status === "OK" && provider !== "" &&
    !provider.includes("deterministic") && provider !== "";
  const blocked = message.status === "BLOCKED";
  const softStatus = message.status === "NO_DATA" || message.status === "OUT_OF_SCOPE";

  return (
    <div className="rounded-lg border border-v2-border bg-white p-3 shadow-sm">
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        {blocked ? (
          <GuardrailChip message={message} />
        ) : aiWorded ? (
          <>
            <AiGeneratedChip model={provider} />
            <span className="text-[9.5px] italic text-v2-muted">wording only</span>
          </>
        ) : softStatus ? (
          <span className="rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-muted">
            {message.status === "NO_DATA" ? "No data" : "Out of scope"}
          </span>
        ) : null}
        {!blocked && <ContextChip message={message} />}
      </div>
      <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-v2-text">
        {message.text}
      </p>
      {!blocked && <Figures message={message} />}
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
        {queries.length > 0 && (
          <span className="font-mono text-[10px] text-v2-muted">
            Ran: {[...new Set(queries.map((q) => q.query))].join(" · ")}
          </span>
        )}
        <span className="ml-auto flex items-center gap-3">
          {extra?.evidence_driver_id && (
            <Link href="/ai-insights" className="text-[11px] font-semibold text-v2-navy hover:underline">
              Evidence ›
            </Link>
          )}
          {extra?.links.map((l) => (
            <Link key={l.href} href={l.href} className="text-[11px] font-semibold text-v2-navy hover:underline">
              {l.label}
            </Link>
          ))}
        </span>
      </div>
      {extra?.redaction_note && (
        <p className="mt-1 text-[10px] italic text-v2-muted">{extra.redaction_note}</p>
      )}
    </div>
  );
}

export function AssistantPanel({ variant }: { variant: "overlay" | "page" }) {
  const {
    messages, extras, sending, error, send, pinned, setPinned, screen,
  } = useAssistant();
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "ASSISTANT");
  const suggestions = lastAssistant
    ? extras[lastAssistant.message_id]?.suggestions ?? []
    : [];
  const chipText = pinned
    ? `Pinned: ${[pinned.advisor_sid, pinned.from_month && pinned.to_month
        ? `${pinned.from_month}→${pinned.to_month}` : pinned.to_month]
        .filter(Boolean).join(" · ")}`
    : `Following screen: ${[screen.advisor_sid, screen.from_month && screen.to_month
        ? `${screen.from_month}→${screen.to_month}` : screen.to_month, "credited"]
        .filter(Boolean).join(" · ")}`;

  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    void send(text);
  };

  const wide = variant === "page";

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* context chip + Pin (A4 — visible resolved context) */}
      <div className="flex items-center justify-between gap-2 border-b border-v2-border bg-v2-warn-bg px-3 py-1.5">
        <span className="truncate text-[10.5px] text-v2-warn">↺ {chipText}</span>
        <button
          type="button"
          onClick={() => setPinned(pinned ? null : { ...screen })}
          className={`shrink-0 rounded px-2 py-0.5 text-[10.5px] font-semibold ${
            pinned ? "bg-v2-navy text-white" : "text-v2-navy hover:bg-v2-header-bg"}`}
          title={pinned ? "Unpin — follow the screen again" : "Pin this context so it stops following the screen"}
        >
          {pinned ? "Pinned ✕" : "Pin"}
        </button>
      </div>

      {/* transcript (B4: empty / loading / error states all render) */}
      <div className={`min-h-0 flex-1 overflow-y-auto px-3 py-3 ${wide ? "mx-auto w-full max-w-3xl" : ""}`}>
        {messages.length === 0 && !sending && (
          <div className="mt-6 text-center">
            <p className="text-[12.5px] font-semibold text-v2-text">Ask about your revenue data</p>
            <p className="mx-auto mt-1 max-w-xs text-[11px] text-v2-muted">
              Answers come from your loaded revenue data. The assistant runs the
              same audited queries used across the app — it never estimates a figure.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {STARTERS.map((s) => (
                <button key={s} type="button" onClick={() => void send(s)}
                  className="rounded-full border border-v2-border bg-white px-3 py-1 text-[11px] text-v2-navy hover:border-v2-navy">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="space-y-3">
          {messages.map((m) =>
            m.role === "USER" ? (
              <div key={m.message_id} className="flex justify-end">
                <div className="max-w-[85%] rounded-lg bg-v2-navy px-3 py-2 text-[12.5px] text-white">
                  {m.text}
                </div>
              </div>
            ) : (
              <AssistantTurn key={m.message_id} message={m} />
            ),
          )}
          {sending && (
            <div className="flex items-center gap-2 text-[11.5px] text-v2-muted">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-v2-navy" />
              Running queries…
            </div>
          )}
          {error && (
            <div className="rounded border border-v2-border bg-v2-negative-bg px-3 py-2 text-[11.5px] text-v2-negative">
              {error}
            </div>
          )}
        </div>
        {suggestions.length > 0 && !sending && (
          <div className="mt-3">
            <p className="text-[9.5px] font-semibold uppercase tracking-wide text-v2-muted">Suggested</p>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => void send(s)}
                  className="rounded-full border border-v2-border bg-white px-3 py-1 text-[11px] text-v2-navy hover:border-v2-navy">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* input + honesty footer (B1) */}
      <div className={`border-t border-v2-border bg-white px-3 py-2 ${wide ? "mx-auto w-full max-w-3xl" : ""}`}>
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            placeholder={messages.length ? "Ask a follow-up…" : "Ask about revenue, drivers, accounts or transactions…"}
            aria-label="Ask iPerform"
            className="h-8 min-w-0 flex-1 rounded border border-v2-border px-2.5 text-[12px] outline-none focus:border-v2-navy"
          />
          <button type="button" onClick={submit} disabled={sending || !draft.trim()}
            className="h-8 rounded bg-v2-navy px-3.5 text-[11.5px] font-semibold text-white disabled:opacity-40">
            Send
          </button>
        </div>
        <p className="mt-1 text-[9.5px] text-v2-muted">
          Answers use only loaded data · figures are computed, never estimated.
        </p>
      </div>
    </div>
  );
}
