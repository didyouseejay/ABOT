# ABOT — Project Documentation and Research Log

This file is the running record of the ABOT project: what was built, how, why each design
decision was made, and what the results and limitations are. It is written to support a later
research paper, so it keeps methods, parameters, data provenance and validation figures in one
place. **Every change or addition to the project is logged in the [Change log](#10-change-log)
at the end**, newest first.

- Repository: `abot` (Python package `abot`, v0.1.0)
- Author: Carl John L. Coopera (GitHub: didyouseejay; carljohn.coopera@wvsu.edu.ph), West Visayas State University
- Licence: source code MIT ([LICENSE](LICENSE), since Milestone 06.1); data keeps its own licences
  ([docs/ATTRIBUTION.md](docs/ATTRIBUTION.md))
- Study area: Iloilo City, Iloilo, Western Visayas (Region VI), Philippines
- Current state: **Milestone 06.2A follow-up, uncommitted** (2026-11-02): archive-aware validation.
  Without any `data/archive/` the archive-dependent checks are NOT PERFORMED, never passed, and a
  fresh clone can export; they stay strict whenever archives exist (contract `abot-dashboard`
  1.1.0). Before that, **Milestone 06.2A** (commit `8ff8aea`): the targeted gap snapshot became
  optional, declared evidence (check V-S5, contract 1.0.1); fresh-clone workflow audit in
  [docs/M06_2A_REPRODUCIBILITY.md](docs/M06_2A_REPRODUCIBILITY.md). No analytical result changed.
  Before that, **Milestone 06.1** (commit `3073524`): documentation, licensing and
  portfolio presentation (README rewrite, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), MIT
  `LICENSE`, attribution, screenshots, unused `chart.js` and `react-leaflet` removed). No analytical
  code, method or result changed. Before that, **Milestone 06.0** (commit `daa2f69`): technical audit
  and portfolio baseline ([docs/M06_TECHNICAL_AUDIT.md](docs/M06_TECHNICAL_AUDIT.md)). Before that,
  **Milestone 05.3** (commit `56fbd64`): the dashboard front end redesigned for
  residents and barangay/city officials (plain language, five public sections, street/satellite
  background maps); the technical pages move under "For researchers". No analytical result changed.
  Before that, **Milestone 05.2 S3** (2026-11-01): dashboard application shell
  (navigation, provenance bar, interface states, seven placeholder sections) on the verified
  bundle loader of S0–S2 (commit `c913983`); no analytical page yet.
  Before that, **Milestone 05.1** (2026-11-01): dashboard data exporter
  `abot export-dashboard` (contract `abot-dashboard v1.0.0`) writes a validated, derived bundle to
  `data/processed/dashboard/v1/`; no analytical result changed. Before that, **Milestone 04 +
  follow-up** (2026-10-31): component-aware (A3)
  walking reporting layer added next to the unchanged baseline (A1, the optimistic connectivity
  scenario); access classification for reporting only; `e7_buffer_3km` originals removed after
  verified archiving; 7 approved duplicate classifications recorded (7 pending). The targeted
  Overpass snapshot was obtained: F001 and F100/F101 are linked to the main network in OSM only
  through `access=private`, gated corridors (reviewed, nothing applied). The routing, the largest-component
  baseline and the 250 m connector are unchanged. Builds on Milestone 03 (commit `8b464a4`) and 02B (commit `3e85764`: 3 km
  baseline, census-anchored weights, reliability flags, `abot audit`, manual review files)
- Detailed references: [docs/METHODOLOGY.md](docs/METHODOLOGY.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md),
  [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), [docs/MILESTONE_02_ANALYTICAL_AUDIT.md](docs/MILESTONE_02_ANALYTICAL_AUDIT.md),
  [docs/MILESTONE_02_VALIDITY_ASSESSMENT.md](docs/MILESTONE_02_VALIDITY_ASSESSMENT.md),
  [docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md), [docs/MILESTONE_02B_RESULTS.md](docs/MILESTONE_02B_RESULTS.md),
  [docs/MILESTONE_03_RESULTS.md](docs/MILESTONE_03_RESULTS.md), [docs/MILESTONE_04_RESULTS.md](docs/MILESTONE_04_RESULTS.md),
  [docs/MILESTONE_04_FOLLOWUP_RESULTS.md](docs/MILESTONE_04_FOLLOWUP_RESULTS.md)

---

## Contents

