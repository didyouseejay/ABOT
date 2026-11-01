/**
 * Pieces shared by several pages: the print header and the barangay panel (the map's side drawer and
 * the Barangay Analysis profile). A barangay value is always shown with its reliability, A1 walking
 * only beside A3, and driving in its own block.
 */
import { Chip, Ref } from "../components/notes.tsx";
import { Badge, CatSym, Icon, Int, Min, Num, Pct, Rel, Role, Scen } from "../components/ui.tsx";
import type { Manifest } from "../contract/types.ts";
import { delta, fixed, formatUtc } from "../model/format.ts";
import { CATEGORIES, DESCRIPTIVE_ONLY, FAC_CATS, facCatLabel, groupLabel, RELIABILITY_DIMENSIONS } from "../model/labels.ts";
import { pctKey } from "../model/view.ts";
import { type Barangay, bval, relOf } from "../model/values.ts";
import { useNotes } from "../components/notes.tsx";
import { useView } from "../view.tsx";

export function PrintHead({ what, manifest }: { what: string; manifest: Manifest }) {
  const c = manifest.code;
  return (
    <div className="topbar-print">
      ABOT · {what} · {manifest.contract} v{manifest.contract_version} · generated {formatUtc(manifest.generated_utc)} · commit {c.git_commit ? c.git_commit.slice(0, 7) : "unknown"}
      {c.git_working_tree_clean === false ? " (uncommitted changes)" : ""}
    </div>
  );
}

export const NOT_RANKED = "Not ranked: low population/network reliability";

