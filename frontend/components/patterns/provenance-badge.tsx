import { type ProvenanceFlag, provenanceStyle } from "@/components/design-system/design-tokens";

/** Provenance badge — every non-real value carries one (ABSOLUTE RULE 3).
 * DUMMY / ASSUMED explain themselves on hover (what data would make it real). */
export function ProvenanceBadge({ value, className = "" }: { value: string; className?: string }) {
  const flag = (["REAL", "DERIVED", "ASSUMED", "DUMMY"].includes(value) ? value : "DUMMY") as ProvenanceFlag;
  const style = provenanceStyle[flag];
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase ${className}`}
      style={{ color: style.color, backgroundColor: style.bg }}
      title={style.tooltip}
    >
      {flag}
    </span>
  );
}

/** Cause tag — deliberately quieter than the provenance badge. */
export function CauseTag({ causeId, className = "" }: { causeId: string; className?: string }) {
  return (
    <span
      className={`inline-block rounded-full bg-v2-header-bg px-2 py-0.5 text-[9.5px] font-semibold uppercase text-v2-navy ${className}`}
    >
      {causeId.replace(/_/g, "-")}
    </span>
  );
}
