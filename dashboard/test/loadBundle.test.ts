import { describe, expect, it } from "vitest";
import { type LoadResult, loadBundle } from "../src/data/loadBundle.ts";
import { type Docs, fetcherFor, flipByte, makeDocs, serialize } from "./fixtures/bundle.ts";

async function load(edit: (d: Docs) => void = () => {}, after: (f: Map<string, Uint8Array>) => void = () => {}, subtle?: SubtleCrypto | null) {
  const docs = makeDocs();
  edit(docs);
  const files = serialize(docs);
  after(files);
  return loadBundle(fetcherFor(files), subtle === undefined ? {} : { subtle });
}

function ready(r: LoadResult) {
  if (r.status !== "ready") throw new Error(`expected ready, got fatal: ${JSON.stringify(r.issues)}`);
  return r.bundle;
}

function fatalText(r: LoadResult): string {
  expect(r.status).toBe("fatal");
  return r.status === "fatal" ? r.issues.map((i) => i.message).join("\n") : "";
}

function allEnvelopes(d: Docs, f: (e: Record<string, unknown>) => void) {
  for (const doc of [d.manifest, d.city, d.barangays, d.indicators, d.facilities, d.network, d.provenance, ...d.chunks]) f(doc);
}

describe("a valid bundle", () => {
  it("loads completely, verified, with every dataset and the logical cell dataset in order", async () => {
    const b = ready(await load());
    expect(b.verification).toBe("verified");
    expect(b.compatibility.status).toBe("compatible");
    expect(b.issues).toEqual([]);
    for (const st of [b.barangays, b.indicators, b.facilities, b.network, b.provenance, b.cells]) expect(st.status).toBe("ok");
    expect(b.cells.status === "ok" && b.cells.data.map((c) => c.properties.cell_id)).toEqual(["r1c1", "r1c2", "r1c3", "r1c4", "r1c5"]);
  });

  it("passes values through unchanged: null stays null and zero stays zero", async () => {
    const b = ready(await load());
    const cells = b.cells.status === "ok" ? b.cells.data : [];
    const p = (id: string) => cells.find((c) => c.properties.cell_id === id)!.properties;
    expect(p("r1c2").walk_citywide["g1"]).toBe(0);
    expect(p("r1c3").walk_citywide["g1"]).toBeNull();
    expect(p("r1c3").walk_internal).toEqual({ g1: null });
    expect(p("r1c1").walk_internal).toBeNull();
    expect(p("r1c5").drive_a1["g1"]).toBeNull();
    expect(b.city.walk.find((r) => r.statistic === "mean_min")!.value).toBeNull();
    expect(b.city.walk.find((r) => r.scenario === "A1")!.value).toBe(0);
    const ind = b.indicators.status === "ok" ? b.indicators.data.barangays : [];
    expect(ind[1]!.values["A3.walk.g1.pct_le10"]).toBeNull();
    expect(ind[0]!.values["A3.walk.g1.pct_le10"]).toBe(0);
  });
});

describe("contract compatibility (§9.2 condition 4)", () => {
  it("rejects another major version", async () => {
    expect(fatalText(await load((d) => allEnvelopes(d, (e) => (e["contract_version"] = "2.0.0"))))).toMatch(/major version/);
  });
  it("rejects another contract identifier", async () => {
    expect(fatalText(await load((d) => (d.manifest["contract"] = "other-dashboard")))).toMatch(/not an abot-dashboard bundle/);
  });
  it("warns about a newer minor version instead of assuming compatibility", async () => {
    const b = ready(await load((d) => allEnvelopes(d, (e) => (e["contract_version"] = "1.2.0"))));
    expect(b.compatibility.status).toBe("newer_minor");
    expect(b.issues.some((i) => i.level === "warning" && /newer than the supported/.test(i.message))).toBe(true);
  });
  it("reports a missing bundle as fatal", async () => {
    expect(fatalText(await loadBundle(fetcherFor(new Map())))).toMatch(/no bundle/);
  });
});

