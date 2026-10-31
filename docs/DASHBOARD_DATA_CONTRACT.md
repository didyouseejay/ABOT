# ABOT dashboard data contract — `abot-dashboard v1.0.0`

| | |
|---|---|
| **Contract** | `abot-dashboard`, version **1.0.0** |
| **Date** | 2026-10-31 |
| **Status** | Draft for approval (M05.0). Documentation only: no exporter, bundle or frontend exists yet |
| **Bundle location** | `data/processed/dashboard/v1/` (git-ignored, like all of `data/`) |
| **Producer (future)** | `abot export-dashboard` (M05.1), Python, read-only over the analytical outputs |
| **Consumer (future)** | static React + Vite + Leaflet + Chart.js app (M05.2+), no API or database |
| **Basis** | M05 discovery report (2026-10-31): every source field named below was read from the generated files of commit `56a934c` |

The key words **MUST**, **MUST NOT** and **SHOULD** are normative.

---

## 1. Purpose and scope

The bundle is a **derived, presentation-ready copy** of results that ABOT has already computed and
validated. It reshapes, renames, reprojects, rounds and annotates those results so that a browser can
display them without re-deriving their meaning.

**In scope:** A3 walking indicators, A1 walking comparison, A1 driving indicators, population categories,
facility locations and counts, citywide travel-time distributions, component and gap evidence, access
taxonomy summaries, provenance and data-quality metadata.

**Out of scope for v1:** any new accessibility calculation; per-facility catchments, loads or
capacities; public transport; the routed walk or drive network geometry; geometry for all 112 network
components; experiment runs (`hist_buffer_1km`, `sens_maxspeed_override`, `comparisons/`); manual-review
maps.

---

## 2. Authority rules (normative)

| ID | Rule |
|---|---|
| **R1** | The CSV and GeoPackage outputs in `data/processed/` are **authoritative**. The bundle is derived data only. Where the two disagree, the source is right and the bundle is invalid. |
| **R2** | The exporter **MUST NOT** compute any new accessibility indicator. Allowed operations: selection, renaming, type conversion, reshaping (wide ↔ long), joining on identifiers, reprojection, display simplification of polygons, rounding no finer than the source, and the citywide distribution summaries of R7. |
| **R3** | Barangay **A3** values (population categories, walking indicators, internal-access counts) **MUST** come from `component_aware/barangay_access_a3.csv`. |
| **R4** | Barangay **A1** values (walking comparison, driving indicators, `pop_connected`/`pop_not_connected`, facility counts, reliability fields, census fields) **MUST** come from `barangay_access.csv` (the active A1 baseline, not an experiment folder). |
| **R5** | Barangay population or indicators **MUST NOT** be reconstructed by aggregating `cells_a3.csv` (or any cell layer) by `adm4_pcode`. Barangay values are built from fractional cell pieces (`pop_pieces`); a cell's `adm4_pcode` is only the barangay holding most of the cell. Verified: a cell sum by `adm4_pcode` differs from `pop_total` in 179 of 180 barangays (max 1,070.7 residents). |
| **R6** | Cell data is for **spatial visualisation** and **citywide** travel-time distributions only. |
| **R7** | Citywide statistics derived from cells **MUST** reproduce `component_aware/citywide_a3.csv` exactly (verified possible: 0 mismatches) and keep their original denominators (§4). |
| **R8** | **A3** is the primary walking scenario. **A1** is a comparison scenario: optimistic, **not** an observed result and **not** a guaranteed upper bound. **A2** is comparison-only and not preferred. |
| **R9** | **A1 driving** indicators are a separate mode and scenario. They **MUST NOT** be shown as, mixed with, or compared like A3 walking indicators. |
| **R10** | Local-only (`locally_connected`) and `access_uncertain` populations, and their internal times, **MUST NOT** be merged into citywide (main-network) accessibility. Unconnected residents stay in every "share of all residents" denominator. |
| **R11** | Null stays null. A missing value **MUST NOT** be replaced by `0`, an empty string, or a sentinel number. |
| **R12** | Analysis-only content (access-impact removal scenarios, access-tag classes, candidate corridors) **MUST** carry `analysis_only: true` / `applied: false` and **MUST NOT** be presented as a result of the active model. |
| **R13** | The exporter **MUST NOT** read: `abot_iloilo.gpkg` layers `pop_cells_2026`, `pop_cells_2020`, `access_cells_2026` (legacy Milestone 01/02, 1 km buffer, 7,815 / 7,738 / 7,815 rows); any experiment or comparison folder; any archive. |
| **R14** | The exporter **MUST NOT** write anywhere except `data/processed/dashboard/v1/`, and **MUST NOT** modify any source file. |

---

## 3. Scenarios, populations and roles

### 3.1 Scenarios

| Code | Name (source `scenario_labels`) | Mode | Role in the dashboard |
|---|---|---|---|
| `A3` | A3 component-aware reporting scenario: citywide times only for residents connected to the main network; internal times reported separately | walk | **primary** |
| `A1` | A1 optimistic connectivity scenario (the active baseline): every cell within 250 m of the main network gets citywide times, also through a straight connector past an unlinked fragment. Optimistic, not a verified upper bound | walk | **comparative** |
| `A1` | (same baseline) | drive | **primary for driving, separate mode**: modelled uncongested car travel time, a lower bound, assumes a car |
| `A2` | A2 all eligible components (comparison only; not preferred) | walk | **evidence-only** (Network Connectivity section, approach table) |

The scenario label strings **MUST** be copied from `component_aware/run_info.json` → `scenario_labels`,
not retyped.

### 3.2 Population categories

| Category | Scenario | Meaning | Source |
|---|---|---|---|
| `network_connected` | A3 | cell attached to the main walk network: citywide times | `cells_a3.a3_category`; `barangay_access_a3.pop_/pct_network_connected` |
| `locally_connected` | A3 | attached to an eligible isolated component: internal times only | `…_locally_connected` |
| `access_uncertain` | A3 | attached to an access-uncertain component: internal times reported apart | `…_access_uncertain` |
| `unconnected` | A3 | no acceptable edge within 250 m | `…_unconnected` |
| `connected` / `not_connected` | A1 | A1 connection status (`conn_status == connected`) | `barangay_access.pop_connected`, `pop_not_connected` |

