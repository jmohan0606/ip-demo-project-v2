"use client";
/**
 * Transactions drill-down (UI_SPEC §7). The target of every clickable pivot
 * figure and evidence "Open all in Transactions" link. Accepts
 * ?advisor=&month=&group=. The footer total is the API's credited_total —
 * its equality with the pivot cell the user clicked from is the point of
 * this screen.
 */
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  type HierarchyNode,
  type TransactionRow,
  v2Api,
} from "@/lib/api/v2";
import { fmtDate, fmtMoney, monthShort } from "@/lib/v2/format";
import { useV2Context } from "@/components/layout/v2-shell";
import { AsyncBoundary, LoadingState } from "@/components/patterns/async-state";

const PAGE_SIZE = 200;

type SortKey =
  | "trade_ref_no"
  | "trade_dt"
  | "product_name"
  | "group_id"
  | "account_no"
  | "rev_nature"
  | "credited_amt"
  | "split_pct"
  | "file_key";

const COLUMNS: { key: SortKey; label: string; align?: "right" }[] = [
  { key: "trade_ref_no", label: "Trade ref" },
  { key: "trade_dt", label: "Trade date" },
  { key: "product_name", label: "Product" },
  { key: "group_id", label: "Group" },
  { key: "account_no", label: "Account" },
  { key: "rev_nature", label: "Type" },
  { key: "credited_amt", label: "Credited", align: "right" },
  { key: "split_pct", label: "Split %", align: "right" },
  { key: "file_key", label: "Source feed" },
];

