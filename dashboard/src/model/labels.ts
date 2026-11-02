/**
 * Display names for ids the bundle uses: indicator groups, A3 categories, facility categories,
 * component classes and connection statuses. Names only: caveats are statements (manifest.statements)
 * and are never written here. An id without a name is shown as the id itself, never hidden.
 */
import type { A3Category } from "../contract/types.ts";

const GROUPS: Record<string, [label: string, phrase: string]> = {
  health_hospital: ["Hospital", "a hospital"],
  health_primary_care: ["Primary care", "primary care"],
  pharmacy: ["Pharmacy", "a pharmacy"],
  education_basic: ["Basic education", "a basic-education school"],
  education_higher: ["Higher education", "a higher-education institution"],
  safety_police: ["Police", "a police station"],
  safety_fire: ["Fire station", "a fire station"],
  market_public: ["Public market", "a public market"],
  market_supermarket: ["Supermarket", "a supermarket"],
  finance_bank: ["Bank", "a bank"],
};

export const groupLabel = (id: string): string => GROUPS[id]?.[0] ?? id;
export const groupPhrase = (id: string): string => GROUPS[id]?.[1] ?? id;

/**
 * Everyday names for the public pages (the technical pages keep groupLabel). The plural is used in
 * map toggles ("Show hospitals"); the phrase completes "can walk to …".
 */
const SERVICES: Record<string, [name: string, plural: string, phrase: string]> = {
  health_hospital: ["Hospital", "hospitals", "a hospital"],
  health_primary_care: ["Health center", "health centers and clinics", "a health center or clinic"],
  pharmacy: ["Pharmacy", "pharmacies", "a pharmacy"],
  education_basic: ["School", "elementary and high schools", "an elementary or high school"],
  education_higher: ["College", "colleges and universities", "a college or university"],
  safety_police: ["Police station", "police stations", "a police station"],
  safety_fire: ["Fire station", "fire stations", "a fire station"],
  market_public: ["Public market", "public markets", "a public market"],
  market_supermarket: ["Supermarket", "supermarkets", "a supermarket"],
  finance_bank: ["Bank", "banks", "a bank"],
};

export const serviceName = (id: string): string => SERVICES[id]?.[0] ?? groupLabel(id);
export const servicePlural = (id: string): string => SERVICES[id]?.[1] ?? groupLabel(id).toLowerCase();
export const servicePhrase = (id: string): string => SERVICES[id]?.[2] ?? groupPhrase(id);

/** Everyday names for the nine facility categories. */
const FAC_NAMES: Record<string, string> = {
  health: "Health",
  pharmacy: "Pharmacy",
  education: "Schools",
  safety: "Police & fire",
  government: "Government offices",
  market: "Markets",
  finance: "Banks",
  transport: "Transport",
  evacuation: "Evacuation centers",
};
/** The facility category of an indicator group ("health_hospital" -> "health"), for marker colours. */
export const groupCategory = (id: string): string => id.split("_")[0] ?? id;

export const facCatName = (c: string): string => FAC_NAMES[c] ?? facCatLabel(c);

/** The reliability levels in everyday words, for the public pages. */
export const CONFIDENCE: Record<string, [word: string, text: string]> = {
  ok: ["Good", "The population and road data for this barangay are complete enough for these figures."],
  caution: ["Fair", "Some population or road data here is less certain. The figures are a reasonable guide."],
  low: ["Limited", "Population or road data here is uncertain, so the figures are rough and the barangay is not ranked."],
  unverified: ["Unverified", "This data has not been checked."],
  unknown: ["Unknown", "No confidence rating is available."],
};

export interface CategoryDef {
  id: A3Category;
  label: string;
  sym: string;
  desc: string;
  cssVar: string;
}

/** The four A3 categories, always shown separately and in this order, each with a symbol. */
export const CATEGORIES: readonly CategoryDef[] = [
  { id: "network_connected", label: "Network-connected", sym: "●", desc: "Connected to the main walk network; has citywide times", cssVar: "--cat-network-connected" },
  { id: "locally_connected", label: "Locally connected", sym: "◆", desc: "Connected only to an isolated fragment; internal times only", cssVar: "--cat-locally-connected" },
  { id: "access_uncertain", label: "Access uncertain", sym: "▲", desc: "Attached to a fragment whose public access is uncertain", cssVar: "--cat-access-uncertain" },
  { id: "unconnected", label: "Unconnected", sym: "✕", desc: "No network connection within tolerance", cssVar: "--cat-unconnected" },
];

export const categoryDef = (id: string): CategoryDef | undefined => CATEGORIES.find((c) => c.id === id);

/** Facility categories in display order; the last three are descriptive only (no travel times). */
export const FAC_CATS = ["health", "pharmacy", "education", "safety", "government", "market", "finance", "transport", "evacuation"] as const;
export const DESCRIPTIVE_ONLY: readonly string[] = ["government", "transport", "evacuation"];
export const facCatLabel = (c: string): string => (c ? c.charAt(0).toUpperCase() + c.slice(1) : c);

const COMPONENT_CLASSES: Record<string, string> = {
  main: "Main network",
  isolated_mapped_dead_end: "Isolated, mapped dead end",
  isolated_local_network: "Isolated local network",
  separated_by_water: "Separated by water",
  small_fragment: "Small fragment",
  restricted_access: "Restricted access",
  likely_geometry_error: "Likely geometry error",
  access_uncertain: "Access uncertain",
};

export const underscores = (s: unknown): string => String(s ?? "").replace(/_/g, " ");
export const componentClassLabel = (c: string | null | undefined): string => (c ? COMPONENT_CLASSES[c] ?? underscores(c) : "—");

/** Why a cell or facility has no connection (a3_conn_status / a1_conn_status). */
export const CONN_REASON: Record<string, string> = {
  beyond_tolerance: "no walkable network edge within the 250 m connection tolerance",
  barrier_blocked: "the straight connector would cross water or a wall",
  connected: "connected",
};
