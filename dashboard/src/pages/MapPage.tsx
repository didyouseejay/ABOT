/**
 * Accessibility Map (#/map): full-bleed Leaflet map with a barangay choropleth, 100 m cells (canvas),
 * facilities and outlines; controls, legend, a barangay drawer and a table alternative. Walking (A3)
 * and driving (A1) are separate modes and never share a ramp; A1 walking appears only as a comparison
 * readout in the drawer. If the cells dataset failed, the whole cell layer is hidden.
 */
import { useEffect, useRef, useState } from "react";
import { Chip } from "../components/notes.tsx";
import { Badge, Check, GroupSelect, Icon, Pct, Min, Rel, Scen, Seg, thresholdOptions } from "../components/ui.tsx";
import type { CellProps, FacilityProps, Feature } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { type L, type LMap, useLeaflet } from "../map/leaflet.ts";
import { fixed } from "../model/format.ts";
import { CATEGORIES, categoryDef, CONN_REASON, DESCRIPTIVE_ONLY, FAC_CATS, facCatLabel, groupLabel, underscores } from "../model/labels.ts";
import { DRIVE_BREAKS, DRIVE_LABELS, ramps, SHARE_LABELS, shareClass, shareLabel, TIME_BREAKS, TIME_LABELS, timeClass, timeLabel } from "../model/ramps.ts";
import { type Params, type Shared, statCodes, statKey, statLabel } from "../model/view.ts";
import { type Barangay, barangaysOf, boundsOf, bval, relOf } from "../model/values.ts";
import { useView } from "../view.tsx";
import { BarangayPanel, NOT_RANKED } from "./common.tsx";
import type * as LeafletNS from "leaflet";

const esc = (s: unknown) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);

interface Opt {
  choro: boolean;
  cells: boolean;
  facs: boolean;
  outline: boolean;
  lowrel: boolean;
  cc: "time" | "cat";
  op: number;
  fset: "group" | "all";
  fcats: string[];
  b: string | null;
  table: boolean;
  lyr: string[];
}

function options(p: Params, cellsOk: boolean): Opt {
  const lyr = (p["lyr"] ?? "choro,facs").split(",");
  const op = Number(p["op"]);
  return {
    choro: lyr.includes("choro"),
    cells: lyr.includes("cells") && cellsOk,
    facs: lyr.includes("facs"),
    outline: lyr.includes("outline"),
    lowrel: !lyr.includes("nolow"),
    cc: p["cc"] === "cat" ? "cat" : "time",
    op: Number.isFinite(op) && op >= 0.2 && op <= 1 ? op : 0.75,
    fset: p["fset"] === "all" ? "all" : "group",
    fcats: p["fc"] !== undefined ? p["fc"].split(",").filter(Boolean) : [...FAC_CATS],
    b: p["b"] ?? null,
    table: p["view"] === "table",
    lyr,
  };
}

const value = (b: Barangay, s: Shared) => bval(b.rec, s.m === "drive" ? "drive" : "A3", s.g, statKey(s));

function choroColor(v: number | null, s: Shared): string | null {
  if (v === null) return null;
  const R = ramps();
  if (s.stat === "pct") return R.share[shareClass(v)] ?? null;
  return (s.m === "drive" ? R.drive[timeClass(v, DRIVE_BREAKS)] : R.time[timeClass(v, TIME_BREAKS)]) ?? null;
}

function cellValue(c: CellProps, s: Shared): number | null {
  return (s.m === "drive" ? c.drive_a1[s.g] : c.walk_citywide[s.g]) ?? null;
}

function cellColor(c: CellProps, s: Shared, o: Opt): string | null {
  const R = ramps();
  if (o.cc === "cat") return R.cat[c.a3_category] ?? null;
  const v = cellValue(c, s);
  if (v === null) return null;
  return (s.m === "drive" ? R.drive[timeClass(v, DRIVE_BREAKS)] : R.time[timeClass(v, TIME_BREAKS)]) ?? null;
}

