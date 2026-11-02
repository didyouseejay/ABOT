/**
 * The application shell and pages rendered to static HTML (react-dom/server; no DOM library) for each
 * bundle state. Checks the top navigation, active-route marking, landmarks, plain language on the public
 * pages, the bundle status on Data quality, the interface states, and that every page renders from the
 * fixture bundle.
 */
import { describe, expect, it } from "vitest";
import type { BundleState } from "../src/data/BundleContext.tsx";
import { type LoadedBundle, loadBundle } from "../src/data/loadBundle.ts";
import { bundleStatusItems, shellStatusItems } from "../src/model/shell.ts";
import { isUnknownHash, routeFromHash } from "../src/router.ts";
import { DEFAULT_ROUTE, ROUTES, ROUTE_IDS, routeDef } from "../src/routes.ts";
import { type Docs, fetcherFor, makeDocs, serialize } from "./fixtures/bundle.ts";
import { render } from "./render.ts";

async function bundle(edit: (d: Docs) => void = () => {}, after: (f: Map<string, Uint8Array>) => void = () => {}, subtle?: SubtleCrypto | null): Promise<LoadedBundle> {
  const docs = makeDocs();
  edit(docs);
  const files = serialize(docs);
  after(files);
  const r = await loadBundle(fetcherFor(files), subtle === undefined ? {} : { subtle });
  if (r.status !== "ready") throw new Error(JSON.stringify(r.issues));
  return r.bundle;
}

const ready = async (...a: Parameters<typeof bundle>): Promise<BundleState> => ({ status: "ready", bundle: await bundle(...a) });

const ALL_DOCS = (d: Docs) => [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks];

describe("routes", () => {
  it("registers five public sections and three pages for researchers, once each", () => {
    expect(ROUTES.filter((r) => !r.reference).map((r) => r.navLabel)).toEqual(["Home", "Map", "Barangays", "Facilities", "About"]);
    expect(ROUTES.filter((r) => r.reference).map((r) => r.id)).toEqual(["methods", "quality", "network"]);
    expect(new Set(ROUTE_IDS).size).toBe(ROUTES.length);
    expect(DEFAULT_ROUTE).toBe("overview");
  });
  it("resolves hash routes and falls back to the overview", () => {
    for (const id of ROUTE_IDS) expect(routeFromHash(`#/${id}`, ROUTE_IDS, DEFAULT_ROUTE)).toBe(id);
    expect(routeFromHash("#/barangays?g=pharmacy", ROUTE_IDS, DEFAULT_ROUTE)).toBe("barangays");
    expect(routeFromHash("#/unknown", ROUTE_IDS, DEFAULT_ROUTE)).toBe("overview");
    expect(routeFromHash("", ROUTE_IDS, DEFAULT_ROUTE)).toBe("overview");
    expect(routeDef("unknown").id).toBe("overview");
  });
  it("detects an unknown section so the address can be corrected, but not an empty hash", () => {
    expect(isUnknownHash("#/nope", ROUTE_IDS)).toBe(true);
    expect(isUnknownHash("#/map?r=1", ROUTE_IDS)).toBe(false);
    expect(isUnknownHash("", ROUTE_IDS)).toBe(false);
    expect(isUnknownHash("#/", ROUTE_IDS)).toBe(false);
  });
});

describe("shell structure and top navigation", () => {
  it("renders the skip link first, the top bar, the five public sections and the main region", async () => {
    const html = render("barangays", await ready());
    expect(html.indexOf('class="skip-link" href="#main-content"')).toBeLessThan(html.indexOf('class="topbar"'));
    expect(html).toContain('<nav class="topnav" aria-label="Main">');
    expect(html).toMatch(/<main class="main" id="main-content" tabindex="-1">/);
    const header = html.slice(html.indexOf('class="topnav"'), html.indexOf("</header>"));
    for (const r of ROUTES) expect(header.includes(`href="#/${r.id}"`), r.id).toBe(!r.reference);
    // the active section is marked in the top bar and in the small-screen menu panel, nowhere else
    expect(html.match(/aria-current="page"/g)).toHaveLength(2);
    expect(html).toMatch(/class="topnav__link" href="#\/barangays" aria-current="page">Barangays</);
    expect(html).toContain('<h1 id="page-title" tabindex="-1">Barangays</h1>');
    expect(html.match(/<h1/g)).toHaveLength(1);
  });
  it("links the pages for researchers from the footer", async () => {
    const html = render("overview", await ready());
    const footer = html.slice(html.indexOf('<footer class="footer">'));
    expect(footer).toContain("For researchers");
    for (const r of ROUTES.filter((x) => x.reference)) expect(footer).toContain(`href="#/${r.id}"`);
  });
  it("shows the project identity in the footer", async () => {
    const html = render("overview", await ready());
    expect(html).toContain("Geospatial Accessibility and Public Infrastructure Intelligence System");
    expect(html).toContain("Bringing essential services within reach.");
    expect(html).toContain("West Visayas State University");
  });
  it("exposes the menu-panel state on the menu button", async () => {
    const s = await ready();
    expect(render("overview", s, false)).toMatch(/aria-expanded="false" aria-controls="navpanel"/);
    const open = render("overview", s, true);
    expect(open).toMatch(/class="topbar__menu-btn" aria-expanded="true"/);
    expect(open).toContain('data-open="true"');
  });
  it("keeps the shared selection in every navigation link", async () => {
    const html = render("overview", await ready(), false, { stat: "mean", sort: "pop" });
    expect(html).toContain('href="#/map?stat=mean"');
    expect(html).not.toContain("sort=pop"); // a page's own parameters stay on that page
  });
  it("has no footer on the full-height map", async () => {
    expect(render("map", await ready())).not.toContain('<footer class="footer">');
  });
});

