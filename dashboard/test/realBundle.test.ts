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
import { BUNDLE_DIR } from "../vite.config.ts";

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
});