function cellTip(c: CellProps, s: Shared): string {
  const drive = s.m === "drive";
  const cat = categoryDef(c.a3_category);
  const v = cellValue(c, s);
  let why = "";
  if (v === null) {
    if (drive) why = c.a1_conn_status !== "connected" ? `A1: ${CONN_REASON[c.a1_conn_status] ?? c.a1_conn_status}` : "no drive route";
    else if (c.a3_category === "network_connected") why = "not reachable";
    else if (c.a3_category === "unconnected") why = CONN_REASON[c.a3_conn_status] ?? c.a3_conn_status;
    else why = `connected only to isolated fragment ${c.component ?? "?"} (${underscores(c.component_class)})`;
  }
  const internal = !drive ? c.walk_internal?.[s.g] : null;
  return (
    `<b>${fixed(c.pop, 1)} residents</b> (fractional, 100 m cell)<br>${cat?.sym ?? ""} ${esc(cat?.label ?? c.a3_category)}<br>` +
    `${drive ? "Drive" : "Citywide walk"} to ${esc(groupLabel(s.g).toLowerCase())}: ` +
    (v === null ? `<b>${drive ? "no drive time" : "no citywide time"}</b><br><span class="muted">Reason: ${esc(why)}</span>` : `<b>${fixed(v, 1)}&#8239;min</b>`) +
    (internal !== null && internal !== undefined ? `<br>Internal, isolated fragment only: ${fixed(internal, 1)}&#8239;min <span class="muted">(DQ-LOCAL)</span>` : "")
  );
}

export function facTip(f: FacilityProps): string {
  return (
    `<b>${f.name ? esc(f.name) : "<i>Unnamed</i>"}</b><br>${esc(facCatLabel(f.category))} · ${esc(underscores(f.subtype))} · ${esc(f.tier)}<br>` +
    `${f.inside_city ? "Inside city" : "Outside city (3 km buffer)"} · ${f.conn_status === "connected" ? `connected (${f.conn_m === null ? "?" : fixed(f.conn_m, 0)} m)` : "not connected: not used as a destination"}`
  );
}

function facVisible(f: FacilityProps, s: Shared, o: Opt): boolean {
  if (o.fset === "group") return (f.destination_groups ?? []).includes(s.g) || (f.indicator_groups ?? []).includes(s.g);
  return o.fcats.includes(f.category);
}

/** Draw facility markers: filled = indicative destination, hollow = descriptive, dashed = not connected, ring = outside the city. */
export function drawFacilities(L: L, group: LeafletNS.LayerGroup, feats: Feature<FacilityProps>[], colour: (f: FacilityProps) => string, selected: string | null, onClick?: (f: FacilityProps) => void) {
  group.clearLayers();
  for (const ft of feats) {
    const f = ft.properties;
    const [lon, lat] = ft.geometry.coordinates as [number, number];
    const ind = f.tier === "indicative";
    const sel = f.fid_key === selected;
    const col = colour(f);
    if (!f.inside_city) L.circleMarker([lat, lon], { radius: 7, color: "#1b2a2f", weight: 1, fill: false, interactive: false }).addTo(group);
    const m = L.circleMarker([lat, lon], {
      radius: sel ? 8 : 4.5,
      fillColor: ind ? col : "#fff",
      fillOpacity: 1,
      color: sel ? "#0a3a44" : ind ? "#fff" : col,
      weight: sel ? 3 : ind ? 1.2 : 2,
      dashArray: f.conn_status === "connected" ? undefined : "2 2",
    }).bindTooltip(facTip(f), { className: "map-tip", direction: "top" });
    if (onClick) m.on("click", () => onClick(f));
    m.addTo(group);
  }
}

interface Layers {
  choro: LeafletNS.GeoJSON;
  outline: LeafletNS.GeoJSON;
  cells: LeafletNS.FeatureGroup | null;
  cellList: CellProps[];
  facs: LeafletNS.FeatureGroup;
}

