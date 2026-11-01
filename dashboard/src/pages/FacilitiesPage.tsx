/**
 * Facilities (#/facilities): the mapped facilities on a map and in a list with the same filter, a
 * facility card, and the inventory per indicator group. Counts are row counts of facilities.geojson;
 * the inventory status is "unverified" wherever the bundle says so.
 */
import { useEffect, useRef, useState } from "react";
import { InventoryTable } from "../components/InventoryTable.tsx";
import { Chip, Ref } from "../components/notes.tsx";
import { EmptyState, Unavailable } from "../components/states/States.tsx";
import { Badge, Icon, Num, NullValue, PageHeader, Panel, Rel, Role, StatStrip } from "../components/ui.tsx";
import type * as LeafletNS from "leaflet";
import type { FacilityProps, Feature } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { type L, useLeaflet } from "../map/leaflet.ts";
import { fixed } from "../model/format.ts";
import { DESCRIPTIVE_ONLY, FAC_CATS, facCatLabel, groupLabel, underscores } from "../model/labels.ts";
import { ramps } from "../model/ramps.ts";
import type { Params } from "../model/view.ts";
import { barangaysOf, boundsOf, type DupStatus, dupStatus, facilitySummary } from "../model/values.ts";
import { useView } from "../view.tsx";
import { drawFacilities } from "./MapPage.tsx";

const DUP_FILTER: [string, string][] = [
  ["", "Any"],
  ["pending", "Pending"],
  ["likely", "Likely duplicate, not merged"],
  ["reviewed", "Reviewed: distinct"],
  ["none", "Not in review"],
];

function matches(f: FacilityProps, p: Params): boolean {
  const q = (p["fq"] ?? "").toLowerCase();
  return (
    (!p["fcat"] || f.category === p["fcat"]) &&
    (!p["fsub"] || f.subtype === p["fsub"]) &&
    (!p["tier"] || f.tier === p["tier"]) &&
    (!p["fg"] || (f.indicator_groups ?? []).includes(p["fg"])) &&
    (!p["loc"] || (p["loc"] === "in") === f.inside_city) &&
    (!p["conn"] || (p["conn"] === "connected") === (f.conn_status === "connected")) &&
    (!p["dup"] || dupStatus(f) === (p["dup"] as DupStatus)) &&
    (!q || (f.name ?? "unnamed").toLowerCase().includes(q))
  );
}

function Sym({ f }: { f: FacilityProps }) {
  const ind = f.tier === "indicative";
  return (
    <span
      className={`fac-sym${ind ? "" : " fac-sym--desc"}${f.inside_city ? "" : " fac-sym--out"}${f.conn_status === "connected" ? "" : " fac-sym--nc"}`}
      style={ind ? { background: `var(--fac-${f.category})` } : { borderColor: `var(--fac-${f.category})` }}
      aria-hidden="true"
    />
  );
}

function Card({ f, onClose }: { f: FacilityProps; onClose: () => void }) {
  return (
    <div className="fac-card" aria-live="polite">
      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="page__eyebrow" style={{ margin: 0 }}>
            {facCatLabel(f.category)} · {underscores(f.subtype)}
          </p>
          <h3 id="fac-title">{f.name ?? <i className="muted">Unnamed</i>}</h3>
        </div>
        <button type="button" className="drawer__close" id="fac-close" aria-label="Close facility card" onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      <dl className="kv small">
        <dt>OSM</dt>
        <dd>
          <a href={`https://www.openstreetmap.org/${f.osm_type}/${f.osm_id}`} target="_blank" rel="noopener noreferrer" className="mono">
            {f.osm_type}/{f.osm_id}
          </a>
        </dd>
        <dt>Tier</dt>
        <dd>{f.tier === "indicative" ? <Role k="primary" text="Indicative" /> : f.tier === "descriptive" ? <Role k="descriptive" /> : <Badge tone="unknown">Excluded</Badge>}</dd>
        <dt>Roles</dt>
        <dd>
          {(f.roles ?? []).map((r, i) => (
            <span key={i} style={{ display: "block" }}>
              {facCatLabel(r.category)} · {underscores(r.subtype)} · {r.tier}
              {r.primary ? " (primary)" : ""} <span className="muted">{underscores(r.status)}</span>
            </span>
          ))}
        </dd>
        <dt>Indicator groups</dt>
        <dd>{f.indicator_groups?.length ? f.indicator_groups.map(groupLabel).join(", ") : <span className="muted">none (no travel times)</span>}</dd>
        <dt>Destination for</dt>
        <dd>{f.destination_groups?.length ? f.destination_groups.map(groupLabel).join(", ") : <span className="muted">none</span>}</dd>
        <dt>Location</dt>
        <dd>{f.inside_city ? "Inside the city" : "Outside the city, in the 3 km buffer (a destination only if connected)"}</dd>
        <dt>Connection</dt>
        <dd>
          {f.conn_status === "connected" ? (
            <>
              <Badge tone="ok">Connected</Badge> <Num v={f.conn_m} d={1} /> m to the walk network
            </>
          ) : (
            <>
              <Badge tone="warn">Not connected</Badge> not used as a destination
            </>
          )}
        </dd>
        <dt>Drive access</dt>
        <dd>{f.drive_access_m === null || f.drive_access_m === undefined ? <NullValue reason="No drive access distance" short={false} /> : `${fixed(f.drive_access_m, 1)} m`}</dd>
        <dt>Classification</dt>
        <dd className="mono" style={{ fontSize: ".7rem" }}>
          {f.data_quality?.classification?.class_reason ?? f.class_reason ?? ""}
        </dd>
        <dt>Duplicate review</dt>
        <dd>
          {f.data_quality?.duplicate_review?.length ? (
            f.data_quality.duplicate_review.map((r) => (
              <span key={r.review_id} style={{ display: "block" }}>
                <span className="mono">{r.review_id}</span> {r.role} · with <span className="mono">{r.other_fid}</span> ·{" "}
                {r.review_status === "pending" ? <Badge tone="warn">Pending</Badge> : r.reviewer_decision === "likely_duplicate_not_merged" ? <Badge tone="warn">Likely duplicate, not merged</Badge> : <Badge tone="ok">Distinct, keep both</Badge>}
              </span>
            ))
          ) : (
            <span className="muted">Not in a review pair</span>
          )}
        </dd>
      </dl>
      <div className="map-legend__chips" style={{ marginTop: "var(--space-2)" }}>
        <Chip code="DQ-FAC-OSM" />
        <Chip code="DQ-DUP" />
      </div>
    </div>
  );
}

