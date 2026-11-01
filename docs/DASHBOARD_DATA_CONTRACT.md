# ABOT dashboard data contract — `abot-dashboard v1.0.1`

| | |
|---|---|
| **Contract** | `abot-dashboard`, version **1.0.1** (patch of 1.0.0; see §14 Revisions) |
| **Date** | 2026-10-31; final M05.0 review 2026-11-01; 1.0.1 on 2026-11-02 (M06.2A) |
| **Status** | Approved; implemented by `abot export-dashboard` (M05.1). Frontend M05.2 in progress |
| **Bundle location** | `data/processed/dashboard/v1/` (git-ignored, like all of `data/`) |
| **Producer (future)** | `abot export-dashboard` (M05.1), Python, read-only over the analytical outputs |
| **Consumer (future)** | static React + Vite + Leaflet app (M05.2+; Chart.js was planned but not used), no API or database |
| **Basis** | M05 discovery report (2026-10-31): every source field named below was read from the generated files of commit `56a934c`. Final review (2026-11-01, HEAD `5ed16d2`, a documentation-only commit): every count, identity and source path was re-checked read-only against the same outputs and against `src/abot/` (`accessibility.py`, `components.py`, `audit.py`, `cli.py`, `config.py`, `qa.py`, `fetch/targeted.py`) |

The key words **MUST**, **MUST NOT** and **SHOULD** are normative. Figures marked "at discovery" are
the values of the current outputs. They document the contract and are **not** constants for the
exporter, which reads every value from the sources (§6.3).

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
| **R2** | The exporter **MUST NOT** compute any new accessibility indicator. Allowed operations: selection, renaming, type conversion, reshaping (wide ↔ long), joining on identifiers, reprojection, display simplification of barangay polygons (§8.2), rounding no finer than the source, counts and sums over the 112-row component inventory (§7.7 `component_classes`), the citywide distribution summaries of R7 (§7.2), and splitting the cell dataset into physical chunks (§7.5.1). Recomputations used only for validation (V-C1, V-C3) are never exported. |
| **R3** | Barangay **A3** values (population categories, walking indicators, internal-access counts) **MUST** come from `component_aware/barangay_access_a3.csv`. |
| **R4** | Barangay **A1** values (walking comparison, driving indicators, `pop_connected`/`pop_not_connected`, facility counts, reliability fields) **MUST** come from `barangay_access.csv` (the active A1 baseline, not an experiment folder). |
| **R5** | Barangay population or indicators **MUST NOT** be reconstructed by aggregating `cells_a3.csv` (or any cell layer) by `adm4_pcode`. Barangay values are built from fractional cell pieces (`pop_pieces`); a cell's `adm4_pcode` is only the barangay holding most of the cell. Verified: a cell sum by `adm4_pcode` differs from `pop_total` by more than 0.5 residents in all 180 barangays and by more than 1 resident in 179 (max 1,070.7 residents). |
| **R6** | Cell data is for **spatial visualisation** and **citywide** travel-time distributions only. |
| **R7** | Citywide statistics derived from cells **MUST** reproduce `component_aware/citywide_a3.csv` exactly at source rounding (verified possible: 0 mismatches over 30 shares and 10 means, also through the bins of §7.2) and keep their original denominators (§4). |
| **R8** | **A3** is the primary walking scenario. **A1** is a comparison scenario: optimistic, **not** an observed result and **not** a guaranteed upper bound. **A2** is comparison-only and not preferred. |
| **R9** | **A1 driving** indicators are a separate mode and scenario. They **MUST NOT** be shown as, mixed with, or compared like A3 walking indicators. |
| **R10** | Local-only (`locally_connected`) and `access_uncertain` populations, and their internal times, **MUST NOT** be merged into citywide (main-network) accessibility. Unconnected residents stay in every "share of all residents" denominator. |
| **R11** | Null stays null. A missing value **MUST NOT** be replaced by `0`, an empty string, or a sentinel number. |
| **R12** | Analysis-only content (access-impact removal scenarios, access-tag classes, candidate corridors) **MUST** carry `analysis_only: true` / `applied: false` and **MUST NOT** be presented as a result of the active model. |
| **R13** | The exporter's data loading **MUST** read only the source files of §7.1.1 and **MUST NOT** read: `abot_iloilo.gpkg` layers `pop_cells_2026`, `pop_cells_2020`, `access_cells_2026` (legacy Milestone 01/02, 1 km buffer, 7,815 / 7,738 / 7,815 rows); any experiment or comparison folder; any archive. Two clarifications: (a) the `reference` string of `review/m04/taxonomy_check.json` names an archive path; it is copied as text, the archive is not opened; (b) the in-process audit of §6.1.1 is the existing read-only `abot.audit.Audit`, which by design hashes raw and archived files and reads experiment `run_meta.json` files. Its reads are not bundle sources, are not listed in `source_files`, and no bundle value other than the `audit` block comes from them. |
| **R14** | The exporter **MUST NOT** write anywhere except `data/processed/dashboard/` (the bundle `v1/` and its temporary and backup siblings of §10.1), and **MUST NOT** modify any source file. |

---

## 3. Scenarios, populations and roles

### 3.1 Scenarios

| Code | Mode | `scenario_labels` key | Name | Role in the dashboard |
|---|---|---|---|---|
| `A3` | walk | `A3_component_aware` | A3 component-aware reporting scenario: citywide times only for residents connected to the main network; internal times reported separately | **primary** |
| `A1` | walk | `A1_baseline` | A1 optimistic connectivity scenario (the active baseline): every cell within 250 m of the main network gets citywide times, also through a straight connector past an unlinked fragment. Optimistic, not a verified upper bound | **comparative** |
| `A1` | drive | — (no source label) | fixed contract text: "A1 driving: modelled uncongested car travel time from A1-connected cells (a lower bound; assumes a car)" | **primary for driving, separate mode** |
| `A2` | walk | `A2_all_eligible` | A2 all eligible components (comparison only; not preferred) | **evidence-only** (Network Connectivity section, approach table) |

Walking scenario labels **MUST** be copied from `component_aware/run_info.json` → `scenario_labels`
under the key shown, not retyped (they are identical to `approach_comparison.csv` `scenario_label`,
verified). The `A1_baseline` label describes walking connectivity and **MUST NOT** be used as the label
of A1 driving values.

### 3.2 Population categories

| Category | Scenario | Meaning | Source |
|---|---|---|---|
| `network_connected` | A3 | cell attached to the main walk network: citywide times | `cells_a3.a3_category`; `barangay_access_a3.pop_/pct_network_connected` |
| `locally_connected` | A3 | attached to an eligible isolated component: internal times only | `…_locally_connected` |
| `access_uncertain` | A3 | attached to an access-uncertain component: internal times reported apart | `…_access_uncertain` |
| `unconnected` | A3 | no acceptable edge within 250 m | `…_unconnected` |
| `connected` / `not_connected` | A1 | A1 connection status (`conn_status == connected`) | `barangay_access.pop_connected`, `pop_not_connected` |

A1 `not_connected` (3,969.1 residents citywide at discovery) and A3 `unconnected` (3,472.3) are **different quantities**:
A3 attaches 496.9 A1-unconnected residents to fragments (474.3 locally connected, 22.6 access-uncertain;
`review/m04/transition_A1_to_A3_pop.csv`). They **MUST NOT** be labelled with the same name. Citywide
figures come from citywide sources; sums of the 1-decimal barangay columns differ slightly (e.g.
Σ barangay `pop_not_connected` = 3,969.4) and **MUST NOT** be shown as citywide values.

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
| `evidence_only` | diagnostic or review material, never a result (A2, component evidence, gap evidence, access taxonomy, access-impact scenarios, drive-speed sensitivity) |

---

## 4. Indicator semantics (numerators, denominators, populations)

Indicator groups (10, from `config/settings.yaml` → `indicator_groups`): `health_hospital`,
`health_primary_care`, `pharmacy`, `education_basic`, `education_higher`, `safety_police`,
`safety_fire`, `market_public`, `market_supermarket`, `finance_bank`. Thresholds: walk 10, 15, 30
minutes; drive 5, 10, 15 minutes. Walking speed 4.5 km/h. Times are to the **nearest** facility of the
group.

### 4.1 Indicator catalogue

`{g}` = indicator group, `{N}` = threshold, `{category}` = A3 category. **Level** says where an id
occurs: `barangay` (`barangay_indicators.json`) or `city` (`city.json`). An id never changes meaning
between levels; only the population described changes (the barangay or the whole city). Barangay rows
use fractional cell pieces; citywide rows use all cells. The id is exactly the string shown (a "city"
prefix is never part of an id).