function Chip({ label, onRemove }: { label: string; onRemove?: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-v2-header-bg px-2.5 py-1 text-[10.5px] font-semibold text-v2-navy">
      {label}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove filter ${label}`}
          className="text-v2-muted hover:text-v2-negative"
        >
          ×
        </button>
      )}
    </span>
  );
}

function TransactionsView() {
  const params = useSearchParams();
  const ctx = useV2Context();

  const paramAdvisor = params.get("advisor") ?? "";
  const paramMonth = params.get("month");
  const paramGroup = params.get("group");

  // null = "no override yet — use the URL param, else the context default".
  const [monthOverride, setMonthOverride] = useState<string | null>(null);
  const [groupOverride, setGroupOverride] = useState<string | null>(null);

  const advisorId = paramAdvisor || ctx.advisorId || "";
  const monthId = monthOverride ?? paramMonth ?? ctx.toMonth;
  const groupId = groupOverride ?? paramGroup ?? "";

  const [groups, setGroups] = useState<HierarchyNode[]>([]);
  const [rows, setRows] = useState<TransactionRow[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [creditedTotal, setCreditedTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "trade_dt",
    dir: "asc",
  });
  const [page, setPage] = useState(0);

  useEffect(() => {
    let active = true;
    v2Api
      .productHierarchy()
      .then((h) => {
        if (active) setGroups(h.groups);
      })
      .catch(() => {
        /* group dropdown simply stays empty */
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!ctx.loaded || !advisorId || !monthId) return;
    let active = true;
    setLoading(true);
    setError(null);
    v2Api
      .transactions(advisorId, monthId, groupId)
      .then((res) => {
        if (!active) return;
        setRows(res.transactions);
        setRowCount(res.row_count);
        setCreditedTotal(res.credited_total);
        ctx.reportTier(res.served_by_tier);
        setPage(0);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Failed to load transactions.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.loaded, advisorId, monthId, groupId, retryKey]);

  const groupName = (id: string): string =>
    groups.find((g) => g.group_id === id)?.group_name ?? id;

  const sorted = useMemo(() => {
    const copy = [...rows];
    const { key, dir } = sort;
    copy.sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      let cmp: number;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av ?? "").localeCompare(String(bv ?? ""));
      return dir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sort]);

  const paginated = sorted.length > PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageRows = paginated
    ? sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
    : sorted;

  const toggleSort = (key: SortKey) => {
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" },
    );
    setPage(0);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[16px] font-semibold text-v2-text">Transactions</h1>
        <p className="text-[11.5px] text-v2-muted">
          Source transactions — every pivot figure and evidence record resolves to these rows.
        </p>
      </div>

      <div className="rounded-[3px] border border-v2-border bg-v2-card">
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2 border-b border-v2-border px-4 py-2.5">
          <span className="text-[10.5px] font-semibold uppercase tracking-[0.5px] text-v2-muted">
            Filters
          </span>
          <Chip label={`Advisor ${advisorId || "—"}`} />
          {monthId && (
            <Chip
              label={`Month ${monthShort(monthId)}`}
              onRemove={monthId !== ctx.toMonth ? () => setMonthOverride(ctx.toMonth) : undefined}
            />
          )}
          {groupId && (
            <Chip label={`Group ${groupName(groupId)}`} onRemove={() => setGroupOverride("")} />
          )}
          <div className="ml-auto flex items-center gap-2">
            <label className="text-[11px] text-v2-muted" htmlFor="txn-month">
              Month
            </label>
            <select
              id="txn-month"
              value={monthId}
              onChange={(e) => {
                setMonthOverride(e.target.value);
                setPage(0);
              }}
              className="h-6 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]"
            >
              {ctx.months.map((m) => (
                <option key={m.month_id} value={m.month_id}>
                  {monthShort(m.month_id)}
                </option>
              ))}
            </select>
            <label className="text-[11px] text-v2-muted" htmlFor="txn-group">
              Group
            </label>
            <select
              id="txn-group"
              value={groupId}
              onChange={(e) => {
                setGroupOverride(e.target.value);
                setPage(0);
              }}
              className="h-6 rounded-[3px] border border-v2-border bg-white px-1.5 text-[11.5px]"
            >
              <option value="">All groups</option>
              {groups.map((g) => (
                <option key={g.group_id} value={g.group_id ?? ""}>
                  {g.group_name ?? g.group_id}
                </option>
              ))}
            </select>
          </div>
        </div>

        <AsyncBoundary
          loading={loading}
          error={error}
          onRetry={() => setRetryKey((k) => k + 1)}
          loadingLabel="Loading transactions…"
        >
          {rows.length === 0 ? (
            <div className="px-4 py-10 text-center text-[11.5px] text-v2-muted">
              No transactions match the current filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[11.5px]">
                <thead>
                  <tr className="bg-v2-header-bg">
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        className={`px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.5px] ${
                          col.align === "right" ? "text-right" : "text-left"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(col.key)}
                          className="uppercase hover:text-v2-link"
                        >
                          {col.label}
                          {sort.key === col.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((t) => (
                    <tr key={t.txn_id} className="border-b border-v2-border-subtle hover:bg-v2-sub-bg">
                      <td className="px-3 py-1.5 font-mono text-[11px] text-v2-link">{t.trade_ref_no}</td>
                      <td className="px-3 py-1.5">{fmtDate(t.trade_dt)}</td>
                      <td className="px-3 py-1.5">{t.product_name}</td>
                      <td className="px-3 py-1.5">{groupName(t.group_id)}</td>
                      <td className="px-3 py-1.5 font-mono text-[11px]">{t.account_no}</td>
                      <td className="px-3 py-1.5">{t.rev_nature}</td>
                      <td className={`px-3 py-1.5 text-right ${t.credited_amt < 0 ? "text-v2-negative" : ""}`}>
                        {fmtMoney(t.credited_amt)}
                      </td>
                      <td className="px-3 py-1.5 text-right">{Math.round((t.split_pct ?? 0) * 100)}%</td>
                      <td className="px-3 py-1.5 font-mono text-[11px] text-v2-muted">{t.file_key}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-v2-border px-4 py-2.5">
            <span className="text-[11.5px] font-semibold text-v2-text">
              {rowCount} transactions · Credited revenue {fmtMoney(creditedTotal)}
            </span>
            {paginated && (
              <div className="flex items-center gap-2 text-[11.5px] text-v2-muted">
                <button
                  type="button"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="rounded-[3px] border border-v2-border px-2 py-0.5 disabled:opacity-40"
                >
                  ‹ Prev
                </button>
                <span>
                  Page {page + 1} of {pageCount}
                </span>
                <button
                  type="button"
                  disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  className="rounded-[3px] border border-v2-border px-2 py-0.5 disabled:opacity-40"
                >
                  Next ›
                </button>
              </div>
            )}
          </div>
        </AsyncBoundary>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading transactions…" />}>
      <TransactionsView />
    </Suspense>
  );
}
