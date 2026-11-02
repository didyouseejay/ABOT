/**
 * Map (#/map): Leaflet map of Iloilo City with a choice of background (street map or none),
 * barangays coloured by the selected service, facilities of that service, and an optional 100 m grid.
 * A side panel holds the choices, a legend explains the colours, and clicking a barangay opens its
 * details. Walking is the primary (A3) result and "by car" is A1 driving, each with its own breaks.
 * If the cells dataset failed, the grid option is disabled and says so.
 */
import type * as LeafletNS from "leaflet";
import { useEffect, useRef, useState } from "react";
import { ModeSwitch, ServiceSelect, TimeLimit } from "../components/controls.tsx";
import { Glyph } from "../components/glyphs.tsx";
import { Check, Seg } from "../components/ui.tsx";
import type { CellProps, FacilityProps, Feature } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { BasemapSwitcher } from "../map/BasemapSwitcher.tsx";
import { type L, type LMap, useBasemapChoice, useBasemapLayer, useLeaflet } from "../map/leaflet.ts";
import { esc, fixed } from "../model/format.ts";
import { facCatName, groupCategory, serviceName, servicePhrase, servicePlural } from "../model/labels.ts";
import { brgyAvg, brgyShare, limitOf, minText, modeOf, pctText, statOf, verbOf } from "../model/plain.ts";
import { DRIVE_BREAKS, DRIVE_LABELS, ramps, shareClass, TIME_BREAKS, TIME_LABELS, timeClass } from "../model/ramps.ts";
import type { Params, Shared } from "../model/view.ts";
import { type Barangay, barangaysOf, boundsOf } from "../model/values.ts";
import { useView } from "../view.tsx";
import { BarangayPanel } from "./common.tsx";

const SHARE_WORDS = ["Under 20%", "20–40%", "40–60%", "60–80%", "80% or more"];

interface Opt {
  choro: boolean;
  cells: boolean;
  facs: boolean;
  op: number;
  b: string | null;
  lyr: string[];
}

function options(p: Params, cellsOk: boolean): Opt {
  const lyr = (p["lyr"] ?? "choro,facs").split(",");
  const op = Number(p["op"]);
  return {
    choro: lyr.includes("choro"),
    cells: lyr.includes("cells") && cellsOk,
    facs: lyr.includes("facs"),
    op: Number.isFinite(op) && op >= 0.2 && op <= 1 ? op : 0.7,
    b: p["b"] ?? null,
    lyr,
  };
}

const value = (b: Barangay, s: Shared) => (statOf(s) === "pct" ? brgyShare(b.rec, s) : brgyAvg(b.rec, s));

function timeColor(v: number | null, s: Shared): string | null {
  if (v === null) return null;
  const R = ramps();
  return (s.m === "drive" ? R.drive[timeClass(v, DRIVE_BREAKS)] : R.time[timeClass(v, TIME_BREAKS)]) ?? null;
}

function choroColor(v: number | null, s: Shared): string | null {
  if (v === null) return null;
  return statOf(s) === "pct" ? (ramps().share[shareClass(v)] ?? null) : timeColor(v, s);
}

const cellValue = (c: CellProps, s: Shared): number | null => (s.m === "drive" ? c.drive_a1[s.g] : c.walk_citywide[s.g]) ?? null;

function cellTip(c: CellProps, s: Shared): string {
  const v = cellValue(c, s);
  const where = `About ${fixed(Math.max(c.pop, 0), 0)} residents in this 100 m square`;
  if (v !== null) return `${where}<br>${verbOf(s) === "walk" ? "Walk" : "Drive"} to ${esc(servicePhrase(s.g))}: <b>${minText(v)}</b>`;
  const why = c.a3_category === "network_connected" || s.m === "drive" ? "No route found in the map data." : "This spot is not linked to the city's street network in the map data.";
  return `${where}<br><b>No ${modeOf(s)} time</b><br><span class="muted">${why}</span>`;
}

export function facTip(f: FacilityProps): string {
  return `<b>${f.name ? esc(f.name) : "Unnamed place"}</b><br>${esc(facCatName(f.category))}${f.inside_city ? "" : " · just outside the city"}`;
}

/** Facility markers in their category colour; the selected one is larger with a dark ring. */
export function drawFacilities(L: L, group: LeafletNS.LayerGroup, feats: Feature<FacilityProps>[], colour: (f: FacilityProps) => string, selected: string | null, onClick?: (f: FacilityProps) => void) {
  group.clearLayers();
  for (const ft of feats) {
    const f = ft.properties;
    const [lon, lat] = ft.geometry.coordinates as [number, number];
    const sel = f.fid_key === selected;
    const m = L.circleMarker([lat, lon], {
      radius: sel ? 9 : 5.5,
      fillColor: colour(f),
      fillOpacity: 1,
      color: sel ? "#0f172a" : "#ffffff",
      weight: sel ? 3 : 1.5,
    }).bindTooltip(facTip(f), { className: "map-tip", direction: "top" });
    if (onClick) m.on("click", () => onClick(f));
    m.addTo(group);
  }
}

