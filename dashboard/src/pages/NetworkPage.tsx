/**
 * Network Connectivity (#/network): evidence only throughout. The A1/A2/A3 approach comparison, the
 * A1 -> A3 transition (absent pairs are not zero), component classes and the component table, a map of
 * the mapped fragment geometries with gap lines (other components only as dashed, labelled bounding
 * boxes), the gap evidence and the access-tag analysis, each record stamped "not applied".
 */
import type * as LeafletNS from "leaflet";
import { type CSSProperties, Fragment, type ReactNode, useRef } from "react";
import { Chips } from "../components/notes.tsx";
import { guard, Unavailable } from "../components/states/States.tsx";
import { Badge, CatSym, Check, Int, MetricTile, Num, NullValue, PageHeader, PageSection, PageToc, Panel, PropBar, Role, Scen, Stamp } from "../components/ui.tsx";
import type { Network } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { BasemapSwitcher } from "../map/BasemapSwitcher.tsx";
import { useBasemapChoice, useBasemapLayer, useLeaflet } from "../map/leaflet.ts";
import { esc, fixed } from "../model/format.ts";
import { CATEGORIES, componentClassLabel, underscores } from "../model/labels.ts";
import { barangaysOf, boundsOf } from "../model/values.ts";
import { useNotes } from "../components/notes.tsx";
import { useView } from "../view.tsx";

const APPROACH: Record<string, [ReactNode, ReactNode]> = {
  A1_baseline: [<Scen k="a1" text="A1 · walk" />, <Role k="comparative" />],
  A2_all_eligible: [<Scen k="a2" text="A2 · walk" />, <Role k="evidence" />],
  A3_component_aware: [<Scen k="a3" text="A3 · walk" />, <Role k="primary" />],
};

