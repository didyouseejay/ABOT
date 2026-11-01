/**
 * About / Methodology (#/about): what ABOT is, the study area, the method in five steps, the scenarios
 * (definitions from manifest.scenarios), indicator definitions (one example per statistic type from the
 * catalogue), limitations, documents, the citation and the data sources.
 */
import { guard, Unavailable } from "../components/states/States.tsx";
import { Int, PageHeader, Panel, Role, roleOf, Scen, type ScenKey, SectionBand } from "../components/ui.tsx";
import type { CatalogEntry } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { fixed, formatUtc } from "../model/format.ts";
import { PROJECT } from "../components/layout/Brand.tsx";

const STEPS: [string, string][] = [
  ["Boundaries", "OCHA COD-AB city and barangay polygons, in UTM 51N."],
  ["Census-anchored population", "WorldPop 100 m cells, weighted to PSA 2020 barangay totals."],
  ["OSM networks", "Walk and drive networks, barriers and facilities for the city plus a 3 km buffer."],
  ["Nearest-facility routing", "One multi-source Dijkstra per indicator group on the reversed graph; walk at the configured speed, car uncongested."],
  ["Barangay aggregation", "Population-weighted shares within N min (all residents), mean and p90 (connected residents)."],
];

function ScenarioSvg() {
  return (
    <svg className="chart" viewBox="0 0 720 230" role="img" aria-labelledby="scn-t scn-d">
      <title id="scn-t">Schematic: three kinds of population cell</title>
      <desc id="scn-d">
        Left: a cell connected to the main walk network gets citywide times in A1 and A3. Middle: a cell attached to an isolated fragment gets citywide times in A1 through a straight connector, but only internal times in A3. Right: a cell with no edge within 250 metres is unconnected in both.
      </desc>
      <g transform="translate(10,20)">
        <text x="0" y="0" className="chart__strong">
          1 · Connected to the main network
        </text>
        <path d="M10 120 H210 M60 120 V40 M150 120 V200 M60 70 H200" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <rect x="85" y="85" width="26" height="26" fill="var(--cat-network-connected)" opacity="0.85" />
        <line x1="98" y1="98" x2="98" y2="120" stroke="var(--color-ink)" strokeDasharray="2 2" />
        <text x="10" y="222">
          A1 and A3: citywide time ● network-connected
        </text>
      </g>
      <g transform="translate(250,20)">
        <text x="0" y="0" className="chart__strong">
          2 · Isolated fragment
        </text>
        <path d="M0 150 H70 M30 150 V200" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M120 60 H200 M160 60 V110" stroke="var(--cat-locally-connected)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <line x1="70" y1="150" x2="120" y2="60" stroke="var(--color-error)" strokeWidth="1.5" strokeDasharray="3 4" />
        <text x="40" y="100" style={{ fill: "var(--color-error)" }}>
          no link
        </text>
        <rect x="175" y="80" width="26" height="26" fill="var(--cat-locally-connected)" opacity="0.85" />
        <line x1="188" y1="106" x2="66" y2="150" stroke="var(--scenario-a1)" strokeDasharray="1 3" strokeWidth="1.5" />
        <text x="105" y="140" style={{ fill: "var(--scenario-a1)" }}>
          A1 straight connector
        </text>
        <text x="0" y="222">
          A1: citywide time · A3: internal only ◆ locally connected
        </text>
      </g>
      <g transform="translate(500,20)">
        <text x="0" y="0" className="chart__strong">
          3 · Unconnected
        </text>
        <path d="M0 190 H120" stroke="var(--color-brand)" strokeWidth="4" fill="none" strokeLinecap="round" />
        <circle cx="140" cy="80" r="62" fill="none" stroke="var(--color-border-strong)" strokeDasharray="4 4" />
        <text x="150" y="160">
          250 m
        </text>
        <rect x="127" y="67" width="26" height="26" fill="var(--cat-unconnected)" opacity="0.9" />
        <text x="133" y="86" style={{ fill: "#fff", fontWeight: 700 }}>
          ✕
        </text>
        <text x="0" y="222">
          No time in either; still in every denominator
        </text>
      </g>
    </svg>
  );
}

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

