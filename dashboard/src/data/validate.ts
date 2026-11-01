/**
 * Structural and referential checks of a loaded bundle (docs/DASHBOARD_DATA_CONTRACT.md).
 *
 * These checks never recompute an indicator, never aggregate cells and never repair a value: the
 * exporter has already validated the analytical content (§10.2). The frontend only confirms that what
 * it received has the shape, identifiers and references it relies on, and refuses what does not.
 * Each function returns a list of problems; an empty list means the check passed.
 */
import type {
  AuditBlock,
  BarangayIndicators,
  Barangays,
  CatalogEntry,
  CellProps,
  City,
  Facilities,
  Feature,
  Manifest,
  WalkDistribution,
} from "../contract/types.ts";

export function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** A number or null; never NaN, Infinity or a string standing in for a number (§5.1). */
export function isNumberOrNull(v: unknown): v is number | null {
  return v === null || (typeof v === "number" && Number.isFinite(v));
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => deepEqual(x, b[i]));
  }
  if (isObject(a) && isObject(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => Object.hasOwn(b, k) && deepEqual(a[k], b[k]));
  }
  return false;
}

/** Order by Unicode code points, as the exporter sorts cell_id (§7.5). */
export function compareCodePoints(a: string, b: string): number {
  const x = Array.from(a);
  const y = Array.from(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = (x[i] as string).codePointAt(0)! - (y[i] as string).codePointAt(0)!;
    if (d !== 0) return d;
  }
  return x.length - y.length;
}

const ARRAYS = ["files", "indicator_catalog", "statements", "scenarios", "known_issues", "source_files"] as const;

export function validateManifest(m: Record<string, unknown>): string[] {
  const bad: string[] = [];
  for (const k of ARRAYS) if (!Array.isArray(m[k])) bad.push(`manifest.${k} is missing or not an array`);
  const layout = m["cells_layout"];
  if (!isObject(layout) || !Array.isArray(layout["chunks"])) bad.push("manifest.cells_layout is missing");
  if (!isObject(m["data_quality"]) || !isObject((m["data_quality"] as Record<string, unknown>)["source_validation"])) {
    bad.push("manifest.data_quality.source_validation is missing");
  }
  if (bad.length) return bad;
  const man = m as unknown as Manifest;
  const ids = new Set<string>();
  for (const e of man.indicator_catalog) {
    if (ids.has(e.id)) bad.push(`indicator id listed twice in the catalogue: ${e.id}`);
    ids.add(e.id);
    if (!e.unit || !e.role || !Array.isArray(e.levels) || e.levels.length === 0) {
      bad.push(`catalogue entry without unit, role or levels: ${e.id}`);
    }
  }
  const codes = new Set<string>();
  for (const s of man.statements) {
    if (typeof s.code !== "string" || typeof s.text !== "string" || s.text.length === 0) {
      bad.push(`statement without code or text: ${JSON.stringify(s)}`);
    } else if (codes.has(s.code)) bad.push(`statement code listed twice: ${s.code}`);
    codes.add(s.code);
  }
  const fileNames = new Set(man.files.map((f) => f.name));
  if (fileNames.size !== man.files.length) bad.push("manifest.files lists a file twice");
  bad.push(...unresolvedStatements(man.data_quality.statements, codes, "manifest.data_quality"));
  for (const e of man.indicator_catalog) bad.push(...unresolvedStatements(e.statements, codes, `catalogue ${e.id}`));
  bad.push(...validateAudit(man.data_quality.source_validation.audit));
  return bad;
}

/** §6.3: every statement code must resolve to a text in manifest.statements. */
export function unresolvedStatements(used: unknown, known: Set<string>, where: string): string[] {
  if (!Array.isArray(used)) return [`${where}: statements is not an array`];
  return used.filter((c) => typeof c !== "string" || !known.has(c)).map((c) => `${where}: unresolved statement code ${String(c)}`);
}

/** §6.1.1: only obtained/pass, obtained/warn or not_run can be in a written bundle. */
export function validateAudit(a: AuditBlock | undefined): string[] {
  if (!isObject(a)) return ["audit block missing"];
  if (a.status === "obtained") {
    const bad: string[] = [];
    if (a.outcome !== "pass" && a.outcome !== "warn") bad.push(`audit outcome ${String(a.outcome)} cannot be in a bundle`);
    if (a.counts === null || !isObject(a.counts)) bad.push("obtained audit without counts");
    else if (a.counts.warn !== a.findings.length) bad.push("audit warning count differs from its findings");
    return bad;
  }
  if (a.status === "not_run") {
    return a.counts === null && a.outcome === null ? [] : ["audit not_run carries counts or an outcome"];
  }
  return [`audit status ${String(a.status)} cannot be in a bundle`];
}

function checkIds(
  records: { indicator_id: string; value: unknown }[],
  catalog: Map<string, CatalogEntry>,
  level: "city" | "barangay",
  where: string,
): string[] {
  const bad: string[] = [];
  for (const r of records) {
    const e = catalog.get(r.indicator_id);
    if (e === undefined) bad.push(`${where}: unknown indicator id ${r.indicator_id}`);
    else if (!e.levels.includes(level)) bad.push(`${where}: ${r.indicator_id} is not a ${level}-level indicator`);
    if (!isNumberOrNull(r.value)) bad.push(`${where}: ${r.indicator_id} value is not a number or null`);
  }
  return bad;
}