A1 `not_connected` (3,969.1 residents) and A3 `unconnected` (3,472.3) are **different quantities**:
A3 attaches 496.9 A1-unconnected residents to fragments (474.3 locally connected, 22.6 access-uncertain;
`transition_A1_to_A3_pop.csv`). They **MUST NOT** be labelled with the same name.

Cell-level connection status also differs by scenario: `access_cells.conn_status` (A1: connected 7,733,
beyond_tolerance 169, barrier_blocked 133) vs `cells_a3.conn_status` (A3: connected 7,772,
beyond_tolerance 135, barrier_blocked 128). Both are exported under distinct names (§7.5).

### 3.3 Data roles

Every dataset and every indicator carries one `role`:

| Role | Meaning |
|---|---|
| `primary` | the headline result for its mode (A3 walking; A1 driving) |
| `comparative` | shown only next to a primary value (A1 walking) |
| `descriptive` | counts or attributes with no travel-time meaning (facility counts, descriptive facilities, population) |
| `evidence_only` | diagnostic or review material, never a result (A2, component evidence, gap evidence, access taxonomy, access-impact scenarios) |

---

## 4. Indicator semantics (numerators, denominators, populations)

Indicator groups (10, from `config/settings.yaml` → `indicator_groups`): `health_hospital`,
`health_primary_care`, `pharmacy`, `education_basic`, `education_higher`, `safety_police`,
`safety_fire`, `market_public`, `market_supermarket`, `finance_bank`. Thresholds: walk 10, 15, 30
minutes; drive 5, 10, 15 minutes. Walking speed 4.5 km/h. Times are to the **nearest** facility of the
group.

### 4.1 Indicator catalogue

`{g}` = indicator group, `{N}` = threshold. Barangay rows use fractional cell pieces; citywide rows use
all cells.

| Indicator id | Source column(s) | Unit | Numerator | Denominator / population described | Role |
|---|---|---|---|---|---|
| `A3.walk.{g}.pct_le{N}` | `barangay_access_a3.walk_{g}_pct_le{N}`; city `citywide_a3` metric `walk_{g}_pct_le{N}` col `A3` | % (0–100) | residents in `network_connected` cells with citywide time ≤ N | **all residents** of the barangay / city | primary |
| `A3.walk.{g}.mean_min` | `…walk_{g}_mean_min`; city `A3` | minutes | population-weighted mean of citywide time | **network-connected residents with a time** | primary |
| `A3.walk.{g}.p90_min` | `barangay_access_a3.walk_{g}_p90_min` (barangay only) | minutes | population-weighted 90th percentile | **network-connected residents with a time** | primary |
| `A3.walk.{g}.pop_local_internal` | `pop_local_internal_{g}` | residents (count) | residents in `locally_connected` cells with an internal time to a facility in their own component | — (count, not a share) | evidence_only |
| `A3.walk.{g}.pop_local_internal_le15` | `pop_local_internal_{g}_le15` | residents | as above, internal time ≤ 15 | — | evidence_only |
| `A3.walk.{g}.pop_uncertain_internal[_le15]` | `pop_uncertain_internal_{g}[_le15]` | residents | as above for `access_uncertain` cells | — | evidence_only |
| city `A3.walk.{g}.local_internal_pop_le{N}` | `citywide_a3` col `A3_local_internal_pop`, metric `walk_{g}_pct_le{N}` | **residents (count)** | `locally_connected` residents with internal time ≤ N | — | evidence_only |
| city `A3.walk.{g}.uncertain_internal_pop_le{N}` | col `A3_uncertain_internal_pop` | **residents (count)** | `access_uncertain` residents with internal time ≤ N | — | evidence_only |
| `A1.walk.{g}.pct_le{N}` | `barangay_access.walk_{g}_pct_le{N}`; city `citywide_a3` col `A1` | % | A1-connected residents with time ≤ N | **all residents** | comparative |
| `A1.walk.{g}.mean_min`, `p90_min` | `barangay_access.walk_{g}_mean_min`, `_p90_min`; city col `A1` (mean only) | minutes | weighted mean / p90 | **A1-connected residents with a time** | comparative |
| `A1.drive.{g}.pct_le{N}` (N = 5, 10, 15) | `barangay_access.drive_{g}_pct_le{N}`; city `drive_speed_sensitivity` row factor 1.0 | % | A1-connected residents with drive time ≤ N | **all residents** | primary (drive) |
| `A1.drive.{g}.mean_min`, `p90_min` | `barangay_access.drive_{g}_mean_min`, `_p90_min`; city `drive_speed_sensitivity.mean_min` (factor 1.0) | minutes | weighted mean / p90 | **A1-connected residents with a time** | primary (drive) |
| `A1.drive.{g}.sensitivity` | `drive_speed_sensitivity.csv` rows factor 1.0 / 1.5 / 2.0 (`mean_min`, `pct_le5/10/15`, `pct_not_connected`) | min / % | drive-network leg × factor; walking legs unchanged | as above | evidence_only (illustrative) |
| `A3.population.pct_{category}` | `barangay_access_a3.pct_{category}`; city `citywide_a3` metric `pop_{category}` col `A3_pct` | % | residents in the category | **all residents** (the four sum to 100 ± 0.01 per barangay) | primary |
| `A3.population.pop_{category}` | `…pop_{category}`; city col `A3` | residents | — | — | primary |
| `A1.population.pct_not_connected` | `barangay_access.pct_not_connected` | % | A1 not-connected residents | **all residents** | comparative |
| `A1.population.pop_connected` | `barangay_access.pop_connected`; city metric `pop_connected_A1_optimistic` col `A1` / `A1_pct` | residents / % | — | all residents (for the %) | comparative |
| `A1.drive.pop_drive_access_gt_flag` | `barangay_access.pop_drive_access_gt_flag` | residents | residents whose routed walk to the drive network exceeds `drive_access_flag_m` (500 m) | — (count) | evidence_only |

Identity that holds for every share of all residents: `pct_le{N} + pct_gt{N} + pct_not_connected (A1) or
pct of non-network-connected categories (A3) = 100`. The dashboard **MUST NOT** display a "share of
connected residents" unless it is labelled as such and computed only in a documented future contract
version.

### 4.2 Rounding as delivered by the sources (the bundle keeps it)

| Source | Shares | Minutes | Residents |
|---|---|---|---|
| `barangay_access_a3.csv`, `citywide_a3.csv` | 2 decimals | 2 | 1 |
| `barangay_access.csv` (A1) | **1 decimal** | 2 | 1 |
| `drive_speed_sensitivity.csv` | 1 decimal | 2 | — |

