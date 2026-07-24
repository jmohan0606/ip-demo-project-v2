"use client";
/**
 * Revenue-Driver glossary (FIX_SPEC_R3 T4-3, rebuilt FIX_SPEC_R8 A3). One
 * dialog listing EVERY revenue driver with its display name, plain-English
 * meaning and how it is computed — rendered from GQ-004 get_driver_causes
 * (phx_dm_v2_driver_cause), NEVER from hardcoded text. The operator renames
 * or re-describes a driver by editing the seed / graph; this component has
 * no driver names of its own. Openable from a "What do these mean?" link on
 * both the AI-Insights and evidence screens. Drivers whose
 * default_data_source is DUMMY carry the DUMMY badge: modelled, awaiting data.
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ProvenanceBadge } from "@/components/patterns/provenance-badge";
import { useDriverCauses } from "@/lib/v2/driver-causes";

export function RevenueDriverGlossaryDialog({ onClose }: { onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { causes, loaded } = useDriverCauses();
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      trigger?.focus?.();
    };
  }, [onClose]);

  // S-A1 — portal to document.body: the trigger link lives inside a <p> on
  // two screens, and a dialog rendered as its sibling puts an <h2> inside
  // that <p> (invalid HTML → 8 hydration errors). The portal guarantees the
  // dialog is never a DOM descendant of its trigger. The dialog only mounts
  // after a click, so document is always available.
  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-10"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Revenue-driver glossary"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-[880px] overflow-y-auto rounded-[3px] bg-white font-v2 text-v2-text shadow-2xl outline-none"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-v2-border bg-white px-6 py-4">
          <div>
            <h2 className="text-[15px] font-semibold">Revenue Drivers — what they mean</h2>
            <p className="mt-0.5 text-[11.5px] text-v2-muted">
              Every driver the attribution can name, with its meaning and how it is computed.
              All contributions are deterministic — computed from graph data, never by a model.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close glossary"
            className="ml-3 flex h-7 w-7 shrink-0 items-center justify-center rounded-[3px] text-[16px] text-v2-muted hover:bg-v2-header-bg hover:text-v2-text"
          >
            ×
          </button>
        </div>
        <div className="px-6 py-4">
          <table className="w-full border-collapse text-[11.5px]">
            <thead>
              <tr className="bg-v2-header-bg text-left">
                <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">Revenue Driver</th>
                <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">What it means</th>
                <th className="px-3 py-[7px] text-[10px] font-semibold uppercase tracking-[0.5px]">How it is computed</th>
              </tr>
            </thead>
            <tbody>
              {causes.map((row) => (
                <tr key={row.cause_id} className="border-b border-v2-border-subtle align-top">
                  <td className="whitespace-nowrap px-3 py-2.5 font-semibold">
                    {row.display_name}
                    {row.default_data_source === "DUMMY" && (
                      <ProvenanceBadge value="DUMMY" className="ml-1.5" />
                    )}
                  </td>
                  <td className="px-3 py-2.5">{row.description}</td>
                  <td className="px-3 py-2.5 text-v2-muted">{row.computation}</td>
                </tr>
              ))}
              {!loaded && (
                <tr>
                  <td colSpan={3} className="px-3 py-4 text-center text-v2-muted">
                    Loading driver definitions from the graph…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="mt-3 text-[10.5px] italic text-v2-faint">
            Drivers marked DUMMY are illustrative placeholders — they contribute $0 until their
            data source is supplied, and are never presented as established fact.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** The "What do these mean?" link that opens the glossary. */
export function GlossaryLink({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`text-[11px] text-v2-link hover:underline ${className}`}
      >
        What do these mean?
      </button>
      {open && <RevenueDriverGlossaryDialog onClose={() => setOpen(false)} />}
    </>
  );
}
