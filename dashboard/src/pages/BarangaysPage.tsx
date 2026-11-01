/**
 * Barangays (#/barangays): find a barangay and compare it with the others on one service. Ranks are
 * given only to ranking-eligible barangays (rank 1 = least access); when sorted by access, barangays
 * with limited data follow in their own group, unranked, so they are never compared with the rest.
 * Selecting a barangay opens its profile.
 */
import { useEffect, useState } from "react";
import { ModeSwitch, ServiceSelect, TimeLimit } from "../components/controls.tsx";
import { Glyph } from "../components/glyphs.tsx";
import { EmptyState, Unavailable } from "../components/states/States.tsx";
import { PageHeader } from "../components/ui.tsx";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { CONFIDENCE, serviceName, servicePhrase } from "../model/labels.ts";
import { brgyAvg, brgyShare, intText, limitOf, minText, pctText, verbOf } from "../model/plain.ts";
import { type Barangay, barangaysOf, rankEligible, relOf } from "../model/values.ts";
import { useView } from "../view.tsx";
import { BarangayPanel, NOT_RANKED } from "./common.tsx";

const SORTS: [string, string][] = [
  ["least", "Least access first"],
  ["most", "Most access first"],
  ["name", "Name (A–Z)"],
  ["pop", "Most residents first"],
];

