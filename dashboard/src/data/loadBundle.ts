/**
 * Loads and checks an `abot-dashboard` bundle (docs/DASHBOARD_DATA_CONTRACT.md §5.3, §7.1, §7.5.1, §9.2).
 *
 * Order: manifest -> compatibility -> every listed file (size, SHA-256 when Web Crypto is available,
 * envelope) -> cell reconstruction -> structural validation. Values are passed through unchanged:
 * nothing is recomputed, aggregated, rounded or defaulted, and null stays null.
 *
 * A failed manifest or city.json is fatal (nothing can be shown). Any other failed dataset is marked
 * failed with its reasons and the rest of the dashboard stays usable; the cell dataset in particular is
 * either complete or disabled, never partial.
 */
import type {
  BarangayIndicators,
  Barangays,
  CatalogEntry,
  CellChunk,
  CellProps,
  City,
  DatasetName,
  Envelope,
  Facilities,
  Feature,
  Manifest,
  ManifestFile,
  Network,
  Provenance,
} from "../contract/types.ts";
import { type Compatibility, checkCompatibility } from "../contract/version.ts";
import { getSubtle, sha256Hex } from "./sha256.ts";
import {
  compareCodePoints,
  deepEqual,
  isObject,
  unresolvedStatements,
  validateBarangays,
  validateCellFields,
  validateCity,
  validateFacilities,
  validateIndicators,
  validateManifest,
} from "./validate.ts";

/** Returns a bundle file's bytes, or null when it does not exist. May throw on a transport error. */
export type Fetcher = (name: string) => Promise<Uint8Array | null>;

export interface Issue {
  level: "error" | "warning";
  dataset: string;
  message: string;
}

export type DatasetState<T> = { status: "ok"; data: T } | { status: "failed"; reasons: string[] };

/** "verified": every size and SHA-256 checked. "unavailable": sizes checked, hashes could not be. */
export type Verification = "verified" | "unavailable";

export interface LoadedBundle {
  manifest: Manifest;
  compatibility: Compatibility;
  verification: Verification;
  city: City;
  barangays: DatasetState<Barangays>;
  indicators: DatasetState<BarangayIndicators>;
  facilities: DatasetState<Facilities>;
  network: DatasetState<Network>;
  provenance: DatasetState<Provenance>;
  /** The logical cell dataset (all chunks, in order) or the reasons the cell layer is disabled. */
  cells: DatasetState<Feature<CellProps>[]>;
  issues: Issue[];
}

export type LoadResult = { status: "ready"; bundle: LoadedBundle } | { status: "fatal"; issues: Issue[] };

export interface LoadOptions {
  /** Web Crypto implementation; null forces the verification-unavailable path (tests). */
  subtle?: SubtleCrypto | null;
}

const SINGLE: DatasetName[] = ["city", "barangays", "barangay_indicators", "facilities", "network", "provenance"];

type FileResult = { ok: true; doc: Envelope & Record<string, unknown> } | { ok: false; reasons: string[] };

