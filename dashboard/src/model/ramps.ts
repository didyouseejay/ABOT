/**
 * Map classes for the colour ramps (tokens.css §B). Walking and driving times have separate ramps
 * (never one scale for both); "no value" has its own swatch and is never the end of a ramp.
 */

export const TIME_BREAKS = [10, 15, 30, 45, 60];
export const TIME_LABELS = ["0–10 min", "10–15 min", "15–30 min", "30–45 min", "45–60 min", "> 60 min"];
export const DRIVE_BREAKS = [5, 10, 15, 30];
export const DRIVE_LABELS = ["0–5 min", "5–10 min", "10–15 min", "15–30 min", "> 30 min"];
export const SHARE_BREAKS = [20, 40, 60, 80];
export const SHARE_LABELS = ["0–20 %", "20–40 %", "40–60 %", "60–80 %", "80–100 %"];

/** Class index for a time (upper bounds inclusive); -1 for null. */
export function timeClass(v: number | null, breaks: readonly number[]): number {
  if (v === null) return -1;
  let i = 0;
  while (i < breaks.length && v > (breaks[i] as number)) i++;
  return i;
}

/** Class index for a share (lower bounds inclusive); -1 for null. */
export function shareClass(v: number | null): number {
  if (v === null) return -1;
  let i = 0;
  while (i < SHARE_BREAKS.length && v >= (SHARE_BREAKS[i] as number)) i++;
  return i;
}

export interface Ramps {
  time: string[];
  drive: string[];
  share: string[];
  none: string;
  cat: Record<string, string>;
  fac: Record<string, string>;
}

let RAMPS: Ramps | null = null;

/** Colours read once from the tokens, for Leaflet styles (canvas cannot use CSS variables). */
export function ramps(): Ramps {
  if (RAMPS) return RAMPS;
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  RAMPS = {
    time: [1, 2, 3, 4, 5, 6].map((i) => v(`--ramp-time-${i}`)),
    drive: [1, 2, 3, 4, 5].map((i) => v(`--ramp-drive-${i}`)),
    share: [1, 2, 3, 4, 5].map((i) => v(`--ramp-share-${i}`)),
    none: v("--ramp-none"),
    cat: Object.fromEntries(
      ["network_connected", "locally_connected", "access_uncertain", "unconnected"].map((c) => [c, v(`--cat-${c.replace(/_/g, "-")}`)]),
    ),
    fac: Object.fromEntries(
      ["health", "pharmacy", "education", "safety", "government", "market", "finance", "transport", "evacuation"].map((c) => [c, v(`--fac-${c}`)]),
    ),
  };
  return RAMPS;
}

export function timeLabel(v: number | null, drive: boolean): string {
  if (v === null) return "No value";
  return drive ? (DRIVE_LABELS[timeClass(v, DRIVE_BREAKS)] as string) : (TIME_LABELS[timeClass(v, TIME_BREAKS)] as string);
}

export function shareLabel(v: number | null): string {
  return v === null ? "No value" : (SHARE_LABELS[shareClass(v)] as string);
}