describe("plain language on the public pages", () => {
  it("shows no scenario codes, statement codes or bundle internals", async () => {
    const s = await ready();
    for (const r of ROUTES.filter((x) => !x.reference)) {
      const main = render(r.id, s).replace(/<footer[\s\S]*$/, "");
      expect(main, r.id).not.toMatch(/\bA[123] ·|DQ-[A-Z]|SHA-256|abot-dashboard v|Notes for this view|caveat-chip/);
    }
  });
  it("answers the headline question in one sentence, read from the bundle", async () => {
    const s = await ready();
    expect(render("overview", s, false, { g: "g1", t: "10" })).toContain('<span class="headline__value">25%</span> of Iloilo City residents can walk to g1 within 10 minutes.');
    expect(render("overview", s, false, { g: "g1", m: "drive", dt: "5" })).toContain('<span class="headline__value">50%</span> of Iloilo City residents can drive to g1 within 5 minutes.');
  });
});

describe("bundle status on Data quality (read from the bundle, never hard-coded)", () => {
  it("shows version, generation time, integrity, audit, code and datasets from the bundle", async () => {
    const s = await ready((d) => {
      for (const doc of ALL_DOCS(d)) doc["generated_utc"] = "2031-02-03T04:05:06+00:00";
    });
    const html = render("quality", s);
    expect(html).toContain("abot-dashboard 1.0.0");
    expect(html).toContain("2031-02-03 04:05 UTC");
    expect(html).toContain("Verified (sizes and SHA-256)");
    expect(html).toContain("Passed with warnings");
    expect(html).toContain("5ed16d2");
    expect(html).toContain("All datasets available");
    // the public pages show only the date the data was prepared
    expect(render("overview", s)).toContain("Data prepared 2031-02-03");
  });
  it("lists the known issues on Data quality, not on the public pages", async () => {
    const s = await ready();
    expect(render("quality", s)).toContain("AUDIT-WARN");
    expect(render("overview", s)).not.toContain("AUDIT-WARN");
  });
  it("gives success tones only to verified, passed, clean states", async () => {
    const b = await bundle();
    const tone = Object.fromEntries(bundleStatusItems(b).map((i) => [i.key, i.tone]));
    expect(tone).toEqual({ contract: "info", generated: "info", integrity: "ok", audit: "warn", git: "warn", datasets: "ok" });
  });
  it("marks unverified integrity as a warning", async () => {
    const s = await ready(undefined, undefined, null);
    const items = s.status === "ready" ? bundleStatusItems(s.bundle) : [];
    expect(items.find((i) => i.key === "integrity")).toMatchObject({ tone: "warn", value: "Not verified (SHA-256 unavailable; sizes checked)" });
    expect(render("quality", s)).toContain("Not verified (SHA-256 unavailable; sizes checked)");
  });
  it("never shows a skipped audit as passed", async () => {
    const skip = { status: "not_run", ran_utc: null, implementation: "x", outcome: null, counts: null, findings: [], reason: "skipped" };
    const s = await ready((d) => {
      for (const doc of ALL_DOCS(d)) doc["data_quality"].source_validation.audit = skip;
    });
    const audit = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "audit") : undefined;
    expect(audit).toMatchObject({ tone: "warn", value: "Audit not run for this bundle" });
    const html = render("quality", s);
    expect(html).toContain("Not run");
    expect(html).not.toContain("Passed");
  });
  it("shows a component-class comparison that was not performed as such, never as passed or failed", async () => {
    const notPerformed = { status: "not_performed", reference: null, components_compared: null, identical: null, reason: "data/archive/ absent" };
    const s = await ready((d) => {
      for (const doc of ALL_DOCS(d)) doc["data_quality"].source_validation.component_classes_check = notPerformed;
    });
    const html = render("quality", s);
    expect(html).toMatch(/Component classes identical to the archived reference<\/span><span class="badge badge--warn"[^>]*>.*?Not performed/);
    expect(html).toContain("data/archive/ absent");
    expect(html).not.toContain("null compared");
    // performed comparisons keep their Yes / No
    const ok = await ready();
    expect(render("quality", ok)).toMatch(/Component classes identical \(3 compared\)<\/span><span class="badge badge--ok"/);
  });
  it("distinguishes unknown Git status from a dirty tree", async () => {
    const s = await ready((d) => (d.manifest["code"] = { git_commit: null, git_working_tree_clean: null, git_dirty_count: null, git_dirty_paths: [], abot_version: "0.1.0" }));
    const git = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "git") : undefined;
    expect(git).toMatchObject({ tone: "unknown", value: "Code version unknown (Git metadata unavailable)" });
  });
  it("tells every page about a newer minor contract version", async () => {
    const s = await ready((d) => {
      for (const doc of ALL_DOCS(d)) doc["contract_version"] = "1.2.0";
    });
    expect(render("overview", s)).toContain("newer version of ABOT");
    expect(s.status === "ready" && bundleStatusItems(s.bundle)[0]!.tone).toBe("warn");
  });
});

