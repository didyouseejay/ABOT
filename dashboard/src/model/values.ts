/**
 * Read access to bundle values by indicator id. Nothing is recomputed: a value is looked up as exported,
 * and a value the bundle does not have is null (shown as "No value"), never zero. The only derived
 * figures are counts of rows (filtering) and ranks among ranking-eligible barangays (sorting).
 */
import type { BarangayProps, BarangayRecord, City, Facilities, FacilityProps, Feature, Manifest } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import type { Choices } from "./view.ts";

export type WalkScenario = "A3" | "A1";

const cache = new WeakMap<object, Map<string, number | null>>();

function indexed<R extends { value: number | null }>(records: R[], key: (r: R) => string): Map<string, number | null> {
  let m = cache.get(records);
  if (m === undefined) {
    m = new Map(records.map((r) => [key(r), r.value]));
    cache.set(records, m);
  }
  return m;
}

export function cityWalk(city: City, scen: WalkScenario, group: string, stat: string): number | null {
  return indexed(city.walk, (r) => r.indicator_id).get(`${scen}.walk.${group}.${stat}`) ?? null;
}

/** A1 driving; factor 1 is the result, other factors are the illustrative sensitivity (evidence only). */
export function cityDrive(city: City, group: string, stat: string, factor = 1): number | null {
  const m = indexed(city.drive, (r) => `${r.group}|${r.statistic}|${r.network_time_factor}`);
  return m.get(`${group}|${stat}|${factor}`) ?? null;
}

export function walkKey(scen: WalkScenario, group: string, stat: string): string {
  return `${scen}.walk.${group}.${stat}`;
}

export function driveKey(group: string, stat: string): string {
  return `A1.drive.${group}.${stat}`;
}

/** A barangay value; scen "drive" reads A1 driving. */
export function bval(rec: BarangayRecord, scen: WalkScenario | "drive", group: string, stat: string): number | null {
  const v = rec.values[scen === "drive" ? driveKey(group, stat) : walkKey(scen, group, stat)];
  return v === undefined ? null : v;
}

export type RelLevel = "ok" | "caution" | "low" | "unverified" | "unknown";

export function relOf(rec: BarangayRecord, dim: "population" | "network" | "facility_inventory" | "overall"): { level: RelLevel; reasons: string | null } {
  const r = rec.data_quality.reliability[dim] as { level?: string; reasons?: string | null } | undefined;
  const l = r?.level;
  return { level: l === "ok" || l === "caution" || l === "low" || l === "unverified" ? l : "unknown", reasons: r?.reasons ?? null };
}

export function choicesOf(m: Manifest): Choices {
  return { groups: m.indicator_groups.map((g) => g.id), walk: m.thresholds_min.walk, drive: m.thresholds_min.drive };
}

// --- barangays: indicators joined to their boundary properties ---------------------------------

export interface Barangay {
  code: string;
  name: string;
  rec: BarangayRecord;
  props: BarangayProps | undefined;
  geometry: Feature<BarangayProps>["geometry"] | undefined;
}

const brgyCache = new WeakMap<LoadedBundle, Barangay[] | null>();

/** Null when barangay_indicators did not load. Boundaries are optional (display only). */
export function barangaysOf(b: LoadedBundle): Barangay[] | null {
  if (brgyCache.has(b)) return brgyCache.get(b) ?? null;
  let out: Barangay[] | null = null;
  if (b.indicators.status === "ok") {
    const feats = new Map(b.barangays.status === "ok" ? b.barangays.data.features.map((f) => [f.properties.adm4_pcode, f]) : []);
    out = b.indicators.data.barangays.map((rec) => {
      const f = feats.get(rec.adm4_pcode);
      return { code: rec.adm4_pcode, name: rec.adm4_name, rec, props: f?.properties, geometry: f?.geometry };
    });
  }
  brgyCache.set(b, out);
  return out;
}

export function relCounts(list: Barangay[], dim: "population" | "network" | "overall"): Record<"ok" | "caution" | "low", number> {
  const c = { ok: 0, caution: 0, low: 0 };
  for (const x of list) {
    const l = relOf(x.rec, dim).level;
    if (l === "ok" || l === "caution" || l === "low") c[l]++;
  }
  return c;
}

