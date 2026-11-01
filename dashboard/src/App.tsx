/**
 * Wires the browser to the pure shell: the address (route + view parameters), the bundle state, the
 * menu panel and the notices. After a route change the page heading receives focus, so keyboard and
 * screen-reader users land on the new page; the menu closes on navigation and on Escape.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "./components/layout/AppShell.tsx";
import { NAV_PANEL_ID, PAGE_TITLE_ID } from "./components/layout/ids.ts";
import { useBundle } from "./data/BundleContext.tsx";
import { applyPatch, buildHash, defaults, FALLBACK_CHOICES, localParams, parseHash, type Patch, resolveShared } from "./model/view.ts";
import { choicesOf } from "./model/values.ts";
import { isUnknownHash } from "./router.ts";
import { DEFAULT_ROUTE, ROUTE_IDS, routeDef } from "./routes.ts";
import type { View } from "./view.tsx";

function useHash(): [string, (h: string) => void] {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const sync = () => {
      // An unknown section shows the overview; the address is corrected to match what is shown.
      if (isUnknownHash(window.location.hash, ROUTE_IDS)) window.history.replaceState(null, "", `#/${DEFAULT_ROUTE}`);
      setHash(window.location.hash);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const replace = useCallback((h: string) => {
    window.history.replaceState(null, "", h);
    setHash(h);
  }, []);
  return [hash, replace];
}

export default function App() {
  const state = useBundle();
  const [hash, replaceHash] = useHash();
  const [navOpen, setNavOpen] = useState(false);
  const [noticesOpen, setNoticesOpen] = useState<boolean | null>(null);
  const first = useRef(true);

  const choices = state.status === "ready" ? choicesOf(state.bundle.manifest) : FALLBACK_CHOICES;
  const view: View = useMemo(() => {
    const { name, params } = parseHash(hash);
    const route = ROUTE_IDS.includes(name) ? name : DEFAULT_ROUTE;
    const def = defaults(choices);
    const s = resolveShared(params, choices);
    const p = localParams(params);
    return {
      route,
      s,
      def,
      p,
      href: (r, extra) => buildHash(r, s, def, extra),
      set: (patch: Patch) => {
        const next = applyPatch({ ...p, ...Object.fromEntries(Object.entries(s).map(([k, v]) => [k, String(v)])) }, patch);
        replaceHash(buildHash(route, resolveShared(next, choices), def, localParams(next)));
      },
    };
    // choices change once, when the bundle has loaded
  }, [hash, state.status, replaceHash]);

  const route = view.route;
  useEffect(() => {
    document.title = `${routeDef(route).navLabel} · ABOT`;
    document.body.dataset["route"] = route;
    setNavOpen(false);
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo(0, 0);
    document.getElementById(PAGE_TITLE_ID)?.focus({ preventScroll: true });
  }, [route]);

  useEffect(() => {
    if (!navOpen) return;
    const panel = document.getElementById(NAV_PANEL_ID);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNavOpen(false);
        document.querySelector<HTMLElement>(".topbar__menu-btn")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    (panel?.querySelector<HTMLElement>('[aria-current="page"]') ?? panel?.querySelector<HTMLElement>("a"))?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  const toggle = useCallback(() => setNavOpen((o) => !o), []);
  const close = useCallback(() => setNavOpen(false), []);
  const toggleNotices = useCallback(() => {
    const el = document.getElementById("notices");
    // open if it is currently hidden (the default state depends on the bundle, see AppShell)
    setNoticesOpen(el ? el.hidden === true : true);
  }, []);

  return <AppShell view={view} state={state} navOpen={navOpen} onToggleNav={toggle} onNavigate={close} noticesOpen={noticesOpen} onToggleNotices={toggleNotices} />;
}
