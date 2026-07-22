"use client";
/**
 * Revenue-Driver glossary (FIX_SPEC_R3 T4-3). One dialog listing EVERY revenue
 * driver with its display name, plain-English meaning and how it is computed.
 * Openable from a "What do these mean?" link on both the AI-Insights and
 * evidence screens. The table text is the single source shared with the
 * SOLUTION_GUIDE calculation chapter — change it there and here together.
 * Market / Net Flow carry the DUMMY badge: modelled, awaiting data.
 */
import { useEffect, useRef, useState } from "react";
import { ProvenanceBadge } from "@/components/patterns/provenance-badge";

interface GlossaryRow {
  name: string;
  meaning: string;
  computed: string;
  illustrative?: boolean;
}

export const REVENUE_DRIVER_GLOSSARY: GlossaryRow[] = [
  {
    name: "New Account",
    meaning: "Revenue from accounts active this month that were not active last month",
    computed:
      "Accounts with credited transactions in the current month but none in the prior month, evaluated at advisor level so a mere product switch is not miscounted as a new account. Contribution = Σ credited revenue of those accounts.",
  },
  {
    name: "Lost Account",
    meaning: "Revenue lost from accounts active last month but not this month",
    computed:
      "Mirror of New Account: accounts credited last month, none this month. Contribution = −(their prior-month credited revenue).",
  },
  {
    name: "One-Time",
    meaning: "Non-recurring items such as syndicate allocations, new issues, referrals",
    computed:
      "Change in revenue tagged one-time (from file_key and trade_description) between the two months.",
  },
  {
    name: "Eligibility",
    meaning: "Revenue moving into or out of credited status",
    computed:
      "Change in non-credited revenue for the group (e.g. a household crossing the minimum-household threshold moves revenue from credited to non-credited). Contribution = −(Δ non-credited).",
  },
  {
    name: "Late Processing",
    meaning: "Revenue excluded because it processed more than 90 days after the trade",
    computed:
      "Change in revenue failing the 90-day rule (proc_dt − trade_dt > 90). Contribution = −(Δ late-excluded).",
  },
  {
    name: "Excluded Bookings",
    meaning: "Revenue moving into or out of an excluded state (e.g. a deleted booking)",
    computed:
      "Change in revenue carrying an excluding reason code (e.g. 9X deleted) between the two months. Contribution = −(Δ excluded).",
  },
  {
    name: "Timing",
    meaning: "Quarterly or periodic billing landing in one month but not the other",
    computed:
      "Revenue for a group present in one month's billing cycle and absent the other, not already claimed by One-Time.",
  },
  {
    name: "Fee Rate",
    meaning: "Change in the effective fee rate charged",
    computed:
      "Prior-month asset proxy × (this month's avg rate − last month's), in bps.",
  },
  {
    name: "Discount",
    meaning: "Change in fee discounting / concessions",
    computed:
      "Change in Σ discount amount and in the count of discounted transactions.",
  },
  {
    name: "Billable Days",
    meaning: "A different number of billing days between the two months",
    computed:
      "Recurring/fee-based revenue × (Δ billable days ÷ prior billable days). Derived from a business-day calendar.",
  },
  {
    name: "Volume",
    meaning: "More or fewer transactions at similar rates",
    computed:
      "(Δ transaction count) × prior-month average transaction value, for transaction-based groups.",
  },
  {
    name: "Product Mix",
    meaning: "The residual shift between products at different rates",
    computed:
      "Whatever remains after all named drivers are attributed. A large value here means a driver may be missing.",
  },
  {
    name: "Clawback",
    meaning: "Reversals / chargebacks (negative revenue)",
    computed: "Change in the sum of negative credited amounts between the months.",
  },
  {
    name: "Market",
    meaning: "Movement in asset values (not yet sourced — shown as illustrative)",
    computed:
      "Requires an index-return feed not currently available. Modelled, flagged, contributes $0 until data is supplied.",
    illustrative: true,
  },
  {
    name: "Net Flow",
    meaning: "Client inflows and outflows (not yet sourced — shown as illustrative)",
    computed:
      "Requires a flows feed (current source stops Jan 2026). Modelled, flagged, contributes $0 until data is supplied.",
    illustrative: true,
  },
];

export function RevenueDriverGlossaryDialog({ onClose }: { onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
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

  return (
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
              {REVENUE_DRIVER_GLOSSARY.map((row) => (
                <tr key={row.name} className="border-b border-v2-border-subtle align-top">
                  <td className="whitespace-nowrap px-3 py-2.5 font-semibold">
                    {row.name}
                    {row.illustrative && <ProvenanceBadge value="DUMMY" className="ml-1.5" />}
                  </td>
                  <td className="px-3 py-2.5">{row.meaning}</td>
                  <td className="px-3 py-2.5 text-v2-muted">{row.computed}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[10.5px] italic text-v2-faint">
            Drivers marked DUMMY are illustrative placeholders — they contribute $0 until their
            data source is supplied, and are never presented as established fact.
          </p>
        </div>
      </div>
    </div>
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
