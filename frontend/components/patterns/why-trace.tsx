"use client";

import { useEffect, useRef, useState } from "react";
import { HelpCircle, ArrowUpRight } from "lucide-react";
import { colors } from "@/styles/tokens";

export interface TraceInfo {
  source: string;
  computation: string;
  link?: string | null;
  linkLabel?: string;
}

/**
 * REQ-2 — "no dead numbers": a small ⓘ affordance next to any figure that opens
 * a popover explaining exactly which real computation / model / traversal
 * produced it, with a link to the screen where the full lineage lives
 * (Predictions contributions, Explainability trace, Revenue analytics, …).
 */
export function WhyTrace({ trace, label = "How was this computed?" }: { trace: TraceInfo; label?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      {open && (
        <div
          className="absolute right-0 top-6 z-50 w-72 rounded-xl border bg-white p-3 text-left shadow-lg"
          style={{ borderColor: colors.surface.border }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Why this number</div>
          <div className="mt-1 text-[11px] leading-snug text-foreground">{trace.computation}</div>
          <div className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Source</div>
          <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{trace.source}</div>
          {trace.link && (
            <a
              href={trace.link}
              className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
            >
              {trace.linkLabel ?? "Open the full model / lineage view"} <ArrowUpRight className="h-3 w-3" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