| Indicator id | Level | Source column(s) | Unit | Numerator | Denominator / population described | Role |
|---|---|---|---|---|---|---|
| `A3.walk.{g}.pct_le{N}` | barangay, city | `barangay_access_a3.walk_{g}_pct_le{N}`; `citywide_a3` metric `walk_{g}_pct_le{N}` col `A3` | % (0–100) | residents in `network_connected` cells with citywide time ≤ N | **all residents** of the barangay / city | primary |
| `A3.walk.{g}.mean_min` | barangay, city | `…walk_{g}_mean_min`; city col `A3` | minutes | population-weighted mean of citywide time | **network-connected residents with a time** | primary |
| `A3.walk.{g}.p90_min` | barangay | `barangay_access_a3.walk_{g}_p90_min` | minutes | population-weighted 90th percentile | **network-connected residents with a time** | primary |
| `A3.walk.{g}.pop_local_internal` | barangay | `pop_local_internal_{g}` | residents (count) | residents in `locally_connected` cells with an internal time to a facility in their own component | — (count, not a share) | evidence_only |
| `A3.walk.{g}.pop_local_internal_le15` | barangay | `pop_local_internal_{g}_le15` | residents | as above, internal time ≤ 15 | — | evidence_only |
| `A3.walk.{g}.pop_uncertain_internal`, `…_le15` | barangay | `pop_uncertain_internal_{g}`, `…_le15` | residents | as above for `access_uncertain` cells | — | evidence_only |
| `A3.walk.{g}.local_internal_pop_le{N}` | city | `citywide_a3` col `A3_local_internal_pop` on metric row `walk_{g}_pct_le{N}` | **residents (count)** | `locally_connected` residents with internal time ≤ N | — | evidence_only |
| `A3.walk.{g}.uncertain_internal_pop_le{N}` | city | col `A3_uncertain_internal_pop`, same rows | **residents (count)** | `access_uncertain` residents with internal time ≤ N | — | evidence_only |
| `A1.walk.{g}.pct_le{N}` | barangay, city | `barangay_access.walk_{g}_pct_le{N}`; `citywide_a3` col `A1` | % | A1-connected residents with time ≤ N | **all residents** | comparative |
| `A1.walk.{g}.mean_min` | barangay, city | `barangay_access.walk_{g}_mean_min`; city col `A1` | minutes | weighted mean | **A1-connected residents with a time** | comparative |
| `A1.walk.{g}.p90_min` | barangay | `barangay_access.walk_{g}_p90_min` | minutes | weighted p90 | **A1-connected residents with a time** | comparative |
| `A1.drive.{g}.pct_le{N}` (N = 5, 10, 15) | barangay, city | `barangay_access.drive_{g}_pct_le{N}`; city `drive_speed_sensitivity.pct_le{N}`, row `network_time_factor == 1.0` | % | A1-connected residents with drive time ≤ N | **all residents** | primary (drive) |
| `A1.drive.{g}.mean_min` | barangay, city | `barangay_access.drive_{g}_mean_min`; city `drive_speed_sensitivity.mean_min` (factor 1.0) | minutes | weighted mean | **A1-connected residents with a time** | primary (drive) |
| `A1.drive.{g}.p90_min` | barangay | `barangay_access.drive_{g}_p90_min` | minutes | weighted p90 | **A1-connected residents with a time** | primary (drive) |
| `A1.drive_sensitivity.{g}.mean_min`, `….pct_le{N}` | city (records qualified by `network_time_factor` 1.5 or 2.0) | `drive_speed_sensitivity.csv` rows factor 1.5 / 2.0 | minutes / % | drive-network leg × factor; walking legs unchanged | as the corresponding `A1.drive` id | evidence_only (illustrative) |
| `A3.population.pct_{category}` | barangay, city | `barangay_access_a3.pct_{category}`; city `citywide_a3` metric `pop_{category}` col `A3_pct` | % | residents in the category | **all residents** (the four sum to 100 ± 0.02) | primary |
| `A3.population.pop_{category}` | barangay, city | `…pop_{category}`; city col `A3` | residents | — | — | primary |
| `A1.population.pop_connected` | barangay, city | `barangay_access.pop_connected`; city metric `pop_connected_A1_optimistic` col `A1` | residents | — | — | comparative |
| `A1.population.pct_connected` | city | `citywide_a3` metric `pop_connected_A1_optimistic` col `A1_pct` | % | A1-connected residents | **all residents** | comparative |
| `A1.population.pop_not_connected` | barangay | `barangay_access.pop_not_connected` | residents | — | — | comparative |
| `A1.population.pct_not_connected` | barangay, city | `barangay_access.pct_not_connected`; city `drive_speed_sensitivity.pct_not_connected` (identical on every row) | % | A1 not-connected residents | **all residents** | comparative |
| `A1.drive.pop_drive_access_gt_flag` | barangay | `barangay_access.pop_drive_access_gt_flag` | residents | residents whose routed walk to the drive network exceeds `drive_access_flag_m` (500 m) | — (count) | evidence_only |

Identity that holds for every share of all residents (not exported, for reading only): `pct_le{N}` +
share of residents with a time above N + (A1: `pct_not_connected`; A3: the three
non-`network_connected` category shares) = 100, within source rounding. The dashboard **MUST NOT**
display a "share of connected residents" unless it is labelled as such and computed only in a
documented future contract version.

### 4.2 Rounding as delivered by the sources (the bundle keeps it)

| Source | Shares | Minutes | Residents |
|---|---|---|---|
| `barangay_access_a3.csv`, `citywide_a3.csv` | 2 decimals | 2 | 1 |
| `barangay_access.csv` (A1) | **1 decimal** | 2 | 1 |
| `drive_speed_sensitivity.csv` | `pct_le*` 1 decimal; **`pct_not_connected` 2 decimals** | 2 | — |
| `cells_a3.csv`, `access_cells` (cell times) | — | 2 | as source |

An A1–A3 difference at barangay level therefore carries up to about ±0.05 pp rounding from the A1 side;
the dashboard **SHOULD** display such deltas to 1 decimal.

### 4.3 Facility counts

| Field | Source | Meaning | Limitation |
|---|---|---|---|
| `n_{category}` (9 categories: pharmacy, health, education, safety, government, market, finance, transport, evacuation) | `barangay_access.csv` | distinct mapped features with a role of the category located in the barangay, inside the city, **any tier** | OSM only; unverified completeness; includes descriptive features |
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
- UTF-8, no BOM; JSON (RFC 8259) or GeoJSON (RFC 7946).
- Serialisation is deterministic: Python `json.dumps(obj, ensure_ascii=False, allow_nan=False,
  separators=(",", ":"))` followed by one `"\n"`; object keys in the order of this contract's tables;
  arrays ordered as stated per dataset (barangays by `adm4_pcode`, cells by `cell_id`, facilities by
  `fid_key`, components in `component_inventory.csv` row order, long-format records by config group
  order, then scenario, then statistic). Two exports of identical sources differ only in
  `generated_utc`, `code.*` and the `audit` block.
- **Size** means the number of bytes of the file as written (uncompressed UTF-8); `1 MB` = 1,000,000
  bytes. Transport compression (gzip, brotli) is not part of the contract and is never used to meet a
  size limit.
- Each file is self-describing (§5.3 envelope).
- Numbers are JSON numbers; no `NaN`, `Infinity` or strings for numbers.

### 5.2 Types used in this contract

`string`, `number` (IEEE double), `integer`, `boolean`, `null`, `enum<…>` (string from a closed set),
`array<T>`, `object`. `T | null` marks a nullable field; any field not marked nullable **MUST** be
present and non-null. Fields are never omitted to signal "not applicable": that is `null` (§5.4).

### 5.3 Envelope (every JSON file; GeoJSON as RFC 7946 foreign members)

| Field | Type | Meaning |
|---|---|---|
| `contract` | string | `"abot-dashboard"` |
| `contract_version` | string | `"1.0.0"` |
| `dataset` | enum | `manifest`, `city`, `barangays`, `barangay_indicators`, `cells`, `facilities`, `network`, `provenance` (every cell chunk carries `cells`) |
| `generated_utc` | string (ISO 8601) | export time, identical across the bundle |
| `role` | enum<§3.3> | dominant role of the dataset |
| `data_quality` | object | dataset-level data-quality block (§6.1) |

GeoJSON files **MUST NOT** contain the obsolete `crs` member (RFC 7946 §4).

### 5.4 Null semantics (R11)

| Situation | Encoding | Explanation available from |
|---|---|---|
| value not applicable in context (e.g. citywide time for a `locally_connected` cell; `walk_internal` of a `network_connected` cell) | `null` | `a3_category`, `a3_conn_status` |
| no connection (cell `a3_conn_m`, `component`, `component_class`: 263 cells; `drive_a1`, `drive_access_m`: 302 cells; facility `conn_m`, `drive_access_m`: 13) | `null` | `a3_conn_status` / `a1_conn_status` / facility `conn_status` ∈ {`beyond_tolerance`, `barrier_blocked`} |
| no internal facility in the cell's component | `null` (internal time) | `component` |
| barangay statistic absent in the source because the barangay has no connected resident (A1: `accessibility.barangay_indicators` then writes no mean, p90 or share for the group; none at discovery) | `null` | `a1_population`, `a3_population` |
| source free text absent (`rel_population_reasons`, `rel_network_reasons`: "no reason recorded") | `null` | `level` |
| source optional attribute absent (facility `name`: 75; `components_A1_baseline`: 13; `gap_crosses_water`: 102) | `null` | — |

A count that is genuinely zero in the source (e.g. `pop_local_internal_* = 0.0`) is `0`, not `null`.

### 5.5 Identifiers

| Identifier | Format / example | Cardinality | Joins |
|---|---|---|---|
| `adm4_pcode` | `PH0603022NNN` (`PH0603022001`) | 180, unique | barangay geometry ↔ A3 ↔ A1 ↔ population |
| `cell_id` | string from `access_cells.cell_id` (`r<row>c<col>`, e.g. `r12408c6769`) | 8,035, unique | `cells_a3` ↔ `access_cells` |
| `fid_key` | `node/<id>`, `way/<id>` or `relation/<id>` (542 / 359 / 36 at discovery) | 937 unique facilities | `facilities` ↔ `facility_roles` ↔ `facilities_by_approach` ↔ duplicate review (`flagged_fid`, `related_fid`) |
| `review_id` | `D01` … `D14` | 14, unique | duplicate review pairs |
| `fragment` | `main`, `F001` … `F111` | 112 | `component_inventory` ↔ `gap_investigation` ↔ `cells_a3.component` ↔ M03 `network_fragments` (9) |
| indicator id | §4.1 pattern | — | `manifest.indicator_catalog` ↔ `barangay_indicators.values` ↔ `city.*.indicator_id` |

Display values (`adm4_name`, facility `name`, `scenario_label`, `class_reason`) **MUST NOT** be used as
keys.

---

## 6. Data-quality metadata (`data_quality`)

### 6.1 Schema

