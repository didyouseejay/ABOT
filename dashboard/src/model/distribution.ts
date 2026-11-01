/**
 * Display view of a citywide walking-time distribution (§7.2). A pure re-labelling of the exported
 * bins and cumulative points: nothing is recomputed, the open "> 60 min" bin is kept as its own bar,
 * the final cumulative point (which includes it) is kept, and the curve is never extended to 100 %.
 */
import type { WalkDistribution } from "../contract/types.ts";

export interface DistributionBar {
  label: string;
  lowerMin: number;
  upperMin: number | null;
  pop: number;
  open: boolean;
}

export interface DistributionView {
  group: string;
  bars: DistributionBar[];
  /** Points at 1 … closedMax minutes. */
  cumulative: { minutes: number; pct: number }[];
  /** All residents with a citywide time, including those above closedMax minutes. */
  final: { label: string; pct: number };
  popWithTime: number;
  popOpenBin: number;
  popTotal: number;
  closedMax: number;
}

export function finalPointLabel(closedMax: number): string {
  return `all citywide times (incl. > ${closedMax} min)`;
}

export function distributionView(d: WalkDistribution, closedMax: number): DistributionView {
  const last = d.bins.at(-1);
  const final = d.cumulative.at(-1);
  if (last === undefined || last.upper_min !== null || final === undefined || final.minutes !== null) {
    throw new Error(`walk_distribution ${d.group}: no open final bin or no final cumulative point`);
  }
  return {
    group: d.group,
    bars: d.bins.map((b) => ({
      label: b.upper_min === null ? `> ${b.lower_min}` : `${b.lower_min}–${b.upper_min}`,
      lowerMin: b.lower_min,
      upperMin: b.upper_min,
      pop: b.pop,
      open: b.upper_min === null,
    })),
    cumulative: d.cumulative
      .filter((c): c is { minutes: number; pct_all_residents: number } => c.minutes !== null)
      .map((c) => ({ minutes: c.minutes, pct: c.pct_all_residents })),
    final: { label: finalPointLabel(closedMax), pct: final.pct_all_residents },
    popWithTime: d.pop_with_time,
    popOpenBin: d.pop_open_bin,
    popTotal: d.pop_total,
    closedMax,
  };
}
