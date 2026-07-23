"use client";
/**
 * Ask iPerform — overlay presentation (FIX_SPEC_R7 B1, mockup
 * docs/ui/reference/roadmap/04_chat_overlay.png).
 *
 * OVERLAY, not push: content keeps its full-width layout; the panel floats at
 * the right edge (~420px) with a shadow. It persists across navigation (state
 * lives in AssistantProvider at the shell level) and COLLAPSES to a floating
 * button rather than closing, so returning is one click and context is kept.
 * ⤢ expands into /ask — the full-page presentation of the SAME component.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { useAssistant } from "@/components/assistant/assistant-context";

function groupLabel(iso: string): string {
  const d = new Date(iso.replace(" ", "T") + "Z");
  const today = new Date();
  const days = Math.floor((today.setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short" });
}

export function AssistantOverlay() {
  const pathname = usePathname();
  const {
    open, setOpen, title, conversations, openConversation, newConversation,
  } = useAssistant();
  const [historyOpen, setHistoryOpen] = useState(false);

  // The full-page view renders the same component itself — no overlay there.
  if (pathname?.startsWith("/ask")) return null;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Ask iPerform"
        className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-v2-navy text-[13px] font-bold text-white shadow-lg hover:bg-v2-navy-dark print:hidden"
      >
        iP
      </button>
    );
  }

  return (
    <aside
      aria-label="Ask iPerform"
      className="fixed inset-y-0 right-0 z-40 flex w-[420px] max-w-full flex-col border-l border-v2-border bg-v2-page shadow-[-8px_0_24px_rgba(15,40,80,0.18)] print:hidden"
    >
      {/* header */}
      <div className="flex items-center gap-2 border-b border-v2-border bg-white px-3 py-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-v2-navy text-[10px] font-bold text-white">iP</span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold leading-tight text-v2-text">Ask iPerform</p>
          <p className="truncate text-[10.5px] leading-tight text-v2-muted">{title || "New conversation"}</p>
        </div>
        <div className="relative">
          <button type="button" onClick={() => setHistoryOpen((v) => !v)}
            className="rounded px-1.5 py-1 text-[11px] text-v2-muted hover:bg-v2-header-bg hover:text-v2-navy"
            aria-label="Conversation history" aria-expanded={historyOpen}>
            ⌄ History
          </button>
          {historyOpen && (
            <div className="absolute right-0 top-8 z-50 max-h-80 w-72 overflow-y-auto rounded-md border border-v2-border bg-white py-1 shadow-lg">
              <button type="button"
                onClick={() => { newConversation(); setHistoryOpen(false); }}
                className="block w-full px-3 py-1.5 text-left text-[11.5px] font-semibold text-v2-navy hover:bg-v2-header-bg">
                + New conversation
              </button>
              {conversations.length === 0 && (
                <p className="px-3 py-2 text-[11px] text-v2-muted">No conversations in the last 10 days.</p>
              )}
              {conversations.map((c) => (
                <button key={c.conversation_id} type="button"
                  onClick={() => { void openConversation(c.conversation_id); setHistoryOpen(false); }}
                  className="block w-full px-3 py-1.5 text-left hover:bg-v2-header-bg">
                  <span className="block truncate text-[11.5px] text-v2-text">{c.title}</span>
                  <span className="text-[10px] text-v2-muted">
                    {groupLabel(c.last_message_at)} · {c.message_count} messages
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        <Link href="/ask" aria-label="Expand to full page"
          className="rounded px-1.5 py-1 text-[13px] text-v2-muted hover:bg-v2-header-bg hover:text-v2-navy">
          ⤢
        </Link>
        <button type="button" onClick={() => setOpen(false)} aria-label="Collapse Ask iPerform"
          className="rounded px-1.5 py-1 text-[13px] text-v2-muted hover:bg-v2-header-bg hover:text-v2-navy">
          ✕
        </button>
      </div>
      <AssistantPanel variant="overlay" />
    </aside>
  );
}