Each file carries a dataset-level `data_quality` object (in the §5.3 envelope); selected records carry
a record-level one (§6.2). The two never share a field name at the same level: a dataset-level block
describes the whole file; a record-level block, always nested in a record, describes only that record.

```
data_quality (dataset level) = {
  "role":                 enum<primary|comparative|descriptive|evidence_only>,
  "scenario":             enum<A1|A2|A3|mixed|none>,   # mixed: the dataset holds several scenarios
  "mode":                 enum<walk|drive|mixed|none>,
  "analysis_only":        boolean,          # true only for a dataset that is entirely analysis-only
  "source_validation":    object,           # §6.1.1, identical in every file of the bundle
  "statements":           array<string>,    # codes of §6.3 that the UI must show with the data; texts only from manifest.statements
  "known_issues":         array<object>     # {code: string, text: string, affects: array<string>}
}
```

```
source_validation = {
  "audit":                       object,    # §6.1.1
  "a1_reproduces_baseline":      boolean,   # recorded by `abot components` in run_info.json at created_utc (not re-verified)
  "baseline_outputs_unchanged":  boolean,   # recorded in run_info.json (not re-verified)
  "baseline_hashes_match_disk":  boolean,   # re-verified by the exporter (V-S2); always true in a written bundle
  "component_classes_check":     {reference: string | null, components_compared: integer, identical: boolean}
                                             # review/m04/taxonomy_check.json; V-S4 requires identical = true
}
```

#### 6.1.1 Audit block

The exporter obtains the audit by calling the existing implementation in-process:
`abot.audit.Audit(settings, config_path, hashes=True).run()`, with `settings` loaded by
`load_settings(config_path, create_dirs=False)`. It **MUST NOT** call `abot.audit.run` (prints and may
write a report), **MUST NOT** start `abot audit` as a subprocess, and **MUST NOT** reimplement any
audit check. Verified at review: the call is read-only (no file or directory created or changed
anywhere in the repository, nothing downloaded, no stage triggered, no review decision applied; about
9 s). It runs before any bundle file is written.

```
audit = {
  "status":        enum<obtained|not_run|error>,
  "ran_utc":       string | null,          # start of the call; null when not_run
  "implementation": "abot.audit.Audit.run(hashes=True), in-process, read-only",
  "outcome":       enum<pass|warn|fail> | null,   # null unless status = obtained
  "counts":        {pass: integer, warn: integer, fail: integer, info: integer} | null,
  "findings":      array<{section: string, check: string, status: enum<WARN>, detail: string, action: string}>,
                                           # the WARN findings (a FAIL never reaches a written bundle)
  "reason":        string | null           # why not_run; null when obtained
}
```

| `status` | `outcome` | When | `counts` | Export | Manifest `known_issues` | UI |
|---|---|---|---|---|---|---|
| `obtained` | `pass` | `run()` returned findings with no FAIL and no WARN | from the findings | **allowed** | — | "Audit passed" |
| `obtained` | `warn` | `run()` returned findings with at least one WARN and no FAIL | from the findings | **allowed** | `AUDIT-WARN` | "Audit passed with warnings", every finding of `findings` listed |
| `obtained` | `fail` | `run()` returned at least one FAIL (an `audit_error` finding is a FAIL) | from the findings | **blocked** | — (no bundle) | — |
| `error` | `null` | constructing `Audit` or calling `run()` raised | `null`; `reason` holds the exception | **blocked** | — (no bundle) | — |
| `not_run` | `null` | the exporter was started with `--skip-audit` (the only way to reach this state) | `null`; `reason` = `"skipped on request (--skip-audit)"` | **allowed** | `AUDIT-NOT-RUN` | "Audit not run for this bundle" |

A blocked export behaves like any failed check (§10.1 step 5): nothing is written, the previous bundle
is kept, the findings or the exception are printed, and the exit status is non-zero. A written bundle
can therefore only carry `obtained`/`pass`, `obtained`/`warn` or `not_run`. Only `obtained`/`pass` may
be displayed as a passed audit; `not_run` **MUST NOT** be presented as passed, and `counts` are never
invented. Without `--skip-audit` the audit always runs.

### 6.2 Record-level blocks

| Where | Field | Type | Source |
|---|---|---|---|
| barangay | `reliability.population` | `{level: enum<ok\|caution\|low>, reasons: string \| null}` | `rel_population`, `rel_population_reasons` |
| barangay | `reliability.network` | same | `rel_network`, `rel_network_reasons` |
| barangay | `reliability.facility_inventory` | `{level: enum<unverified>, reasons: string}` | `rel_facility_inventory`, `_reasons` |
| barangay | `reliability.overall` | `{level: enum<ok\|caution\|low>, reasons: string}` | `rel_overall`, `_reasons` (most restrictive of population and network; a rule, not a score) |
| barangay | `ranking_eligible` | boolean | `pop_ranking_eligible` (False when population or network reliability is low: 31 barangays) |
| barangay | `indicators_flag_not_connected` | boolean | A1 `indicators_flag_not_connected` (`pct_not_connected` > `reliability.network.low_pct_not_connected`, 5) |
| barangay | `resolved_separately` | boolean | `barangay_access_a3.resolved_separately` (Calahunan, Hibao-an Sur): included in every total and denominator, never treated as missing |
| barangay | `n_facilities_duplicate_review` | integer | `barangay_access.n_facilities_duplicate_review` |
| facility | `duplicate_review` | `array<{review_id, role: enum<flagged\|related>, other_fid, review_status: enum<pending\|reviewed>, reviewer_decision: string \| null}>` (empty array when the facility is in no pair; 3 facilities are in two pairs) | `review/possible_duplicates_review.csv` (`flagged_fid` / `related_fid` verified to match `fid_key`); copied as is, decisions never applied |
| facility | `classification.class_status`, `class_reason` | string | facilities layer; an identical copy of the top-level `class_status` and `class_reason` of §7.6 (both are always written and always equal; V-C2) |
| cell | `population_allocation` | constant statement only (no per-cell field) | — |

### 6.3 Required statements

Statement texts are fixed by the contract. Figures in a statement (marked `{…}`) are filled at export
from the named source, never typed in; V-Q3 checks them. The exporter writes every statement, with its
figures filled in, to `manifest.statements` (§7.1). The frontend **MUST** display caveat texts from
`manifest.statements`, looked up by code; components **MUST NOT** retype, paraphrase or hard-code a
statement text (a retyped `DQ-DUP` would show stale review counts). An unresolved code is a load error
(§7.1), never an empty caveat.

| Code | Applies to | Statement |
|---|---|---|
| `DQ-SHARE-ALL` | every `pct_le*` | "Share of all residents, including those without a network connection." |
| `DQ-MEAN-CONN` | every `mean_min`, `p90_min` | A3: "Describes residents connected to the main walk network only." A1: "Describes A1-connected residents only." |
| `DQ-A1-OPT` | every A1 walking value | "A1 is an optimistic comparison scenario, not an observed result or a verified upper bound." |
| `DQ-DRIVE` | every drive value | "Modelled uncongested car travel time: a lower bound that assumes car availability; no congestion, parking or turn delays." |
| `DQ-LOCAL` | local / uncertain internal values | "Travel within an isolated network component only; never counted as citywide access." |
| `DQ-FAC-OSM` | facility counts and maps | "Mapped OpenStreetMap features; completeness unverified against official registries." |
| `DQ-DUP` | facilities, facility counts | "{pending} of {pairs} possible duplicate pairs pending review; {likely} pairs judged likely duplicates but not merged (both records still counted). No pair is merged automatically." Counts from `possible_duplicates_review.csv` (`review_status == "pending"`; `reviewer_decision == "likely_duplicate_not_merged"`). At discovery: 7 of 14, 2. |
| `DQ-POP-ALLOC` | barangay values, cells | "Barangay values use a fractional allocation of 100 m population cells; cell values cannot be summed to barangays." |
| `DQ-RESOLVED` | Calahunan, Hibao-an Sur | "Included in all totals; resolved separately in Milestone 03." |
| `DQ-ANALYSIS-ONLY` | access impact, access taxonomy, corridors | "Analysis only: not applied to the network or to any indicator." |
| `DQ-PHYS-NOT-PUBLIC` | gap evidence | "Physical connection in OSM topology is not public pedestrian access." |
| `DQ-BBOX` | component boxes | "Bounding box of the component's nodes, not its network geometry." |
| `DQ-DIST` | `city.walk_distribution` | "Distribution of citywide walking times of network-connected residents; residents without a citywide time are outside the curve but inside the denominator." |
| `DQ-SIMPLIFIED` | barangay polygons | "Boundaries simplified for display; areas and all values use the original boundaries." |

---

## 7. Datasets

### 7.1 `manifest.json`

**Purpose:** contract identity, provenance of every input, scenario and indicator definitions, the
physical layout of the cell dataset, and the data needed to detect a stale bundle. **Role:** descriptive.

