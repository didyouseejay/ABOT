/**
 * TypeScript view of the `abot-dashboard` bundle. The authority is docs/DASHBOARD_DATA_CONTRACT.md;
 * section numbers refer to it. Every field the contract marks nullable is `T | null` here, so code that
 * reads a value has to handle null explicitly (R11: null is never zero).
 */

export type Role = "primary" | "comparative" | "descriptive" | "evidence_only";
export type ScenarioCode = "A1" | "A2" | "A3";
export type Mode = "walk" | "drive" | "mixed" | "none";
export type A3Category = "network_connected" | "locally_connected" | "access_uncertain" | "unconnected";
export type ConnStatus = "connected" | "beyond_tolerance" | "barrier_blocked";
export type DatasetName =
  | "manifest"
  | "city"
  | "barangays"
  | "barangay_indicators"
  | "cells"
  | "facilities"
  | "network"
  | "provenance";

// --- §6.1 data quality ------------------------------------------------------------------------

export interface AuditFinding {
  section: string;
  check: string;
  status: "WARN";
  detail: string;
  action: string;
}

export interface AuditCounts {
  pass: number;
  warn: number;
  fail: number;
  info: number;
}

/** §6.1.1. A written bundle only holds obtained/pass, obtained/warn or not_run. */
export interface AuditBlock {
  status: "obtained" | "not_run" | "error";
  ran_utc: string | null;
  implementation: string;
  outcome: "pass" | "warn" | "fail" | null;
  counts: AuditCounts | null;
  findings: AuditFinding[];
  reason: string | null;
}

export interface SourceValidation {
  audit: AuditBlock;
  a1_reproduces_baseline: boolean;
  baseline_outputs_unchanged: boolean;
  baseline_hashes_match_disk: boolean;
  component_classes_check: { reference: string | null; components_compared: number; identical: boolean };
}

export interface KnownIssue {
  code: string;
  text: string;
  affects: string[];
}

export interface DataQuality {
  role: Role;
  scenario: ScenarioCode | "mixed" | "none";
  mode: Mode;
  analysis_only: boolean;
  source_validation: SourceValidation;
  /** Codes only; texts come from manifest.statements (§6.3). */
  statements: string[];
  known_issues: KnownIssue[];
}

/** §5.3 envelope, present in every file. */
export interface Envelope {
  contract: string;
  contract_version: string;
  dataset: DatasetName;
  generated_utc: string;
  role: Role;
  data_quality: DataQuality;
}

// --- §7.1 manifest ----------------------------------------------------------------------------

export interface ManifestFile {
  name: string;
  sha256: string;
  bytes: number;
  dataset: DatasetName;
}

export interface CellChunkEntry {
  index: number;
  name: string;
  features: number;
  first_cell_id: string;
  last_cell_id: string;
  bytes: number;
  sha256: string;
}

export interface CellsLayout {
  dataset: "cells";
  features: number;
  order: string;
  max_file_bytes: number;
  single_file_bytes: number;
  count: number;
  chunks: CellChunkEntry[];
}

export interface CatalogEntry {
  id: string;
  levels: ("barangay" | "city")[];
  scenario: ScenarioCode;
  mode: "walk" | "drive" | "none";
  group: string | null;
  statistic: string;
  unit: "%" | "minutes" | "residents";
  numerator: string;
  denominator: string | null;
  population_described: string | null;
  role: Role;
  source_file: string;
  source_column: string;
  statements: string[];
}

export interface Statement {
  code: string;
  applies_to: string;
  text: string;
}

export interface Scenario {
  code: ScenarioCode;
  mode: "walk" | "drive";
  role: Role;
  label_key: string | null;
  label: string;
}

export interface Manifest extends Envelope {
  dataset: "manifest";
  files: ManifestFile[];
  cells_layout: CellsLayout;
  source_files: { path: string; sha256: string; bytes: number; mtime_utc: string; used_for: string[] }[];
  code: {
    git_commit: string | null;
    git_working_tree_clean: boolean | null;
    git_dirty_count: number | null;
    git_dirty_paths: string[];
    abot_version: string;
  };
  config_sha256: string;
  stage_completed_utc: Record<string, string>;
  a3_run_info: Record<string, unknown>;
  population_total: number;
  scenarios: Scenario[];
  indicator_groups: { id: string; category: string; subtypes: string[] }[];
  thresholds_min: { walk: number[]; drive: number[] };
  walk_speed_kmh: number;
  drive_access_flag_m: number;
  drive_network_time_factors: number[];
  walk_distribution: { bin_width_min: number; closed_max_min: number };
  indicator_catalog: CatalogEntry[];
  statements: Statement[];
  known_issues: KnownIssue[];
  crs: "EPSG:4326";
}

// --- §7.2 city --------------------------------------------------------------------------------

export interface CityValueRecord {
  indicator_id: string;
  group: string;
  scenario: ScenarioCode;
  statistic: string;
  value: number | null;
  unit: string;
  role: Role;
}

