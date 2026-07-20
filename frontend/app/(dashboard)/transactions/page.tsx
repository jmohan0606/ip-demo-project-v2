import { PageHeader } from "@/components/patterns/page-header";

export default function Page() {
  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Results" title="Transactions" subtitle="Source transactions — the drill-down target for every pivot cell." />
      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-slate-500">
        Built in Phase 6 — transactions drill-down.
      </div>
    </div>
  );
}
