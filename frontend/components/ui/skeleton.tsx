import * as React from "react";
import { cn } from "@/lib/utils";

/** Skeleton — the single shimmer primitive for the whole app (CLAUDE.md 1B:
 * "loading skeletons that match final layout shape"). Uses the design-token
 * `muted` surface, so it reads the same in light + dark. Compose it into
 * layout-shaped placeholders rather than hand-rolling animate-pulse divs. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-muted/70 dark:bg-muted", className)}
      {...props}
    />
  );
}