| Field | Type | Source / rule |
|---|---|---|
| envelope | §5.3 | — |
| `files` | `array<{name, sha256, bytes, dataset}>` | every other bundle file (6 files + the cell chunks of §7.5.1), hashed after writing |
| `cells_layout` | object (§7.5.1) | exporter |
| `source_files` | `array<{path, sha256, bytes, mtime_utc, used_for: array<string>}>` | exactly the files of §7.1.1 (paths relative to the repository root, `/` separators), hashed before export and re-hashed after (V-X1) |
| `code.git_commit` | string \| null | `git rev-parse HEAD`; null if git is unavailable or the root is not a repository |
| `code.git_working_tree_clean` | boolean \| null | `git status --porcelain -z` reports no entry (tracked and untracked, excluding ignored); null if git is unavailable |
| `code.git_dirty_count` | integer \| null | number of entries reported by `git status --porcelain -z` (a rename or copy counts once) |
| `code.git_dirty_paths` | `array<string>` | paths of those entries, parsed from the NUL-separated `-z` output so that spaces and unusual characters are kept literally (never C-quoted); for a rename or copy the new path; sorted, at most 50 (`git_dirty_count` shows whether the list is truncated) |
| `code.abot_version` | string | `abot.__version__` (`"0.1.0"` at discovery) |
| `config_sha256` | string | `Settings.config_sha256` of the configuration the exporter loaded; **MUST** equal `run_info.json.config_sha256` and every stage in `data/interim/run_meta.json` (V-S3) |
| `stage_completed_utc` | `{boundaries, population, osm, accessibility, report: string}` | `data/interim/run_meta.json` `<stage>.completed_utc` |
| `a3_run_info` | object | `component_aware/run_info.json` copied verbatim (`config_sha256`, `created_utc`, `a1_reproduces_baseline`, `baseline_outputs_unchanged`, `baseline_sha256`, `population_total`, `scenario_labels`) |
| `population_total` | number | 457,626.0 at discovery; **MUST** equal `a3_run_info.population_total` |
| `scenarios` | `array<{code, mode, role, label_key \| null, label}>` | §3.1 |
| `indicator_groups` | `array<{id, category, subtypes: array<string>}>` | `config/settings.yaml` → `indicator_groups` |
| `thresholds_min` | `{walk: array<integer>, drive: array<integer>}` | config → `accessibility.thresholds_min` |
| `walk_speed_kmh` | number | config → `accessibility.walk_speed_kmh` |
| `drive_access_flag_m` | number | config → `accessibility.connection.drive_access_flag_m` |
| `drive_network_time_factors` | `array<number>` | `[1.0]` + config → `accessibility.drive_network_time_factors` |
| `walk_distribution` | `{bin_width_min: 1, closed_max_min: 60}` | §7.2 |
| `indicator_catalog` | `array<{id, levels: array<enum<barangay\|city>>, scenario, mode, group \| null, statistic, unit, numerator, denominator \| null, population_described \| null, role, source_file, source_column, statements: array<code>}>` | §4.1, one entry per concrete id (every `{g}`, `{N}`, `{category}` expanded); `denominator` null for counts |
| `statements` | `array<{code, applies_to, text}>` | §6.3, every code, with figures filled in; the texts that the `statements` codes of every `data_quality` block and catalogue entry refer to |
| `known_issues` | `array<{code, text, affects}>` | bundle-wide issues (`AUDIT-WARN`, `AUDIT-NOT-RUN`, `GIT-DIRTY`) |
| `crs` | `"EPSG:4326"` | §8 |

A commit SHA alone **MUST NOT** be presented as proof that the outputs match the repository: the UI
shows `git_working_tree_clean` next to it, and `false` or `null` is displayed as "built from a working
tree with uncommitted changes" / "unknown". When the tree is not clean, the manifest carries known issue
`GIT-DIRTY`.

#### 7.1.1 Source files read by the exporter

Paths are relative to `data/processed/` unless they start with `data/` or `config/`. This is the
complete list (V-S1); the exporter reads nothing else for bundle content (R13).

| Source | Used for |
|---|---|
| `component_aware/barangay_access_a3.csv` | A3 barangay values (R3) |
| `component_aware/cells_a3.csv` | cells (A3 part, coordinates), `walk_distribution` (the A3 GeoPackage `component_aware.gpkg` is not read) |
| `component_aware/citywide_a3.csv` | city A3/A1 walking and population |
| `component_aware/run_info.json` | `a3_run_info`, scenario labels, V-S2, V-S3 |
| `barangay_access.csv` | A1 barangay values (R4) |
| `facility_inventory.csv` | facility inventory |
| `facilities.csv` | V-G2 coordinate check only |
| `drive_speed_sensitivity.csv` | city A1 drive and sensitivity |
| `barangay_population.csv` | V-S2 baseline hash only (not exported, Q7) |
| `abot_iloilo.gpkg` layers `barangays`, `access_cells`, `facilities`, `facility_roles` | barangay geometry, A1 cell part, facilities; whole file hashed for V-S2 |
| `review/possible_duplicates_review.csv` | facility duplicate review, `DQ-DUP` |
| `review/m03/validation.gpkg` layers `network_fragments`, `fragment_gaps` | 9 fragment geometries |
| `review/m04/facilities_by_approach.csv`, `approach_comparison.csv`, `transition_A1_to_A3_pop.csv`, `component_inventory.csv`, `gap_investigation.csv`, `access_classification_summary.csv`, `access_impact.csv`, `access_impact_by_group.csv`, `taxonomy_check.json` | `network.json`, facility `off_main_network_in`, V-S4 |
| `review/m04/snapshot_status.json` | whether `abot components` used a targeted gap snapshot (`obtained`), V-S5 (1.0.1) |
| `review/m04/snapshot_corridor_analysis.csv`, **only when** `snapshot_status.obtained` is true | `gap_evidence` path fields (1.0.1: conditional; an empty file without columns, written for a snapshot with no link candidate, is read as no rows) |
| `data/interim/run_meta.json`, `data/interim/osm_provenance.json`, `data/interim/qa/*.json` | provenance, V-S3 |
| `data/raw/manifest.json` | `provenance.sources` |
| `config/settings.yaml` | groups, thresholds, `config_sha256` |

### 7.2 `city.json`

**Purpose:** citywide headline values (Citywide Overview, Travel-Time Analysis, Facility section
summaries). **Role:** primary (with comparative and evidence-only parts flagged per record).

| Part | Structure | Source | Transformation |
|---|---|---|---|
| `population` | `{total, a3: {<category>: {pop, pct}}, a1: {connected_pop, connected_pct, not_connected_pct}}` | `citywide_a3` metrics `pop_{category}` (`A3`, `A3_pct`), `pop_connected_A1_optimistic` (`A1`, `A1_pct`); `not_connected_pct` = `drive_speed_sensitivity.pct_not_connected` | pivot; `total` = `run_info.population_total`. A1 not-connected **residents** are not exported citywide (no source column); the share is a source value, labelled A1 |
| `walk` | `array<{indicator_id, group, scenario: A1\|A3, statistic: pct_le10\|pct_le15\|pct_le30\|mean_min, value: number \| null, unit, role}>` | `citywide_a3` cols `A3`, `A1` | long format; one record per (group, scenario, statistic); `unit` % or minutes |
| `walk_internal` | `array<{indicator_id, group, category: locally_connected\|access_uncertain, threshold_min, value, unit: "residents", role: "evidence_only"}>` | `citywide_a3` cols `A3_local_internal_pop`, `A3_uncertain_internal_pop` on the `walk_{g}_pct_le{N}` rows | **unit conversion of meaning:** these columns are resident counts sitting on percentage rows; they are moved to their own records |
| `walk_distribution` | `array<{group, scenario: "A3", bins: array<{lower_min, upper_min: integer \| null, pop}>, cumulative: array<{minutes: integer \| null, pct_all_residents}>, pop_with_time, pop_open_bin, pop_total}>` | `cells_a3.t_walk_{g}_citywide`, `cells_a3.pop` | the only computed part (R7), defined below |
| `drive` | `array<{indicator_id, group, scenario: "A1", network_time_factor, statistic: mean_min\|pct_le5\|pct_le10\|pct_le15, value, unit, role}>` | `drive_speed_sensitivity.csv` | long format; factor 1.0 → ids `A1.drive.{g}.*`, role `primary`; factors 1.5 / 2.0 → ids `A1.drive_sensitivity.{g}.*`, role `evidence_only` (illustrative) |
| `facility_inventory` | `array<{group, n_in_city, n_in_buffer_outside_city, n_destinations_connected, n_not_connected_not_used, n_unnamed, n_not_decided_by_tag_rule, n_duplicate_review_pending, registry_reference, inventory_status, note}>` | `facility_inventory.csv` | copy |

**`walk_distribution` (Q5).** One record per group, over all 8,035 cells of `cells_a3` with their whole
`pop` (not barangay pieces):
- **Bins:** 1-minute, right-closed. Bin `k` (k = 1 … 60) holds the population of cells with a citywide
  time `t` such that `k − 1 < t ≤ k` (bin 1 also holds `t = 0`; the smallest time at discovery is 0.05).
  Record: `{lower_min: k − 1, upper_min: k, pop}`. All 60 bins are always present, empty bins with
  `pop: 0`.
- **Open final bin:** one more record `{lower_min: 60, upper_min: null, pop}` holding every cell with
  `t > 60`; the UI labels it "> 60 min". 60 is a fixed contract value (`manifest.walk_distribution.closed_max_min`),
  twice the largest walking threshold; it is not taken from the data. The maximum observed time is
  therefore in bin `ceil(t_max)` if `t_max ≤ 60` and in the open bin otherwise (at discovery the group
  maxima are 46.5–91.9 min; the open bin holds 0–19,602.6 residents depending on the group).
- **Cells without a citywide time** (every cell that is not `network_connected`) are in no bin.
- `pop` of a bin and `pop_open_bin` are rounded to 1 decimal; `pop_with_time` = Σ `pop` of cells with a
  citywide time (1 decimal); `pop_total` = Σ `cells_a3.pop` (= `population.total`).
- **Cumulative:** for `minutes` = 1 … 60, `pct_all_residents` = 100 × (unrounded population of bins 1 … k) /
  `pop_total`, rounded to 2 decimals; then one final point `{minutes: null, pct_all_residents}` that adds
  the open bin: 100 × `pop_with_time` / `pop_total` (every resident with a citywide time, including those
  above 60 min). The open-bin population is never dropped: it is in `bins`, in `pop_open_bin`, in the
  final cumulative point, in `pop_with_time` and in `pop_total`. The UI labels the final point "all
  citywide times (incl. > 60 min)". The curve still ends below 100 %: the rest is
  `pop_total − pop_with_time` (residents without a citywide time). The UI **MUST NOT** extend the curve to
  100 % and shows statement `DQ-DIST`.