/**
 * Rank among ranking-eligible barangays with a value; rank 1 is the worst served (lowest share, or
 * longest time). Ties share a rank. Ineligible barangays get no rank.
 */
export function rankEligible(list: Barangay[], value: (b: Barangay) => number | null, higherIsBetter: boolean): Map<string, number> {
  const el = list
    .filter((b) => b.rec.data_quality.ranking_eligible && value(b) !== null)
    .sort((a, b) => (higherIsBetter ? (value(a) as number) - (value(b) as number) : (value(b) as number) - (value(a) as number)));
  const out = new Map<string, number>();
  let prev: number | null = null;
  let rank = 0;
  el.forEach((b, i) => {
    const v = value(b) as number;
    if (v !== prev) rank = i + 1;
    prev = v;
    out.set(b.code, rank);
  });
  return out;
}

// --- facilities ---------------------------------------------------------------------------------

export type DupStatus = "none" | "pending" | "likely" | "reviewed";

export function dupStatus(p: FacilityProps): DupStatus {
  const r = p.data_quality?.duplicate_review ?? [];
  if (r.length === 0) return "none";
  if (r.some((x) => x.review_status === "pending")) return "pending";
  if (r.some((x) => x.reviewer_decision === "likely_duplicate_not_merged")) return "likely";
  return "reviewed";
}

export interface FacilitySummary {
  total: number;
  outside: number;
  unnamed: number;
  pairs: number;
  pending: number;
  likely: number;
}

/** Row counts over facilities.geojson (no values are derived). */
export function facilitySummary(f: Facilities): FacilitySummary {
  const pairs = new Map<string, { pending: boolean; likely: boolean }>();
  for (const x of f.features) {
    for (const r of x.properties.data_quality?.duplicate_review ?? []) {
      const p = pairs.get(r.review_id) ?? { pending: false, likely: false };
      if (r.review_status === "pending") p.pending = true;
      if (r.reviewer_decision === "likely_duplicate_not_merged") p.likely = true;
      pairs.set(r.review_id, p);
    }
  }
  const ps = [...pairs.values()];
  return {
    total: f.features.length,
    outside: f.features.filter((x) => x.properties.inside_city === false).length,
    unnamed: f.features.filter((x) => x.properties.name === null || x.properties.name === undefined).length,
    pairs: ps.length,
    pending: ps.filter((p) => p.pending).length,
    likely: ps.filter((p) => p.likely).length,
  };
}

// --- geometry -----------------------------------------------------------------------------------

export type BBox = [number, number, number, number];

/** Longitude/latitude extent of the barangay boundaries (for fitting maps). */
export function boundsOf(list: Barangay[]): BBox | null {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; // prettier-ignore
  const walk = (c: unknown): void => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]); // prettier-ignore
      return;
    }
    c.forEach(walk);
  };
  for (const b of list) walk(b.geometry?.coordinates);
  return Number.isFinite(x0) ? [x0, y0, x1, y1] : null;
}

/** SVG path data per barangay (equirectangular, scaled by cos(latitude)); for small static maps. */
export function svgPaths(list: Barangay[], width: number): { paths: Map<string, string>; w: number; h: number } | null {
  const bb = boundsOf(list);
  if (bb === null) return null;
  const [x0, y0, x1, y1] = bb;
  const k = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
  const sx = width / ((x1 - x0) * k);
  const pt = (c: number[]) => `${(((c[0] as number) - x0) * k * sx).toFixed(1)},${((y1 - (c[1] as number)) * sx).toFixed(1)}`;
  const ring = (r: number[][]) => `M${r.map(pt).join("L")}Z`;
  const paths = new Map<string, string>();
  for (const b of list) {
    const g = b.geometry;
    if (!g) continue;
    const polys = (g.type === "Polygon" ? [g.coordinates] : g.coordinates) as number[][][][];
    paths.set(b.code, polys.map((p) => p.map(ring).join("")).join(""));
  }
  return { paths, w: width, h: Math.ceil((y1 - y0) * sx) };
}