export function BarangayPanel({ b, groups, walkT, driveT, compact, onClose }: { b: Barangay; groups: string[]; walkT: readonly number[]; driveT: readonly number[]; compact: boolean; onClose: () => void }) {
  const { s, href } = useView();
  const { statement } = useNotes();
  const { g, t, dt } = s;
  const drive = s.m === "drive";
  const r = b.rec;
  const dq = r.data_quality;
  const eligible = dq.ranking_eligible;
  const w3 = (x: string, st: string) => bval(r, "A3", x, st);
  const w1 = (x: string, st: string) => bval(r, "A1", x, st);
  const dv = (x: string, st: string) => bval(r, "drive", x, st);
  const pop = (id: (typeof CATEGORIES)[number]["id"]) => r.a3_population[id] ?? { pop: null, pct: null };
  const localKeys = ["pop_local_internal", "pop_local_internal_le15", "pop_uncertain_internal", "pop_uncertain_internal_le15"].map((k) => w3(g, k));
  const hasLocal = (localKeys[0] ?? 0) + (localKeys[2] ?? 0) > 0;
  const codes = ["DQ-POP-ALLOC", "DQ-SHARE-ALL", "DQ-MEAN-CONN", drive ? "DQ-DRIVE" : "DQ-A1-OPT", "DQ-FAC-OSM", ...(dq.resolved_separately ? ["DQ-RESOLVED"] : [])];

  return (
    <>
      <div className="drawer__grabber" aria-hidden="true" />
      <div className="drawer__head">
        <div>
          <p className="page__eyebrow" style={{ margin: 0 }}>
            {compact ? "Barangay" : "Barangay profile"} · <span className="mono">{b.code}</span>
          </p>
          <h2 className="drawer__title" id="drawer-title">
            {b.name}
          </h2>
          <p className="small muted" style={{ margin: 0 }}>
            Population{" "}
            <b className="num" style={{ color: "var(--color-ink)" }}>
              <Int v={r.pop_total} />
            </b>
            {b.props && (
              <>
                {" "}
                · <Num v={b.props.area_km2} d={2} /> km² · {b.props.adm3_name}
              </>
            )}
          </p>
        </div>
        <button type="button" className="drawer__close" aria-label={`Close ${compact ? "panel" : "profile"}`} onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      <div className="drawer__body">
        {dq.resolved_separately && (
          <div className="resolved-note">
            <Badge tone="info">Resolved separately</Badge> {statement("DQ-RESOLVED")?.text ?? ""}
            <Ref codes={["DQ-RESOLVED"]} />
          </div>
        )}
        <div className="drawer__section">
          <h3>Reliability</h3>
          <ul className="rel-list">
            {RELIABILITY_DIMENSIONS.map(([k, l]) => {
              const x = relOf(r, k);
              return (
                <li key={k}>
                  <span>{l}</span>
                  <span>
                    <Rel level={x.level} />
                  </span>
                  {x.reasons && <span className="rel-list__reason">{x.reasons}</span>}
                </li>
              );
            })}
            <li>
              <span>Ranking</span>
              <span>{eligible ? <Badge tone="ok">Ranking-eligible</Badge> : <Badge tone="unknown">Not ranked</Badge>}</span>
              {!eligible && <span className="rel-list__reason">{NOT_RANKED}</span>}
            </li>
          </ul>
        </div>
        <div className="drawer__section">
          <h3>Selected indicator</h3>
          {drive ? (
            <div className="indicator-card indicator-card--drive">
              <span className="indicator-card__label">
                <Scen k="drive" /> {groupLabel(g)}
              </span>
              <div className="compare-pair">
                <span className="compare-pair__a3">
                  <Pct v={dv(g, pctKey(dt))} />
                  <Ref codes={["DQ-SHARE-ALL", "DQ-DRIVE"]} />
                </span>
                <span className="compare-pair__a1" style={{ border: 0 }}>
                  <Min v={dv(g, "mean_min")} /> mean
                  <Ref codes={["DQ-MEAN-CONN"]} />
                </span>
                <span className="compare-pair__lab">% of all residents ≤ {dt} min drive</span>
                <span className="compare-pair__lab compare-pair__lab--a1">A1-connected residents</span>
              </div>
            </div>
          ) : (
            <div className="indicator-card">
              <span className="indicator-card__label">
                <Scen k="a3" /> {groupLabel(g)}
              </span>
              <div className="compare-pair">
                <span className="compare-pair__a3">
                  <Pct v={w3(g, pctKey(t))} d={2} />
                  <Ref codes={["DQ-SHARE-ALL"]} />
                </span>
                <span className="compare-pair__a1">
                  <Pct v={w1(g, pctKey(t))} d={2} /> {delta(w3(g, pctKey(t)), w1(g, pctKey(t))) && <span className="delta">({delta(w3(g, pctKey(t)), w1(g, pctKey(t)))})</span>}
                  <Ref codes={["DQ-A1-OPT"]} />
                </span>
                <span className="compare-pair__lab">A3 · all residents ≤ {t} min</span>
                <span className="compare-pair__lab compare-pair__lab--a1">A1 comparison</span>
              </div>
              <div className="compare-pair compare-pair--sm">
                <span className="compare-pair__a3">
                  <Min v={w3(g, "mean_min")} d={2} /> <span className="small muted">mean</span> · <Min v={w3(g, "p90_min")} d={2} /> <span className="small muted">p90</span>
                  <Ref codes={["DQ-MEAN-CONN"]} />
                </span>
                <span className="compare-pair__a1">
                  <Min v={w1(g, "mean_min")} d={2} />
                </span>
                <span className="compare-pair__lab">connected residents only</span>
                <span className="compare-pair__lab compare-pair__lab--a1">A1 mean</span>
              </div>
            </div>
          )}
        </div>
        <div className="drawer__section">
          <h3>Population by A3 category</h3>
          <div className="stackbar stackbar--sm" role="img" aria-label={CATEGORIES.map((c) => `${c.label} ${fixed(pop(c.id).pct ?? 0, 2)} %`).join(", ")}>
            {CATEGORIES.map((c) => (
              <span key={c.id} className={`stackbar__seg stackbar__seg--${c.id}`} style={{ width: `${pop(c.id).pct ?? 0}%`, ...(pop(c.id).pct ? {} : { minWidth: 0 }) }} />
            ))}
          </div>
          <ul className="cat-list" style={{ fontSize: "var(--font-size-xs)" }}>
            {CATEGORIES.map((c) => (
              <li key={c.id}>
                <CatSym id={c.id} />
                <span>{c.label}</span>
                <span className="num">
                  <Num v={pop(c.id).pop} d={1} />
                </span>
                <span className="num">
                  <Pct v={pop(c.id).pct} d={2} />
                </span>
              </li>
            ))}
          </ul>
          <p className="small muted" style={{ margin: ".5rem 0 0" }}>
            <Scen k="a1" text="A1 · comparison" /> not connected <Num v={r.a1_population.pop_not_connected} d={1} /> (<Pct v={r.a1_population.pct_not_connected} d={1} />)
            <Ref codes={["DQ-A1-OPT"]} />
          </p>
        </div>
        <div className="drawer__section">
          <h3>{compact ? "All groups at a glance" : `Walking, all ${groups.length} groups`}</h3>
          {compact ? (
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th scope="col">Group</th>
                  {drive ? (
                    <>
                      <th className="n" scope="col">
                        ≤ {dt} min
                      </th>
                      <th className="n" scope="col">
                        Mean
                      </th>
                    </>
                  ) : (
                    <>
                      <th className="n" scope="col">
                        A3 ≤ {t}
                      </th>
                      <th className="n col-a1" scope="col">
                        A1
                      </th>
                      <th className="n" scope="col">
                        A3 mean
                      </th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {groups.map((x) => (
                  <tr key={x} data-selected={x === g ? "true" : undefined}>
                    <th scope="row" style={{ fontWeight: x === g ? 650 : 400 }}>
                      {groupLabel(x)}
                    </th>
                    {drive ? (
                      <>
                        <td className="n">
                          <Pct v={dv(x, pctKey(dt))} />
                        </td>
                        <td className="n">
                          <Num v={dv(x, "mean_min")} d={1} />
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="n">
                          <Pct v={w3(x, pctKey(t))} />
                        </td>
                        <td className="n col-a1">
                          <Pct v={w1(x, pctKey(t))} />
                        </td>
                        <td className="n">
                          <Num v={w3(x, "mean_min")} d={1} />
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="table-wrap">
              <table className="data-table data-table--compact">
                <thead>
                  <tr className="data-table__group">
                    <th />
                    <th colSpan={walkT.length + 2}>
                      <Scen k="a3" />
                    </th>
                    <th colSpan={walkT.length + 1} className="col-sep col-a1">
                      <Scen k="a1" />
                    </th>
                  </tr>
                  <tr>
                    <th scope="col">Group</th>
                    {walkT.map((x) => (
                      <th key={x} className="n" scope="col">
                        ≤ {x} %
                      </th>
                    ))}
                    <th className="n" scope="col">
                      Mean
                    </th>
                    <th className="n" scope="col">
                      p90
                    </th>
                    {walkT.map((x, i) => (
                      <th key={x} className={`n col-a1${i ? "" : " col-sep"}`} scope="col">
                        ≤ {x}
                      </th>
                    ))}
                    <th className="n col-a1" scope="col">
                      Mean
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((x) => (
                    <tr key={x} data-selected={x === g ? "true" : undefined}>
                      <th scope="row" style={{ fontWeight: 500 }}>
                        {groupLabel(x)}
                      </th>
                      {walkT.map((tt) => (
                        <td key={tt} className="n">
                          <Num v={w3(x, pctKey(tt))} d={2} />
                        </td>
                      ))}
                      <td className="n">
                        <Num v={w3(x, "mean_min")} d={2} />
                      </td>
                      <td className="n">
                        <Num v={w3(x, "p90_min")} d={2} />
                      </td>
                      {walkT.map((tt, i) => (
                        <td key={tt} className={`n col-a1${i ? "" : " col-sep"}`}>
                          <Num v={w1(x, pctKey(tt))} d={2} />
                        </td>
                      ))}
                      <td className="n col-a1">
                        <Num v={w1(x, "mean_min")} d={2} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {!compact && (
          <div className="drawer__section" style={{ borderTop: "3px solid var(--scenario-drive)" }}>
            <h3>
              Driving · separate mode <Scen k="drive" />
            </h3>
            <div className="table-wrap">
              <table className="data-table data-table--compact">
                <thead>
                  <tr>
                    <th scope="col">Group</th>
                    {driveT.map((x) => (
                      <th key={x} className="n" scope="col">
                        ≤ {x} %
                      </th>
                    ))}
                    <th className="n" scope="col">
                      Mean
                    </th>
                    <th className="n" scope="col">
                      p90
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((x) => (
                    <tr key={x}>
                      <th scope="row" style={{ fontWeight: 500 }}>
                        {groupLabel(x)}
                      </th>
                      {[...driveT.map(pctKey), "mean_min", "p90_min"].map((st) => (
                        <td key={st} className="n">
                          <Num v={dv(x, st)} d={2} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="small muted" style={{ margin: ".5rem 0 0" }}>
              <Num v={r.a1_drive_access?.pop_drive_access_gt_flag} d={1} /> residents have a walk to the car above the drive-access flag distance.
              <Ref codes={["DQ-DRIVE"]} />
            </p>
          </div>
        )}
        <div className="drawer__section">
          <h3>Facility counts ({FAC_CATS.length} categories)</h3>
          <div className="fc-grid">
            {FAC_CATS.map((c) => (
              <div key={c} className={DESCRIPTIVE_ONLY.includes(c) ? "fc-desc" : ""}>
                <span>
                  {facCatLabel(c)}
                  {DESCRIPTIVE_ONLY.includes(c) && (
                    <>
                      {" "}
                      <small>(descr.)</small>
                    </>
                  )}
                </span>
                <b>
                  <Int v={r.facility_counts[`n_${c}`]} />
                </b>
              </div>
            ))}
          </div>
          <p className="small muted" style={{ margin: ".4rem 0 0" }}>
            Inventory <Rel level={relOf(r, "facility_inventory").level} /> · {dq.n_facilities_duplicate_review} in duplicate review
            <Ref codes={["DQ-FAC-OSM", "DQ-DUP"]} />
          </p>
        </div>
        {!compact && (
          <div className="drawer__section panel--evidence" style={{ padding: "var(--space-3)", border: "1px solid #d8c79a", borderRadius: "var(--radius-sm)" }}>
            <h3>
              Internal access within isolated fragments <Role k="evidence" />
            </h3>
            {hasLocal ? (
              <dl className="kv">
                <dt>Locally connected residents</dt>
                <dd>
                  <Num v={localKeys[0]} d={1} /> · of whom <Num v={localKeys[1]} d={1} /> reach {groupLabel(g).toLowerCase()} ≤ 15 min internally
                </dd>
                <dt>Access-uncertain residents</dt>
                <dd>
                  <Num v={localKeys[2]} d={1} /> · <Num v={localKeys[3]} d={1} /> ≤ 15 min internally
                </dd>
              </dl>
            ) : (
              <p className="small" style={{ margin: 0 }}>
                No locally connected or access-uncertain residents in this barangay.
              </p>
            )}
            <p className="small muted" style={{ margin: ".4rem 0 0" }}>
              Never counted as citywide access.
              <Ref codes={["DQ-LOCAL"]} />
            </p>
          </div>
        )}
        <div className="drawer__section">
          <h3>Notes</h3>
          <div className="map-legend__chips">
            {codes.map((c) => (
              <Chip key={c} code={c} />
            ))}
          </div>
        </div>
      </div>
      <div className="drawer__actions">
        {compact ? (
          <a className="btn btn--primary" href={href("barangays", { b: b.code })}>
            Open in Barangay Analysis <Icon name="arrow" />
          </a>
        ) : (
          <>
            <a className="btn" href={href("map", { b: b.code })}>
              <Icon name="map" />
              Show on map
            </a>
            <button type="button" className="btn" onClick={() => window.print()}>
              <Icon name="print" />
              Print profile (A4)
            </button>
          </>
        )}
      </div>
    </>
  );
}