- Points of the distribution other than 10, 15 and 30 min are a display aid, not catalogue indicators,
  and are never shown as headline values.

Denominators per §4.1. CRS: none. Nulls: `citywide_a3` blanks (e.g. the `A1`, `A3_pct` cells of rows
that do not carry them) are structural; they produce no record, never a zero.

**Validation:** `population.total` = Σ A3 category pops (±0.5) = 457,626.0 at discovery; A3 pct sum 100 ± 0.02;
`walk_distribution` reproduces `citywide_a3` (V-C1); factor-1.0 drive values equal the recomputation
from `access_cells` (V-C3, Q6); `not_connected_pct` identical on all `drive_speed_sensitivity` rows.

### 7.3 `barangays.geojson`

**Purpose:** barangay polygons for maps. **Role:** descriptive. **No indicator values** (they live in
`barangay_indicators.json`, joined by `adm4_pcode` in the client). Features ordered by `adm4_pcode`.

| Property | Type | Source (`abot_iloilo.gpkg` › `barangays`) |
|---|---|---|
| `adm4_pcode` | string | `adm4_pcode` |
| `adm4_name` | string | `adm4_name` |
| `adm3_pcode`, `adm3_name` | string | same names |
| `area_km2` | number | `area_km2` (computed by ABOT from the unsimplified EPSG:32651 polygon, the value used in QA; equals the source polygon area exactly). `area_sqkm` (COD-AB attribute, ≤ 0.003 km² different) is **not** exported |
| geometry | MultiPolygon, EPSG:4326 | reprojected from EPSG:32651, then display-simplified (§8.2); always written as MultiPolygon (Shapely returns a Polygon for the single-part source polygons; it is wrapped, keeping the part count of the source) |
| foreign member `simplification` | `{method: "shapely simplify, preserve_topology=True, after reprojection to EPSG:4326", tolerance_deg: 2e-05, tolerance_unit: "degree", display_only: true, vertices_before: integer, vertices_after: integer}` | exporter |

**Validation:** exactly 180 features; `adm4_pcode` set equals the A3 and A1 sets; every geometry valid
and non-empty after simplification **and** coordinate rounding, with the source's part count; no
repair (`make_valid`, `buffer(0)`) is applied, an invalid geometry fails the export; `area_km2` equals
the unsimplified source value.

### 7.4 `barangay_indicators.json`

**Purpose:** all barangay-level values (Barangay Accessibility, Overview map, detail panel). **Role:**
primary (A3 walk), comparative (A1 walk), primary for driving (A1 drive, separate mode), descriptive
(counts), with each value typed by its catalogue entry. Records ordered by `adm4_pcode`.

```
{ envelope,
  "barangays": array<{
     "adm4_pcode": string, "adm4_name": string,
     "pop_total": number,                                   # A3 file; must equal A1 file
     "a3_population": {<category>: {"pop": number, "pct": number}},   # 4 categories
     "a1_population": {"pop_connected": number, "pop_not_connected": number, "pct_not_connected": number},
     "values": {<indicator_id>: number | null},             # every catalogue id with level "barangay"
     "facility_counts": {"n_<category>": integer, "n_<group>": integer},
     "a1_drive_access": {"pop_drive_access_gt_flag": number},
     "data_quality": {reliability, ranking_eligible, indicators_flag_not_connected,
                      resolved_separately, n_facilities_duplicate_review}     # §6.2
  }> }
```

`values` has the same key set in every record: exactly the catalogue ids whose `levels` include
`barangay` (Q2). `a3_population`, `a1_population` and `a1_drive_access` repeat, for convenience, values
that are also in `values` under their ids (`A3.population.*`, `A1.population.*`,
`A1.drive.pop_drive_access_gt_flag`); the two copies **MUST** be equal (V-C2).

| Group of fields | Source | Rule |
|---|---|---|
| `adm4_name`, `pop_total`, `a3_population`, `A3.*` ids, `resolved_separately` | `component_aware/barangay_access_a3.csv` | R3 |
| `a1_population`, `A1.*` ids, `facility_counts`, `a1_drive_access`, reliability, `ranking_eligible`, `indicators_flag_not_connected`, `n_facilities_duplicate_review` | `barangay_access.csv` | R4 |

Census and WorldPop fields of `barangay_access.csv` (`psgc_2023`, `census_name`, `census_2020`,
`pop_wp2020`, `pop_wp2026`, `pop_census2020_adj`, `census_adj_factor`, `census_unallocated`,
`pop_cells_centre`, `pop_cells_touching`, `pct_pop_from_straddling_cells`, `pop_wp2020_centre_rule`,
`wp2020_vs_census_pct`, `primary_weight`) are **not** exported in v1 (Q7).

**Nulls:** a source blank stays `null` (none at discovery: the A3 file has no nulls; the A1 file only in
the reasons text). **CRS:** none.

**Validation:** 180 records, unique `adm4_pcode`; Σ A3 category pop = `pop_total` (±0.5) per record;
`pop_total` equal in both sources (±0.05); `values` keys = the barangay-level catalogue ids; every `%` in
[0, 100]; every minute ≥ 0; ranking views use `ranking_eligible` only.

### 7.5 Cell dataset (`cells`)

**Purpose:** cell map (A3 category, citywide times, drive times). **Role:** primary (A3 walk, A1 drive)
for **visualisation only** (R5, R6). The citywide distribution in `city.json` is computed by the
exporter from `cells_a3.csv` directly, not from the written cell files.

One **logical** dataset: a GeoJSON FeatureCollection of all 8,035 cells, one Point feature per cell,
ordered by `cell_id` ascending (Unicode code-point order; equals the source row order at discovery).
Its **physical** layout is §7.5.1.

| Property | Type | Source | Notes |
|---|---|---|---|
| `cell_id` | string | `cells_a3.cell_id` | key |
| `pop` | number | `cells_a3.pop` | residents of the whole cell inside the city (all barangays it touches) |
| `display_adm4_pcode` | string | `cells_a3.adm4_pcode` | **renamed**: barangay holding most of the cell; display and filtering only, never aggregation |
| `a3_category` | enum<§3.2 A3> | `cells_a3.a3_category` | |
| `a3_conn_status` | enum<connected\|beyond_tolerance\|barrier_blocked> | `cells_a3.conn_status` | A3 status |
| `a3_conn_m` | number \| null | `cells_a3.conn_m` | null when unconnected (263) |
| `component` | string \| null | `cells_a3.component` | `main`, `Fnnn`; null when unconnected (263) |
| `component_class` | string \| null | `cells_a3.component_class` | null when unconnected |
| `walk_citywide` | `{<group>: number \| null}` (all 10 groups) | `cells_a3.t_walk_{g}_citywide` | null unless `network_connected` (459 cells null in every group) |
| `walk_internal` | `{<group>: number \| null}` (all 10 groups) \| null | `cells_a3.t_walk_{g}_internal` | object only for `locally_connected` and `access_uncertain` cells (196), group value null when the component has no facility of the group; `null` for every other cell |
| `a1_conn_status` | enum (as above) | `access_cells.conn_status` | A1 status (differs from A3) |
| `drive_a1` | `{<group>: number \| null}` (all 10 groups) | `access_cells.t_drive_{g}` | null when A1-unconnected (302 cells) |
| `drive_access_m` | number \| null | `access_cells.drive_access_m` | routed walk to the drive network; null when A1-unconnected |
| geometry | Point, EPSG:4326 | `cells_a3.lon`, `lat` | 6 decimals as in the source, copied |

A1 per-cell **walking** times (`access_cells.t_walk_*`) are not exported in v1 (barangay and citywide A1
comparisons suffice; Q8).

#### 7.5.1 Physical layout (Q9)

Measured at review: the logical dataset above, serialised per §5.1 as one file, is **6,935,709 bytes**
(6.94 MB; 8,035 features, 837–1,098 bytes each). It exceeds the 4 MB limit, so at discovery it is
written as 2 chunks of about 3.5 MB. The exporter applies this rule on every export:

1. Serialise the whole logical dataset as one FeatureCollection; `single_file_bytes` = its size.
2. `max_file_bytes` = 4,000,000. If `single_file_bytes ≤ max_file_bytes`, `n` = 1; otherwise `n` is the
   smallest integer ≥ 2 for which every chunk of step 3 is ≤ `max_file_bytes`.
3. Split the `cell_id`-ordered feature list into `n` contiguous chunks; chunk `i` (1-based) holds features
   `(i−1)·m` … `min(i·m, 8035) − 1` (0-based), where `m = ceil(8035 / n)`. No other split key (barangay,
   group, runtime order) is used.
4. Write chunk `i` as `cells-<iii>.geojson` (`iii` = 3-digit, zero-padded, from `001`), also when `n` = 1.
   Each chunk is a complete GeoJSON FeatureCollection with the §5.3 envelope (`dataset: "cells"`,
   identical in every chunk) and the foreign member `chunk: {index, count, features, first_cell_id, last_cell_id}`.
   Features, properties and values are exactly those of the logical dataset: nothing is dropped,
   rounded further or renamed to meet the limit.

```
manifest.cells_layout = {
  "dataset": "cells", "features": 8035, "order": "cell_id ascending (Unicode code points)",
  "max_file_bytes": 4000000, "single_file_bytes": integer, "count": integer,
  "chunks": array<{index, name, features, first_cell_id, last_cell_id, bytes, sha256}>   # ordered by index
}
```

Every chunk is also listed in `manifest.files` with `dataset: "cells"`. The frontend reconstructs the
logical dataset by loading every chunk of `cells_layout.chunks`, checking each chunk's envelope
(`contract_version`, `generated_utc`), `chunk.index` and feature count, and concatenating the features
in `index` order; it **SHOULD** check each `sha256`. If any chunk is missing or fails a check, the cell
map is not shown at all (never a partial city). A change of `count` between exports is a data-size
consequence, not a schema change (§14).

