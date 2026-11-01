/**
 * Barangay Analysis (#/barangays): a sortable, filterable table of every barangay. Ranks are given
 * only to ranking-eligible barangays (rank 1 = worst served on the rank column); ineligible rows stay
 * in the table, unranked, with the reason. A profile drawer and a compare tray (up to 3) follow the
 * same rules as the map: A1 walking beside A3 only, driving in its own block.
 */
import { type ReactNode, useEffect, useState } from "react";
import { Chip, Ref } from "../components/notes.tsx";
import { EmptyState, Unavailable } from "../components/states/States.tsx";
import { Badge, GroupSelect, Icon, Int, Num, NullValue, PageHeader, Rel, Scen, Seg, StatStrip, thresholdOptions } from "../components/ui.tsx";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { delta, fixed } from "../model/format.ts";
import { groupLabel } from "../model/labels.ts";
import { pctKey } from "../model/view.ts";
import { type Barangay, barangaysOf, bval, rankEligible, relCounts, relOf } from "../model/values.ts";
import { useView } from "../view.tsx";
import { BarangayPanel, NOT_RANKED, PrintHead } from "./common.tsx";

interface SortDef {
  label: string;
  f: (b: Barangay, g: string) => number | string | null;
  text?: boolean;
  /** A larger value is better served (shares); ranks put the lowest first. */
  hi?: boolean;
}

const RELORDER: Record<string, number> = { ok: 0, caution: 1, low: 2 };

function sorts(walkT: readonly number[]): Record<string, SortDef> {
  const out: Record<string, SortDef> = {
    name: { label: "Barangay", f: (b) => b.name, text: true },
    pop: { label: "Population", f: (b) => b.rec.pop_total },
    rel: { label: "Overall reliability", f: (b) => RELORDER[relOf(b.rec, "overall").level] ?? 3 },
  };
  for (const t of walkT) out[`a3_${t}`] = { label: `A3 % ≤ ${t} min`, f: (b, g) => bval(b.rec, "A3", g, pctKey(t)), hi: true };
  out["a3_mean"] = { label: "A3 mean (min)", f: (b, g) => bval(b.rec, "A3", g, "mean_min") };
  out["a3_p90"] = { label: "A3 p90 (min)", f: (b, g) => bval(b.rec, "A3", g, "p90_min") };
  out["unc"] = { label: "A3 unconnected %", f: (b) => b.rec.a3_population.unconnected?.pct ?? null };
  return out;
}

const LEVELS = ["ok", "caution", "low"] as const;
const LEVEL_WORD = { ok: "OK", caution: "Caution", low: "Low" };

