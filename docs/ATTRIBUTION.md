# Data and third-party attribution

ABOT is an independent personal portfolio project by Carl John L. Coopera. It is not affiliated with
or endorsed by any university, agency or data provider.

ABOT's original source code is released under the [MIT License](../LICENSE). That licence does
**not** extend to the data the pipeline downloads or derives, nor to third-party software, fonts or
map tiles. Each keeps its own terms, summarised below. Library licences were read from the installed
package metadata (Python `importlib.metadata`, `dashboard/node_modules/*/package.json`) on
2026-11-02.

## 1. Data sources

No source data is stored in this repository (`data/` is git-ignored). `abot fetch` downloads the
data again, and `data/raw/manifest.json` records each file's URL, licence and SHA-256. Details are in
[DATA_SOURCES.md](DATA_SOURCES.md).

| Data | Provider | Licence | Required credit |
|---|---|---|---|
| Roads, paths, barriers and facilities | © OpenStreetMap contributors, via the Overpass API (osmnx) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) | "© OpenStreetMap contributors", linked to <https://www.openstreetmap.org/copyright> |
| Administrative boundaries (COD-AB v03) | OCHA / HDX, from NAMRIA and PSA | CC BY-IGO | OCHA / NAMRIA / PSA, COD-AB |
| 2020 Census of Population by barangay | Philippine Statistics Authority (PSA), via HDX | CC BY | PSA, 2020 Census of Population and Housing |
| Population counts, constrained 100 m (R2025A, 2020 and 2026) | WorldPop, University of Southampton (DOI 10.5258/SOTON/WP00839) | CC BY 4.0 | WorldPop (www.worldpop.org) |

### OpenStreetMap and the ODbL

- Every ABOT output that contains OpenStreetMap data is a **Derivative Database** under the ODbL:
  the GeoPackage, the CSVs and the dashboard bundle (`facilities.geojson`, `network.json`, and the
  travel times computed on the OSM network).
- **If you publish such a database** (for example, by deploying the dashboard with its bundle, or
  attaching the bundle to a release), it must be offered under the ODbL. It must also keep the
  attribution and state that it contains OpenStreetMap data. ABOT's own notice for its published
  dataset is [LICENSE-DATA.md](../LICENSE-DATA.md). The dashboard shows it in the footer and on the
  About page, with a link to the release downloads.
- Maps, figures and screenshots made from it are **Produced Works**. They need the credit
  "© OpenStreetMap contributors", but not the ODbL itself. The screenshots in
  [assets/screenshots/](assets/screenshots/) show this credit in the map attribution.
- The MIT licence of the code does not change any of this.

### Registries researched but not used

The DOH National Health Facility Registry, the DepEd school masterlist and the Iloilo City CDRRMO
evacuation-centre list were researched but are **not** integrated. No redistribution licence was
found for any of them ([DATA_SOURCES.md](DATA_SOURCES.md) §4).

## 2. Map backgrounds in the dashboard

The dashboard loads background tiles directly from a third-party server at view time. No tiles are
stored in the repository or the bundle.

| Background | Server | Credit shown in the map | Terms |
|---|---|---|---|
| Street map | `tile.openstreetmap.org` | "Street map © OpenStreetMap contributors" | [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/): suitable for light use such as a portfolio demo; heavy traffic needs another tile provider |

The Esri World Imagery "Satellite" background (and its Esri place-name overlay), offered since
M05.3, was **removed in M06.3**. Its terms for a public deployment were not cleared. No other imagery
provider replaces it. A browser that had "Satellite" saved falls back to the street map.

The map also always shows the data credit "Data © OpenStreetMap contributors (ODbL 1.0) ·
boundaries OCHA COD-AB · population PSA, WorldPop" (`dashboard/src/map/leaflet.ts`). With "No
background" selected, no tile server is contacted.

The Python pipeline's local review and validation maps (`src/abot/review.py`, `validation.py`) still
offer an Esri imagery layer. They are generated for local inspection only and are not part of the
public dashboard.

## 3. Python libraries (runtime)

Pinned in [`uv.lock`](../uv.lock).

| Package | Version | Licence |
|---|---|---|
| geopandas | 1.2.0 | BSD-3-Clause |
| osmnx | 2.1.1 | MIT |
| networkx | 3.7 | BSD-3-Clause |
| shapely | 2.2.0 | BSD-3-Clause |
| rasterio | 1.5.2 | BSD-3-Clause |
| pyproj | 3.8.0 | MIT |
| pyogrio | 0.13.0 | MIT |
| pandas | 3.1.0 | BSD-3-Clause |
| numpy | 2.5.4 | BSD-3-Clause (with bundled 0BSD, MIT, Zlib, CC0-1.0 parts) |
| scipy | 1.18.1 | BSD-3-Clause |
| folium | 0.20.0 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| PyYAML | 6.0.3 | MIT |
| openpyxl | 3.1.5 | MIT |

Development tools: pytest (MIT) and ruff (MIT).

## 4. Dashboard libraries and assets

Pinned in [`dashboard/package-lock.json`](../dashboard/package-lock.json).

| Package | Version | Licence | Shipped to the browser? |
|---|---|---|---|
| react, react-dom | 19.3.1 | MIT | Yes |
| leaflet | 1.9.4 | BSD-2-Clause | Yes (loaded on first map view) |
| @fontsource/atkinson-hyperlegible | 5.3.0 | SIL Open Font License 1.1 | Yes (self-hosted font files) |
| vite | 8.3.5 | MIT | No (build tool) |
| @vitejs/plugin-react | 6.1.2 | MIT | No |
| typescript | 7.0.2 | Apache-2.0 | No |
| vitest | 5.0.5 | MIT | No |
| @types/* | — | MIT | No (type declarations) |

Milestone 06.1 removed `chart.js` (MIT) and `react-leaflet` (Hippocratic License 2.1, which is not
an OSI-approved open-source licence) because neither was used. The charts are hand-built SVG, and
Leaflet is used directly.
