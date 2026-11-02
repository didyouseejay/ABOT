/**
 * Facilities (#/facilities): the mapped places on a map and in a list with the same filter (type and
 * name), and a card for the selected place. Counts are row counts of facilities.geojson. The
 * classification, duplicate review and per-group inventory are on Data quality, for researchers.
 */
import type * as LeafletNS from "leaflet";
import { useEffect, useRef, useState } from "react";
import { Glyph } from "../components/glyphs.tsx";
import { EmptyState, Unavailable } from "../components/states/States.tsx";
import { PageHeader } from "../components/ui.tsx";
import type { FacilityProps, Feature } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { BasemapSwitcher } from "../map/BasemapSwitcher.tsx";
import { type L, useBasemapChoice, useBasemapLayer, useLeaflet } from "../map/leaflet.ts";
import { fixed } from "../model/format.ts";
import { FAC_CATS, facCatName, serviceName, underscores } from "../model/labels.ts";
import { ramps } from "../model/ramps.ts";
import { barangaysOf, boundsOf } from "../model/values.ts";
import { useView } from "../view.tsx";
import { drawFacilities } from "./MapPage.tsx";

/** "primary_care_clinic" -> "Primary care clinic". */
const kind = (s: string | null | undefined) => {
  const t = underscores(s);
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
};

/** "Health · Primary care", or just "Banks" when the subtype only repeats the category. */
const typeLine = (f: FacilityProps) => {
  const c = facCatName(f.category);
  const k = kind(f.subtype);
  return !k || c.toLowerCase().startsWith(k.toLowerCase().slice(0, 4)) ? c : `${c} · ${k}`;
};

function Card({ f, onClose }: { f: FacilityProps; onClose: () => void }) {
  const used = (f.destination_groups ?? []).length > 0;
  return (
    <div className="fac-card" aria-live="polite">
      <div className="fac-card__head">
        <span className="fac-dot fac-dot--lg" style={{ background: `var(--fac-${f.category})` }} aria-hidden="true" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="drawer__eyebrow">{typeLine(f)}</p>
          <h2 id="fac-title">{f.name ?? "Unnamed place"}</h2>
        </div>
        <button type="button" className="drawer__close" id="fac-close" aria-label="Close" onClick={onClose}>
          <Glyph name="close" />
        </button>
      </div>
      <dl className="kv">
        <dt>Location</dt>
        <dd>{f.inside_city ? "Inside Iloilo City" : "Just outside Iloilo City (within 3 km)"}</dd>
        <dt>Counted in travel times</dt>
        <dd>
          {used
            ? `Yes, as ${(f.destination_groups ?? []).map((g) => serviceName(g).toLowerCase()).join(", ")}`
            : f.conn_status !== "connected"
              ? "No: it is not linked to the street network in the map data"
              : "No: this type of place is shown on the map but not timed"}
        </dd>
      </dl>
      <a className="btn btn--sm" href={`https://www.openstreetmap.org/${f.osm_type}/${f.osm_id}`} target="_blank" rel="noopener noreferrer">
        <Glyph name="externalLink" />
        View on OpenStreetMap
      </a>
    </div>
  );
}

