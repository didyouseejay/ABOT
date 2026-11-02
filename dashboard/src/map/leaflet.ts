/**
 * Leaflet, loaded on first use (it needs a browser window, so it is never imported at module load:
 * pages still render to static HTML in tests), and the background maps.
 *
 * Background maps (M05.3; satellite imagery removed in M06.3 for licensing): a street map (the
 * standard OpenStreetMap tiles) or none. The street tiles are the only requests the dashboard makes
 * outside its own bundle, and only while a map with that background is on screen; "No background"
 * makes none. The choice is remembered in the browser (localStorage) and shared by every map.
 */
import type * as LeafletNS from "leaflet";
import { type RefObject, useCallback, useEffect, useRef, useState } from "react";
import type { BBox } from "../model/values.ts";

export type L = typeof LeafletNS;
export type LMap = LeafletNS.Map;

let pending: Promise<L> | null = null;

export function loadLeaflet(): Promise<L> {
  pending ??= import("leaflet").then((m) => (m as unknown as { default?: L }).default ?? (m as unknown as L));
  return pending;
}

export const ATTRIBUTION = 'Data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (ODbL 1.0) · boundaries OCHA COD-AB · population PSA, WorldPop';

// --- background maps ----------------------------------------------------------------------------

export type BasemapId = "street" | "none";

export const BASEMAPS: readonly { id: BasemapId; label: string }[] = [
  { id: "street", label: "Street map" },
  { id: "none", label: "No background" },
];

const TILES = {
  street: {
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 19, attribution: 'Street map © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' },
  },
} as const;

const STORE_KEY = "abot.basemap";
const DEFAULT_BASEMAP: BasemapId = "street";

function stored(): BasemapId {
  try {
    const v = typeof localStorage === "undefined" ? null : localStorage.getItem(STORE_KEY);
    // a stored "satellite" (offered before M06.3) falls back to the street map
    return v === "street" || v === "none" ? v : DEFAULT_BASEMAP;
  } catch {
    return DEFAULT_BASEMAP;
  }
}

/** The background the user chose last (on any map), and a setter that remembers it. */
export function useBasemapChoice(): [BasemapId, (b: BasemapId) => void] {
  const [bm, setBm] = useState<BasemapId>(stored);
  const set = useCallback((b: BasemapId) => {
    setBm(b);
    try {
      localStorage.setItem(STORE_KEY, b);
    } catch {
      // private mode or storage disabled: the choice lasts for this page only
    }
  }, []);
  return [bm, set];
}

/** Show the chosen background under the map's own layers. */
export function useBasemapLayer(handle: MapHandle<unknown> | null, id: BasemapId): void {
  useEffect(() => {
    if (!handle) return;
    const { L, map } = handle;
    const layers: LeafletNS.TileLayer[] = [];
    if (id === "street") layers.push(L.tileLayer(TILES.street.url, TILES.street.options));
    for (const l of layers) l.addTo(map);
    map.getContainer().dataset["basemap"] = id;
    return () => {
      for (const l of layers) map.removeLayer(l);
    };
  }, [handle, id]);
}

// --- map creation -------------------------------------------------------------------------------

function makeMap(L: L, el: HTMLElement, bounds: BBox | null): LMap {
  const map = L.map(el, { zoomControl: false, attributionControl: true, preferCanvas: true, minZoom: 11, maxZoom: 19 });
  L.control.zoom({ position: "bottomright" }).addTo(map);
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