An A1–A3 difference at barangay level therefore carries up to ±0.05 pp rounding from the A1 side; the
dashboard **SHOULD** display such deltas to 1 decimal.

### 4.3 Facility counts

| Field | Source | Meaning | Limitation |
|---|---|---|---|
| `n_{category}` (9 categories: pharmacy, health, education, safety, government, market, finance, transport, evacuation) | `barangay_access.csv` | distinct mapped features of the category located in the barangay, inside the city, **any tier** | OSM only; unverified completeness; includes descriptive features |
| `n_{group}` (10 groups) | `barangay_access.csv` | distinct mapped features of the group's category and subtypes located in the barangay, inside the city, **regardless of tier and connection status** (`accessibility.facility_counts`; at discovery every matching role is tier `indicative`) | a facility serves residents of other barangays; facilities in the 3 km buffer are in no barangay but are valid destinations when connected |
| per group: `n_in_city`, `n_in_buffer_outside_city`, `n_destinations_connected`, `n_not_connected_not_used`, `n_unnamed`, `n_not_decided_by_tag_rule`, `n_duplicate_review_pending`, `registry_reference`, `inventory_status`, `note` | `facility_inventory.csv` | citywide inventory per group | `inventory_status = unverified` for all groups |

Facility counts are `descriptive`. They **MUST NOT** be divided by population to form a provision
ratio in v1 (no such indicator exists in the sources).

### 4.4 Analysis-only scenarios

`access_impact.csv` / `access_impact_by_group.csv` describe what **would** happen if edges carrying
certain raw access tags were removed from the A1 network. They were **not applied**. Exported with
`analysis_only: true`, role `evidence_only`; their population fields are counts of residents, and
`pct_le15_*` shares use all residents.

---

## 5. Common conventions

### 5.1 Files and encoding
- UTF-8, no BOM; JSON (RFC 8259) or GeoJSON (RFC 7946). Line endings irrelevant.
- Each file is self-describing (§5.3 envelope).
- Numbers are JSON numbers; no `NaN`, `Infinity` or strings for numbers.

### 5.2 Types used in this contract

`string`, `number` (IEEE double), `integer`, `boolean`, `null`, `enum<…>` (string from a closed set),
`array<T>`, `object`. `T | null` marks a nullable field; any field not marked nullable **MUST** be
present and non-null.

### 5.3 Envelope (every JSON file; GeoJSON as RFC 7946 foreign members)

| Field | Type | Meaning |
|---|---|---|
| `contract` | string | `"abot-dashboard"` |
| `contract_version` | string | `"1.0.0"` |
| `dataset` | enum | `manifest`, `city`, `barangays`, `barangay_indicators`, `cells`, `facilities`, `network`, `provenance` |
| `generated_utc` | string (ISO 8601) | export time, identical across the bundle |
| `role` | enum<§3.3> | dominant role of the dataset |
| `data_quality` | object | dataset-level data-quality block (§6) |

GeoJSON files **MUST NOT** contain the obsolete `crs` member (RFC 7946 §4).

### 5.4 Null semantics (R11)

| Situation | Encoding | Explanation available from |
|---|---|---|
| value not applicable in context (e.g. citywide time for a `locally_connected` cell) | `null` | `a3_category`, `a3_conn_status` |
| no connection | `null` | `a3_conn_status` / `a1_conn_status` ∈ {`beyond_tolerance`, `barrier_blocked`} |
| no internal facility in the cell's component | `null` (internal time) | `component` |
| source free text absent (`rel_population_reasons`, `rel_network_reasons`: "no reason recorded") | `null` | `level` |
| source optional attribute absent (facility `name` 75 missing, `component` 263 missing) | `null` | — |

A count that is genuinely zero in the source (e.g. `pop_local_internal_* = 0.0`) is `0`, not `null`.

### 5.5 Identifiers

| Identifier | Format / example | Cardinality | Joins |
|---|---|---|---|
| `adm4_pcode` | `PH0603022NNN` (`PH0603022001`) | 180, unique | barangay geometry ↔ A3 ↔ A1 ↔ population |
| `cell_id` | string from `access_cells.cell_id` | 8,035, unique | `cells_a3` ↔ `access_cells` |
| `fid_key` | `node/<id>` or `way/<id>` | 937 unique facilities | `facilities` ↔ `facility_roles` ↔ `facilities_by_approach` ↔ duplicate review |
| `fragment` | `main`, `F001` … `F111` | 112 | `component_inventory` ↔ `gap_investigation` ↔ `cells_a3.component` ↔ M03 `network_fragments` (9) |
| indicator id | §4.1 pattern | — | `manifest.indicator_catalog` ↔ `barangay_indicators.values` |

Display values (`adm4_name`, facility `name`, `scenario_label`, `class_reason`) **MUST NOT** be used as
keys.

---

## 6. Data-quality metadata (`data_quality`)

### 6.1 Proposed schema

Each file carries a dataset-level `data_quality` object; selected records carry a record-level one.

```
data_quality (dataset level) = {
  "role":                 enum<primary|comparative|descriptive|evidence_only>,
  "scenario":             enum<A1|A2|A3|none>,
  "mode":                 enum<walk|drive|none>,
  "analysis_only":        boolean,          # true for removal scenarios, access taxonomy, corridors
  "source_validation":    object,           # §6.2
  "statements":           array<string>,    # fixed caveat texts that the UI must show with the data
  "known_issues":         array<object>     # {code: string, text: string, affects: array<string>}
}
```

```
source_validation = {
  "audit_summary":        {pass: integer, warn: integer, fail: integer, info: integer} | null,
  "audit_warnings":       array<string>,    # check names, e.g. "possible_duplicates"
  "a1_reproduces_baseline":      boolean,   # run_info.json
  "baseline_outputs_unchanged":  boolean,   # run_info.json
  "baseline_hashes_match_disk":  boolean,   # exporter re-hash (V-P2)
  "component_classes_check":     {reference: string | null, components_compared: integer, identical: boolean} | null
                                             # review/m04/taxonomy_check.json
}
```

`audit_summary` is `null` unless the exporter runs (or reads a recorded result of) `abot audit`; the
exporter **MUST NOT** invent it. (See unresolved question Q3.)

### 6.2 Record-level blocks