function Controls({ b, list, o, setLyr }: { b: LoadedBundle; list: Barangay[]; o: Opt; setLyr: (name: string, on: boolean) => void }) {
  const { s, set } = useView();
  const m = b.manifest;
  const drive = s.m === "drive";
  const groups = m.indicator_groups.map((g) => g.id);
  const cellsFailed = b.cells.status === "failed";
  const nCells = b.cells.status === "ok" ? b.cells.data.length : null;
  return (
    <>
      <div className="ctl-group">
        <h2>Mode</h2>
        <Seg id="mc-m" ariaLabel="Mode" fill options={[["walk", "Walk · A3"], ["drive", "Drive · A1"]]} value={s.m} btnCls={(v) => (v === "drive" ? "seg__btn--drive" : "")} onChange={(v) => set({ m: v })} />
        <p className="small muted" style={{ margin: 0 }}>
          {drive ? "Uncongested car time; a separate mode. Walking values are not shown on the map in this mode." : "A3 is the primary walking result. A1 walking appears only as a comparison readout in the barangay panel."}
        </p>
      </div>
      <div className="ctl-group">
        <h2>Indicator</h2>
        <GroupSelect id="mc-g" groups={groups} value={s.g} onChange={(g) => set({ g })} />
        <Seg id="mc-stat" label="Statistic" options={[["pct", "% within N"], ["mean", "Mean"], ["p90", "p90"]]} value={s.stat} onChange={(v) => set({ stat: v })} />
        {s.stat === "pct" &&
          (drive ? (
            <Seg id="mc-dt" label="Threshold" cls="seg--drive" options={thresholdOptions(m.thresholds_min.drive)} value={String(s.dt)} onChange={(v) => set({ dt: v })} />
          ) : (
            <Seg id="mc-t" label="Threshold" options={thresholdOptions(m.thresholds_min.walk)} value={String(s.t)} onChange={(v) => set({ t: v })} />
          ))}
      </div>
      <div className="ctl-group">
        <h2>Layers</h2>
        <Check id="ly-choro" checked={o.choro} onChange={(on) => setLyr("choro", on)}>
          Barangay choropleth
          <span className="small muted" style={{ display: "block" }}>
            {statLabel(s)}
          </span>
        </Check>
        {o.choro && (
          <div className="ctl-sub">
            <Check id="ly-low" checked={o.lowrel} onChange={(on) => setLyr("nolow", !on)}>
              Mark low reliability (dashed outline)
            </Check>
          </div>
        )}
        <Check id="ly-cells" checked={o.cells} disabled={cellsFailed} onChange={(on) => setLyr("cells", on)}>
          100 m population cells
          {cellsFailed ? (
            <span className="small" style={{ display: "block", color: "var(--color-error)" }}>
              Unavailable: the cells dataset failed to load. The whole layer is hidden.
            </span>
          ) : (
            <span className="small muted" style={{ display: "block" }}>
              {nCells === null ? "" : `${fixed(nCells, 0)} cells`}
            </span>
          )}
        </Check>
        {o.cells && (
          <div className="ctl-sub">
            <Seg id="cc" ariaLabel="Colour cells by" options={[["time", drive ? "Drive time" : "Walk time"], ["cat", "A3 category"]]} value={o.cc} onChange={(v) => set({ cc: v === "time" ? null : v })} />
          </div>
        )}
        <Check id="ly-facs" checked={o.facs} onChange={(on) => setLyr("facs", on)}>
          Facilities
        </Check>
        {o.facs && (
          <div className="ctl-sub">
            <Seg id="fs" ariaLabel="Facilities shown" options={[["group", groupLabel(s.g)], ["all", "By category"]]} value={o.fset} onChange={(v) => set({ fset: v === "group" ? null : v })} />
            {o.fset === "all" && (
              <div className="chipset" role="group" aria-label="Facility categories">
                {FAC_CATS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className="chip-toggle"
                    id={`fc-${c}`}
                    aria-pressed={o.fcats.includes(c)}
                    onClick={() => {
                      const next = new Set(o.fcats);
                      if (next.has(c)) next.delete(c);
                      else next.add(c);
                      set({ fc: next.size === FAC_CATS.length ? null : [...next].join(",") || "," });
                    }}
                  >
                    <span className={`fac-sym${DESCRIPTIVE_ONLY.includes(c) ? " fac-sym--desc" : ""}`} style={{ background: `var(--fac-${c})`, width: ".6rem", height: ".6rem" }} aria-hidden="true" />
                    {facCatLabel(c)}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <Check id="ly-outline" checked={o.outline} onChange={(on) => setLyr("outline", on)}>
          Barangay outlines
        </Check>
        <p className="small muted" style={{ margin: 0 }}>
          No basemap tiles are loaded: the dashboard makes no requests outside its own bundle.
        </p>
        <div className="opacity-row">
          <label htmlFor="ly-op">Fill opacity</label>
          <input type="range" id="ly-op" min="0.2" max="1" step="0.05" value={o.op} onChange={(e) => set({ op: e.target.value })} />
          <span className="num">{Math.round(o.op * 100)} %</span>
        </div>
      </div>
      <div className="ctl-group">
        <h2>Find a barangay</h2>
        <label className="field" htmlFor="mc-find">
          <span className="visually-hidden">Barangay</span>
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
      </div>
    </>
  );
}

function Legend({ b, list, o, collapsed, onToggle, nFacs }: { b: LoadedBundle; list: Barangay[]; o: Opt; collapsed: boolean; onToggle: () => void; nFacs: number }) {
  const { s } = useView();
  const drive = s.m === "drive";
  const sw = (c: string, l: string) => (
    <li key={l}>
      <span className="legend__sw" style={{ background: c }} />
      {l}
    </li>
  );
  const ramp = (cells: boolean) => (s.stat === "pct" && !cells ? SHARE_LABELS.map((l, i) => sw(`var(--ramp-share-${i + 1})`, l)) : drive ? DRIVE_LABELS.map((l, i) => sw(`var(--ramp-drive-${i + 1})`, l)) : TIME_LABELS.map((l, i) => sw(`var(--ramp-time-${i + 1})`, l)));
  const nLow = list.filter((x) => relOf(x.rec, "overall").level === "low").length;
  const codes = ["DQ-SIMPLIFIED", "DQ-POP-ALLOC", ...statCodes(s), ...(o.facs ? ["DQ-FAC-OSM"] : [])];
  const known = new Set(b.manifest.statements.map((x) => x.code));
  return (
    <>
      <button type="button" className="linkbtn" id="legend-toggle" aria-expanded={!collapsed} style={{ marginBottom: ".25rem" }} onClick={onToggle}>
        <Icon name="layers" />
        Legend
      </button>
      <div className="map-legend__body">
        {o.choro && (
          <div className="map-legend__block">
            <h3>Barangays {drive ? <Scen k="drive" /> : <Scen k="a3" />}</h3>
            <p className="small" style={{ margin: "0 0 .375rem" }}>
              {groupLabel(s.g)} · {statLabel(s)}
            </p>
            <ul className="legend">
              {ramp(false)}
              <li>
                <span className="legend__sw legend__sw--none" />
                No value
              </li>
              {o.lowrel && (
                <li>
                  <span className="legend__sw legend__sw--low" />
                  Low overall reliability ({nLow})
                </li>
              )}
            </ul>
          </div>
        )}
        {o.cells && (
          <div className="map-legend__block">
            <h3>100 m cells {o.cc === "cat" ? <Scen k="a3" text="A3 · category" /> : drive ? <Scen k="drive" /> : <Scen k="a3" />}</h3>
            {o.cc !== "cat" && (
              <p className="small" style={{ margin: "0 0 .375rem" }}>
                {drive ? "Drive" : "Citywide walk"} time to {groupLabel(s.g).toLowerCase()}
              </p>
            )}
            <ul className="legend">
              {o.cc === "cat"
                ? CATEGORIES.map((c, i) => (
                    <li key={c.id}>
                      <span className="legend__sw" style={{ background: `var(${c.cssVar})`, ...(i ? { outline: "1.5px solid #1b2a2f", outlineOffset: "-2px" } : {}) }} />
                      {c.sym} {c.label}
                    </li>
                  ))
                : [
                    ...ramp(true),
                    <li key="none">
                      <span className="legend__sw legend__sw--none" />
                      {drive ? "No drive time" : "No citywide time"}
                    </li>,
                  ]}
            </ul>
          </div>
        )}
        {o.facs && (
          <div className="map-legend__block">
            <h3>
              Facilities{" "}
              <span className="muted" style={{ fontWeight: 400 }}>
                {nFacs} shown
              </span>
            </h3>
            {nFacs === 0 ? (
              <p className="legend__note" style={{ margin: 0 }}>
                No facilities match. Choose at least one category.
              </p>
            ) : (
              <ul className="legend">
                <li>
                  <span className="fac-sym" style={{ background: "#1b2a2f" }} />
                  Indicative (travel-time destination)
                </li>
                <li>
                  <span className="fac-sym fac-sym--desc" />
                  Descriptive only (no travel times)
                </li>
                <li>
                  <span className="fac-sym fac-sym--nc" style={{ background: "#fff" }} />
                  Not connected (not used)
                </li>
                <li>
                  <span className="fac-sym fac-sym--out" style={{ background: "#1b2a2f" }} />
                  Outside city, 3 km buffer
                </li>
              </ul>
            )}
          </div>
        )}
        {!o.choro && !o.cells && !o.facs && (
          <p className="legend__note" style={{ margin: 0 }}>
            No layers selected.
          </p>
        )}
        <div className="map-legend__chips">
          {codes.filter((c) => known.has(c)).map((c) => (
            <Chip key={c} code={c} />
          ))}
        </div>
      </div>
    </>
  );
}

function MapTable({ list, onOpen, onBack }: { list: Barangay[]; onOpen: (code: string) => void; onBack: () => void }) {
  const { s } = useView();
  const pct = s.stat === "pct";
  const drive = s.m === "drive";
  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)", alignItems: "baseline", marginBottom: "var(--space-3)" }}>
        <h2 style={{ margin: 0 }}>Current choropleth as a table</h2>
        <span className="muted small">
          {groupLabel(s.g)} · {statLabel(s)} · {drive ? <Scen k="drive" /> : <Scen k="a3" />} · {list.length} barangays, alphabetical
        </span>
        <button type="button" className="btn btn--sm" id="map-view-map" style={{ marginLeft: "auto" }} onClick={onBack}>
          <Icon name="map" />
          Back to map
        </button>
      </div>
      <div className="table-wrap">
        <table className="data-table data-table--compact">
          <caption className="visually-hidden">Barangay values shown on the map</caption>
          <thead>
            <tr>
              <th scope="col">Barangay</th>
              <th scope="col" className="n">
                {statLabel(s, true)}
              </th>
              <th scope="col">Map class</th>
              <th scope="col">Overall reliability</th>
              <th scope="col">Ranking</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {[...list]
              .sort((a, c) => a.name.localeCompare(c.name))
              .map((x) => {
                const v = value(x, s);
                const rel = relOf(x.rec, "overall");
                return (
                  <tr key={x.code}>
                    <th scope="row" style={{ fontWeight: 500 }}>
                      {x.name}
                    </th>
                    <td className="n">{pct ? <Pct v={v} d={2} /> : <Min v={v} d={2} />}</td>
                    <td>{pct ? shareLabel(v) : timeLabel(v, drive)}</td>
                    <td>
                      <Rel level={rel.level} reason={rel.reasons} />
                    </td>
                    <td>
                      {x.rec.data_quality.ranking_eligible ? (
                        "Eligible"
                      ) : (
                        <span className="not-ranked" title={NOT_RANKED}>
                          Not ranked
                        </span>
                      )}
                    </td>
                    <td>
                      <button type="button" className="row-link" onClick={() => onOpen(x.code)}>
                        Details
                      </button>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function MapPage({ bundle }: { bundle: LoadedBundle }) {
  const view = useView();
  const { s, p, set } = view;
  const list = barangaysOf(bundle);
  const o = options(p, bundle.cells.status === "ok");
  const el = useRef<HTMLDivElement>(null);
  const live = useRef({ s, o, set, list });
  live.current = { s, o, set, list };
  const facFeats = bundle.facilities.status === "ok" ? bundle.facilities.data.features : [];
  const visibleFacs = o.facs ? facFeats.filter((f) => facVisible(f.properties, s, o)) : [];

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
            const { s: cur } = live.current;
            const v = value(x, cur);
            const rel = relOf(x.rec, "overall");
            const shown = v === null ? "no value" : cur.stat === "pct" ? `${fixed(v, 2)}&#8239;%` : `${fixed(v, 2)}&#8239;min`;
            return `<b>${esc(x.name)}</b><br>${statLabel(cur, true)}: ${shown}<br>Overall reliability: ${rel.level}${x.rec.data_quality.ranking_eligible ? "" : " · not ranked"}`;
          },
          { className: "map-tip", sticky: true },
        );
        layer.on("click", () => live.current.set({ b: x.code }));
      },
    }).addTo(map);
    const outline = L.geoJSON(feats, { style: { weight: 0, fill: false }, interactive: false }).addTo(map);
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
        if (c) layer.bindTooltip(cellTip(c, live.current.s), { className: "cell-tip", sticky: true }).openTooltip(e.latlng);
      });
      cells.on("mouseout", (e) => (e.layer as LeafletNS.Layer).unbindTooltip());
    }
    const facs = L.featureGroup([], { pane: "facs" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);
    return { choro, outline, cells, cellList, facs };
  });

  // Restyle on every change of the selection or the layer options.
  useEffect(() => {
    if (!handle) return;
    const { L, map, layers } = handle;
    const lookup = new Map((list ?? []).map((x) => [x.code, x]));
    layers.choro.setStyle((f) => {
      const x = lookup.get((f?.properties as { c: string }).c);
      if (!o.choro || !x) return { stroke: false, fill: false };
      const c = choroColor(value(x, s), s);
      const sel = o.b === x.code;
      const low = o.lowrel && relOf(x.rec, "overall").level === "low";
      return { fill: true, stroke: true, fillColor: c ?? ramps().none, fillOpacity: c ? o.op : o.op * 0.8, color: sel ? "#0a3a44" : low ? "#1b2a2f" : "#ffffff", weight: sel ? 3 : low ? 1.4 : 0.6, dashArray: low && !sel ? "4 3" : "", opacity: 1 };
    });
    layers.outline.setStyle({ color: "#1b2a2f", weight: o.outline ? 0.8 : 0, opacity: o.outline ? 0.7 : 0, fill: false });
    if (layers.cells) {
      if (o.cells && !map.hasLayer(layers.cells)) layers.cells.addTo(map);
      if (!o.cells && map.hasLayer(layers.cells)) map.removeLayer(layers.cells);
      if (o.cells)
        layers.cells.eachLayer((l) => {
          const c = layers.cellList[(l as LeafletNS.Path & { options: { ci: number } }).options.ci];
          if (!c) return;
          const col = cellColor(c, s, o);
          (l as LeafletNS.Path).setStyle({ fillColor: col ?? ramps().none, fillOpacity: col ? Math.min(1, o.op + 0.15) : 0.55, stroke: !col || (o.cc === "cat" && c.a3_category !== "network_connected"), color: "#1b2a2f", weight: 0.8, dashArray: col ? "" : "2 2" });
        });
    }
    drawFacilities(L as L, layers.facs as unknown as LeafletNS.LayerGroup, visibleFacs, (f) => (o.fset === "all" ? ramps().fac[f.category] ?? "#1b2a2f" : "#1b2a2f"), null);
    // restyled from the address (s, p); the other inputs derive from it
  }, [handle, s, p, list]);

  // Zoom to a barangay chosen from the finder, the table or a link.
  useEffect(() => {
    if (!handle || !o.b) return;
    handle.layers.choro.eachLayer((l) => {
      const f = (l as LeafletNS.GeoJSON & { feature?: { properties: { c: string } } }).feature;
      if (f?.properties.c === o.b) {
        const wide = window.innerWidth > 1024;
        (handle.map as LMap).fitBounds((l as LeafletNS.Polygon).getBounds(), { maxZoom: 15, paddingBottomRight: [wide ? 480 : 0, wide ? 0 : 300] });
      }
    });
  }, [handle, o.b]);

  const selected = o.b && list ? list.find((x) => x.code === o.b) : undefined;
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [ctlOpen, setCtlOpen] = useState(false);
  const groups = bundle.manifest.indicator_groups.map((g) => g.id);

  if (!list) {
    return (
      <div className="page">
        <div className="state state--unavailable" role="status">
          <h1 id="page-title" tabIndex={-1} className="state__title">
            Accessibility map is unavailable
          </h1>
          <p>Barangay indicators did not load, so the map has nothing to show. Other pages are unaffected.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mappage" id="mappage">
      <aside className="mappage__controls" id="map-controls" data-collapsed={String(!ctlOpen)} aria-label="Map controls">
        <div className="mappage__header">
          <div>
            <h1 id="page-title" tabIndex={-1}>
              Accessibility map
            </h1>
            <p>
              Iloilo City · {list.length} barangays{bundle.cells.status === "ok" ? ` · ${fixed(bundle.cells.data.length, 0)} cells` : ""}
              {bundle.facilities.status === "ok" ? ` · ${fixed(facFeats.length, 0)} facilities` : ""}
            </p>
          </div>
          <button
            type="button"
            className="btn btn--sm ctl-toggle-mobile"
            id="ctl-toggle"
            aria-expanded={ctlOpen}
            aria-controls="map-ctl"
            onClick={() => setCtlOpen((c) => !c)}
          >
            <Icon name="sliders" />
            Controls
          </button>
        </div>
        <div id="map-ctl">
          <Controls b={bundle} list={list} o={o} setLyr={setLyr} />
        </div>
      </aside>
      <div className="mappage__map">
        <div id="leaflet" ref={el} role="region" aria-label="Map of Iloilo City. A table of the same values is available with the View as table button." />
        {bundle.cells.status === "failed" && (
          <div className="map-status">
            <Badge tone="error">Cell layer unavailable: cells dataset failed to load</Badge>
          </div>
        )}
        <div className="map-toolbar">
          <button type="button" className="btn btn--sm" id="map-view-table" aria-pressed={o.table} onClick={() => set({ view: o.table ? null : "table" })}>
            <Icon name="table" />
            View as table
          </button>
        </div>
        <div className="map-legend" id="map-legend" aria-label="Legend" role="region" data-collapsed={String(legendCollapsed)}>
          <Legend b={bundle} list={list} o={o} collapsed={legendCollapsed} onToggle={() => setLegendCollapsed((c) => !c)} nFacs={visibleFacs.length} />
        </div>
        <div className="map-table" id="map-table" hidden={!o.table}>
          {o.table && (
            <MapTable
              list={list}
              onOpen={(code) => {
                set({ b: code, view: null });
                setTimeout(() => document.querySelector<HTMLElement>("#b-drawer .drawer__close")?.focus(), 0);
              }}
              onBack={() => {
                set({ view: null });
                setTimeout(() => document.getElementById("map-view-table")?.focus(), 0);
              }}
            />
          )}
        </div>
        {selected && (
          <aside
            className="drawer"
            id="b-drawer"
            aria-label="Barangay details"
            onKeyDown={(e) => {
              if (e.key === "Escape") set({ b: null });
            }}
          >
            <BarangayPanel b={selected} groups={groups} walkT={bundle.manifest.thresholds_min.walk} driveT={bundle.manifest.thresholds_min.drive} compact onClose={() => set({ b: null })} />
          </aside>
        )}
      </div>
    </div>
  );
}
