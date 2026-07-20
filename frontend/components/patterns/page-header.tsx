import type { ReactNode } from "react";

import { colors, type } from "@/styles/tokens";

/**
 * Canonical page header (item 4): one consistent type hierarchy across ALL pages.
 *   eyebrow  — small uppercase system/context label (smallest)
 *   title    — the primary page title (largest, using type.pageTitle)
 *   subtitle — the description line beneath (medium)
 * `actions` renders right-aligned controls (buttons, selectors) on the same row.
 *
 * `eyebrow` accepts a node so callers can pass the ProductSystemLabel chip or a
 * plain string — either way it sits ABOVE and SMALLER than the title, never inverted.
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {eyebrow != null &&
          (typeof eyebrow === "string" ? (
            <div className={type.eyebrow} style={{ color: colors.text.muted }}>{eyebrow}</div>
          ) : (
            eyebrow
          ))}
        <h1 className={`mt-1 ${type.pageTitle}`} style={{ color: colors.text.primary }}>{title}</h1>
        {subtitle != null && (
          <p className={`mt-1 ${type.pageSubtitle}`} style={{ color: colors.text.secondary }}>{subtitle}</p>
        )}
      </div>
      {actions != null && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