| Where | Field | Type | Source |
|---|---|---|---|
| barangay | `reliability.population` | `{level: enum<ok\|caution\|low>, reasons: string \| null}` | `rel_population`, `rel_population_reasons` |
| barangay | `reliability.network` | same | `rel_network`, `rel_network_reasons` |
| barangay | `reliability.facility_inventory` | `{level: enum<unverified>, reasons: string}` | `rel_facility_inventory`, `_reasons` |
| barangay | `reliability.overall` | `{level, reasons}` | `rel_overall`, `_reasons` (most restrictive of population and network; a rule, not a score) |
| barangay | `ranking_eligible` | boolean | `pop_ranking_eligible` (False when population or network reliability is low: 31 barangays) |
| barangay | `indicators_flag_not_connected` | boolean | A1 `indicators_flag_not_connected` (`pct_not_connected` > 5) |
| barangay | `resolved_separately` | boolean | `barangay_access_a3.resolved_separately` (Calahunan, Hibao-an Sur) |
| barangay | `n_facilities_duplicate_review` | integer | `barangay_access.n_facilities_duplicate_review` |
| facility | `duplicate_review` | `array<{review_id, role: enum<flagged\|related>, other_fid, review_status: enum<pending\|reviewed>, reviewer_decision: string \| null}>` | `review/possible_duplicates_review.csv` (identifiers verified to match `fid_key`) |
| facility | `classification.class_status`, `class_reason` | string | facilities layer |
| cell | `population_allocation` | constant statement only (no per-cell field) | — |

### 6.3 Required statements (exact meaning; wording may be refined at approval)

| Code | Applies to | Statement |
|---|---|---|
| `DQ-SHARE-ALL` | every `pct_le*` | "Share of all residents, including those without a network connection." |
| `DQ-MEAN-CONN` | every `mean_min`, `p90_min` | A3: "Describes residents connected to the main walk network only." A1: "Describes A1-connected residents only." |
| `DQ-A1-OPT` | every A1 walking value | "A1 is an optimistic comparison scenario, not an observed result or a verified upper bound." |
| `DQ-DRIVE` | every drive value | "Modelled uncongested car travel time: a lower bound that assumes car availability; no congestion, parking or turn delays." |
| `DQ-LOCAL` | local / uncertain internal values | "Travel within an isolated network component only; never counted as citywide access." |
| `DQ-FAC-OSM` | facility counts and maps | "Mapped OpenStreetMap features; completeness unverified against official registries." |
| `DQ-DUP` | facilities | "7 of 14 possible duplicate pairs pending review; 2 pairs judged likely duplicates but not merged (both records still counted)." |
| `DQ-POP-ALLOC` | barangay values, cells | "Barangay values use a fractional allocation of 100 m population cells; cell values cannot be summed to barangays." |
| `DQ-RESOLVED` | Calahunan, Hibao-an Sur | "Included in all totals; resolved separately in Milestone 03." |
| `DQ-ANALYSIS-ONLY` | access impact, access taxonomy, corridors | "Analysis only: not applied to the network or to any indicator." |
| `DQ-PHYS-NOT-PUBLIC` | gap evidence | "Physical connection in OSM topology is not public pedestrian access." |
| `DQ-BBOX` | component boxes | "Bounding box of the component's nodes, not its network geometry." |

---

## 7. Datasets

### 7.1 `manifest.json`

**Purpose:** contract identity, provenance of every input, scenario and indicator definitions, and the
data needed to detect a stale bundle. **Role:** descriptive.

| Field | Type | Source / rule |
|---|---|---|
| envelope | §5.3 | — |
| `files` | `array<{name, sha256, bytes, dataset}>` | the other seven bundle files, hashed after writing |
| `source_files` | `array<{path, sha256, bytes, mtime_utc, used_for: array<string>}>` | every file the exporter read (paths relative to the repository root) |
| `code.git_commit` | string \| null | `git rev-parse HEAD` |
| `code.git_working_tree_clean` | boolean \| null | `git status --porcelain` empty (tracked and untracked, excluding ignored) |
| `code.git_dirty_paths` | `array<string>` | paths reported by `git status --porcelain`, at most 50 |
| `code.abot_version` | string | `abot.__version__` (`"0.1.0"` at discovery) |
| `config_sha256` | string | `Settings.config_sha256`; **MUST** equal `run_info.json.config_sha256` and every stage in `data/interim/run_meta.json` |
| `stage_completed_utc` | `{boundaries, population, osm, accessibility, report: string}` | `data/interim/run_meta.json` |
| `a3_run_info` | object | `component_aware/run_info.json` copied verbatim (`created_utc`, `a1_reproduces_baseline`, `baseline_outputs_unchanged`, `baseline_sha256`, `population_total`, `scenario_labels`) |
| `population_total` | number | 457,626.0 at discovery; **MUST** equal `a3_run_info.population_total` |
| `scenarios` | `array<{code, mode, role, label}>` | §3.1; labels from `scenario_labels` |
| `indicator_groups` | `array<{id, category, subtypes: array<string>}>` | `config/settings.yaml` → `indicator_groups` |
| `thresholds_min` | `{walk: array<integer>, drive: array<integer>}` | config → `accessibility.thresholds_min` |
| `walk_speed_kmh` | number | config → `accessibility.walk_speed_kmh` |
| `drive_access_flag_m` | number | config → `accessibility.connection.drive_access_flag_m` |
| `indicator_catalog` | `array<{id, scenario, mode, group \| null, statistic, unit, numerator, denominator, population_described \| null, role, source_file, source_column, statements: array<code>}>` | §4.1, one entry per concrete id |
| `crs` | `"EPSG:4326"` | §8 |

A commit SHA alone **MUST NOT** be presented as proof that the outputs match the repository: the UI
shows `git_working_tree_clean` next to it, and `false` or `null` is displayed as "built from a working
tree with uncommitted changes" / "unknown".

### 7.2 `city.json`

**Purpose:** citywide headline values (Citywide Overview, Travel-Time Analysis, Facility section
summaries). **Role:** primary (with comparative and evidence-only parts flagged per record).

