import { normalizeSeverity, severity } from "@/styles/tokens";

export function SeverityBadge({ value }: { value: string | null | undefined }) {
  const level = normalizeSeverity(value);
  const tone = severity[level];
  return (
    <span
      className="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.06em]"
      style={{ color: tone.fg, backgroundColor: tone.bg, borderColor: tone.border }}
    >
      {tone.label}
    </span>
  );
}
