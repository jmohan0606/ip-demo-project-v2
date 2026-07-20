"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Bell, UserRound, Home, FileText, X } from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { useShellContext } from "@/components/layout/shell-context";
import { colors } from "@/styles/tokens";

interface SearchResult { type: string; id: string; label: string; sublabel: string; href: string }
interface Notification { severity: string; type: string; title: string; detail: string; advisor_id: string; href: string }

const TYPE_ICON: Record<string, typeof UserRound> = { Advisor: UserRound, Household: Home, Document: FileText };
const SEV: Record<string, string> = { critical: colors.negative, urgent: "#EA580C", attention: colors.warning };

/** Section 10 — real global search + real notifications (the two flagged header
 * icons given real purpose). Search hits /search/global; the bell hits
 * /search/notifications (a real feed from live data). */
export function HeaderSearchNotifications() {
  const router = useRouter();
  const shell = useShellContext();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiClient.get<{ items: Notification[] }>("/search/notifications").then((r) => setNotifs(r.items)).catch(() => setNotifs([]));
  }, [shell.refreshNonce]);

  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    const t = setTimeout(() => {
      apiClient.get<{ results: SearchResult[] }>(`/search/global?q=${encodeURIComponent(q)}`).then((r) => setResults(r.results)).catch(() => setResults([]));
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => { if (boxRef.current && !boxRef.current.contains(e.target as Node)) { setSearchOpen(false); setBellOpen(false); } };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (r: SearchResult) => {
    if (r.type === "Advisor") shell.setScope("Advisor", r.id, r.label);
    setSearchOpen(false); setQ("");
    router.push(r.href);
  };

  return (
    <div ref={boxRef} className="relative flex items-center gap-2">
      {/* Global search */}
      <div className="relative">
        <div className="flex h-8 items-center gap-1.5 rounded-lg border border-border bg-background px-2">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); setSearchOpen(true); }}
            onFocus={() => setSearchOpen(true)}
            placeholder="Search advisors, households, docs…"
            className="w-44 bg-transparent text-[12px] outline-none xl:w-56"
          />
          {q && <button onClick={() => { setQ(""); setResults([]); }}><X className="h-3 w-3 text-muted-foreground" /></button>}
        </div>
        {searchOpen && q.trim() && (
          <div className="absolute right-0 top-9 z-50 w-80 rounded-lg border bg-white shadow-lg" style={{ borderColor: colors.surface.border }}>
            {results.length === 0 ? (
              <div className="px-3 py-3 text-[12px] text-muted-foreground">No matches for “{q}”.</div>
            ) : results.map((r) => {
              const Icon = TYPE_ICON[r.type] ?? FileText;
              return (
                <button key={`${r.type}-${r.id}`} onClick={() => pick(r)} className="flex w-full items-center gap-2 border-b px-3 py-2 text-left last:border-0 hover:bg-muted/50" style={{ borderColor: colors.surface.border }}>
                  <Icon className="h-3.5 w-3.5 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-semibold">{r.label}</div>
                    <div className="truncate text-[10px] text-muted-foreground">{r.type} · {r.sublabel}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Notifications bell */}
      <div className="relative">
        <button onClick={() => setBellOpen((v) => !v)} className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background" title="Notifications">
          <Bell className="h-3.5 w-3.5" />
          {notifs.length > 0 && <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-bold text-white" style={{ background: colors.negative }}>{notifs.length}</span>}
        </button>
        {bellOpen && (
          <div className="absolute right-0 top-9 z-50 w-96 rounded-lg border bg-white shadow-lg" style={{ borderColor: colors.surface.border }}>
            <div className="flex items-center justify-between border-b px-3 py-2" style={{ borderColor: colors.surface.border }}>
              <span className="text-[12px] font-bold">Notifications ({notifs.length})</span>
              <span className="text-[10px] text-muted-foreground">live from advisor risk & CRM data</span>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {notifs.length === 0 ? (
                <div className="px-3 py-3 text-[12px] text-muted-foreground">No active alerts.</div>
              ) : notifs.map((n, i) => (
                <button key={i} onClick={() => { if (n.advisor_id) shell.setScope("Advisor", n.advisor_id, n.advisor_id); setBellOpen(false); router.push(n.href); }} className="flex w-full items-start gap-2 border-b px-3 py-2 text-left last:border-0 hover:bg-muted/50" style={{ borderColor: colors.surface.border }}>
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: SEV[n.severity] ?? colors.text.muted }} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-semibold">{n.title}</div>
                    <div className="text-[11px] text-muted-foreground">{n.detail}</div>
                  </div>
                  <span className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase" style={{ color: SEV[n.severity], background: `${SEV[n.severity]}18` }}>{n.type}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