1. [Project overview](#1-project-overview)
2. [Study area](#2-study-area)
3. [Data sources](#3-data-sources)
4. [System architecture](#4-system-architecture)
5. [Methodology](#5-methodology)
6. [Quality assurance and validation](#6-quality-assurance-and-validation)
7. [Results](#7-results)
8. [Limitations and threats to validity](#8-limitations-and-threats-to-validity)
9. [Reproducibility](#9-reproducibility)
10. [Change log](#10-change-log)
11. [Notes for the paper](#11-notes-for-the-paper)

---

## 1. Project overview

**ABOT** is a geospatial accessibility and public-infrastructure intelligence system for Iloilo
City. It estimates how long residents take to reach the nearest essential public facility on
foot and by car, and summarises the results for each of the city's 180 barangays.

### Problem

Planners need to know which neighbourhoods are poorly served by health, education, safety and
other public facilities. Straight-line (Euclidean) distance understates real travel time because
it ignores the street network, rivers, and one-way streets. ABOT uses the road network and a
high-resolution population grid instead, so accessibility is measured where people actually live.

### Approach in one paragraph

Barangay boundaries (OCHA COD-AB) define the study area. Population weights are census-anchored:
each barangay's PSA 2020 census count is spread over its 100 m cells following the WorldPop 2020
pattern, and cells straddling barangay limits are split by area. The original WorldPop estimates
are kept alongside. OpenStreetMap provides the
walk and drive road networks, barrier features (water, waterways, coastline) and the locations of
facilities in nine categories, each refined into sub-types with a reporting tier. Every cell is
joined to the nearest walkable edge whose straight connector does not cross water. For each
indicator group and mode, one multi-source Dijkstra search computes the travel time from every
connected 100 m cell to its nearest mapped destination. Cell times are then aggregated to
population-weighted barangay indicators. Shares use all residents, and residents without a
connection are reported separately. Each barangay carries separate population, network and
facility-inventory reliability flags.

### Facility categories

`health`, `pharmacy`, `education`, `safety`, `government`, `market`, `finance`, `transport`,
`evacuation`. Since Milestone 02 each category has sub-types with a reporting tier (indicative,
descriptive or excluded). Travel-time indicators are computed only for ten indicator groups of
indicative sub-types. See [Section 5.4](#54-facilities).

---

## 2. Study area

| Property | Value | Source |
|---|---|---|
| City | Iloilo City (highly urbanised city) | — |
| COD-AB adm3 p-code | `PH0603022` | COD-AB v03 |
| Barangays | 180 | COD-AB; matches PSA |
| Area (COD-AB polygon) | 72.63 km² | computed, EPSG:32651 |
| Smallest / largest barangay | 0.0141 km² / 3.65 km² | computed |
| Population, 2020 census (= census-anchored weights, primary since M02B) | 457,626 | PSA 2020 |
| Population, WorldPop 2020 (original; fractional allocation / M01 centre rule) | 467,501 / 468,282 | WorldPop R2025A |
| Population, WorldPop 2026 projection (original; fractional / centre rule) | 491,633 / 492,459 | WorldPop R2025A |

72.63 km² is the area of the COD-AB v03 polygon, not an official land area. The often-cited
78.34 km² appears only in secondary sources (dated 2013), and no open boundary reproduces it. The
validity assessment showed that the coastline is **not** the cause: COD-AB is a land polygon, with
only 0.045 km² seaward of the OSM coastline. COD-AB and the OSM admin boundary do differ by about
2.6 km² on the northern inland boundary (Dungon, Lanit, Bito-on, Tacas), which holds about 0.5% of
the population. See
[docs/MILESTONE_02_VALIDITY_ASSESSMENT.md](docs/MILESTONE_02_VALIDITY_ASSESSMENT.md) §3.

---

## 3. Data sources

All data is open. None of it is stored in the git repository. `abot fetch` downloads it again,
and `data/raw/manifest.json` records the exact URL, retrieval time, size and SHA-256 for every file.

| Dataset | Provider | Version / date | Licence | Use |
|---|---|---|---|---|
| Administrative boundaries (COD-AB) | OCHA / HDX, from NAMRIA & PSA | v03; HDX modified 2026-05-28 | CC BY-IGO | City and barangay polygons |
| 2020 Census population by barangay | PSA via HDX | HDX modified 2023-09-21 | CC BY | Barangay totals of the primary (census-anchored) weights. Never used as validation of WorldPop, which was built from it |
| Population counts, constrained 100 m | WorldPop | Global2 R2025A v1 (**alpha** release, Sept 2025; DOI 10.5258/SOTON/WP00839), years 2020 and 2026 | CC BY 4.0 | 2020: within-barangay pattern for census anchoring; 2026: projection, sensitivity only |
| 2024 POPCEN population by barangay | PSA (PSGC page, read manually 2026-10-31) | Reference date 1 July 2024; PSGC as of 30 Sept 2026 | CC BY 4.0 | Validation only; **not yet used by the pipeline** |
| Road networks, barriers and facilities | OpenStreetMap contributors (via Overpass / osmnx) | Retrieved 2026-10-31; snapshot timestamps in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | ODbL 1.0 | Routing, connection checks and destinations |

**WorldPop R2025A inputs for the Philippines** (from WorldPop's census-sources sheet): PSA 2020
census at **barangay level** (admin 4; 42,058 units, nested to 38,911); the 2010 census was not used.
National totals are aligned to UN WPP 2024 at a 1 January reference date. All years other than 2020
are modelled. Years after 2020 are projections with no newer population input.

### Provenance of the Milestone 01 run (retrieved 2026-10-31 UTC)

| File | Bytes | SHA-256 |
|---|---|---|
| `cod_ab/phl_admin_boundaries.gdb.zip` | 360,586,879 | `e7fc18f1383a21066ecfbe595c5c1d77375c93341dedf7284f09d66dbd28c5ad` |
| `census_2020/2020-census-total-popn_single-age_malefemale_admin4.xlsx` | 48,727,855 | `7865dc000fab8308a6f57f9fe087024b99e9df12df7e9ff61c47c4dbf2263a64` |
| `worldpop/phl_pop_2026_CN_100m_R2025A_v1.tif` | 63,798,093 | `23b71c8e196a072a55b8d3596d589e4a8c7bf295e9b8944a6b937620f99c6751` |
| `worldpop/phl_pop_2020_CN_100m_R2025A_v1.tif` | 63,095,801 | `6a98ec3e2b9389535d2b9d9708fb9f5700aabf2a34f5a7fbc093dbc32724cac2` |

The raw Overpass responses are cached under `data/raw/osm_cache/`. OSM changes continuously, so
the exact snapshot is defined by that cache. Since Milestone 02, each response's Overpass
`timestamp_osm_base`, SHA-256, query and the runs that used it are recorded in `manifest.json` and
`data/interim[/<run>]/osm_provenance.json`.

External facility registries (DOH NHFR, DepEd masterlist, Iloilo City CDRRMO evacuation centres)
were researched but **not integrated**; see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) section 4.

**Licence obligation:** if a database derived from OSM is shared publicly, it must also be released
under the ODbL. Maps and figures must credit "© OpenStreetMap contributors". Library, font and
map-tile licences are listed in [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md) (M06.1).

---

## 4. System architecture

### Pipeline

```
abot fetch   ->  data/raw/          (COD-AB, census, WorldPop + manifest.json)
abot build   ->  boundaries -> population -> osm -> accessibility
                 data/interim/      (census CSV cache, GraphML networks, per-stage QA JSON)
                 data/processed/    (GeoPackage + CSVs)
abot report  ->  data/processed/qa_report.md, abot_map.html
abot all     ->  fetch + build + report
abot compare BASE VARIANT  ->  data/processed/comparisons/<name>/  (city-wide, barangay, cell)
abot review  ->  data/processed/review/  (manual-review files and maps; changes no data)
abot validate -> data/processed/review/m03/  (desk evidence for the review items; Overpass cache only)
abot audit   ->  console (or --output FILE outside data/): PASS / WARN / FAIL / INFO; read-only
```

Each build stage records its completion time and configuration fingerprint in
`data/interim[/<run>]/run_meta.json`, which `abot audit` uses to detect stale outputs.

Experiment configs (`config/experiments/*.yaml`) extend `settings.yaml` and set `paths.run_name`,
so their outputs go to `data/interim/<run>/` and `data/processed/<run>/`. `data/raw/` is shared.

You can run single build stages with `abot build --only population osm`.

### Code layout

| Module | Responsibility |
|---|---|
| [src/abot/cli.py](src/abot/cli.py) | Command-line entry point (`fetch`, `build`, `report`, `all`, `compare`, `review`, `validate`, `components`, `fetch-gaps`, `audit`, `export-dashboard`) |
| [src/abot/config.py](src/abot/config.py) | Loads [config/settings.yaml](config/settings.yaml), resolves data paths |
| [src/abot/fetch/common.py](src/abot/fetch/common.py) | Streaming download in 1 MiB chunks, cache check, provenance manifest with SHA-256 |
| [src/abot/fetch/sources.py](src/abot/fetch/sources.py) | Finds resources through the HDX CKAN API; WorldPop URL template |
| [src/abot/boundaries.py](src/abot/boundaries.py) | Extracts the city and its barangays from the national GeoDatabase |
| [src/abot/population.py](src/abot/population.py) | WorldPop cells, fractional barangay allocation, census-anchored weights |
| [src/abot/osm.py](src/abot/osm.py) | Walk/drive graphs, edge speeds, facility extraction and categorisation |
| [src/abot/accessibility.py](src/abot/accessibility.py) | Snapping, multi-source Dijkstra, barangay indicators |
| [src/abot/qa.py](src/abot/qa.py) | Per-stage QA records (`ok` / `value` / `note`) |
| [src/abot/report.py](src/abot/report.py) | Markdown QA report and folium interactive map |
| [src/abot/compare.py](src/abot/compare.py) | Comparison of two runs (Milestone 02) |
| [src/abot/reliability.py](src/abot/reliability.py) | Barangay reliability flags and the facility-inventory table (Milestone 02B) |
| [src/abot/review.py](src/abot/review.py) | Manual-review files and maps (Milestone 02B); logged, reversible recording of approved duplicate decisions, and pair-checked carry-over (M04 follow-up) |
| [src/abot/audit.py](src/abot/audit.py) | Read-only audit of inputs, outputs, staleness (including experiment runs) and consistency (Milestone 02B, 03) |
| [src/abot/validation.py](src/abot/validation.py) | Desk evidence for duplicates, unconnected cells, network fragments and disconnected facilities (Milestone 03) |
| [tests/test_core.py](tests/test_core.py) | Offline unit tests (Milestone 01) |
| [tests/test_m02.py](tests/test_m02.py) | Offline regression tests for the Milestone 02 corrections |
| [tests/test_m02b.py](tests/test_m02b.py) | Offline regression tests for Milestone 02B |
| [src/abot/access.py](src/abot/access.py) | Pedestrian access taxonomy from OSM tags: mapped access status, public pedestrian status, authorised group, verification flag and reason per way or gate; shared by the component evidence and the snapshot corridor analysis (Milestone 04 methodology review; reporting only) |
| [src/abot/components.py](src/abot/components.py) | Component inventory, network-approach comparison (A1/A2/A3), the A3 component-aware reporting layer (`data/processed/component_aware/`), access classification and access-tag impact, snapshot gap evidence, facility review summary (Milestone 04; never changes the baseline) |
| [src/abot/archive.py](src/abot/archive.py) | Copy superseded outputs to `data/archive/` with a SHA-256 record, independent verification, and removal of originals only after verification (Milestone 04) |
| [src/abot/fetch/targeted.py](src/abot/fetch/targeted.py) | Targeted Overpass query for the network gaps: build, validate, download only with `--allow-download`; snapshot evidence and link candidates (Milestone 04) |
| [tests/test_m03.py](tests/test_m03.py) | Offline regression tests for Milestone 03 |
| [tests/test_m04.py](tests/test_m04.py) | Offline regression tests for Milestone 04 |
| [src/abot/dashboard_data.py](src/abot/dashboard_data.py) | Dashboard data bundle per [docs/DASHBOARD_DATA_CONTRACT.md](docs/DASHBOARD_DATA_CONTRACT.md): read-only over the outputs, audit gate, deterministic cell chunks, validation of the written files, temporary-directory install, `--check` staleness report (Milestone 05.1) |
| [tests/test_m05.py](tests/test_m05.py) | Regression tests for Milestone 05.1 and its M05.2 S0 hardening (28 offline unit tests; 2 end-to-end tests that read the real outputs read-only, write only to a temporary directory and are skipped without data) |
| [tests/test_m06.py](tests/test_m06.py) | Regression tests for Milestone 06.2A: the optional, declared targeted snapshot in the exporter (V-S5) and the archive-aware validation of the follow-up (audit NOT PERFORMED, V-S4 `not_performed`, strict with archives): 17 offline unit tests and 3 end-to-end tests on the real outputs (temporary directory only; skipped without data) |
| [dashboard/](dashboard/) | Static frontend (Milestone 05.2): React 19 + Vite 8 + TypeScript 7 (strict). `vite/bundlePlugin.ts` serves the bundle in development (read per request, never watched) and copies it, hash-checked, into `dist/data/v1/` at build; `src/contract/` types and version check; `src/data/` loader, validation, SHA-256, React context; `src/model/` catalogue, scenario names, formatting, distribution view, audit/Git states; `test/` Vitest suite with a hand-made fixture bundle. S3: `src/routes.ts` (section registry), `src/model/shell.ts` (provenance items). S4–S7: `src/components/` (top bar, provenance colophon, caveat notes, shared UI, interface states), `src/pages/` (the seven pages), `src/model/{view,values,labels,ramps}.ts`, `src/map/leaflet.ts`, `src/styles/{tokens,app}.css` |

### Outputs (`data/processed/`)

| File | Contents |
|---|---|
| `abot_iloilo.gpkg` | Layers: `city`, `barangays`, `pop_cells`, `pop_pieces`, `network_walk`, `network_drive`, `barriers`, `facilities`, `facility_roles`, `access_cells`, `barangay_access` (Milestone 01/02: `pop_cells_<year>`, `access_cells_2026`) |
| `barangay_access.csv` | One row per barangay: population (adjusted and original), connected / unconnected residents, facility counts, travel-time indicators, reliability flags |
| `facility_inventory.csv` | Per indicator group: destinations in and outside the city, connected, unnamed, not decided by a tag rule, pending duplicate review; inventory status |
| `drive_speed_sensitivity.csv` | City-wide car-time shares with the drive-network leg × 1, 1.5, 2 |
| `review/` | Manual-review files (duplicates, unconnected cells), `review.gpkg`, two HTML maps; status `pending` |
| `review/m03/` | Desk-validation evidence (`abot validate`): duplicate assessment, cell diagnostics, network fragments, pond polygons, disconnected facilities, tolerance sensitivity, `validation.gpkg`, `validation_map.html` |
| `facilities.csv` | Every mapped facility with OSM id and tags, sub-type, tier, classification status and reason |
| `facility_exclusions.csv` | Merged points, flagged possible duplicates, unmatched features |
| `barangay_population.csv` | Per barangay: PSA 2020 census, census-adjusted total and anchoring factor, original WorldPop 2020/2026 (fractional and centre rule), cell counts, share from straddling cells |
| `qa_report.md` | All validation checks (PASS / WARN / info) and data provenance |
| `comparisons/<name>/` | Output of `abot compare` |
| `dashboard/v1/` | Dashboard data bundle (`abot export-dashboard`, contract `abot-dashboard v1.0.0`): `manifest.json`, `city.json`, `barangays.geojson`, `barangay_indicators.json`, `cells-NNN.geojson` (chunks ≤ 4,000,000 bytes), `facilities.geojson`, `network.json`, `provenance.json`. Derived presentation data only; the files above stay authoritative |

Column definitions: [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).
| `abot_map.html` | Interactive map: travel-time and population choropleths, facility markers |

### Software environment

- Python 3.13 (3.13.18 in the Milestone 01 run), managed with **uv**. Dependencies are pinned in `uv.lock`.
- Key libraries (versions used): geopandas 1.2.0, osmnx 2.1.1, networkx 3.7, rasterio 1.5.2,
  shapely 2.2.0, pyproj 3.8.0, numpy 2.5.4, pandas 3.1.0, scipy 1.18.1, folium 0.20.0.
- Dev tools: pytest, ruff. No dependencies were added in Milestone 02 or 02B.
- Frontend (`dashboard/`, Milestone 05.2): Node 24.18.0, npm 10.8.1; versions pinned in
  `dashboard/package.json` and `dashboard/package-lock.json`. Runtime: react 19.3.1, react-dom 19.3.1,
  leaflet 1.9.4 (used directly, no React wrapper), @fontsource/atkinson-hyperlegible 5.3.0
  (self-hosted font, M05.3); charts are hand-built SVG. `react-leaflet` 5.0.0 and `chart.js` 4.6.1
  were listed until M06.1 but never imported, and were removed. Development: vite 8.3.5,
  @vitejs/plugin-react 6.1.2, typescript 7.0.2, vitest 5.0.5, @types/react 19.3.0,
  @types/react-dom 19.3.0, @types/leaflet 1.9.22, @types/node 24.19.2 (types only).
- Run npm scripts from PowerShell or cmd. In the Git Bash used by the coding assistant,
  `npm run …` exits 1 without output; `npx vite build` works there.
- Hardware target: CPU-only laptop with 8 GB RAM. A full build from the cache takes about 40 s
  (3 km buffer) after the data has been downloaded (about 550 MB).

---

## 5. Methodology

All distance and area calculations use **WGS 84 / UTM zone 51N (EPSG:32651)**, in metres.
Parameters live in [config/settings.yaml](config/settings.yaml). This section summarises the
current (Milestone 02) method and notes what changed since Milestone 01. The full reference is
[docs/METHODOLOGY.md](docs/METHODOLOGY.md).

### 5.1 Boundaries

1. Only features with `adm3_pcode = 'PH0603022'` are read from the COD-AB national GeoDatabase,
   for both the adm3 (city) and adm4 (barangay) layers. Because of this attribute filter, the
   national file is never fully loaded into memory.
2. Layer names differ between COD-AB releases, so layers are matched by the suffix
   `admin{n}` / `adm{n}`.
3. Geometries are reprojected to EPSG:32651 and repaired with `make_valid()`.
4. Checks: exactly one city, 180 barangays, unique p-codes, valid geometries, the barangay union
   within 1% of the city area, and total overlap below 0.01 km².

### 5.2 Population

*Milestone 02B (validity assessment P1, P2).*

1. **Raster read:** `rasterio.mask` crops the 2020 and 2026 WorldPop rasters to the city polygon
   (`all_touched`, so every cell touching the city is read). The two rasters must share one grid,
   and this is checked.
2. **Cells:** every cell with population > 0 in either year. The id `r<row>c<col>` is the cell's
   row and column in the national raster.
3. **Fractional allocation:** each cell square is intersected with the barangay polygons, giving
   `pop_pieces` (cell, barangay, area fraction). A cell's population is split by area. The part
   outside the city is not counted (about 1.0% of the touching cells' population), so neighbouring
   municipalities are not double-counted. Milestone 01/02 assigned each whole cell to the barangay
   containing its centre. In the 27 barangays with ≤ 5 cell centres, this changes totals by a
   median of 15%.
4. **Census join:** the PSA 2020 file uses old 9-digit PSGC codes (e.g. `PH063022001`). These are
   converted to COD-AB p-codes by padding the province code to 3 digits (`PH0603022001`); 180/180
   match. The 2023 10-digit PSGC (`BgyCode_new`) uses a different scheme and is kept as
   `psgc_2023` for reference only.
5. **Weights.** Three sets are kept side by side, and their names say which is which:
   - `pop_census2020_adj` (**primary**, adjusted): within each barangay, WorldPop 2020's piece
     values are rescaled so the barangay sums to its PSA 2020 count. The factor census / WorldPop
     2020 ranges from 0.19 to 4.48 (median 0.96). Census population in a barangay with no WorldPop
     2020 cells would be reported as `census_unallocated`, never spread elsewhere; there are none.
   - `pop_wp2020`, `pop_wp2026`: the original WorldPop R2025A estimates (2026 = projection).
   - `pop` is a copy of the configured weight (`population.primary_weight`: `census_2020_anchored`
     | `worldpop_2020` | `worldpop_2026`).
6. **Diagnostics, not validation:** the WorldPop 2020 vs census differences (city +2.16%; barangay
   median |difference| 30.5%; 56 barangays above 50%) are reported as measures of unit alignment.
   WorldPop used this census as an input, so they are not accuracy tests.
7. **Reference year.** The barangay totals are 2020 (census). The 2026 projection adds no barangay
   information (the validity assessment §1 found rank correlation 0.05 with PSA 2020→2024 growth)
   and is a sensitivity weight only. POPCEN 2024 anchoring is possible once the PSA table is added
   to `data/raw/`.

### 5.3 Road networks

1. The networks are fetched with osmnx (`graph_from_polygon`) for the city polygon **plus a
   3 km buffer** (`osm.boundary_buffer_m`; 1 km in Milestones 01–02, kept as
   `config/experiments/hist_buffer_1km.yaml`). The buffer means trips and facilities just across the
   city limit are not cut off. Experiment E7 showed that 1 km understated access for border barangays
   (Section 7).
2. Network types are osmnx `walk` and `drive`, with topology simplified.
3. **Largest component only:** the largest weakly connected component is kept for walk and the
   largest strongly connected component for drive. Since Milestone 02, QA records what this removes
   (walk 97.1% of nodes kept; drive 97.0%). *Milestone 04 (analysis only, not applied):* the 3 km walk
   fetch has 112 components. A component-aware alternative (A3) would label 5,206 residents
   "locally connected" (on an isolated component; internal times only) and 91.9 "access-uncertain";
   4,731.7 of them now get citywide times through a straight connector. Retaining all components
   with nearest-edge attachment (A2) would pull 9 citywide destinations (one hospital) onto campus
   fragments. See [docs/MILESTONE_04_RESULTS.md](docs/MILESTONE_04_RESULTS.md) §5.
   **Access tags:** the osmnx walk filter drops `access=private`, `service=private` and `foot=no`
   ways before download, but keeps `access=no` (5.3 km in the main network), `destination`
   (22.3 km) and `customers` (0.9 km). It ignores gate-node tags: the router passes 703 gates,
   171 of them `access=private`. Impact per tag: M04 results §6. *M04 methodology review:* access
   labels keep physical connectivity, mapped restriction, public pedestrian status and authorised
   group apart; the road class never decides who may use a way, and `access=private` names no group
   ([docs/MILESTONE_04_ACCESS_TAXONOMY.md](docs/MILESTONE_04_ACCESS_TAXONOMY.md); routing unchanged).
4. **Walk travel time:** edge length / 4.5 km/h.
5. **Drive travel time:** assumed free-flow speeds per road class (km/h), *including link roads*:

   | motorway | trunk | primary | secondary | tertiary | unclassified / residential / road | living_street | motorway / trunk / primary / secondary / tertiary `_link` |
   |---|---|---|---|---|---|---|---|
   | 60 | 40 | 30 | 25 | 25 | 20 | 10 | 40 / 30 / 25 / 20 / 20 |

   **`maxspeed` policy (Milestone 02): `cap`.** A tagged OSM `maxspeed` can only *lower* the
   configured speed (234 edges); it never raises it. In Milestone 01, osmnx let tags replace the
   configured speed on 17% of edges (up to 80 km/h), and imputed unlisted link classes. Each edge
   records `speed_source`. There is no congestion model.

   **Merged edges (fixed in Milestone 02B):** a simplified edge spanning several highway classes
   takes the **slowest** configured class (32 edges, 9 km). Milestone 02 took the first element of a
   list whose order osmnx builds from a set, so car times varied between processes.
6. **Barriers (Milestone 02):** water areas, watercourses and coastline (hard; culverted
   watercourses excluded), walls (flag only).
7. Graphs are projected to EPSG:32651 and saved as GraphML (`data/interim/graph_{mode}.graphml`).

### 5.4 Facilities

Facilities are fetched from OSM for the bounding box of the buffered area and clipped to it. A
bounding box is used because the polygon query exceeds the Overpass size limit. Every feature keeps
its OSM type, id and all tags (`osm_tags`).

- **Category membership:** a feature belongs to *every* category whose tags match. Tags are listed
  in `config/settings.yaml`; multi-valued tags are split. `category_priority` only picks the
  primary category for display and de-duplication. In Milestone 01 each feature had exactly one
  category, and a feature tagged only `healthcare=pharmacy` would have been counted as health.
- **Sub-types and tiers:** ordered rules per category, using OSM tags plus a few recorded name
  rules.

  | Category | Indicative (travel times computed) | Descriptive / excluded |
  |---|---|---|
  | health | hospital, primary_care | dental, other_health; **veterinary (excluded)** |
  | pharmacy | pharmacy | chemist_only |
  | education | school_public, school_private, school_ownership_unknown, kindergarten, higher_education | — |
  | safety | police, fire_station | — |
  | government | — | barangay, city_government, provincial_government, other_government_office |
  | market | public_market, supermarket | — |
  | finance | bank | atm, other_finance |
  | transport | — | land_terminal, ferry_terminal |
  | evacuation | — | named_evacuation_centre (OSM name only, *not official*), assembly_point, other |

- **Status and reason:** every classification records `class_status` (e.g. `tag_rule`,
  `reclassified_by_name`, `osm_name_only`, `attribute_missing`) and a human-readable reason.
- **De-duplication:** a point inside a polygon of the same category is merged into it (108 points).
  Possible duplicates (same name, within 50 m) are flagged but kept (14). All are listed in
  `facility_exclusions.csv`.
- **Representative location:** polygons are reduced to `representative_point()`.
- `inside_city` flags facilities within the city limit. Facility counts per barangay use only
  these. Routing uses all **connected** facilities, including those in the buffer. A facility with
  no valid connection is never a destination (3 km run: 121 external destinations used, 13 external
  facilities unconnected, 0 unconnected inside the city).

### 5.5 Accessibility computation

1. **Connection (Milestone 02):** each cell centre and facility is joined by a straight connector
   to the nearest point on a walkable **edge** (not node). Candidate edges are tried nearest-first,
   and a connector that crosses mapped water is rejected.
   - Tolerance: 250 m for cells, 500 m for facilities.
   - Cells with no acceptable edge are **not connected**: they get no time, are **not** forced onto
     the network, stay in every denominator, and are reported separately (M02B baseline: 3,969
     residents, 0.87%; 302 cells listed for manual review).
   - `rel_network` is `low` when more than 5% of a barangay's residents are not connected (4
     barangays) and `caution` above 1% (6).
   - In Milestone 01 the connector was an unchecked straight line to the nearest node; see
     Section 8, item 6.
2. **Walk:** a virtual source is linked to both end nodes of each destination's edge. One Dijkstra
   on the reversed walk graph runs per indicator group.
3. **Drive:** the walk from home to the car, and from the car to the facility, is **routed on the
   walk network** to the nearest drive-network node. The drive leg is a Dijkstra on the reversed
   drive graph, so one-way streets are followed.
4. Verified against independent implementations to within 0.005 min.
5. **Car-time sensitivity (M02B):** the drive-network leg is multiplied by 1.5 and 2 (walk legs
   unchanged), giving `drive_speed_sensitivity.csv`. The factors are illustrative, not calibrated.

### 5.6 Barangay indicators

Weights *w* are the primary population weights of the fractional cell pieces (Section 5.2); each
piece carries its cell's travel time. For each mode × indicator group:

| Indicator | Definition |
|---|---|
| `<mode>_<group>_mean_min` | Population-weighted mean time to the nearest mapped destination, **connected** residents |
| `<mode>_<group>_p90_min` | Population-weighted 90th percentile, connected residents (replaces `max_min`, the value of a single cell, in M02B) |
| `<mode>_<group>_pct_le<N>` | % of **all** residents within N minutes (walk 10/15/30; drive 5/10/15). Residents not connected are neither within nor beyond (M02B; previously the connected population) |
| `pop_total`, `pop_connected`, `pop_not_connected`, `pct_not_connected` | Connection status of the residents |
| `rel_population`, `rel_network`, `rel_facility_inventory`, `rel_overall` (+ `_reasons`) | Reliability per dimension (ok / caution / low; facility inventory `unverified`). Not a score |
| `pop_ranking_eligible` | False if population or network reliability is low: excluded from rankings of population-based quantities |
| `pop_drive_access_gt_flag` | Residents whose walk to the drive network exceeds 500 m |
| `n_<category>`, `n_<group>`, `n_facilities_duplicate_review` | Mapped facilities inside the barangay (counts of mapped features, not capacity) |

The thresholds are analytical reporting thresholds, not official standards. Every indicator is
*access to the nearest mapped facility* of a defined sub-type, that is, geographic proximity.
Service level (facility level and public/private status) is not verified, and capacity is not
measured (validity assessment P6). Car times are *modelled uncongested car travel time* (P5).

**Reliability rules** (`reliability:` in `settings.yaml`):

| Dimension | low | caution |
|---|---|---|
| population | ≤ 5 cell centres, or census population that cannot be placed | 6–10 cell centres, or census/WorldPop 2020 factor outside 0.5–2.0 |
| network | > 5% of residents not connected | > 1% |
| facility inventory | always `unverified` until an official registry is matched; reasons list duplicates pending review | |
| overall | most restrictive of population and network, with all reasons | |

## 6. Quality assurance and validation

Each stage writes its own checks to `data/interim/qa/<stage>.json`. The status is PASS, WARN
(failed a threshold) or info (reported, no threshold). `abot report` collects them into
`qa_report.md`.

> **Milestone 02 note.** The Milestone 01 run had no WARNs, but the audit found that some PASS checks
> could not fail (e.g. unreachable population = 0 by construction; facility count at least 5). These
> were replaced by checks that test real conditions; see
> [docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md) section 6. The current baseline has
> two WARNs, both genuine findings: one school is not connected (across a river from every mapped
> path), and small barangays show a +69.9% WorldPop bias. The tables below are the Milestone 01
> record, except where marked.

### Boundaries

| Check | Result |
|---|---|
| City found | 1 (PASS) |
| Barangay count | 180 of 180 expected (PASS) |
| Unique p-codes | 180 (PASS) |
| Invalid geometries | 0 (PASS) |
| Barangay union vs city area | 0.0% (PASS) |
| Barangay overlap | ≈0 km² (PASS) |

### Population

| Check | 2026 | 2020 |
|---|---|---|
| WorldPop total (centre rule) | 492,459 | 468,282 |
| Populated cells | 7,815 | 7,738 |
| Excluded edge-cell population | 0.86% (PASS, <5%) | 0.85% (PASS) |
| Unassigned cells | 0 (PASS) | 0 (PASS) |
| Barangays with no population | 0 | 0 |

**WorldPop 2020 vs PSA census 2020** (180 of 180 barangays matched by p-code):

| Metric | Value | Threshold |
|---|---|---|
| City-wide difference | +2.33% (468,282 vs 457,626) | < 10% → PASS |
| Pearson r across barangays | 0.916 | > 0.7 → PASS |
| Median absolute % error per barangay | 32.0% | info |
| Barangays with abs. error > 30% | 97 of 180 | — |

Interpretation (revised by the validity assessment, 2026-10-31):
- **This is not independent validation.** WorldPop's input for the Philippines was the 2020
  census itself, at barangay level. The +2.33% city difference is roughly WorldPop's national
  adjustment to UN totals, so it is true by construction. Raw-count r = 0.916 is inflated by the
  range of barangay sizes; the density correlation is 0.51.
- Barangay differences (median 32%) mostly measure how WorldPop's input units line up with
  COD-AB barangays, plus WorldPop's modelled split within those units. Eight barangays reproduce
  census × 1.0224 exactly.
- **Independent check against PSA POPCEN 2024:**
  - City level agrees: WP2024 is +2.29% above POPCEN; growth 2020→2024 is +3.48% (WorldPop) vs
    +3.52% (PSA).
  - Barangay level does not: PSA growth ranges from −42.6% to +65.7% (34 barangays declined),
    WorldPop's from +2.7% to +5.0%, with a rank correlation of 0.05.
  - So post-2020 WorldPop years carry no information on differences in barangay change.
- Barangays with ≤ 5 cells (27) have population totals that shift 15–26% depending on the
  cell-allocation rule. Their travel times are stable.

### Networks and facilities

| Check | Walk | Drive |
|---|---|---|
| Nodes | 12,927 (PASS, >1000) | 6,794 (PASS) |
| Directed edges | 33,902 | 16,930 |
| Directed length | 2,237.1 km | 1,542.4 km |

The directed length counts two-way streets in both directions.

| Category | In city | Incl. 1 km buffer |
|---|---|---|
| finance | 172 | 178 |
| government | 162 | 168 |
| education | 153 | 162 |
| health | 98 | 99 |
| pharmacy | 92 | 97 |
| market | 64 | 74 |
| safety | 28 | 28 |
| transport | 11 | 15 |
| evacuation | 5 | 5 |

Milestone 01 flagged a category as unreliable if it had fewer than 5 facilities in the city.
Evacuation was exactly at that limit and passed. Since Milestone 02, counts are info only, and
evacuation and transport are descriptive-only categories (see Section 8).

### Accessibility

- Milestone 01: unreachable population **0** for every mode × category (PASS). This check could
  not fail and was replaced in Milestone 02.
- Milestone 02 baseline: 99.08% of population connected; 3,404 beyond 250 m and 1,134 blocked by
  water (not connected); 0 connected cells without a time; 4 barangays flagged (> 5% not connected).
- Milestone 02B baseline (3 km, census-anchored): 99.13% connected; 2,983 beyond 250 m and 986
  blocked (3,969, 0.87%, kept in denominators); 0 connected cells without a time; facilities 924 of
  937 connected (the 13 unconnected are all outside the city); rerouted around water 1,644; wall
  flag 369.

### Population and reliability (Milestone 02B baseline)

| Check | Result |
|---|---|
| Census-adjusted total = census | 457,626 = 457,626 (PASS); 0 unallocated (PASS) |
| Original WorldPop 2020 / 2026, in city (fractional) | 467,501 / 491,633 (outside part of touching cells: 1.0%) |
| WorldPop 2020 vs census, city | +2.16% (info: by construction, not validation) |
| Barangay median \|difference\| | 30.5% (info: unit alignment) |
| Anchoring factor | 0.19 – 4.48 (median 0.96) |
| `rel_population` ok / caution / low | 102 / 51 / 27 |
| `rel_network` ok / caution / low | 170 / 6 / 4 |
| `rel_overall` ok / caution / low; ranking-eligible | 92 / 57 / 31; 149 |
| `abot audit` (3 km baseline) | M02B: PASS 50, WARN 3, FAIL 0, INFO 11. M03 (with the experiment-run checks): PASS 54, WARN 4 (pending reviews, Guimaras facilities, stale `e7_buffer_3km`), FAIL 0, INFO 11. M04: PASS 55 (new archive `hist_e7_buffer_3km_m02` verified), WARN 4, FAIL 0, INFO 11. M04 follow-up: PASS 57 (A3 layer current; review restore point verified), WARN 3 (`e7_buffer_3km` cleared; 7 duplicates still pending), FAIL 0, INFO 11 |
| Determinism (M04 + follow-up) | `abot components` under `PYTHONHASHSEED` 0 and 12345: all 17 evidence files and the A3 CSVs byte-identical (A3 GeoPackage identical in content); A1 reproduces the saved baseline, and baseline file hashes are unchanged on every run |

### Unit tests (250 Python, all passing; 82 Vitest tests in `dashboard/test/`, all passing; 20 Milestone 06.2A tests in `tests/test_m06.py`, 3 of which read the real outputs; the 13 Milestone 01 tests are listed here, 40 Milestone 02 tests are in `tests/test_m02.py`, 32 Milestone 02B tests in `tests/test_m02b.py`, 18 Milestone 03 tests in `tests/test_m03.py`, 97 Milestone 04 tests in `tests/test_m04.py`, 30 Milestone 05 tests in `tests/test_m05.py`, 2 of which read the real outputs and are skipped without them)

- Conversion from old PSGC codes to COD-AB p-codes (3 cases).
- Merging of OSM query tags (lists and "any value").
- Facility categorisation, including priority, `true` wildcards and NaN tags (6 cases).
- Multi-source Dijkstra: facility offsets are included, one-way streets are respected, the
  nearest of several facilities is chosen, and the virtual source is removed afterwards (3 tests).

---

## 7. Results

### 7.0 Current results (Milestone 02B baseline)

3 km OSM buffer, census-anchored 2020 weights (457,626 residents). The figures describe proximity
to **mapped** facilities. Means and p90 cover connected residents; shares are of **all** residents
(0.87% not connected). Car = modelled uncongested car travel time; its shares are lower bounds.
Details: [docs/MILESTONE_02B_RESULTS.md](docs/MILESTONE_02B_RESULTS.md).

| Indicator group | Walk mean (min) | Walk p90 (min) | Walk ≤ 15 / ≤ 30 min | Car mean (min) | Car ≤ 10 min (× 1 / × 2 network time) |
|---|---|---|---|---|---|
| health_hospital | 27.92 | 50.64 | 22.9% / 61.2% | 7.61 | 79.6% / 38.5% |
| health_primary_care | 13.21 | 28.23 | 66.6% / 91.1% | 4.25 | 97.5% / 81.2% |
| pharmacy | 13.81 | 28.57 | 62.7% / 90.8% | 4.21 | 97.2% / 81.9% |
| education_basic | 8.66 | 15.45 | 88.3% / 98.9% | 3.82 | 98.3% / 95.1% |
| education_higher | 23.63 | 45.15 | 37.3% / 68.8% | 6.96 | 81.9% / 51.6% |
| safety_police | 19.31 | 34.07 | 37.8% / 82.2% | 5.58 | 95.7% / 63.2% |
| safety_fire | 17.28 | 31.03 | 46.1% / 87.3% | 5.30 | 96.1% / 68.3% |
| market_public | 20.47 | 38.67 | 39.4% / 80.6% | 5.85 | 91.9% / 61.5% |
| market_supermarket | 17.54 | 32.60 | 48.0% / 85.6% | 5.27 | 96.2% / 67.7% |
| finance_bank | 16.09 | 31.30 | 53.1% / 87.3% | 4.58 | 97.1% / 75.2% |

**Experiment E7, re-run under the M02B method** (`hist_buffer_1km` vs the default): city-wide means
change by ≤ 0.08 min and shares by ≤ 0.2 percentage points. Barangay ρ ≥ 0.9999, with 20/20 of the
worst barangays unchanged, and no cell is slower. The largest change is in Hibao-an Norte: walk to
primary care 42.49 → 29.98 min. This is why 3 km is now the default.

**Milestone 02 snapshot → 02B** (1 km both; new weights, new denominators and the speed fix): walk to
hospital ≤ 15 min 24.7% → 22.9%; walk to police 41.6% → 37.8%; car to hospital mean 7.46 → 7.61
min. Barangay ranks are stable (ρ ≥ 0.988).

**Milestone 02 baseline figures** (1 km, WorldPop 2026, connected-only denominators) are kept in
[docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md). They are superseded.

### 7.1 Milestone 01 results (superseded, kept as a record)

> These figures used undifferentiated categories (e.g. "health" was dominated by dental, laboratory
> and therapy features), straight-line node snapping and `maxspeed` overrides. **Do not cite them as
> current results.** See [docs/MILESTONE_02_ANALYTICAL_AUDIT.md](docs/MILESTONE_02_ANALYTICAL_AUDIT.md).

Analysis year is 2026 (WorldPop projection), with population weighting. The city-wide figures
below are derived from the Milestone 01 `barangay_access.csv` (archived in
`data/archive/m01_3edc0dd/`).

### City-wide population-weighted mean travel time (minutes)

| Category | Walk | Drive |
|---|---|---|
| education | 8.88 | 2.85 |
| government | 10.06 | 2.70 |
| health | 12.67 | 3.18 |
| pharmacy | 14.05 | 3.20 |
| finance | 14.79 | 3.25 |
| market | 15.83 | 3.53 |
| safety | 15.84 | 3.79 |
| transport | 34.96 | 5.84 |
| evacuation | 37.16 | 6.65 |

### Share of city population within a travel-time threshold (%)

| Category | Walk ≤ 15 min | Walk ≤ 30 min | Drive ≤ 10 min |
|---|---|---|---|
| education | 87.8 | 99.6 | 99.8 |
| government | 82.8 | 95.9 | 99.5 |
| health | 70.1 | 93.2 | 99.4 |
| pharmacy | 62.2 | 91.6 | 99.5 |
| finance | 58.6 | 90.3 | 99.4 |
| market | 56.0 | 89.8 | 99.4 |
| safety | 54.7 | 89.6 | 99.4 |
| transport | 17.1 | 47.4 | 93.9 |
| evacuation | 11.9 | 32.3 | 96.1 |

### Barangays with the longest mean walking time

| Category | Barangay | Mean walk (min) |
|---|---|---|
| health | Hibao-an Norte | 42.33 |
| pharmacy | Hinactacan | 46.11 |
| safety | Hibao-an Norte | 42.99 |
| government | Hibao-an Norte | 42.63 |
| market | Ingore | 47.78 |
| finance | Hinactacan | 39.32 |
| education | Dungon | 19.91 |

127 of the 180 barangays have no OSM-mapped health facility inside their boundary. Residents may
still be near one in a neighbouring barangay; the travel-time indicators account for that.

### Preliminary observations from Milestone 01 (revised in Milestone 02)

- *Milestone 01:* about 30% of residents live more than a 15-minute walk from the nearest health
  facility. *Revised:* this "health" mixed dental, lab and therapy services. About 75% live more
  than 15 minutes' walk from a mapped **hospital**, and about 33% from mapped **primary care**.
- The longest walking times are concentrated in peripheral barangays (e.g. Hibao-an Norte,
  Hinactacan, Ingore). This fits a centre–periphery pattern, but no formal spatial statistic has
  been computed yet.
- Drive times are short almost everywhere (≥ 99% within 10 minutes for most categories). This is
  largely because the model assumes free-flow speeds, and it should not be read as evidence of
  good car access (see Section 8).
- The transport and evacuation results mostly reflect missing OSM data. They are not reliable
  measures of real accessibility.

---

## 8. Limitations and threats to validity

1. **OSM completeness differs by category.** Evacuation centres (5 mapped) and transport terminals
   (11) are severely under-mapped. Health and education facilities have not yet been checked
   against official registries (DOH National Health Facility Registry, DepEd school lists).
   *Milestone 02:* evacuation, transport and government are now descriptive only (no travel
   times). About 450 designated evacuation centres are reported in the press, against 6 OSM
   features. Registry availability is in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) section 4.
2. **Drive times are modelled uncongested car travel times, not journey times.** Threshold shares
   depend heavily on this assumption. Example (M02B baseline, `drive_speed_sensitivity.csv`): "≤ 10
   min to a hospital" is 79.6% of residents, 55.5% if the network leg takes 1.5× as long, and 38.5%
   at 2×. The factors are illustrative. Car times describe
   access only for households with a car. Speeds are assumed per road class. There is no congestion,
   parking time, or turn penalty.
3. **No public transport model.** Jeepneys, tricycles and walking to transit are the main ways
   many residents travel in Iloilo, and they are not modelled yet.
4. **WorldPop R2025A is an alpha release**, and 2026 values are projections. The 2026 surface
   is essentially the 2020 pattern scaled up, and it does not reflect barangay change measured by
   PSA POPCEN 2024 (see Section 6). *Milestone 02B:* barangay totals are now the PSA 2020 census
   (census-anchored), so WorldPop decides only the split within each barangay. That split is still
   modelled, and the totals are fixed at 2020. POPCEN 2024 anchoring awaits the PSA table.
5. **Population cells are 100 m.** Very small barangays (smallest is 0.014 km²) are represented
   by very few cells. *Milestone 02B:* fractional allocation is used, and 27 barangays with ≤ 5 cell
   centres are `rel_population = low` and excluded from population-based rankings. District
   aggregates (validity assessment P2) are not possible yet: no barangay→district table is
   available.
6. **Off-network legs are straight lines.** The walk from a cell centre to the nearest node ignores
   obstacles such as rivers or walls. The median snap distance is 47–66 m. Measured in the validity
   assessment:
   - These legs cross rivers, fishponds or the coastline for 4,695 people (0.95%) on foot and
     7,800 (1.58%) by car. The count ranges from about 4,700 to 14,500 depending on tolerance
     settings.
   - Concentrated in Calahunan, Hibao-an Sur and Ticud. City averages shift by ≤ 0.2 min; the
     largest single-cell error is about 13 min.
   - *Addressed in the Milestone 02 implementation:* edge-based, water-aware connectors and
     walk-routed drive access replace these straight lines. 4,538 people (0.92%) cannot be
     connected; they are reported (`pop_not_connected`, `pct_not_connected`), and 4 barangays are
     flagged (> 5%). The remaining uncertainty is missing OSM footpaths and bridges and outdated
     fishpond polygons.
   - *Milestone 02B:* 3,969 residents (302 cells) are not connected. They stay in every denominator,
     and they are listed with coordinates, blocking features and nearby paths in
     `review/unconnected_cells_review.csv` with a map, **pending manual review**. Calahunan (30.7%)
     and Hibao-an Sur (23.7%) indicators describe only their connected residents.
   - *Milestone 03 (desk evidence, nothing applied):* 2,537 of the 3,969 have no mapped way of any
     kind within 250 m. 2,326 of them form one cluster in Calahunan / Hibao-an Sur. A reviewer
     imagery check (2020 and 2026) shows paved, populated subdivisions there whose streets are
     missing from the walk network: an artefact of the network data, not a real lack of access. 832 are cut off by a creek or river (Calajunan Creek 291). 528
     are next to mapped ways that OSM does not link to the main network. 72 have their centre in
     mapped water (53 in ponds). The count is tolerance-sensitive: 2,835 / 1,922 / 1,407 would remain
     at 300 / 400 / 500 m.
   - *Milestone 03:* the largest-component filter drops 111 OSM fragments (39.5 km of ways). Besides
     the unconnected cells, 4,812 *connected* residents (1.05%) have an unlinked fragment as their
     nearest mapped way and reach the main network by a longer straight connector (median 104 m).
     2,134 of them are in one 10.4 km subdivision in Tabuc Suba (La Paz) whose streets are 10.9 m
     from the main network (fragment F001; cause unverified).
   - *Milestone 04 (cache evidence, nothing applied):* F001 has 4 dead ends within 20 m of
     main-network streets, all tagged `noexit=yes`, and the main-network side of the 10.9 m gap is
     `noexit=yes` too. Mappers marked these as deliberate dead ends, which argues against an
     unmapped link there. The subdivision's entrance (possibly a private way the walk filter drops)
     is **unverified**: the targeted Overpass snapshot was not obtained. *M04 follow-up:* the baseline
     (A1) is labelled the **optimistic connectivity scenario** (not a verified upper bound). An
     additional A3 reporting layer (`data/processed/component_aware/`) reports 5,206 residents as
     locally connected and 91.9 as access-uncertain, with internal times kept apart from citywide
     ones. Tabuc Suba (La Paz) is 43.5% locally connected, San Agustin 29.2%, Baybay Tanza 26.8%. The
     A1 baseline is unchanged.
   - *M04 snapshot review (observed, nothing applied):* the targeted snapshot shows that F001's
     streets hang off **Gustilo Street**, a 1 km `access=private` tertiary road. Its southern end is a
     `barrier=gate` + `access=private` node where the public Gustilo Street ends, and an 87 m private
     way with no mapped gate links it northwards. F100/F101 reach the public fishport road only through
     private fishport service roads ending at `access=private` gates (184 m / 579 m). They are
     physically connected in OSM topology, but public pedestrian access is **restricted according to
     mapped tags**. Whether F001's own residents use Gustilo Street as their exit is **unverified**, an
     assumption pending a methodology decision
     ([docs/MILESTONE_04_SNAPSHOT_REVIEW.md](docs/MILESTONE_04_SNAPSHOT_REVIEW.md)).
   - *M04 methodology review:* `access=private` names no authorised group, so neither F001 residents
     nor fishport neighbours are assumed authorised (`authorized_group=unspecified`). A resident-egress
     scenario for F001 would be a separate authorised-user scenario with stated assumptions and bounds,
     not a public-access result; it is documented, not implemented. Fishport pedestrian permissions
     need the operator's access rules or documented field verification
     ([docs/MILESTONE_04_ACCESS_TAXONOMY.md](docs/MILESTONE_04_ACCESS_TAXONOMY.md) §5).
   - *Milestone 04:* gate nodes and `access=no` ways are routed through (the osmnx walk filter keeps
     them). Removing them would change citywide ≤ 15 min shares by at most 0.75 pp, but would cut
     12.6 (`access=no`) to 218.3 (all explicit restrictions) residents off the network.
7. **Boundary definition.** 72.63 km² is the area of the COD-AB v03 polygon (land), not the official
   land area. The often-cited 78.34 km² has no reproducible geometry and is no longer used as a
   comparison (P4). There is an inland mismatch of about 2.6 km² with OSM on the northern boundary
   (Section 2).
8. **Facility type is not weighted by capacity or service level.** A barangay health station and a
   tertiary hospital both count as "health". *Milestone 02* separates hospitals from primary
   care, but hospital level and capacity are still not distinguished.
9. **OSM is a snapshot.** Results depend on the retrieval date (2026-10-31).
10. **Indicators measure proximity only.** They give the travel time to the nearest mapped facility
    of a defined type. They do not measure service level (for example, hospital level is not
    verified) or capacity (beds, staff, enrolment). In OSM, `beds` is tagged for only 3 of 16
    hospitals. Do not describe results as "served", "coverage" or "adequate".

Treatments P1–P7 from [docs/MILESTONE_02_VALIDITY_ASSESSMENT.md](docs/MILESTONE_02_VALIDITY_ASSESSMENT.md)
are implemented in Milestone 02B, except district aggregates (P2), the optional boundary QA
against OSM (P4) and the connector radius × tolerance experiment (P3).

11. **Sensitivity analysis is partial.** Tested so far: the OSM buffer (E7), the speed policy
    (regenerated on the 3 km baseline in Milestone 03), the car network-time factors (× 1.5, × 2)
    and the origin connector tolerance (Milestone 03, not applied). E1, E3, E4 and E6 remain.
12. **Facility duplicates.** 14 possible duplicate pairs are kept, never merged automatically, and
    are pending manual review (`review/possible_duplicates_review.csv`). *Milestone 03 desk
    assessment:* 2 are the same facility (D13, D14), 5 are distinct (bank and ATM), 6 are likely
    duplicates and 1 is uncertain. They affect facility counts only (≤ 41 m position shifts).
    *Milestone 04:* the one approved lookup of BPI's branch directory for D10 returned HTTP 404
    (inconclusive). *M04 follow-up (user-approved, logged, reversible):* D01, D02, D07, D08, D09
    `distinct_keep_both`; D13, D14 `likely_duplicate_not_merged` (both records kept, no count changed);
    D03–D06 and D10–D12 still pending.
13. **External facilities.** 13 facilities in the 3 km buffer are not connected. All are on Guimaras,
    across the Iloilo Strait, and are never used as destinations (Milestone 03).

---

## 9. Reproducibility

```bash
uv sync                 # Python 3.13 + pinned dependencies from uv.lock
uv run abot fetch       # ~550 MB into data/raw (records manifest.json with SHA-256)
uv run abot build       # boundaries -> population -> osm -> accessibility
uv run abot report      # qa_report.md and abot_map.html
uv run abot review      # manual-review files (changes no data)
uv run abot validate    # Milestone 03 desk evidence (Overpass cache only, changes no data)
uv run abot components  # M04 component/access evidence + A3 reporting layer (cache only; baseline unchanged)
uv run abot fetch-gaps  # Milestone 04 targeted query: dry run; --allow-download sends it once
uv run abot audit       # read-only PASS / WARN / FAIL check of everything above
uv run pytest           # offline unit tests
```

- Historical 1 km baseline: `uv run abot --config config/experiments/hist_buffer_1km.yaml build`.
  The exact Milestone 01 code is commit `3edc0dd`, and its outputs are in `data/archive/m01_3edc0dd/`.
- Archives have SHA-256 records (`data/archive/<name>.sha256.json`), checked by `abot audit`.
- Builds are deterministic (verified under different `PYTHONHASHSEED` values after the M02B
  mixed-class speed fix, and again in Milestone 03 for the regenerated `sens_maxspeed_override`
  run: byte-identical CSVs and `access_cells` layer).
- `abot audit` also checks every `config/experiments/*` run against its own configuration and the
  code dates (Milestone 03), so stale experiment outputs are flagged.

- Inputs are verified by the SHA-256 checksums in Section 3 and `data/raw/manifest.json`.
- All parameters are in `config/settings.yaml`.
- The data is not in git (`data/` is in `.gitignore`). OSM results can differ on a new fetch unless
  the existing `data/raw/osm_cache/` is reused. The manifest records each cached response's SHA-256
  and Overpass timestamp, so a changed snapshot is detectable.
- Experiments: see [docs/MILESTONE_02B_RESULTS.md](docs/MILESTONE_02B_RESULTS.md) section 10
  (current) and [docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md) section 8 (Milestone 02).

---

## 10. Change log

Newest entries first. Each entry records the date, the milestone, what changed and why, files
affected, and any effect on results. Future work is appended here as it is done.

### 2026-11-02 — Milestone 06.2A follow-up: archive-aware validation (uncommitted)

**Why:** The author approved the proposal in [docs/M06_2A_REPRODUCIBILITY.md](docs/M06_2A_REPRODUCIBILITY.md)
§3.3. An entirely absent `data/archive/`, as in a fresh clone, must not block the export.
Archive-dependent validation must stay strict whenever archives exist. Details are in report §10.

**Changed:**
- `src/abot/audit.py`: without `data/archive/`, `check_archive` reports one WARN,
  `m01_archive_present: NOT PERFORMED: data/archive/ absent …` (constant `audit.NOT_PERFORMED`),
  instead of a FAIL. With `data/archive/` present it is unchanged: the M01 archive missing is
  FAIL, and a changed or missing archived file is FAIL.
- `src/abot/dashboard_data.py`:
  - `classes_check()` (V-S4) returns the recorded block and the problems:
    - `performed` and strict when a comparison was made;
    - `not_performed`, with `identical`/`components_compared` null and a `reason`, only when
      `data/archive/` is absent;
    - otherwise a V-S4 problem: incomplete archive, comparison not made, another reference, a
      reference no longer present, or a failed comparison.
  - The new known issue `ARCHIVE-CHECKS-NOT-PERFORMED` is written if and only if the check is
    `not_performed`, and the exporter's validation enforces that.
  - `archive_dir()` helper; `CONTRACT_VERSION` 1.1.0.
- `src/abot/cli.py`: help text.
- Dashboard:
  - `contract/types.ts`: nullable comparison fields, `status`, `reason`.
  - `version.ts`: supports 1.1.0; 1.0.x bundles still load.
  - `pages/QualityPage.tsx`: a "Not performed" warning badge, never Yes/No; the reason is shown.
  - Tests: one new render test. The "newer minor" examples move to 1.2.0.
- `docs/DASHBOARD_DATA_CONTRACT.md`: version 1.1.0 (minor), with a states table for
  `component_classes_check`, V-S4, the new known issue and the revision record.
- `README.md`, `docs/ARCHITECTURE.md`: fresh-clone export behaviour, contract 1.1.0, test counts.
- `docs/M06_2A_REPRODUCIBILITY.md`: §3.2/§3.3 updated; new §10, which states which validations are
  and are not performed in a fresh clone, and that a fresh-clone bundle does not reproduce the
  published results.

**Added:** 10 tests in `tests/test_m06.py`, covering:
- an absent archive tree;
- a complete archive with valid references;
- an archive missing its references;
- four invalid or inconsistent reference cases and a modified archived file;
- an end-to-end export with no archives (indicators equal to the installed bundle) and with an
  incomplete archive (blocked).

**Verified:**
- pytest: 250 passed.
- ruff check: passed; `ruff format --check`: the same 8 pre-existing files.
- Vitest: 82 passed; typecheck clean; production build passed.
- On the real data (read-only): V-S4 `performed` and passing; `m01_archive_present` PASS.
- In the isolated scratch copy, with no `data/archive/` and the real audit:
  - `abot audit`: WARN NOT PERFORMED, 0 FAIL;
  - `abot export-dashboard`: exit 0, with every indicator file equal to the installed bundle;
  - with an empty `data/archive/`: the export is blocked by V-S4, and the audit FAILs
    `m01_archive_present`.

**Effect on results:** none.
- No methodology, indicator code or archive changed.
- The installed bundle is unchanged (contract 1.0.0, commit `3073524`, still current). A re-export
  on this machine gives `component_classes_check.status: performed` and contract 1.1.0, with the
  same indicator values.

### 2026-11-02 — Milestone 06.2A: fresh-clone workflow audit; targeted snapshot made optional, declared evidence (commit `8ff8aea`)

**Why:** M06.1 found that `abot export-dashboard` failed on a fresh clone unless
`abot fetch-gaps --allow-download` had run first. Full report:
[docs/M06_2A_REPRODUCIBILITY.md](docs/M06_2A_REPRODUCIBILITY.md).

**Found:**
- **The snapshot is optional evidence.** It never changes a component class or indicator:
  - `components.build` writes the A3 layer before it reads the snapshot;
  - an isolated run without the snapshot gave byte-identical A3, approach, component, transition
    and access-impact files (only `gap_investigation.csv` differed).
- **`abot components` already supports its absence:** it deletes the snapshot tables and writes
  `snapshot_status.json` with `obtained: false`.
- **Only the exporter's source list (V-S1) required `snapshot_corridor_analysis.csv`.** The
  observed failure was `V-S1: missing source …`, with nothing written.
- **Second latent defect:** a snapshot with no link candidates makes `components` write an empty
  file that `pd.read_csv` cannot parse, so the export would have crashed.
- **Two further fresh-clone blockers, documented and not changed:**
  - V-S4 needs the archived pre-taxonomy component reference;
  - the audit gate fails without `data/archive/m01_3edc0dd/`.

  A fix is proposed in report §3.3 for the author's decision.

**Changed:**
- `src/abot/dashboard_data.py`:
  - `snapshot_status.json` is a declared source;
  - the corridor table is a source only when a snapshot is declared;
  - `load_corridors` reads an empty table as no rows;
  - new check **V-S5** refuses every mismatch between the declaration, the corridor table, the gap
    table and the latest `osm_targeted/` manifest entry, with "re-run `abot components`";
  - `CONTRACT_VERSION` is now 1.0.1.
- `src/abot/cli.py`: help text.
- `docs/DASHBOARD_DATA_CONTRACT.md`: version 1.0.1 (patch):
  - §7.1.1 makes the corridor table conditional;
  - `gap_evidence` and `targeted_snapshot` are documented as nullable, as the 1.0.0 code already
    produced;
  - V-S5;
  - a revision record.
- `README.md` and `docs/ARCHITECTURE.md`: `fetch-gaps` is optional; the archive blockers are stated;
  contract 1.0.1.

**Added:**
- `tests/test_m06.py`: 10 tests covering the declared, undeclared, empty and missing states, five
  inconsistent states, and an end-to-end export of the no-snapshot path on the real outputs to a
  temporary folder.
- `docs/M06_2A_REPRODUCIBILITY.md`.

**Verified:**
- pytest: 240 passed.
- ruff check: passed; `ruff format --check`: the same 8 pre-existing files.
- Vitest: 81 passed; typecheck clean.
- V-S5 passes on the current data (read-only).
- Isolated scratch run (HEAD code via `git archive`, copied data without the snapshot):
  - HEAD exporter: exit 1 (V-S1);
  - fixed exporter, no archives: exit 1 (V-S4);
  - fixed exporter with archives: exit 0, with every indicator equal to the installed bundle.

**Effect on results:** none.
- The installed bundle is unchanged: version 1.0.0, from `3073524`, still current.
- A re-export after commit will differ only in `contract_version` 1.0.1, one more `source_files`
  entry, timestamps and commit.

### 2026-11-02 — Milestone 06.1: make it visible (documentation, licensing, presentation; uncommitted)

**Why:** The M06.0 audit found that a reviewer could not see or understand the project quickly.
Its High findings were:
- the README was out of date;
- there were no screenshots;
- there was no LICENSE;
- there was no architecture overview.

It also found unused dependencies.

**Added:**
- `LICENSE`: MIT, © 2026 Carl John L. Coopera. The author confirmed ownership and chose MIT. The
  licence covers the code only; data keeps its own licences.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system overview, Mermaid data-flow diagram, each
  pipeline stage, the exporter, the frontend loader, provenance, limitations, and why there is no
  API server or database.
- [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md):
  - data licences;
  - ODbL obligations;
  - tile providers (OSM tile policy, Esri terms);
  - Python and npm libraries with licences, read from the installed metadata.
- `docs/assets/screenshots/`: six genuine 1440×900 captures of the running dashboard and the current
  bundle (overview, map, barangays, facilities, quality, network). They were taken with the
  installed Chrome in headless mode, so no new tool was added.

**Changed:**
- `README.md`: rewritten as the entry point. It covers the problem, features, screenshots, selected
  findings, architecture, stack, setup for both halves, tests, attribution, limitations and licence.
  Every figure comes from the current bundle (`city.json`, `barangay_indicators.json`) or the
  export-time audit.
- `pyproject.toml`:
  - `license = "MIT"`, `license-files = ["LICENSE"]`;
  - author name. A test wheel build with uv 0.13.6 carried `License-Expression: MIT` and the
    LICENSE file. `uv lock --check` was unchanged (38 packages).
- `dashboard/package.json`: `"license": "MIT"`.
- `.gitignore`: `.vscode/`. `export-dashboard` counts untracked files as uncommitted changes, so
  without this rule the planned clean re-export would still record a dirty tree.
- This file: the author, licence and current-state lines, and the frontend stack in §4.

**Removed:** `chart.js` 4.6.1 and `react-leaflet` 5.0.0 (with `@kurkle/color`, `@react-leaflet/core`),
via `npm uninstall`, which updated `package-lock.json`. Before removal it was verified that:
- no static or dynamic import uses either package (the only dynamic import is `import("leaflet")`);
- nothing in the lockfile depends on them except the root;
- the production bundle contained none of their code.

`react-leaflet` is licensed Hippocratic-2.1, which is not OSI-approved.

**Found (documented, not changed):** a fresh clone cannot run `abot export-dashboard` without first
running `abot fetch-gaps --allow-download`. The reason:
- `dashboard_data.load` reads `review/m04/snapshot_corridor_analysis.csv` unconditionally;
- `abot components` writes that file only when a targeted snapshot exists.

The README lists the full command chain.

**Effect on results:** none. No analytical code, configuration, data or bundle was changed. The
bundle still records commit `5ed16d2` (dirty) until it is re-exported after this milestone is
committed.

### 2026-11-02 — Milestone 06.0: audit re-verified (assessment only; uncommitted)

**Why:** The 2026-11-01 audit was re-checked independently before any M06 implementation relies on
it.

**Re-run and observed** (same commit `56fbd64`; nothing written under `data/` or `dashboard/dist/`):
- pytest: 230 passed.
- ruff check: passed.
- ruff format --check: 8 files would be reformatted.
- Vitest: 81 passed.
- tsc (both configs): clean.
- vite build: succeeded, 9 bundle files verified.
- `abot audit --skip-hashes`: PASS 51 · WARN 3 · FAIL 0.
- `export-dashboard --check`: current, commit `5ed16d2`, working tree not clean.

`uv lock --check` was not re-run because `uv` was not on the PATH.

**Changed:** [docs/M06_TECHNICAL_AUDIT.md](docs/M06_TECHNICAL_AUDIT.md). Corrections:
- The per-file frontend test counts (loader 32, plugin 7, models 15).
- The count of `any` in source: 0 (two in tests).
- The M10 wording: six effects omit dependencies and justify it in comments; no lint suppressions
  exist.
- The claim that `uv` worked in PowerShell.

**Added:** L6 (the production build ships source maps), a note that PyProj is used only through
GeoPandas, and Appendix A recording the re-verification.

**Effect on findings:** no severity changed, and the recommended next step (M06.1) stands.

**Effect on results:** none.

### 2026-11-01 — Milestone 06.0: technical audit and portfolio baseline (assessment only; uncommitted)

**Why:** Milestone 06 prepares ABOT as a portfolio project for internship applications in GIS, data
engineering and software development. This step measures the current state before any change is
made.

**Added:** [docs/M06_TECHNICAL_AUDIT.md](docs/M06_TECHNICAL_AUDIT.md). It covers architecture, data
architecture, code quality, testing, reproducibility, documentation, technical debt, a portfolio
scorecard and an M06 roadmap.

**Checks run and observed** (nothing written under `data/`; the frontend build went to a temporary
folder outside the repository):
- pytest: 230 passed.
- ruff check: passed.
- ruff format --check: 8 files would be reformatted.
- uv lock --check: consistent.
- Vitest: 81 passed.
- tsc (both configs): clean.
- vite build: succeeded, with the bundle verified while copying.
- `abot audit --skip-hashes`: PASS 51 · WARN 3 · FAIL 0.
- `abot export-dashboard --check`: current, but the manifest records commit `5ed16d2` with a dirty
  working tree.

**Main findings:**
- No Critical issues.
- Five High issues, all about presentation and outside reproducibility, not correctness:
  - the README is out of date (Milestone 02B, no dashboard);
  - no demo, screenshots or sample data;
  - no CI;
  - no LICENSE;
  - no architecture overview.
- Medium issues include:
  - `chart.js` and `react-leaflet` are installed but unused;
  - the bundle provenance records uncommitted code;
  - the OSM snapshot cannot be reproduced from a clone;
  - very large modules;
  - no end-to-end or browser tests.
- The static-JSON design is judged appropriate. A REST API, PostgreSQL or PostGIS would not serve
  any current requirement.

**Recommended next step:** M06.1, "Make it visible". Add a LICENSE, an architecture document and a
rewritten README with screenshots. Correct the stack description and remove the unused packages.
Re-export the bundle from a clean commit.

**Unchanged:** all application code, configuration, data, tests and Git history.

**Effect on results:** none.

### 2026-11-01 — Milestone 05.3: public redesign of the dashboard, with background maps (uncommitted)

**Why:** The dashboard's likely users are residents and barangay/city officials, not researchers. The
S4–S7 pages put research detail first: scenario codes (A1/A2/A3), statement chips (DQ-…), integrity
hashes, p90 and sensitivity tables. The map had no background, so it was hard to tell where things
are. This step makes the public pages plain and uncluttered, adds street and satellite backgrounds,
and keeps all technical detail one link away for the thesis committee and other researchers.

**Design basis:** the ui-ux-pro-max skill's design-system search (civic/public-service product).
- Adopted: civic blue palette (#1E40AF primary) and Atkinson Hyperlegible, a font designed for
  legibility.
- Not adopted: the suggested "video hero" pattern and "exaggerated minimalism" style, which suit
  marketing pages, not a data tool.
- The map-specific UX query returned no database match, so the map controls follow the general
  rules: 44 px touch targets, visible labels, a legend with a word for every colour, and keyboard
  operation.

**Information architecture (`dashboard/src/routes.ts`)**
- Top bar, five public sections: Home, Map, Barangays, Facilities, About.
- "For researchers", linked from About and the footer: Methodology (`#/methods`, the former
  About / Methodology page, unchanged in content), Data quality, Network connectivity.
- The provenance bar is removed from every page. Its facts (bundle version, generation time,
  integrity, audit, code version, datasets) are now a "Dataset status" panel on Data quality. The
  public pages show only the date the data was prepared.
- The facility inventory table moves from Overview/Facilities to Data quality.
- A notice appears on the public pages only when a dataset failed to load or the bundle is a newer
  minor version (`DataAlert.tsx`). Known issues stay on Data quality.
- "Notes for this view" (statement texts) appears on the researcher pages only.

**Public pages**
- Home: one sentence answers the question, e.g. "66% of Iloilo City residents can walk to a health
  center or clinic within 15 minutes", with service, walking/by car and time-limit controls.
  - Ten service cards show the same figure for every service.
  - "Barangays with the least access" lists the five lowest, ranking-eligible barangays only.
  - "Good to know" gives three plain caveats.
  - Removed from Home: the A1 comparison, the population-by-category bar, the distribution chart,
    the driving sensitivity table and the inventory.
- Map: Leaflet with a background-map switch.
  - Backgrounds: Street map (standard OpenStreetMap tiles), Satellite (Esri World Imagery, with Esri
    place names on top), or No background.
  - The choice is remembered in the browser (localStorage) and shared by every map, including the
    Facilities and Network maps.
  - A "Color strength" slider lets the imagery show through the barangay colours.
  - Barangays are coloured by share of residents or by typical time. The facilities of the selected
    service and an optional 100 m grid can be shown.
  - Clicking a barangay opens a details panel.
  - Removed from the map: the A3-category cell colouring, the low-reliability dashed outline, the
    separate outline layer and the table view (the Barangays page is the list view).
- Barangays: search, service, mode, time limit and sort ("Least access first", etc.).
  - Ranks are given to ranking-eligible barangays only.
  - When sorted by access, the others follow in a separate "Not ranked · limited data" group.
  - Equal shares are ordered by the longer typical trip.
  - The profile shows every service for walking and by car, the mapped facility counts, and the
    data confidence in words (Good / Fair / Limited).
  - Removed: A1 columns, p90, the unconnected % column, p-codes, the reliability filter chips and
    the compare tray.
- Facilities: type chips with counts, a name search, the map and a list. The card says where the
  place is, whether it counts in travel times (and why not), and links to OpenStreetMap.
  - Tier, roles, classification reason, connection distance and duplicate review are left to Data
    quality.
- About: what the dashboard does, the method in four plain steps, how to read the colours, five
  things to keep in mind, who made it, and cards to the researcher pages.

**Wording rules for the public pages (`src/model/plain.ts`, `src/model/labels.ts`)**
- Walking means the A3 (primary) result; "by car" means A1 driving. The A1 walking comparison
  appears only on the researcher pages.
- Everyday service names, e.g. "Health center" for primary care and "School" for basic education.
- Figures are rounded to whole numbers for reading ("<1%" for a small non-zero share); null is
  "No data", never 0. The technical pages keep the source precision.
- "Typical" walk or drive is the exported mean for connected residents. The p90 statistic is not
  shown on the public pages.
- Departure from rule R2: the short caveats on Home and About are written in plain language rather
  than quoted from `manifest.statements`. The verbatim statements remain on the researcher pages.

**Visual system**
- Tokens (`src/styles/tokens.css`): civic blue palette, larger type scale, larger radii.
- Map ramps: a blue-to-orange diverging scheme replaces the teal and purple ramps. Blue means close
  or most residents; orange means far or few. It stays readable with red–green colour blindness,
  and walking and driving keep their own class breaks.
- Styles: `src/styles/site.css` holds the shell and public pages. `app.css` keeps the base and the
  researcher-page components; its obsolete top-bar, provenance, map and footer sections were removed.
- New components:
  - `components/glyphs.tsx`: line icons for services and controls;
  - `components/controls.tsx`: service, mode and time-limit controls;
  - `map/BasemapSwitcher.tsx`;
  - `components/layout/DataAlert.tsx`.
- Removed: `components/layout/ProvenanceBar.tsx`.

**External requests (changed):** S4–S7 loaded no basemap tiles. The dashboard now requests map tiles
from tile.openstreetmap.org (street) or server.arcgisonline.com (satellite and place names), only
while a map with that background is on screen. "No background" requests none. The bundle itself is
unchanged and still loaded only from the dashboard's own folder. Attribution for each background is
shown on the map. CARTO tiles were tried first and rejected: they now require an API key.

**Tests:** `test/shell.test.ts` rewritten for the new navigation and pages (25 tests). Kept
guarantees:
- null shows as "No data", never 0;
- success tones only for verified, passed or clean states;
- a skipped audit is never shown as passed;
- a missing dataset is named;
- statements are quoted verbatim on the researcher pages.

New checks:
- no scenario or statement codes on the public pages;
- the headline sentence is read from the bundle.

`test/realBundle.test.ts`: the headline matches the exported A3 value, and unranked rows equal the
ineligible count. Vitest: 81 tests, all passing. `tsc` (both configs) and `vite build` pass.

**Checked in a browser on the real bundle:** all public pages at 1440 px, with no horizontal overflow
at 390 px.
- Switching street, none and satellite: tiles load, 48 of 48 for satellite, and the choice persists.
- No console errors.
- One overflow fixed: the reliability table on Data quality now scrolls on narrow screens.

**Unchanged:** the bundle, `data/`, `vite/`, the loader and validation, Python code and tests.

**Effect on results:** none (presentation only).

### 2026-11-01 — Milestone 05.2 S4–S7: analytical pages from the Claude Design prototype (uncommitted)

**Why:** The Claude Design prototype (`index.html`, `scripts/`, `styles/`; brief in its
`uploads/claude-design-prompt.md`) defines the top-navigation shell and the seven analytical pages.
This step rebuilds it in the React app on the real bundle, replacing the S3 sidebar and placeholders.

**Changed (`dashboard/`)**
- Shell: the left sidebar is replaced by a sticky top bar (`src/components/layout/TopBar.tsx`).
  - Below 75rem, the three reference sections move under a "Reference" menu.
  - Below 56rem, all sections move into a menu panel: focus moves in, Escape closes it, and choosing a
    section closes it.
- The provenance bar is now a compact colophon, and a footer is added.
  - Known issues and loader conditions are collapsed behind "N bundle notices".
  - The notices open by themselves when a dataset failed.
- Styles:
  - `src/styles/tokens.css` gains the prototype's additions: travel-time, drive and share ramps; A3
    category, reliability, scenario and facility-category colours; evidence surfaces.
  - `src/styles/app.css` is the prototype stylesheet; `shell.css` is removed.
- View state in the address (`src/model/view.ts`, `src/view.tsx`):
  - group, walk threshold, mode, drive threshold and statistic are shared between pages;
  - other parameters belong to their page;
  - values outside the manifest's groups and thresholds fall back to the default.
- Caveats (`src/components/notes.tsx`):
  - numbered references and code chips open the statement text from `manifest.statements`;
  - "Notes for this view" lists each statement used on the page once.
- Pages (`src/pages/`):
  - Overview.
  - Accessibility Map: Leaflet, canvas cells, a barangay drawer and a table alternative.
  - Barangay Analysis: sort and filter; ranks for ranking-eligible barangays only; a profile; compare
    up to 3.
  - Facilities: map, list, facility card and inventory.
  - Network Connectivity: evidence only; analysis-only records are stamped "not applied".
  - Data Quality.
  - About / Methodology.
- `src/contract/types.ts`: the network and provenance parts are now typed. If the bundle lacks a part,
  only that panel says "could not be shown" (`guard()` in `States.tsx`).
- Departures from the prototype:
  - Every figure the prototype typed in (totals, counts, the A1 → A3 sentence, gap-card statuses) is
    read or counted from the bundle.
  - No basemap tiles are loaded, so the dashboard makes no request outside its bundle.
  - Charts are SVG and HTML as in the prototype, not Chart.js.
  - Leaflet is used directly and loaded on first use, not through react-leaflet.
  - The design-only routes `#/components` and `#/states` are not built.
- Tests:
  - `test/shell.test.ts` is rewritten for the new shell and pages (23 tests).
  - `test/realBundle.test.ts` renders every page from the real bundle. It checks the exported figures,
    the distribution end point and the ranks.
  - Vitest: 79 tests, all passing.

**Checked in a browser on the real bundle**
- All seven routes, with no console errors and no broken panel.
- The map: cells, facilities, legend and barangay drawer.

**Unchanged:** the bundle, `data/`, `vite/`, the loader and validation, Python code and tests.

**Effect on results:** none (presentation only).

### 2026-11-01 — Milestone 05.2 S3: dashboard application shell (uncommitted)

**Why:** S3 sets out the dashboard's identity, layout, navigation and global states before any
analytical page is built.

**Added (`dashboard/`)**
- Design tokens (`src/styles/tokens.css`): typography, spacing, a restrained deep-teal palette,
  borders, surfaces, navigation states and status colours. Text contrast meets WCAG AA, and every
  status shows a symbol and a word as well as a colour.
- The shell (`src/components/layout/`) has:
  - a skip link;
  - a sidebar with the project identity, tagline and supporting phrase;
  - section navigation that marks the active section with `aria-current="page"`;
  - a header with a menu button for small screens;
  - a provenance bar on every page.
- Provenance bar (`src/model/shell.ts`): dataset version, generation time, integrity, audit, code
  version and dataset availability, all read from the bundle.
  - "OK" is shown only for verified, passed or clean states.
  - Unverified integrity, a skipped audit and a dirty tree are warnings; unknown Git status is shown
    as unknown.
- Interface states (`src/components/states/`):
  - loading (announced to screen readers);
  - fatal error (every issue listed; navigation stays usable);
  - bundle-wide notices: integrity not verified, newer contract, failed datasets;
  - per-page dataset availability, with the reasons for anything that failed;
  - an empty placeholder.
- Seven routes registered once in `src/routes.ts`: Overview, Accessibility Map, Barangay Analysis,
  Facilities, Network Connectivity, Data Quality, About / Methodology. All are placeholders that show
  no values.
- Routing:
  - an unknown section falls back to Overview, and the address is corrected to match;
  - each route change moves focus to the page heading and sets the document title.
- Small screens (below 56rem): the navigation becomes a drawer. Opening it moves focus into the
  menu; Escape closes it and returns focus to the button; choosing a section closes it.
- 17 shell tests (`test/shell.test.ts`, rendered with react-dom/server; no new dependency).

**Checked in a browser on the real bundle**
- All 7 routes, the active-route marking and the focus moves.
- The skip-link and focus rings.
- The drawer cycle at 387 px width.
- One defect found and fixed: on narrow screens the long Code badge was wider than the screen.
  Badges now wrap.

**Unchanged:** `vite/bundlePlugin.ts` and `vite.config.ts` (byte-identical), the bundle, `data/`,
Python code and tests (230 passing).

**Effect on results:** none.

### 2026-11-01 — Milestone 05.2 S0–S2: contract clarifications, exporter hardening, frontend foundation and data loader (uncommitted)

**Why:** M05.1 was accepted with discrepancies D1–D10. M05.2 starts with fixing them (S0), then the
frontend foundation (S1) and the layer that loads and checks the bundle (S2). No dashboard page yet.

**S0 — contract (`docs/DASHBOARD_DATA_CONTRACT.md`, still 1.0.0)**
- D1: the frontend must show caveat texts from `manifest.statements`; components never retype them;
  an unresolved code is a load error.
- D3: `analysis_only` / `applied` are on every record of the three access tables.
- D4: `data_quality.classification` is an identical copy of the top-level facility fields.
- The outdated "wording may be refined at approval" heading is removed.
- New §10.1.1 for D8: exactly which directories are exporter-owned, when a backup is restored or
  removed, and when recovery stops for manual resolution.
- Git fields now say `git status --porcelain -z`.
- V-C1 now lists the independent recomputation it performs.

**S0 — exporter (`src/abot/dashboard_data.py`, `tests/test_m05.py`)**
- D6: Git status parsed from `--porcelain -z`; paths with spaces are kept literally, and a rename
  counts once.
- D7: V-C1 recomputes every bin, the open bin, every cumulative point and the final point from
  `cells_a3` with plain masks, independently of the binning code.
- D8:
  - every failed check is printed, with no 200-message cap;
  - recovery touches only `.v1.tmp-<12 hex>` / `.v1.old-<12 hex>`;
  - a backup is deleted only when `v1/` verifies completely;
  - several or incomplete backups stop the export.
- D9: when `v1/` is missing, `--check` reports each backup, says whether it is complete, and says
  whether the next export restores it.
- 12 regression tests added. The recovery tests were rewritten for the ownership rule.
- The bundle was regenerated with the hardened exporter (all checks pass).
- `.gitignore`: `node_modules/`, and the exception `!/dashboard/src/data/`. The existing unanchored
  `data/` rule also matched the loader folder `dashboard/src/data/`, which would otherwise never be
  committed. `/data/` and `dashboard/dist/` stay ignored.

**S1 — `dashboard/`**
- Vite + React + strict TypeScript; hash routing with no router library; no backend.
- `vite/bundlePlugin.ts`:
  - in development, each file is read per request and nothing is watched;
  - at build, only the manifest's files are copied, each size- and hash-checked.
- Verified:
  - `abot export-dashboard` ran successfully while the dev server was running (Windows directory
    renames not blocked);
  - the dev server refuses paths outside the bundle (404);
  - the build copies the 9 files byte-identically.

**S2 — data layer**
- Contract types and version check:
  - another contract ID or major version is refused;
  - a newer minor version gives a warning;
  - an older minor or any patch difference is compatible.
- The loader checks each file's size and SHA-256 (or reports verification as unavailable), its
  envelope and its shared `generated_utc`.
- The cells are rebuilt in chunk order; any problem disables the cell layer and it is never partial.
- Validation also covers:
  - indicator IDs and their levels against the catalogue;
  - statement codes;
  - the distribution shape;
  - the audit state;
  - the facility classification copy.
- Values pass through unchanged; null stays null.
- Fixture bundle and 55 Vitest tests, including one read-only test on the real bundle.

**Files:** `docs/DASHBOARD_DATA_CONTRACT.md`, `src/abot/dashboard_data.py`, `tests/test_m05.py`,
`.gitignore`, this file, and new `dashboard/**` (excluding `node_modules/` and `dist/`, which are
ignored).

**Effect on results:** none. No analytical output, raw file or archive changed; the bundle was
regenerated from unchanged sources.

### 2026-11-01 — Milestone 05.1: dashboard data exporter `abot export-dashboard` (uncommitted)

**Why:** M05 needs the contract of M05.0 implemented as a reproducible, validated bundle that a static
frontend can load without re-deriving any result.

**Approved decisions applied first (contract, documentation only)**
- Audit gate (Q3):
  - `pass` and `warn` allow the export; `warn` is kept in the bundle as known issue `AUDIT-WARN`.
  - `fail` and `error` block it: nothing is written and the previous bundle is kept.
  - `not_run` happens only with `--skip-audit` and is recorded as `AUDIT-NOT-RUN`.
  - Checked by the new rule V-A1; the command line is documented in §10.3.
- Distribution (Q5): fixed 60-minute cap with an open "> 60 min" bin.
  - The cumulative series now ends with a point that includes the open bin, so those residents are
    in the bins, the cumulative curve and the totals (hospital at discovery: 19,602.6 residents above
    60 min).
- `manifest.statements` added. Statement codes had no texts anywhere in the bundle; additive, not a
  breaking change.

**Added**
- `src/abot/dashboard_data.py` and the `abot export-dashboard [--skip-audit] [--check]` command in
  `src/abot/cli.py`.
- What the exporter does:
  - hashes the 31 source files of contract §7.1.1 and runs V-S2–V-S4;
  - runs the existing `abot.audit.Audit` in-process (read-only, no reimplementation);
  - builds the 8 datasets in memory and splits the cells into chunks under 4,000,000 bytes, in
    `cell_id` order;
  - writes everything into `data/processed/dashboard/.v1.tmp-*`, re-reads the files and runs every
    §10.2 check on them;
  - re-hashes the sources (V-X1), then swaps the directory into `v1/` with two renames.
- `--check` reports staleness and writes nothing. An experiment configuration is refused.
- `tests/test_m05.py`: 18 tests. They cover:
  - serialisation and nulls;
  - right-closed bins and the open bin;
  - chunk rule;
  - audit states and gate;
  - display geometry wrapping, and that an invalid geometry fails instead of being repaired;
  - catalogue typing;
  - install and crash recovery;
  - `--check`;
  - export blocked by a failed audit, and a failed validation that keeps the previous bundle.

**Bundle at export (2026-10-31T22:47 UTC)**
- 9 files, 10,186,866 bytes:

  | File | Bytes |
  |---|---|
  | `cells-001.geojson` (4,018 cells) | 3,469,352 |
  | `cells-002.geojson` (4,017 cells) | 3,469,534 |
  | `barangay_indicators.json` | 1,764,729 |
  | `facilities.geojson` | 808,641 |
  | `manifest.json` | 177,393 |
  | `barangays.geojson` | 183,593 |
  | `network.json` | 171,498 |
  | `city.json` | 107,198 |
  | `provenance.json` | 34,928 |

  The single-file cell form would be 6,937,203 bytes.
- 303 catalogue entries (202 barangay-level, 231 city-level).
- Audit `obtained` / `warn` (58 pass, 3 warn, 0 fail, 11 info); known issues `AUDIT-WARN`,
  `GIT-DIRTY`.
- Repeatability: two exports from the same sources were compared after setting aside the fields that
  depend on the run itself: `generated_utc`, the audit `ran_utc`, and every `sha256` of a bundle file
  (each file embeds `generated_utc`, so its hash changes from run to run). With those fields set aside,
  all 9 files were identical, and so were their sizes. The bytes on disk are therefore not identical
  between runs; the content is.
- Every source file and the rest of `data/` are byte-identical before and after (299 entries
  compared).

**Files:** `src/abot/dashboard_data.py` (new), `src/abot/cli.py`, `tests/test_m05.py` (new),
`docs/DASHBOARD_DATA_CONTRACT.md`, this file. No dependency added.

**Effect on results:** none. No A1/A2/A3 value, network, population, classification or review decision
changed; the bundle is derived data and the sources remain authoritative (R1).

### 2026-11-01 — Milestone 05.0: final review of the dashboard data contract (documentation only; uncommitted)

**Why:** before implementation, the contract was checked against the outputs and the code, not only
proofread.

**Changes to `docs/DASHBOARD_DATA_CONTRACT.md` (still 1.0.0)**
- Q1: 2e-5° is an angle in EPSG:4326, not a displacement bound (measured median 2.0 m, max 3.9 m);
  polygons are wrapped as MultiPolygon; display only.
- Q3: the audit is called in-process; it was verified read-only.
- Q9: one file would be 6.94 MB, so the cells are written as deterministic chunks.
- Q5: the bin rule is now unambiguous.
- Corrections:
  - `relation/` facility IDs (36) were missing;
  - R5 counts corrected;
  - `pct_not_connected` rounding (2 decimals);
  - M03 `n_edges` counts directed edges, so it is taken from the inventory;
  - a missing gap-evidence field added;
  - "absent" fields made `null`;
  - catalogue IDs with mixed units split;
  - the A1 drive label separated from the walking label;
  - frontend staleness claims removed;
  - Windows-safe two-rename install;
  - figures in statements are now filled from the sources;
  - complete source-file list (§7.1.1).

**Effect on results:** none.

### 2026-10-31 — Milestone 05.0: dashboard data contract `abot-dashboard v1.0.0` (documentation only; uncommitted)

**Why:** the M05 analytical dashboard needs a fixed, verified interface to the existing outputs so it
communicates their meaning without re-deriving or oversimplifying it. The M05 discovery found the traps
the contract must close:
- cells cannot be summed to barangays (179 of 180 differ, up to 1,070.7 residents);
- legacy layers remain in `abot_iloilo.gpkg`;
- `citywide_a3.csv` mixes percentages and resident counts;
- the coordinate systems are mixed;
- `facilities.csv` lacks connection status;
- component geometry exists for 9 fragments only.

**Added**
- `docs/DASHBOARD_DATA_CONTRACT.md`. It covers:
  - authority rules R1–R14: the CSV and GeoPackage outputs are authoritative, no new calculation,
    no cell→barangay aggregation, A3 primary, A1 comparative, A1 drive a separate mode,
    local-only and uncertain access never merged into citywide access, null never zero;
  - the indicator catalogue with numerator, denominator and the population each statistic describes;
  - the `data_quality` schema with required statements;
  - eight datasets (`manifest`, `city`, `barangays`, `barangay_indicators`, `cells`, `facilities`,
    `network`, `provenance`) with sources, fields, types, units, nulls, CRS, transformations and
    validation;
  - geometry rules: EPSG:4326, 6 decimals, display simplification, bounding boxes never drawn as
    networks;
  - provenance and stale-bundle detection: commit SHA plus working-tree cleanliness;
  - exporter checks V-*;
  - limitations, unsupported indicators, 8 open questions, versioning.

**Verified while authoring (read-only):**
- the destination rule is role-level and reproduces `facility_inventory.n_destinations_connected`
  for all 10 groups;
- `n_<group>` counts any tier;
- A1 barangay shares are rounded to 1 decimal, A3 shares to 2;
- the A1 and A3 cell connection statuses differ (302 vs 263 cells not connected);
- the duplicate-review identifiers match `fid_key`.

**Files:** `docs/DASHBOARD_DATA_CONTRACT.md` (new), this file.

**Effect on results:** none. No code, output, network, scenario or classification changed; no bundle
generated.

**Paper notes:** a dashboard is a presentation layer. State each indicator's denominator and the
population its mean describes, and keep the primary (A3 walk), comparative (A1 walk), separate-mode
(A1 drive) and evidence-only (A2, access taxonomy, gap evidence) roles visible.

### 2026-10-31 — Milestone 04: methodology review of the access taxonomy (uncommitted)

**Why:** the approved M04 follow-up access classes conflated road function with access restriction.
`access=private` became `resident_restricted` on `service` roads (so the fishport compound roads
read as "residents and visitors"), and `private_uncertain` on other roads (so Gustilo Street,
`tertiary` + `access=private`, read as "uncertain"). `ineligible` mixed prohibited with private,
`access=customers` + `foot=permissive` became plain public, and the snapshot corridor rule needed
**all** path ways to be restrictive. Physical connectivity, mapped restriction, public pedestrian
access and authorised-user access must stay separate. Details:
[docs/MILESTONE_04_ACCESS_TAXONOMY.md](docs/MILESTONE_04_ACCESS_TAXONOMY.md).

**Added**
- `src/abot/access.py`: `access_assessment` returns `mapped_access_status` (`no`, `private`,
  `residents`, `customers`, `unknown`, `destination`, `pedestrian_override`, `untagged`, `public`),
  `deciding_tag`, `public_pedestrian_status`, `authorized_group`, `field_verification_required` and
  `classification_reason`.
  - Precedence: `foot` decides. A public foot value with private/residents/customers is a flagged
    conflict (`pedestrian_override`); with `access=no` it is a recorded override (`public`).
  - `highway` never changes the status; permissive is documented as revocable.
- Exact component-class check in `abot components` against the archived pre-review inventory (all
  112 components; class plus rule inputs) → `review/m04/taxonomy_check.json`.
- Archive `data/archive/review_m04_pre_access_taxonomy/` (`review/m04`, `component_aware`, and the
  old-to-new crosswalk; 27 files, verified); `archive.archive_m04_pre_access_taxonomy`.
- New evidence columns: gate table (`locked` and the assessment fields), restricted-way table,
  per-status `public_pedestrian_status` and gate verification counts, corridor
  `path_mapped_access_status` / `public_pedestrian_status` / `authorized_group` /
  `classification_reason`, gap-table `snapshot_*` status columns.
- 35 tests.

**Changed:**
- Snapshot corridors use the shared assessment, and the **any** rule on the path (ways and gates).
  The legacy `public_pedestrian_access` column is kept.
- Removal scenarios are defined on raw gate tags (`gate_tag_flags`) as before. Their numbers are
  unchanged; only two definition texts were clarified.
- `remaining_unverified` no longer names presumed user groups.
- Old labels are retired; superseded notes were added to the follow-up results and the snapshot
  review. The land-use refinement suggested there was not adopted.

**Files:** `src/abot/access.py` (new), `src/abot/{components,archive}.py`, `src/abot/fetch/targeted.py`,
`tests/test_m04.py`, `docs/METHODOLOGY.md` §3.1, `docs/MILESTONE_04_ACCESS_TAXONOMY.md` (new),
`docs/MILESTONE_04_{FOLLOWUP_RESULTS,SNAPSHOT_REVIEW}.md` (notes), `docs/DATA_DICTIONARY.md` §10,
this file.

**Effect on results:** none on any number.
- **Identical before and after:** walk-graph topology (15,376 nodes, 39,698 edges, 112 components:
  fingerprint), all 112 component classes and rule inputs, A3 CSVs (byte-identical), the A3
  GeoPackage (content), baseline hashes, population 457,626, facility travel times, and the
  targeted snapshot (hashes match).
- **Labels changed:** 52 ways `ineligible`→`no` (50) / `private` (2); 3 ways `public`→`pedestrian_override`
  (0.12 km, main); 4 ways `uncertain`→`unknown`; 167 gates `private_uncertain`→`private`; 35 gates
  `ineligible`→`no` (31) / `private` (4); 3 gates →`unknown`.
- **Checks:** tests 165 → 200; audit PASS 57 / WARN 3 → PASS 58 / WARN 3 (the new archive verified).
- F001, F100 and F101 stay physically connected in OSM topology, `private`, `not_public`, with an
  unspecified authorised group, unapplied, and `locally_connected` in A3.

**Paper notes:** report four kinds of evidence separately: physical connectivity (topology), mapped
restriction (tags), public pedestrian access (tags, unverified on site) and authorised-user access
(only when a tag names the group, or in an explicitly assumed scenario). A private service road is
not a residents' road, and a tertiary road can be private. Neither a missing tag nor a missing gate
is evidence of public access.

### 2026-10-31 — Milestone 04: targeted Overpass candidate review and stale-documentation fix (uncommitted)

**Why:** the user's single approved run of `abot fetch-gaps --allow-download` produced
`data/raw/osm_targeted/m04_gaps_20261031T131445Z.json` (1,117 elements, OSM base
2026-10-31T13:14:07Z, SHA-256 `12922cd2…`). The two generated link candidates needed a geometric and
access review. The generated gap table and README still said the snapshot was "not obtained".

**Added**
- `targeted.corridor_analysis` → `review/m04/snapshot_corridor_analysis.csv`: for each candidate and
  fragment, the contact nodes, the shortest route along candidate ways, gates on the route and the
  corridor, exact access tags, and separate verdicts for physical connection (OSM topology), public
  pedestrian access (mapped tags only) and field verification.
- `docs/MILESTONE_04_SNAPSHOT_REVIEW.md`; 6 tests.

**Fixed:** stale generated documentation. `gap_investigation()` ran before the snapshot was read
and wrote a fixed "(not obtained)" sentence, and the README section was fixed as "cache evidence
only". Now the snapshot is read first; the gap table separates `cache_*` measurements from `snapshot_*`
evidence; the remaining-unverified text depends on the actual state; the README has a "Targeted
snapshot evidence" section; and with no snapshot, stale snapshot tables are removed.

**Findings [observed]:** F001 is linked in OSM topology through Gustilo Street (`access=private`,
gated at the public road) and an 87 m private way with no mapped gate. F100/F101 are linked through
private fishport service roads ending at private gates. Public pedestrian access is restricted
according to mapped tags for all three, and field verification is needed. Component classes, A1/A2/A3
and routing are unchanged.

**Files:** `src/abot/components.py`, `src/abot/fetch/targeted.py`, `tests/test_m04.py`, docs.

**Effect on results:** none. Before and after regeneration, the baseline, the A3 layer, the other
evidence, the snapshot and the review CSVs are byte-identical. Only `gap_investigation.csv`,
`snapshot_status.json` and the README changed, and `snapshot_corridor_analysis.csv` is new. Tests
159 → 165.

**Paper notes:** an OSM fragment that looks isolated can be a gated private subdivision whose access
roads the routing profile removes. Report physical connectivity (topology), legal/public access (tags)
and observed use (field) as three separate kinds of evidence.

### 2026-10-31 — Milestone 04 follow-up: approved decisions implemented (uncommitted)

**Why:** the user approved the A3 component-aware layer as an additional reporting layer, an access
classification for reporting only, removal of the verified `e7_buffer_3km` originals, and 7 duplicate
classifications. Details: [docs/MILESTONE_04_FOLLOWUP_RESULTS.md](docs/MILESTONE_04_FOLLOWUP_RESULTS.md).

**Added**
- A3 reporting layer in `data/processed/component_aware/` (cells, barangay counts and percentages,
  citywide A1 vs A3, GeoPackage). Citywide indicators use main-network residents only, internal
  accessibility is kept in separate columns, and access-uncertain residents are kept apart. Baseline
  file hashes are checked before and after; A1 is labelled the optimistic connectivity scenario.
- Access classes revised to the approved scheme (`foot=private` ineligible; `access=private`
  resident-restricted or uncertain by context; private gates flagged; untagged gates not excluded),
  with a per-class summary of ways, edges, km, gate nodes, components, cells and residents.
- Snapshot evidence analysis (`targeted.snapshot_evidence`): runs automatically once the user's
  approved `fetch-gaps --allow-download` has produced a snapshot. Link candidates are never applied.
- `archive.remove_verified_originals`; `review.record_duplicate_decisions` /
  `revert_duplicate_decision` with `review/review_decisions_log.csv`; restore point
  `data/archive/review_pre_m04_decisions/`; audit check `component_aware_layer_current`.

**Changed / Fixed**
- `review._keep_reviewer_columns`: a duplicate decision is carried over only while the same two OSM
  records form the pair. Before this fix, positional ids could move a decision to another pair after an
  OSM update.
- `facility_review_summary` reads the live reviewer columns.

**Removed:** `data/interim/e7_buffer_3km/`, `data/processed/e7_buffer_3km/`,
`data/processed/comparisons/e7_buffer_1km_vs_3km/` (20 files), after hash verification. They are
archived in `data/archive/hist_e7_buffer_3km_m02/` (21/21 verified after removal); the config is kept.

**Files:** `src/abot/{components,archive,review,audit}.py`, `src/abot/fetch/targeted.py`,
`tests/test_m04.py`, `data/processed/review/README.md` (decision note), docs.

**Effect on results:** active baseline **none** (hash-checked). Reporting layer (A3, walking):
main-network connected 98.08%, locally connected 1.14%, access-uncertain 0.02%, unconnected 0.76%
(A1: 99.13% connected, 0.87% unconnected); hospital ≤ 15 min 22.90% (A1) vs 22.64% (A3). Duplicate
review: 14 → 7 pending; no facility count changed. Tests 138 → 159; audit PASS 55 / WARN 4 → PASS 57 / WARN 3.

**Paper notes:** report A1 as the optimistic connectivity scenario and A3 as the component-aware
scenario. Present them side by side, and keep internal (within a gated or isolated network)
accessibility distinct from citywide access. Distinguish physical traversability, public access and
resident-restricted access when interpreting OSM access tags.

### 2026-10-31 — Milestone 04: network connectivity investigation (read-only; uncommitted)

**Why:** Milestone 03 showed that the largest-component filter drops a 10.4 km Tabuc Suba
subdivision (F001) 10.9 m from the main network, and that 4,812 connected residents reach the
network only by a longer straight connector. This milestone asks whether the component policy and
OSM access handling are appropriate, before changing anything.

**Added**
- `abot components` (`src/abot/components.py`): inventory and classes of all 112 walk components;
  comparison of A1 (current), A2 (all eligible components) and A3 (component-aware: network-connected
  / locally connected / access-uncertain / unconnected, with internal times kept apart); way and
  gate-node access classes; removal impact per restriction tag; F001/F100/F101 cache evidence; facility
  review summary. Writes `data/processed/review/m04/`.
- `abot fetch-gaps` (`src/abot/fetch/targeted.py`): the approved targeted Overpass query (3 gap
  corridors at 50 m plus the F001 box at +50 m; every highway way with no access filter, plus barriers,
  entrances, bridges and `noexit`). Validated statically; downloads only with `--allow-download`,
  into `data/raw/osm_targeted/`, never into `osm_cache/`.
- `src/abot/archive.py` and the archive `data/archive/hist_e7_buffer_3km_m02/` (21 files, SHA-256
  verified three ways; originals kept).
- `tests/test_m04.py` (35 tests); `docs/MILESTONE_04_RESULTS.md`, `docs/MILESTONE_04_AUDIT.md`.

**Not obtained:** the Overpass snapshot (the server closed the single approved request; nothing
saved) and the D10 BPI directory (HTTP 404).

**Files:** `src/abot/{components,archive}.py`, `src/abot/fetch/targeted.py`, `src/abot/cli.py`,
`tests/test_m04.py`, docs.

**Effect on results:** none. The baseline, 1 km historical and speed-sensitivity outputs were not
rebuilt, and no review decision was entered. Scenario figures (not applied): A3 network-connected
453,656.9 → 448,855.8, locally connected 5,206.0, access-uncertain 91.9, unconnected 3,969.1 →
3,472.3; citywide hospital ≤ 15 min walk 22.90% → 22.64%. Tests 103 → 138; audit PASS 54 → 55, WARN 4,
FAIL 0.

**Paper notes:** the largest-component filter has two opposite failure modes. It overstates access
by giving citywide times through a straight connector, which at F001 runs to points mapped as
`noexit`. Retaining all fragments with nearest-edge attachment understates access, because hospitals
and campuses get attached to their internal path fragments. A component-aware classification that
keeps internal and citywide access separate avoids both and makes the uncertainty explicit. OSM
`noexit=yes` is useful evidence that a gap is deliberate.

### 2026-10-31 — Milestone 03: manual spatial validation and analytical finalization (uncommitted)

**Why:** to finish the open review items from Milestone 02B (14 duplicate pairs, 302 unconnected
cells, 13 disconnected external facilities) and the stale speed-policy sensitivity outputs, without
applying any unverified manual decision.

**Added**
- `abot validate` (`src/abot/validation.py`). It reads outputs, review files and the Overpass cache;
  it refuses HTTP requests and writes only `data/processed/review/m03/`. Contents: duplicate desk
  assessment (polygon overlap, OSM-id gap, tag identity, sub-type), the walk-network fragments dropped
  by the largest-component filter and their gaps to the main network, a diagnostic class per
  unconnected cell, pond-polygon checks, disconnected-facility diagnostics, a connector-tolerance
  sensitivity, connected cells nearer to an unlinked fragment, a GeoPackage and a map.
- `abot audit` checks: `validation_files_current`, and `experiment: <run>` freshness for every
  `config/experiments/*` run (this is the gap that let the stale speed outputs go unnoticed).
- 18 tests (`tests/test_m03.py`); 103 pass. `docs/MILESTONE_03_RESULTS.md`, `docs/MILESTONE_03_AUDIT.md`.

**Changed**
- `sens_maxspeed_override` rebuilt on the 3 km baseline with the current code (cache only), and
  `comparisons/speed_override_vs_cap` regenerated. The stale 1 km / M02 outputs were moved, with a
  SHA-256 record, to `data/archive/stale_sens_maxspeed_override_m02_1km/`.

**Not changed:** no pipeline stage, no baseline output, no review decision. The three review CSVs are
byte-identical. The M01 and M02 archives are unchanged.

**Files:** `src/abot/{validation (new),audit,cli}.py`, `tests/test_m03.py` (new),
`docs/MILESTONE_03_{RESULTS,AUDIT}.md` (new), `docs/{METHODOLOGY,DATA_SOURCES}.md`, this file;
data: `review/m03/` (new), `sens_maxspeed_override/` and `comparisons/speed_override_vs_cap/`
(regenerated), `data/archive/stale_sens_maxspeed_override_m02_1km/` (new), `data/raw/manifest.json`
(`used_by_runs`).

**Effect on results:** baseline indicators are unchanged. Speed-policy sensitivity (stale M02 1 km →
regenerated 3 km): car to hospital ≤ 10 min, override vs cap 93.1% vs 81.7% → 92.0% vs 79.6%; mean
6.38 vs 7.61 min. Walk is identical between the two runs, and no cell is faster under the cap.
Audit PASS 50 / WARN 3 → PASS 54 / WARN 4 (new WARN: stale `e7_buffer_3km`), FAIL 0.

**Findings (desk evidence, pending decisions):**
- Duplicates: 2 same facility (D13, D14), 5 distinct, 6 likely duplicates, 1 uncertain.
- Unconnected (3,969 residents): 2,537 with no mapped way within 250 m (2,326 in one Calahunan /
  Hibao-an Sur cluster), 832 cut off by a watercourse, 528 next to unlinked OSM fragments (all of
  Tabuc Suba's and Baybay Tanza's), 72 in mapped water (53 in 30 pond polygons, none contradicted
  by mapped ways).
- The 13 external facilities are all on Guimaras: they are separated by the strait, not misplaced.
- *Reviewer imagery check* (Google Earth Pro; Maxar 2020-05-15, Airbus 2026-07-22): the Calahunan /
  Hibao-an Sur cluster is a set of established paved residential subdivisions (Monterosa Estate,
  Anaros Village), populated since at least 2020, and not a landfill. Their streets are absent from
  the walk network, so the cluster's not-connected status is a network-data artefact. Whether the
  streets are unmapped in OSM or excluded by the walk filter (for example `access=private`) is still
  open. Nothing applied.
- 4,812 connected residents rely on a longer connector because their nearest mapped way is an
  unlinked fragment; fragment F001 is a 10.4 km subdivision 10.9 m from the main network.

**Paper notes:**
- Report the not-connected share together with its tolerance sensitivity (3,969 at 250 m → 1,407
  at 500 m).
- The largest-component filter is a real source of error for gated subdivisions and newly mapped
  coastal paths; describe it as a limitation of OSM topology.
- Treat the duplicate desk assessment as evidence, not a decision.

### 2026-10-31 — Milestone 02B: baseline adoption, reliability flags, audit, manual review (commit `3e85764`)

**Why:** the user approved the 3 km buffer (E7) and validity-assessment proposals P1, P2 and P4–P7.
Two goals: no indicator should silently drop residents, and the analytical reliability of every
barangay should be stated per dimension.

**Added**
- `config/experiments/hist_buffer_1km.yaml` (historical 1 km buffer; only the buffer differs).
- Census-anchored weights `pop_census2020_adj`, kept beside the original `pop_wp2020` /
  `pop_wp2026`; `population.primary_weight`. Fractional cell allocation (`pop_pieces` layer).
- `reliability.py`: `rel_population`, `rel_network`, `rel_facility_inventory`, `rel_overall` with
  reasons, plus `pop_ranking_eligible` and `facility_inventory.csv`. No combined score.
- `<mode>_<group>_p90_min`; car network-time sensitivity (`drive_speed_sensitivity.csv`, report
  section).
- `abot review` (`review.py`): duplicate-pair and unconnected-cell review CSVs, `review.gpkg`, two
  HTML maps. Status `pending`; nothing applied.
- `abot audit` (`audit.py`): read-only PASS / WARN / FAIL / INFO with actions; stage records
  (`run_meta.json`) and a configuration fingerprint for staleness; SHA-256 records for the archives.
- Structured duplicate fields (`related_osm_type`, `related_osm_id`, `distance_m`) in
  `facility_exclusions.csv`. QA: external destinations, mixed-class edges, anchoring checks.
- `data/archive/m02_wip_1km_20261031/`: a copy of the uncommitted M02 1 km outputs, made before
  rebuilding. `m01_3edc0dd` is untouched (hash verified).
- 32 tests (`tests/test_m02b.py`); 85 pass. `docs/MILESTONE_02B_RESULTS.md`.

**Changed**
- Default `osm.boundary_buffer_m` 1000 → 3000.
- Shares `pct_le<N>` now use **all** residents (previously the connected residents), in
  `barangay_access`, QA and `abot compare`. `max_min` was replaced by `p90_min`.
- Layers `pop_cells_<year>` / `access_cells_2026` became `pop_cells` / `access_cells` (`abot compare`
  reads both).
- Wording (P4–P6): COD-AB polygon area; "modelled uncongested car travel time"; proximity, not
  service level or capacity; WorldPop–census agreement is not validation.

**Fixed**
- Non-deterministic car speeds on merged edges with several highway classes (osmnx list order comes
  from a set). The slowest configured class is now used (32 edges, 9 km). Found while re-running
  E7: 81 residents appeared slower with 3 km.
- Stage timestamps are recorded to the millisecond, so stage order is unambiguous.

**Files:** `config/settings.yaml`, `config/experiments/{hist_buffer_1km (new),e7_buffer_3km,sens_maxspeed_override}.yaml`,
`src/abot/{population,accessibility,osm,boundaries,compare,report,cli,config,qa}.py`,
`src/abot/{reliability,review,audit}.py` (new), `tests/test_m02.py` (one assertion),
`tests/test_m02b.py` (new), `README.md`, `docs/{METHODOLOGY,DATA_DICTIONARY,MILESTONE_02_RESULTS}.md`,
`docs/MILESTONE_02B_RESULTS.md` (new), this file.

**Effect on results:**
- Population total 492,459 (WorldPop 2026) → 457,626 (census-anchored 2020).
- Not connected 4,538 (0.92%) → 3,969 (0.87%).
- Walk to hospital ≤ 15 min 24.9% → 22.9%, mean 27.26 → 27.92 min.
- Car to hospital ≤ 10 min 81.7% → 79.6% (38.5% at 2× network time).
- E7 under M02B: ≤ 0.08 min city-wide; Hibao-an Norte primary care 42.5 → 30.0 min.
- Reliability: rel_overall ok / caution / low 92 / 57 / 31.

**Paper notes:**
- Report census anchoring as a *weighting choice*, not a validation result.
- Report reliability per dimension, and state that low-population-reliability barangays are
  excluded from population-based rankings.
- Report the determinism bug as a reproducibility lesson: library attribute order can depend on
  hash seeds.

### 2026-10-31 — Milestone 02: Priority 0 corrections, category refinement, E7 (uncommitted)

**Why:** the analytical audit and the validity assessment found that several Milestone 01
indicators were misleading for identifiable reasons:
- "health" was dominated by dental, laboratory and therapy features and included a veterinary
  hospital;
- evacuation was reported quantitatively from 5 OSM features;
- straight-line snap legs crossed mapped water;
- OSM `maxspeed` overrode the configured speeds;
- two QA checks could not fail;
- the OSM snapshot was not recorded.

**Added**
- Facility sub-types and reporting tiers in all nine categories. Multi-category membership
  (`facility_roles` layer). Classification status and reason per feature. All OSM tags kept as
  JSON. `facility_exclusions.csv` (merged points, possible duplicates).
- Ten indicator groups of indicative sub-types. The config refuses non-indicative sub-types in a
  group.
- Barrier layer (water, waterways, coastline; culverts crossable; walls flagged). Edge-based,
  water-aware connection of cells and facilities with tolerances. Unconnected population reported
  per barangay with a > 5% flag (validity assessment P3, in part). Drive access routed on the walk
  network.
- Drive speed policy (`maxspeed_policy: cap`), `*_link` speeds, per-edge `speed_source`.
- QA: connection, conservation, connected-without-time, component filter, speed sources, population
  density r, small-barangay bias, error share, OSM provenance (timestamps, SHA-256, `used_by_runs`).
- `abot compare` command; experiment configs with `extends:` and `run_name`;
  `config/experiments/e7_buffer_3km.yaml` and `sens_maxspeed_override.yaml`.
- `docs/METHODOLOGY.md`, `docs/DATA_DICTIONARY.md`, `docs/DATA_SOURCES.md` (incl. registry research),
  `docs/MILESTONE_02_RESULTS.md`.
- 40 regression tests (`tests/test_m02.py`); 53 tests pass.

**Changed**
- Facility and barrier queries use the study-area bounding box, clipped locally, to avoid Overpass
  HTTP 413. The facility query adds a few tags, so it is a new facility snapshot. The networks are
  the same cached responses as in Milestone 01.
- Barangay indicator columns renamed from `<mode>_<category>_*` to `<mode>_<group>_*`. The
  percentage denominators are now the connected population.
- The QA report and map carry a "how to read" note. The map shows sub-type and tier.

**Removed**
- Travel-time indicators for evacuation, transport, government, ATMs and other health (descriptive
  only).
- The vacuous QA checks.

**Files:** `config/settings.yaml`, `config/experiments/*`, `src/abot/{config,osm,accessibility,population,report,compare,cli}.py`,
`tests/test_m02.py`, `README.md`, `docs/{METHODOLOGY,DATA_DICTIONARY,DATA_SOURCES,MILESTONE_02_RESULTS}.md`,
this file. Milestone 01 outputs are archived in `data/archive/m01_3edc0dd/`.

**Effect on results:** see [docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md) section 4.
- Walk to hospital: 27.3 min mean, 24.9% within 15 min (Milestone 01 "health": 12.7 min, 70.1%).
- Drive times are higher (pharmacy 3.20 → 4.19 min), split about equally between routed car access
  and the speed cap.
- E7: the buffer does not materially change city-wide results or rankings; border barangays are
  affected.

**Paper notes:**
- The sub-type split and the measured water crossings in Milestone 01 are a methodological point
  worth reporting.
- E7 supports the choice of buffer.
- Registry reconciliation (25 NHFR codes and 85 DepEd School IDs already in OSM `ref`) is the next
  validation step.

### 2026-10-31 — Milestone 02: focused validity assessment (no pipeline change)

**Why:** before more development, check six threats to validity raised by the analytical audit
(WorldPop product, straight connectors across water, boundary discrepancy, 100 m cells in small
barangays, free-flow driving, proximity vs service level vs capacity).

**Added**
- `docs/MILESTONE_02_VALIDITY_ASSESSMENT.md`: evidence, quantified impact, data needs, recommended
  treatment and remaining uncertainty for each issue, plus proposals P1–P7 awaiting approval.

**Files:** `docs/MILESTONE_02_VALIDITY_ASSESSMENT.md` (new). `Documentation.md` updated:
- §2 boundary note
- §3 WorldPop provenance, plus a POPCEN 2024 row
- §6 population interpretation
- §8 limitations 2, 4, 6 and 7, plus new item 10
- §11 paper notes

No code, configuration or project data changed. Diagnostics ran outside the repository against the
archived M01 outputs.

**Effect on results:** none (nothing implemented). Key measured findings:
- WorldPop R2025A is an alpha release. Its Philippine input is the PSA 2020 census at barangay
  level (admin 4; 42,058 units nested to 38,911), aligned to UN WPP 2024 at 1 January. The
  city-level +2.33% vs the census is therefore true by construction. WP2024 vs PSA POPCEN 2024 city
  total: +2.29%; city growth 2020→2024 is +3.48% (WorldPop) vs +3.52% (PSA).
- M01 straight connectors crossing water: walk 4,695 people (0.95%), drive 7,800 (1.58%). The
  count varies about threefold (4,695–14,464) with the origin-radius and tolerance settings. In
  the M02 working tree, 4,538 people are not connected; Calahunan has about 30% of its residents
  not connected.
- Boundary: COD-AB v03 is a land polygon (only 0.045 km² seaward of the OSM coastline). It
  differs from the OSM admin boundary on land by about 2.6 km², on the northern inland boundary.
  The 78.34 km² figure has no reproducible geometry behind it.
- 27 barangays have ≤ 5 cells. Their population totals change by 15–26% between centre and
  fractional allocation; their travel times change by a median of 0.2 min.
- Drive "≤ 10 min to hospital" falls from 81.7% to 31.4% if network legs take twice as long.

- Addendum: PSA 2024 POPCEN barangay counts (180 rows, sum 473,728, CC BY 4.0) were read from
  the PSA PSGC page in the user's browser. PSA barangay growth 2020→2024 ranges from −42.6% to
  +65.7% (34 barangays declined). WorldPop's ranges from +2.7% to +5.0%, and the two have a rank
  correlation of 0.05. Not yet used by the pipeline; the extracted table is kept outside the
  repository.

**Paper notes:** cite the WorldPop DOI 10.5258/SOTON/WP00839 and the alpha status. Do not present
the WorldPop-vs-census agreement as independent validation. The POPCEN 2024 comparison shows that
post-2020 WorldPop years do not capture differences in barangay change.

### 2026-10-31 — Milestone 02: analytical audit (no code change)

- Added `docs/MILESTONE_02_ANALYTICAL_AUDIT.md`: audit of the Milestone 01 method, with confirmed
  and potential issues, a data completeness assessment, recommended indicators, a sensitivity plan
  and a roadmap.
- Read-only diagnostics; no code, configuration or data changed.

### 2026-10-31 — Documentation file created

- Added `Documentation.md` (this file) as the project's research log and paper source.
- Documents Milestone 01 in full: data, methods, parameters, QA results, headline results and
  limitations.
- From now on, every change to the project is logged in this section.
- No change to code or results.

### 2026-10-31 — Milestone 01: data foundation and accessibility indicators (commit `3edc0dd`)

Initial implementation of the whole pipeline.

**Added**
- uv project on Python 3.13 with a pinned geospatial stack (`pyproject.toml`, `uv.lock`,
  `.python-version`). Ruff and pytest configuration.
- `config/settings.yaml`: study area, CRS, sources, OSM buffer, facility tag mapping, category
  priority, speeds and thresholds.
- `abot fetch`: COD-AB boundaries and PSA 2020 census found through the HDX API, WorldPop R2025A
  2026/2020 rasters, and a provenance manifest (URL, date, size, SHA-256).
- `abot build`:
  - `boundaries`: 180 barangays extracted with an attribute filter and validated.
  - `population`: WorldPop cells, centre-rule assignment, census cross-check through the PSGC
    code conversion.
  - `osm`: walk/drive networks with a 1 km buffer and largest-component filtering, 9 facility
    categories with priority matching and polygon/point de-duplication.
  - `accessibility`: KD-tree snapping, multi-source reversed-graph Dijkstra, population-weighted
    barangay indicators.
- `abot report`: Markdown QA report and an interactive folium map.
- 13 offline unit tests.
- `README.md` with quick start, method summary, limitations and licences.
- `.gitignore` excludes `data/`, caches and the virtual environment.

**Results:** see Sections 6 and 7. All QA threshold checks passed.

<!--
Template for future entries (copy above the latest entry):

### YYYY-MM-DD — <Milestone NN / short title> (commit `xxxxxxx`)

**Why:** <research motivation or problem being fixed>

**Added / Changed / Removed / Fixed**
- ...

**Files:** ...

**Effect on results:** <which numbers changed, before -> after; or "none">

**Paper notes:** <anything worth citing or discussing>
-->

---

## 11. Notes for the paper

A suggested structure, mapped to the sections of this document:

| Paper section | Source in this document |
|---|---|
| Introduction / problem | 1 |
| Study area | 2 |
| Data | 3 (cite each provider and licence) |
| Methods | 5 (boundaries → population → network → facilities → accessibility → indicators) |
| Validation | 6 (WorldPop vs census is not independent; independent check vs POPCEN 2024), routing verification ([docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md) section 3), E7 |
| Results | 7 (tables and the map `abot_map.html` for figures) |
| Discussion / limitations | 7 (observations) and 8 |
| Reproducibility / data availability | 3, 9 |

Possible figures: a choropleth of mean walking time to health per barangay; a facility map by
category; a scatter plot of WorldPop 2020 vs census 2020 per barangay; a cumulative curve of the
share of population vs walking time per category.

Candidate methodological contributions to highlight:
- Using a single reversed-graph multi-source Dijkstra per category, which follows one-way streets
  correctly and replaces one search per facility.
- Including the off-network walk at both ends of every trip.
- Measuring accessibility at the 100 m cell level with population weighting, not from barangay
  centroids.
- Comparing the population grid with the census. Present this carefully: the 2020 comparison is
  not independent, because WorldPop used the 2020 barangay census as input. The independent test
  is against PSA POPCEN 2024, which shows that post-2020 WorldPop years do not capture differences
  in barangay change. This is a useful finding in its own right.
- Water-aware, edge-based origin connection, which measurably removes straight-line access across
  rivers and fishponds (Milestone 02).
- Separating destination sub-types: "access to health" changes by more than 2× depending on
  whether dental, lab and therapy services count.
- Full provenance (checksummed inputs) and reproducibility from a single command.
- Census-anchored, fractionally allocated population weights, with the original WorldPop estimates
  kept for comparison (Milestone 02B).
- Multi-dimensional barangay reliability flags instead of a single confidence score, and a
  read-only audit that regenerates the validity diagnostics (Milestone 02B).
