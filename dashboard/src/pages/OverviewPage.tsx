/**
 * Home (#/overview): the citywide picture for residents. One sentence answers "how many people can
 * reach this service in time?", a card per service gives the same figure for every service, and a short
 * list names the barangays with the least access (ranking-eligible barangays only). Walking is the
 * primary (A3) result; "by car" is A1 driving. Technical detail is on the pages for researchers.
 */
import { ModeSwitch, ServiceSelect, TimeLimit } from "../components/controls.tsx";
import { Glyph, ServiceGlyph } from "../components/glyphs.tsx";
import { guard } from "../components/states/States.tsx";
import { PAGE_TITLE_ID } from "../components/layout/ids.ts";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { fixed } from "../model/format.ts";
import { serviceName, servicePhrase } from "../model/labels.ts";
import { brgyAvg, brgyShare, cityAvg, cityShare, limitOf, minText, pctText, verbOf } from "../model/plain.ts";
import { barangaysOf } from "../model/values.ts";
import { useView } from "../view.tsx";

function Headline({ b, groups }: { b: LoadedBundle; groups: string[] }) {
  const { s } = useView();
  const m = b.manifest;
  const v = cityShare(b.city, s);
  return (
    <section className="card headline" aria-labelledby="headline-h">
      <h2 className="visually-hidden" id="headline-h">
        Citywide answer
      </h2>
      <div className="headline__controls">
        <ServiceSelect id="ov-g" groups={groups} />
        <ModeSwitch id="ov-m" />
        <TimeLimit id="ov-t" walk={m.thresholds_min.walk} drive={m.thresholds_min.drive} />
      </div>
      <p className="headline__sentence" aria-live="polite">
        <span className="headline__value">{pctText(v)}</span> of Iloilo City residents can {verbOf(s)} to {servicePhrase(s.g)} within {limitOf(s)} minutes.
      </p>
      <div className="meter meter--lg" aria-hidden="true">
        <span className="meter__fill" style={{ width: `${v ?? 0}%` }} />
      </div>
      <p className="headline__sub">
        <Glyph name="clock" /> Typical {verbOf(s)} to the nearest {serviceName(s.g).toLowerCase()}: <b>{minText(cityAvg(b.city, s))}</b>
      </p>
    </section>
  );
}

function ServiceCards({ b, groups }: { b: LoadedBundle; groups: string[] }) {
  const { s, set } = useView();
  return (
    <section className="section" aria-labelledby="svc-h">
      <div className="section__head">
        <h2 id="svc-h">Every service at a glance</h2>
        <p>
          Share of residents who can {verbOf(s)} there within {limitOf(s)} minutes. Choose a service to see it above and on the list below.
        </p>
      </div>
      <ul className="svc-cards">
        {groups.map((g) => {
          const v = cityShare(b.city, s, g);
          return (
            <li key={g}>
              <button type="button" className="svc-card" id={`svc-${g}`} aria-pressed={g === s.g} onClick={() => set({ g })}>
                <span className="svc-card__icon">
                  <ServiceGlyph id={g} />
                </span>
                <span className="svc-card__name">{serviceName(g)}</span>
                <span className="svc-card__v">{pctText(v)}</span>
                <span className="meter" aria-hidden="true">
                  <span className="meter__fill" style={{ width: `${v ?? 0}%` }} />
                </span>
                <span className="svc-card__avg">Typical: {minText(cityAvg(b.city, s, g))}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function LeastServed({ b }: { b: LoadedBundle }) {
  const { s, href } = useView();
  const list = barangaysOf(b);
  if (!list) return null;
  const rows = list
    .filter((x) => x.rec.data_quality.ranking_eligible && brgyShare(x.rec, s) !== null)
    // ties (often several at 0 %) go to the longer typical trip
    .sort((x, y) => (brgyShare(x.rec, s) as number) - (brgyShare(y.rec, s) as number) || (brgyAvg(y.rec, s) ?? Infinity) - (brgyAvg(x.rec, s) ?? Infinity))
    .slice(0, 5);
  return (
    <section className="card" aria-labelledby="least-h">
      <h2 id="least-h" className="card__title">
        Barangays with the least access
      </h2>
      <p className="card__sub">
        Lowest share of residents who can {verbOf(s)} to {servicePhrase(s.g)} within {limitOf(s)} minutes.
      </p>
      <ol className="rank-list">
        {rows.map((x, i) => {
          const v = brgyShare(x.rec, s);
          return (
            <li key={x.code}>
              <span className="rank-list__n">{i + 1}</span>
              <a className="rank-list__name" href={href("map", { b: x.code })}>
                {x.name}
              </a>
              <span className="meter" aria-hidden="true">
                <span className="meter__fill meter__fill--warn" style={{ width: `${v ?? 0}%` }} />
              </span>
              <span className="rank-list__v">{pctText(v)}</span>
            </li>
          );
        })}
      </ol>
      <a className="card__link" href={href("barangays")}>
        See all {list.length} barangays <Glyph name="arrowRight" />
      </a>
    </section>
  );
}

function GoodToKnow() {
  const { href } = useView();
  return (
    <section className="card card--soft" aria-labelledby="know-h">
      <h2 id="know-h" className="card__title">
        Good to know
      </h2>
      <ul className="tips">
        <li>
          <b>These are estimates.</b> Travel times follow the mapped streets to the <i>nearest</i> facility, at a steady walking pace or by car without traffic.
        </li>
        <li>
          <b>Facility locations come from OpenStreetMap,</b> a map made by volunteers. Some places may be missing or out of date.
        </li>
        <li>
          <b>Nearest is not always best.</b> The figures do not show opening hours, services offered or how crowded a place is.
        </li>
      </ul>
      <a className="card__link" href={href("about")}>
        How this works <Glyph name="arrowRight" />
      </a>
    </section>
  );
}

export function OverviewPage({ bundle }: { bundle: LoadedBundle }) {
  const { href } = useView();
  const groups = bundle.manifest.indicator_groups.map((g) => g.id);
  const total = bundle.city.population.total;
  const nBrgy = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.length : null;
  return (
    <div className="home">
      <section className="hero-band">
        <div className="hero-band__inner">
          <p className="hero-band__eyebrow">
            Iloilo City{nBrgy === null ? "" : ` · ${nBrgy} barangays`} · {fixed(total, 0)} residents
          </p>
          <h1 id={PAGE_TITLE_ID} tabIndex={-1}>
            How close are essential services to you?
          </h1>
          <p className="hero-band__lead">See how long it takes people in Iloilo City to walk or drive to the nearest hospital, health center, school, market and more, for every barangay.</p>
          <div className="hero-band__actions">
            <a className="btn btn--primary btn--lg" href={href("map")}>
              <Glyph name="street" />
              Explore the map
            </a>
            <a className="btn btn--ghost btn--lg" href={href("barangays")}>
              <Glyph name="search" />
              Find your barangay
            </a>
          </div>
        </div>
      </section>
      <div className="page page--home">
        {guard("The citywide answer", () => <Headline b={bundle} groups={groups} />)}
        {guard("The service cards", () => <ServiceCards b={bundle} groups={groups} />)}
        <div className="two-col">
          {guard("The least-served list", () => <LeastServed b={bundle} />)}
          <GoodToKnow />
        </div>
      </div>
    </div>
  );
}