export function AboutPage({ bundle }: { bundle: LoadedBundle }) {
  const m = bundle.manifest;
  const prov = bundle.provenance.status === "ok" ? bundle.provenance.data : null;
  const nBrgy = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.length : null;
  const nCells = bundle.cells.status === "ok" ? bundle.cells.data.length : null;
  const nFac = bundle.facilities.status === "ok" ? bundle.facilities.data.features.length : null;
  const examples = catalogExamples(m.indicator_catalog);
  const commit = m.code.git_commit ? m.code.git_commit.slice(0, 7) : "unknown";
  return (
    <div className="page">
      <PageHeader eyebrow="Reference" title="About and methodology" lead={`ABOT (“reach” in Hiligaynon and Filipino) estimates how long residents of Iloilo City take to reach essential public facilities on foot and by car, and reports the results for each of the city's ${nBrgy ?? ""} barangays.`} />
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
              <p>It accompanies a thesis at {PROJECT.institution} and is meant for city planners, the thesis committee and researchers reading the paper.</p>
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
              <dt>Population cells</dt>
              <dd>{nCells === null ? "—" : `${fixed(nCells, 0)} × 100 m`}</dd>
              <dt>Facilities</dt>
              <dd>
                {nFac === null ? "—" : `${fixed(nFac, 0)} mapped`}, {m.indicator_groups.length} indicator groups
              </dd>
              <dt>Walking speed</dt>
              <dd>{fixed(m.walk_speed_kmh, 1)} km/h</dd>
            </dl>
          </Panel>
        </div>
      </div>
      <SectionBand title="Method in five steps" />
      <ol className="steps" aria-label="Method">
        {STEPS.map(([t, d], i) => (
          <li key={t}>
            <span className="steps__n">0{i + 1}</span>
            <span className="steps__t">{t}</span>
            <span className="steps__d">{d}</span>
          </li>
        ))}
      </ol>
      <SectionBand title="Scenarios" />
      <div className="grid">
        <div className="span-12">
          <Panel id="scn" title="A1, A2 and A3" codes={["DQ-A1-OPT", "DQ-DRIVE", "DQ-LOCAL"]}>
            <ScenarioSvg />
            <div className="table-wrap" style={{ marginTop: "var(--space-4)" }}>
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
        </div>
      </div>
      <SectionBand title="Indicator definitions">
        {`${examples.length} statistic types from the indicator catalogue (${m.indicator_catalog.length} entries across ${m.indicator_groups.length} groups). Thresholds: walk ${m.thresholds_min.walk.join("/")} min, drive ${m.thresholds_min.drive.join("/")} min. Percentile: p90 only.`}
      </SectionBand>
      <div className="table-wrap" style={{ marginBottom: "var(--space-4)" }}>
        <table className="data-table data-table--compact">
          <caption className="visually-hidden">Indicator definitions</caption>
          <thead>
            <tr>
              <th scope="col">Example id</th>
              <th scope="col">Scenario · mode</th>
              <th scope="col">Unit</th>
              <th scope="col">Numerator</th>
              <th scope="col">Denominator</th>
              <th scope="col">Population described</th>
              <th scope="col">Role</th>
              <th scope="col">Statements</th>
            </tr>
          </thead>
          <tbody>
            {examples.map((c) => (
              <tr key={c.id}>
                <td className="mono" style={{ fontSize: ".68rem" }}>
                  {c.id}
                </td>
                <td>
                  {c.scenario} · {c.mode}
                </td>
                <td>{c.unit}</td>
                <td className="small" style={{ minWidth: "14rem" }}>
                  {c.numerator}
                </td>
                <td className="small">{c.denominator ?? "—"}</td>
                <td className="small" style={{ minWidth: "10rem" }}>
                  {c.population_described ?? "—"}
                </td>
                <td>
                  <Role k={roleOf(c.role)} />
                </td>
                <td>
                  {c.statements.map((s) => (
                    <code key={s} className="small" style={{ display: "block" }}>
                      {s}
                    </code>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid">
        <div className="span-7">
          <Panel id="lim" title="Limitations">
            {prov
              ? guard("The limitations", () => (
                  <ol className="statement-list" style={{ listStyle: "none" }}>
                    {prov.limitations.map((l) => (
                      <li key={l.code} style={{ gridTemplateColumns: "3rem minmax(0,1fr)" }}>
                        <code>{l.code}</code>
                        <span>{l.text}</span>
                      </li>
                    ))}
                  </ol>
                ))
              : <Unavailable bundle={bundle} dataset="provenance" what="The limitations list" />}
          </Panel>
        </div>
        <div className="span-5">
          <Panel id="docs" title="Documents" sub="In the repository, beside the pipeline code.">
            {prov
              ? guard("The document list", () => (
                  <ul className="rel-list">
                    {prov.documents.map((d) => (
                      <li key={d.path} style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
                        <span>{d.title}</span>
                        <code className="small">{d.path}</code>
                      </li>
                    ))}
                  </ul>
                ))
              : <Unavailable bundle={bundle} dataset="provenance" what="The document list" />}
          </Panel>
          <div style={{ height: "var(--space-4)" }} />
          <Panel id="cite" title="How to cite">
            <pre className="citation">{`[Author surname, initials] (${m.generated_utc.slice(0, 4)}). ABOT: ${PROJECT.fullName}.
Accessibility to essential public facilities in Iloilo City, Philippines
[Dashboard, data contract ${m.contract} v${m.contract_version}, generated
${formatUtc(m.generated_utc)}, code ${commit}]. ${PROJECT.institution}.`}</pre>
            <p className="small muted" style={{ margin: "var(--space-2) 0 0" }}>
              Bracketed fields are filled from the thesis record. OSM-derived data: © OpenStreetMap contributors, ODbL 1.0.
            </p>
          </Panel>
        </div>
      </div>
      <SectionBand title="Data sources">{prov ? `${prov.sources?.length ?? 0} raw sources, each with its licence, retrieval time and SHA-256.` : undefined}</SectionBand>
      {prov ? (
        guard("The source list", () => (
          <div className="table-wrap">
            <table className="data-table data-table--compact">
              <caption className="visually-hidden">Raw data sources</caption>
              <thead>
                <tr>
                  <th scope="col">Source file</th>
                  <th scope="col">Licence</th>
                  <th scope="col">Retrieved (UTC)</th>
                  <th scope="col" className="n">
                    Bytes
                  </th>
                  <th scope="col">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {prov.sources.map((s) => (
                  <tr key={s.path}>
                    <td className="mono" style={{ fontSize: ".7rem", overflowWrap: "anywhere", maxWidth: "22rem" }}>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noopener noreferrer">
                          {s.path}
                        </a>
                      ) : (
                        s.path
                      )}
                    </td>
                    <td className="small">{s.licence ?? "—"}</td>
                    <td className="small num">{s.retrieved_utc ? formatUtc(s.retrieved_utc) : "—"}</td>
                    <td className="n">
                      <Int v={s.bytes} />
                    </td>
                    <td className="mono" style={{ fontSize: ".68rem" }} title={s.sha256 ?? ""}>
                      {s.sha256 ? `${s.sha256.slice(0, 12)}…` : "—"}
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
    </div>
  );
}