interface Layers {
  choro: LeafletNS.GeoJSON;
  cells: LeafletNS.FeatureGroup | null;
  cellList: CellProps[];
  facs: LeafletNS.FeatureGroup;
}

function Controls({ b, list, o, setLyr }: { b: LoadedBundle; list: Barangay[]; o: Opt; setLyr: (name: string, on: boolean) => void }) {
  const { s, set, href } = useView();
  const m = b.manifest;
  const groups = m.indicator_groups.map((g) => g.id);
  const cellsFailed = b.cells.status === "failed";
  return (
    <div className="mapside__body" id="map-ctl">
      <ServiceSelect id="mc-g" groups={groups} />
      <ModeSwitch id="mc-m" />
      <TimeLimit id="mc-t" walk={m.thresholds_min.walk} drive={m.thresholds_min.drive} />
      <Seg
        id="mc-stat"
        label="Color barangays by"
        fill
        options={[
          ["pct", "Share of residents"],
          ["mean", "Typical time"],
        ]}
        value={statOf(s)}
        onChange={(v) => set({ stat: v })}
      />
      <fieldset className="mapside__layers">
        <legend className="field__label">Show on the map</legend>
        <Check id="ly-choro" checked={o.choro} onChange={(on) => setLyr("choro", on)}>
          Barangay colors
        </Check>
        <Check id="ly-facs" checked={o.facs} onChange={(on) => setLyr("facs", on)}>
          {servicePlural(s.g).charAt(0).toUpperCase() + servicePlural(s.g).slice(1)}
        </Check>
        <Check id="ly-cells" checked={o.cells} disabled={cellsFailed} onChange={(on) => setLyr("cells", on)}>
          Detailed 100 m grid
          <span className="check__hint">{cellsFailed ? "Not available: this data did not load." : "Travel time from each 100 m square"}</span>
        </Check>
      </fieldset>
      <div className="field">
        <label className="field__label" htmlFor="ly-op">
          Color strength
        </label>
        <div className="range-row">
          <input type="range" id="ly-op" min="0.2" max="1" step="0.05" value={o.op} onChange={(e) => set({ op: e.target.value })} />
          <span className="num">{Math.round(o.op * 100)}%</span>
        </div>
        <span className="check__hint">Lower it to see the background map through the colors.</span>
      </div>
      <label className="field" htmlFor="mc-find">
        <span className="field__label">Find a barangay</span>
        <select className="select" id="mc-find" value={o.b ?? ""} onChange={(e) => set({ b: e.target.value || null })}>
          <option value="">Choose a barangay…</option>
          {[...list]
            .sort((a, c) => a.name.localeCompare(c.name))
            .map((x) => (
              <option key={x.code} value={x.code}>
                {x.name}
              </option>
            ))}
        </select>
      </label>
      <a className="mapside__link" href={href("barangays")}>
        <Glyph name="list" />
        See every barangay as a list
      </a>
    </div>
  );
}

