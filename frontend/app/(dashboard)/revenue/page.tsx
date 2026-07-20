import { PageHeader } from "@/components/patterns/page-header";

export default function Page() {
  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Results" title="Revenue" subtitle="Revenue overview." />
      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-slate-500">
        Not in this build — the Revenue overview arrives in a later phase. Use Trends and AI Insights for month-over-month analysis.
      </div>
    </div>
  );
}
