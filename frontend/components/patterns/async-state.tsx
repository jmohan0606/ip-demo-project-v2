import type { ReactNode } from "react";
import { AlertTriangle, Loader2, RotateCw } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Shared async-state primitives (UX polish request). ONE cohesive loading /
 * error language for every component that fetches real / AI-generated content,
 * so a slow backend call reads as "work in progress", not "frozen or broken".
 * All styling flows from the design tokens (muted surface, primary accent,
 * negative red) — no ad-hoc per-page spinners.
 */

/** Inline spinner + short label, e.g. "Generating insight…". Centered in its
 * container by default. Use where a full skeleton is overkill (buttons already
 * have their own busy text; this is for content regions). */
export function LoadingState({
  label = "Loading…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center justify-center gap-2 py-8 text-[12px] text-muted-foreground",
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>{label}</span>
    </div>
  );
}

/** Clean "couldn't load — retry" state. Replaces a permanent blank/spinner when
 * a fetch fails. Retry button appears only when an onRetry handler is given. */
export function ErrorState({
  message = "Couldn't load this content.",
  onRetry,
  className,
}: {
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-red-200 bg-red-50/60 py-6 text-center dark:border-red-900/60 dark:bg-red-950/30",
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
      <p className="max-w-[28rem] px-4 text-[12px] text-red-700 dark:text-red-300">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-0.5 inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-white px-2.5 py-1 text-[12px] font-semibold text-red-700 transition-colors hover:bg-red-50 dark:border-red-800 dark:bg-transparent dark:text-red-300 dark:hover:bg-red-950/50"
        >
          <RotateCw className="h-3.5 w-3.5" /> Retry
        </button>
      ) : null}
    </div>
  );
}

/**
 * AsyncBoundary — one place that decides loading vs. error vs. content, so every
 * fetching component renders the same three states the same way.
 *  - loading (and no data yet) → `skeleton` if provided, else a labelled spinner
 *  - error (and no data yet)   → ErrorState with retry
 *  - otherwise                 → children (the real, working content — untouched)
 * Passing `data`-aware `loading`/`error` (i.e. only true when there's nothing to
 * show) lets a background refetch keep showing stale content instead of flashing
 * a skeleton — callers decide by ANDing with `!data`.
 */
export function AsyncBoundary({
  loading,
  error,
  onRetry,
  loadingLabel,
  errorMessage,
  skeleton,
  children,
}: {
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  loadingLabel?: string;
  errorMessage?: string;
  skeleton?: ReactNode;
  children: ReactNode;
}) {
  if (error) return <ErrorState message={errorMessage ?? error} onRetry={onRetry} />;
  if (loading) return <>{skeleton ?? <LoadingState label={loadingLabel} />}</>;
  return <>{children}</>;
}

/** Layout-shaped skeleton for the AI Insight / Coaching cards — mirrors their
 * header + sectioned-body shape so the swap to real content doesn't reflow. */
export function AiCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("premium-card space-y-3 p-4", className)}
    >
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-5 rounded-full" />
        <Skeleton className="h-4 w-40" />
        <Skeleton className="ml-auto h-4 w-16" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-11/12" />
      <div className="grid gap-1.5 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-7" />
        ))}
      </div>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-3 w-4/5" />
      <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        Generating insight…
      </div>
    </div>
  );
}

/** Generic card-shaped skeleton (title + chart/body block). For chart cards,
 * tables, and panels where the AI-card shape doesn't fit. */
export function CardSkeleton({
  bodyHeight = "h-40",
  className,
}: {
  bodyHeight?: string;
  className?: string;
}) {
  return (
    <div role="status" aria-live="polite" className={cn("space-y-3", className)}>
      <Skeleton className="h-4 w-48" />
      <Skeleton className={cn("w-full", bodyHeight)} />
    </div>
  );
}
