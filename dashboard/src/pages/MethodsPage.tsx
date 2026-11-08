/**
 * Methodology (#/methods, for researchers): what ABOT is, the study area, the method in five steps, the scenarios
 * (definitions from manifest.scenarios), indicator definitions (one example per statistic type from the
 * catalogue, grouped by scenario and mode), limitations, documents, the citation and the data sources.
 */
import { Fragment, type ReactNode, useState } from "react";
import { Glyph, type GlyphName } from "../components/glyphs.tsx";
import { guard, Unavailable } from "../components/states/States.tsx";
import { Int, MetricTile, PageHeader, PageSection, PageToc, Panel, Role, roleOf, Scen, type ScenKey } from "../components/ui.tsx";
import type { CatalogEntry } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { fixed, formatUtc } from "../model/format.ts";
import { PROJECT } from "../components/layout/Brand.tsx";

const STEPS: [GlyphName, string, string][] = [
  ["pin", "Boundaries", "OCHA COD-AB city and barangay polygons, in UTM 51N."],
  ["users", "Census-anchored population", "WorldPop 100 m cells, weighted to PSA 2020 barangay totals."],
  ["street", "OSM networks", "Walk and drive networks, barriers and facilities for the city plus a 3 km buffer."],
  ["clock", "Nearest-facility routing", "One multi-source Dijkstra per indicator group on the reversed graph; walk at the configured speed, car uncongested."],
  ["layers", "Barangay aggregation", "Population-weighted shares within N min (all residents), mean and p90 (connected residents)."],
];

/** The three kinds of population cell, each drawn on its own so labels never collide. */
const CELL_KINDS: { key: string; title: string; svg: ReactNode; a1: string; a3: string; cat: [string, string]; note: string }[] = [
  {
    key: "connected",
    title: "Connected to the main network",
    svg: (
      <>
        <path d="M10 100 H210 M60 100 V20 M150 100 V150 M60 50 H200" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <rect x="85" y="65" width="26" height="26" rx="3" fill="var(--cat-network-connected)" opacity="0.9" />
        <line x1="98" y1="91" x2="98" y2="100" stroke="var(--color-ink)" strokeDasharray="2 2" />
      </>
    ),
    a1: "Citywide time",
    a3: "Citywide time",
    cat: ["●", "Network-connected"],
    note: "The cell snaps to an edge of the main walk network.",
  },
  {
    key: "fragment",
    title: "Attached to an isolated fragment",
    svg: (
      <>
        <path d="M10 125 H80 M40 125 V150" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M120 35 H205 M165 35 V85" stroke="var(--cat-locally-connected)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <line x1="80" y1="125" x2="120" y2="35" stroke="var(--color-error)" strokeWidth="1.5" strokeDasharray="3 4" />
        <rect x="180" y="55" width="26" height="26" rx="3" fill="var(--cat-locally-connected)" opacity="0.9" />
        <line x1="193" y1="81" x2="76" y2="125" stroke="var(--scenario-a1)" strokeDasharray="1 3" strokeWidth="1.5" />
        <text x="62" y="70" className="chart__err">
          no link
        </text>
      </>
    ),
    a1: "Citywide time, through a straight connector",
    a3: "Internal times only",
    cat: ["◆", "Locally connected"],
    note: "The fragment has no mapped link to the main network.",
  },
  {
    key: "none",
    title: "Unconnected",
    svg: (
      <>
        <path d="M10 140 H120" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <circle cx="150" cy="65" r="55" fill="none" stroke="var(--color-border-strong)" strokeDasharray="4 4" />
        <text x="158" y="135">
          250 m
        </text>
        <rect x="137" y="52" width="26" height="26" rx="3" fill="var(--cat-unconnected)" opacity="0.95" />
        <path d="M144 59 L156 71 M156 59 L144 71" stroke="#fff" strokeWidth="2" />
      </>
    ),
    a1: "No time",
    a3: "No time",
    cat: ["✕", "Unconnected"],
    note: "No walkable edge within 250 m. Still counted in every denominator.",
  },
];

const SCEN_ROW: [code: string, mode: string, k: ScenKey, where: string][] = [
  ["A3", "walk", "a3", "Every walking headline, chart and table"],
  ["A1", "walk", "a1", "Only beside an A3 value, visually subordinate"],
  ["A1", "drive", "drive", "Its own panels; never on a walking axis"],
  ["A2", "walk", "a2", "Network Connectivity only"],
];

