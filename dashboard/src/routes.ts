/**
 * The dashboard sections (M05.2 plan). Every route is registered here once; navigation, the router
 * and the placeholder pages read this list. `datasets` names the bundle datasets a page will read,
 * so a placeholder can already show whether they loaded. `summary` describes planned content only;
 * caveats are never written here (they come from manifest.statements).
 */

export type DatasetKey = "city" | "barangays" | "indicators" | "cells" | "facilities" | "network" | "provenance";

export interface RouteDef {
  id: string;
  title: string;
  navLabel: string;
  summary: string;
  /** When the page content is planned. */
  planned: string;
  datasets: DatasetKey[];
}

export const ROUTES: readonly RouteDef[] = [
  {
    id: "overview",
    title: "Citywide overview",
    navLabel: "Overview",
    summary:
      "Citywide population by A3 network category, A3 walking accessibility with the A1 comparison, " +
      "the walking-time distribution, and A1 driving as a separate mode.",
    planned: "M05.2 S5",
    datasets: ["city"],
  },
  {
    id: "map",
    title: "Accessibility map",
    navLabel: "Accessibility Map",
    summary: "Barangay polygons, population cells and facility locations on one map, with legends for every value class.",
    planned: "M05.2 S6",
    datasets: ["barangays", "indicators", "cells", "facilities"],
  },
  {
    id: "barangays",
    title: "Barangay analysis",
    navLabel: "Barangay Analysis",
    summary: "Barangay-level indicators as exported, with reliability flags and ranking eligibility.",
    planned: "a later milestone",
    datasets: ["barangays", "indicators"],
  },
  {
    id: "facilities",
    title: "Facilities",
    navLabel: "Facilities",
    summary: "Mapped facilities by indicator group, destination status and duplicate-review state.",
    planned: "a later milestone",
    datasets: ["facilities"],
  },
  {
    id: "network",
    title: "Network connectivity",
    navLabel: "Network Connectivity",
    summary: "Walk-network components, the A1/A2/A3 approach comparison and gap evidence.",
    planned: "a later milestone",
    datasets: ["network"],
  },
  {
    id: "quality",
    title: "Data quality",
    navLabel: "Data Quality",
    summary: "Audit result, known issues, statements, integrity verification and bundle provenance.",
    planned: "M05.2 S4",
    datasets: ["provenance"],
  },
  {
    id: "about",
    title: "About and methodology",
    navLabel: "About / Methodology",
    summary: "Scenarios, indicator definitions, data sources and limitations.",
    planned: "a later milestone",
    datasets: ["provenance"],
  },
];

export const ROUTE_IDS: readonly string[] = ROUTES.map((r) => r.id);
export const DEFAULT_ROUTE = "overview";

export function routeDef(id: string): RouteDef {
  return ROUTES.find((r) => r.id === id) ?? (ROUTES[0] as RouteDef);
}
