/**
 * Overview (#/overview): the citywide picture. A3 walking is the headline; A1 walking appears only
 * beside it as a muted comparison; A1 driving has its own band and is never on a walking axis. The
 * distribution curve ends where the exported cumulative curve ends (below 100 %), with the gap labelled.
 */
import { InventoryTable } from "../components/InventoryTable.tsx";
import { Ref } from "../components/notes.tsx";
import { guard, Unavailable } from "../components/states/States.tsx";
import { CatSym, GroupSelect, Icon, type IconName, Int, Min, Num, Panel, PageHeader, Pct, Role, Scen, SectionBand, Seg, thresholdOptions, txt } from "../components/ui.tsx";
import type { City } from "../contract/types.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { distributionView } from "../model/distribution.ts";
import { delta, fixed } from "../model/format.ts";
import { CATEGORIES, groupLabel, groupPhrase } from "../model/labels.ts";
import { pctKey } from "../model/view.ts";
import { cityDrive, cityWalk, facilitySummary } from "../model/values.ts";
import { useView } from "../view.tsx";
import { PrintHead } from "./common.tsx";

function Hero({ city, groups, thresholds, total }: { city: City; groups: string[]; thresholds: readonly number[]; total: number }) {
  const { s, set } = useView();
  const { g, t } = s;
  const a3 = cityWalk(city, "A3", g, pctKey(t));
  const a1 = cityWalk(city, "A1", g, pctKey(t));
  const m3 = cityWalk(city, "A3", g, "mean_min");
  const m1 = cityWalk(city, "A1", g, "mean_min");
  return (
    <section className="panel hero" aria-labelledby="hero-h">
      <h2 className="visually-hidden" id="hero-h">
        Headline
      </h2>
      <div className="panel__tags" style={{ marginBottom: "var(--space-3)" }}>
        <Scen k="a3" /> <Role k="primary" />
      </div>
      <p className="hero__sentence" aria-live="polite">
        <span className="hero__value">
          <Pct v={a3} />
        </span>
        <Ref codes={["DQ-SHARE-ALL"]} /> of Iloilo City residents live within a{" "}
        <span style={{ whiteSpace: "nowrap" }}>
          <select className="hero__inline-select" id="hero-t" aria-label="Threshold, minutes" value={t} onChange={(e) => set({ t: e.target.value })}>
            {thresholds.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
          -minute
        </span>{" "}
        walk of{" "}
        <select className="hero__inline-select" id="hero-g" aria-label="Indicator group" value={g} onChange={(e) => set({ g: e.target.value })}>
          {groups.map((x) => (
            <option key={x} value={x}>
              {groupPhrase(x)}
            </option>
          ))}
        </select>
        .
      </p>
      <div className="hero__meta">
        <div className="compare-pair">
          <span className="compare-pair__a3">
            <Pct v={a3} d={2} />
          </span>
          <span className="compare-pair__a1">
            <Pct v={a1} d={2} /> {delta(a3, a1) && <span className="delta">({delta(a3, a1)} pt)</span>}
            <Ref codes={["DQ-A1-OPT"]} />
          </span>
          <span className="compare-pair__lab">A3 · share of all {fixed(total, 0)} residents</span>
          <span className="compare-pair__lab compare-pair__lab--a1">A1 comparison, optimistic</span>
        </div>
        <div className="compare-pair compare-pair--sm">
          <span className="compare-pair__a3">
            <Min v={m3} d={2} />
          </span>
          <span className="compare-pair__a1">
            <Min v={m1} d={2} />
            <Ref codes={["DQ-MEAN-CONN"]} />
          </span>
          <span className="compare-pair__lab">Mean walk · connected residents only</span>
          <span className="compare-pair__lab compare-pair__lab--a1">A1 comparison</span>
        </div>
      </div>
    </section>
  );
}

function population(city: City) {
  const P = city.population;
  const cats = CATEGORIES.map((c) => ({ ...c, pop: P.a3[c.id]?.pop ?? null, pct: P.a3[c.id]?.pct ?? null }));
  const rest = cats.slice(1);
  const restPct = rest.reduce((sum, c) => sum + (c.pct ?? 0), 0);
  const uncertain = rest.findIndex((c) => c.id === "access_uncertain");
  const before = rest.slice(0, uncertain).reduce((sum, c) => sum + (c.pct ?? 0), 0);
  const unc = rest[uncertain];
  const pin = restPct > 0 && unc ? ((before + (unc.pct ?? 0) / 2) / restPct) * 100 : 0;
  const first = rest[0];
  const last = rest.at(-1);
  return (
    <Panel id="pop" title="Population by A3 network category" tags={<Role k="descriptive" />} sub={`Every share on this page uses all ${fixed(P.total, 0)} residents as the denominator, including the categories without citywide times.`} codes={["DQ-SHARE-ALL"]}>
      <div className="stackbar" role="img" aria-label={cats.map((c) => `${c.label} ${txt(c.pct, 2, " %")}`).join(", ")}>
        {cats.map((c) => (
          <span key={c.id} className={`stackbar__seg stackbar__seg--${c.id}`} style={{ width: `${c.pct ?? 0}%` }} title={`${c.label}: ${txt(c.pct, 2, " %")}`} />
        ))}
      </div>
      {restPct > 0 && (
        <>
          <p className="callout-line" style={{ margin: "var(--space-3) 0 0.25rem" }}>
            Detail: the {fixed(restPct, 2)} % outside the main network, enlarged ×{Math.max(1, Math.round(100 / restPct / 10) * 10)}
          </p>
          <div className="stackbar stackbar--sm" style={{ height: "1.5rem" }} role="img" aria-label="Detail of the categories outside the main network">
            {rest.map((c) => (
              <span key={c.id} className={`stackbar__seg stackbar__seg--${c.id}`} style={{ width: `${((c.pct ?? 0) / restPct) * 100}%`, minWidth: c.id === "access_uncertain" ? "5px" : "3px" }} title={`${c.label}: ${txt(c.pct, 2, " %")}`} />
            ))}
          </div>
          <div style={{ position: "relative", height: "2.4rem", fontSize: "0.6875rem", color: "var(--color-ink-muted)" }}>
            {first && (
              <span style={{ position: "absolute", left: 0, top: "0.2rem" }}>
                <CatSym id={first.id} /> {txt(first.pct, 2, " %")}
              </span>
            )}
            {last && (
              <span style={{ position: "absolute", right: 0, top: "0.2rem" }}>
                <CatSym id={last.id} /> {txt(last.pct, 2, " %")}
              </span>
            )}
            {unc && (
              <>
                <span style={{ position: "absolute", left: `${pin}%`, top: 0, height: "1.2rem", borderLeft: "1.5px solid var(--cat-access-uncertain)" }} />
                <span style={{ position: "absolute", left: `${pin}%`, top: "1.15rem", transform: "translateX(-50%)", whiteSpace: "nowrap", color: "var(--color-ink)", fontWeight: 500 }}>
                  <CatSym id="access_uncertain" /> {unc.label}: {txt(unc.pct, 2, " %")} · {txt(unc.pop, 1)} residents
                </span>
              </>
            )}
          </div>
        </>
      )}
      <ul className="cat-list">
        {cats.map((c) => (
          <li key={c.id}>
            <CatSym id={c.id} />
            <span title={c.desc}>{c.label}</span>
            <span className="num">
              <Num v={c.pop} d={1} />
            </span>
            <span className="num" style={{ minWidth: "4.5rem" }}>
              <b>
                <Pct v={c.pct} d={2} />
              </b>
            </span>
          </li>
        ))}
        <li style={{ borderTop: "1px solid var(--color-border)", paddingTop: "0.375rem" }}>
          <span />
          <span>All residents (2020 census anchor)</span>
          <span className="num">
            <b>
              <Int v={P.total} />
            </b>
          </span>
          <span className="num">100.00&#8239;%</span>
        </li>
      </ul>
      <p className="small muted" style={{ margin: "var(--space-3) 0 0", paddingTop: "var(--space-2)", borderTop: "1px dashed var(--color-border-strong)" }}>
        <Scen k="a1" text="A1 · comparison" /> connected <Num v={P.a1.connected_pop} d={1} /> (<Pct v={P.a1.connected_pct} d={2} />) · not connected <Pct v={P.a1.not_connected_pct} d={2} />
        <Ref codes={["DQ-A1-OPT"]} />. A1 uses a different connection rule; its categories are not the A3 categories.
      </p>
    </Panel>
  );
}

function GroupsChart({ city, groups }: { city: City; groups: string[] }) {
  const { s, set } = useView();
  const { g, t } = s;
  const rows = groups
    .map((id) => ({ id, a3: cityWalk(city, "A3", id, pctKey(t)), a1: cityWalk(city, "A1", id, pctKey(t)), m: cityWalk(city, "A3", id, "mean_min") }))
    .sort((a, b) => (b.a3 ?? -1) - (a.a3 ?? -1));
  const withBoth = rows.filter((r) => r.a3 !== null && r.a1 !== null);
  const top = rows[0];
  const bottom = rows.filter((r) => r.a3 !== null).at(-1);
  return (
    <Panel id="groups" title={`Walking accessibility · share within ${t} min`} tags={<><Scen k="a3" /><Scen k="a1" /></>} sub="Ranked by A3. A1 is a hollow tick on the A3 bar, never a bar of its own." codes={["DQ-SHARE-ALL", "DQ-MEAN-CONN", "DQ-A1-OPT"]}>
      <table className="dotchart" aria-describedby="groups-sum">
        <caption className="visually-hidden">A3 share of all residents within {t} minutes' walk, by indicator group, with A1 comparison and mean time for connected residents</caption>
        <thead>
          <tr>
            <th scope="col">Group</th>
            <th scope="col">
              <div className="dotchart__scale">
                <span>0</span>
                <span>25</span>
                <span>50</span>
                <span>75</span>
                <span>100 %</span>
              </div>
            </th>
            <th scope="col" className="dotchart__val">
              A3 ≤ {t} min
              <Ref codes={["DQ-SHARE-ALL"]} />
            </th>
            <th scope="col" className="dotchart__a1">
              A1
              <Ref codes={["DQ-A1-OPT"]} />
            </th>
            <th scope="col" className="dotchart__mean" style={{ borderLeft: "1px solid var(--color-border)" }}>
              Mean, connected
              <br />
              residents
              <Ref codes={["DQ-MEAN-CONN"]} />
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-selected={String(r.id === g)}>
              <th scope="row" className="dotchart__name">
                <button type="button" id={`gc-${r.id}`} aria-pressed={r.id === g} onClick={() => set({ g: r.id })}>
                  {groupLabel(r.id)}
                </button>
              </th>
              <td>
                <div className="dotchart__track" aria-hidden="true">
                  {[25, 50, 75].map((p) => (
                    <span key={p} className="dotchart__grid" style={{ left: `${p}%` }} />
                  ))}
                  <span className="dotchart__axis" />
                  {r.a3 !== null && <span className="dotchart__bar" style={{ width: `${r.a3}%` }} />}
                  {r.a1 !== null && <span className="dotchart__tick" style={{ left: `${r.a1}%` }} />}
                  {r.a3 !== null && <span className="dotchart__dot" style={{ left: `${r.a3}%` }} />}
                </div>
              </td>
              <td className="dotchart__val">
                <b>
                  <Pct v={r.a3} />
                </b>
              </td>
              <td className="dotchart__a1">
                <Pct v={r.a1} />
              </td>
              <td className="dotchart__mean">
                <Min v={r.m} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="legend-inline" style={{ marginTop: "var(--space-3)" }}>
        <span className="legend-inline__item">
          <span className="lg-dot" />A3 · share of all residents (primary)
        </span>
        <span className="legend-inline__item">
          <span className="lg-tick" />A1 · comparison (optimistic)
        </span>
        <span className="legend-inline__item">Mean is a different population: connected residents only</span>
      </div>
      <p className="chart-summary" id="groups-sum">
        {top && bottom && `Highest: ${groupLabel(top.id)} ${txt(top.a3, 1, " %")}; lowest: ${groupLabel(bottom.id)} ${txt(bottom.a3, 1, " %")}. `}
        {withBoth.length > 0 && `A1 differs from A3 by at most ${fixed(Math.max(...withBoth.map((r) => Math.abs((r.a1 as number) - (r.a3 as number)))), 1)} points. `}
        Select a group to update the headline and the distribution.
      </p>
    </Panel>
  );
}

function distribution(b: LoadedBundle, g: string, thresholds: readonly number[]) {
  const city = b.city;
  const d = city.walk_distribution.find((x) => x.group === g);
  if (!d) throw new Error(`city.walk_distribution has no group ${g}`);
  const v = distributionView(d, b.manifest.walk_distribution.closed_max_min);
  const max = v.closedMax;
  const W = 560, x0 = 44, xMax = 440, xF = 512, yT = 14, yB = 196, hT = 214, hB = 280; // prettier-ignore
  const X = (m: number) => x0 + ((xMax - x0) * m) / max;
  const Y = (p: number) => yB - ((yB - yT) * p) / 100;
  const pts: [number, number][] = [[0, 0], ...v.cumulative.map((c): [number, number] => [c.minutes, c.pct])];
  const line = `M${pts.map(([m, p]) => `${X(m).toFixed(1)},${Y(p).toFixed(1)}`).join("L")}`;
  const area = `${line}L${X(max)},${yB}L${X(0)},${yB}Z`;
  const final = v.final.pct;
  const last = v.cumulative.at(-1)?.pct ?? 0;
  const closed = v.bars.filter((x) => !x.open);
  const open = v.bars.find((x) => x.open);
  const maxBin = Math.max(...v.bars.map((x) => x.pop), 1);
  const H = (p: number) => ((hB - hT) * p) / maxBin;
  const at = (m: number) => cityWalk(city, "A3", g, pctKey(m));
  const cumAt = (m: number) => v.cumulative.find((c) => c.minutes === m)?.pct ?? null;
  const ticks = [0, 20, 40, 50, max].filter((m) => !thresholds.includes(m));
  const sum = `${groupLabel(g)}: ${thresholds.map((t) => `${txt(at(t), 1, " %")} of all residents within ${t} min`).join(", ")}. The curve ends at ${txt(final, 2, " %")} (all citywide times, including ${txt(v.popOpenBin, 0)} residents over ${max} min); ${fixed(100 - final, 2)} % have no citywide time.`;
  return (
    <Panel id="dist" title={`Walking-time distribution · ${groupLabel(g)}`} tags={<Scen k="a3" />} sub={`Cumulative share of all residents over one-minute bins. Only ${thresholds.join("/")} min are headline values; other points are a visual aid.`} codes={["DQ-DIST", "DQ-SHARE-ALL"]}>
      <svg className="chart" viewBox={`0 0 ${W} 300`} role="img" aria-labelledby="dist-title dist-sum">
        <title id="dist-title">{`Cumulative share of all residents by citywide walking time to ${groupLabel(g)}`}</title>
        {[0, 25, 50, 75, 100].map((p) => (
          <g key={p}>
            <line x1={x0} x2={xF + 10} y1={Y(p)} y2={Y(p)} stroke="var(--color-border)" strokeDasharray={p === 100 ? "4 3" : undefined} />
            <text x={x0 - 6} y={Y(p) + 4} textAnchor="end">
              {p}%
            </text>
          </g>
        ))}
        <path d={area} fill="var(--color-brand)" opacity="0.07" />
        <path d={line} fill="none" stroke="var(--color-brand)" strokeWidth="2.25" />
        <line x1={X(max)} y1={Y(last)} x2={xF} y2={Y(final)} stroke="var(--color-brand)" strokeWidth="1.5" strokeDasharray="3 3" />
        <circle cx={xF} cy={Y(final)} r="5" fill="#fff" stroke="var(--color-brand)" strokeWidth="2.25" />
        <text x={xF - 8} y={Y(final) + 18} textAnchor="end" className="chart__strong">
          {fixed(final, 2)} %
        </text>
        <text x={xF - 8} y={Y(final) + 31} textAnchor="end">
          {v.final.label}
        </text>
        <line x1={xF + 12} x2={xF + 12} y1={Y(100)} y2={Y(final)} stroke="var(--color-error)" strokeWidth="2" />
        <line x1={xF + 8} x2={xF + 16} y1={Y(100)} y2={Y(100)} stroke="var(--color-error)" strokeWidth="1.5" />
        <line x1={xF + 8} x2={xF + 16} y1={Y(final)} y2={Y(final)} stroke="var(--color-error)" strokeWidth="1.5" />
        <text x={xF + 4} y={Y(100) - 4} textAnchor="end" style={{ fill: "var(--color-error)" }}>
          no citywide time {fixed(100 - final, 2)} %
        </text>
        {thresholds.map((t) => {
          const p = at(t);
          return (
            <g key={t}>
              <line x1={X(t)} x2={X(t)} y1={yT} y2={hB} stroke="var(--color-ink)" strokeDasharray="2 3" opacity="0.55" />
              {p !== null && <circle cx={X(t)} cy={Y(p)} r="4" fill="var(--color-brand)" stroke="#fff" strokeWidth="1.5" />}
              {p !== null && (
                <text x={X(t) + 5} y={Y(p) + 14} className="chart__strong">
                  {fixed(p, 1)} %
                </text>
              )}
              <text x={X(t)} y={yB + 14} textAnchor="middle">
                {t}
              </text>
            </g>
          );
        })}
        {ticks.map((m) => (
          <text key={m} x={X(m)} y={yB + 14} textAnchor="middle">
            {m}
          </text>
        ))}
        <text x={(x0 + xMax) / 2} y={yB + 28} textAnchor="middle">
          walking time, minutes (one-minute bins)
        </text>
        <text x={xF} y={yB + 14} textAnchor="middle">
          open
        </text>
        <line x1={x0} x2={xF + 10} y1={hB} y2={hB} stroke="var(--color-border-strong)" />
        {closed.map((bar) => (
          <rect key={bar.lowerMin} x={(X(bar.lowerMin) + 0.4).toFixed(1)} y={(hB - H(bar.pop)).toFixed(1)} width={(X(1) - X(0) - 0.8).toFixed(1)} height={H(bar.pop).toFixed(1)} fill="var(--color-brand)" opacity="0.55" />
        ))}
        {open && (
          <>
            <rect x={xF - 10} y={hB - H(open.pop)} width="20" height={Math.max(H(open.pop), 0)} fill="var(--ramp-time-6)" />
            <text x={xF} y={hB + 13} textAnchor="middle">
              &gt; {max} min
            </text>
            <text x={xF + 14} y={hB - H(open.pop) - 4} textAnchor="start" className="chart__strong">
              {fixed(open.pop, 0)}
            </text>
          </>
        )}
        <text x={x0 - 6} y={hT + 8} textAnchor="end">
          res.
        </text>
      </svg>
      <p className="chart-summary" id="dist-sum">
        {sum}
      </p>
      <details className="data-fallback">
        <summary>Show as table</summary>
        <table className="data-table data-table--compact" style={{ marginTop: "0.5rem" }}>
          <thead>
            <tr>
              <th>Within</th>
              <th className="n">Cumulative % of all residents</th>
            </tr>
          </thead>
          <tbody>
            {[...new Set([...thresholds, 45, max])].sort((a, b) => a - b).map((m) => (
              <tr key={m}>
                <td>
                  ≤ {m} min{thresholds.includes(m) ? "" : " (visual aid)"}
                </td>
                <td className="n">
                  <Pct v={thresholds.includes(m) ? at(m) : cumAt(m)} d={2} />
                </td>
              </tr>
            ))}
            <tr>
              <td>All citywide times (incl. &gt; {max} min)</td>
              <td className="n">
                <Pct v={final} d={2} />
              </td>
            </tr>
            <tr>
              <td>No citywide time</td>
              <td className="n">
                <Pct v={100 - final} d={2} />
              </td>
            </tr>
          </tbody>
        </table>
      </details>
    </Panel>
  );
}

function Driving({ b, groups }: { b: LoadedBundle; groups: string[] }) {
  const { s, p, set } = useView();
  const city = b.city;
  const drive = b.manifest.thresholds_min.drive;
  const factors = b.manifest.drive_network_time_factors.filter((f) => f !== 1);
  const sens = factors.map(String).includes(p["sens"] ?? "") ? Number(p["sens"]) : null;
  const dt = s.dt;
  return (
    <>
      <SectionBand title="Driving" kind="drive" tags={<><Scen k="drive" /><Role k="primary" /></>}>
        A separate mode, never on the same axis as walking. Uncongested car time from A1-connected cells, including the walk to and from the car.
      </SectionBand>
      <div className="grid">
        <div className="span-12">
          {guard("The driving table", () => (
            <Panel id="drive" cls="panel--drive" title="Share of all residents within N minutes' drive, and mean drive time" tags={<Scen k="drive" />} sub="The sensitivity columns multiply the network leg only. They illustrate sensitivity and are not results." codes={["DQ-DRIVE", "DQ-SHARE-ALL", "DQ-MEAN-CONN"]}>
              <div className="ctl-row" style={{ gap: "var(--space-4)" }}>
                <Seg id="ov-dt" label="Highlight threshold" cls="seg--drive" options={thresholdOptions(drive)} value={String(dt)} onChange={(v) => set({ dt: v })} />
                {factors.length > 0 && (
                  <Seg id="sens" label="Illustrative sensitivity" options={[["off", "Off"], ...factors.map((f): [string, string] => [String(f), `×${fixed(f, 1)}`])]} value={sens === null ? "off" : String(sens)} onChange={(v) => set({ sens: v === "off" ? null : v })} />
                )}
                {sens !== null && <Role k="evidence" />}
              </div>
              <div className="table-wrap" style={{ marginTop: "var(--space-3)" }}>
                <table className="data-table">
                  <caption className="visually-hidden">A1 driving indicators by group</caption>
                  <thead>
                    <tr className="data-table__group">
                      <th />
                      <th colSpan={drive.length + 1} style={{ color: "var(--scenario-drive)" }}>
                        A1 · drive · network-time factor ×1.0
                      </th>
                      {sens !== null && (
                        <th colSpan={drive.length + 1} className="col-sep" style={{ background: "var(--evidence-bg)", color: "var(--evidence-ink)" }}>
                          ×{fixed(sens, 1)} · illustrative · evidence only
                        </th>
                      )}
                    </tr>
                    <tr>
                      <th scope="col">Group</th>
                      {drive.map((t, i) => (
                        <th key={t} scope="col" className="n" style={t === dt ? { color: "var(--color-ink)", fontWeight: 650 } : undefined}>
                          ≤ {t} min{i === 0 && <Ref codes={["DQ-SHARE-ALL"]} />}
                        </th>
                      ))}
                      <th scope="col" className="n">
                        Mean (min)
                        <Ref codes={["DQ-MEAN-CONN"]} />
                      </th>
                      {sens !== null && (
                        <>
                          {drive.map((t, i) => (
                            <th key={t} scope="col" className={`n${i === 0 ? " col-sep" : ""}`} style={{ background: "var(--evidence-bg)" }}>
                              ≤ {t}
                            </th>
                          ))}
                          <th scope="col" className="n" style={{ background: "var(--evidence-bg)" }}>
                            Mean
                          </th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {groups.map((g) => (
                      <tr key={g}>
                        <th scope="row" style={{ fontWeight: 500 }}>
                          {groupLabel(g)}
                        </th>
                        {drive.map((t) => {
                          const v = cityDrive(city, g, pctKey(t));
                          return (
                            <td key={t} className="n" style={t === dt ? { fontWeight: 650 } : undefined}>
                              <Pct v={v} />
                              {t === dt && v !== null && (
                                <span className="inline-bar inline-bar--drive" aria-hidden="true">
                                  <span className="inline-bar__fill" style={{ width: `${v}%` }} />
                                </span>
                              )}
                            </td>
                          );
                        })}
                        <td className="n">
                          <Num v={cityDrive(city, g, "mean_min")} d={2} />
                        </td>
                        {sens !== null && (
                          <>
                            {drive.map((t, i) => (
                              <td key={t} className={`n${i === 0 ? " col-sep" : ""}`} style={{ background: "var(--evidence-bg)", color: "var(--evidence-ink)" }}>
                                <Pct v={cityDrive(city, g, pctKey(t), sens)} />
                              </td>
                            ))}
                            <td className="n" style={{ background: "var(--evidence-bg)", color: "var(--evidence-ink)" }}>
                              <Num v={cityDrive(city, g, "mean_min", sens)} d={2} />
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          ))}
        </div>
      </div>
    </>
  );
}

function Signpost({ href, title, text, icon }: { href: string; title: string; text: string; icon: IconName }) {
  return (
    <a className="signpost" href={href}>
      <span className="signpost__title">
        <Icon name={icon} />
        {title}
      </span>
      <span className="signpost__text">{text}</span>
    </a>
  );
}

export function OverviewPage({ bundle }: { bundle: LoadedBundle }) {
  const { s, set, href } = useView();
  const m = bundle.manifest;
  const city = bundle.city;
  const groups = m.indicator_groups.map((g) => g.id);
  const total = city.population.total;
  const nBrgy = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.length : null;
  const nElig = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.filter((x) => x.data_quality.ranking_eligible).length : null;
  const fac = bundle.facilities.status === "ok" ? facilitySummary(bundle.facilities.data) : null;
  return (
    <div className="page">
      <PrintHead what="Citywide overview" manifest={m} />
      <PageHeader
        eyebrow={`Iloilo City · ${nBrgy === null ? "" : `${nBrgy} barangays · `}${fixed(total, 0)} residents (2020 census)`}
        tagline="Bringing essential services within reach."
        title="Citywide overview"
        lead="How long residents take to walk or drive to the nearest mapped essential facility, modelled on the OpenStreetMap network from 100 m population cells."
        controls={
          <>
            <GroupSelect id="ov-g" groups={groups} value={s.g} onChange={(g) => set({ g })} />
            <Seg id="ov-t" label="Walk threshold" options={thresholdOptions(m.thresholds_min.walk)} value={String(s.t)} onChange={(t) => set({ t })} />
            <button type="button" className="btn" onClick={() => window.print()}>
              <Icon name="print" />
              Print A4
            </button>
          </>
        }
      />
      <div className="grid">
        <div className="span-7">{guard("The headline", () => <Hero city={city} groups={groups} thresholds={m.thresholds_min.walk} total={total} />)}</div>
        <div className="span-5">{guard("Population by category", () => population(city))}</div>
      </div>
      <SectionBand title="Walking" tags={<><Scen k="a3" /><Role k="primary" /></>}>
        A3 is the primary result. A1 appears only as a comparison beside it.
      </SectionBand>
      <div className="grid">
        <div className="span-7">{guard("The group chart", () => <GroupsChart city={city} groups={groups} />)}</div>
        <div className="span-5">{guard("The walking-time distribution", () => distribution(bundle, s.g, m.thresholds_min.walk))}</div>
      </div>
      <Driving b={bundle} groups={groups} />
      <SectionBand title="Facilities" tags={<Role k="descriptive" />}>
        Counts of mapped OpenStreetMap features. Completeness is unverified for every group.
      </SectionBand>
      <div className="grid">
        <div className="span-12">
          {guard("The facility inventory", () => (
            <Panel id="inv" title="Facility inventory by indicator group" tags={<Role k="descriptive" />} sub={fac ? `${fixed(fac.total, 0)} mapped features in total, ${fixed(fac.outside, 0)} of them in the 3 km buffer outside the city. Facilities outside the city are destinations only if connected.` : "Facilities outside the city are destinations only if connected."} codes={["DQ-FAC-OSM", "DQ-DUP"]}>
              <InventoryTable city={city} />
            </Panel>
          ))}
          {bundle.facilities.status === "failed" && <Unavailable bundle={bundle} dataset="facilities" what="The facility totals" />}
        </div>
      </div>
      <div className="signposts" style={{ marginTop: "var(--space-6)" }}>
        <Signpost href={href("map")} title="Accessibility Map" text="Barangay choropleth, 100 m cells and facilities, with a table alternative." icon="map" />
        <Signpost href={href("barangays")} title="Barangay Analysis" text={`Sort and filter ${nBrgy ?? "the"} barangays; ranks for the ${nElig ?? ""} ranking-eligible ones only.`} icon="table" />
        <Signpost href={href("quality")} title="Data Quality" text={`Audit, known issues, integrity and the ${m.statements.length} statements.`} icon="shield" />
      </div>
    </div>
  );
}
