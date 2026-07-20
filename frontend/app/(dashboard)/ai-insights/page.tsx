import { PageHeader } from "@/components/patterns/page-header";

export default function Page() {
  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Results" title="AI Insights" subtitle="Month-over-month walk with AI commentary — every figure computed from graph data." />
      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-slate-500">
        Built in Phase 6 — chart, commentary cards and monthly walk table.
      </div>
    </div>
  );
}
