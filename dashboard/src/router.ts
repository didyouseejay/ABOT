/**
 * Hash routing without a router library: "#/overview" -> "overview". The hash keeps the dashboard a
 * set of static files that work from any folder (no server-side routes).
 */
export function routeFromHash(hash: string, routes: readonly string[], fallback: string): string {
  const name = hash.replace(/^#\/?/, "").split(/[/?]/)[0] ?? "";
  return routes.includes(name) ? name : fallback;
}

/** True when the hash names no registered route (an empty hash is not unknown: it means the default). */
export function isUnknownHash(hash: string, routes: readonly string[]): boolean {
  const name = hash.replace(/^#\/?/, "").split(/[/?]/)[0] ?? "";
  return name !== "" && !routes.includes(name);
}
