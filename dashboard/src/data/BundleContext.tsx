/**
 * Loads the bundle once and shares it with every page. Components never fetch bundle files themselves.
 */
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { type Fetcher, type Issue, type LoadedBundle, loadBundle } from "./loadBundle.ts";

export type BundleState =
  | { status: "loading" }
  | { status: "fatal"; issues: Issue[] }
  | { status: "ready"; bundle: LoadedBundle };

/** Default location: served by the dev plugin and copied into dist/ at build (vite/bundlePlugin.ts). */
export const DEFAULT_BUNDLE_URL = `${import.meta.env.BASE_URL}data/v1/`;

export function httpFetcher(baseUrl: string): Fetcher {
  return async (name) => {
    const res = await fetch(`${baseUrl}${encodeURIComponent(name)}`, { cache: "no-store" });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return new Uint8Array(await res.arrayBuffer());
  };
}

const BundleContext = createContext<BundleState>({ status: "loading" });

export function BundleProvider({ children, baseUrl = DEFAULT_BUNDLE_URL }: { children: ReactNode; baseUrl?: string }) {
  const [state, setState] = useState<BundleState>({ status: "loading" });
  useEffect(() => {
    let live = true;
    loadBundle(httpFetcher(baseUrl)).then(
      (r) => {
        if (live) setState(r.status === "ready" ? { status: "ready", bundle: r.bundle } : { status: "fatal", issues: r.issues });
      },
      (e: unknown) => {
        if (live) setState({ status: "fatal", issues: [{ level: "error", dataset: "manifest", message: String(e) }] });
      },
    );
    return () => {
      live = false;
    };
  }, [baseUrl]);
  return <BundleContext.Provider value={state}>{children}</BundleContext.Provider>;
}

export function useBundle(): BundleState {
  return useContext(BundleContext);
}