| Part | Structure | Source | Transformation |
|---|---|---|---|
| `population` | `{total, a3: {<category>: {pop, pct}}, a1: {connected_pop, connected_pct}}` | `citywide_a3` metrics `pop_{category}` (`A3`, `A3_pct`), `pop_connected_A1_optimistic` (`A1`, `A1_pct`) | pivot; A1 not-connected is **not** derived here (it is `total − connected`, shown only if labelled A1) |
| `walk` | `array<{indicator_id, group, scenario: A1\|A3, statistic: pct_le10\|pct_le15\|pct_le30\|mean_min, value: number \| null, unit, role}>` | `citywide_a3` cols `A3`, `A1` | long format; one record per (group, statistic, scenario); `unit` % or minutes |
| `walk_internal` | `array<{group, threshold, scenario: "A3", local_internal_pop, uncertain_internal_pop, role: "evidence_only"}>` | `citywide_a3` cols `A3_local_internal_pop`, `A3_uncertain_internal_pop` on `pct_le{N}` metric rows | **unit conversion of meaning:** these columns are resident counts sitting on percentage rows; they are moved to their own records |
| `walk_distribution` | `array<{group, scenario: "A3", bins: array<{upper_min, pop}>, cumulative: array<{minutes, pct_all_residents}>, pop_with_time, pop_total}>` | `cells_a3.t_walk_{g}_citywide`, `pop` | the only computed part (R7): population-weighted histogram over network-connected cells; cumulative share uses **all residents** as denominator; **MUST** reproduce `citywide_a3` at 10/15/30 and the A3 mean exactly. Bin edges: 1-minute bins to the group maximum (Q5) |
| `drive` | `array<{group, network_time_factor, mean_min, pct_le5, pct_le10, pct_le15, pct_not_connected, role}>` | `drive_speed_sensitivity.csv` | factor 1.0 rows role `primary` (A1 drive), 1.5 / 2.0 rows `evidence_only` (illustrative sensitivity) |
| `facility_inventory` | `array<{group, n_in_city, n_in_buffer_outside_city, n_destinations_connected, n_not_connected_not_used, n_unnamed, n_not_decided_by_tag_rule, n_duplicate_review_pending, registry_reference, inventory_status, note}>` | `facility_inventory.csv` | copy |

Denominators per §4.1. CRS: none. Nulls: `citywide_a3` blanks become absent records, never zeros.

**Validation:** `population.total` = Σ A3 category pops (±0.5) = 457,626.0; A3 pct sum 100 ± 0.02;
`walk_distribution` reproduces `citywide_a3` (exact at source rounding); factor-1.0 drive `mean_min`
equals the A1 drive mean recomputed from `access_cells` (Q6).

### 7.3 `barangays.geojson`

**Purpose:** barangay polygons for maps. **Role:** descriptive. **No indicator values** (they live in
`barangay_indicators.json`, joined by `adm4_pcode` in the client).

| Property | Type | Source (`abot_iloilo.gpkg` › `barangays`) |
|---|---|---|
| `adm4_pcode` | string | `adm4_pcode` |
| `adm4_name` | string | `adm4_name` |
| `adm3_pcode`, `adm3_name` | string | same names |
| `area_km2` | number | `area_km2` (computed by ABOT from the EPSG:32651 polygon, the value used in QA). `area_sqkm` (COD-AB attribute, ≤ 0.003 km² different) is **not** exported |
| geometry | MultiPolygon, EPSG:4326 | reprojected from EPSG:32651, then display-simplified (§8.2) |
| foreign member `simplification` | `{method: "shapely simplify, preserve_topology=True", tolerance_deg: number, vertices_before: integer, vertices_after: integer}` | exporter |

**Validation:** 180 features; `adm4_pcode` set equals the A3 and A1 sets; every geometry valid and
non-empty after simplification; area is the unsimplified value.

### 7.4 `barangay_indicators.json`

**Purpose:** all barangay-level values (Barangay Accessibility, Overview map, detail panel). **Role:**
primary (A3), comparative (A1 walk), primary-drive (A1 drive), descriptive (counts), with each value
typed by its catalogue entry.

```
{ envelope,
  "barangays": array<{
     "adm4_pcode": string, "adm4_name": string,
     "pop_total": number,                                   # A3 file; must equal A1 file
     "a3_population": {<category>: {"pop": number, "pct": number}},   # 4 categories
     "a1_population": {"pop_connected": number, "pop_not_connected": number, "pct_not_connected": number},
     "values": {<indicator_id>: number | null},             # §4.1 ids, barangay-level only
     "facility_counts": {"n_<category>": integer, "n_<group>": integer},
     "a1_drive_access": {"pop_drive_access_gt_flag": number},
     "data_quality": {reliability, ranking_eligible, indicators_flag_not_connected,
                      resolved_separately, n_facilities_duplicate_review}     # §6.2
  }> }
```

| Group of fields | Source | Rule |
|---|---|---|
| `adm4_name`, `pop_total`, `a3_population`, `A3.walk.*`, internal counts, `resolved_separately` | `component_aware/barangay_access_a3.csv` | R3 |
| `a1_population`, `A1.walk.*`, `A1.drive.*`, `facility_counts`, `a1_drive_access`, reliability, `ranking_eligible`, `indicators_flag_not_connected`, `n_facilities_duplicate_review` | `barangay_access.csv` | R4 |

Census and WorldPop fields of `barangay_access.csv` (`census_2020`, `pop_wp2020`, `pop_wp2026`,
`pop_census2020_adj`, `census_adj_factor`, …) are **not** exported in v1 (Q7).

**Nulls:** a source blank stays `null` (none at discovery: A3 file has no nulls; A1 file only in the
reasons text). **CRS:** none.

**Validation:** 180 records, unique `adm4_pcode`; Σ A3 category pop = `pop_total` (±0.5) per record;
`pop_total` equal in both sources (±0.05); `values` keys ⊆ catalogue; every `%` in [0, 100]; every
minute ≥ 0; ranking views use `ranking_eligible` only.

### 7.5 `cells.geojson`

**Purpose:** cell map (A3 category, citywide times, drive times) and the source of the citywide
distribution in `city.json`. **Role:** primary (A3 walk, A1 drive) for **visualisation only** (R5, R6).

