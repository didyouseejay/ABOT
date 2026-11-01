/**
 * About (#/about): what the dashboard shows and how, in everyday words; what to keep in mind; who made
 * it; and the way into the pages for researchers (methodology, data quality, network evidence).
 */
import { Glyph, type GlyphName } from "../components/glyphs.tsx";
import { PROJECT } from "../components/layout/Brand.tsx";
import { PageHeader } from "../components/ui.tsx";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { fixed, formatUtc } from "../model/format.ts";
import { servicePlural } from "../model/labels.ts";
import { useView } from "../view.tsx";

const STEPS: [GlyphName, string, string][] = [
  ["users", "Where people live", "The city is divided into 100 m squares. Each square gets its share of the 2020 census population of its barangay."],
  ["street", "The streets", "Walking paths and roads come from OpenStreetMap, including one-way streets, rivers and the coastline."],
  ["pin", "The nearest place", "From every square, the dashboard finds the quickest route along the streets to the nearest place of each type."],
  ["list", "Barangay summaries", "The squares are added up for each barangay: how many residents are within 10, 15 or 30 minutes, and the typical trip."],
];

export function AboutPage({ bundle }: { bundle: LoadedBundle }) {
  const { href } = useView();
  const m = bundle.manifest;
  const nBrgy = bundle.indicators.status === "ok" ? bundle.indicators.data.barangays.length : null;
  const research: [string, string, string, GlyphName][] = [
    ["methods", "Methodology", "The full method, scenarios, indicator definitions, limitations and data sources.", "book"],
    ["quality", "Data quality", "Checks, known issues, file integrity, reliability by barangay and the facility inventory.", "info"],
    ["network", "Network connectivity", "How parts of the street network that are not linked to the rest were handled.", "layers"],
  ];
  return (
    <div className="page page--narrow">
      <PageHeader
        title="About this dashboard"
        lead={`ABOT means “reach” in Hiligaynon and Filipino. This dashboard shows how long it takes residents of Iloilo City to walk or drive to the nearest essential services, for each of the city's ${nBrgy ?? ""} barangays.`}
      />
      <section className="section">
        <h2>What you can do here</h2>
        <ul className="feature-list">
          <li>
            <Glyph name="street" />
            <span>
              <b>Explore the map</b> with a street map or satellite background, and see which barangays are close to {m.indicator_groups.slice(0, 3).map((g) => servicePlural(g.id)).join(", ")} and more.
            </span>
          </li>
          <li>
            <Glyph name="search" />
            <span>
              <b>Look up your barangay</b> to see the share of residents near each service and the typical travel time.
            </span>
          </li>
          <li>
            <Glyph name="pin" />
            <span>
              <b>Browse the facilities</b> that were mapped in and around the city.
            </span>
          </li>
        </ul>
      </section>
      <section className="section">
        <h2>How the travel times are worked out</h2>
        <ol className="how-steps">
          {STEPS.map(([icon, t, d], i) => (
            <li key={t}>
              <span className="how-steps__icon">
                <Glyph name={icon} />
              </span>
              <span className="how-steps__n">Step {i + 1}</span>
              <b>{t}</b>
              <p>{d}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className="section">
        <h2>Reading the colors</h2>
        <div className="color-key">
          <div>
            <span className="color-key__bar color-key__bar--share" aria-hidden="true" />
            <p>
              <b>Share of residents:</b> orange means few residents can reach the service in time; blue means most can.
            </p>
          </div>
          <div>
            <span className="color-key__bar color-key__bar--time" aria-hidden="true" />
            <p>
              <b>Travel time:</b> blue means a short trip; orange and brown mean a long one. Grey means there is no data.
            </p>
          </div>
        </div>
      </section>
      <section className="section">
        <h2>Things to keep in mind</h2>
        <ul className="tips tips--plain">
          <li>
            <b>The times are estimates, not measurements.</b> Walking is at a steady pace; driving assumes no traffic and includes the short walk to and from the car.
          </li>
          <li>
            <b>Only the nearest place counts.</b> The dashboard does not know opening hours, which services a place offers, or how crowded it is.
          </li>
          <li>
            <b>The facility list may be incomplete.</b> It comes from OpenStreetMap, which volunteers keep up to date, and has not been checked against official registries.
          </li>
          <li>
            <b>Some barangays have limited data.</b> Where the population or street data is uncertain, the barangay is marked “Limited” and is not ranked.
          </li>
          <li>
            <b>A few places are not linked to the street network</b> in the map data (for example, some areas along rivers or the coast). They are counted as not able to reach the service.
          </li>
        </ul>
      </section>
      <section className="section">
        <h2>Who made this</h2>
        <p>
          {PROJECT.name} ({PROJECT.fullName}) is a research project of {PROJECT.institution}. It is a read-only prototype: nothing you do here is saved or sent anywhere.
        </p>
        <p className="muted small">
          Data prepared {formatUtc(m.generated_utc)} · {fixed(bundle.city.population.total, 0)} residents (2020 census) · Map data © OpenStreetMap contributors · Boundaries: OCHA COD-AB · Satellite imagery © Esri and partners
        </p>
      </section>
      <section className="section" aria-labelledby="research-h">
        <h2 id="research-h">For researchers</h2>
        <p>The full technical record behind every figure on this dashboard:</p>
        <div className="research-cards">
          {research.map(([id, t, d, icon]) => (
            <a key={id} className="research-card" href={href(id)}>
              <Glyph name={icon} />
              <span className="research-card__t">{t}</span>
              <span className="research-card__d">{d}</span>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
