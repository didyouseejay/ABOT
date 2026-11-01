/**
 * A small hand-made `abot-dashboard` 1.0.0 bundle for unit tests: 1 indicator group, 2 barangays,
 * 5 cells in 2 chunks, 2 facilities. `makeDocs()` returns editable documents; `serialize()` writes
 * them as the exporter does (compact JSON + "\n") and fills manifest.files and cells_layout with the
 * real sizes and SHA-256 of the serialised bytes, so a test can tamper either with the content
 * (re-serialised: hashes stay consistent) or with the bytes afterwards (hashes no longer match).
 */
import { createHash } from "node:crypto";
import type { Fetcher } from "../../src/data/loadBundle.ts";

// Loosely typed on purpose: tests edit these documents freely to build broken bundles.
type Doc = Record<string, any>;

export interface Docs {
  manifest: Doc;
  city: Doc;
  barangays: Doc;
  indicators: Doc;
  facilities: Doc;
  network: Doc;
  provenance: Doc;
  chunks: Doc[];
}

const GEN = "2026-11-01T00:00:00+00:00";
const AUDIT = {
  status: "obtained",
  ran_utc: GEN,
  implementation: "abot.audit.Audit.run(hashes=True), in-process, read-only",
  outcome: "warn",
  counts: { pass: 3, warn: 1, fail: 0, info: 1 },
  findings: [{ section: "validity", check: "possible_duplicates", status: "WARN", detail: "1 pending", action: "review" }],
  reason: null,
};
const SV = {
  audit: AUDIT,
  a1_reproduces_baseline: true,
  baseline_outputs_unchanged: true,
  baseline_hashes_match_disk: true,
  component_classes_check: { reference: null, components_compared: 3, identical: true },
};

function env(dataset: string, role: string, statements: string[] = []) {
  return {
    contract: "abot-dashboard",
    contract_version: "1.0.0",
    dataset,
    generated_utc: GEN,
    role,
    data_quality: { role, scenario: "none", mode: "none", analysis_only: false, source_validation: structuredClone(SV), statements, known_issues: [] },
  };
}

function entry(id: string, levels: string[], unit: string, role: string, statements: string[], extra: Doc = {}) {
  const [scenario, mode] = id.split(".");
  return {
    id, levels, scenario, mode: mode === "population" ? "none" : mode, group: "g1", statistic: id.split(".").at(-1),
    unit, numerator: "residents", denominator: unit === "%" ? "all residents" : null,
    population_described: unit === "%" ? "all residents" : "connected residents with a time",
    role, source_file: "x.csv", source_column: "x", statements, ...extra,
  }; // prettier-ignore
}

const CATALOG = [
  entry("A3.walk.g1.pct_le10", ["barangay", "city"], "%", "primary", ["DQ-SHARE-ALL"]),
  entry("A3.walk.g1.mean_min", ["barangay", "city"], "minutes", "primary", ["DQ-MEAN-CONN"]),
  entry("A1.walk.g1.pct_le10", ["barangay", "city"], "%", "comparative", ["DQ-SHARE-ALL", "DQ-A1-OPT"]),
  entry("A1.drive.g1.pct_le5", ["barangay", "city"], "%", "primary", ["DQ-DRIVE"]),
  entry("A3.walk.g1.local_internal_pop_le10", ["city"], "residents", "evidence_only", ["DQ-LOCAL"]),
];

/** Bins 1..60 plus the open bin; one resident at 5 min, two at 61 min (open bin), one without a time. */
function distribution() {
  const bins = Array.from({ length: 60 }, (_, i) => ({ lower_min: i, upper_min: i + 1, pop: i === 4 ? 1 : 0 }));
  bins.push({ lower_min: 60, upper_min: null as unknown as number, pop: 2 });
  const cumulative = Array.from({ length: 60 }, (_, i) => ({ minutes: i + 1 as number | null, pct_all_residents: i >= 4 ? 25 : 0 }));
  cumulative.push({ minutes: null, pct_all_residents: 75 });
  return { group: "g1", scenario: "A3", bins, cumulative, pop_with_time: 3, pop_open_bin: 2, pop_total: 4 };
}

function cell(id: string, category: string, citywide: number | null, internal: number | null | undefined, drive: number | null) {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [122.55, 10.7] },
    properties: {
      cell_id: id, pop: 1.0, display_adm4_pcode: "PH0603022001", a3_category: category,
      a3_conn_status: category === "unconnected" ? "beyond_tolerance" : "connected",
      a3_conn_m: category === "unconnected" ? null : 10.0, component: category === "unconnected" ? null : "main",
      component_class: category === "unconnected" ? null : "main", walk_citywide: { g1: citywide },
      walk_internal: internal === undefined ? null : { g1: internal }, a1_conn_status: drive === null ? "beyond_tolerance" : "connected",
      drive_a1: { g1: drive }, drive_access_m: drive === null ? null : 50.0,
    },
  }; // prettier-ignore
}

