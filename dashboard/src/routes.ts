/**
 * The dashboard sections. Every route is registered here once; the top navigation and the router read
 * this list. `reference` marks the three reference sections, grouped at the right end of the top bar
 * (and under "Reference" at medium widths). Caveats are never written here (they come from
 * manifest.statements).
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
  { id: "overview", title: "Citywide overview", navLabel: "Overview", reference: false, datasets: ["city", "facilities"] },
  { id: "map", title: "Accessibility map", navLabel: "Accessibility Map", reference: false, datasets: ["barangays", "indicators", "cells", "facilities"] },
  { id: "barangays", title: "Barangay analysis", navLabel: "Barangay Analysis", reference: false, datasets: ["barangays", "indicators"] },
  { id: "facilities", title: "Facilities", navLabel: "Facilities", reference: false, datasets: ["facilities", "barangays", "city"] },
  { id: "network", title: "Network connectivity", navLabel: "Network Connectivity", reference: true, datasets: ["network", "barangays"] },
  { id: "quality", title: "Data quality", navLabel: "Data Quality", reference: true, datasets: ["indicators", "barangays", "provenance"] },
  { id: "about", title: "About and methodology", navLabel: "About / Methodology", reference: true, datasets: ["provenance"] },
];

export const ROUTE_IDS: readonly string[] = ROUTES.map((r) => r.id);
export const DEFAULT_ROUTE = "overview";

export function routeDef(id: string): RouteDef {
  return ROUTES.find((r) => r.id === id) ?? (ROUTES[0] as RouteDef);
}