export function FacilitiesPage({ bundle }: { bundle: LoadedBundle }) {
  const { p, set } = useView();
  const [q, setQ] = useState(p["fq"] ?? "");
  const el = useRef<HTMLDivElement>(null);
  const live = useRef(set);
  live.current = set;
  const feats: Feature<FacilityProps>[] = bundle.facilities.status === "ok" ? bundle.facilities.data.features : [];
  const list = feats.filter((f) => matches(f.properties, p));
  const selected = p["f"] ? feats.find((f) => f.properties.fid_key === p["f"])?.properties : undefined;
  const brgy = barangaysOf(bundle) ?? [];
  const sum = bundle.facilities.status === "ok" ? facilitySummary(bundle.facilities.data) : null;
  const groups = bundle.manifest.indicator_groups.map((g) => g.id);
  const subs = [...new Set(feats.filter((f) => !p["fcat"] || f.properties.category === p["fcat"]).map((f) => f.properties.subtype))].filter(Boolean).sort();

  useEffect(() => {
    const id = setTimeout(() => {
      if ((p["fq"] ?? "") !== q) set({ fq: q || null });
    }, 150);
    return () => clearTimeout(id);
    // only the typed text drives this; the address is written once typing pauses
  }, [q]);

  const handle = useLeaflet<{ facs: LeafletNS.LayerGroup }>(el, boundsOf(brgy), (L, map) => {
    const outlines = brgy.filter((b) => b.geometry).map((b) => ({ type: "Feature" as const, geometry: b.geometry as never, properties: {} }));
    L.geoJSON(outlines, { style: { color: "#0e4f5c", weight: 0.6, fillColor: "#ffffff", fillOpacity: 0.35 }, interactive: false }).addTo(map);
    return { facs: L.layerGroup().addTo(map) };
  });
  useEffect(() => {
    if (!handle) return;
    drawFacilities(handle.L as L, handle.layers.facs, list, (f) => ramps().fac[f.category] ?? "#1b2a2f", p["f"] ?? null, (f) => live.current({ f: f.fid_key }));
    // redrawn from the address (p); the list derives from it
  }, [handle, p]);

  const sel = (id: string, label: string, key: string, opts: [string, string][]) => (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <select className="select" id={id} value={p[key] ?? ""} onChange={(e) => set({ [key]: e.target.value || null, ...(key === "fcat" ? { fsub: null } : {}) })}>
        {opts.map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </select>
    </label>
  );
  const clear = () => {
    setQ("");
    set({ fcat: null, fsub: null, tier: null, fg: null, loc: null, conn: null, dup: null, fq: null });
  };
  const shown = p["fall"] === "1" ? list : list.slice(0, 120);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Mapped OpenStreetMap features · city + 3 km buffer"
        title="Facilities"
        lead="Where the destinations are, how they were classified, and which ones are in duplicate review. Evacuation, transport and government are descriptive only: mapped and counted, with no travel times."
      />
      {sum && (
        <StatStrip
          items={[
            [<>{fixed(sum.total, 0)}<Ref codes={["DQ-FAC-OSM"]} /></>, "mapped features"],
            [fixed(sum.outside, 0), "outside the city (3 km buffer)"],
            [fixed(sum.unnamed, 0), "unnamed"],
            [<>{sum.pairs}<Ref codes={["DQ-DUP"]} /></>, `possible duplicate pairs: ${sum.pending} pending, ${sum.likely} likely duplicates not merged`],
            [<Rel level="unverified" />, "inventory status, every group"],
          ]}
        />
      )}
      {bundle.facilities.status === "ok" ? (
        <>
          <div className="filterbar" role="search" aria-label="Filter facilities">
            <label className="field" htmlFor="ff-q">
              <span className="field__label">Name</span>
              <input className="input" type="search" id="ff-q" value={q} placeholder="e.g. Unnamed" style={{ width: "11rem" }} onChange={(e) => setQ(e.target.value)} />
            </label>
            {sel("ff-cat", "Category", "fcat", [["", `All ${FAC_CATS.length}`], ...FAC_CATS.map((c): [string, string] => [c, facCatLabel(c) + (DESCRIPTIVE_ONLY.includes(c) ? " (descriptive)" : "")])])}
            {sel("ff-sub", "Subtype", "fsub", [["", "All"], ...subs.map((x): [string, string] => [x, underscores(x)])])}
            {sel("ff-tier", "Tier", "tier", [["", "All"], ["indicative", "Indicative"], ["descriptive", "Descriptive"], ["excluded", "Excluded"]])}
            {sel("ff-g", "Indicator group", "fg", [["", "Any"], ...groups.map((g): [string, string] => [g, groupLabel(g)])])}
            {sel("ff-loc", "Location", "loc", [["", "Inside + buffer"], ["in", "Inside city"], ["out", "Outside (3 km buffer)"]])}
            {sel("ff-conn", "Connection", "conn", [["", "Any"], ["connected", "Connected"], ["not", "Not connected"]])}
            {sel("ff-dup", "Duplicate review", "dup", DUP_FILTER)}
            <span className="filterbar__count" aria-live="polite">
              Showing <b>{list.length}</b> of {feats.length}
            </span>
          </div>
          <div className="fac-layout">
            <div className="fac-map" ref={el} role="region" aria-label="Facility map. The list beside it contains the same facilities." />
            <div className="fac-list">
              <div id="fac-card">
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
              </div>
              <div className="fac-list__scroll" id="fac-scroll" role="list" aria-label="Facilities">
                {list.length === 0 ? (
                  <EmptyState
                    title="No facilities match these filters"
                    action={
                      <button type="button" className="btn btn--sm" id="ff-clear" onClick={clear}>
                        Clear all filters
                      </button>
                    }
                  >
                    <p>Nothing is hidden for any other reason. Clear one or more filters.</p>
                  </EmptyState>
                ) : (
                  <>
                    {shown.map(({ properties: f }) => {
                      const d = dupStatus(f);
                      return (
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
                          <Sym f={f} />
                          <span style={{ minWidth: 0 }}>
                            <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name ?? <i className="muted">Unnamed</i>}</span>
                            <span className="fac-row__meta">
                              {facCatLabel(f.category)} · {underscores(f.subtype)} · {f.tier}
                            </span>
                          </span>
                          <span className="fac-row__meta" style={{ textAlign: "right" }}>
                            {!f.inside_city && <span style={{ display: "block" }}>outside city</span>}
                            {f.conn_status !== "connected" && <span style={{ display: "block" }}>not connected</span>}
                            {d === "pending" ? "dup. pending" : d === "likely" ? "likely dup." : ""}
                          </span>
                        </button>
                      );
                    })}
                    {list.length > shown.length && (
                      <div style={{ padding: "var(--space-3) var(--space-4)" }}>
                        <button type="button" className="btn btn--sm" id="f-all" onClick={() => set({ fall: "1" })}>
                          Show all {list.length}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="panel__foot" style={{ borderRadius: "0 0 var(--radius-md) var(--radius-md)" }}>
                <span className="legend-inline">
                  <span className="legend-inline__item">
                    <span className="fac-sym" style={{ background: "#1b2a2f" }} />
                    indicative
                  </span>
                  <span className="legend-inline__item">
                    <span className="fac-sym fac-sym--desc" />
                    descriptive
                  </span>
                  <span className="legend-inline__item">
                    <span className="fac-sym fac-sym--nc" style={{ background: "#fff" }} />
                    not connected
                  </span>
                  <span className="legend-inline__item">
                    <span className="fac-sym fac-sym--out" style={{ background: "#1b2a2f" }} />
                    outside city
                  </span>
                </span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <Unavailable bundle={bundle} dataset="facilities" what="The facility map and list" />
      )}
      <Panel id="inv2" title="Inventory per indicator group" tags={<Role k="descriptive" />} sub={`Counts of mapped features used for each group's travel times.${bundle.city.facility_inventory.every((r) => r["registry_reference"] === "none") ? " No group has been matched to an official registry." : ""}`} codes={["DQ-FAC-OSM", "DQ-DUP"]}>
        <InventoryTable city={bundle.city} deep />
      </Panel>
    </div>
  );
}
