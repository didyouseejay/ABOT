/**
 * The current view (route + address parameters) for every component. Changing a selection replaces the
 * address (history.replaceState) instead of adding a history entry, so Back still leaves the page;
 * moving to another page keeps the shared selection and drops the old page's own parameters.
 */
import { createContext, useContext } from "react";
import { type Params, type Patch, type Shared, buildHash, defaults, FALLBACK_CHOICES } from "./model/view.ts";

export interface View {
  route: string;
  s: Shared;
  def: Shared;
  /** This page's own parameters (shared keys removed). */
  p: Params;
  set: (patch: Patch) => void;
  href: (route: string, extra?: Params) => string;
}

const DEF = defaults(FALLBACK_CHOICES);

export const ViewContext = createContext<View>({
  route: "overview",
  s: DEF,
  def: DEF,
  p: {},
  set: () => {},
  href: (route, extra) => buildHash(route, DEF, DEF, extra),
});

export function useView(): View {
  return useContext(ViewContext);
}
