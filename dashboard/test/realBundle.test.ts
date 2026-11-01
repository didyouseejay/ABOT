/**
 * Runs the loader against the real bundle written by `abot export-dashboard`, read-only. Skipped when
 * the bundle is absent (data/ is git-ignored). Checks that nothing in the bundle changed.
 */
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { loadBundle } from "../src/data/loadBundle.ts";
import { distributionView } from "../src/model/distribution.ts";
import { ROUTE_IDS } from "../src/routes.ts";
import { BUNDLE_DIR } from "../vite.config.ts";
import { render } from "./render.ts";

const HAVE = existsSync(path.join(BUNDLE_DIR, "manifest.json"));

async function fingerprint() {
  const names = (await readdir(BUNDLE_DIR)).sort();
  return Promise.all(
    names.map(async (n) => {
      const p = path.join(BUNDLE_DIR, n);
      const s = await stat(p);
      return [n, s.size, s.mtimeMs, createHash("sha256").update(await readFile(p)).digest("hex")];
    }),
  );
}

describe.skipIf(!HAVE)("real bundle (read-only)", () => {
  it("loads, verifies and validates without errors and leaves the bundle unchanged", async () => {
    const before = await fingerprint();
    const r = await loadBundle(async (name) => {
      try {
        return new Uint8Array(await readFile(path.join(BUNDLE_DIR, name)));
      } catch {
        return null;
      }
    });
    expect(r.status).toBe("ready");
    if (r.status !== "ready") return;
    const b = r.bundle;
    expect(b.verification).toBe("verified");
    expect(b.compatibility.status).toBe("compatible");
    expect(b.issues.filter((i) => i.level === "error")).toEqual([]);
    for (const st of [b.barangays, b.indicators, b.facilities, b.network, b.provenance, b.cells]) expect(st.status).toBe("ok");
    expect(b.cells.status === "ok" && b.cells.data.length).toBe(b.manifest.cells_layout.features);
    if (b.barangays.status === "ok" && b.indicators.status === "ok") {
      expect(b.indicators.data.barangays.length).toBe(b.barangays.data.features.length);
    }
    // the hospital distribution keeps its > 60 min residents and the final cumulative point
    const hosp = b.city.walk_distribution.find((d) => d.group === "health_hospital");
    if (hosp !== undefined) {
      const v = distributionView(hosp, b.manifest.walk_distribution.closed_max_min);
      expect(v.bars.at(-1)!.open).toBe(true);
      expect(v.bars.at(-1)!.pop).toBe(v.popOpenBin);
      expect(v.final.pct).toBeGreaterThanOrEqual(v.cumulative.at(-1)!.pct);
    }
    // every statement code used anywhere resolves; the audit block is a written-bundle state
    const codes = new Set(b.manifest.statements.map((s) => s.code));
    for (const e of b.manifest.indicator_catalog) for (const c of e.statements) expect(codes.has(c)).toBe(true);
    expect(["obtained", "not_run"]).toContain(b.manifest.data_quality.source_validation.audit.status);
    expect(await fingerprint()).toEqual(before);
  });

  it("renders every page from the real bundle with no broken panel and the exported figures", async () => {
    const r = await loadBundle(async (name) => {
      try {
        return new Uint8Array(await readFile(path.join(BUNDLE_DIR, name)));
      } catch {
        return null;
      }
    });
    if (r.status !== "ready") throw new Error("bundle not ready");
    const state = { status: "ready" as const, bundle: r.bundle };
    for (const route of ROUTE_IDS) {
      const html = render(route, state);
      expect(html, route).not.toContain("could not be shown");
      expect(html, route).not.toContain("is unavailable");
      expect(html.match(/<h1/g), route).toHaveLength(1);
    }
    const ov = render("overview", state);
    const city = r.bundle.city;
    const a3 = city.walk.find((x) => x.indicator_id === "A3.walk.health_primary_care.pct_le15")?.value;
    expect(a3).not.toBeUndefined();
    // the headline is the exported A3 value, rounded for reading
    expect(ov).toContain(`<span class="headline__value">${new Intl.NumberFormat("en-PH", { maximumFractionDigits: 0 }).format(a3 as number)}%</span> of Iloilo City residents can walk to a health center or clinic within 15 minutes.`);
    expect(ov).toContain(new Intl.NumberFormat("en-PH").format(city.population.total));
    // every statement text on a researcher page comes from the bundle verbatim
    const me = render("methods", state);
    for (const s of r.bundle.manifest.statements.filter((x) => me.includes(`id="note-${x.code}"`))) expect(me).toContain(s.text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));
    // ranks only for eligible barangays: ineligible rows are listed in their own unranked group
    const br = render("barangays", state, false, { all: "1" });
    const inel = r.bundle.indicators.status === "ok" ? r.bundle.indicators.data.barangays.filter((x) => !x.data_quality.ranking_eligible).length : -1;
    expect(br.match(/class="not-ranked"/g)?.length ?? 0).toBe(inel);
    if (inel > 0) expect(br).toContain(`Not ranked · limited data (${inel})`);
  });
});
