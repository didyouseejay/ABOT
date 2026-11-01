/**
 * Scenario, mode, role and population-category names (§3). Scenario labels come from the bundle
 * (manifest.scenarios); the short names below are names only. Caveats such as "A1 is optimistic, not
 * an observed result or a verified upper bound" are statements (DQ-A1-OPT) and are taken from
 * manifest.statements, never written here.
 */
import type { A3Category, Manifest, Role, Scenario, ScenarioCode } from "../contract/types.ts";

export const ROLE_NAMES: Record<Role, string> = {
  primary: "Primary",
  comparative: "Comparison",
  descriptive: "Descriptive",
  evidence_only: "Evidence only",
};

/** The four A3 categories, always shown separately and in this order (§3.2, R10). */
export const A3_CATEGORIES: readonly A3Category[] = [
  "network_connected",
  "locally_connected",
  "access_uncertain",
  "unconnected",
];

export const A3_CATEGORY_NAMES: Record<A3Category, string> = {
  network_connected: "Main network",
  locally_connected: "Local network only",
  access_uncertain: "Access uncertain",
  unconnected: "Unconnected",
};

export const MODE_NAMES: Record<"walk" | "drive", string> = {
  walk: "Walking",
  drive: "Driving (separate mode)",
};

/** Short scenario names; the full labels are in the bundle. */
export const SCENARIO_NAMES: Record<string, string> = {
  "A3:walk": "A3 walking",
  "A1:walk": "A1 walking (comparison)",
  "A1:drive": "A1 driving",
  "A2:walk": "A2 walking (supporting evidence)",
};

export function findScenario(manifest: Pick<Manifest, "scenarios">, code: ScenarioCode, mode: "walk" | "drive"): Scenario | undefined {
  return manifest.scenarios.find((s) => s.code === code && s.mode === mode);
}

export function scenarioName(code: ScenarioCode, mode: "walk" | "drive"): string {
  return SCENARIO_NAMES[`${code}:${mode}`] ?? `${code} ${mode}`;
}
