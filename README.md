# ABOT

**ABOT** is a geospatial accessibility and public-infrastructure intelligence system for
**Iloilo City, Philippines**. It estimates how long residents take to reach essential public
facilities on foot and by car, and summarises the results for each of the city's 180 barangays.

> Status: **Milestone 02B**: 3 km baseline buffer, census-anchored population weights, barangay
> reliability flags, read-only `abot audit`, manual-review files (see
> [docs/MILESTONE_02B_RESULTS.md](docs/MILESTONE_02B_RESULTS.md)).
> This is a research prototype. Read [How to read the results](#how-to-read-the-results) before
> using any number.

## How to read the results

- Travel times are **modelled** on the mapped OpenStreetMap network to the nearest **mapped**
  facility: **geographic proximity**. They do not measure service level (facility level is not
  verified) or capacity, and they are not real travel times.
- Car times are **modelled uncongested (free-flow) car travel time**, including the walk to and
  from the road. They exclude congestion, signals, parking and car availability; their threshold
  shares are lower bounds (see `drive_speed_sensitivity.csv`).
- Population weights are **census-adjusted**: PSA 2020 barangay totals spread by the WorldPop 2020
  pattern. The original WorldPop estimates (`pop_wp2020`, `pop_wp2026`) are kept beside them.
  WorldPop was built from this census, so their agreement is **not** validation.
- Shares within N minutes are of **all** residents. Residents with no valid network connection
  (0.87%) are reported separately (`pct_not_connected`).
- Each barangay has separate **reliability** flags (`rel_population`, `rel_network`,
  `rel_facility_inventory`, `rel_overall`, each with reasons). Do not rank population-based
  quantities for barangays where `pop_ranking_eligible` is False.
- **No facility category has been verified** against an official registry. Only coherent sub-types
  (hospitals, primary care, pharmacies, schools, police, fire stations, public markets,
  supermarkets, banks) get travel-time indicators. **Evacuation, transport, government, ATMs and
  "other health" are descriptive only**: they are mapped and counted, with no travel-time
  statistics.
- A missing facility in OSM is a **data gap**, not proof that the service is absent.

## Documentation

| Document | Contents |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | How every number is produced, and what it does and does not mean |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Every output file, layer and column |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Sources, licences, OSM snapshot provenance, external registry research |
| [docs/MILESTONE_02_ANALYTICAL_AUDIT.md](docs/MILESTONE_02_ANALYTICAL_AUDIT.md) | Audit of the Milestone 01 method |
| [docs/MILESTONE_02_VALIDITY_ASSESSMENT.md](docs/MILESTONE_02_VALIDITY_ASSESSMENT.md) | Focused assessment of six threats to validity, with proposals P1–P7 |
| [docs/MILESTONE_02_RESULTS.md](docs/MILESTONE_02_RESULTS.md) | What changed in Milestone 02, by how much, and Experiment E7 |
| [docs/MILESTONE_02B_RESULTS.md](docs/MILESTONE_02B_RESULTS.md) | Milestone 02B: 3 km baseline, weights, reliability flags, audit, review files |
| [Documentation.md](Documentation.md) | Running research log and change log |

## Outputs (`data/processed/`)

| Output | Contents |
|---|---|
| `abot_iloilo.gpkg` | Layers `city`, `barangays`, `pop_cells`, `pop_pieces`, `network_walk/drive`, `barriers`, `facilities`, `facility_roles`, `access_cells`, `barangay_access` |
| `barangay_access.csv` | One row per barangay: population (adjusted and original), connected and unconnected residents, travel-time indicators per indicator group, facility counts, reliability flags |
| `barangay_population.csv` | PSA 2020 census, census-adjusted totals and factor, original WorldPop 2020/2026, cell counts |
| `facility_inventory.csv` | Measurable inventory-completeness signals per indicator group (status: unverified) |
| `drive_speed_sensitivity.csv` | Car-time shares with the network leg × 1, 1.5, 2 |
| `review/` | Manual-review files and maps (possible duplicates, unconnected cells), all `pending` |
| `facilities.csv` | Every mapped facility: OSM id and tags, category, sub-type, tier, classification status and reason, network connection |
| `facility_exclusions.csv` | Merged points, flagged possible duplicates, unmatched features (never silently dropped) |
| `qa_report.md` | QA checks (PASS/WARN = tested condition; info = reported) and full provenance |
| `abot_map.html` | Interactive map with choropleths and facility markers by category, sub-type and tier |

Indicators per mode (`walk`, `drive`) and indicator group (`health_hospital`,
`health_primary_care`, `pharmacy`, `education_basic`, `education_higher`, `safety_police`,
`safety_fire`, `market_public`, `market_supermarket`, `finance_bank`):

- `<mode>_<group>_mean_min`: population-weighted mean travel time to the nearest mapped destination
- `<mode>_<group>_p90_min`: population-weighted 90th percentile (connected residents)
- `<mode>_<group>_pct_le<N>`: share of **all** residents within N minutes (walk 10/15/30, drive
  5/10/15). These are analytical thresholds, not official standards.
- `pop_not_connected`, `pct_not_connected`: residents with no valid network connection. They are in
  every denominator but have no time; `rel_network` is low above 5%.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.13 automatically.

```bash
uv sync                 # create .venv with pinned dependencies
uv run abot fetch       # download ~550 MB of source data into data/raw (once)
uv run abot build       # boundaries -> population -> osm -> accessibility
uv run abot report      # data/processed/qa_report.md and abot_map.html
uv run abot review      # data/processed/review/: manual-review files and maps (changes no data)
uv run abot audit       # read-only PASS / WARN / FAIL check; exit 1 on FAIL
uv run pytest           # offline unit and regression tests
```

`abot audit` never downloads and never writes under `data/`. Use `--output audit.md` (outside
`data/`) to save the findings, or `--skip-hashes` for a faster run.

You can run single stages with `uv run abot build --only population osm`. All parameters are in
[`config/settings.yaml`](config/settings.yaml): facility categories, sub-types and tiers, indicator
groups, speeds and the `maxspeed` policy, connection tolerances, barriers and thresholds.

OSM responses are cached in `data/raw/osm_cache/`, so rebuilds reuse the same snapshot. Each
response's Overpass timestamp and SHA-256 is recorded in `data/raw/manifest.json`.

### Experiments and comparisons

Experiment configs extend the baseline and write to their own folders. They never overwrite the
baseline.

```bash
uv run abot --config config/experiments/hist_buffer_1km.yaml build   # -> data/processed/hist_buffer_1km/
uv run abot --config config/experiments/hist_buffer_1km.yaml report
uv run abot compare data/processed/hist_buffer_1km data/processed --name e7_buffer_1km_vs_3km_m02b
```

The extraction buffer is `osm.boundary_buffer_m` (default 3,000 m since Milestone 02B). The 1 km
buffer of Milestones 01–02 is preserved in `config/experiments/hist_buffer_1km.yaml`. The
Milestone 01 outputs are archived in `data/archive/m01_3edc0dd/`, and their SHA-256 values are
checked by `abot audit`.

The pipeline runs on a CPU-only laptop with 8 GB of RAM. The national boundary file and WorldPop
rasters are read through spatial filters, so they are never loaded whole into memory.

## Method in brief

Full detail is in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

1. **Boundaries:** OCHA COD-AB city and barangay polygons, in UTM 51N (EPSG:32651).
2. **Population:** WorldPop R2025A 100 m cells, split between barangays by area. Weights are PSA
   2020 barangay totals spread by the WorldPop 2020 pattern; the original WorldPop values are kept.
3. **OpenStreetMap:** walk and drive networks, barrier features (water, waterways, coastline,
   walls) and facilities, for the city plus a 3 km buffer. Drive speeds are assumed by road class;
   a tagged `maxspeed` can only lower them.
4. **Facilities:** nine categories with sub-types and reporting tiers. A feature can belong to
   several categories. Veterinary facilities are excluded from human health.
5. **Connection:** each cell and facility is joined to the nearest walkable **edge** whose straight
   connector does not cross water, within 250 m (500 m for facilities). Cells that cannot be
   connected get no travel time, stay in the denominators, are reported separately and are listed
   for manual review. Facilities outside the city are used only if connected.
6. **Accessibility:** one multi-source Dijkstra search per indicator group on the reversed graph,
   so one-way streets are respected. In drive mode, the walk to and from the car is routed on the
   walk network.

## Data sources and licences

Downloaded data is **not** stored in this repository. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

| Data | Source | Licence |
|---|---|---|
| Administrative boundaries (COD-AB v03) | [OCHA / HDX](https://data.humdata.org/dataset/cod-ab-phl), from NAMRIA & PSA | CC BY-IGO |
| 2020 Census population by barangay | [PSA via HDX](https://data.humdata.org/dataset/popn-single-year-age-sex-and-barangay-census-2020) | CC BY |
| Population counts R2025A, 100 m | [WorldPop](https://hub.worldpop.org/) | CC BY 4.0 |
| Roads, barriers and facilities | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors | ODbL 1.0 |

Any database you derive from OpenStreetMap data and share publicly must also be released under
the ODbL.
