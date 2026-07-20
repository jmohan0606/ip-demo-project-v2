import { PageHeader } from "@/components/patterns/page-header";

export default function Page() {
  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Results" title="Trends" subtitle="Credited revenue by product hierarchy per month, and month-over-month change." />
      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-slate-500">
        Built in Phase 6 — Trends pivot and MoM change tables.
      </div>
    </div>
  );
}
