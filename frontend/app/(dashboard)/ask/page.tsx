"use client";
/**
 * Ask iPerform — full-page presentation (FIX_SPEC_R7 B2, mockup
 * docs/ui/reference/roadmap/01_conversational_assistant.png).
 *
 * The SAME AssistantPanel the overlay uses (one component, two presentations
 * — logic never forked), plus the left conversation rail grouped
 * Today / Yesterday / date over the ASSISTANT_HISTORY_DAYS window.
 */
import { useEffect, useMemo } from "react";
import { TierPill, useV2Context } from "@/components/layout/v2-shell";
import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { useAssistant } from "@/components/assistant/assistant-context";
import { type ConversationRow } from "@/lib/api/v2";

function dayGroup(iso: string): string {
  const d = new Date(iso.replace(" ", "T") + "Z");
  const now = new Date();
  const days = Math.floor(
    (new Date(now).setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short" }).toUpperCase();
}

export default function AskPage() {
  const { advisor, months } = useV2Context();
  const {
    conversationId, conversations, openConversation, newConversation,
    refreshConversations, servedByTier,
  } = useAssistant();

  useEffect(() => { void refreshConversations(); }, [refreshConversations]);

  const grouped = useMemo(() => {
    const out: [string, ConversationRow[]][] = [];
    for (const c of conversations) {
      const g = dayGroup(c.last_message_at);
      const last = out[out.length - 1];
      if (last && last[0] === g) last[1].push(c);
      else out.push([g, [c]]);
    }
    return out;
  }, [conversations]);

  const range = months.length
    ? `${months[0].month_name}–${months[months.length - 1].month_name}`
    : "";

  return (
    <div className="-mx-6 -my-4 flex h-[calc(100vh-6rem)] min-h-0">
      {/* left rail — conversations grouped by day */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-v2-border bg-white">
        <div className="flex items-center justify-between border-b border-v2-border px-4 py-3">
          <div>
            <p className="text-[14px] font-bold text-v2-text">Conversations</p>
            <p className="text-[10.5px] text-v2-muted">Last 10 days · stored in graph</p>
          </div>
          <button type="button" onClick={newConversation}
            className="rounded bg-v2-navy px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-v2-navy-dark">
            + New
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto py-2">
          {conversations.length === 0 && (
            <p className="px-4 py-2 text-[11.5px] text-v2-muted">
              No conversations yet — ask your first question.
            </p>
          )}
          {grouped.map(([group, rows]) => (
            <div key={group}>
              <p className="px-4 pb-1 pt-2 text-[9.5px] font-semibold uppercase tracking-wide text-v2-muted">
                {group}
              </p>
              {rows.map((c) => (
                <button key={c.conversation_id} type="button"
                  onClick={() => void openConversation(c.conversation_id)}
                  className={`block w-full border-l-2 px-4 py-1.5 text-left ${
                    c.conversation_id === conversationId
                      ? "border-v2-navy bg-v2-header-bg"
                      : "border-transparent hover:bg-v2-header-bg"}`}>
                  <span className="block truncate text-[12px] text-v2-text">{c.title}</span>
                  <span className="text-[10px] text-v2-muted">{c.message_count} messages</span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <p className="border-t border-v2-border px-4 py-2 text-[9.5px] italic text-v2-muted">
          Conversations older than 10 days are archived.
        </p>
      </aside>

      {/* main conversation area — the SAME component as the overlay */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-v2-border bg-white px-5 py-3">
          <div>
            <p className="text-[15px] font-bold text-v2-text">Ask iPerform</p>
            <p className="text-[11px] text-v2-muted">
              Answers come from your loaded revenue data{range ? ` — ${range}` : ""}.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {advisor && (
              <span className="rounded-full bg-v2-header-bg px-3 py-1 text-[10.5px] text-v2-navy">
                Scope: {advisor.advisor_sid}
              </span>
            )}
            {servedByTier != null && <TierPill />}
          </div>
        </div>
        <AssistantPanel variant="page" />
      </div>
    </div>
  );
}