describe("interface states", () => {
  it("loading: announces loading and claims nothing as known", () => {
    const html = render("overview", { status: "loading" });
    expect(html).toContain('role="status"');
    expect(html).toContain("Loading the map data");
    expect(shellStatusItems({ status: "loading" })).toEqual([{ key: "datasets", label: "Bundle", value: "Loading…", tone: "unknown" }]);
    expect(html).not.toContain("Verified");
  });
  it("fatal: shows every error and keeps the navigation usable", () => {
    const issues = [
      { level: "error" as const, dataset: "manifest", message: "no bundle: manifest.json not found" },
      { level: "error" as const, dataset: "city", message: "city.walk: unknown indicator id X" },
    ];
    const html = render("barangays", { status: "fatal", issues });
    expect(html).toContain('role="alert"');
    for (const i of issues) expect(html).toContain(i.message);
    expect(html).toContain("abot export-dashboard");
    expect(html).toMatch(/href="#\/barangays" aria-current="page"/);
  });
  it("missing dataset: every page says what is missing, and the map disables the grid", async () => {
    const s = await ready(undefined, (f) => f.delete("cells-002.geojson"));
    const html = render("map", s);
    expect(html).toContain('class="data-alert" role="alert"');
    expect(html).toContain("the detailed 100 m grid on the map");
    expect(html).toMatch(/id="ly-cells" disabled=""/);
    expect(html).toContain("Not available: this data did not load.");
    // the count is on Data quality, and a page that does not need the cells still renders its content
    expect(render("quality", s)).toContain("1 dataset(s) unavailable");
    expect(render("network", s)).toContain("Evidence only.");
  });
  it("missing barangay indicators: the barangay list says so, nothing replaces it", async () => {
    const s = await ready(undefined, (f) => f.delete("barangay_indicators.json"));
    const html = render("barangays", s);
    expect(html).toContain("The barangay list is unavailable");
    expect(html).toContain("barangay_indicators.json");
  });
});

describe("pages render from the fixture bundle", () => {
  it("every page renders one h1 and no broken panel except for parts the fixture lacks", async () => {
    const s = await ready();
    for (const r of ROUTES) expect(render(r.id, s).match(/<h1/g), r.id).toHaveLength(1);
    // the fixture has an envelope-only network: its panels say so instead of failing the page
    expect(render("network", s)).toContain("could not be shown");
  });
  it("shows null as no data, never as zero", async () => {
    const s = await ready();
    // the city A3 mean for g1 is null in the fixture; barangay Two has no values
    expect(render("overview", s, false, { g: "g1", t: "10" })).toContain("Typical walk to the nearest g1: <b>No data</b>");
    const br = render("barangays", s, false, { g: "g1", t: "10" });
    const two = br.slice(br.indexOf(">Two<"));
    expect(two.slice(0, two.indexOf("</tr>"))).toContain("No data");
  });
  it("lists the statements a researcher page used, verbatim from the bundle, once each", async () => {
    const html = render("methods", await ready());
    expect(html).toContain("Notes for this view");
    const footer = html.slice(html.indexOf("Notes for this view"));
    expect(footer).toContain("Fixture text of DQ-A1-OPT (2 of 3 pending).");
    expect(footer.match(/Fixture text of DQ-A1-OPT/g)).toHaveLength(1);
  });
});