**Validation:** 8,035 features in total over all chunks; `cell_id` unique and equal to the
`access_cells` set; Σ `pop` = 457,626.0 (±0.5); `walk_citywide` non-null iff `a3_category =
network_connected`; `walk_internal` non-null iff `a3_category` ∈ {`locally_connected`, `access_uncertain`};
`drive_a1` all-null iff `a1_conn_status ≠ connected`; coordinates within the study-area bounds; layout
per §7.5.1 (V-K1).

### 7.6 `facilities.geojson`

**Purpose:** facility map and facility tables. **Role:** descriptive (locations, counts); facilities with
a role of tier `indicative` are the destinations behind the travel times. Features ordered by `fid_key`.

| Property | Type | Source |
|---|---|---|
| `fid_key` | string | facilities layer `fid_key` (937 unique) |
| `osm_type`, `osm_id` | enum<node\|way\|relation>, integer | facilities layer |
| `name` | string \| null | facilities layer (75 null) |
| `category`, `subtype`, `tier` | string | facilities layer (primary role) |
| `class_status`, `class_reason` | string | facilities layer |
| `geom_source` | enum<node\|representative_point> | facilities layer (`representative_point` for mapped areas) |
| `inside_city` | boolean | facilities layer (134 outside: destinations only if connected) |
| `conn_status` | enum<connected\|beyond_tolerance> | facilities layer (`facilities.csv` lacks it) |
| `conn_m`, `drive_access_m` | number \| null | facilities layer (13 null: not connected) |
| `nearest_edge_m` | number | facilities layer |
| `roles` | `array<{category, subtype, tier, status, primary: boolean}>` | `facility_roles` (938 rows; `way/628752365` has two roles: government barangay hall, evacuation centre) |
| `indicator_groups` | `array<string>` | derived: groups whose `category` and `subtypes` match any role (config `indicator_groups`) |
| `destination_groups` | `array<string>` | groups for which a matching role has `tier == "indicative"` **and** the facility `conn_status == "connected"`. Verified to reproduce `facility_inventory.n_destinations_connected` for all 10 groups. Evaluated per role, not on the primary `tier` |
| `off_main_network_in` | `{A1: string \| null, A2: string, A3: string} \| null` | `review/m04/facilities_by_approach.csv` (25 facilities; `components_*` values copied as source strings, e.g. `F024;main`); `null` for the other 912 |
| `data_quality.duplicate_review` | §6.2 | `review/possible_duplicates_review.csv` |
| geometry | Point, EPSG:4326 | facilities layer (EPSG:32651) reprojected, 6 decimals |

**Validation:** 937 features, unique `fid_key`; reprojected coordinates equal `facilities.csv`
`lon`/`lat` within 1e-6° (max 5e-8° at review, before rounding); per-group counts of `destination_groups` equal
`facility_inventory.n_destinations_connected`; every duplicate-review id resolves to a feature.

### 7.7 `network.json`

**Purpose:** Network Connectivity section. **Role:** `evidence_only` throughout, except the A1/A3
population transition (`descriptive`). All sources are in `review/m04/` unless stated.

| Part | Structure | Source | Notes |
|---|---|---|---|
| `approaches` | `array<{approach, scenario_label, role, components_retained, network_km, cells_{category}, pop_{category}}>` | `approach_comparison.csv` rows `group == "_population"` | roles: A1 comparative, A2 `evidence_only`, A3 primary |
| `approaches_by_group` | `array<{approach, group, mean_min, pct_le15_all_residents, pct_le30_all_residents, pop_with_time, pop_local_with_internal_time, pop_local_internal_le15}>` | `approach_comparison.csv` other rows | A2 `mean_min` mixes internal and citywide times (as defined by A2): labelled |
| `transition_a1_to_a3` | `array<{a1_category, a3_category, pop}>` | `transition_A1_to_A3_pop.csv` (`cat_A1_baseline` × A3 columns) | long format; blanks are absent pairs, not zero |
| `component_classes` | `array<{component_class, components, length_km, pop_attached_A3}>` | grouped from `component_inventory.csv` | counts and sums of the 112-row table (R2) |
| `components` | `array<{fragment, component_class, class_reason, length_km, km_inside_city, n_nodes, n_edges, gap_to_main_m, gap_crosses_water \| null, noexit_at_gap, retained_A2, retained_A3, cells_attached_A3, pop_attached_A3, pop_internal_health_primary_care_reachable, pop_internal_education_basic_reachable, km_no, km_private, km_residents, km_customers, km_unknown, km_destination, km_pedestrian_override, km_untagged, km_public, gates_restricted, gates_untagged, bbox: {lon_min, lat_min, lon_max, lat_max}, geometry_kind: "bounding_box"}>` | `component_inventory.csv` | `bbox` from the source `lon_*`/`lat_*` (EPSG:4326, 6 decimals) |
| `fragment_geometries` | GeoJSON FeatureCollection: 9 features `geometry_kind: "mapped_fragment_geometry"`, properties `{fragment, n_edges, length_km, gap_to_main_m}`, + 9 `gap_line` features (`geometry_kind: "gap_line"`, properties `{fragment, gap_to_main_m}`) | `review/m03/validation.gpkg` › `network_fragments` (9, MultiLineString) and `fragment_gaps` (9, LineString), EPSG:32651 → 4326 | only 9 fragments; see §8.4. `n_edges` and `length_km` are taken from `component_inventory.csv`: the M03 layer's `n_edges` counts directed edges (exactly twice the inventory value) and is not exported |
| `gap_evidence` | `array<{fragment, component_class, component_class_changed_by_snapshot, cache_*…, snapshot_physical_connection, snapshot_link_m, snapshot_link_ways, snapshot_link_access_tags, snapshot_link_gates, snapshot_corridor_gates, snapshot_public_pedestrian_access, snapshot_path_access_status, snapshot_public_pedestrian_status, snapshot_authorized_group, snapshot_field_verification_required, remaining_unverified, path_ways, path_gates, classification_reason, applied: false}>` | `gap_investigation.csv` (+ `snapshot_corridor_analysis.csv` joined on `fragment`, one row each, for `path_ways`, `path_gates`, `classification_reason`, `applied`) | F001, F100, F101; physical connection, mapped path access, public pedestrian status and authorised group kept in separate fields. Without a corridor row for a fragment (no targeted snapshot, or no link candidate) `path_ways`, `path_gates` and `classification_reason` are `null` and `applied` is false; without a snapshot `snapshot_physical_connection` is `not_examined` and `remaining_unverified` says so |
| `access_classification` | `array<{kind, access_class, public_pedestrian_status, treatment, ways, edges, km, km_main, components, cells_attached_A1, pop_attached_A1, nodes, nodes_flag_for_review, nodes_field_verification, nodes_main}>` (nullable per `kind`) | `access_classification_summary.csv` | `analysis_only: true` |
| `access_impact` | `array<{scenario, definition, ways_all_components, km_all_components, edges_removed_main, km_removed_main, pop_lose_network, pop_become_local, pop_become_unconnected, pop_time_up_gt1min, pop_lose_network_focus \| null}>` and `access_impact_by_group` (`scenario, group, pct_le15_baseline, pct_le15_scenario, mean_min_baseline, mean_min_scenario`) | `access_impact.csv`, `access_impact_by_group.csv` | `analysis_only: true`, `applied: false` |

**Validation:** 112 components incl. `main`; class counts match `component_inventory`; the 9 fragment
geometries' `fragment` ids exist in `components` and their source `gap_to_main_m` equals the inventory
value (verified at review for all 9); `component_classes_check.identical` is true; every
`gap_evidence.applied` and every corridor `applied` is false.

In the three access tables (`access_classification`, `access_impact`, `access_impact_by_group`) the
flags are written on **every record**, not once per table: each record carries `analysis_only: true`
and `applied: false` after its source fields (R12, V-Q2). `gap_evidence` records carry `applied` only.

### 7.8 `provenance.json`

**Purpose:** Methodology and Data Provenance section. **Role:** descriptive.

| Part | Fields | Source |
|---|---|---|
| `sources` | `array<{path, url, licence, retrieved_utc, bytes, sha256, source \| null, release \| null, year \| null, hdx_dataset \| null, hdx_last_modified \| null, timestamp_osm_base \| null, overpass_timestamp_osm_base \| null, query_file \| null, query_sha256 \| null, query_label \| null, boundary_buffer_m \| null, used_by_runs \| null}>` | `data/raw/manifest.json` (14 entries; fields vary by source: absent → null). Recorded values, not re-hashed by the exporter |
| `osm` | `{osmnx_version, overpass_endpoint, boundary_buffer_m, responses: array<{label, cache_file, overpass_timestamp_osm_base, elements, sha256}>}` | `data/interim/osm_provenance.json` |
| `targeted_snapshot` | `{file, sha256, timestamp_osm_base, used_for: "evidence only"}` \| `null` | latest manifest entry `osm_targeted/…`; `null` when no targeted snapshot was used (the v1.0.0 exporter already wrote `null` then; documented in 1.0.1). V-S5 guarantees it is the snapshot `abot components` used |
| `qa` | per file `{check: {ok: boolean \| null, value, note}}` | every `data/interim/qa/*.json` (5 at discovery: `boundaries`, `population`, `osm`, `accessibility`, `provenance`) |
| `audit` | `source_validation` object of §6.1 | exporter |
| `limitations` | `array<{code, text}>` | §11 of this contract (fixed text; figures filled from sources as in §6.3) |
| `documents` | `array<{title, path}>` | `docs/METHODOLOGY.md`, this contract, M04 documents (paths only; not read) |

---

## 8. Geometry and coordinate reference system