function Legend({ o, nFacs, collapsed, onToggle }: { o: Opt; nFacs: number; collapsed: boolean; onToggle: () => void }) {
  const { s } = useView();
  const drive = s.m === "drive";
  const timeRamp = drive ? DRIVE_LABELS.map((l, i) => [`var(--ramp-drive-${i + 1})`, l]) : TIME_LABELS.map((l, i) => [`var(--ramp-time-${i + 1})`, l]);
  const ramp = statOf(s) === "pct" ? SHARE_WORDS.map((l, i) => [`var(--ramp-share-${i + 1})`, l]) : timeRamp;
  const sw = ([c, l]: string[]) => (
    <li key={l}>
      <span className="legend__sw" style={{ background: c }} />
      {l}
    </li>
  );
  return (
    <div className="map-legend" id="map-legend" role="region" aria-label="Legend" data-collapsed={String(collapsed)}>
      <button type="button" className="map-legend__toggle" aria-expanded={!collapsed} onClick={onToggle}>
        <Glyph name="layers" />
        Legend
      </button>
      <div className="map-legend__body">
        {o.choro && (
          <div className="map-legend__block">
            <p className="map-legend__title">{statOf(s) === "pct" ? `Residents who can ${verbOf(s)} to ${servicePhrase(s.g)} within ${limitOf(s)} min` : `Typical ${verbOf(s)} to ${servicePhrase(s.g)}`}</p>
            <ul className="legend">
              {ramp.map(sw)}
              <li>
                <span className="legend__sw legend__sw--none" />
                No data
              </li>
            </ul>
          </div>
        )}
        {o.cells && (
          <div className="map-legend__block">
            <p className="map-legend__title">100 m grid: {modeOf(s)} time</p>
            <ul className="legend">
              {(statOf(s) === "pct" || !o.choro ? timeRamp : []).map(sw)}
              {statOf(s) !== "pct" && o.choro && <li className="legend__same">Same colors as above</li>}
              <li>
                <span className="legend__sw legend__sw--none" />
                No route
              </li>
            </ul>
          </div>
        )}
        {o.facs && (
          <div className="map-legend__block">
            <ul className="legend">
              <li>
                <span className="legend__dot" style={{ background: `var(--fac-${groupCategory(s.g)})` }} />
                {serviceName(s.g)} ({nFacs})
              </li>
            </ul>
          </div>
        )}
        {!o.choro && !o.cells && !o.facs && <p className="legend__note">Nothing selected. Turn on a layer in the panel.</p>}
      </div>
    </div>
  );
}

