import { colors } from "@/styles/tokens";

/** Pill row linking an AI output to the artifacts that produced it —
 * the visible face of the persisted lineage chain. */
export function EvidenceTracePills({ items }: { items: Array<{ kind: string; id: string | null | undefined }> }) {
  const present = items.filter((item) => item.id);
  if (present.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {present.map((item) => (
        <span
          key={`${item.kind}-${item.id}`}
          className="inline-flex max-w-[260px] items-center gap-1 truncate rounded-md border px-1.5 py-0.5 font-mono text-[10px]"
          style={{ borderColor: colors.surface.border, color: colors.text.secondary, backgroundColor: colors.surface.canvas }}
          title={`${item.kind}: ${item.id}`}
        >
          <span className="font-sans font-semibold uppercase tracking-wide" style={{ color: colors.aiAccent }}>
            {item.kind}
          </span>
          {item.id}
        </span>
      ))}
    </div>
  );
}