### 8.1 General
- Every bundle geometry and coordinate **MUST** be EPSG:4326 (WGS 84), axis order longitude, latitude
  (RFC 7946). Sources are mixed: barangay polygons, `access_cells`, facilities and M03 fragments are
  EPSG:32651; all CSV `lon`/`lat` columns (including `cells_a3.csv`) are EPSG:4326.
- Reprojection uses GeoPandas/pyproj `to_crs("EPSG:4326")`. Distances and areas are never computed in
  the bundle; they come from the sources (computed in EPSG:32651).
- Coordinates are written with **6 decimals** (≈ 0.11 m), matching the source CSVs: values already at 6
  decimals are copied; reprojected values are rounded with Python `round(x, 6)`.

### 8.2 Barangay polygons (Q1)
- Order of operations: reproject to EPSG:4326 → simplify each polygon with Shapely
  `simplify(2e-5, preserve_topology=True)` → wrap as MultiPolygon (§7.3) → round to 6 decimals →
  validate (§7.3). The tolerance is an **angle, 2e-5 degrees**, applied in EPSG:4326, not a distance
  in metres.
- Its ground equivalent varies with latitude and direction; at the study area (≈ 10.7° N) 2e-5° is about
  2.2 m north–south and 2.2 m east–west. It is **not** a bound on displacement: measured at review, the
  simplified boundaries depart from the originals by a median 2.0 m and at most 3.9 m (Hausdorff
  distance); areas change by up to 1.0 %; neighbouring barangays no longer share identical edges (slivers
  a few metres wide). At discovery: 16,582 → 6,118 vertices; 180 valid, non-empty single-part polygons;
  0.42 MB unsimplified, 0.18 MB simplified (§5.1 serialisation, properties of §7.3).
- Simplified polygons are for **browser display only**. No area, distance, population, accessibility or
  spatial operation (join, containment, overlay) may use them, in the exporter or in the frontend.
  `area_km2` comes from the unsimplified source; the authoritative geometries in `abot_iloilo.gpkg` are
  never modified. The UI shows `DQ-SIMPLIFIED`.

### 8.3 Cells and facilities
- Cells are **points** at the cell coordinates of `cells_a3` (the 100 m WorldPop cell is not drawn as a
  square in v1: the grid geometry is not in the A3 outputs).
- Facilities are points from the facilities layer; for mapped areas the point is the
  `representative_point` (`geom_source`), not a centroid of a building outline.

### 8.4 Components: actual geometry vs bounding boxes
- **Actual fragment geometry exists for 9 fragments only** (`review/m03/validation.gpkg` ›
  `network_fragments`, MultiLineString, with `fragment_gaps` lines): F001, F002, F004, F005, F018, F060,
  F062, F100, F101. These are mapped OSM ways and may be drawn as lines with
  `geometry_kind = "mapped_fragment_geometry"`.
- **No geometry exists for the other 102 non-main components or for the main component.** v1 does not
  generate any (approved decision).
- Every component has a **bounding box** (`component_inventory.lon_min/lat_min/lon_max/lat_max`, the
  extent of its nodes). It **MUST** be exported as a `bbox` attribute with `geometry_kind =
  "bounding_box"` and **MUST NOT** be written as a GeoJSON geometry, drawn or described as a road, a
  network or a coverage area; if drawn at all, as a dashed outline with statement `DQ-BBOX`.
- The routed walk and drive networks (`network_walk` 38,864 lines, `network_drive` 20,021) are not in
  the v1 bundle.

---

## 9. Provenance, reproducibility and staleness

### 9.1 What the manifest proves and what it does not
- `source_files[].sha256` proves which bytes were read (hashed before the export, re-checked after).
- `config_sha256` proves which configuration produced them (checked against `run_meta.json` and
  `run_info.json`).
- `stage_completed_utc` and `a3_run_info.created_utc` are the times recorded by the pipeline; the
  exporter copies them and does not verify them.
- `git_commit` identifies the code version **only if** `git_working_tree_clean` is true. Otherwise the
  bundle states that the outputs may come from uncommitted code; the commit SHA is never shown alone as
  proof. `null` means unknown, never clean.
- `a3_run_info.baseline_sha256` ties the A3 layer to the A1 baseline it was built against; V-S2 proves
  the baseline files on disk still have those hashes.
- `provenance.sources[].sha256` are the hashes recorded at download; the exporter does not re-hash raw
  files (the audit does, §6.1.1).

### 9.2 Stale-bundle detection
A bundle is **stale** when any of the following holds:

1. any `source_files[].sha256` differs from the current file on disk, or a listed source is missing;
2. `config_sha256` differs from the current configuration;
3. `run_meta.json` `accessibility.completed_utc` or `component_aware/run_info.json` `created_utc` is newer
   than `generated_utc`;
4. `contract_version` differs from the version the frontend declares it supports (major mismatch →
   refuse to load; minor → warn);
5. any `files[].sha256` differs from the bundle file on disk (bundle edited after export).

`abot export-dashboard --check` (M05.1) evaluates conditions 1, 2, 3 and 5, prints the result, exits
with status 1 when stale, and writes nothing (it never modifies the bundle or any source). A future
audit check `dashboard_bundle_current` may reuse it; that change to `audit.py` is not part of M05.1.

The static frontend cannot read the repository: it evaluates condition 4 itself and **SHOULD** check
condition 5 (hashing the loaded files), and shows `generated_utc`, `git_commit`,
`git_working_tree_clean` and the audit block in the provenance section with the note "Currency against
the repository is checked with `abot export-dashboard --check`". It **MUST NOT** claim that the bundle is
current.

---

## 10. Exporter validation requirements (M05.1)

### 10.1 Export procedure (no partial bundle)

1. Clean up an interrupted run (rules in §10.1.1).
2. Hash every source file of §7.1.1 (`source_files`); run the V-S checks; obtain the audit (§6.1.1)
   unless `--skip-audit` is given, and stop (step 5) if its outcome is `fail` or its status is `error`.
3. Build the bundle in memory and write it to a new directory `data/processed/dashboard/.v1.tmp-<id>/`
   (same parent as `v1/`, so renames stay on one filesystem); `manifest.json` is written last.
4. Run every check below against the files **as written** (re-read from disk), then re-hash the sources
   (V-X1).
5. If any check fails: delete the temporary directory, leave `v1/` untouched, report every failed check
   and exit with a non-zero status. Validation never repairs source data or output values.
6. If all pass: rename `v1/` (if present) to `.v1.old-<id>/`, rename `.v1.tmp-<id>/` to `v1/`, delete
   `.v1.old-<id>/`. If the second rename fails, rename `.v1.old-<id>/` back to `v1/` and fail.

The replacement is two renames, not one atomic operation (Windows cannot rename over a non-empty
directory): between them `v1/` may briefly be absent. Any reader **MUST** treat a missing `v1/` or a
`v1/` without `manifest.json` as "no bundle", never as a partial one. A failed export never removes the
previous valid bundle. Every failed check is reported (no truncation).

#### 10.1.1 Recovery of an interrupted run

Only **exporter-owned** directories are ever touched: entries directly in `data/processed/dashboard/`
whose names match exactly `.v1.tmp-<id>` or `.v1.old-<id>`, `<id>` being 12 lowercase hexadecimal
characters. Every other file or directory there is left alone. A backup is **complete** when it holds a
`manifest.json` that parses and every file of its `manifest.files` with the recorded size and SHA-256;
`v1/` is **safely present** when it is complete by the same test.

| State at the start of an export | Action |
|---|---|
| `.v1.tmp-<id>/` (any number) | deleted: a temporary directory is never a bundle |
| `v1/` safely present, `.v1.old-<id>/` present | each backup deleted (left by a crash after the second rename) |
| `v1/` present but **not** safely present, `.v1.old-<id>/` present | nothing deleted; the backups are reported and kept; the export continues (on success, `v1/` is replaced as usual and the backups are reported again) |
| `v1/` missing, exactly one complete `.v1.old-<id>/` | renamed back to `v1/` (crash between the two renames), then the export continues |
| `v1/` missing, several backups or an incomplete one | nothing renamed or deleted; the export stops with a non-zero status and lists them for manual resolution |

`--check` (§10.3) applies the same tests read-only: when `v1/` is missing it reports whether a complete
backup exists and that the next export restores it, and it never renames or deletes anything.

### 10.2 Checks

Every check is computed by the exporter, all rows and all mapped columns (no sampling). Tolerances are
the ones stated; "equal" without a tolerance means exactly equal after JSON round-trip.