| Property | Type | Source | Notes |
|---|---|---|---|
| `cell_id` | string | `cells_a3.cell_id` | key |
| `pop` | number | `cells_a3.pop` | residents in the whole cell (all barangays it touches) |
| `display_adm4_pcode` | string | `cells_a3.adm4_pcode` | **renamed**: barangay holding most of the cell; display and filtering only, never aggregation |
| `a3_category` | enum<§3.2> | `cells_a3.a3_category` | |
| `a3_conn_status` | enum<connected\|beyond_tolerance\|barrier_blocked> | `cells_a3.conn_status` | A3 status |
| `a3_conn_m` | number \| null | `cells_a3.conn_m` | null when unconnected |
| `component` | string \| null | `cells_a3.component` | `main`, `Fnnn`; null when unconnected |
| `component_class` | string \| null | `cells_a3.component_class` | |
| `walk_citywide` | `{<group>: number \| null}` | `cells_a3.t_walk_{g}_citywide` | null unless `network_connected` (459 null cells) |
| `walk_internal` | `{<group>: number}` (only groups with a value) | `cells_a3.t_walk_{g}_internal` | present only when not null; `locally_connected` or `access_uncertain` cells |
| `a1_conn_status` | enum (as above) | `access_cells.conn_status` | A1 status (differs from A3) |
| `drive_a1` | `{<group>: number \| null}` | `access_cells.t_drive_{g}` | null when A1-unconnected (302 cells) |
| `drive_access_m` | number \| null | `access_cells.drive_access_m` | routed walk to the drive network |
| geometry | Point, EPSG:4326 | `cells_a3.lon`, `lat` | 6 decimals as in the source |

A1 per-cell **walking** times (`access_cells.t_walk_*`) are not exported in v1 (barangay and citywide A1
comparisons suffice; Q8).

**Validation:** 8,035 features; `cell_id` unique and equal to the `access_cells` set; Σ `pop` =
457,626.0 (±0.5); `walk_citywide` non-null iff `a3_category = network_connected` and a time exists;
`walk_internal` present only for `locally_connected` / `access_uncertain`; `drive_a1` null iff
`a1_conn_status ≠ connected`; coordinates within the study-area bounds; size target ≤ 4 MB (Q9).

### 7.6 `facilities.geojson`

**Purpose:** facility map and facility tables. **Role:** descriptive (locations, counts); facilities of
tier `indicative` are the destinations behind the travel times.

| Property | Type | Source |
|---|---|---|
| `fid_key` | string | facilities layer `fid_key` (937 unique) |
| `osm_type`, `osm_id` | string, integer | facilities layer |
| `name` | string \| null | facilities layer (75 null) |
| `category`, `subtype`, `tier` | string | facilities layer (primary role) |
| `class_status`, `class_reason` | string | facilities layer |
| `geom_source` | enum<node\|representative_point> | facilities layer (`representative_point` for mapped areas) |
| `inside_city` | boolean | facilities layer (134 outside: destinations only if connected) |
| `conn_status` | enum<connected\|beyond_tolerance> | facilities layer (`facilities.csv` lacks it) |
| `conn_m`, `nearest_edge_m`, `drive_access_m` | number \| null | facilities layer |
| `roles` | `array<{category, subtype, tier, status, primary: boolean}>` | `facility_roles` (938 rows; `way/628752365` has two roles: government barangay hall, evacuation centre) |
| `indicator_groups` | `array<string>` | derived: groups whose `category` and `subtypes` match any role (config `indicator_groups`) |
| `destination_groups` | `array<string>` | groups for which a matching role has `tier == "indicative"` **and** the facility `conn_status == "connected"`. Verified at discovery to reproduce `facility_inventory.n_destinations_connected` for all 10 groups. Evaluated per role, not on the primary `tier` |
| `off_main_network_in` | `{A1: string \| null, A2: string, A3: string}` | `review/m04/facilities_by_approach.csv` (25 facilities; `components_*` values); absent otherwise |
| `data_quality.duplicate_review` | §6.2 | `review/possible_duplicates_review.csv` |
| geometry | Point, EPSG:4326 | facilities layer (EPSG:32651) reprojected, 6 decimals |

**Validation:** 937 features, unique `fid_key`; reprojected coordinates equal `facilities.csv`
`lon`/`lat` within 1e-6°; per-group counts of `destination_groups` equal
`facility_inventory.n_destinations_connected`; every duplicate-review id resolves to a feature.

### 7.7 `network.json`

**Purpose:** Network Connectivity section. **Role:** `evidence_only` throughout, except the A1/A3
population transition (primary context).

| Part | Structure | Source | Notes |
|---|---|---|---|
| `approaches` | `array<{approach, scenario_label, role, components_retained, network_km, cells_{category}, pop_{category}}>` | `approach_comparison.csv` rows `group == "_population"` | A2 role `evidence_only` |
| `approaches_by_group` | `array<{approach, group, mean_min, pct_le15_all_residents, pct_le30_all_residents, pop_with_time, pop_local_with_internal_time, pop_local_internal_le15}>` | `approach_comparison.csv` other rows | A2 `mean_min` mixes internal and citywide times (as defined by A2): labelled |
| `transition_a1_to_a3` | `array<{a1_category, a3_category, pop}>` | `transition_A1_to_A3_pop.csv` | long format; blanks are absent pairs, not zero |
| `component_classes` | `array<{component_class, components, length_km, pop_attached_A3}>` | grouped from `component_inventory.csv` | counts and sums of a 112-row table (permitted reshaping) |
| `components` | `array<{fragment, component_class, class_reason, length_km, km_inside_city, n_nodes, n_edges, gap_to_main_m, gap_crosses_water \| null, noexit_at_gap, retained_A2, retained_A3, cells_attached_A3, pop_attached_A3, pop_internal_health_primary_care_reachable, pop_internal_education_basic_reachable, km_<access_status>…, gates_restricted, gates_untagged, bbox: {lon_min, lat_min, lon_max, lat_max}, geometry_kind: "bounding_box"}>` | `component_inventory.csv` | `bbox` from the source `lon_*`/`lat_*` (EPSG:4326, 6 decimals) |
| `fragment_geometries` | GeoJSON FeatureCollection, `geometry_kind: "mapped_fragment_geometry"`, properties `{fragment, n_edges, length_km, gap_to_main_m}` + `gap_line` features (`geometry_kind: "gap_line"`) | `review/m03/validation.gpkg` › `network_fragments` (9, MultiLineString) and `fragment_gaps` (9, LineString), EPSG:32651 → 4326 | only 9 fragments; see §8.4 |
| `gap_evidence` | `array<{fragment, component_class, component_class_changed_by_snapshot, cache_*…, snapshot_physical_connection, snapshot_link_m, snapshot_link_ways, snapshot_link_access_tags, snapshot_link_gates, snapshot_corridor_gates, snapshot_path_access_status, snapshot_public_pedestrian_status, snapshot_authorized_group, snapshot_field_verification_required, remaining_unverified, applied: false}>` | `gap_investigation.csv` (+ `snapshot_corridor_analysis.csv` for `path_ways`, `path_gates`, `classification_reason`) | F001, F100, F101; four access concepts kept in separate fields |
| `access_classification` | `array<{kind, access_class, public_pedestrian_status, treatment, ways, edges, km, km_main, components, cells_attached_A1, pop_attached_A1, nodes, nodes_flag_for_review, nodes_field_verification, nodes_main}>` (nullable per `kind`) | `access_classification_summary.csv` | `analysis_only: true` |
| `access_impact` | `array<{scenario, definition, ways_all_components, km_all_components, edges_removed_main, km_removed_main, pop_lose_network, pop_become_local, pop_become_unconnected, pop_time_up_gt1min, pop_lose_network_focus \| null}>` and `access_impact_by_group` (`scenario, group, pct_le15_baseline, pct_le15_scenario, mean_min_baseline, mean_min_scenario`) | `access_impact.csv`, `access_impact_by_group.csv` | `analysis_only: true`, `applied: false` |

