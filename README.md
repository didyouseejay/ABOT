# ABOT

**ABOT** is a geospatial accessibility and public-infrastructure intelligence system for
**Iloilo City, Philippines**. It estimates how long residents take to reach essential public
facilities on foot and by car, and summarises the results for each of the city's 180 barangays.

> Status: **Milestone 01** — data foundation and a first set of accessibility indicators.
> This is a research prototype. Read [Limitations](#limitations) before using any result.

## What Milestone 01 produces

| Output (in `data/processed/`) | Contents |
|---|---|
| `abot_iloilo.gpkg` | GeoPackage with layers `city`, `barangays`, `pop_cells_2026`, `pop_cells_2020`, `network_walk`, `network_drive`, `facilities`, `access_cells_2026`, `barangay_access` |
| `barangay_access.csv` | One row per barangay: population, facility counts, and population-weighted travel-time indicators |
| `barangay_population.csv` | WorldPop 2026/2020 totals per barangay alongside the PSA 2020 census |
| `qa_report.md` | Every validation check with PASS / WARN / info, plus data provenance (URLs, dates, SHA-256) |
| `abot_map.html` | Interactive map: choropleths of travel times and population, facility markers by category |

Indicators are computed per mode (`walk`, `drive`) and per facility category (`health`, `pharmacy`,
`education`, `safety`, `government`, `market`, `finance`, `transport`, `evacuation`):

- `<mode>_<category>_mean_min`: population-weighted mean travel time to the nearest facility
- `<mode>_<category>_max_min`: worst populated 100 m cell in the barangay
- `<mode>_<category>_pct_le<N>`: share of residents within N minutes (walk 10/15/30, drive 5/10/15)
- `n_<category>`: facilities located inside the barangay

## Quick start

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.13 automatically.

```bash
uv sync                 # create .venv with pinned dependencies
uv run abot fetch       # download ~550 MB of source data into data/raw (once)
uv run abot build       # boundaries -> population -> osm -> accessibility (~1–3 min)
uv run abot report      # data/processed/qa_report.md and abot_map.html
uv run pytest           # offline unit tests
```

You can run single stages with `uv run abot build --only population osm`. Settings such as the
facility tag mapping, speeds, thresholds and WorldPop years are in [`config/settings.yaml`](config/settings.yaml).

The pipeline runs comfortably on a CPU-only laptop with 8 GB of RAM. The national boundary file
and WorldPop rasters are read through spatial filters, so they are never loaded whole into memory.

## Method

1. **Boundaries**: city and barangay polygons come from the OCHA COD-AB GeoDatabase, filtered to
   p-code `PH0603022` and projected to UTM 51N (EPSG:32651).
2. **Population**: WorldPop R2025A constrained 100 m counts are read for the city window. Each
   cell is assigned to the barangay containing its centre. The 2020 raster is checked against the
   PSA 2020 census, joined by converting old 9-digit PSGC codes to COD-AB p-codes.
3. **OpenStreetMap**: walk and drive networks and facilities are fetched via Overpass (osmnx) for
   the city plus a 1 km buffer, so facilities just across the city limit still count. When a
   facility is mapped as both a point and a polygon, the duplicate point is removed.
4. **Accessibility**: each category gets one Dijkstra run from a virtual source connected to all
   facilities, on the reversed graph so that one-way streets are respected. The off-network walk at
   both ends (cell centre to network, network to facility) is included.

## Limitations

- **OSM completeness varies by category.** Evacuation centres (5 mapped) and transport terminals
  are severely under-mapped, so their travel times reflect missing data more than real
  accessibility. Health and education coverage has not yet been checked against official
  registries (DOH NHFR, DepEd).
- **Drive times are free-flow.** Speeds are assumed per road class (see config). There is no
  congestion, parking, or jeepney/public transport model yet.
- **WorldPop R2025A is an alpha release**, and 2026 values are projections. In 2020 it matches the
  census within about 2% city-wide (r ≈ 0.92 across barangays), but individual barangays can be off
  by 30% or more, especially very small ones.
- **COD-AB's coastline** gives a city area of 72.6 km², a few km² less than commonly cited
  figures.

## Data sources and licences

Downloaded data is **not** stored in this repository. Running `abot fetch` re-creates it, and
`data/raw/manifest.json` records exact URLs, dates and checksums.

| Data | Source | Licence |
|---|---|---|
| Administrative boundaries (COD-AB v03) | [OCHA / HDX](https://data.humdata.org/dataset/cod-ab-phl), from NAMRIA & PSA | CC BY-IGO |
| 2020 Census population by barangay | [PSA via HDX](https://data.humdata.org/dataset/popn-single-year-age-sex-and-barangay-census-2020) | CC BY |
| Population counts R2025A, 100 m | [WorldPop](https://hub.worldpop.org/) | CC BY 4.0 |
| Roads and facilities | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors | ODbL 1.0 |

Any database you derive from OpenStreetMap data and share publicly must also be released under
the ODbL.
