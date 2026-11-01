/**
 * Values for the public pages, in everyday terms. Walking is the primary (A3) result and "by car" is
 * A1 driving; the A1 walking comparison is shown only on the pages for researchers. Values are read as
 * exported, never recomputed; null is "No data", never zero. Figures are rounded to whole numbers for
 * reading (the technical pages keep the source precision).
 */
import type { BarangayRecord, City } from "../contract/types.ts";
import { fixed } from "./format.ts";
import { pctKey, type Shared } from "./view.ts";
import { bval, cityDrive, cityWalk } from "./values.ts";

/** The time limit of the current mode, in minutes. */
export const limitOf = (s: Shared): number => (s.m === "drive" ? s.dt : s.t);
export const verbOf = (s: Shared): string => (s.m === "drive" ? "drive" : "walk");
export const modeOf = (s: Shared): string => (s.m === "drive" ? "driving" : "walking");
/** "share" or "average": p90 is a researchers' statistic and reads as the average here. */
export const statOf = (s: Shared): "pct" | "mean" => (s.stat === "pct" ? "pct" : "mean");

const scen = (s: Shared) => (s.m === "drive" ? "drive" : "A3");

export function brgyShare(rec: BarangayRecord, s: Shared, g = s.g): number | null {
  return bval(rec, scen(s), g, pctKey(limitOf(s)));
}

export function brgyAvg(rec: BarangayRecord, s: Shared, g = s.g): number | null {
  return bval(rec, scen(s), g, "mean_min");
}

export function cityShare(city: City, s: Shared, g = s.g): number | null {
  return s.m === "drive" ? cityDrive(city, g, pctKey(s.dt)) : cityWalk(city, "A3", g, pctKey(s.t));
}

export function cityAvg(city: City, s: Shared, g = s.g): number | null {
  return s.m === "drive" ? cityDrive(city, g, "mean_min") : cityWalk(city, "A3", g, "mean_min");
}

export const NO_DATA = "No data";

/** "62%", "<1%" for a small non-zero share, "No data" for null. */
export function pctText(v: number | null | undefined): string {
  if (v === null || v === undefined) return NO_DATA;
  if (v > 0 && v < 0.5) return "<1%";
  return `${fixed(v, 0)}%`;
}

/** "9 min", "<1 min", "No data". */
export function minText(v: number | null | undefined): string {
  if (v === null || v === undefined) return NO_DATA;
  if (v < 0.5) return "<1 min";
  return `${fixed(v, 0)} min`;
}

export const intText = (v: number | null | undefined): string => (v === null || v === undefined ? NO_DATA : fixed(Math.round(v), 0));