/** One example entry per (scenario, mode, statistic): the catalogue's definitions without its 10× group repetition. */
function catalogExamples(cat: CatalogEntry[]): CatalogEntry[] {
  const seen = new Map<string, CatalogEntry>();
  for (const e of cat) {
    const k = `${e.scenario}|${e.mode}|${e.statistic}|${e.id.split(".")[1] ?? ""}`;
    if (!seen.has(k)) seen.set(k, e);
  }
  return [...seen.values()];
}

const FAMILY: Record<string, [title: string, scen?: ScenKey]> = {
  "A3.walk": ["A3 walking", "a3"],
  "A1.walk": ["A1 walking", "a1"],
  "A1.drive": ["Driving", "drive"],
  "A1.drive_sensitivity": ["Driving sensitivity", "drive"],
  "A3.population": ["Population by A3 category", "a3"],
  "A1.population": ["Population by A1 category", "a1"],
};

/** Example entries grouped by their id family ("A3.walk", "A1.drive", ...), in catalogue order. */
function families(ex: CatalogEntry[]): [string, CatalogEntry[]][] {
  const g = new Map<string, CatalogEntry[]>();
  for (const e of ex) {
    const k = e.id.split(".").slice(0, 2).join(".");
    g.set(k, [...(g.get(k) ?? []), e]);
  }
  return [...g.entries()];
}

/** "A3.walk.health_hospital.pct_le10" -> "pct_le10" (the statistic part shown big; the full id stays below). */
const statOf = (id: string) => id.split(".").slice(3).join(".") || id.split(".").slice(2).join(".") || id;

/** An id with a line-break opportunity after each ".", so it wraps between parts, not inside them. */
const dotted = (id: string) =>
  id.split(".").map((part, i) => (
    <Fragment key={i}>
      {i > 0 && (
        <>
          .<wbr />
        </>
      )}
      {part}
    </Fragment>
  ));

function Definitions({ m }: { m: LoadedBundle["manifest"] }) {
  const ex = catalogExamples(m.indicator_catalog);
  const fam = families(ex);
  return (
    <div className="defs">
      {fam.map(([k, rows], i) => {
        const [title, scen] = FAMILY[k] ?? [k];
        const roles = [...new Set(rows.map((r) => roleOf(r.role)))];
        return (
          <details key={k} className="defs__group" open={i === 0}>
            <summary className="defs__summary">
              <span className="defs__chev" aria-hidden="true" />
              <span className="defs__title">{title}</span>
              {scen && <Scen k={scen} />}
              <span className="defs__roles">
                {roles.map((r) => (
                  <Role key={r} k={r} />
                ))}
              </span>
              <span className="defs__count">
                {rows.length} statistic{rows.length === 1 ? "" : "s"}
              </span>
            </summary>
            <div className="table-wrap defs__table">
              <table className="data-table data-table--compact data-table--defs">
                <caption className="visually-hidden">{`Indicator definitions: ${title}`}</caption>
                <colgroup>
                  <col style={{ width: "20%" }} />
                  <col style={{ width: "26%" }} />
                  <col style={{ width: "13%" }} />
                  <col style={{ width: "17%" }} />
                  <col style={{ width: "10%" }} />
                  <col style={{ width: "14%" }} />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">Statistic</th>
                    <th scope="col">Numerator</th>
                    <th scope="col">Denominator</th>
                    <th scope="col">Population described</th>
                    <th scope="col">Role</th>
                    <th scope="col">Statements</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.id}>
                      <th scope="row" className="defs__stat">
                        <span className="defs__name">{statOf(c.id)}</span>
                        <span className="defs__unit">{c.unit}</span>
                        <span className="defs__id mono">{dotted(c.id)}</span>
                      </th>
                      <td>{c.numerator}</td>
                      <td>{c.denominator ?? "—"}</td>
                      <td>{c.population_described ?? "—"}</td>
                      <td>
                        <Role k={roleOf(c.role)} />
                      </td>
                      <td>
                        <span className="code-chips">
                          {c.statements.map((s) => (
                            <code key={s}>{s}</code>
                          ))}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        );
      })}
    </div>
  );
}

function Citation({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="citation-box">
      <pre className="citation">{text}</pre>
      <button
        type="button"
        className="btn btn--sm citation-box__copy"
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          });
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <span className="visually-hidden" aria-live="polite">
        {copied ? "Citation copied to the clipboard" : ""}
      </span>
    </div>
  );
}

