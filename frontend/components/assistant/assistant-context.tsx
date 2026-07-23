"use client";
/**
 * Ask iPerform — shared conversation state (FIX_SPEC_R7 B1/B2).
 *
 * Lives at the SHELL level so the conversation persists across navigation
 * (Trends -> AI Insights -> Transactions keeps the panel open and follows the
 * screen context). ONE state store serves BOTH presentations — the overlay
 * panel and the full-page /ask view — so the logic is never forked.
 *
 * Screen state seeds the context on every send (advisor + loaded transition);
 * Pin freezes it (A4). The open/collapsed flag and current conversation id
 * survive a reload via localStorage + server-side rehydration (A5).
 */
import {
  ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import {
  type AskResponse, type ConversationRow, type MessageRow, type ScreenContext,
  v2Api,
} from "@/lib/api/v2";

/** Per-answer extras that only exist on live responses (not rehydrated). */
export interface TurnExtras {
  suggestions: string[];
  links: { label: string; href: string }[];
  evidence_driver_id: string;
  redaction_note?: string;
}

interface AssistantState {
  open: boolean;
  setOpen: (open: boolean) => void;
  conversationId: string;
  title: string;
  messages: MessageRow[];
  extras: Record<string, TurnExtras>; // message_id -> extras
  sending: boolean;
  error: string | null;
  pinned: ScreenContext | null;
  setPinned: (pin: ScreenContext | null) => void;
  screen: ScreenContext;
  send: (text: string) => Promise<void>;
  newConversation: () => void;
  openConversation: (conversationId: string) => Promise<void>;
  conversations: ConversationRow[];
  refreshConversations: () => Promise<void>;
  servedByTier: number | null;
}

const AssistantContext = createContext<AssistantState | null>(null);

export function useAssistant(): AssistantState {
  const ctx = useContext(AssistantContext);
  if (!ctx) throw new Error("useAssistant outside AssistantProvider");
  return ctx;
}

export function AssistantProvider({ children, advisorId, fromMonth, toMonth }: {
  children: ReactNode;
  // screen state passed down from the shell (avoids a shell<->assistant import cycle)
  advisorId: string | null;
  fromMonth: string;
  toMonth: string;
}) {
  const [open, setOpenState] = useState(false);
  const [conversationId, setConversationId] = useState("");
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [extras, setExtras] = useState<Record<string, TurnExtras>>({});
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pinned, setPinned] = useState<ScreenContext | null>(null);
  const [conversations, setConversations] = useState<ConversationRow[]>([]);
  const [servedByTier, setServedByTier] = useState<number | null>(null);

  // The screen context that seeds resolution: the advisor bar's selection and
  // the latest loaded transition (A4 — "why did this drop?" resolves).
  const screen = useMemo<ScreenContext>(() => {
    const months = [fromMonth, toMonth].filter(Boolean).sort();
    return {
      advisor_sid: advisorId ?? undefined,
      from_month: months.length > 1 ? months[months.length - 2] : undefined,
      to_month: months[months.length - 1],
    };
  }, [advisorId, fromMonth, toMonth]);

  const setOpen = useCallback((next: boolean) => {
    setOpenState(next);
    window.localStorage.setItem("v2.assistant.open", next ? "1" : "0");
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const r = await v2Api.assistantConversations();
      setConversations(r.conversations);
      setServedByTier(r.served_by_tier);
    } catch {
      /* history list is non-critical; the panel still works */
    }
  }, []);

  const openConversation = useCallback(async (id: string) => {
    setError(null);
    try {
      const r = await v2Api.assistantConversation(id);
      setConversationId(id);
      setMessages(r.messages);
      setTitle(r.conversation?.title ?? "");
      setExtras({});
      setServedByTier(r.served_by_tier);
      window.localStorage.setItem("v2.assistant.cid", id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to open conversation.");
    }
  }, []);

  // Reload restore: reopen the stored conversation (rehydration, A5).
  useEffect(() => {
    setOpenState(window.localStorage.getItem("v2.assistant.open") === "1");
    const cid = window.localStorage.getItem("v2.assistant.cid");
    if (cid) void openConversation(cid);
    void refreshConversations();
  }, [openConversation, refreshConversations]);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || sending) return;
    setSending(true);
    setError(null);
    try {
      const r: AskResponse = await v2Api.assistantAsk({
        text,
        conversation_id: conversationId,
        screen,
        pinned,
      });
      setConversationId(r.conversation.conversation_id);
      setTitle(r.conversation.title);
      window.localStorage.setItem("v2.assistant.cid", r.conversation.conversation_id);
      setMessages((prev) => [...prev, r.user_message, r.assistant_message]);
      setExtras((prev) => ({
        ...prev,
        [r.assistant_message.message_id]: {
          suggestions: r.suggestions,
          links: r.links,
          evidence_driver_id: r.evidence_driver_id,
          redaction_note: r.redaction_note,
        },
      }));
      if (r.served_by_tier != null) setServedByTier(r.served_by_tier);
      void refreshConversations();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The assistant could not answer.");
    } finally {
      setSending(false);
    }
  }, [conversationId, pinned, screen, sending, refreshConversations]);

  const newConversation = useCallback(() => {
    setConversationId("");
    setTitle("");
    setMessages([]);
    setExtras({});
    setError(null);
    window.localStorage.removeItem("v2.assistant.cid");
  }, []);

  const value = useMemo<AssistantState>(() => ({
    open, setOpen, conversationId, title, messages, extras, sending, error,
    pinned, setPinned, screen, send, newConversation, openConversation,
    conversations, refreshConversations, servedByTier,
  }), [open, setOpen, conversationId, title, messages, extras, sending, error,
       pinned, screen, send, newConversation, openConversation, conversations,
       refreshConversations, servedByTier]);

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}