export function BarangaysPage({ bundle }: { bundle: LoadedBundle }) {
  const { s, p, set } = useView();
  const m = bundle.manifest;
  const list = barangaysOf(bundle);
  const groups = m.indicator_groups.map((x) => x.id);
  const walkT = m.thresholds_min.walk;
  const { g, t, dt } = s;
  const [q, setQ] = useState(p["q"] ?? "");
  const open = p["b"] && list ? list.find((x) => x.code === p["b"]) : undefined;

  useEffect(() => {
    const id = setTimeout(() => {
      if ((p["q"] ?? "") !== q) set({ q: q || null });
    }, 150);
    return () => clearTimeout(id);
    // only the typed text drives this; the address is written once typing pauses
  }, [q]);

  useEffect(() => {
    document.body.dataset["drawer"] = open ? "open" : "";
    return () => {
      document.body.dataset["drawer"] = "";
    };
  }, [open]);

  if (!list) {
    return (
      <div className="page">
        <PageHeader title="Barangay analysis" />
        <Unavailable bundle={bundle} dataset="indicators" what="The barangay table" />
      </div>
    );
  }

  const S = sorts(walkT);
  const key = p["sort"] && S[p["sort"]] ? p["sort"] : "a3_mean";
  const sd = S[key] as SortDef;
  const dir = p["dir"] === "asc" || p["dir"] === "desc" ? p["dir"] : sd.text ? "asc" : "desc";
  const rankKey = key.startsWith("a3_") ? key : "a3_mean";
  const rd = S[rankKey] as SortDef;
  const rank = rankEligible(list, (b) => rd.f(b, g) as number | null, rd.hi === true);
  const showA1 = p["a1"] !== "0";
  const rel = p["rel"] ? p["rel"].split(",") : [...LEVELS];
  const ql = (p["q"] ?? "").trim().toLowerCase();
  const filtered = list.filter(
    (b) =>
      (!ql || b.name.toLowerCase().includes(ql) || b.code.toLowerCase().includes(ql)) &&
      rel.includes(relOf(b.rec, "overall").level) &&
      (p["elig"] !== "1" || b.rec.data_quality.ranking_eligible) &&
      (p["flag"] !== "1" || b.rec.data_quality.indicators_flag_not_connected),
  );
  const rows = [...filtered].sort((a, b) => {
    const x = sd.f(a, g);
    const y = sd.f(b, g);
    if (x === null) return 1;
    if (y === null) return -1;
    const c = typeof x === "string" ? x.localeCompare(String(y)) : x - (y as number);
    return dir === "asc" ? c : -c;
  });
  const shown = p["all"] === "1" ? rows : rows.slice(0, 50);
  const cmp = (p["cmp"] ?? "").split(",").filter((c) => list.some((x) => x.code === c));
  const counts = relCounts(list, "overall");
  const nElig = list.filter((b) => b.rec.data_quality.ranking_eligible).length;
  const nFlag = list.filter((b) => b.rec.data_quality.indicators_flag_not_connected).length;
  const ti = walkT.indexOf(t);

  const sortBy = (k: string) => {
    const d = S[k] as SortDef;
    const nextDir = key === k ? (dir === "asc" ? "desc" : "asc") : d.text ? "asc" : "desc";
    set({ sort: k, dir: nextDir });
  };
  const th = (k: string, extra: ReactNode = null, cls = "n") => (
    <th key={k} scope="col" className={cls} aria-sort={key === k ? (dir === "asc" ? "ascending" : "descending") : undefined}>
      <button type="button" className="sort-btn" id={`sort-${k}`} onClick={() => sortBy(k)}>
        {(S[k] as SortDef).label.replace(/^A3 /, "")}
        {extra}
        <span className="sort-ind" aria-hidden="true">
          {key === k ? (dir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
  const close = () => {
    const opener = p["b"];
    set({ b: null });
    setTimeout(() => document.getElementById(`open-${opener}`)?.focus(), 0);
  };
  const colCount = 6 + walkT.length + 2 + (showA1 ? 3 : 0) + 1;

  return (
    <div className="page" onKeyDown={(e) => e.key === "Escape" && open && close()}>
      <PrintHead what={open ? `Barangay profile: ${open.name}` : "Barangay analysis"} manifest={m} />
      <PageHeader
        eyebrow={`${list.length} barangays · ${nElig} ranking-eligible`}
        title="Barangay analysis"
        lead="Compare barangays on the selected group. Ranks are given only to ranking-eligible barangays; rank 1 is the lowest share or the longest time, i.e. the worst served on that column."
        controls={
          <>
            <GroupSelect id="bg-g" groups={groups} value={g} onChange={(x) => set({ g: x })} />
            <Seg id="bg-t" label="Highlight threshold" options={thresholdOptions(walkT)} value={String(t)} onChange={(x) => set({ t: x })} />
          </>
        }
      />
      <StatStrip
        items={[
          [list.length, "barangays (all shown)"],
          [nElig, "ranking-eligible"],
          [<><Rel level="ok" /> {counts.ok}</>, "overall reliability OK"],
          [<><Rel level="caution" /> {counts.caution}</>, "caution"],
          [<><Rel level="low" /> {counts.low}</>, "low"],
          [<Rel level="unverified" />, `facility inventory, all ${list.length}`],
        ]}
      />
      <div className="filterbar" role="search" aria-label="Filter barangays">
        <label className="field" htmlFor="bf-q">
          <span className="field__label">Search name or p-code</span>
          <input className="input" id="bf-q" type="search" value={q} placeholder="e.g. Tacas" style={{ width: "13rem" }} onChange={(e) => setQ(e.target.value)} />
        </label>
        <fieldset>
          <legend>Overall reliability</legend>
          <div className="chipset">
            {LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                className="chip-toggle"
                id={`bf-rel-${l}`}
                aria-pressed={rel.includes(l)}
                onClick={() => {
                  const next = new Set(rel);
                  if (next.has(l)) next.delete(l);
                  else next.add(l);
                  set({ rel: next.size === LEVELS.length ? null : [...next].join(",") || "none" });
                }}
              >
                {LEVEL_WORD[l]} <span className="muted">{counts[l]}</span>
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Show</legend>
          <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap" }}>
            <label className="check" htmlFor="bf-elig">
              <input type="checkbox" id="bf-elig" checked={p["elig"] === "1"} onChange={(e) => set({ elig: e.target.checked ? "1" : null })} />
              Ranking-eligible only ({nElig})
            </label>
            <label className="check" htmlFor="bf-flag">
              <input type="checkbox" id="bf-flag" checked={p["flag"] === "1"} onChange={(e) => set({ flag: e.target.checked ? "1" : null })} />⚑ &gt; 5 % not connected ({nFlag})
            </label>
          </div>
        </fieldset>
        <label className="switch" htmlFor="bf-a1">
          <input type="checkbox" id="bf-a1" checked={showA1} onChange={(e) => set({ a1: e.target.checked ? null : "0" })} />A1 comparison columns
        </label>
        <span className="filterbar__count" aria-live="polite">
          Showing <b>{filtered.length}</b> of {list.length}
        </span>
      </div>
      <div className="table-wrap" style={{ maxHeight: "70vh" }}>
        <table className="data-table" id="b-table">
          <caption className="visually-hidden">
            Barangays with {groupLabel(g)} indicators, sorted by {sd.label} {dir}ending
          </caption>
          <thead>
            <tr className="data-table__group">
              <th colSpan={6} />
              <th colSpan={walkT.length + 2} className="col-sep">
                <Scen k="a3" /> {groupLabel(g)}
              </th>
              {showA1 && (
                <th colSpan={3} className="col-sep col-a1">
                  <Scen k="a1" />
                </th>
              )}
              <th />
            </tr>
            <tr>
              <th scope="col">
                <span className="visually-hidden">Compare</span>
              </th>
              <th scope="col" className="n" title={`Rank among the ${nElig} ranking-eligible barangays by ${rd.label}; 1 = ${rd.hi ? "lowest share" : "longest time"}`}>
                Rank
                <br />
                <span style={{ fontWeight: 400 }}>{rd.label.replace("A3 ", "")}</span>
              </th>
              {th("name", null, "")}
              {th("pop")}
              {th("rel", null, "")}
              <th scope="col">Ranking</th>
              {walkT.map((x, i) => th(`a3_${x}`, i === 0 ? <Ref codes={["DQ-SHARE-ALL"]} /> : null, `n${i === 0 ? " col-sep" : ""}`))}
              {th("a3_mean", <Ref codes={["DQ-MEAN-CONN"]} />)}
              {th("a3_p90")}
              {showA1 && (
                <>
                  <th scope="col" className="n col-a1 col-sep">
                    % ≤ {t}
                    <Ref codes={["DQ-A1-OPT"]} />
                  </th>
                  <th scope="col" className="n col-a1">
                    Mean
                  </th>
                  <th scope="col" className="n col-a1">
                    Δ mean
                  </th>
                </>
              )}
              {th("unc")}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={colCount} style={{ padding: "var(--space-5)" }}>
                  <EmptyState
                    title="No barangays match these filters"
                    action={
                      <button
                        type="button"
                        className="btn btn--sm"
                        id="clear-filters"
                        onClick={() => {
                          setQ("");
                          set({ q: null, rel: null, elig: null, flag: null });
                        }}
                      >
                        Clear all filters
                      </button>
                    }
                  >
                    <p>
                      {ql ? `Search “${p["q"]}” with the` : "The"} current reliability and eligibility filters return nothing. Values are not hidden for any other reason.
                    </p>
                  </EmptyState>
                </td>
              </tr>
            ) : (
              shown.map((b) => {
                const dq = b.rec.data_quality;
                const r = rank.get(b.code);
                const o = relOf(b.rec, "overall");
                const w = (st: string) => bval(b.rec, "A3", g, st);
                const a = (st: string) => bval(b.rec, "A1", g, st);
                const checked = cmp.includes(b.code);
                return (
                  <tr key={b.code} data-selected={String(p["b"] === b.code)}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Compare ${b.name}`}
                        checked={checked}
                        disabled={!checked && cmp.length >= 3}
                        onChange={(e) => {
                          const next = new Set(cmp);
                          if (e.target.checked) next.add(b.code);
                          else next.delete(b.code);
                          set({ cmp: [...next].join(",") || null });
                        }}
                      />
                    </td>
                    <td className="n">
                      {dq.ranking_eligible ? (
                        r !== undefined ? (
                          <span className="rank">{r}</span>
                        ) : (
                          <NullValue reason="No value for this column" />
                        )
                      ) : (
                        <span className="not-ranked" tabIndex={0} title={`${NOT_RANKED}. ${o.reasons ?? ""}`}>
                          not ranked
                        </span>
                      )}
                    </td>
                    <th scope="row" style={{ fontWeight: 400 }}>
                      <button
                        type="button"
                        className="row-link"
                        id={`open-${b.code}`}
                        onClick={() => {
                          set({ b: b.code });
                          setTimeout(() => document.querySelector<HTMLElement>("#b-profile .drawer__close")?.focus(), 0);
                        }}
                      >
                        {b.name}
                      </button>
                      {dq.resolved_separately && (
                        <>
                          {" "}
                          <Chip code="DQ-RESOLVED" />
                        </>
                      )}
                      <span className="pcode">{b.code}</span>
                    </th>
                    <td className="n">
                      <Int v={b.rec.pop_total} />
                    </td>
                    <td>
                      <Rel level={o.level} reason={o.reasons} />
                    </td>
                    <td className="small">{dq.ranking_eligible ? "Eligible" : <span className="muted">{NOT_RANKED}</span>}</td>
                    {walkT.map((x, i) => {
                      const v = w(pctKey(x));
                      return (
                        <td key={x} className={`n${i === 0 ? " col-sep" : ""}`} style={i === ti ? { fontWeight: 650 } : undefined}>
                          <Num v={v} d={2} />
                          {i === ti && v !== null && (
                            <span className="inline-bar" aria-hidden="true">
                              <span className="inline-bar__fill" style={{ width: `${v}%` }} />
                            </span>
                          )}
                        </td>
                      );
                    })}
                    <td className="n">
                      <Num v={w("mean_min")} d={2} />
                    </td>
                    <td className="n">
                      <Num v={w("p90_min")} d={2} />
                    </td>
                    {showA1 && (
                      <>
                        <td className="n col-a1 col-sep">
                          <Num v={a(pctKey(t))} d={2} />
                        </td>
                        <td className="n col-a1">
                          <Num v={a("mean_min")} d={2} />
                        </td>
                        <td className="n col-a1">{delta(w("mean_min"), a("mean_min"))}</td>
                      </>
                    )}
                    <td className="n">
                      <Num v={b.rec.a3_population.unconnected?.pct} d={2} />
                      {dq.indicators_flag_not_connected && (
                        <>
                          {" "}
                          <span title="More than 5 % of residents not connected" aria-label="flag: more than 5 % not connected">
                            ⚑
                          </span>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {rows.length > shown.length && (
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", padding: "var(--space-3) 0" }}>
          <button type="button" className="btn btn--sm" id="b-all" onClick={() => set({ all: "1" })}>
            Show all {rows.length} rows
          </button>
          <span className="small muted">
            Showing the first {shown.length} in the current sort. Ranks are computed over all {nElig} eligible barangays.
          </span>
        </div>
      )}
      <p className="small muted" style={{ marginTop: "var(--space-2)" }}>
        Percentages: share of all residents
        <Ref codes={["DQ-SHARE-ALL"]} />. Barangay values use fractional cell allocation
        <Ref codes={["DQ-POP-ALLOC"]} />. A1 columns are an optimistic comparison
        <Ref codes={["DQ-A1-OPT"]} />. Driving is in each profile, in its own block.
      </p>
      {cmp.length > 0 && (
        <section className="compare-tray" aria-labelledby="cmp-h">
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "baseline", marginBottom: "var(--space-2)" }}>
            <h2 id="cmp-h" style={{ margin: 0, fontSize: "var(--font-size-md)" }}>
              <Icon name="compare" /> Compare {cmp.length} of 3 · {groupLabel(g)}
            </h2>
            <button type="button" className="linkbtn small" id="cmp-clear" style={{ marginLeft: "auto" }} onClick={() => set({ cmp: null })}>
              Clear
            </button>
          </div>
          <CompareGrid bs={cmp.map((c) => list.find((x) => x.code === c) as Barangay)} g={g} walkT={walkT} t={t} dt={dt} />
        </section>
      )}
      {open && (
        <aside className="drawer" id="b-profile" aria-labelledby="drawer-title" style={{ width: "min(44rem,100vw)" }}>
          <BarangayPanel b={open} groups={groups} walkT={walkT} driveT={m.thresholds_min.drive} compact={false} onClose={close} />
        </aside>
      )}
    </div>
  );
}

function CompareGrid({ bs, g, walkT, t, dt }: { bs: Barangay[]; g: string; walkT: readonly number[]; t: number; dt: number }) {
  const row = (label: string, f: (b: Barangay) => ReactNode, cls = "") => (
    <>
      <div className={`l ${cls}`}>{label}</div>
      {bs.map((b) => (
        <div key={b.code} className={cls}>
          {f(b)}
        </div>
      ))}
    </>
  );
  const n = (v: number | null) => (v === null ? "—" : fixed(v, 1));
  return (
    <div className="compare-grid" style={{ ["--n" as string]: bs.length }}>
      {row("", (b) => <b>{b.name}</b>, "h")}
      {row("Population", (b) => <Int v={b.rec.pop_total} />)}
      {row("Overall reliability", (b) => {
        const o = relOf(b.rec, "overall");
        return <Rel level={o.level} reason={o.reasons} />;
      })}
      {row("Ranking", (b) => (b.rec.data_quality.ranking_eligible ? "Eligible" : <Badge tone="unknown">Not ranked</Badge>))}
      {row(`A3 % ≤ ${walkT.join(" / ")}`, (b) => walkT.map((x) => n(bval(b.rec, "A3", g, pctKey(x)))).join(" / "))}
      {row("A3 mean · p90 (min)", (b) => `${n(bval(b.rec, "A3", g, "mean_min"))} · ${n(bval(b.rec, "A3", g, "p90_min"))}`)}
      {row(`A1 % ≤ ${t} (comparison)`, (b) => <span style={{ color: "var(--scenario-a1)" }}>{n(bval(b.rec, "A1", g, pctKey(t)))}</span>)}
      {row(`Drive % ≤ ${dt} · mean`, (b) => (
        <span style={{ color: "var(--scenario-drive)" }}>
          {n(bval(b.rec, "drive", g, pctKey(dt)))} · {n(bval(b.rec, "drive", g, "mean_min"))} min
        </span>
      ))}
    </div>
  );
}
