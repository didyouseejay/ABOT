/**
 * Leaflet, loaded on first use (it needs a browser window, so it is never imported at module load:
 * pages still render to static HTML in tests). No basemap tiles are requested: the dashboard reads
 * nothing outside its bundle.
 */
import type * as LeafletNS from "leaflet";
import { type RefObject, useEffect, useRef, useState } from "react";
import type { BBox } from "../model/values.ts";

export type L = typeof LeafletNS;
export type LMap = LeafletNS.Map;

let pending: Promise<L> | null = null;

export function loadLeaflet(): Promise<L> {
  pending ??= import("leaflet").then((m) => (m as unknown as { default?: L }).default ?? (m as unknown as L));
  return pending;
}

export const ATTRIBUTION = "Data © OpenStreetMap contributors (ODbL) · boundaries OCHA COD-AB";

function makeMap(L: L, el: HTMLElement, bounds: BBox | null): LMap {
  const map = L.map(el, { zoomControl: true, attributionControl: true, preferCanvas: true, minZoom: 11, maxZoom: 17 });
  if (bounds) map.fitBounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], { padding: [16, 16] });
  else map.setView([10.715, 122.555], 13);
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution(ATTRIBUTION);
  return map;
}

export interface MapHandle<T> {
  L: L;
  map: LMap;
  layers: T;
}

/**
 * Create a map once for the element and remove it on unmount. `build` adds the layers and returns the
 * ones the component restyles later; the returned handle is null until they exist.
 */
export function useLeaflet<T>(el: RefObject<HTMLElement | null>, bounds: BBox | null, build: (L: L, map: LMap) => T): MapHandle<T> | null {
  const [handle, setHandle] = useState<MapHandle<T> | null>(null);
  const buildRef = useRef(build);
  buildRef.current = build;
  useEffect(() => {
    let live = true;
    let map: LMap | null = null;
    void loadLeaflet().then((L) => {
      if (!live || !el.current) return;
      map = makeMap(L, el.current, bounds);
      setHandle({ L, map, layers: buildRef.current(L, map) });
    });
    return () => {
      live = false;
      map?.remove();
      setHandle(null);
    };
    // the map is built once per element; later changes restyle its layers
  }, [el]);
  return handle;
}
