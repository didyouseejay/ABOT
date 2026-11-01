/**
 * The indicator catalogue (manifest.indicator_catalog, §4.1) and the statement texts
 * (manifest.statements, §6.3). Units, roles, denominators and caveats are looked up here, never typed
 * into components; caveat texts come only from manifest.statements.
 */
import type { CatalogEntry, Manifest, Statement } from "../contract/types.ts";

export class Catalog {
  private readonly entries: Map<string, CatalogEntry>;
  private readonly texts: Map<string, Statement>;

  constructor(manifest: Pick<Manifest, "indicator_catalog" | "statements">) {
    this.entries = new Map(manifest.indicator_catalog.map((e) => [e.id, e]));
    this.texts = new Map(manifest.statements.map((s) => [s.code, s]));
  }

  get(id: string): CatalogEntry | undefined {
    return this.entries.get(id);
  }

  /** Throws for an id that is not in the catalogue: an unknown id is a bug, never a silent blank. */
  require(id: string): CatalogEntry {
    const e = this.entries.get(id);
    if (e === undefined) throw new Error(`indicator id not in the catalogue: ${id}`);
    return e;
  }

  idsAt(level: "barangay" | "city"): string[] {
    return [...this.entries.values()].filter((e) => e.levels.includes(level)).map((e) => e.id);
  }

  /** The text of a statement code, exactly as written by the exporter. */
  statement(code: string): string {
    const s = this.texts.get(code);
    if (s === undefined) throw new Error(`statement code not in manifest.statements: ${code}`);
    return s.text;
  }

  /** The caveats an indicator must be shown with, in catalogue order. */
  statementsFor(id: string): Statement[] {
    return this.require(id).statements.map((c) => ({ ...(this.texts.get(c) as Statement), code: c }));
  }

  /** What a value describes: denominator for shares, population for means and counts. */
  describes(id: string): string {
    const e = this.require(id);
    return e.denominator ?? e.population_described ?? "";
  }
}