export function makeDocs(): Docs {
  return structuredClone(buildDocs()); // fresh copies: tests tamper with the result
}

function buildDocs(): Docs {
  const values = (v: number | null) => ({
    "A3.walk.g1.pct_le10": v, "A3.walk.g1.mean_min": v === null ? null : 7.5, "A1.walk.g1.pct_le10": v, "A1.drive.g1.pct_le5": 0.0,
  }); // prettier-ignore
  const brgy = (code: string, name: string, v: number | null) => ({
    adm4_pcode: code, adm4_name: name, pop_total: 2.0,
    a3_population: { network_connected: { pop: 1, pct: 50 }, locally_connected: { pop: 1, pct: 50 }, access_uncertain: { pop: 0, pct: 0 }, unconnected: { pop: 0, pct: 0 } },
    a1_population: { pop_connected: 2, pop_not_connected: 0, pct_not_connected: 0 }, values: values(v),
    facility_counts: { n_health: 1 }, a1_drive_access: { pop_drive_access_gt_flag: 0 },
    data_quality: { reliability: {}, ranking_eligible: true, indicators_flag_not_connected: false, resolved_separately: false, n_facilities_duplicate_review: 0 },
  }); // prettier-ignore
  const poly = { type: "MultiPolygon", coordinates: [[[[122.5, 10.7], [122.6, 10.7], [122.6, 10.8], [122.5, 10.7]]]] };
  const fac = (id: string) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [122.55, 10.72] },
    properties: { fid_key: id, class_status: "tag_rule", class_reason: "amenity=clinic",
                  data_quality: { duplicate_review: [], classification: { class_status: "tag_rule", class_reason: "amenity=clinic" } } },
  }); // prettier-ignore
  const chunk = (index: number, features: Doc[]) => ({
    type: "FeatureCollection", ...env("cells", "primary", ["DQ-POP-ALLOC"]),
    chunk: { index, count: 2, features: features.length, first_cell_id: features[0]!.properties.cell_id, last_cell_id: features.at(-1)!.properties.cell_id },
    features,
  }); // prettier-ignore
  return {
    manifest: {
      ...env("manifest", "descriptive"),
      files: [],
      cells_layout: { dataset: "cells", features: 5, order: "cell_id ascending (Unicode code points)", max_file_bytes: 4000000, single_file_bytes: 0, count: 2, chunks: [] },
      source_files: [],
      code: { git_commit: "5ed16d2e9269f4584664fcc7ac93bc066e78d661", git_working_tree_clean: false, git_dirty_count: 2, git_dirty_paths: ["a b.txt", "x.py"], abot_version: "0.1.0" },
      config_sha256: "c".repeat(64),
      stage_completed_utc: {},
      a3_run_info: {},
      population_total: 4.0,
      scenarios: [
        { code: "A3", mode: "walk", role: "primary", label_key: "A3_component_aware", label: "A3 label from the bundle" },
        { code: "A1", mode: "walk", role: "comparative", label_key: "A1_baseline", label: "A1 label from the bundle" },
        { code: "A1", mode: "drive", role: "primary", label_key: null, label: "A1 driving label from the bundle" },
        { code: "A2", mode: "walk", role: "evidence_only", label_key: "A2_all_eligible", label: "A2 label from the bundle" },
      ],
      indicator_groups: [{ id: "g1", category: "health", subtypes: ["clinic"] }],
      thresholds_min: { walk: [10], drive: [5] },
      walk_speed_kmh: 4.5,
      drive_access_flag_m: 500,
      drive_network_time_factors: [1.0, 1.5],
      walk_distribution: { bin_width_min: 1, closed_max_min: 60 },
      indicator_catalog: CATALOG,
      statements: ["DQ-SHARE-ALL", "DQ-MEAN-CONN", "DQ-A1-OPT", "DQ-DRIVE", "DQ-LOCAL", "DQ-POP-ALLOC", "DQ-DIST"].map((code) => ({
        code, applies_to: "fixture", text: `Fixture text of ${code} (2 of 3 pending).`,
      })), // prettier-ignore
      known_issues: [{ code: "AUDIT-WARN", text: "1 warning", affects: ["bundle"] }, { code: "GIT-DIRTY", text: "dirty", affects: ["code"] }],
      crs: "EPSG:4326",
    },
    city: {
      ...env("city", "primary", ["DQ-SHARE-ALL", "DQ-DIST"]),
      population: {
        total: 4.0,
        a3: { network_connected: { pop: 3, pct: 75 }, locally_connected: { pop: 1, pct: 25 }, access_uncertain: { pop: 0, pct: 0 }, unconnected: { pop: 0, pct: 0 } },
        a1: { connected_pop: 4, connected_pct: 100, not_connected_pct: 0 },
      },
      walk: [
        { indicator_id: "A3.walk.g1.pct_le10", group: "g1", scenario: "A3", statistic: "pct_le10", value: 25, unit: "%", role: "primary" },
        { indicator_id: "A3.walk.g1.mean_min", group: "g1", scenario: "A3", statistic: "mean_min", value: null, unit: "minutes", role: "primary" },
        { indicator_id: "A1.walk.g1.pct_le10", group: "g1", scenario: "A1", statistic: "pct_le10", value: 0, unit: "%", role: "comparative" },
      ],
      walk_internal: [
        { indicator_id: "A3.walk.g1.local_internal_pop_le10", group: "g1", category: "locally_connected", threshold_min: 10, value: 0.0, unit: "residents", role: "evidence_only" },
      ],
      walk_distribution: [distribution()],
      drive: [
        { indicator_id: "A1.drive.g1.pct_le5", group: "g1", scenario: "A1", network_time_factor: 1.0, statistic: "pct_le5", value: 50, unit: "%", role: "primary" },
      ],
      facility_inventory: [],
    },
    barangays: {
      type: "FeatureCollection", ...env("barangays", "descriptive"), simplification: {},
      features: [
        { type: "Feature", geometry: poly, properties: { adm4_pcode: "PH0603022001", adm4_name: "One", adm3_pcode: "PH0603022", adm3_name: "Iloilo City", area_km2: 1.5 } },
        { type: "Feature", geometry: poly, properties: { adm4_pcode: "PH0603022002", adm4_name: "Two", adm3_pcode: "PH0603022", adm3_name: "Iloilo City", area_km2: 0.5 } },
      ],
    }, // prettier-ignore
    indicators: { ...env("barangay_indicators", "primary", ["DQ-POP-ALLOC"]), barangays: [brgy("PH0603022001", "One", 0), brgy("PH0603022002", "Two", null)] },
    facilities: { type: "FeatureCollection", ...env("facilities", "descriptive"), features: [fac("node/1"), fac("way/2")] },
    network: { ...env("network", "evidence_only") },
    provenance: { ...env("provenance", "descriptive") },
    chunks: [
      chunk(1, [cell("r1c1", "network_connected", 5.0, undefined, 3.0), cell("r1c2", "network_connected", 0.0, undefined, 0.0),
                cell("r1c3", "locally_connected", null, null, 4.0)]),
      chunk(2, [cell("r1c4", "network_connected", 61.0, undefined, 2.0), cell("r1c5", "unconnected", null, undefined, null)]),
    ], // prettier-ignore
  };
}