export function MethodsPage({ bundle }: { bundle: LoadedBundle }) {
  const m = bundle.manifest;
  const prov = bundle.provenance.status === "ok" ? bundle.provenance.data : null;
  const nBrgy = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.length : null;
  const nCells = bundle.cells.status === "ok" ? bundle.cells.data.length : null;
  const nFac = bundle.facilities.status === "ok" ? bundle.facilities.data.features.length : null;
  const examples = catalogExamples(m.indicator_catalog);
  const commit = m.code.git_commit ? m.code.git_commit.slice(0, 7) : "unknown";
  const citation = `Coopera, C. J. L. (${m.generated_utc.slice(0, 4)}). ABOT: ${PROJECT.fullName}.
Accessibility to essential public facilities in Iloilo City, Philippines
[Dashboard, data contract ${m.contract} v${m.contract_version}, generated
${formatUtc(m.generated_utc)}, code ${commit}]. Independent project.`;
  return (
    <div className="page page--research">
      <PageHeader eyebrow="For researchers" title="Methodology" lead={`ABOT (“reach” in Hiligaynon and Filipino) estimates how long residents of Iloilo City take to reach essential public facilities on foot and by car, and reports the results for each of the city's ${nBrgy ?? ""} barangays.`} />
      <PageToc
        items={[
          ["m-overview", "Overview"],
          ["m-method", "Method"],
          ["m-scenarios", "Scenarios"],
          ["m-defs", "Indicator definitions"],
          ["m-limits", "Limitations & citation"],
          ["m-sources", "Data sources"],
        ]}
      />

      <PageSection id="m-overview" title="Overview">
        <div className="metrics metrics--6">
          <MetricTile value={nBrgy ?? "—"} label="Barangays" detail="Iloilo City, Philippines" />
          <MetricTile value={<Int v={m.population_total} />} label="Residents" detail="2020 census anchor" />
          <MetricTile value={nCells === null ? "—" : fixed(nCells, 0)} label="Population cells" detail="100 m × 100 m" />
          <MetricTile value={nFac === null ? "—" : fixed(nFac, 0)} label="Facilities" detail={`mapped · ${m.indicator_groups.length} indicator groups`} />
          <MetricTile value={`${fixed(m.walk_speed_kmh, 1)}`} label="Walking speed" detail="km/h, constant" />
          <MetricTile value={<span className="metric__v--sm">{m.thresholds_min.walk.join(" · ")}</span>} label="Walk limits" detail={`minutes · drive ${m.thresholds_min.drive.join(" · ")} min`} />
        </div>
        <div className="grid">
          <div className="span-8">
            <Panel id="what" title="What ABOT is">
              <div className="prose">
                <p>
                  A static, read-only research dashboard over a fixed data contract (
                  <code>
                    {m.contract} v{m.contract_version}
                  </code>
                  ). Travel times are <strong>modelled</strong> on the mapped OpenStreetMap network to the nearest <strong>mapped</strong> facility: geographic proximity, not service level, capacity or observed travel.
                </p>
                <p>It is an independent personal portfolio project by {PROJECT.author}, meant for city planners, researchers and anyone interested in access to services in the city.</p>
              </div>
            </Panel>
          </div>
          <div className="span-4">
            <Panel id="area" title="Study area">
              <dl className="kv">
                <dt>City</dt>
                <dd>Iloilo City, Philippines</dd>
                <dt>Location</dt>
                <dd>about 10.7° N, 122.55° E; coastal, with the Iloilo River through it</dd>
                <dt>Barangays</dt>
                <dd>{nBrgy ?? "—"}</dd>
                <dt>Residents</dt>
                <dd>
                  <Int v={m.population_total} /> (2020 census anchor)
                </dd>
              </dl>
            </Panel>
          </div>
        </div>
      </PageSection>

      <PageSection id="m-method" title="Method in five steps" lead="From boundaries to barangay indicators. Each step's inputs and outputs are hashed in the provenance record.">
        <ol className="flow" aria-label="Method">
          {STEPS.map(([g, t, d], i) => (
            <li key={t} className="flow__step">
              <span className="flow__icon" aria-hidden="true">
                <Glyph name={g} />
              </span>
              <span className="flow__n">Step {i + 1}</span>
              <span className="flow__t">{t}</span>
              <span className="flow__d">{d}</span>
            </li>
          ))}
        </ol>
      </PageSection>

      <PageSection id="m-scenarios" title="Scenarios" lead="How A1 and A3 treat three kinds of population cell. A3 is the reporting scenario; A1 is shown only for comparison.">
        <div className="cell-kinds" role="list">
          {CELL_KINDS.map((c, i) => (
            <figure key={c.key} className="cell-kind" role="listitem">
              <figcaption className="cell-kind__title">
                <span className="cell-kind__n">{i + 1}</span>
                {c.title}
              </figcaption>
              <svg className="chart cell-kind__svg" viewBox="0 0 220 160" aria-hidden="true">
                {c.svg}
              </svg>
              <dl className="cell-kind__rows">
                <div>
                  <dt>
                    <Scen k="a3" text="A3" />
                  </dt>
                  <dd>{c.a3}</dd>
                </div>
                <div>
                  <dt>
                    <Scen k="a1" text="A1" />
                  </dt>
                  <dd>{c.a1}</dd>
                </div>
              </dl>
              <p className="cell-kind__cat">
                <span className={`cat-sym cat-sym--${c.key === "connected" ? "network_connected" : c.key === "fragment" ? "locally_connected" : "unconnected"}`} aria-hidden="true">
                  {c.cat[0]}
                </span>{" "}
                {c.cat[1]} · <span className="muted">{c.note}</span>
              </p>
            </figure>
          ))}
        </div>
        <Panel id="scn" title="A1, A2 and A3" codes={["DQ-A1-OPT", "DQ-DRIVE", "DQ-LOCAL"]}>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col">Role</th>
                  <th scope="col">Definition (from the manifest)</th>
                  <th scope="col">Where it appears</th>
                </tr>
              </thead>
              <tbody>
                {SCEN_ROW.map(([code, mode, k, where]) => {
                  const sc = m.scenarios.find((x) => x.code === code && x.mode === mode);
                  return (
                    <tr key={k}>
                      <td>
                        <Scen k={k} />
                      </td>
                      <td>{sc ? <Role k={roleOf(sc.role)} /> : "—"}</td>
                      <td>{sc?.label ?? "Not in this bundle"}</td>
                      <td className="small">{where}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </PageSection>

      <PageSection
        id="m-defs"
        title="Indicator definitions"
        lead={`${examples.length} statistic types from the indicator catalogue (${m.indicator_catalog.length} entries across ${m.indicator_groups.length} groups), one example per type. Thresholds: walk ${m.thresholds_min.walk.join("/")} min, drive ${m.thresholds_min.drive.join("/")} min. Percentile: p90 only.`}
      >
        <Definitions m={m} />
      </PageSection>

      <PageSection id="m-limits" title="Limitations, documents and citation">
        <div className="grid">
          <div className="span-7">
            <Panel id="lim" title="Limitations">
              {prov
                ? guard("The limitations", () => (
                    <ol className="limits">
                      {prov.limitations.map((l) => (
                        <li key={l.code}>
                          <code className="limits__code">{l.code}</code>
                          <span>{l.text}</span>
                        </li>
                      ))}
                    </ol>
                  ))
                : <Unavailable bundle={bundle} dataset="provenance" what="The limitations list" />}
            </Panel>
          </div>
          <div className="span-5 stack">
            <Panel id="cite" title="How to cite">
              <Citation text={citation} />
              <p className="small muted" style={{ margin: "var(--space-2) 0 0" }}>
                OSM-derived data: © OpenStreetMap contributors; the dataset is available under the ODbL 1.0. Population: PSA 2020 census and WorldPop (CC BY 4.0).
              </p>
            </Panel>
            <Panel id="docs" title="Documents" sub="In the repository, beside the pipeline code.">
              {prov
                ? guard("The document list", () => (
                    <ul className="doc-list">
                      {prov.documents.map((d) => (
                        <li key={d.path}>
                          <Glyph name="book" />
                          <span className="doc-list__t">{d.title}</span>
                          <code className="doc-list__p">{d.path}</code>
                        </li>
                      ))}
                    </ul>
                  ))
                : <Unavailable bundle={bundle} dataset="provenance" what="The document list" />}
            </Panel>
          </div>
        </div>
      </PageSection>

      <PageSection id="m-sources" title="Data sources" lead={prov ? `${prov.sources?.length ?? 0} raw sources, each with its licence.` : undefined}>
        {prov ? (
          guard("The source list", () => (
            <div className="table-wrap">
              <table className="data-table data-table--compact">
                <caption className="visually-hidden">Raw data sources</caption>
                <thead>
                  <tr>
                    <th scope="col">Source file</th>
                    <th scope="col">Licence</th>
                    <th scope="col" className="n">
                      Bytes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {prov.sources.map((s) => (
                    <tr key={s.path}>
                      <td className="mono" style={{ fontSize: ".72rem", overflowWrap: "anywhere", maxWidth: "22rem" }}>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noopener noreferrer">
                            {s.path}
                          </a>
                        ) : (
                          s.path
                        )}
                      </td>
                      <td className="small">{s.licence ?? "—"}</td>
                      <td className="n">
                        <Int v={s.bytes} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        ) : (
          <Unavailable bundle={bundle} dataset="provenance" what="The source list" />
        )}
      </PageSection>
    </div>
  );
}
