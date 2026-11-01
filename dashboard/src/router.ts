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

export function useHashRoute(routes: readonly string[], fallback: string): string {
  const [route, setRoute] = useState(() => routeFromHash(window.location.hash, routes, fallback));
  useEffect(() => {
    const onChange = () => setRoute(routeFromHash(window.location.hash, routes, fallback));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, [routes, fallback]);
  return route;
}