export interface CityInternalRecord {
  indicator_id: string;
  group: string;
  category: "locally_connected" | "access_uncertain";
  threshold_min: number;
  value: number | null;
  unit: "residents";
  role: "evidence_only";
}

export interface DistributionBin {
  lower_min: number;
  /** null only for the open final bin (> closed_max_min). */
  upper_min: number | null;
  pop: number;
}

export interface CumulativePoint {
  /** null only for the final point, which includes the open bin. */
  minutes: number | null;
  pct_all_residents: number;
}

export interface WalkDistribution {
  group: string;
  scenario: "A3";
  bins: DistributionBin[];
  cumulative: CumulativePoint[];
  pop_with_time: number;
  pop_open_bin: number;
  pop_total: number;
}

export interface CityDriveRecord extends CityValueRecord {
  network_time_factor: number;
}

export interface City extends Envelope {
  dataset: "city";
  population: {
    total: number;
    a3: Record<A3Category, { pop: number | null; pct: number | null }>;
    a1: { connected_pop: number | null; connected_pct: number | null; not_connected_pct: number };
  };
  walk: CityValueRecord[];
  walk_internal: CityInternalRecord[];
  walk_distribution: WalkDistribution[];
  drive: CityDriveRecord[];
  facility_inventory: Record<string, string | number | null>[];
}

// --- §7.3 barangays, §7.4 barangay indicators -------------------------------------------------

export interface GeoJSONGeometry {
  type: string;
  coordinates: unknown;
}

export interface Feature<P> {
  type: "Feature";
  geometry: GeoJSONGeometry;
  properties: P;
}

export interface FeatureCollection<P> extends Envelope {
  type: "FeatureCollection";
  features: Feature<P>[];
}

export interface BarangayProps {
  adm4_pcode: string;
  adm4_name: string;
  adm3_pcode: string;
  adm3_name: string;
  area_km2: number;
}

export interface Barangays extends FeatureCollection<BarangayProps> {
  dataset: "barangays";
  simplification: Record<string, unknown>;
}

export interface Reliability {
  level: string;
  reasons: string | null;
}

export interface BarangayRecord {
  adm4_pcode: string;
  adm4_name: string;
  pop_total: number;
  a3_population: Record<A3Category, { pop: number; pct: number }>;
  a1_population: { pop_connected: number; pop_not_connected: number; pct_not_connected: number };
  values: Record<string, number | null>;
  facility_counts: Record<string, number>;
  a1_drive_access: { pop_drive_access_gt_flag: number };
  data_quality: {
    reliability: Record<"population" | "network" | "facility_inventory" | "overall", Reliability>;
    ranking_eligible: boolean;
    indicators_flag_not_connected: boolean;
    resolved_separately: boolean;
    n_facilities_duplicate_review: number;
  };
}

export interface BarangayIndicators extends Envelope {
  dataset: "barangay_indicators";
  barangays: BarangayRecord[];
}

// --- §7.5 cells -------------------------------------------------------------------------------

export interface CellProps {
  cell_id: string;
  pop: number;
  display_adm4_pcode: string;
  a3_category: A3Category;
  a3_conn_status: ConnStatus;
  a3_conn_m: number | null;
  component: string | null;
  component_class: string | null;
  walk_citywide: Record<string, number | null>;
  /** An object only for locally_connected / access_uncertain cells; null for all others. */
  walk_internal: Record<string, number | null> | null;
  a1_conn_status: ConnStatus;
  drive_a1: Record<string, number | null>;
  drive_access_m: number | null;
}

export interface CellChunk extends FeatureCollection<CellProps> {
  dataset: "cells";
  chunk: { index: number; count: number; features: number; first_cell_id: string; last_cell_id: string };
}

// --- §7.6 facilities, §7.7 network, §7.8 provenance (typed loosely until their pages exist) -----

export interface FacilityProps {
  fid_key: string;
  osm_type: "node" | "way" | "relation";
  osm_id: number;
  name: string | null;
  category: string;
  subtype: string;
  tier: string;
  class_status: string;
  class_reason: string;
  geom_source: string;
  inside_city: boolean;
  conn_status: string;
  conn_m: number | null;
  drive_access_m: number | null;
  nearest_edge_m: number | null;
  roles: { category: string; subtype: string; tier: string; status: string; primary: boolean }[];
  indicator_groups: string[];
  destination_groups: string[];
  off_main_network_in: { A1: string | null; A2: string; A3: string } | null;
  data_quality: {
    duplicate_review: {
      review_id: string;
      role: "flagged" | "related";
      other_fid: string;
      review_status: "pending" | "reviewed";
      reviewer_decision: string | null;
    }[];
    classification: { class_status: string; class_reason: string };
  };
}

export interface Facilities extends FeatureCollection<FacilityProps> {
  dataset: "facilities";
}

export interface Network extends Envelope {
  dataset: "network";
  [part: string]: unknown;
}

export interface Provenance extends Envelope {
  dataset: "provenance";
  [part: string]: unknown;
}
