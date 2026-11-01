/**
 * Wires the browser to the pure shell: the hash route, the bundle state and the drawer menu. After a
 * route change the page heading receives focus, so keyboard and screen-reader users land on the new
 * page; the drawer closes on navigation and on Escape.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "./components/layout/AppShell.tsx";
import { PAGE_TITLE_ID } from "./components/layout/PageContainer.tsx";
import { NAV_ID } from "./components/layout/Sidebar.tsx";
import { useBundle } from "./data/BundleContext.tsx";
import { useHashRoute } from "./router.ts";
import { DEFAULT_ROUTE, ROUTE_IDS, routeDef } from "./routes.ts";

export default function App() {
  const route = useHashRoute(ROUTE_IDS, DEFAULT_ROUTE);
  const state = useBundle();
  const [navOpen, setNavOpen] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    document.title = `${routeDef(route).navLabel} — ABOT`;
    setNavOpen(false);
    if (first.current) {
      first.current = false;
      return;
    }
    document.getElementById(PAGE_TITLE_ID)?.focus();
  }, [route]);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNavOpen(false);
        document.querySelector<HTMLElement>(".header__menu")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    document.querySelector<HTMLElement>(`#${NAV_ID} a`)?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  const toggle = useCallback(() => setNavOpen((o) => !o), []);
  const close = useCallback(() => setNavOpen(false), []);

  return <AppShell route={route} state={state} navOpen={navOpen} onToggleNav={toggle} onNavigate={close} />;
}