describe("file verification", () => {
  it("rejects a file whose SHA-256 differs", async () => {
    const r = ready(await load(undefined, (f) => flipByte(f, "facilities.geojson")));
    expect(r.facilities.status === "failed" && r.facilities.reasons.join()).toMatch(/SHA-256/);
  });
  it("shows an explicit verification-unavailable state without Web Crypto, but still checks sizes", async () => {
    const b = ready(await load(undefined, (f) => flipByte(f, "facilities.geojson"), null));
    expect(b.verification).toBe("unavailable");
    expect(b.issues.some((i) => /verification unavailable/.test(i.message))).toBe(true);
    const short = await load(undefined, (f) => f.set("network.json", f.get("network.json")!.slice(0, -2)), null);
    expect(ready(short).network.status).toBe("failed");
  });
  it("rejects a file with another generated_utc", async () => {
    const r = await load((d) => (d.city["generated_utc"] = "2026-11-02T00:00:00+00:00"));
    expect(fatalText(r)).toMatch(/generated_utc/);
  });
  it("rejects a dataset name that differs from manifest.files", async () => {
    const b = ready(await load((d) => (d.network["dataset"] = "provenance")));
    expect(b.network.status === "failed" && b.network.reasons.join()).toMatch(/dataset provenance/);
  });
  it("rejects validation metadata that differs from the manifest", async () => {
    const b = ready(await load((d) => (d.facilities["data_quality"].source_validation.baseline_hashes_match_disk = false)));
    expect(b.facilities.status === "failed" && b.facilities.reasons.join()).toMatch(/source_validation/);
  });
});

describe("cell reconstruction (§7.5.1): complete or disabled, never partial", () => {
  const disabled = async (edit?: (d: Docs) => void, after?: (f: Map<string, Uint8Array>) => void) => {
    const b = ready(await load(edit, after));
    expect(b.cells.status).toBe("failed");
    expect(b.barangays.status).toBe("ok"); // the rest of the dashboard stays usable
    return b.cells.status === "failed" ? b.cells.reasons.join("\n") : "";
  };
  it("disables the cells when a chunk is missing", async () => {
    expect(await disabled(undefined, (f) => f.delete("cells-002.geojson"))).toMatch(/cells-002.geojson: missing/);
  });
  it("disables the cells when a chunk hash is wrong", async () => {
    expect(await disabled(undefined, (f) => flipByte(f, "cells-001.geojson"))).toMatch(/SHA-256/);
  });
  it("disables the cells when the chunk count is wrong", async () => {
    expect(await disabled((d) => (d.manifest["cells_layout"].count = 3))).toMatch(/count/);
  });
  it("disables the cells when the total feature count differs", async () => {
    expect(await disabled((d) => (d.manifest["cells_layout"].features = 6))).toMatch(/5 cells reconstructed/);
  });
  it("disables the cells on a duplicate cell_id", async () => {
    const reasons = await disabled((d) => {
      d.chunks[1]!["features"][1].properties.cell_id = "r1c4";
      d.chunks[1]!["chunk"].last_cell_id = "r1c4";
    });
    expect(reasons).toMatch(/duplicate cell_id r1c4/);
  });
  it("disables the cells when cell_id is not ascending", async () => {
    const reasons = await disabled((d) => {
      const f = d.chunks[0]!["features"];
      [f[0], f[1]] = [f[1], f[0]];
      d.chunks[0]!["chunk"].first_cell_id = "r1c2";
      d.chunks[0]!["chunk"].last_cell_id = "r1c3";
    });
    expect(reasons).toMatch(/not in ascending order/);
  });
  it("disables the cells when a cell omits a field", async () => {
    expect(await disabled((d) => delete d.chunks[1]!["features"][0].properties.drive_access_m)).toMatch(/different field set/);
  });
  it("disables the cells when a chunk's generated_utc differs", async () => {
    expect(await disabled((d) => (d.chunks[1]!["generated_utc"] = "2026-11-02T00:00:00+00:00"))).toMatch(/generated_utc/);
  });
  it("reconstructs in chunk-index order even if the layout lists the chunks out of order", async () => {
    const docs = makeDocs();
    const files = serialize(docs);
    const man = JSON.parse(new TextDecoder().decode(files.get("manifest.json")));
    man.cells_layout.chunks.reverse();
    files.set("manifest.json", new TextEncoder().encode(`${JSON.stringify(man)}\n`));
    const b = ready(await loadBundle(fetcherFor(files)));
    expect(b.cells.status === "ok" && b.cells.data[0]!.properties.cell_id).toBe("r1c1");
  });
});

