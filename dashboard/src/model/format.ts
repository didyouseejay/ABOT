/**
 * Display formatting. Null is "unavailable or not applicable" and is shown as NULL_TEXT, never as 0
 * (R11); a real zero is shown as a number. Formatting never rounds more finely than the source and
 * never changes a value's meaning.
 */

export const NULL_TEXT = "—";

const MAX_DECIMALS: Record<string, number> = { "%": 2, minutes: 2, residents: 1 };

export function formatNumber(v: number, maxDecimals = 2): string {
  return new Intl.NumberFormat("en", { maximumFractionDigits: maxDecimals }).format(v);
}

/** A value with its unit; null -> NULL_TEXT. */
export function formatValue(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return NULL_TEXT;
  const n = formatNumber(v, MAX_DECIMALS[unit] ?? 2);
  if (unit === "%") return `${n} %`;
  if (unit === "minutes") return `${n} min`;
  if (unit === "residents") return `${n} residents`;
  return n;
}

const FIXED = [0, 1, 2].map((d) => new Intl.NumberFormat("en-PH", { minimumFractionDigits: d, maximumFractionDigits: d }));

/** en-PH figure with exactly 0, 1 or 2 decimals (1 in compact views, the source's 2 in tables). */
export function fixed(v: number, decimals = 1): string {
  return (FIXED[decimals] ?? (FIXED[1] as Intl.NumberFormat)).format(v);
}

/** A1 − A3 difference, signed, one decimal; empty when either value is missing. */
export function delta(a3: number | null | undefined, a1: number | null | undefined): string {
  if (a3 === null || a3 === undefined || a1 === null || a1 === undefined) return "";
  const d = a1 - a3;
  return `${d >= 0 ? "+" : "−"}${fixed(Math.abs(d), 1)}`;
}

export function isUnavailable(v: number | null | undefined): v is null | undefined {
  return v === null || v === undefined;
}

/** HTML-escaped text for Leaflet tooltip strings (OpenStreetMap names and tags are untrusted input). */
export const esc = (s: unknown) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);

/** ISO 8601 UTC timestamp shown with an explicit UTC marker. */
export function formatUtc(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