export function FacilitiesPage({ bundle }: { bundle: LoadedBundle }) {
  const { p, set, href } = useView();
  const [q, setQ] = useState(p["fq"] ?? "");
  const el = useRef<HTMLDivElement>(null);
  const live = useRef(set);
  live.current = set;
  const [basemap, setBasemap] = useBasemapChoice();
  const feats: Feature<FacilityProps>[] = bundle.facilities.status === "ok" ? bundle.facilities.data.features : [];
  const cat = p["fcat"] && (FAC_CATS as readonly string[]).includes(p["fcat"]) ? p["fcat"] : "";
  const ql = (p["fq"] ?? "").toLowerCase();
  const list = feats.filter((f) => (!cat || f.properties.category === cat) && (!ql || (f.properties.name ?? "unnamed").toLowerCase().includes(ql)));
  const selected = p["f"] ? feats.find((f) => f.properties.fid_key === p["f"])?.properties : undefined;
  const brgy = barangaysOf(bundle) ?? [];
  const counts = new Map<string, number>(FAC_CATS.map((c) => [c, feats.filter((f) => f.properties.category === c).length]));

  useEffect(() => {
    const id = setTimeout(() => {
      if ((p["fq"] ?? "") !== q) set({ fq: q || null });
    }, 150);
    return () => clearTimeout(id);
    // only the typed text drives this; the address is written once typing pauses
  }, [q]);

  const handle = useLeaflet<{ facs: LeafletNS.LayerGroup; outlines: LeafletNS.GeoJSON }>(el, boundsOf(brgy), (L, map) => {
    const outlines = brgy.filter((b) => b.geometry).map((b) => ({ type: "Feature" as const, geometry: b.geometry as never, properties: {} }));
    return { outlines: L.geoJSON(outlines, { interactive: false }).addTo(map), facs: L.layerGroup().addTo(map) };
  });
  useBasemapLayer(handle, basemap);
  useEffect(() => {
    if (!handle) return;
    handle.layers.outlines.setStyle({ color: "#334155", weight: 0.8, opacity: 0.7, fillColor: "#ffffff", fillOpacity: basemap === "none" ? 0.6 : 0 });
    drawFacilities(handle.L as L, handle.layers.facs, list, (f) => ramps().fac[f.category] ?? "#0f172a", p["f"] ?? null, (f) => live.current({ f: f.fid_key }));
    // redrawn from the address (p) and the background; the list derives from the address
  }, [handle, p, basemap]);

  const shown = p["fall"] === "1" ? list : list.slice(0, 100);

  return (
    <div className="page">
      <PageHeader title="Facilities" lead="Hospitals, health centers, schools, markets and other public places mapped in and around Iloilo City. Choose a type or search by name." />
      {bundle.facilities.status === "ok" ? (
        <>
          <div className="toolbar card" role="search" aria-label="Filter facilities">
            <div className="chipset" role="group" aria-label="Type of place">
              <button type="button" className="chip-toggle" id="fc-all" aria-pressed={!cat} onClick={() => set({ fcat: null, f: null })}>
                All <span className="chip-toggle__n">{fixed(feats.length, 0)}</span>
              </button>
              {FAC_CATS.map((c) => (
                <button key={c} type="button" className="chip-toggle" id={`fc-${c}`} aria-pressed={cat === c} onClick={() => set({ fcat: cat === c ? null : c, f: null })}>
                  <span className="fac-dot" style={{ background: `var(--fac-${c})` }} aria-hidden="true" />
                  {facCatName(c)} <span className="chip-toggle__n">{fixed(counts.get(c) ?? 0, 0)}</span>
                </button>
              ))}
            </div>
            <label className="field toolbar__search" htmlFor="ff-q">
              <span className="field__label">Search by name</span>
              <span className="input-icon">
                <Glyph name="search" />
                <input className="input" type="search" id="ff-q" value={q} placeholder="e.g. Iloilo Doctors" onChange={(e) => setQ(e.target.value)} />
              </span>
            </label>
          </div>
          <div className="fac-layout">
            <div className="fac-map">
              <div ref={el} className="fac-map__leaflet" role="region" aria-label="Map of facilities. The list beside it contains the same places." />
              <BasemapSwitcher id="bm-f" value={basemap} onChange={setBasemap} />
            </div>
            <div className="fac-list card">
              {selected && (
                <Card
                  f={selected}
                  onClose={() => {
                    const k = p["f"];
                    set({ f: null });
                    setTimeout(() => document.getElementById(`fr-${k}`)?.focus(), 0);
                  }}
                />
              )}
              <p className="fac-list__count" aria-live="polite">
                {fixed(list.length, 0)} {list.length === 1 ? "place" : "places"}
              </p>
              <div className="fac-list__scroll" id="fac-scroll" role="list" aria-label="Facilities">
                {list.length === 0 ? (
                  <EmptyState
                    title="No places match"
                    action={
                      <button
                        type="button"
                        className="btn btn--sm"
                        id="ff-clear"
                        onClick={() => {
                          setQ("");
                          set({ fcat: null, fq: null });
                        }}
                      >
                        Clear filters
                      </button>
                    }
                  >
                    <p>Try another name or type.</p>
                  </EmptyState>
                ) : (
                  <>
                    {shown.map(({ properties: f }) => (
                      <button
                        key={f.fid_key}
                        type="button"
                        role="listitem"
                        className="fac-row"
                        id={`fr-${f.fid_key}`}
                        aria-current={p["f"] === f.fid_key}
                        onClick={() => {
                          set({ f: f.fid_key });
                          setTimeout(() => document.getElementById("fac-close")?.focus(), 0);
                        }}
                      >
                        <span className="fac-dot" style={{ background: `var(--fac-${f.category})` }} aria-hidden="true" />
                        <span className="fac-row__text">
                          <span className="fac-row__name">{f.name ?? "Unnamed place"}</span>
                          <span className="fac-row__meta">
                            {typeLine(f)}
                            {f.inside_city ? "" : " · outside the city"}
                          </span>
                        </span>
                      </button>
                    ))}
                    {list.length > shown.length && (
                      <div className="more-row">
                        <button type="button" className="btn btn--sm" id="f-all" onClick={() => set({ fall: "1" })}>
                          Show all {fixed(list.length, 0)}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
          <p className="footnote">
            <Glyph name="info" />
            <span>
              Locations come from OpenStreetMap, a map made by volunteers, so some places may be missing or out of date. Researchers: see the <a href={href("quality")}>facility inventory and review</a>.
            </span>
          </p>
        </>
      ) : (
        <Unavailable bundle={bundle} dataset="facilities" what="The facility map and list" />
      )}
    </div>
  );
}
