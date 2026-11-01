/**
 * The application shell rendered to static HTML (react-dom/server; no DOM library) for each bundle
 * state. Checks navigation, active-route marking, landmarks, metadata from the bundle and the states.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AppShell } from "../src/components/layout/AppShell.tsx";
import type { BundleState } from "../src/data/BundleContext.tsx";
import { type LoadedBundle, loadBundle } from "../src/data/loadBundle.ts";
import { bundleStatusItems, shellStatusItems } from "../src/model/shell.ts";
import { isUnknownHash, routeFromHash } from "../src/router.ts";
import { DEFAULT_ROUTE, ROUTES, ROUTE_IDS, routeDef } from "../src/routes.ts";
import { type Docs, fetcherFor, makeDocs, serialize } from "./fixtures/bundle.ts";

async function bundle(edit: (d: Docs) => void = () => {}, after: (f: Map<string, Uint8Array>) => void = () => {}, subtle?: SubtleCrypto | null): Promise<LoadedBundle> {
  const docs = makeDocs();
  edit(docs);
  const files = serialize(docs);
  after(files);
  const r = await loadBundle(fetcherFor(files), subtle === undefined ? {} : { subtle });
  if (r.status !== "ready") throw new Error(JSON.stringify(r.issues));
  return r.bundle;
}

function render(route: string, state: BundleState, navOpen = false): string {
  return renderToStaticMarkup(createElement(AppShell, { route, state, navOpen, onToggleNav: () => {}, onNavigate: () => {} }));
}

const ready = async (...a: Parameters<typeof bundle>): Promise<BundleState> => ({ status: "ready", bundle: await bundle(...a) });

describe("routes", () => {
  it("registers the seven planned sections once each", () => {
    expect(ROUTES.map((r) => r.navLabel)).toEqual([
      "Overview", "Accessibility Map", "Barangay Analysis", "Facilities", "Network Connectivity", "Data Quality", "About / Methodology",
    ]); // prettier-ignore
    expect(new Set(ROUTE_IDS).size).toBe(ROUTES.length);
    expect(DEFAULT_ROUTE).toBe("overview");
  });
  it("resolves hash routes and falls back to the overview", () => {
    for (const id of ROUTE_IDS) expect(routeFromHash(`#/${id}`, ROUTE_IDS, DEFAULT_ROUTE)).toBe(id);
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
  it("route summaries describe planned content and retype no caveat", () => {
    for (const r of ROUTES) expect(r.summary).not.toMatch(/observed|upper bound|optimistic|lower bound/i);
  });
});

describe("shell structure and navigation", () => {
  it("renders landmarks, a skip link and one link per section with the active one marked", async () => {
    const html = render("map", await ready());
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('<nav class="nav" id="primary-navigation" aria-label="Dashboard sections">');
    expect(html).toMatch(/<main class="shell__main" id="main-content" tabindex="-1">/);
    for (const r of ROUTES) expect(html).toContain(`href="#/${r.id}"`);
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
    expect(html).toMatch(/href="#\/map" aria-current="page">Accessibility Map</);
    expect(html).toContain("<h1 id=\"page-title\" tabindex=\"-1\">Accessibility map</h1>");
    expect(html.match(/<h1/g)).toHaveLength(1);
  });
  it("shows the project identity", async () => {
    const html = render("overview", await ready());
    expect(html).toContain("Geospatial Accessibility and Public Infrastructure Intelligence System");
    expect(html).toContain("Bringing essential services within reach.");
    expect(html).toContain("Mapping communities. Measuring accessibility. Informing better infrastructure decisions.");
  });
  it("exposes the drawer state on the menu button", async () => {
    const s = await ready();
    expect(render("overview", s, false)).toMatch(/aria-controls="primary-navigation" aria-expanded="false"/);
    const open = render("overview", s, true);
    expect(open).toMatch(/aria-expanded="true"/);
    expect(open).toContain('data-nav-open="true"');
  });
  it("renders a placeholder for every section, with no values", async () => {
    const s = await ready();
    for (const r of ROUTES) {
      const html = render(r.id, s);
      expect(html).toContain("This page is not built yet");
      expect(html).toContain(r.planned);
      expect(html).not.toContain("Fixture text of"); // no statement or value content on placeholders
    }
  });
});

describe("bundle metadata in the shell (read from the bundle, never hard-coded)", () => {
  it("shows version, generation time, integrity, audit, code and datasets from the bundle", async () => {
    const s = await ready((d) => {
      d.manifest["generated_utc"] = "2031-02-03T04:05:06+00:00";
      for (const doc of [d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["generated_utc"] = "2031-02-03T04:05:06+00:00";
    });
    const html = render("overview", s);
    expect(html).toContain("abot-dashboard 1.0.0");
    expect(html).toContain("2031-02-03 04:05 UTC");
    expect(html).toContain("Verified (sizes and SHA-256)");
    expect(html).toContain("Audit passed with 1 warning(s)");
    expect(html).toContain("Built from a working tree with 2 uncommitted change(s) on top of 5ed16d2");
    expect(html).toContain("All datasets available");
  });
  it("gives success tones only to verified, passed, clean states", async () => {
    const b = await bundle();
    const tone = Object.fromEntries(bundleStatusItems(b).map((i) => [i.key, i.tone]));
    expect(tone).toEqual({ contract: "info", generated: "info", integrity: "ok", audit: "warn", git: "warn", datasets: "ok" });
  });
  it("marks unverified integrity as a warning and states it above the page", async () => {
    const s = await ready(undefined, undefined, null);
    const items = s.status === "ready" ? bundleStatusItems(s.bundle) : [];
    expect(items.find((i) => i.key === "integrity")).toMatchObject({ tone: "warn", value: "Not verified (SHA-256 unavailable; sizes checked)" });
    expect(render("overview", s)).toContain("Integrity not verified");
  });
  it("never shows a skipped audit as passed", async () => {
    const skip = { status: "not_run", ran_utc: null, implementation: "x", outcome: null, counts: null, findings: [], reason: "skipped" };
    const s = await ready((d) => {
      for (const doc of [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["data_quality"].source_validation.audit = skip;
    });
    const audit = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "audit") : undefined;
    expect(audit).toMatchObject({ tone: "warn", value: "Audit not run for this bundle" });
  });
  it("distinguishes unknown Git status from a dirty tree", async () => {
    const s = await ready((d) => (d.manifest["code"] = { git_commit: null, git_working_tree_clean: null, git_dirty_count: null, git_dirty_paths: [], abot_version: "0.1.0" }));
    const git = s.status === "ready" ? bundleStatusItems(s.bundle).find((i) => i.key === "git") : undefined;
    expect(git).toMatchObject({ tone: "unknown", value: "Code version unknown (Git metadata unavailable)" });
  });
  it("warns about a newer minor contract version", async () => {
    const s = await ready((d) => {
      for (const doc of [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) doc["contract_version"] = "1.1.0";
    });
    const html = render("overview", s);
    expect(html).toContain("Newer bundle version");
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
  it("missing dataset: the shell, the notices and the page all say which dataset and why", async () => {
    const s = await ready(undefined, (f) => f.delete("cells-002.geojson"));
    const html = render("map", s);
    expect(html).toContain("1 dataset(s) unavailable");
    expect(html).toContain("Some datasets could not be loaded");
    expect(html).toContain("cells-002.geojson: missing");
    expect(html).toMatch(/Unavailable<\/span><span>Population cells/);
    // a page that does not need the cells still shows its own datasets as loaded
    expect(render("network", s)).toMatch(/Loaded<\/span><span>Network evidence/);
  });
});
