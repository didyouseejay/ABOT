/**
 * The dashboard sections. Every route is registered here once; the top navigation and the router read
 * this list. The five public sections are in the top bar. `reference` marks the three pages for
 * researchers (methodology, data quality, network evidence): they are linked from About and the footer,
 * not from the top bar, so residents are not met with technical detail first.
 */

export type DatasetKey = "city" | "barangays" | "indicators" | "cells" | "facilities" | "network" | "provenance";

export interface RouteDef {
  id: string;
  title: string;
  navLabel: string;
  reference: boolean;
  /** The bundle datasets the page reads. */
  datasets: DatasetKey[];
}

export const ROUTES: readonly RouteDef[] = [
  { id: "overview", title: "How close are essential services?", navLabel: "Home", reference: false, datasets: ["city", "indicators"] },
  { id: "map", title: "Map", navLabel: "Map", reference: false, datasets: ["barangays", "indicators", "cells", "facilities"] },
  { id: "barangays", title: "Barangays", navLabel: "Barangays", reference: false, datasets: ["barangays", "indicators"] },
  { id: "facilities", title: "Facilities", navLabel: "Facilities", reference: false, datasets: ["facilities", "barangays"] },
  { id: "about", title: "About this dashboard", navLabel: "About", reference: false, datasets: [] },
  { id: "methods", title: "Methodology", navLabel: "Methodology", reference: true, datasets: ["provenance"] },
  { id: "quality", title: "Data quality", navLabel: "Data quality", reference: true, datasets: ["indicators", "barangays", "provenance"] },
  { id: "network", title: "Network connectivity", navLabel: "Network connectivity", reference: true, datasets: ["network", "barangays"] },
];

export const ROUTE_IDS: readonly string[] = ROUTES.map((r) => r.id);
export const DEFAULT_ROUTE = "overview";

export function routeDef(id: string): RouteDef {
  return ROUTES.find((r) => r.id === id) ?? (ROUTES[0] as RouteDef);
}
