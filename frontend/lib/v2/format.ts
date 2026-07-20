/**
 * THE shared number formatter (DESIGN_TOKENS.md "enforce globally").
 * Negatives are parenthesised — never a minus sign. Zero renders "—".
 */

export function fmtMoney(value: number | null | undefined, decimals = 0): string {
  if (value == null) return "—";
  if (value === 0) return "$0";
  const text = `$${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  })}`;
  return value < 0 ? `(${text})` : text;
}

/** Compact thousands: +$23.8k / ($44.1k). Positive gets an explicit +. */
export function fmtMoneyK(value: number | null | undefined): string {
  if (value == null) return "—";
  const text = `$${(Math.abs(value) / 1000).toLocaleString("en-US", {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  })}k`;
  return value < 0 ? `(${text})` : `+${text}`;
}

export function fmtPct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return "—";
  const text = `${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  })}%`;
  return value < 0 ? `(${text})` : text;
}

/** "▲ $43,430  9.3%" / "▼ ($90,685)  (17.7%)" */
export function fmtChange(amount: number, pct: number | null): string {
  const arrow = amount >= 0 ? "▲" : "▼";
  return `${arrow} ${fmtMoney(amount)}  ${pct == null ? "n/a" : fmtPct(pct)}`;
}

/** Cell "—" for zero; used by pivot cells where zero means no activity. */
export function isZeroish(value: number | null | undefined): boolean {
  return value == null || Math.abs(value) < 0.005;
}

const MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_NAMES_FULL = ["", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

/** "202604" -> "APR 2026" (pivot column headers). */
export function monthHeader(monthId: string): string {
  return `${MONTH_NAMES[Number(monthId.slice(4, 6))].toUpperCase()} ${monthId.slice(0, 4)}`;
}

/** "202604" -> "Apr 2026". */
export function monthShort(monthId: string): string {
  return `${MONTH_NAMES[Number(monthId.slice(4, 6))]} ${monthId.slice(0, 4)}`;
}

/** "202604" -> "April 2026". */
export function monthFull(monthId: string): string {
  return `${MONTH_NAMES_FULL[Number(monthId.slice(4, 6))]} ${monthId.slice(0, 4)}`;
}

/** "2026-06-30 00:00:00" -> "30 Jun 2026". */
export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = String(value).slice(0, 10);
  const [y, m, day] = d.split("-");
  if (!y || !m || !day) return d;
  return `${Number(day)} ${MONTH_NAMES[Number(m)]} ${y}`;
}