**Validation:** 112 components incl. `main`; class counts match `component_inventory`; the 9 fragment
geometries' `fragment` ids exist in `components` and their `gap_to_main_m` equals the inventory value
(verified at discovery for all 9); `component_classes_check.identical` is true; every
`gap_evidence.applied` and every corridor `applied` is false.

### 7.8 `provenance.json`

**Purpose:** Methodology and Data Provenance section. **Role:** descriptive.

| Part | Fields | Source |
|---|---|---|
| `sources` | `array<{path, url, licence, retrieved_utc, bytes, sha256, source \| null, release \| null, year \| null, hdx_dataset \| null, hdx_last_modified \| null, timestamp_osm_base \| null, overpass_timestamp_osm_base \| null, query_file \| null, query_sha256 \| null, query_label \| null, boundary_buffer_m \| null, used_by_runs \| null}>` | `data/raw/manifest.json` (14 entries; fields vary by source: absent → null) |
| `osm` | `{osmnx_version, overpass_endpoint, boundary_buffer_m, responses: array<{label, cache_file, overpass_timestamp_osm_base, elements, sha256}>}` | `data/interim/osm_provenance.json` |
| `targeted_snapshot` | `{file, sha256, timestamp_osm_base, used_for: "evidence only"}` | manifest entry `osm_targeted/…` |
| `qa` | per stage `{check: {ok: boolean \| null, value, note}}` | `data/interim/qa/{boundaries,population,osm,accessibility}.json` |
| `audit` | `source_validation` object of §6.1 | exporter |
| `limitations` | `array<{code, text}>` | §11 of this contract (fixed text) |
| `documents` | `array<{title, path}>` | `docs/METHODOLOGY.md`, this contract, M04 documents |

---

## 8. Geometry and coordinate reference system

### 8.1 General
- Every bundle geometry and coordinate **MUST** be EPSG:4326 (WGS 84), axis order longitude, latitude
  (RFC 7946). Sources are mixed: barangay polygons, `access_cells`, facilities and M03 fragments are
  EPSG:32651; `cells_a3` (GeoPackage) and all CSV `lon`/`lat` columns are EPSG:4326.
- Reprojection uses GeoPandas/pyproj `to_crs("EPSG:4326")`. Distances and areas are never computed in
  the bundle; they come from the sources (computed in EPSG:32651).
- Coordinates are written with **6 decimals** (≈ 0.11 m), matching the source CSVs.

### 8.2 Barangay polygons
- Reproject first, then simplify for display with topology preserved. At discovery: 16,582 vertices;
  GeoJSON 0.70 MB unsimplified, 0.27 MB at 2e-5° (≈ 2 m), 0.20 MB at 5e-5° (≈ 5.5 m). **Proposed
  tolerance: 2e-5°** (Q1).
- Simplified polygons are for display only; no spatial operation may use them.

### 8.3 Cells and facilities
- Cells are **points** at the cell coordinates of `cells_a3` (the 100 m WorldPop cell is not drawn as a
  square in v1: the grid geometry is not in the A3 outputs).
- Facilities are points from the facilities layer; for mapped areas the point is the
  `representative_point` (`geom_source`), not a centroid of a building outline.

### 8.4 Components: actual geometry vs bounding boxes
- **Actual fragment geometry exists for 9 fragments only** (`review/m03/validation.gpkg` ›
  `network_fragments`, MultiLineString, with `fragment_gaps` lines). These are mapped OSM ways and may be
  drawn as lines with `geometry_kind = "mapped_fragment_geometry"`.
- **No geometry exists for the other 102 non-main components or for the main component.** v1 does not
  generate any (approved decision).
- Every component has a **bounding box** (`component_inventory.lon_min/lat_min/lon_max/lat_max`, the
  extent of its nodes). It **MUST** be exported as a `bbox` attribute with `geometry_kind =
  "bounding_box"` and **MUST NOT** be drawn or described as a road, a network or a coverage area; if
  drawn at all, as a dashed outline with statement `DQ-BBOX`.
- The routed walk and drive networks (`network_walk` 38,864 lines, `network_drive` 20,021) are not in
  the v1 bundle.

---

## 9. Provenance, reproducibility and staleness

### 9.1 What the manifest proves and what it does not
- `source_files[].sha256` proves which bytes were read.
- `config_sha256` proves which configuration produced them (checked against `run_meta.json` and
  `run_info.json`).
- `git_commit` identifies the code version **only if** `git_working_tree_clean` is true. Otherwise the
  bundle states that the outputs may come from uncommitted code; the commit SHA is never shown alone as
  proof.
- `a3_run_info.baseline_sha256` ties the A3 layer to the A1 baseline it was built against.

