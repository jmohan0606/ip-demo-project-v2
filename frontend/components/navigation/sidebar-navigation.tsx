"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BadgeDollarSign, BarChart3, BookOpenCheck, Bot, BrainCircuit, ChevronLeft, ChevronRight, Contact, Database, FileText, GitBranch, LayoutDashboard, LineChart, Network, PlayCircle, PlugZap, Radar, Receipt, ShieldCheck, SlidersHorizontal, Sparkles, Target, TrendingUp, UploadCloud, UserCircle, Users, Workflow } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { navigationGroups, navigationItems } from "@/lib/navigation";
import { useShellContext } from "@/components/layout/shell-context";

const iconMap = { Activity, LayoutDashboard, LineChart, BarChart3, Users, Target, SlidersHorizontal, Sparkles, TrendingUp, Bot, BookOpenCheck, Network, GitBranch, BrainCircuit, Workflow, UploadCloud, ShieldCheck, Database, FileText, Radar, Contact, UserCircle, Receipt, PlayCircle, BadgeDollarSign, PlugZap };

export function SidebarNavigation({ collapsed, onToggle }: { collapsed?: boolean; onToggle?: () => void }) {
  const pathname = usePathname();
  const context = useShellContext();
  return (
    <aside className={cn("hidden shrink-0 border-r border-border/70 bg-slate-950 text-white lg:flex lg:flex-col transition-all", collapsed ? "w-[72px]" : "w-[238px]")}>
      <div className="flex items-center justify-between border-b border-white/10 p-3">
        {!collapsed && <div><div className="text-base font-black">iPerform</div><div className="text-[10px] text-slate-300">Insights & Coaching</div></div>}
        <Button variant="ghost" size="icon" onClick={onToggle} className="text-white hover:bg-white/10">{collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}</Button>
      </div>
      <nav className="min-h-0 flex-1 space-y-3 overflow-y-auto p-2">
        {navigationGroups.map((group) => (
          <div key={group}>
            {!collapsed && <div className="mb-1 px-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-400">{group}</div>}
            <div className="space-y-1">
              {navigationItems.filter((item) => item.group === group).map((item) => {
                const Icon = iconMap[item.iconName as keyof typeof iconMap] ?? LayoutDashboard;
                const active = pathname === item.href || (pathname === "/" && item.href === "/dashboard");
                return (
                  <Link key={item.id} href={item.href} title={item.description} className={cn("flex items-center gap-2 rounded-lg px-2 py-2 text-[12px] font-medium text-slate-300 transition hover:bg-white/10 hover:text-white", active && "bg-blue-600 text-white shadow-lg")}>
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span className="min-w-0 flex-1 truncate">{item.label}</span>}
                    {!collapsed && item.status === "new" && <Badge variant="success">New</Badge>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      {!collapsed && (
        <div className="m-2 rounded-xl border border-white/10 bg-white/5 p-3 text-[11px]">
          <div className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400">Active View</div>
          <dl className="space-y-1">
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-400">Persona</dt>
              <dd className="font-semibold text-white">{context.persona}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-400">Scope</dt>
              <dd className="truncate font-semibold text-white" title={`${context.scopeLabel} (${context.scopeType})`}>
                {context.scopeLabel || context.scopeId} <span className="text-slate-400">· {context.scopeType}</span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-slate-400">Period</dt>
              <dd className="font-semibold text-white">{context.period}</dd>
            </div>
          </dl>
        </div>
      )}
    </aside>
  );
}
