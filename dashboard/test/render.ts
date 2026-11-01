/** Render the shell for a route and bundle state to static HTML, as the browser would show it. */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AppShell } from "../src/components/layout/AppShell.tsx";
import type { BundleState } from "../src/data/BundleContext.tsx";
import { choicesOf } from "../src/model/values.ts";
import { buildHash, defaults, FALLBACK_CHOICES, localParams, type Params, resolveShared } from "../src/model/view.ts";
import type { View } from "../src/view.tsx";

export function viewFor(route: string, state: BundleState, params: Params = {}): View {
  const choices = state.status === "ready" ? choicesOf(state.bundle.manifest) : FALLBACK_CHOICES;
  const def = defaults(choices);
  const s = resolveShared(params, choices);
  return { route, s, def, p: localParams(params), set: () => {}, href: (r, e) => buildHash(r, s, def, e) };
}

export function render(route: string, state: BundleState, navOpen = false, params: Params = {}): string {
  return renderToStaticMarkup(createElement(AppShell, { view: viewFor(route, state, params), state, navOpen, onToggleNav: () => {}, onNavigate: () => {} }));
}
