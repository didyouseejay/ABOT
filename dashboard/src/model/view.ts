/**
 * View state in the address: "#/barangays?g=pharmacy&t=30&sort=pop". The shared selection (indicator
 * group, walk threshold, mode, drive threshold, statistic) is kept when moving between pages, so a view
 * can be shared as a link; every other parameter belongs to the page it was set on. Values outside the
 * bundle's own lists (groups, thresholds) fall back to the default, never to an invented choice.
 */

export type Stat = "pct" | "mean" | "p90";
export type ModeKey = "walk" | "drive";

export interface Shared {
  g: string;
  t: number;
  m: ModeKey;
  dt: number;
  stat: Stat;
}

export type Params = Record<string, string>;
export type Patch = Record<string, string | null | undefined>;

export const SHARED_KEYS = ["g", "t", "m", "dt", "stat"] as const;
type SharedKey = (typeof SHARED_KEYS)[number];

/** What the bundle allows: its indicator groups and thresholds (manifest.indicator_groups, thresholds_min). */
export interface Choices {
  groups: readonly string[];
  walk: readonly number[];
  drive: readonly number[];
}

/** Used until the bundle is loaded, and by pages that need no bundle values. */
export const FALLBACK_CHOICES: Choices = { groups: [], walk: [10, 15, 30], drive: [5, 10, 15] };

export function parseHash(hash: string): { name: string; params: Params } {
  const h = hash.replace(/^#\/?/, "");
  const i = h.indexOf("?");
  const path = i < 0 ? h : h.slice(0, i);
  const qs = i < 0 ? "" : h.slice(i + 1);
  return { name: path.split("/")[0] ?? "", params: Object.fromEntries(new URLSearchParams(qs)) };
}

const pick = <T,>(want: T, list: readonly T[]): T => (list.includes(want) || list.length === 0 ? want : (list[0] as T));

export function defaults(c: Choices): Shared {
  return {
    g: c.groups.length === 0 || c.groups.includes("health_primary_care") ? "health_primary_care" : (c.groups[0] as string),
    t: pick(15, c.walk),
    m: "walk",
    dt: pick(10, c.drive),
    stat: "pct",
  };
}

export function resolveShared(p: Params, c: Choices): Shared {
  const d = defaults(c);
  const g = p["g"];
  const t = Number(p["t"]);
  const dt = Number(p["dt"]);
  const m = p["m"];
  const stat = p["stat"];
  return {
    g: g !== undefined && (c.groups.length === 0 || c.groups.includes(g)) ? g : d.g,
    t: c.walk.includes(t) ? t : d.t,
    m: m === "walk" || m === "drive" ? m : d.m,
    dt: c.drive.includes(dt) ? dt : d.dt,
    stat: stat === "pct" || stat === "mean" || stat === "p90" ? stat : d.stat,
  };
}

const isShared = (k: string): k is SharedKey => (SHARED_KEYS as readonly string[]).includes(k);

/** The hash for a route: shared values that differ from the default, then the page's own parameters. */
export function buildHash(route: string, shared: Shared, def: Shared, local: Params = {}): string {
  const q = new URLSearchParams();
  for (const k of SHARED_KEYS) if (shared[k] !== def[k]) q.set(k, String(shared[k]));
  for (const [k, v] of Object.entries(local)) if (!isShared(k)) q.set(k, v);
  const s = q.toString();
  return `#/${route}${s ? `?${s}` : ""}`;
}

/** Apply a patch (null or undefined removes a parameter) to the current parameters. */
export function applyPatch(params: Params, patch: Patch): Params {
  const out: Params = { ...params };
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === undefined || v === "") delete out[k];
    else out[k] = v;
  }
  return out;
}

export function localParams(params: Params): Params {
  return Object.fromEntries(Object.entries(params).filter(([k]) => !isShared(k)));
}

/** Parameter name of a share statistic: "pct_le15". */
export const pctKey = (minutes: number): string => `pct_le${minutes}`;

/** The statistic key the shared selection points at: pct_le<N> (by mode), mean_min or p90_min. */
export function statKey(s: Shared): string {
  if (s.stat === "pct") return pctKey(s.m === "drive" ? s.dt : s.t);
  return s.stat === "mean" ? "mean_min" : "p90_min";
}