/** §7.2 distribution shape: closed 1-minute bins, one open final bin, a final cumulative point. */
export function validateDistribution(d: WalkDistribution, closedMax: number): string[] {
  const where = `walk_distribution ${d.group}`;
  const bad: string[] = [];
  if (!Array.isArray(d.bins) || d.bins.length !== closedMax + 1) return [`${where}: expected ${closedMax + 1} bins`];
  d.bins.forEach((b, i) => {
    const open = i === closedMax;
    if (b.lower_min !== i || b.upper_min !== (open ? null : i + 1)) bad.push(`${where}: bin ${i + 1} has wrong edges`);
    if (!isNumberOrNull(b.pop) || b.pop === null) bad.push(`${where}: bin ${i + 1} population is not a number`);
  });
  const last = d.bins[closedMax];
  if (last !== undefined && last.pop !== d.pop_open_bin) bad.push(`${where}: open bin differs from pop_open_bin`);
  const cum = d.cumulative;
  if (!Array.isArray(cum) || cum.length !== closedMax + 1) return [...bad, `${where}: expected ${closedMax + 1} cumulative points`];
  cum.forEach((c, i) => {
    const want = i === closedMax ? null : i + 1;
    if (c.minutes !== want) bad.push(`${where}: cumulative point ${i + 1} is not at ${String(want)} min`);
  });
  const final = cum[closedMax];
  const at60 = cum[closedMax - 1];
  if (final !== undefined && at60 !== undefined && final.pct_all_residents < at60.pct_all_residents) {
    bad.push(`${where}: final cumulative point is below the ${closedMax}-minute point`);
  }
  if (final !== undefined && final.pct_all_residents > 100) bad.push(`${where}: final cumulative point above 100 %`);
  return bad;
}

export function validateCity(city: City, catalog: Map<string, CatalogEntry>, closedMax: number): string[] {
  const bad: string[] = [];
  for (const part of ["walk", "walk_internal", "walk_distribution", "drive"] as const) {
    if (!Array.isArray(city[part])) bad.push(`city.${part} is missing`);
  }
  if (!isObject(city.population) || !isObject(city.population.a3)) bad.push("city.population is missing");
  if (bad.length) return bad;
  bad.push(...checkIds(city.walk, catalog, "city", "city.walk"));
  bad.push(...checkIds(city.walk_internal, catalog, "city", "city.walk_internal"));
  bad.push(...checkIds(city.drive, catalog, "city", "city.drive"));
  for (const d of city.walk_distribution) bad.push(...validateDistribution(d, closedMax));
  for (const c of ["network_connected", "locally_connected", "access_uncertain", "unconnected"] as const) {
    const v = city.population.a3[c];
    if (!isObject(v) || !isNumberOrNull(v.pop) || !isNumberOrNull(v.pct)) bad.push(`city.population.a3.${c} is missing`);
  }
  return bad;
}

export function validateIndicators(ind: BarangayIndicators, catalog: Map<string, CatalogEntry>): string[] {
  if (!Array.isArray(ind.barangays)) return ["barangay_indicators.barangays is missing"];
  const want = [...catalog.values()].filter((e) => e.levels.includes("barangay")).map((e) => e.id).sort();
  const bad: string[] = [];
  const seen = new Set<string>();
  for (const r of ind.barangays) {
    if (seen.has(r.adm4_pcode)) bad.push(`barangay listed twice: ${r.adm4_pcode}`);
    seen.add(r.adm4_pcode);
    const keys = Object.keys(r.values).sort();
    const unknown = keys.filter((k) => !catalog.has(k));
    if (unknown.length) bad.push(`${r.adm4_pcode}: unknown indicator ids ${unknown.slice(0, 5).join(", ")}`);
    else if (!deepEqual(keys, want)) bad.push(`${r.adm4_pcode}: values do not hold exactly the barangay-level catalogue ids`);
    for (const [k, v] of Object.entries(r.values)) {
      if (!isNumberOrNull(v)) bad.push(`${r.adm4_pcode}: ${k} is not a number or null`);
    }
  }
  return bad;
}

export function validateBarangays(b: Barangays): string[] {
  if (!Array.isArray(b.features)) return ["barangays.features is missing"];
  const bad: string[] = [];
  const seen = new Set<string>();
  for (const f of b.features) {
    const p = f.properties.adm4_pcode;
    if (seen.has(p)) bad.push(`barangay polygon listed twice: ${p}`);
    seen.add(p);
    if (f.geometry?.type !== "MultiPolygon") bad.push(`${p}: geometry is not a MultiPolygon`);
  }
  return bad;
}

export function validateFacilities(f: Facilities): string[] {
  if (!Array.isArray(f.features)) return ["facilities.features is missing"];
  const bad: string[] = [];
  const seen = new Set<string>();
  for (const x of f.features) {
    const p = x.properties;
    if (seen.has(p.fid_key)) bad.push(`facility listed twice: ${p.fid_key}`);
    seen.add(p.fid_key);
    const c = p.data_quality?.classification;
    if (c === undefined || c.class_status !== p.class_status || c.class_reason !== p.class_reason) {
      bad.push(`${p.fid_key}: data_quality.classification is not an identical copy (§6.2)`);
    }
  }
  return bad;
}

/** Same field set in every cell (§5.2: fields are never omitted). */
export function validateCellFields(features: Feature<CellProps>[]): string[] {
  const first = features[0];
  if (first === undefined) return [];
  const keys = Object.keys(first.properties).join(",");
  const bad = features.filter((f) => Object.keys(f.properties).join(",") !== keys).map((f) => f.properties.cell_id);
  return bad.length ? [`cells with a different field set: ${bad.slice(0, 5).join(", ")}`] : [];
}