export function MapPage({ bundle }: { bundle: LoadedBundle }) {
  const { s, p, set } = useView();
  const list = barangaysOf(bundle);
  const o = options(p, bundle.cells.status === "ok");
  const el = useRef<HTMLDivElement>(null);
  const live = useRef({ s, set });
  live.current = { s, set };
  const [basemap, setBasemap] = useBasemapChoice();
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [ctlOpen, setCtlOpen] = useState(false);
  const facFeats = bundle.facilities.status === "ok" ? bundle.facilities.data.features : [];
  const visibleFacs = o.facs ? facFeats.filter((f) => (f.properties.destination_groups ?? []).includes(s.g) || (f.properties.indicator_groups ?? []).includes(s.g)) : [];

  const setLyr = (name: string, on: boolean) => {
    const l = o.lyr.filter((x) => x !== name);
    if (on) l.push(name);
    set({ lyr: l.join(",") });
  };

  const handle = useLeaflet<Layers>(el, list ? boundsOf(list) : null, (L, map) => {
    map.createPane("cells").style.zIndex = "420";
    map.createPane("facs").style.zIndex = "640";
    const feats = (list ?? []).filter((x) => x.geometry).map((x) => ({ type: "Feature" as const, geometry: x.geometry as never, properties: { c: x.code } }));
    const byCode = new Map((list ?? []).map((x) => [x.code, x]));
    const choro = L.geoJSON(feats, {
      onEachFeature: (f, layer) => {
        const x = byCode.get((f.properties as { c: string }).c);
        if (!x) return;
        layer.bindTooltip(
          () => {
            const cur = live.current.s;
            const line = statOf(cur) === "pct" ? `${pctText(brgyShare(x.rec, cur))} can ${verbOf(cur)} there within ${limitOf(cur)} min` : `Typical ${verbOf(cur)}: ${minText(brgyAvg(x.rec, cur))}`;
            return `<b>${esc(x.name)}</b><br>${esc(serviceName(cur.g))}: ${line}<br><span class="muted">Click for details</span>`;
          },
          { className: "map-tip", sticky: true },
        );
        layer.on("click", () => live.current.set({ b: x.code }));
      },
    }).addTo(map);
    let cells: LeafletNS.FeatureGroup | null = null;
    const cellList: CellProps[] = [];
    if (bundle.cells.status === "ok") {
      const rend = L.canvas({ pane: "cells", padding: 0.3 });
      cells = L.featureGroup();
      bundle.cells.data.forEach((c, i) => {
        const [lon, lat] = c.geometry.coordinates as [number, number];
        cellList.push(c.properties);
        L.rectangle([[lat - 0.00045, lon - 0.000458], [lat + 0.00045, lon + 0.000458]], { renderer: rend, weight: 0, fillOpacity: 0.8, ...({ ci: i } as object) }).addTo(cells as LeafletNS.FeatureGroup);
      });
      cells.on("mouseover", (e) => {
        const layer = e.layer as LeafletNS.Path & { options: { ci: number } };
        const c = cellList[layer.options.ci];
        if (c) layer.bindTooltip(cellTip(c, live.current.s), { className: "map-tip", sticky: true }).openTooltip(e.latlng);
      });
      cells.on("mouseout", (e) => (e.layer as LeafletNS.Layer).unbindTooltip());
    }
    const facs = L.featureGroup([], { pane: "facs" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    return { choro, cells, cellList, facs };
  });

  useBasemapLayer(handle, basemap);

  // Restyle on every change of the selection or the layer options.
  useEffect(() => {
    if (!handle) return;
    const { L, map, layers } = handle;
    const lookup = new Map((list ?? []).map((x) => [x.code, x]));
    layers.choro.setStyle((f) => {
      const x = lookup.get((f?.properties as { c: string }).c);
      if (!x) return { stroke: false, fill: false };
      const sel = o.b === x.code;
      const line = sel ? { color: "#0f172a", weight: 3.5, opacity: 1 } : { color: "#334155", weight: o.choro ? 0.7 : 1.1, opacity: o.choro ? 0.9 : 0.75 };
      if (!o.choro) return { ...line, fill: true, fillOpacity: 0, stroke: true };
      const c = choroColor(value(x, s), s);
      return { ...line, stroke: true, fill: true, fillColor: c ?? ramps().none, fillOpacity: c ? o.op : o.op * 0.7 };
    });
    if (layers.cells) {
      if (o.cells && !map.hasLayer(layers.cells)) layers.cells.addTo(map);
      if (!o.cells && map.hasLayer(layers.cells)) map.removeLayer(layers.cells);
      if (o.cells)
        layers.cells.eachLayer((l) => {
          const c = layers.cellList[(l as LeafletNS.Path & { options: { ci: number } }).options.ci];
          if (!c) return;
          const col = timeColor(cellValue(c, s), s);
          (l as LeafletNS.Path).setStyle({ fillColor: col ?? ramps().none, fillOpacity: col ? Math.min(1, o.op + 0.15) : 0.5, stroke: false });
        });
    }
    drawFacilities(L as L, layers.facs as unknown as LeafletNS.LayerGroup, visibleFacs, (f) => ramps().fac[f.category] ?? "#0f172a", null);
    // restyled from the address (s, p) and the background; the other inputs derive from them
  }, [handle, s, p, list]);

  // Zoom to a barangay chosen from the finder or a link.
  useEffect(() => {
    if (!handle || !o.b) return;
    handle.layers.choro.eachLayer((l) => {
      const f = (l as LeafletNS.GeoJSON & { feature?: { properties: { c: string } } }).feature;
      if (f?.properties.c === o.b) {
        const wide = window.innerWidth > 1024;
        (handle.map as LMap).fitBounds((l as LeafletNS.Polygon).getBounds(), { maxZoom: 16, paddingBottomRight: [wide ? 440 : 0, wide ? 0 : 320] });
      }
    });
  }, [handle, o.b]);

  const selected = o.b && list ? list.find((x) => x.code === o.b) : undefined;
  const groups = bundle.manifest.indicator_groups.map((g) => g.id);

  if (!list) {
    return (
      <div className="page">
        <div className="state state--unavailable" role="status">
          <h1 id="page-title" tabIndex={-1} className="state__title">
            The map is unavailable
          </h1>
          <p>The barangay data did not load, so the map has nothing to show. Other pages still work.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mappage" id="mappage">
      <aside className="mapside" id="map-controls" data-collapsed={String(!ctlOpen)} aria-label="Map options">
        <div className="mapside__head">
          <div>
            <h1 id="page-title" tabIndex={-1}>
              Map
            </h1>
            <p>
              {serviceName(s.g)} · {s.m === "drive" ? "by car" : "walking"} · within {limitOf(s)} min
            </p>
          </div>
          <button type="button" className="btn btn--sm mapside__toggle" id="ctl-toggle" aria-expanded={ctlOpen} aria-controls="map-ctl" onClick={() => setCtlOpen((c) => !c)}>
            <Glyph name="sliders" />
            {ctlOpen ? "Done" : "Options"}
          </button>
        </div>
        <Controls b={bundle} list={list} o={o} setLyr={setLyr} />
      </aside>
      <div className="mapview">
        <div id="leaflet" ref={el} role="region" aria-label="Map of Iloilo City. The Barangays page lists the same figures." />
        <BasemapSwitcher id="bm" value={basemap} onChange={setBasemap} />
        <Legend o={o} nFacs={visibleFacs.length} collapsed={legendCollapsed} onToggle={() => setLegendCollapsed((c) => !c)} />
        {selected && (
          <aside
            className="drawer"
            id="b-drawer"
            aria-labelledby="drawer-title"
            onKeyDown={(e) => {
              if (e.key === "Escape") set({ b: null });
            }}
          >
            <BarangayPanel b={selected} groups={groups} compact onClose={() => set({ b: null })} />
          </aside>
        )}
      </div>
    </div>
  );
}