function approaches(n: Network, total: number) {
  const rec = (r: object, id: string) => (r as Record<string, number | null>)[`pop_${id}`] ?? 0;
  const notMain = (r: object) => CATEGORIES.filter((c) => c.id !== "network_connected").reduce((s, c) => s + rec(r, c.id), 0);
  const nmMax = Math.max(1e-9, ...n.approaches.map(notMain));
  return (
    <Panel id="appr" cls="panel--evidence" title="Approach comparison: A1, A2, A3" tags={<Role k="evidence" />} sub="How each connectivity rule assigns residents to categories. A3 is the reporting scenario used everywhere else; A2 appears only here." codes={["DQ-A1-OPT"]}>
      <div className="table-wrap">
        <table className="data-table">
          <caption className="visually-hidden">Approach comparison</caption>
          <thead>
            <tr className="data-table__group">
              <th colSpan={4} />
              <th colSpan={4} className="col-sep">
                Residents by category (of {fixed(total, 0)})
              </th>
            </tr>
            <tr>
              <th scope="col">Approach</th>
              <th scope="col" className="n">
                Components retained
              </th>
              <th scope="col" className="n">
                Network km
              </th>
              <th scope="col" className="n appr__dist-h">
                Not network-connected
              </th>
              {CATEGORIES.map((c, i) => (
                <th key={c.id} scope="col" className={`n${i ? "" : " col-sep"}`}>
                  <CatSym id={c.id} /> {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {n.approaches.map((r) => (
              <tr key={r.approach}>
                <th scope="row" className="appr__name">
                  <div style={{ display: "flex", gap: ".25rem", flexWrap: "wrap", marginBottom: ".2rem" }}>{APPROACH[r.approach] ?? <code>{r.approach}</code>}</div>
                  <span className="small muted" style={{ display: "block" }}>
                    {r.scenario_label}
                  </span>
                </th>
                <td className="n">
                  <Int v={r.components_retained} />
                </td>
                <td className="n">
                  <Num v={r.network_km} d={1} />
                </td>
                <td className="n appr__dist">
                  <span className="appr__nm">{fixed(notMain(r), 1)}</span>
                  <span className="appr__bar" style={{ width: `${(100 * notMain(r)) / nmMax}%` }}>
                    <PropBar label={`Residents not network-connected under ${r.approach}`} parts={CATEGORIES.filter((c) => c.id !== "network_connected").map((c) => ({ key: c.id, n: rec(r, c.id), cls: `propbar__seg--${c.id}`, text: c.label.toLowerCase() }))} />
                  </span>
                </td>
                {CATEGORIES.map((c, i) => (
                  <td key={c.id} className={`n${i ? "" : " col-sep"}`}>
                    <Num v={(r as unknown as Record<string, number | null>)[`pop_${c.id}`]} d={1} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="chart-summary">The bar splits the residents who are not network-connected by category; its length is relative to the largest of the three approaches.</p>
      <div className="legend-inline cat-legend">
        {CATEGORIES.filter((c) => c.id !== "network_connected").map((c) => (
          <span key={c.id} className="legend-inline__item">
            <span className={`legend__sw propbar__seg--${c.id}`} aria-hidden="true" />
            <CatSym id={c.id} /> {c.label}
          </span>
        ))}
      </div>
    </Panel>
  );
}

function transition(n: Network) {
  const T = n.transition_a1_to_a3;
  const rows = [...new Set(T.map((x) => x.a1_category))];
  const get = (a1: string, a3: string) => T.find((x) => x.a1_category === a1 && x.a3_category === a3);
  const cross = T.filter((x) => x.a1_category !== x.a3_category && x.pop > 0).sort((a, b) => b.pop - a.pop);
  // shading on a log scale, so the small cross-category flows stay visible beside the large diagonal
  const max = Math.log10(1 + Math.max(1, ...T.map((x) => x.pop)));
  const heat = (v: number) => (v > 0 ? Math.log10(1 + v) / max : 0);
  return (
    <Panel id="trans" cls="panel--evidence" title="A1 → A3 population transition" tags={<Role k="evidence" />}>
      <table className="matrix matrix--heat">
        <caption className="visually-hidden">Residents by A1 category (rows) and A3 category (columns)</caption>
        <thead>
          <tr>
            <th scope="col">A1 ↓ · A3 →</th>
            {CATEGORIES.map((c) => (
              <th key={c.id} scope="col">
                <CatSym id={c.id} /> {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th scope="row">{r === "network_connected" ? "A1 connected" : r === "unconnected" ? "A1 not connected" : `A1 ${underscores(r)}`}</th>
              {CATEGORIES.map((c) => {
                const t = get(r, c.id);
                return t ? (
                  <td key={c.id} style={{ "--heat": heat(t.pop).toFixed(3) } as CSSProperties} data-same={r === c.id ? "true" : undefined}>
                    {fixed(t.pop, 1)}
                  </td>
                ) : (
                  <td key={c.id} className="absent" title="Absent pair: no residents in this combination (not a zero value)">
                    absent
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="chart-summary">
        {cross
          .slice(0, 2)
          .map((x) => `${fixed(x.pop, 1)} residents ${x.a1_category === "network_connected" ? "connected" : "not connected"} under A1 are ${CATEGORIES.find((c) => c.id === x.a3_category)?.label.toLowerCase() ?? x.a3_category} under A3`)
          .join("; ")}
        {cross.length ? ". " : ""}Darker cells hold more residents (log scale). Hatched cells are pairs absent from the bundle, not zeros.
      </p>
    </Panel>
  );
}

function classes(n: Network) {
  const rows = [...n.component_classes].sort((a, b) => b.pop_attached_A3 - a.pop_attached_A3);
  return (
    <Panel id="cls" cls="panel--evidence" title="Component classes" tags={<Role k="evidence" />}>
      <table className="data-table data-table--compact">
        <thead>
          <tr>
            <th scope="col">Class</th>
            <th scope="col" className="n">
              Components
            </th>
            <th scope="col" className="n">
              km
            </th>
            <th scope="col" className="n">
              Residents attached (A3)
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.component_class}>
              <th scope="row" style={{ fontWeight: 400 }}>
                {componentClassLabel(r.component_class)}
              </th>
              <td className="n">{r.components}</td>
              <td className="n">
                <Num v={r.length_km} d={2} />
              </td>
              <td className="n">
                <Num v={r.pop_attached_A3} d={1} />
              </td>
            </tr>
          ))}
          <tr>
            <th scope="row">All</th>
            <td className="n">
              <b>{n.components.length}</b>
            </td>
            <td />
            <td />
          </tr>
        </tbody>
      </table>
    </Panel>
  );
}

const COMP_COLS: [key: string, label: string, text?: boolean][] = [
  ["fragment", "Component", true],
  ["component_class", "Class", true],
  ["length_km", "Length km"],
  ["gap_to_main_m", "Gap to main (m)"],
  ["pop_attached_A3", "Residents (A3)"],
  ["cells_attached_A3", "Cells"],
  ["km_private", "km private"],
  ["km_no", "km access=no"],
  ["retained_A3", "Retained A3", true],
  ["geometry_kind", "Geometry", true],
];

function ComponentTable({ n }: { n: Network }) {
  const { p, set } = useView();
  const key = COMP_COLS.some((c) => c[0] === p["csort"]) ? (p["csort"] as string) : "pop_attached_A3";
  const dir = p["cdir"] === "asc" ? "asc" : "desc";
  const val = (r: object, k: string) => (r as Record<string, unknown>)[k];
  const rows = [...n.components].sort((a, b) => {
    const x = val(a, key);
    const y = val(b, key);
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return dir === "asc" ? c : -c;
  });
  return (
    <div className="table-wrap" style={{ maxHeight: "26rem" }}>
      <table className="data-table data-table--compact">
        <caption className="visually-hidden">All {n.components.length} walk-network components</caption>
        <thead>
          <tr>
            {COMP_COLS.map(([k, l, text]) => (
              <th key={k} scope="col" className={text ? "" : "n"} aria-sort={key === k ? (dir === "asc" ? "ascending" : "descending") : undefined}>
                <button type="button" className="sort-btn" id={`cs-${k}`} onClick={() => set({ csort: k, cdir: key === k && dir !== "asc" ? "asc" : "desc" })}>
                  {l}
                  <span className="sort-ind" aria-hidden="true">
                    {key === k ? (dir === "asc" ? "▲" : "▼") : "↕"}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.fragment}>
              <th scope="row" className="mono" style={{ fontWeight: 500 }}>
                {r.fragment}
              </th>
              <td>{componentClassLabel(r.component_class)}</td>
              <td className="n">
                <Num v={r.length_km} d={2} />
              </td>
              <td className="n">{r.gap_to_main_m === null ? <NullValue reason="No gap value" /> : fixed(r.gap_to_main_m, 1)}</td>
              <td className="n">
                <Num v={r.pop_attached_A3} d={1} />
              </td>
              <td className="n">
                <Int v={r.cells_attached_A3} />
              </td>
              <td className="n">
                <Num v={r.km_private} d={2} />
              </td>
              <td className="n">
                <Num v={r.km_no} d={2} />
              </td>
              <td>{r.retained_A3 ? "Yes" : "No"}</td>
              <td className="small">{r.geometry_kind === "bounding_box" ? "bounding box only" : underscores(r.geometry_kind)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const yesNo = (status: string, good: string) => (status === good ? "ok" : "warn");

/** "way/1;way/2" with a line-break opportunity after each ";", so long OSM way lists wrap between ids. */
const breakAfterSemicolons = (s: string) =>
  s.split(";").map((part, i) => (
    <Fragment key={i}>
      {i > 0 && (
        <>
          ;<wbr />
        </>
      )}
      {part}
    </Fragment>
  ));

function gapCards(n: Network, analysisText: string | undefined) {
  return (
    <div className="gap-cards">
      {n.gap_evidence.map((g) => {
        const gates = (g.snapshot_corridor_gates ?? "").split(";").filter((x) => x.trim());
        const ways = (g.snapshot_link_ways ?? "").split(";").filter((x) => x.trim());
        return (
          <article key={g.fragment} className="gap-card" aria-labelledby={`gap-${g.fragment}`}>
            <header className="gap-card__head">
              <div>
                <h3 id={`gap-${g.fragment}`}>{g.fragment}</h3>
                <span className="gap-card__class">{componentClassLabel(g.component_class)}</span>
              </div>
              <Role k="evidence" />
            </header>
            <dl className="gap-card__figs">
              <div>
                <dt>Gap in walk cache</dt>
                <dd>
                  {g.cache_gap_to_main_m === null ? <NullValue /> : <>{fixed(g.cache_gap_to_main_m, 1)}<small> m</small></>}
                </dd>
              </div>
              <div>
                <dt>Mapped link</dt>
                <dd>{g.snapshot_link_m === null ? <NullValue /> : <>{fixed(g.snapshot_link_m, 1)}<small> m</small></>}</dd>
              </div>
              <div>
                <dt>Gates on corridor</dt>
                <dd>{gates.length}</dd>
              </div>
            </dl>
            <dl className="gap-card__fields">
              <div className="gap-card__field">
                <dt>Physical connection</dt>
                <dd>
                  <Badge tone="info">{underscores(g.snapshot_physical_connection)}</Badge>
                </dd>
              </div>
              <div className="gap-card__field">
                <dt>Mapped access</dt>
                <dd>
                  <code>{g.snapshot_link_access_tags ?? "—"}</code>
                </dd>
              </div>
              <div className="gap-card__field">
                <dt>Public pedestrian status</dt>
                <dd>
                  <Badge tone={yesNo(g.snapshot_public_pedestrian_status, "public")}>{underscores(g.snapshot_public_pedestrian_status)}</Badge>
                </dd>
              </div>
              <div className="gap-card__field">
                <dt>Authorised group</dt>
                <dd>
                  <Badge tone="unknown">{underscores(g.snapshot_authorized_group)}</Badge>
                </dd>
              </div>
              <div className="gap-card__field">
                <dt>Field verification</dt>
                <dd>{g.snapshot_field_verification_required ? <Badge tone="warn">Required</Badge> : <Badge tone="ok">Not required</Badge>}</dd>
              </div>
              <div className="gap-card__field">
                <dt>Applied to network</dt>
                <dd>
                  {g.applied ? "Yes" : "No"} {!g.applied && <Stamp title={analysisText} />}
                </dd>
              </div>
              {g.cache_noexit_at_gap && (
                <div className="gap-card__field">
                  <dt>At the gap</dt>
                  <dd>
                    <code>noexit=yes</code>
                  </dd>
                </div>
              )}
            </dl>
            <p className="gap-card__reason">{g.classification_reason}</p>
            {ways.length > 0 && (
              <details className="gap-card__ways">
                <summary>
                  {ways.length} OSM way{ways.length === 1 ? "" : "s"} on the link
                </summary>
                <p className="mono">{breakAfterSemicolons(g.snapshot_link_ways ?? "")}</p>
              </details>
            )}
            <div className="gap-card__foot">
              <Chips codes={["DQ-PHYS-NOT-PUBLIC", "DQ-ANALYSIS-ONLY"]} />
            </div>
          </article>
        );
      })}
    </div>
  );
}

function access(n: Network, analysisText: string | undefined) {
  const stamp = (applied: boolean) => (applied ? <Badge tone="warn">Applied</Badge> : <Stamp title={analysisText} />);
  const kmMax = Math.max(1e-9, ...n.access_classification.map((a) => a.km ?? 0));
  const loseMax = Math.max(1e-9, ...n.access_impact.map((a) => a.pop_lose_network ?? 0));
  const bar = (v: number | null | undefined, max: number) => (
    <span className="inline-bar inline-bar--evidence" aria-hidden="true">
      <span className="inline-bar__fill" style={{ width: `${(100 * (v ?? 0)) / max}%` }} />
    </span>
  );
  return (
    <div className="stack">
      <div>
        <Panel id="acc" cls="panel--evidence" title="Access-tag classification" tags={<Role k="analysis" />} sub="How mapped access tags would classify ways and gate nodes for pedestrians. Reported, not applied." codes={["DQ-ANALYSIS-ONLY"]}>
          <div className="table-wrap">
            <table className="data-table data-table--compact">
              <caption className="visually-hidden">Access-tag classification</caption>
              <thead>
                <tr>
                  <th scope="col">Kind</th>
                  <th scope="col">Access class</th>
                  <th scope="col">Public pedestrian status</th>
                  <th scope="col" className="n">
                    km
                  </th>
                  <th scope="col" className="n">
                    km in main
                  </th>
                  <th scope="col" className="n">
                    Gate nodes
                  </th>
                  <th scope="col">Record</th>
                </tr>
              </thead>
              <tbody>
                {n.access_classification.map((a, i) => (
                  <tr key={i}>
                    <td>{a.kind}</td>
                    <td>
                      <code>{a.access_class}</code>
                    </td>
                    <td>{underscores(a.public_pedestrian_status)}</td>
                    <td className="n">
                      <Num v={a.km} d={2} />
                      {bar(a.km, kmMax)}
                    </td>
                    <td className="n">
                      <Num v={a.km_main} d={2} />
                    </td>
                    <td className="n">
                      <Int v={a.nodes} />
                    </td>
                    <td>{stamp(a.applied)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
      <div>
        <Panel id="imp" cls="panel--evidence" title="What-if access impact" tags={<Role k="analysis" />} sub="What would change if each tag rule were applied to the network. None of these is applied to the network or to any indicator." codes={["DQ-ANALYSIS-ONLY"]}>
          <div className="table-wrap">
            <table className="data-table data-table--compact">
              <caption className="visually-hidden">What-if access-impact scenarios</caption>
              <thead>
                <tr>
                  <th scope="col">What-if scenario</th>
                  <th scope="col" className="n">
                    km removed (main)
                  </th>
                  <th scope="col" className="n">
                    Residents would lose network
                  </th>
                  <th scope="col" className="n">
                    Would become local
                  </th>
                  <th scope="col" className="n">
                    Time up &gt; 1 min
                  </th>
                  <th scope="col">Record</th>
                </tr>
              </thead>
              <tbody>
                {n.access_impact.map((a) => (
                  <tr key={a.scenario}>
                    <th scope="row" style={{ fontWeight: 400 }}>
                      <code>{a.scenario}</code>
                      <span className="small muted" style={{ display: "block", maxWidth: "22rem" }}>
                        {a.definition ?? ""}
                      </span>
                    </th>
                    <td className="n">
                      <Num v={a.km_removed_main} d={2} />
                    </td>
                    <td className="n">
                      <Num v={a.pop_lose_network} d={1} />
                      {bar(a.pop_lose_network, loseMax)}
                    </td>
                    <td className="n">
                      <Num v={a.pop_become_local} d={1} />
                    </td>
                    <td className="n">
                      <Num v={a.pop_time_up_gt1min} d={1} />
                    </td>
                    <td>{stamp(a.applied)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function FragmentMap({ bundle, n, bboxText }: { bundle: LoadedBundle; n: Network; bboxText: string | undefined }) {
  const { p, set } = useView();
  const el = useRef<HTMLDivElement>(null);
  const showBox = p["bbox"] !== "0";
  const brgy = barangaysOf(bundle) ?? [];
  const boxes = useRef<LeafletNS.LayerGroup | null>(null);
  const handle = useLeaflet(el, boundsOf(brgy), (L, map) => {
    const outlines = brgy.filter((b) => b.geometry).map((b) => ({ type: "Feature" as const, geometry: b.geometry as never, properties: {} }));
    L.geoJSON(outlines, { style: { color: "#334155", weight: 0.5, fillColor: "#fff", fillOpacity: 0.15 }, interactive: false }).addTo(map);
    const box = L.layerGroup();
    for (const c of n.components) {
      if (c.fragment === "main" || c.geometry_kind !== "bounding_box" || !c.bbox) continue;
      const b = c.bbox;
      L.rectangle(
        [
          [b.lat_min, b.lon_min],
          [b.lat_max, b.lon_max],
        ],
        { color: "#5c4a1e", weight: 1, dashArray: "4 3", fill: false },
      )
        .bindTooltip(`<b class="mono">${esc(c.fragment)}</b> · bounding box<br>${esc(componentClassLabel(c.component_class))}<br><span class="muted">${esc(bboxText ?? "")}</span>`, { className: "map-tip" })
        .addTo(box);
    }
    boxes.current = box;
    L.geoJSON(n.fragment_geometries as never, {
      style: (f) => ((f?.properties as { geometry_kind: string }).geometry_kind === "gap_line" ? { color: "#a1121f", weight: 2, dashArray: "2 4" } : { color: "#563b86", weight: 3 }),
      onEachFeature: (f, l) => {
        const pr = f.properties as { fragment: string; geometry_kind: string; n_edges?: number; length_km?: number; gap_to_main_m?: number | null };
        const gap = pr.gap_to_main_m === null || pr.gap_to_main_m === undefined ? "?" : fixed(pr.gap_to_main_m, 1);
        l.bindTooltip(pr.geometry_kind === "gap_line" ? `<b class="mono">${esc(pr.fragment)}</b> gap line to main: ${gap} m` : `<b class="mono">${esc(pr.fragment)}</b> mapped fragment geometry<br>${pr.n_edges ?? "?"} edges · ${pr.length_km === undefined ? "?" : fixed(pr.length_km, 2)} km · gap ${gap} m`, { className: "map-tip", sticky: true });
      },
    }).addTo(map);
    return box;
  });
  const [basemap, setBasemap] = useBasemapChoice();
  useBasemapLayer(handle, basemap);
  if (handle && boxes.current) {
    if (showBox && !handle.map.hasLayer(boxes.current)) boxes.current.addTo(handle.map);
    if (!showBox && handle.map.hasLayer(boxes.current)) handle.map.removeLayer(boxes.current);
  }
  return (
    <>
      <div className="map-toolbar">
        <div className="legend-inline">
          <span className="legend-inline__item">
            <span className="lg-line lg-line--frag" aria-hidden="true" />
            Mapped fragment geometry
          </span>
          <span className="legend-inline__item">
            <span className="lg-line lg-line--gap" aria-hidden="true" />
            Gap line to main
          </span>
          <span className="legend-inline__item">
            <span className="lg-box" aria-hidden="true" />
            Bounding box only
          </span>
        </div>
        <Check id="nb-bbox" checked={showBox} onChange={(on) => set({ bbox: on ? null : "0" })}>
          Show component bounding boxes (dashed, labelled “bounding box”)
        </Check>
      </div>
      <div style={{ position: "relative", height: "28rem", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
        <div id="net-map" ref={el} style={{ position: "absolute", inset: 0 }} role="region" aria-label="Map of fragment geometries; the component table below lists the same components" />
        <BasemapSwitcher id="bm-n" value={basemap} onChange={setBasemap} />
      </div>
    </>
  );
}

export function NetworkPage({ bundle }: { bundle: LoadedBundle }) {
  const { statement } = useNotes();
  if (bundle.network.status !== "ok") {
    return (
      <div className="page">
        <PageHeader title="Network connectivity" />
        <Unavailable bundle={bundle} dataset="network" what="Network connectivity" />
      </div>
    );
  }
  const n = bundle.network.data;
  const analysis = statement("DQ-ANALYSIS-ONLY")?.text;
  return (
    <div className="page page--research">
      <PageHeader eyebrow="For researchers · walk network evidence" title="Network connectivity" lead="How the walk network is split into components, and why some residents have no citywide time. Nothing on this page changes an indicator." />
      <div className="evidence-band" role="note">
        <strong>Evidence only.</strong> <Role k="evidence" /> <Role k="analysis" />
        <span>This page documents the network behind A3. A2, access tags and what-if scenarios appear only here and are never applied.</span>
      </div>
      <PageToc
        items={[
          ["n-summary", "Summary"],
          ["n-approaches", "Approaches"],
          ["n-components", "Components"],
          ["n-gaps", "Gap evidence"],
          ["n-access", "Access tags"],
        ]}
      />
      <PageSection id="n-summary" title="Summary">
        {guard("The network summary", () => {
          const main = n.components.find((c) => c.fragment === "main");
          const mapped = new Set(n.fragment_geometries.features.filter((f) => f.properties.geometry_kind !== "gap_line").map((f) => f.properties.fragment));
          return (
            <div className="metrics metrics--4">
              <MetricTile value={n.components.length} label="Walk-network components" detail={main ? `1 main + ${n.components.length - 1} fragments` : "no main component listed"} />
              <MetricTile value={main ? fixed(main.length_km, 1) : "—"} label="Main network" detail="km of walkable edges" />
              <MetricTile value={mapped.size} label="Fragments with line geometry" detail="the rest as bounding boxes" />
              <MetricTile value={n.gap_evidence.length} label="With gap evidence" detail={n.gap_evidence.map((g) => g.fragment).join(", ") || "none"} />
            </div>
          );
        })}
      </PageSection>
      <PageSection id="n-approaches" title="Approaches" lead="How A1, A2 and A3 assign residents to connectivity categories, and where residents move between A1 and A3.">
        {guard("The approach comparison", () => approaches(n, bundle.city.population.total))}
        <div className="grid" style={{ marginTop: "var(--space-4)" }}>
          <div className="span-7">{guard("The A1 → A3 transition", () => transition(n))}</div>
          <div className="span-5">{guard("The component classes", () => classes(n))}</div>
        </div>
      </PageSection>
      <PageSection id="n-components" title="Components">
        <div className="stack">
          {guard("The fragment map", () => {
            // read here, so a missing part is reported by guard() instead of failing the page
            void n.components.length;
            void n.fragment_geometries.features.length;
            return (
              <Panel id="nmap" cls="panel--evidence" title="Fragments and gaps" tags={<Role k="evidence" />} sub="Bounding boxes show where the other components are, not their geometry. The main network's geometry is not in the bundle." codes={["DQ-BBOX"]}>
                <FragmentMap bundle={bundle} n={n} bboxText={statement("DQ-BBOX")?.text} />
              </Panel>
            );
          })}
          {guard("The component table", () => {
            void n.components.length; // see above
            return (
              <Panel id="comp" cls="panel--evidence" title={`All ${n.components.length} components`} tags={<Role k="evidence" />} sub="Sort by any column.">
                <ComponentTable n={n} />
              </Panel>
            );
          })}
        </div>
      </PageSection>
      <PageSection id="n-gaps" title="Gap evidence" kind="evidence" tags={<Role k="evidence" />} lead="Fragments that look connected in OSM topology but only through access-restricted corridors. Physical connection, mapped access, public pedestrian status and authorised group are separate facts.">
        {guard("The gap evidence", () => gapCards(n, analysis))}
      </PageSection>
      <PageSection id="n-access" title="Access tags" kind="evidence" tags={<Role k="analysis" />} lead="Classification and what-if scenarios, stamped on every record.">
        {guard("The access-tag analysis", () => access(n, analysis))}
      </PageSection>
    </div>
  );
}