export function BarangaysPage({ bundle }: { bundle: LoadedBundle }) {
  const { s, p, set } = useView();
  const m = bundle.manifest;
  const list = barangaysOf(bundle);
  const groups = m.indicator_groups.map((x) => x.id);
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
        <PageHeader title="Barangays" />
        <Unavailable bundle={bundle} dataset="indicators" what="The barangay list" />
      </div>
    );
  }

  const sort = SORTS.some(([k]) => k === p["sort"]) ? (p["sort"] as string) : "least";
  const share = (b: Barangay) => brgyShare(b.rec, s);
  const rank = rankEligible(list, share, true);
  const ql = (p["q"] ?? "").trim().toLowerCase();
  const filtered = list.filter((b) => !ql || b.name.toLowerCase().includes(ql));
  const byShare = (dir: 1 | -1) => (a: Barangay, b: Barangay) => {
    const x = share(a);
    const y = share(b);
    if (x === null) return 1;
    if (y === null) return -1;
    // equal shares (often several at 0 %): the longer typical trip counts as less access
    return dir * (x - y) || dir * ((brgyAvg(b.rec, s) ?? Infinity) - (brgyAvg(a.rec, s) ?? Infinity)) || a.name.localeCompare(b.name);
  };
  const byValue = sort === "least" || sort === "most";
  let ranked: Barangay[];
  let unranked: Barangay[] = [];
  if (byValue) {
    const cmp = byShare(sort === "least" ? 1 : -1);
    ranked = filtered.filter((b) => b.rec.data_quality.ranking_eligible).sort(cmp);
    unranked = filtered.filter((b) => !b.rec.data_quality.ranking_eligible).sort(cmp);
  } else {
    ranked = [...filtered].sort(sort === "name" ? (a, b) => a.name.localeCompare(b.name) : (a, b) => (b.rec.pop_total ?? 0) - (a.rec.pop_total ?? 0));
  }
  const all = p["all"] === "1" || ql !== "";
  const shownRanked = all ? ranked : ranked.slice(0, 50);
  const hidden = ranked.length - shownRanked.length;
  const shownUnranked = hidden > 0 ? [] : unranked;
  const nElig = list.filter((b) => b.rec.data_quality.ranking_eligible).length;

  const close = () => {
    const opener = p["b"];
    set({ b: null });
    setTimeout(() => document.getElementById(`open-${opener}`)?.focus(), 0);
  };

  const row = (b: Barangay) => {
    const v = share(b);
    const r = rank.get(b.code);
    const rel = relOf(b.rec, "overall");
    const eligible = b.rec.data_quality.ranking_eligible;
    return (
      <tr key={b.code} data-selected={String(p["b"] === b.code)}>
        <td className="n brgy-table__rank">{eligible ? (r ?? "—") : <span className="not-ranked" title={NOT_RANKED}>–</span>}</td>
        <th scope="row">
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
        </th>
        <td className="n brgy-table__pop">{intText(b.rec.pop_total)}</td>
        <td className="brgy-table__share">
          <span className="meter" aria-hidden="true">
            <span className="meter__fill" style={{ width: `${v ?? 0}%` }} />
          </span>
          <span className="num">{pctText(v)}</span>
        </td>
        <td className="n brgy-table__avg">{minText(brgyAvg(b.rec, s))}</td>
        <td className="brgy-table__conf">
          <span className={`conf conf--${rel.level}`}>{CONFIDENCE[rel.level]?.[0] ?? "Unknown"}</span>
        </td>
      </tr>
    );
  };

  return (
    <div className="page" onKeyDown={(e) => e.key === "Escape" && open && close()}>
      <PageHeader title="Barangays" lead={`Find your barangay and see how close essential services are. All ${list.length} barangays of Iloilo City are listed.`} />
      <div className="toolbar card" role="search" aria-label="Find and sort barangays">
        <label className="field toolbar__search" htmlFor="bf-q">
          <span className="field__label">Search</span>
          <span className="input-icon">
            <Glyph name="search" />
            <input className="input" id="bf-q" type="search" value={q} placeholder="Type a barangay name" onChange={(e) => setQ(e.target.value)} />
          </span>
        </label>
        <ServiceSelect id="bg-g" groups={groups} />
        <ModeSwitch id="bg-m" />
        <TimeLimit id="bg-t" walk={m.thresholds_min.walk} drive={m.thresholds_min.drive} />
        <label className="field" htmlFor="bf-sort">
          <span className="field__label">Sort</span>
          <select className="select" id="bf-sort" value={sort} onChange={(e) => set({ sort: e.target.value === "least" ? null : e.target.value })}>
            {SORTS.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="result-count" aria-live="polite">
        {ql ? `${filtered.length} of ${list.length} barangays match “${p["q"]}”.` : `Showing how many residents can ${verbOf(s)} to ${servicePhrase(s.g)} within ${limitOf(s)} minutes.`}
      </p>
      {filtered.length === 0 ? (
        <EmptyState
          title="No barangay matches that name"
          action={
            <button
              type="button"
              className="btn btn--sm"
              id="clear-filters"
              onClick={() => {
                setQ("");
                set({ q: null });
              }}
            >
              Clear search
            </button>
          }
        >
          <p>Check the spelling, or clear the search to see every barangay.</p>
        </EmptyState>
      ) : (
        <div className="table-wrap brgy-table-wrap">
          <table className="data-table brgy-table" id="b-table">
            <caption className="visually-hidden">
              Barangays, {serviceName(s.g)}, {s.m === "drive" ? "by car" : "walking"} within {limitOf(s)} minutes, sorted by {SORTS.find(([k]) => k === sort)?.[1]}
            </caption>
            <thead>
              <tr>
                <th scope="col" className="n" title={`Rank among the ${nElig} barangays with enough data; 1 = least access`}>
                  Rank
                </th>
                <th scope="col">Barangay</th>
                <th scope="col" className="n brgy-table__pop">
                  Residents
                </th>
                <th scope="col">Within {limitOf(s)} min</th>
                <th scope="col" className="n brgy-table__avg">
                  Typical {verbOf(s)}
                </th>
                <th scope="col" className="brgy-table__conf">
                  Data
                </th>
              </tr>
            </thead>
            <tbody>
              {shownRanked.map(row)}
              {shownUnranked.length > 0 && (
                <>
                  <tr className="brgy-table__group">
                    <th colSpan={6} scope="rowgroup">
                      Not ranked · limited data ({unranked.length})
                      <span>The population or road data for these barangays is too uncertain to compare fairly.</span>
                    </th>
                  </tr>
                  {shownUnranked.map(row)}
                </>
              )}
            </tbody>
          </table>
        </div>
      )}
      {hidden > 0 && (
        <div className="more-row">
          <button type="button" className="btn" id="b-all" onClick={() => set({ all: "1" })}>
            Show all {ranked.length + unranked.length} barangays
          </button>
        </div>
      )}
      {open && (
        <>
          <div className="scrim" aria-hidden="true" onClick={close} />
          <aside className="drawer drawer--wide" id="b-profile" aria-labelledby="drawer-title">
            <BarangayPanel b={open} groups={groups} compact={false} onClose={close} />
          </aside>
        </>
      )}
    </div>
  );
}