const NAMES: [keyof Docs, string, string][] = [
  ["city", "city.json", "city"],
  ["barangays", "barangays.geojson", "barangays"],
  ["indicators", "barangay_indicators.json", "barangay_indicators"],
  ["facilities", "facilities.geojson", "facilities"],
  ["network", "network.json", "network"],
  ["provenance", "provenance.json", "provenance"],
];

const enc = (o: unknown) => new TextEncoder().encode(`${JSON.stringify(o)}\n`);
const sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex");

/** Bundle files keyed by name, with manifest.files and cells_layout computed from the bytes. */
export function serialize(docs: Docs): Map<string, Uint8Array> {
  const out = new Map<string, Uint8Array>();
  const files: Doc[] = [];
  for (const [key, name, dataset] of NAMES) {
    const b = enc(docs[key]);
    out.set(name, b);
    files.push({ name, sha256: sha(b), bytes: b.length, dataset });
  }
  const chunks: Doc[] = [];
  docs.chunks.forEach((c, i) => {
    const name = `cells-${String(i + 1).padStart(3, "0")}.geojson`;
    const b = enc(c);
    out.set(name, b);
    files.push({ name, sha256: sha(b), bytes: b.length, dataset: "cells" });
    chunks.push({ index: c.chunk.index, name, features: c.features.length, first_cell_id: c.chunk.first_cell_id,
                  last_cell_id: c.chunk.last_cell_id, bytes: b.length, sha256: sha(b) }); // prettier-ignore
  });
  const manifest = structuredClone(docs.manifest);
  if (manifest.files.length === 0) manifest.files = files;
  if (manifest.cells_layout.chunks.length === 0) manifest.cells_layout.chunks = chunks;
  out.set("manifest.json", enc(manifest));
  return out;
}

export function fetcherFor(files: Map<string, Uint8Array>): Fetcher {
  return async (name) => files.get(name) ?? null;
}

/** Replace one byte of a file without changing its length (breaks the SHA-256 only). */
export function flipByte(files: Map<string, Uint8Array>, name: string): void {
  const b = new Uint8Array(files.get(name) as Uint8Array);
  const i = b.length - 3;
  b[i] = (b[i] as number) === 0x30 ? 0x31 : 0x30;
  files.set(name, b);
}