function parseJson(bytes: Uint8Array): unknown {
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

async function fetchSafe(fetcher: Fetcher, name: string): Promise<Uint8Array | null | Error> {
  try {
    return await fetcher(name);
  } catch (e) {
    return e instanceof Error ? e : new Error(String(e));
  }
}

async function loadFile(
  fetcher: Fetcher,
  entry: ManifestFile,
  manifest: Manifest,
  subtle: SubtleCrypto | null,
): Promise<FileResult> {
  const bytes = await fetchSafe(fetcher, entry.name);
  if (bytes instanceof Error) return { ok: false, reasons: [`${entry.name}: could not be read (${bytes.message})`] };
  if (bytes === null) return { ok: false, reasons: [`${entry.name}: missing`] };
  if (bytes.length !== entry.bytes) {
    return { ok: false, reasons: [`${entry.name}: ${bytes.length} bytes, manifest says ${entry.bytes}`] };
  }
  if (subtle !== null && (await sha256Hex(bytes, subtle)) !== entry.sha256) {
    return { ok: false, reasons: [`${entry.name}: SHA-256 differs from manifest.json`] };
  }
  let doc: unknown;
  try {
    doc = parseJson(bytes);
  } catch (e) {
    return { ok: false, reasons: [`${entry.name}: not valid UTF-8 JSON (${(e as Error).message})`] };
  }
  if (!isObject(doc)) return { ok: false, reasons: [`${entry.name}: not a JSON object`] };
  const env = doc as Envelope & Record<string, unknown>;
  const reasons: string[] = [];
  if (env.contract !== manifest.contract) reasons.push(`${entry.name}: contract ${String(env.contract)}`);
  if (env.contract_version !== manifest.contract_version) {
    reasons.push(`${entry.name}: contract_version ${String(env.contract_version)} differs from the manifest`);
  }
  if (env.dataset !== entry.dataset) reasons.push(`${entry.name}: dataset ${String(env.dataset)}, manifest says ${entry.dataset}`);
  if (env.generated_utc !== manifest.generated_utc) {
    reasons.push(`${entry.name}: generated_utc ${String(env.generated_utc)} differs from the manifest (${manifest.generated_utc})`);
  }
  if (!isObject(env.data_quality) || !deepEqual(env.data_quality.source_validation, manifest.data_quality.source_validation)) {
    reasons.push(`${entry.name}: data_quality.source_validation differs from the manifest`);
  }
  return reasons.length ? { ok: false, reasons } : { ok: true, doc: env };
}

/** §7.5.1: rebuild the logical cell dataset; any problem disables it as a whole. */
export function reconstructCells(manifest: Manifest, results: Map<string, FileResult>): DatasetState<Feature<CellProps>[]> {
  const layout = manifest.cells_layout;
  const reasons: string[] = [];
  const chunks = [...layout.chunks].sort((a, b) => a.index - b.index);
  if (layout.count !== chunks.length) reasons.push(`cells_layout.count is ${layout.count} but ${chunks.length} chunks are listed`);
  chunks.forEach((c, i) => {
    if (c.index !== i + 1) reasons.push(`chunk indices are not 1..${chunks.length} (found ${c.index})`);
  });
  const listed = new Map(manifest.files.map((f) => [f.name, f]));
  const cellFiles = manifest.files.filter((f) => f.dataset === "cells").map((f) => f.name);
  const chunkNames = new Set(chunks.map((c) => c.name));
  for (const n of cellFiles) if (!chunkNames.has(n)) reasons.push(`cell file ${n} is not in cells_layout`);
  const parts: Feature<CellProps>[][] = [];
  for (const c of chunks) {
    const entry = listed.get(c.name);
    if (entry === undefined || entry.dataset !== "cells") {
      reasons.push(`chunk ${c.name} is not listed in manifest.files as a cells file`);
      continue;
    }
    if (entry.sha256 !== c.sha256 || entry.bytes !== c.bytes) reasons.push(`chunk ${c.name}: cells_layout and manifest.files disagree`);
    const r = results.get(c.name);
    if (r === undefined) {
      reasons.push(`chunk ${c.name}: not loaded`);
      continue;
    }
    if (!r.ok) {
      reasons.push(...r.reasons);
      continue;
    }
    const doc = r.doc as unknown as CellChunk;
    const ch = doc.chunk;
    if (!isObject(ch) || !Array.isArray(doc.features)) {
      reasons.push(`chunk ${c.name}: no chunk member or features`);
      continue;
    }
    if (ch.index !== c.index || ch.count !== layout.count || ch.features !== c.features) {
      reasons.push(`chunk ${c.name}: chunk member (index ${ch.index}, count ${ch.count}) differs from cells_layout`);
    }
    if (doc.features.length !== c.features) reasons.push(`chunk ${c.name}: ${doc.features.length} features, layout says ${c.features}`);
    const first = doc.features[0]?.properties.cell_id;
    const last = doc.features.at(-1)?.properties.cell_id;
    if (first !== c.first_cell_id || last !== c.last_cell_id || ch.first_cell_id !== c.first_cell_id || ch.last_cell_id !== c.last_cell_id) {
      reasons.push(`chunk ${c.name}: first/last cell_id differ from cells_layout`);
    }
    parts.push(doc.features);
  }
  if (reasons.length) return { status: "failed", reasons };
  const features = parts.flat();
  if (features.length !== layout.features) reasons.push(`${features.length} cells reconstructed, layout says ${layout.features}`);
  const seen = new Set<string>();
  for (let i = 0; i < features.length; i++) {
    const id = (features[i] as Feature<CellProps>).properties.cell_id;
    if (seen.has(id)) reasons.push(`duplicate cell_id ${id}`);
    seen.add(id);
    const prev = features[i - 1];
    if (prev !== undefined && compareCodePoints(prev.properties.cell_id, id) >= 0 && prev.properties.cell_id !== id) {
      reasons.push(`cell_id not in ascending order at ${id}`);
    }
  }
  reasons.push(...validateCellFields(features));
  return reasons.length ? { status: "failed", reasons: reasons.slice(0, 50) } : { status: "ok", data: features };
}

export async function loadBundle(fetcher: Fetcher, options: LoadOptions = {}): Promise<LoadResult> {
  const issues: Issue[] = [];
  const fatal = (message: string, dataset = "manifest"): LoadResult => ({
    status: "fatal",
    issues: [...issues, { level: "error", dataset, message }],
  });

  const mbytes = await fetchSafe(fetcher, "manifest.json");
  if (mbytes instanceof Error) return fatal(`manifest.json could not be read: ${mbytes.message}`);
  if (mbytes === null) return fatal("no bundle: manifest.json not found (run `abot export-dashboard`)");
  let raw: unknown;
  try {
    raw = parseJson(mbytes);
  } catch (e) {
    return fatal(`manifest.json is not valid UTF-8 JSON (${(e as Error).message})`);
  }
  if (!isObject(raw)) return fatal("manifest.json is not a JSON object");
  const compatibility = checkCompatibility(raw["contract"], raw["contract_version"]);
  if (compatibility.status === "incompatible") return fatal(compatibility.message);
  if (compatibility.status === "newer_minor") issues.push({ level: "warning", dataset: "manifest", message: compatibility.message });
  if (raw["dataset"] !== "manifest") return fatal(`manifest.json has dataset ${String(raw["dataset"])}`);
  const mproblems = validateManifest(raw);
  if (mproblems.length) return { status: "fatal", issues: [...issues, ...mproblems.map((m) => ({ level: "error" as const, dataset: "manifest", message: m }))] };
  const manifest = raw as unknown as Manifest;

  const subtle = options.subtle === undefined ? getSubtle() : options.subtle;
  const verification: Verification = subtle === null ? "unavailable" : "verified";
  if (verification === "unavailable") {
    issues.push({
      level: "warning",
      dataset: "manifest",
      message: "SHA-256 verification unavailable (no Web Crypto in this context): file sizes were checked, hashes were not",
    });
  }

  const results = new Map<string, FileResult>();
  await Promise.all(
    manifest.files.map(async (f) => {
      results.set(f.name, await loadFile(fetcher, f, manifest, subtle));
    }),
  );
  for (const f of manifest.files) {
    if (![...SINGLE, "cells"].includes(f.dataset)) issues.push({ level: "warning", dataset: f.dataset, message: `unknown dataset in manifest.files: ${f.name}` });
  }

  const catalog = new Map<string, CatalogEntry>(manifest.indicator_catalog.map((e) => [e.id, e]));
  const codes = new Set(manifest.statements.map((s) => s.code));
  const closedMax = manifest.walk_distribution.closed_max_min;

  const single = <T,>(dataset: DatasetName, check: (doc: T) => string[]): DatasetState<T> => {
    const entries = manifest.files.filter((f) => f.dataset === dataset);
    if (entries.length !== 1) return { status: "failed", reasons: [`manifest.files lists ${entries.length} ${dataset} files, expected 1`] };
    const r = results.get((entries[0] as ManifestFile).name) as FileResult;
    if (!r.ok) return { status: "failed", reasons: r.reasons };
    const reasons = [
      ...unresolvedStatements(r.doc.data_quality.statements, codes, `${dataset}.data_quality`),
      ...check(r.doc as unknown as T),
    ];
    return reasons.length ? { status: "failed", reasons: reasons.slice(0, 50) } : { status: "ok", data: r.doc as unknown as T };
  };

  const city = single<City>("city", (d) => validateCity(d, catalog, closedMax));
  const barangays = single<Barangays>("barangays", validateBarangays);
  let indicators = single<BarangayIndicators>("barangay_indicators", (d) => validateIndicators(d, catalog));
  const facilities = single<Facilities>("facilities", validateFacilities);
  const network = single<Network>("network", () => []);
  const provenance = single<Provenance>("provenance", () => []);

  if (barangays.status === "ok" && indicators.status === "ok") {
    const a = barangays.data.features.map((f) => f.properties.adm4_pcode).sort();
    const b = indicators.data.barangays.map((r) => r.adm4_pcode).sort();
    if (!deepEqual(a, b)) indicators = { status: "failed", reasons: ["barangay codes differ between barangays.geojson and barangay_indicators.json"] };
  }

  let cells = reconstructCells(manifest, results);
  if (cells.status === "ok") {
    for (const name of manifest.cells_layout.chunks.map((c) => c.name)) {
      const r = results.get(name);
      if (r?.ok) {
        const bad = unresolvedStatements(r.doc.data_quality.statements, codes, `${name}.data_quality`);
        if (bad.length) cells = { status: "failed", reasons: bad };
      }
    }
  }

  const named: [string, DatasetState<unknown>][] = [
    ["barangays", barangays],
    ["barangay_indicators", indicators],
    ["facilities", facilities],
    ["network", network],
    ["provenance", provenance],
    ["cells", cells],
  ];
  for (const [dataset, st] of named) {
    if (st.status === "failed") for (const m of st.reasons) issues.push({ level: "error", dataset, message: m });
  }
  if (city.status === "failed") {
    return { status: "fatal", issues: [...issues, ...city.reasons.map((m) => ({ level: "error" as const, dataset: "city", message: m }))] };
  }
  return {
    status: "ready",
    bundle: { manifest, compatibility, verification, city: city.data, barangays, indicators, facilities, network, provenance, cells, issues },
  };
}