| ID | Check |
|---|---|
| V-S1 | Every source file of §7.1.1 exists; the data-loading code opens no other path and none listed in R13. |
| V-S2 | `run_info.baseline_sha256` equals the SHA-256 of each listed baseline file on disk (6 files at discovery, all matching at review). |
| V-S3 | `config_sha256` equal across the current config, `run_meta.json` (all stages) and `run_info.json`. |
| V-S4 | `review/m04/taxonomy_check.json` reports `identical: true` and `components_compared: 112`. |
| V-S5 | (1.0.1) The targeted gap snapshot is used exactly as `review/m04/snapshot_status.json` declares: `obtained` is a boolean; no corridor table is present when it is false; the corridor table is non-empty unless the status records 0 link candidates; `gap_investigation.snapshot_obtained` equals `obtained` on every row; the latest `osm_targeted/` entry of `data/raw/manifest.json` is the snapshot that was used (`response_sha256`), or there is none when `obtained` is false. Any mismatch blocks the export with "re-run `abot components`". |
| V-P1 | Population: Σ `cells_a3.pop` = Σ `access_cells.pop` = Σ `barangay_access_a3.pop_total` = Σ `barangay_access.pop_total` = `run_info.population_total` (±0.5). |
| V-P2 | Per barangay: Σ four A3 category pops = `pop_total` (±0.5); A3 and A1 `pop_total` equal (±0.05). |
| V-P3 | A3 `pct_*` categories sum to 100 ± 0.02 per barangay and citywide. |
| V-I1 | `adm4_pcode`: 180 unique, identical sets in geometry, A3, A1. `cell_id`: 8,035 unique, identical in `cells_a3` and `access_cells`. `fid_key`: 937 unique in the facilities layer, the same set in `facility_roles`. Components: 112 unique `fragment`. |
| V-I2 | No join drops or duplicates a record (row counts before and after every join). |
| V-C1 | For every group, recomputed independently from `cells_a3` (whole-cell `pop`, `t_walk_{g}_citywide`), never from the written bins: (a) the cumulative share at 10, 15 and 30 min equals `citywide_a3` `walk_{g}_pct_le{N}` col `A3`; (b) the population-weighted mean of the unbinned times, rounded to 2 decimals, equals `walk_{g}_mean_min` col `A3`; (c) every bin `k` equals the rounded population with `k − 1 < t ≤ k` (bin 1 also `t = 0`) and the open bin the rounded population with `t > 60`; (d) every cumulative point 1 … 60 equals 100 × Σ pop with `t ≤ k` / `pop_total` rounded to 2 decimals; (e) the final point (`minutes: null`) equals 100 × Σ pop with a citywide time / `pop_total` rounded to 2 decimals, and is ≥ the 60-minute point; (f) `pop_with_time` equals `citywide_a3` `pop_network_connected` (±0.05), and `pop_total` equals Σ `cells_a3.pop` (R7). |
| V-C2 | Every value copied from a source equals the source value (every row, every mapped column), and every convenience copy in `barangay_indicators.json` equals its `values` entry. |
| V-C3 | For every group, the factor-1.0 row of `drive_speed_sensitivity.csv` equals its recomputation from `access_cells` with the rules of `accessibility.drive_sensitivity` (whole-cell `pop`, `conn_status == "connected"`, `t_drive_{g}` not null): `mean_min` (2 decimals), `pct_le5/10/15` (1 decimal), `pct_not_connected` (2 decimals). Verified at review: 0 mismatches. Validation only (Q6). |
| V-N1 | No NaN/Infinity in output; every source null is `null`; no null became `0`; no field is omitted (§5.2). |
| V-N2 | `walk_citywide` non-null only for `network_connected` cells; `walk_internal` non-null iff `locally_connected`/`access_uncertain`; `drive_a1` null iff `a1_conn_status ≠ connected`. |
| V-R1 | Every `%` within [0, 100]; every minute ≥ 0; every count ≥ 0. |
| V-G1 | All geometries valid, non-empty, EPSG:4326, within the study-area bounds (lat 10.6–10.85, lon 122.45–122.7, `LAT_RANGE`/`LON_RANGE` of `fetch/targeted.py`). Barangay polygons: 180, MultiPolygon, source part count, checked after rounding, never repaired. |
| V-G2 | Facility coordinates equal `facilities.csv` `lon`/`lat` within 1e-6°; cell coordinates equal `cells_a3` `lon`/`lat`. |
| V-G3 | Exactly 9 features with `geometry_kind = "mapped_fragment_geometry"` and 9 with `"gap_line"`; no component bounding box written as a geometry. |
| V-K1 | Cell layout per §7.5.1: `count` is the value the rule yields; every chunk ≤ `max_file_bytes` (unless `count` = 1 and the single file fits); chunks contiguous in `cell_id` order, no overlap or gap; Σ chunk features = 8,035; every chunk listed in `cells_layout` and `files` with its `bytes` and `sha256`. |
| V-Q1 | Every indicator id used in any file exists in `manifest.indicator_catalog`; every catalogue entry has levels, unit, numerator, denominator or population described, and role. |
| V-Q2 | Every analysis-only record carries `analysis_only: true` and, where applicable, `applied: false`. |
| V-Q3 | Every figure inserted into a statement or limitation (§6.3, §11) equals its source value. |
| V-A1 | Audit gate (§6.1.1): the written audit block is `obtained`/`pass`, `obtained`/`warn` or `not_run`; `not_run` only when `--skip-audit` was given; `counts` non-null iff `obtained` and equal to the counts of `findings` statuses; `findings` holds exactly the WARN findings; `manifest.known_issues` holds `AUDIT-WARN` iff `warn` and `AUDIT-NOT-RUN` iff `not_run`. |
| V-M1 | `manifest.files` hashes and sizes match the written files; `contract_version` = `1.0.0`. |
| V-X1 | After export, every source file of §7.1.1 has the SHA-256 recorded in `source_files` before the export (analytical outputs byte-identical). |

### 10.3 Command line

```
abot [--config PATH] export-dashboard [--skip-audit] [--check]
```

| Invocation | Effect | Exit status |
|---|---|---|
| `abot export-dashboard` | runs the audit, exports per §10.1; blocked by audit `fail`/`error` or any failed check | 0 written; 1 blocked or failed |
| `abot export-dashboard --skip-audit` | as above without the audit; the bundle records `audit.status = not_run` and `AUDIT-NOT-RUN` | 0 / 1 |
| `abot export-dashboard --check` | read-only staleness check of the existing `v1/` (§9.2 conditions 1, 2, 3, 5); runs no audit, writes nothing; `--skip-audit` has no effect | 0 current; 1 stale or no bundle |

The command loads the settings with `create_dirs=False` and only works on the baseline configuration
(no `paths.run_name`): an experiment configuration is refused, because the bundle describes the active
baseline only.

---

## 11. Known limitations the dashboard must surface

Figures in this list are discovery values; in the bundle they are filled from the sources (§6.3).

1. A1 is optimistic and A3 is a reporting scenario: neither is observed travel or a verified bound.
2. A3 is walking only; driving is A1 only, uncongested, a lower bound, assumes a car. No public transport.
3. Facility inventory is OSM, unverified for all 180 barangays; evacuation, transport and government are
   descriptive only; 7 of 14 possible duplicate pairs pending review, 2 likely duplicates not merged.
4. Population: census-anchored WorldPop with fractional barangay allocation; `rel_population` low in 27
   and caution in 51 barangays; cells cannot be summed to barangays.
5. 3,472.3 residents unconnected and 5,206.0 locally connected (A3); Calahunan and Hibao-an Sur resolved
   separately and included in all totals.
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

## 13. Schema questions (decision record)

All questions are resolved for M05.1. Decisions marked "for approval" are the reviewer's proposals.

| ID | Question | Decision | Where |
|---|---|---|---|
| Q1 | Barangay simplification tolerance | **Resolved:** 2e-5° (an angle in EPSG:4326, ≈ 2.2 m at the study area, not a displacement bound), Shapely `preserve_topology=True` after reprojection, display only; 180 valid features, full `adm4_pcode` set, `area_km2` from the unsimplified source | §7.3, §8.2 |
| Q2 | Indicator values keyed by catalogue id or nested by scenario/mode/group? | **Resolved:** catalogue ids (single semantic registry); `levels` added to the catalogue; city records carry `indicator_id` | §4.1, §7.2, §7.4 |
| Q3 | How the exporter obtains the audit summary | **Resolved (approved 2026-11-01):** in-process `abot.audit.Audit(..., hashes=True).run()` (verified read-only); `pass` and `warn` allow the export (`warn` recorded as `AUDIT-WARN`), `fail` and `error` block it, `not_run` only with `--skip-audit` (recorded as `AUDIT-NOT-RUN`); never invented | §2 R13, §6.1.1, §10.1, §10.3, V-A1 |
| Q5 | Bin width of `walk_distribution` | **Resolved (approved 2026-11-01):** 1-minute right-closed bins 1 … 60 and an open bin "> 60 min" (fixed cap); cumulative share of all residents at 1 … 60 min plus a final point that includes the open bin | §7.2 |
| Q6 | Is `drive_speed_sensitivity.csv` (factor 1.0) the citywide A1 drive source? | **Resolved:** yes; checked against `access_cells` by V-C3 (0 mismatches at review); factors 1.5 / 2.0 are evidence-only sensitivity ids | §4.1, §7.2, V-C3 |
| Q7 | Export census / WorldPop comparison fields? | **Resolved:** no in v1 (full list in §7.4) | §7.4 |
| Q8 | Export A1 per-cell walking times? | **Resolved:** no in v1 | §7.5 |
| Q9 | Cell file size and layout | **Resolved:** one logical dataset; measured 6.94 MB as one file (> 4 MB), so deterministic `cell_id`-ordered chunks of ≤ 4,000,000 bytes (2 at discovery), described in `manifest.cells_layout` | §5.1, §7.1, §7.5.1, V-K1 |

Resolved during authoring (read-only checks): `abot.__version__` exists (`0.1.0`); the destination rule
is role-level (§7.6, reproduces the inventory for all 10 groups); `n_{group}` counts any tier (§4.3).

## 14. Versioning

- **Patch** (1.0.x): wording, statements, validation additions; no field change.
- **Minor** (1.x.0): new optional fields or datasets; old clients keep working.
- **Major** (x.0.0): renamed, removed or re-typed fields, or changed meaning of any indicator,
  denominator or null. The bundle directory follows the major version (`v1/`, `v2/`).
- The number of cell chunks follows from the data size (§7.5.1) and is not a version change.

**Revisions**
- **1.0.1** (2026-11-02, Milestone 06.2A; patch).
  - The targeted gap snapshot (`abot fetch-gaps --allow-download`) becomes optional, declared
    evidence: §7.1.1 reads `snapshot_status.json` and the corridor table only when a snapshot was
    used.
  - New validation V-S5.
  - `provenance.targeted_snapshot` and the `gap_evidence` path fields are documented as `null`
    without a snapshot, which v1.0.0 code already produced.
  - No field is added, renamed or re-typed in output that a 1.0.0 client reads, and no indicator
    changes. The snapshot never affects a component class or indicator: the A3 layer is written
    before `abot components` reads it, and a run without it gives byte-identical A3 files.
- **1.0.0** (2026-10-31): first release.
