/**
 * The application shell and pages rendered to static HTML (react-dom/server; no DOM library) for each
 * bundle state. Checks the top navigation, active-route marking, landmarks, metadata from the bundle,
 * the notices, the interface states, and that every page renders from the fixture bundle.
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

describe("routes", () => {
  it("registers the seven sections once each, with the three reference sections last", () => {
    expect(ROUTES.map((r) => r.navLabel)).toEqual([
      "Overview", "Accessibility Map", "Barangay Analysis", "Facilities", "Network Connectivity", "Data Quality", "About / Methodology",
    ]); // prettier-ignore
    expect(new Set(ROUTE_IDS).size).toBe(ROUTES.length);
    expect(DEFAULT_ROUTE).toBe("overview");
    expect(ROUTES.filter((r) => r.reference).map((r) => r.id)).toEqual(["network", "quality", "about"]);
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
  it("renders the skip link first, the top bar, one link per section and the main region", async () => {
    const html = render("barangays", await ready());
    expect(html.indexOf('class="skip-link" href="#main-content"')).toBeLessThan(html.indexOf('class="topbar"'));
    expect(html).toContain('<nav class="topnav" aria-label="Main">');
    expect(html).toMatch(/<main class="main" id="main-content" tabindex="-1">/);
    for (const r of ROUTES) expect(html).toContain(`href="#/${r.id}"`);
    expect(html).not.toContain("shell__sidebar");
    // the active section is marked in the tab row and in the small-screen menu panel, nowhere else
    expect(html.match(/aria-current="page"/g)).toHaveLength(2);
    expect(html).toMatch(/class="topnav__link" href="#\/barangays" aria-current="page">Barangay Analysis</);
    expect(html).toContain('<h1 id="page-title" tabindex="-1">Barangay analysis</h1>');
    expect(html.match(/<h1/g)).toHaveLength(1);
  });
  it("marks a reference section in the Reference menu too, and names it on the menu button", async () => {
    const html = render("quality", await ready());
    expect(html.match(/aria-current="page"/g)).toHaveLength(3);
    expect(html).toContain("Reference · Data Quality");
    expect(html).toMatch(/data-active="true"/);
  });
  it("shows the project identity (tagline on the Overview header and in the footer)", async () => {
    const html = render("overview", await ready());
    expect(html).toContain("Geospatial Accessibility and Public Infrastructure Intelligence System");
    expect(html.match(/Bringing essential services within reach\./g)?.length).toBeGreaterThanOrEqual(2);
    expect(html).toContain("Mapping communities. Measuring accessibility. Informing better infrastructure decisions.");
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
    const s = await ready();
    const html = render("overview", s, false, { stat: "mean", sort: "pop" });
    expect(html).toContain('href="#/map?stat=mean"');
    expect(html).not.toContain("sort=pop"); // a page's own parameters stay on that page
  });
});

describe("bundle metadata in the shell (read from the bundle, never hard-coded)", () => {
  it("shows version, generation time, integrity, audit, code and datasets from the bundle", async () => {
    const s = await ready((d) => {
      d.manifest["generated_utc"] = "2031-02-03T04:05:06+00:00";
      for (const doc of [d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["generated_utc"] = "2031-02-03T04:05:06+00:00";
    });
    const html = render("overview", s);
    expect(html).toContain("abot-dashboard v1.0.0");
    expect(html).toContain("2031-02-03 04:05 UTC");
    expect(html).toMatch(/Integrity<\/span><span class="badge badge--ok"[^>]*>.*?Verified/);
    expect(html).toContain("Passed with warnings");
    expect(html).toContain("5ed16d2");
    expect(html).toContain("uncommitted changes");
    expect(html).toContain("8 of 8 loaded");
  });
  it("lists the known issues as collapsed bundle notices", async () => {
    const html = render("overview", await ready());
    expect(html).toContain("2 bundle notices");
    expect(html).toMatch(/<div class="notices" id="notices" hidden="">/);
    expect(html).toContain("AUDIT-WARN");
  });
  it("gives success tones only to verified, passed, clean states", async () => {
    const b = await bundle();
    const tone = Object.fromEntries(bundleStatusItems(b).map((i) => [i.key, i.tone]));
    expect(tone).toEqual({ contract: "info", generated: "info", integrity: "ok", audit: "warn", git: "warn", datasets: "ok" });
  });
  it("marks unverified integrity as a warning and states it in the notices", async () => {
    const s = await ready(undefined, undefined, null);
    const items = s.status === "ready" ? bundleStatusItems(s.bundle) : [];
    expect(items.find((i) => i.key === "integrity")).toMatchObject({ tone: "warn", value: "Not verified (SHA-256 unavailable; sizes checked)" });
    const html = render("overview", s);
    expect(html).toContain("Not verified");
    expect(html).toContain("Integrity not verified");
  });
  it("never shows a skipped audit as passed", async () => {
    const skip = { status: "not_run", ran_utc: null, implementation: "x", outcome: null, counts: null, findings: [], reason: "skipped" };
    const s = await ready((d) => {
      for (const doc of [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["data_quality"].source_validation.audit = skip;
    });
    const audit = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "audit") : undefined;
    expect(audit).toMatchObject({ tone: "warn", value: "Audit not run for this bundle" });
    const html = render("quality", s);
    expect(html).toContain("Not run");
    expect(html).not.toContain("Passed");
  });
  it("distinguishes unknown Git status from a dirty tree", async () => {
    const s = await ready((d) => (d.manifest["code"] = { git_commit: null, git_working_tree_clean: null, git_dirty_count: null, git_dirty_paths: [], abot_version: "0.1.0" }));
    const git = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "git") : undefined;
    expect(git).toMatchObject({ tone: "unknown", value: "Code version unknown (Git metadata unavailable)" });
    expect(render("overview", s)).not.toContain("uncommitted changes");
  });
  it("warns about a newer minor contract version", async () => {
    const s = await ready((d) => {
      for (const doc of [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["contract_version"] = "1.1.0";
    });
    expect(render("overview", s)).toContain("Newer bundle version");
    expect(s.status === "ready" && bundleStatusItems(s.bundle)[0]!.tone).toBe("warn");
  });
});

describe("interface states", () => {
  it("loading: announces loading and claims nothing as known", () => {
    const html = render("overview", { status: "loading" });
    expect(html).toContain('role="status"');
    expect(html).toContain("Loading the dashboard bundle");
    expect(shellStatusItems({ status: "loading" })).toEqual([{ key: "datasets", label: "Bundle", value: "Loading…", tone: "unknown" }]);
    expect(html).not.toContain("Verified");
  });
  it("fatal: shows every error and keeps the navigation usable", () => {
    const issues = [
      { level: "error" as const, dataset: "manifest", message: "no bundle: manifest.json not found" },
      { level: "error" as const, dataset: "city", message: "city.walk: unknown indicator id X" },
    ];
    const html = render("quality", { status: "fatal", issues });
    expect(html).toContain('role="alert"');
    for (const i of issues) expect(html).toContain(i.message);
    expect(html).toContain("abot export-dashboard");
    expect(html).toMatch(/href="#\/quality" aria-current="page"/);
    expect(html).toContain("Not loaded (see the error on this page)");
  });
  it("missing dataset: the shell, the notices and the map all say which dataset and why", async () => {
    const s = await ready(undefined, (f) => f.delete("cells-002.geojson"));
    const html = render("map", s);
    expect(html).toContain("7 of 8 loaded");
    expect(html).toContain("Dataset failed");
    expect(html).toContain("cells-002.geojson: missing");
    expect(html).toMatch(/<div class="notices" id="notices">/); // opened by itself
    expect(html).toContain("Cell layer unavailable: cells dataset failed to load");
    expect(html).toMatch(/id="ly-cells" disabled=""/);
    // a page that does not need the cells still renders its content
    expect(render("network", s)).toContain("Evidence only.");
  });
  it("missing barangay indicators: the barangay table says so, nothing replaces it", async () => {
    const s = await ready(undefined, (f) => f.delete("barangay_indicators.json"));
    const html = render("barangays", s);
    expect(html).toContain("The barangay table is unavailable");
    expect(html).toContain("barangay_indicators.json");
  });
});

describe("pages render from the fixture bundle", () => {
  it("every page renders one h1 and no broken panel except for parts the fixture lacks", async () => {
    const s = await ready();
    for (const r of ROUTES) {
      const html = render(r.id, s);
      expect(html.match(/<h1/g)).toHaveLength(1);
    }
    // the fixture has an envelope-only network: its panels say so instead of failing the page
    expect(render("network", s)).toContain("could not be shown");
  });
  it("shows null as no value, never as zero", async () => {
    const s = await ready();
    const html = render("overview", s, false, { g: "g1", t: "10" });
    // city A3 mean for g1 is null in the fixture
    expect(html).toContain('aria-label="No value: not in the bundle"');
  });
  it("lists the statements a page used, verbatim from the bundle, once each", async () => {
    const html = render("overview", await ready(), false, { g: "g1", t: "10" });
    expect(html).toContain("Notes for this view");
    const footer = html.slice(html.indexOf("Notes for this view"));
    expect(footer).toContain("Fixture text of DQ-SHARE-ALL (2 of 3 pending).");
    expect(footer.match(/Fixture text of DQ-SHARE-ALL/g)).toHaveLength(1);
  });
  it("has no notes footer on the full-bleed map", async () => {
    expect(render("map", await ready())).not.toContain("Notes for this view");
  });
});