### 9.2 Stale-bundle detection (future)
A bundle is **stale** when any of the following holds; the future audit check
`dashboard_bundle_current` (and the exporter's own `--check` mode) **MUST** report it:

1. any `source_files[].sha256` differs from the current file on disk, or a listed source is missing;
2. `config_sha256` differs from the current configuration;
3. `run_meta.json` `accessibility.completed_utc` or `component_aware/run_info.json` `created_utc` is newer
   than `generated_utc`;
4. `contract_version` differs from the version the frontend declares it supports (major mismatch →
   refuse to load; minor → warn);
5. any `files[].sha256` differs from the bundle file on disk (bundle edited after export).

The frontend shows `generated_utc`, `git_commit`, `git_working_tree_clean` and the stale status (as
recorded by the last check) in the provenance section.

---

## 10. Exporter validation requirements (M05.1)

The exporter **MUST** stop without writing a partial bundle if any check fails (write to a temporary
directory, validate, then replace `v1/` atomically).

| ID | Check |
|---|---|
| V-S1 | Every required source file exists; the exporter reads no path listed in R13. |
| V-S2 | `run_info.baseline_sha256` equals the SHA-256 of each listed baseline file on disk. |
| V-S3 | `config_sha256` equal across the current config, `run_meta.json` (all stages) and `run_info.json`. |
| V-S4 | `review/m04/taxonomy_check.json` reports `identical: true` for 112 components. |
| V-P1 | Population: Σ `cells_a3.pop` = Σ `barangay_access_a3.pop_total` = Σ `barangay_access.pop_total` = `run_info.population_total` (±0.5). |
| V-P2 | Per barangay: Σ four A3 category pops = `pop_total` (±0.5); A3 and A1 `pop_total` equal (±0.05). |
| V-P3 | A3 `pct_*` categories sum to 100 ± 0.02 per barangay and citywide. |
| V-I1 | `adm4_pcode`: 180 unique, identical sets in geometry, A3, A1. `cell_id`: 8,035 unique, identical in `cells_a3` and `access_cells`. `fid_key`: 937 unique. Components: 112. |
| V-I2 | No join drops or duplicates a record (row counts before and after every join). |
| V-C1 | `city.walk_distribution` reproduces every `citywide_a3` A3 `pct_le{N}` and `mean_min` at source rounding (R7). |
| V-C2 | Every value copied from a source equals the source value (spot check of all rows, all mapped columns). |
| V-N1 | No NaN/Infinity in output; every source null is `null`; no null became `0`. |
| V-N2 | `walk_citywide` non-null only for `network_connected` cells; `walk_internal` only for `locally_connected`/`access_uncertain`; `drive_a1` null iff `a1_conn_status ≠ connected`. |
| V-R1 | Every `%` within [0, 100]; every minute ≥ 0; every count ≥ 0. |
| V-G1 | All geometries valid, non-empty, EPSG:4326, within the study-area bounds (lat 10.6–10.85, lon 122.45–122.7, as used by `fetch/targeted.py`). |
| V-G2 | Facility coordinates equal `facilities.csv` `lon`/`lat` within 1e-6°; cell coordinates equal `cells_a3` `lon`/`lat`. |
| V-G3 | Only 9 features with `geometry_kind = "mapped_fragment_geometry"`; no component box written as a geometry. |
| V-Q1 | Every indicator id used in any file exists in `manifest.indicator_catalog`; every catalogue entry has unit, numerator, denominator or population, role. |
| V-Q2 | Every analysis-only record carries `analysis_only: true` and, where applicable, `applied: false`. |
| V-M1 | `manifest.files` hashes match the written files; `contract_version` = `1.0.0`. |
| V-X1 | After export, the analytical outputs are byte-identical to before (hashes of every source file re-checked). |

---

## 11. Known limitations the dashboard must surface

1. A1 is optimistic and A3 is a reporting scenario: neither is observed travel or a verified bound.
2. A3 is walking only; driving is A1 only, uncongested, a lower bound, assumes a car. No public transport.
3. Facility inventory is OSM, unverified for all 180 barangays; evacuation, transport and government are
   descriptive only; 7 duplicate pairs pending, 2 likely duplicates not merged.
4. Population: census-anchored WorldPop with fractional barangay allocation; `rel_population` low in 27
   and caution in 51 barangays; cells cannot be summed to barangays.
5. 3,472.3 residents unconnected and 5,206.0 locally connected (A3); Calahunan and Hibao-an Sur resolved
   separately.
6. Access tags are reported, not applied; F001, F100, F101 are physically connected in OSM topology but
   mapped `private`, `not_public`, authorised group unspecified, pending field verification.
7. Travel times are to the nearest facility only: no capacity, quality, opening hours or catchment.
8. Component geometry exists for 9 fragments only.

## 12. Indicators not supported (must not appear in v1)

Facility catchment population or load; facilities per capita; travel time to the second-nearest
facility; barangay values at thresholds other than 10/15/30 (walk) and 5/10/15 (drive); barangay
distributions or percentiles other than p90; A2 barangay values; "share of connected residents"
within a threshold; public-transport access; any authorised-user (e.g. F001 resident-egress) scenario.

---

## 13. Unresolved schema questions (for decision before or during M05.1)

| ID | Question | Proposed default |
|---|---|---|
| Q1 | Barangay simplification tolerance | 2e-5° (≈ 2 m; 0.27 MB) |
| Q2 | Should the client receive indicator values keyed by catalogue id (proposed) or as nested objects by scenario/mode/group? | catalogue ids (single semantic registry) |
| Q3 | How the exporter obtains the audit summary: run `abot audit` in-process, read a recorded audit result, or leave `null` | run the audit's checks in-process read-only; if not feasible, `null` with a statement |
| Q5 | Bin width of `walk_distribution` | 1 minute, open last bin labelled "> max" |
| Q6 | A1 citywide drive `mean_min`/`pct_*` exist only in `drive_speed_sensitivity.csv` (factor 1.0); is that the intended citywide A1 drive source? | yes, with V-C2 comparison to `access_cells` |
| Q7 | Export census / WorldPop comparison fields (`census_2020`, `pop_wp2020`, `wp2020_vs_census_pct`, …) for the methodology section? | no in v1 |
| Q8 | Export A1 per-cell walking times for a cell-level A1/A3 comparison map? | no in v1 |
| Q9 | Cell file size: keep all 10 groups in one file (estimated 2–4 MB) or one file per group | one file; revisit if > 4 MB |

Resolved during authoring (read-only checks): `abot.__version__` exists (`0.1.0`); the destination rule
is role-level (§7.6, reproduces the inventory for all 10 groups); `n_{group}` counts any tier (§4.3).

## 14. Versioning

- **Patch** (1.0.x): wording, statements, validation additions; no field change.
- **Minor** (1.x.0): new optional fields or datasets; old clients keep working.
- **Major** (x.0.0): renamed, removed or re-typed fields, or changed meaning of any indicator,
  denominator or null. The bundle directory follows the major version (`v1/`, `v2/`).
