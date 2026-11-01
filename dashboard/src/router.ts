/**
 * Hash routing without a router library: "#/overview" -> "overview". The hash keeps the dashboard a
 * set of static files that work from any folder (no server-side routes).
 */
import { useEffect, useState } from "react";

export function routeFromHash(hash: string, routes: readonly string[], fallback: string): string {
  const name = hash.replace(/^#\/?/, "").split(/[/?]/)[0] ?? "";
  return routes.includes(name) ? name : fallback;
}

export function hrefFor(route: string): string {
  return `#/${route}`;
}

/** True when the hash names no registered route (an empty hash is not unknown: it means the default). */
export function isUnknownHash(hash: string, routes: readonly string[]): boolean {
  const name = hash.replace(/^#\/?/, "").split(/[/?]/)[0] ?? "";
  return name !== "" && !routes.includes(name);
}

export function useHashRoute(routes: readonly string[], fallback: string): string {
  const [route, setRoute] = useState(() => routeFromHash(window.location.hash, routes, fallback));
  useEffect(() => {
    const sync = () => {
      // An unknown section shows the fallback; the address is corrected to match what is shown.
      if (isUnknownHash(window.location.hash, routes)) window.history.replaceState(null, "", hrefFor(fallback));
      setRoute(routeFromHash(window.location.hash, routes, fallback));
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [routes, fallback]);
  return route;
}