describe("catalogues (indicator ids, statement codes)", () => {
  it("rejects an unknown indicator id in city.json (fatal)", async () => {
    expect(fatalText(await load((d) => (d.city["walk"][0].indicator_id = "A3.walk.g1.pct_le99")))).toMatch(/unknown indicator id A3.walk.g1.pct_le99/);
  });
  it("rejects a barangay-only id used at city level", async () => {
    const r = await load((d) => {
      d.manifest["indicator_catalog"][0].levels = ["barangay"];
    });
    expect(fatalText(r)).toMatch(/not a city-level indicator/);
  });
  it("rejects an unknown indicator id in barangay values", async () => {
    const b = ready(await load((d) => (d.indicators["barangays"][0].values["A9.walk.g1.x"] = 1)));
    expect(b.indicators.status === "failed" && b.indicators.reasons.join()).toMatch(/unknown indicator ids A9.walk.g1.x/);
  });
  it("rejects a dataset statement code that manifest.statements does not resolve", async () => {
    expect(fatalText(await load((d) => d.city["data_quality"].statements.push("DQ-NOPE")))).toMatch(/unresolved statement code DQ-NOPE/);
    const b = ready(await load((d) => d.chunks[0]!["data_quality"].statements.push("DQ-NOPE")));
    expect(b.cells.status).toBe("failed");
  });
  it("rejects a catalogue statement code that does not resolve", async () => {
    expect(fatalText(await load((d) => d.manifest["indicator_catalog"][1].statements.push("DQ-NOPE")))).toMatch(/catalogue A3.walk.g1.mean_min: unresolved/);
  });
  it("rejects a value that is a string instead of a number or null", async () => {
    expect(fatalText(await load((d) => (d.city["walk"][0].value = "25")))).toMatch(/not a number or null/);
  });
  it("rejects a facility whose classification copy differs (§6.2)", async () => {
    const b = ready(await load((d) => (d.facilities["features"][0].properties.data_quality.classification.class_status = "fallback")));
    expect(b.facilities.status === "failed" && b.facilities.reasons.join()).toMatch(/identical copy/);
  });
});

describe("distribution shape (§7.2)", () => {
  it("rejects a distribution without the open > 60 min bin", async () => {
    expect(fatalText(await load((d) => d.city["walk_distribution"][0].bins.pop()))).toMatch(/expected 61 bins/);
  });
  it("rejects a distribution without the final cumulative point", async () => {
    expect(fatalText(await load((d) => d.city["walk_distribution"][0].cumulative.pop()))).toMatch(/cumulative points/);
  });
  it("rejects a final cumulative point below the 60-minute point", async () => {
    expect(fatalText(await load((d) => (d.city["walk_distribution"][0].cumulative[60].pct_all_residents = 10)))).toMatch(/below the 60-minute point/);
  });
});

describe("audit block (§6.1.1)", () => {
  const withAudit = (audit: Record<string, unknown>) =>
    load((d) => allEnvelopes(d, (e) => ((e["data_quality"] as Record<string, any>)["source_validation"].audit = audit)));
  it("refuses a bundle claiming a failed audit", async () => {
    const r = await withAudit({ status: "obtained", ran_utc: null, implementation: "x", outcome: "fail", counts: { pass: 0, warn: 0, fail: 1, info: 0 }, findings: [], reason: null });
    expect(fatalText(r)).toMatch(/outcome fail cannot be in a bundle/);
  });
  it("accepts not_run, which carries no counts", async () => {
    const b = ready(await withAudit({ status: "not_run", ran_utc: null, implementation: "x", outcome: null, counts: null, findings: [], reason: "skipped" }));
    expect(b.manifest.data_quality.source_validation.audit.status).toBe("not_run");
  });
});
