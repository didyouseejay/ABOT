# ABOT — Milestone 02: Analytical Audit of the Milestone 01 Methodology

| | |
|---|---|
| **Audited commit** | `3edc0dd` (Milestone 01), branch `main` |
| **Audit date** | 2026-10-31 |
| **Scope** | Accessibility method, population data and aggregation, OSM facility data, indicators, robustness, documentation |
| **Status** | Audit and improvement plan. Written before any change; no source code, configuration or dataset was modified for it. **Update:** the approved Priority 0 items (R-01 excepted), R-10/R-11/R-12/R-13 and E7 have since been implemented. See [MILESTONE_02_RESULTS.md](MILESTONE_02_RESULTS.md). P-01 is now confirmed and P-04 resolved (see [MILESTONE_02_VALIDITY_ASSESSMENT.md](MILESTONE_02_VALIDITY_ASSESSMENT.md)). |

---

## How to read this report

- **Confirmed** means the problem is shown by the code itself or by numbers measured from the Milestone 01 outputs.
- **Potential** means there is evidence or a plausible mechanism, but checking it needs more work or outside data.
- **Data limitation** means the cause is missing or unavailable data, not a defect in ABOT's code.
- Each issue has an ID (for example **C-03** for confirmed or **P-02** for potential), a severity, and a note on whether it can be fixed with data ABOT already has.

### Where the audit numbers come from

All figures in this report fall into two groups:

1. Figures copied from the Milestone 01 outputs (`data/processed/qa_report.md`, `barangay_access.csv`, `barangay_population.csv`, `abot_iloilo.gpkg`).
2. Figures from **read-only diagnostic scripts** run against those outputs and the saved graphs (`data/interim/graph_*.graphml`). These scripts reuse ABOT's own `time_to_nearest` routine and the same KD-tree snapping method. They are **not part of the pipeline** and wrote nothing into the repository. Section 9 (item R-01) recommends rebuilding them as a reproducible `abot audit` command so that every number here can be regenerated.

No external dataset was downloaded for this audit. One web search was used to check the WorldPop R2025A method (see Section 10).

---

## 1. Executive summary

ABOT's Milestone 01 pipeline is **well engineered**. It records provenance, is memory-aware, uses a projected CRS, routes correctly on directed graphs, and its shortest-path core is sound and tested. The main risks are **not computational errors in the routing**. They are **interpretation risks**: what the indicators are labelled as, the facilities and population they rest on, and how far the off-network approximations reach.

**The five most important findings:**

1. **The "health" indicator does not measure access to healthcare in a decision-relevant sense (Critical, C-01).** Of the 99 "health" features, only 14 are human hospitals. The rest include dentists, laboratories, therapists, an optometrist, and one **veterinary** hospital ("Cornerstone Pet Hospital", tagged `amenity=hospital`). The population-weighted walking time to the nearest "health" facility is **12.7 min**, but to the nearest **hospital** it is **27.9 min**. The share of residents within 15 minutes' walk falls from **70.0%** to **23.7%**. The headline health map and statistic are dominated by the category definition.

2. **Evacuation accessibility cannot be reported quantitatively (Critical, C-02).** Only 5 features are classified as evacuation. Three are unnamed `emergency=assembly_point` features, which in OSM usually means a building's fire-drill gathering point, not a community evacuation centre. The QA report still marks this category **PASS**, because the check is `count ≥ 5`. A shortage of OSM tags is not evidence of a shortage of evacuation centres.

3. **"Drive" times are partly straight-line walking times (High, C-03).** Each populated cell is joined to the nearest drive-network *node* by a straight line walked at 4.5 km/h. For health, this off-network leg is **≈26% of the population-weighted drive time**. 12.3% of residents live more than 100 m (straight line) from their drive snap node. For cells more than 150 m away, the walking route to that node is more than 3 times the straight-line distance for 482 cells (7,289 people), which points to straight lines crossing rivers, fishponds, walls or unmapped areas (P-01).

4. **Barangay-level population is much less reliable than the summary statistics suggest (High, C-06).** City-level agreement (+2.3%) and Pearson r = 0.92 hide three things:
   - Small barangays are **systematically overestimated**: the median error in the smallest quarter is **+70%**.
   - The total absolute barangay error equals **26.9%** of the census population.
   - The correlation of population **density** is only **r = 0.51**.

   The city-level agreement is also **not independent validation**, because WorldPop's top-down method distributes official census-based administrative totals.

5. **Several categories mix services that are not substitutes (Medium to High, C-09).** For example:
   - "Government" puts barangay halls together with regional offices of national agencies.
   - "Finance" counts ATMs as banks.
   - "Market" mixes supermarkets with public markets.
   - "Transport" has no jeepney access and includes inter-island ferry terminals.

**What can be interpreted now, with caveats:** the network routing core, city-wide population totals (as modelled estimates), and *relative* walking access to the **mapped** facilities of the better-mapped categories, once those categories are redefined (see Section 6.4).

**What should not be interpreted yet:**
- Evacuation and transport accessibility.
- "Health" as healthcare access.
- Drive times as real travel times.
- Indicators for barangays with very few raster cells.
- 2026 values as observed or census-verified population.

**Recommended direction for the implementation phase:**
- **Fix meaning before adding features.** Split categories, add snap-distance validation and flags, report distribution-based indicators, and calibrate or flag population.
- **Run seven small sensitivity experiments** that fit comfortably on an 8 GB CPU-only laptop (Section 8).
- **Use existing data for almost all of this.** Only facility completeness validation and 2SFCA need outside data.

---

## 2. Existing methodology overview

| Stage | Module | What it does |
|---|---|---|
| Boundaries | [boundaries.py](../src/abot/boundaries.py) | Reads OCHA COD-AB v03 for p-code `PH0603022`, reprojects to EPSG:32651 (UTM 51N), repairs geometries, checks 180 barangays, tiling and overlap. |
| Population | [population.py](../src/abot/population.py) | Masks the WorldPop R2025A constrained ~100 m count rasters (2020, 2026) to the city. A cell is kept if its value is > 0 and its **centre** is inside the city, then assigned to the barangay containing its centre. Totals are compared with the PSA 2020 census, joined through old 9-digit PSGC codes converted to COD-AB p-codes. |
| OSM | [osm.py](../src/abot/osm.py) | Uses osmnx 2.1.1 to fetch `walk` and `drive` networks for the city plus a 1 km buffer. Keeps the largest component (strongly connected for drive). Drive speeds come from OSM `maxspeed` if tagged, otherwise from the config table. Walk speed is a constant 4.5 km/h. Facilities are fetched by tags, given **one** category by priority order, de-duplicated only where a node lies inside a same-category polygon, and reduced to a representative point. |
| Accessibility | [accessibility.py](../src/abot/accessibility.py) | For each mode and category, cells and facilities are snapped to the **nearest graph node** (KD-tree, straight-line distance). A virtual source is linked to all facility nodes (edge weight = the facility's off-network walking time). One Dijkstra run on the **reversed** graph gives node-to-nearest-facility time. Cell time = straight-line snap distance ÷ 4.5 km/h + network time. Barangay indicators: population-weighted mean, worst cell, % within thresholds. |
| Report | [report.py](../src/abot/report.py) | QA tables from each stage's JSON, provenance manifest, folium map. |

Milestone 01 headline values (QA report): 7,815 populated cells; 2026 population 492,459; median snap distance 47.3 m (walk) and 65.9 m (drive); unreachable population 0 for every category.

---

## 3. Confirmed methodological strengths

These are real strengths and should be kept unchanged.

| # | Strength | Evidence |
|---|---|---|
| S-01 | **Correct nearest-facility algorithm.** One multi-source Dijkstra per category on the reversed graph gives the time *from* each node *to* its nearest facility. This is efficient (O(E log V) per category instead of per origin) and handles one-way streets correctly. | `time_to_nearest` in [accessibility.py:40-52](../src/abot/accessibility.py#L40-L52); unit tests for one-way streets, offsets and cleanup in [tests/test_core.py](../tests/test_core.py). |
| S-02 | **Facility off-network leg is included** as a virtual-source edge weight, not ignored. | [accessibility.py:43-46](../src/abot/accessibility.py#L43-L46) |
| S-03 | **Mode-appropriate one-way handling.** The drive graph keeps `oneway`: 822 one-way directed edges. The walk graph is bidirectional (osmnx `bidirectional_network_types = ["walk"]`): all 33,902 walk edges have `oneway=False`, which is correct for pedestrians. | Graph diagnostics |
| S-04 | **Drive graph is reduced to the largest *strongly* connected component**, so every node can reach every other node in both directions. Without this, multi-source Dijkstra could leave cells permanently unreachable. | [osm.py:47](../src/abot/osm.py#L47) |
| S-05 | **All distances are in a metric projected CRS** (UTM 51N), suitable for a 72 km² city at 10.7° N. | `crs.projected` in config |
| S-06 | **No hidden straight-line-as-network shortcut.** The only straight-line distances in the travel-time calculation are the two explicit snap legs (cell → node and facility → node). All other distances are network shortest paths. | Code inspection of [accessibility.py](../src/abot/accessibility.py) |
| S-07 | **Counts are treated as counts.** WorldPop values are persons per cell and are summed, never treated as density. Nodata and zero cells are both excluded from origins, which is correct because they carry no weight. | [population.py:46](../src/abot/population.py#L46) |
| S-08 | **Boundary cells are handled without double counting** (centre rule), and the effect is measured with an `all_touched` upper bound: 0.86% of population is excluded. | QA: `wp2026_edge_excluded_pct = 0.86` |
| S-09 | **Census join is complete and tested** (180/180 through a documented and unit-tested old-PSGC → COD-AB conversion). | QA `census_matched_barangays = 180` |
| S-10 | **Population weights match the origins.** Barangay means use the same 2026 cells that were routed. | [accessibility.py:83-95](../src/abot/accessibility.py#L83-L95) |
| S-11 | **Provenance and reproducibility.** URLs, retrieval time and SHA-256 checksums are recorded for the downloaded files, raw Overpass responses are cached, and config drives all parameters. | `data/raw/manifest.json` |
| S-12 | **Resource-aware.** Windowed raster reads and attribute-filtered GDB reads keep memory low on 8 GB hardware. | [population.py:41-44](../src/abot/population.py#L41-L44), [boundaries.py:36](../src/abot/boundaries.py#L36) |
| S-13 | **Facilities in the 1 km buffer are routed to** (`inside_city` is used only for counts). For about 3% of residents, the nearest market, finance facility or pharmacy is in the buffer, so excluding them would have biased edge barangays. | Diagnostics, Section 4 (C-15) |
| S-14 | **Limitations already acknowledged in the README** (OSM completeness, free-flow drive, alpha WorldPop). This audit makes them sharper and puts numbers on them. | [README.md](../README.md) |

---

## 4. Confirmed methodological problems

### C-01 — The "health" category mixes non-substitutable services and contains a veterinary hospital
**Severity: Critical** · **Addressable with existing data: Yes**

**Evidence**
- `health` in [config/settings.yaml](../config/settings.yaml) matches `amenity ∈ {hospital, clinic, doctors, dentist}` **or `healthcare=*` (any value)**.
- Composition of the 99 health features:
  - 15 `amenity=hospital`, one of which is **"Cornerstone Pet Hospital"** (veterinary, mis-tagged in OSM)
  - 19 dentist-type features
  - 9 laboratories
  - 5 therapy features (physio, occupational, speech)
  - 1 optometrist and 1 dialysis unit
  - about 49 primary-care features (clinic, doctors, health post, birthing centre, midwife)
- Audit re-computation of walking access, using the pipeline's own routing routine:

| Health definition | n | Pop-weighted mean (min) | % pop ≤ 15 min | % pop ≤ 30 min |
|---|---|---|---|---|
| All "health" (current) | 99 | 12.67 | 70.0 | 93.2 |
| Primary care (clinic, doctors, health post, birthing, midwife) | 49 | 14.47 | 63.7 | 90.0 |
| Excluding dental, lab, therapy, optometry, dialysis | 65 | 13.87 | 65.5 | 90.7 |
| Hospitals (excluding veterinary) | 14 | **27.92** | **23.7** | 60.2 |

**Why it matters.** Nearest-facility accessibility assumes that any facility in the category can meet the need. A dental clinic cannot stand in for a hospital, and a veterinary hospital is not a human health service at all. The current map layer "Walk to health" and the citywide figure of 12.67 min would be read by a decision-maker as access to healthcare, and they overstate access to hospital care by more than 2×.

**Recommended correction**
- Split `health` into at least `hospital`, `primary_care` (clinic, doctors, health_post, birthing_centre, midwife) and `other_health` (dental, laboratory, therapy, optometry, dialysis). Report the first two; keep the third descriptive only.
- Replace `healthcare: true` with explicit value lists.
- Add an exclusion rule for veterinary features: `amenity=veterinary`, and names matching "pet" or "veterinar" as a QA flag, not a silent drop.
- Treat this as a refinement inside the existing category, not a new facility category.

---

### C-02 — Evacuation category is too incomplete and too poorly defined for quantitative reporting, yet passes QA
**Severity: Critical** · **Addressable with existing data: Partly** (labelling and QA yes; real coverage needs official data)

**Evidence**
- The 5 features are:
  - "WVSU/Evacuation Center" (`emergency=assembly_point`)
  - "Iloilo City Evacuation Center" (`social_facility=shelter`)
  - **three unnamed `emergency=assembly_point`** features
- On the OSM wiki, `emergency=assembly_point` is mainly a designated gathering point for evacuating a building or site. `social_facility=shelter` is mainly for shelters for homeless or vulnerable people. Neither tag reliably means a designated LGU evacuation centre.
- `evacuation` is **last** in `category_priority`. A school, covered court or barangay hall that is also tagged as an evacuation site is therefore always assigned to its other category and never counted as evacuation ([osm.py:88-94](../src/abot/osm.py#L88-L94)).
- The QA check is `n_in >= 5` ([osm.py:154-158](../src/abot/osm.py#L154-L158)). With exactly 5, the report shows **`facilities_evacuation | PASS`**.
- Current indicator: 37.2 min mean walk and 11.9% of the population within 15 min. Using only the 2 named features: 47.0 min and 5.2%. The result depends entirely on which of five uncertain points are included.

**Why it matters.** Evacuation access is high-stakes. A figure like "88% of residents are more than 15 minutes from an evacuation centre" would be a statement about **OSM tagging**, not about Iloilo City's disaster preparedness. The PASS label makes this worse by giving the category a false quality signal.

**Recommended correction**
- **Suppress quantitative evacuation indicators** in the CSV and map, or move them to a clearly labelled "data-completeness diagnostic" layer.
- Change the QA check to report evacuation as `WARN — not suitable for accessibility reporting` regardless of count.
- Allow **multi-category membership** (see C-10) so that a feature can be both education and evacuation.
- Obtain an authoritative evacuation-centre list (Iloilo City CDRRMO; DSWD DROMIC) before any quantitative use. Do not infer that evacuation centres are absent.

---

### C-03 — Drive-mode travel times contain a large, unbounded straight-line walking component
**Severity: High** · **Addressable with existing data: Yes**

**Evidence**
- Every cell is joined to the **nearest drive-graph node** by a straight line, walked at `snap_speed_kmh = 4.5` ([accessibility.py:63-75](../src/abot/accessibility.py#L63-L75)).
- The osmnx `drive` filter **excludes `highway=service`, alleys and driveways**, which is where much of the dense residential fabric is. As a result, drive snap distances are large:

| Drive snap distance | Value |
|---|---|
| Median / 90th / 99th percentile / max | 65.9 / 218.2 / 459.6 / **867.4 m** |
| Population > 100 m from snap node | 60,623 (12.3%) |
| Population > 300 m | 5,324 (1.1%) |

- The snap leg is about **26% of the population-weighted drive time to health** (walk mode: about 7%).

**Why it matters.** "Drive" is really walk-then-drive, with an unrealistic walk leg (straight line, nearest *node* only). The citywide drive means of about 3 min are short enough that the access leg strongly affects them. This is defensible as a documented "door-to-door" assumption, but at present it is neither labelled nor bounded.

**Recommended correction**
- Snap to the nearest **edge** (projected point on the line), not the nearest node. Interpolate along the edge, or as a cheaper approximation keep node snapping with `simplify=False` near origins.
- Route the access leg on the **walk network** to the nearest drive node instead of using a straight line.
- Report `access_leg_min` and `network_leg_min` as separate columns.
- Rename the mode in outputs to "car, door-to-door (free-flow)".

---

### C-04 — Snap distances are not validated; the "unreachable population" check cannot fail
**Severity: High** · **Addressable with existing data: Yes**

**Evidence**
- Cell snap distances are stored (`snap_m_walk`, `snap_m_drive`), but QA reports only the **median** ([accessibility.py:128-130](../src/abot/accessibility.py#L128-L130)). There is no maximum, no threshold, and no flag.
- Walk snap distances: 95th percentile 206 m, 99th percentile 324 m, max 600 m. 6,151 people (1.25%) are more than 200 m from the walk network.
- **Facility snap distances are not recorded at all.** The audit measured walk: median 25 m, max 376 m; drive: median 48 m, max 376 m, with 14 facilities more than 200 m from the drive network.
- Every cell snaps to *some* node of the largest component, so `t_*` is never NaN. `*_unreachable_pop = 0 | PASS` is therefore true by construction and does not show that origins are genuinely connected.

**Why it matters.** The question "is every populated cell genuinely connected to a valid road location?" is currently unanswered. The QA report suggests it has been answered.

**Recommended correction**
- Store facility snap distances.
- Report snap-distance quantiles and the maximum.
- Set an analytical **snap tolerance**, for example 200 m for walk and 300 m for drive (to be tested in E2, Section 8).
- Flag cells above it (`snap_flag`), report the population affected by barangay, and exclude flagged cells from "within X minutes" claims or show them as "poorly connected".
- Replace the vacuous unreachable check with `pop_beyond_snap_tolerance`.

---

### C-05 — Drive speed assumptions are internally inconsistent
**Severity: High** · **Addressable with existing data: Yes**

**Evidence**
- The config describes its speeds as "assumed free-flow urban speeds … treat drive times as optimistic". However, osmnx `add_edge_speeds` gives **tagged `maxspeed` priority**. 2,955 of 16,930 drive edges (17%) carry `maxspeed` (40 km/h: 1,222; 30: 854; 50: 261; 60: 259; 80: 61).
- As a result, the mean assigned speed is 45.9 km/h for `primary` (config value 30) and 60.7 km/h for `trunk` (config 40), up to 80 km/h on some urban edges. These are **legal limits**, not typical speeds, and are mixed with assumed speeds on untagged roads.
- Highway types missing from the config are imputed by osmnx:
  - `primary_link` → 60 km/h (mean of tagged)
  - `secondary_link`, `tertiary_link`, `road` → 31.4 km/h (global mean fallback)
- The `service: 15` config entry is never used, because osmnx `drive` excludes `highway=service`.
- There are no intersection delays, turn penalties, signal delays or parking time.

**Why it matters.** The drive surface uses two different speed concepts depending on whether a mapper happened to add `maxspeed`. That adds spatially uneven bias, since tagged corridors look faster. The speeds have no cited source.

**Recommended correction**
- Choose one documented policy. The recommended baseline is: ignore `maxspeed`, use config speeds by highway class including `*_link`, and treat `maxspeed` only as a cap.
- Remove the unused `service` key or switch to `drive_service` deliberately.
- Record speed provenance per edge (`speed_source ∈ {config, maxspeed, imputed}`).
- Test alternative speed sets in E5 (Section 8).
- Keep labelling drive times as free-flow lower bounds.

---

### C-06 — Population validation statistics overstate barangay-level reliability
**Severity: High** · **Addressable with existing data: Yes**

**Evidence (audit re-analysis of `barangay_population.csv`)**

| Statistic | Value | Comment |
|---|---|---|
| City total, WorldPop 2020 vs census 2020 | +2.33% | Matches the QA report |
| Pearson r, raw counts | 0.916 | Driven by barangay size range (51 to 15,994 people) |
| Pearson r, log counts | 0.855 | |
| Spearman ρ, counts | 0.867 | |
| **Pearson r, population density** | **0.506** | Spearman 0.76 |
| Median absolute % error (APE) | 32.0% | IQR 11.9% to 65.0%; 90th percentile 110.9%; max 416% |
| Σ\|WorldPop − census\| | 123,042 persons = **26.9% of census total** | Roughly 13% of residents are placed in the wrong barangay |
| Barangays with \|error\| > 50% | 58 (72,671 census residents) | |
| Barangays with \|error\| > 100% | 25 (20,103 census residents) | |

Error by barangay size (census quartiles):

| Size quartile | Census range | Median APE | Median signed error |
|---|---|---|---|
| Q1 (smallest) | 51 to 752 | 69.9% | **+69.9%** (systematic overestimate) |
| Q2 | 760 to 1,806 | 43.5% | +4.2% |
| Q3 | 1,813 to 3,299 | 31.8% | −0.1% |
| Q4 (largest) | 3,350 to 15,994 | 12.4% | +0.9% |

The largest overestimates are small downtown barangays such as Delgado-Jalandoni-Bagumbayan (+416%), Gloria (+330%) and Flores (+316%). This fits WorldPop assigning residents to dense commercial built-up areas where the census counts few residents.

- **Circularity.** WorldPop Global2 R2025A is a *top-down* random-forest dasymetric model that redistributes official administrative population totals (census circa 2020) to 100 m cells. The city-level agreement is therefore largely built into the method, not an independent test. Which administrative level was used as input for the Philippines is not confirmed here (P-04).
- The correlation is **implemented correctly** (`np.corrcoef`). The problem is interpretation: raw-count Pearson r across units of very different size rewards getting large barangays roughly right.

**Why it matters.** Population weights decide both barangay means and the "persons beyond threshold" counts that a decision-support system should report. In central-district barangays, weights may be off by a factor of 2 to 5. Rankings of small barangays are therefore unreliable even where travel times are accurate.

**Recommended correction**
- Replace "r ≈ 0.92" as the headline with: median APE, signed bias by size class, and the share of barangays within ±25%.
- Add a per-barangay `pop_reliability` flag (for example, `low` if 2020 |error| > 50% or ≤ 5 populated cells).
- Offer a **census-calibrated weight variant**: rescale each barangay's 2020 cells so their sum equals the PSA 2020 count, then apply WorldPop's 2020→2026 change. This keeps the within-barangay pattern from WorldPop and the barangay totals from the census. Test it in E4.

---

### C-07 — Barangay indicators for barangays with few populated cells are unstable
**Severity: Medium** · **Addressable with existing data: Yes**

**Evidence**
- `pop_cells` per barangay: minimum 1, 10th percentile 4, median 16. **27 barangays have ≤ 5 cells; 66 have ≤ 10.** The smallest barangay is 0.0141 km² (about 1.7 cells).
- Cells are assigned wholly by centre point. The WorldPop grid is 3 arc-seconds (about 92.6 m × 91.0 m at this latitude, not exactly 100 m).
- `max_min` is the value of a single cell.

**Why it matters.** For a barangay with 2 to 5 cells, the indicators reflect a handful of 100 m points. Their position relative to the boundary and the road network is close to arbitrary. Such barangays should not be ranked against barangays with 50 or more cells without a warning.

**Recommended correction**
- Publish `pop_cells` next to every indicator (it is already in the CSV, but not in the map or documentation).
- Flag barangays with ≤ 5 cells.
- Replace `max_min` with a population-weighted P90.
- Optionally, use **fractional (area-weighted) cell allocation** for boundary cells: split each cell's population by the area of the cell polygon in each barangay. This is cheap at about 7,800 cells.

---

### C-08 — The 2026 population surface is close to a uniform rescaling of 2020
**Severity: Medium** · **Addressable with existing data: Yes** (labelling)

**Evidence**
- The barangay ratio wp_2026 / wp_2020 ranges from 1.040 to 1.077 (median 1.051, 5th to 95th percentile 1.044 to 1.065). City growth is +5.16%.
- The 2026 values are **model projections**. Nothing in ABOT verifies them against a census (the 2024 POPCEN is not used).

**Why it matters.** "Analysis year 2026" may suggest the system reflects current settlement patterns. In practice the spatial pattern is 2020's. New subdivisions or relocations after 2020 are not represented in any specific way.

**Recommended correction**
- Label 2026 values as "WorldPop R2025A 2026 projection (modelled, not census-verified)".
- Run E4 (2020 vs 2026 weights) to show that rankings barely change. If they barely change, this supports reporting 2020-based results, which are closer to observed data.
- If PSA 2024 POPCEN barangay counts become available through HDX or PSA, consider using them as a calibration target (outside data; check licence first).

---

### C-09 — Several other categories mix services that are not substitutes
**Severity: Medium** (High for `government` and `transport`) · **Addressable with existing data: Yes** (splitting); validation needs outside data

**Evidence (tag composition of the 826 features)**

| Category | Composition | Problem |
|---|---|---|
| government (168) | 61 `amenity=townhall` (mostly barangay halls), 105 `office=government` | `office=government` includes regional offices of national agencies (BIR, LTFRB, MARINA, DPWH, SEC, Bureau of Immigration), plus Boy Scouts council, Metro Iloilo Water District, Bangko Sentral ng Pilipinas, Coast Guard, PNP Regional Office, Bureau of Fire Protection. Some of these overlap `safety`. Nearest-"government" time is not a meaningful service measure. |
| market (74) | 58 `shop=supermarket`, 16 `amenity=marketplace` (public markets, talipapa) | Supermarkets and public wet markets serve different needs and price points. |
| finance (178) | 130 bank, 48 ATM | An ATM is not a bank branch. 37 features are unnamed (mostly ATMs). |
| education (162) | 125 school, 24 college, 10 university, 3 kindergarten | Mixes levels. No `isced:level` and no public/private distinction. "Nearest school" says little about the right school for a 7-year-old. |
| transport (15) | 8 bus/jeepney terminals, 7 ferry terminals | Ferry terminals (to Guimaras and other islands) are not everyday transport access. **Jeepney routes and stops, the main public transport mode, are missing.** 14.4% of residents' nearest "transport" facility is outside the city. |
| safety (28) | 11 police, 17 fire | Different services with different response logic. Response is usually *from* the station to the resident, which is a different direction (see P-06). |
| pharmacy (97) | 87 `amenity=pharmacy`, 9 `shop=chemist` only | `shop=chemist` in OSM means a drugstore or toiletries shop and may not dispense medicines. |

**Why it matters.** Within-category substitutability is the core assumption of nearest-facility accessibility. When it fails, the indicator mostly reflects the most numerous sub-type.

**Recommended correction**
- Define sub-types inside the existing nine categories, for example:
  - `government.barangay_hall` vs `government.agency_office`
  - `market.public_market` vs `market.supermarket`
  - `finance.bank` vs `finance.atm`
  - `transport.land_terminal` vs `transport.ferry`
- Report only the sub-types with a clear service meaning.
- Keep an `ambiguous` flag for features whose tags or names conflict (for example, PNP and BFP offices tagged `office=government`).

---

### C-10 — Single-category assignment by priority hides multi-role facilities
**Severity: Medium** · **Addressable with existing data: Yes**

**Evidence**
- `categorise` returns the **first** matching category ([osm.py:88-94](../src/abot/osm.py#L88-L94)).
- The config comment says that putting pharmacy first stops `healthcare=pharmacy` from counting as health. That is only true when `amenity=pharmacy` or `shop=chemist` is also present. A feature tagged only `healthcare=pharmacy` would still be classed as health. No such case exists in the current data, so this is a latent bug.

**Why it matters.** A school that serves as an evacuation centre, or a hospital with a pharmacy, can only appear in one category. Evacuation, which is last in priority, loses the most.

**Recommended correction.** Store a list of all matching categories per feature (or one row per feature–category pair) and route each category on all of its members. Keep `category` (primary) for display. Add a unit test for the `healthcare=pharmacy`-only case.

---

### C-11 — Duplicate facilities remain after de-duplication
**Severity: Low** for travel times, **Medium** for `n_<category>` counts · **Addressable with existing data: Yes**

**Evidence**
- De-duplication only removes a *node* inside a *same-category polygon* ([osm.py:97-105](../src/abot/osm.py#L97-L105)). Remaining:
  - 220 same-category pairs within 50 m
  - **14 same-category, same-name pairs within 50 m**, for example "Development Bank of the Philippines" (two ways 4 m apart), "Pakiad Talipapa" (two marketplace ways 23 m apart), "Ledi Supermart" (two nodes 5.5 m apart), bank + ATM pairs of the same bank 4 to 9 m apart, "Alpha Star Christian Preschool" (two nodes 16 m apart)
  - Barangay hall node + polygon pairs under different names (for example "Sangguniang Pambarangay ng Ungka Ⅱ" and "Bulwagang Pambarangay ng Ungka Ⅱ", 4 m apart)
- Many same-brand facilities far apart are *legitimate* branches (for example 15 Mercury Drug, 17 BPI) and must not be merged.

**Why it matters.** Nearest-facility times are almost unaffected, since a duplicate at the same place does not change the minimum. Facility counts per barangay are inflated, and per-capita or 2SFCA supply measures would double-count.

**Recommended correction.** Add a de-duplication report: same category, within 25 to 50 m, and the same normalised name or one feature unnamed. Flag these for manual review rather than deleting them automatically. Record decisions in a small versioned CSV of overrides (`config/facility_overrides.csv`). This is a correction table, not fabricated data.

---

### C-12 — Accessibility indicators summarise the distribution too narrowly
**Severity: Medium** · **Addressable with existing data: Yes**

**Evidence**
- Indicators are: mean, single-cell max, and % within 10/15/30 minutes (walk) or 5/10/15 minutes (drive) ([accessibility.py:80-98](../src/abot/accessibility.py#L80-L98)).
- The thresholds have no stated source.
- The mean uses only non-NaN cells, while the `% within` denominator includes NaN cells. This is a latent inconsistency, invisible today because there are no NaN cells.
- No absolute count of persons beyond a threshold is produced.
- The QA citywide indicator is the mean only.

**Why it matters.** Means hide the tail, which is the people a public-infrastructure system most needs to find. See Section 7.

---

### C-13 — The QA status labels give false assurance
**Severity: Medium** · **Addressable with existing data: Yes**

**Evidence**
- `facilities_* PASS` means only "≥ 5 mapped in the city". Evacuation (5) and transport (11) both show PASS.
- `*_unreachable_pop PASS` cannot fail (C-04).
- `wp2020_vs_census_barangay_r PASS` (threshold 0.7) passes despite the problems in C-06.

**Recommended correction.** Rename the statuses to say what was tested (for example `count≥5` instead of PASS). Add the checks from C-04 and C-06. Add an explicit `fitness_for_reporting` field per category: `quantitative`, `indicative`, or `descriptive only` (Section 6.4).

---

### C-14 — Single walking speed with no cited source and strong sensitivity
**Severity: Medium** · **Addressable with existing data: Yes**

**Evidence.** Walking speed is 4.5 km/h (1.25 m/s) for everyone. Audit calculation for health (current definition):

| Walk speed | Pop-weighted mean (min) | % ≤ 10 min | % ≤ 15 min |
|---|---|---|---|
| 3.0 km/h (≈ 0.83 m/s; slower pedestrians, e.g. older adults, people carrying loads) | 19.00 | 30.3 | 49.9 |
| 4.5 km/h (baseline) | 12.67 | 49.9 | 70.1 |
| 5.0 km/h | 11.40 | 55.4 | 74.4 |

**Why it matters.** Mean times scale exactly as 4.5 / v. Threshold shares are **non-linear**: "% within 15 min" moves by 20 percentage points between plausible speeds. Threshold-based findings therefore depend heavily on this assumption. There is also no allowance for heat, rain, flooding, footpath quality or road crossings.

**Recommended correction.** Cite a walking-speed source (Section 10), report a slow-pedestrian variant next to the baseline (E1), and describe threshold results as being under a stated speed.

---

### C-15 — Study-area buffer is arbitrary and results near the city limit depend on it
**Severity: Low to Medium** · **Addressable with existing data: Partly** (testing a larger buffer needs a new Overpass fetch)

**Evidence.** Share of residents whose nearest facility is in the 1 km buffer:

| Category | Population share |
|---|---|
| Transport | 14.4% |
| Market | 3.4% |
| Finance | 3.2% |
| Pharmacy | 2.1% |
| Education | 1.0% |
| Government | 0.5% |

Facilities beyond 1 km are invisible. Pavia, Oton and Leganes border the city, and their facilities may be closer than city ones for edge barangays. The network is also cut at 1 km, which can lengthen routes that leave and re-enter the city.

**Why it matters.** This mainly affects edge barangays (Arevalo, Jaro and Mandurriao fringes). For drive mode, 1 km is short.

**Recommended correction.** Test a 3 km buffer once (E7). If edge-barangay results change, adopt the larger buffer for drive mode. Report `nearest_facility_outside_city` per cell.

---

### C-16 — OSM snapshot date is not recorded in provenance
**Severity: Medium** (for research reproducibility) · **Addressable with existing data: Yes**

**Evidence**
- The cached Overpass responses carry `osm3s.timestamp_osm_base` values from 2026-10-31T06:13:55Z to 06:17:57Z.
- This timestamp is not written to `manifest.json` or the QA report.
- The cache is git-ignored. Deleting it silently produces a different OSM snapshot.

**Recommended correction.** Record the Overpass timestamps, the query tags and the osmnx version in the manifest and the QA report. Save the facility table as a versioned CSV for each run.

---

### C-17 — Minor network-filter issues
**Severity: Low** · **Addressable with existing data: Yes**

**Evidence**
- osmnx's default access filter only excludes `access=private`:
  - 21 drive edges (4.1 km) with `access=no` remain in the drive graph (unclassified, residential, tertiary, one `primary_link`).
  - 16 `access=no` service or driveway edges remain in the walk graph.
- `barrier=gate` nodes (common at gated subdivisions) are not considered.
- The walk filter drops roads tagged `sidewalk=separate`. Pedestrian continuity then depends on the separately mapped sidewalks being connected.

**Recommended correction.** Use a custom filter or a post-filter that removes `access=no` edges unless `foot` or `motor_vehicle` explicitly allow them. Review gates manually where they sit on routes for many residents. Low priority.

---

## 5. Potential problems requiring further verification

### P-01 — Snap legs may cross rivers, fishponds or walls
**Severity: High (if confirmed)** · **Verification with existing data: Partly**

**Evidence**
- For the 1,511 cells (25,292 people) more than 150 m from their drive snap node, the audit compared (walk snap distance + walk-network distance to that drive node) with the straight-line distance. Median ratio 1.55; 90th percentile 8.45; 99th percentile 18.4.
- In **482 cells (7,289 people)** the walking route is more than 3× the straight line.
- Iloilo City has the Iloilo River, Batiano River, Dungon Creek and coastal fishponds, all of which a straight snap line can cross.

**Why unconfirmed.** A high ratio can also mean that connecting footpaths are missing from OSM (a data gap) rather than a physical barrier.

**Verification.** Fetch OSM water polygons and waterways for the study area (small; already supported by osmnx) and test whether each snap segment intersects water. Visually inspect the 482 flagged cells. Then either make snapping water-aware (choose the nearest node whose segment does not cross water) or use a walk-network access leg (C-03).

---

### P-02 — Polygon representative points may misplace large facilities
**Severity: Medium** · **Verification with existing data: Partly**

**Evidence.** Hospitals (relations and ways) and universities are reduced to `representative_point()`. That point is somewhere inside the campus, not at the gate, and is then snapped by straight line to the nearest node, possibly on a road with no entrance. Facility snap distances reach 376 m.

**Verification.** For polygons larger than about 1 ha, compare the snapped node with OSM `entrance=*` nodes, or with the nearest point on the polygon boundary to the network. Measure the change in times.

---

### P-03 — Disconnected network fragments were removed silently
**Severity: Low to Medium** · **Verification with existing data: No** (needs a re-fetch with `retain_all=True`, which is small)

`retain_all=False` and `largest_component` discard isolated sub-networks (for example, footpath networks inside compounds or in informal settlements). How many nodes and edges were dropped is not recorded. Residents near those pieces are snapped to the main network, possibly across barriers. Log the number of dropped components, nodes and edges, and map them.

---

### P-04 — Admin level of WorldPop's input totals for the Philippines
**Severity: Medium** (affects how C-06 is read) · **Verification with existing data: No** (needs WorldPop documentation)

The R2025A release statement and its census metadata sheet say which administrative level and source were used for the Philippines. If the inputs were municipal or city totals, then 2.3% city-level agreement is mostly by construction, and the only meaningful test is the within-city one. Check before writing any validation claim.

---

### P-05 — COD-AB barangay boundaries vs census enumeration units
**Severity: Medium** · **Verification with existing data: No**

COD-AB barangay polygons (from NAMRIA and PSA) are suitable for humanitarian use but are not legal cadastral boundaries. Part of the barangay-level error in C-06, especially in tiny downtown barangays, may come from **boundary misalignment** rather than WorldPop error. The COD-AB city area of 72.6 km² vs about 78 km² commonly cited already points to coastline differences. Compare with any official city barangay map available from the Iloilo City Planning and Development Office, if it can be shared.

---

### P-06 — Direction of travel for emergency services
**Severity: Low** for walk, **Medium** for drive safety · **Verification with existing data: Yes**

ABOT computes resident → facility. For fire and police, the relevant time is station → resident, which differs on one-way streets in drive mode. It can be computed on the forward graph cheaply. Decide which direction each category means.

---

### P-07 — Non-residential population in commercial districts
**Severity: Medium** · **Verification with existing data: Partly**

WorldPop estimates where people *reside*, but the overestimates in the commercial core (C-06) suggest that residential population is being assigned to commercial buildings. This affects population weights downtown. Census calibration (C-06) partly corrects it at barangay level.

---

## 6. Data completeness and uncertainty assessment

### 6.1 Sources of uncertainty, by component

| Component | Nature | Main uncertainty | Size (where measured) |
|---|---|---|---|
| Barangay boundaries | Official humanitarian dataset (NAMRIA/PSA via OCHA) | Coastline and seam alignment | City area 72.6 vs ~78 km² (unverified figure) |
| 2020 census | **Observed count** (PSA CPH 2020) | Reference date 1 May 2020; mapped to COD-AB polygons | 180/180 matched |
| WorldPop 2020 | **Modelled** dasymetric estimate | Within-city allocation | Median barangay APE 32%; small barangays +70% |
| WorldPop 2026 | **Modelled projection** | Not census-verified; spatial pattern ≈ 2020 | Ratio 1.04–1.08 |
| OSM roads | Volunteered, mapped data | Missing alleys, footpaths, access tags | Not measured; drive snap leg 26% of time |
| OSM facilities | Volunteered, mapped data | Completeness, tagging, duplicates | See 6.2 |
| Travel speeds | **Assumed** parameters | Walk speed; drive free-flow vs legal limits | ±20 pp in "% within 15 min" (walk) |

### 6.2 Facility completeness — what can be said with current data

**Absence in OSM is not evidence that a service is absent.** With no authoritative registry loaded, completeness cannot be *measured*. It can only be *bounded* using internal clues:

- **Barangay halls.** Only **56 of 180 barangays** contain a mapped `amenity=townhall`. Every barangay has a barangay government and most have a hall, though some may share or rent premises. This points to substantial under-mapping of the most local tier of government.
- **Barangay health stations.** Only about 16 `health_post` features are mapped. Health stations are a core primary-care layer in Philippine cities, so this count is very likely incomplete. It is not proof.
- **Hospitals.** 14 human hospitals are mapped, and the list includes the major named hospitals in the city. This is likely the most complete health sub-type, but it should be checked against the DOH National Health Facility Registry.
- **Evacuation.** 5 features, at most 2 plausibly designated centres. Effectively uncovered.
- **Transport.** No jeepney stops or routes. The category does not represent the dominant mode.
- **Attribute completeness.** Unnamed features: finance 37/178, evacuation 3/5, safety 3/28, transport 3/15. No school level, no public/private ownership, no hospital level or bed capacity.

### 6.3 Recommended facility completeness assessment

For each category or sub-type, compare OSM with an authoritative list:

| Category | Candidate reference source (check access and licence first) |
|---|---|
| Hospitals, health stations, clinics | DOH National Health Facility Registry (NHFR) |
| Public schools | DepEd school masterlist / LIS-based public school list |
| Evacuation centres | Iloilo City CDRRMO list; DSWD DROMIC / CCCM evacuation-centre data |
| Police, fire | PNP and BFP station lists for Iloilo City |
| Barangay halls | City barangay directory (DILG / City Government) |
| Public markets | City Economic Enterprise / market administration list |

**Procedure**
1. Geocode the reference list only where coordinates are given or can be verified. **Never fabricate coordinates.**
2. Match OSM features to the reference by normalised name and distance (for example ≤ 150 m).
3. Report:
   - **recall**: the share of reference facilities found in OSM
   - **precision**: the share of OSM features that are genuine, in-category and operating
   - **positional error** of the matched pairs
4. Store results in `data/interim/qa/completeness.json`.

Where no reference list is available, record "completeness not assessed" rather than a number.

### 6.4 Recommended fitness-for-reporting tiers

The cut-offs below are **analytical reporting rules proposed for ABOT, not official standards**.

| Tier | Rule | Treatment in outputs |
|---|---|---|
| **A: quantitative** | Validated recall ≥ ~80% and a clear service definition | Full indicators, rankings, underserved flags |
| **B: indicative** | Coherent definition, completeness not yet validated or moderate | Indicators shown with the label "access to *mapped* facilities"; no definitive rankings |
| **C: descriptive only** | Very sparse, undefined or unvalidated | Facility map only; no travel-time statistics |

Proposed tiers **before** any external validation (no category can reach Tier A without it):

| Category / sub-type | Proposed tier | Reason |
|---|---|---|
| health.hospital | B | Likely near-complete, needs NHFR check |
| health.primary_care | B (weak) | Health stations likely under-mapped |
| health.other (dental, lab, therapy) | C | Not a basic-access service set |
| education (schools, ideally split by level) | B | Coherent once levels are separated |
| pharmacy (`amenity=pharmacy` only) | B | Coherent; `shop=chemist` ambiguous |
| market.public_market | B | 16 features, coherent |
| market.supermarket | B | Commercial; label clearly |
| finance.bank | B | Coherent |
| finance.atm | C | Not a substitute for a bank |
| government.barangay_hall | C, until completeness improves | 56/180 barangays covered |
| government.agency_office | C | Not a substitutable service |
| safety.police / safety.fire | B, reported separately | Small counts; direction issue (P-06) |
| transport | C | No jeepney data; ferries are special-purpose |
| evacuation | **C** | See C-02 |

### 6.5 Communicating population uncertainty

- Always say "WorldPop modelled estimate". Never say "population" without a qualifier in tables about cells or barangays.
- Show WorldPop and census side by side for 2020 at barangay level, with the signed difference. This is already in `barangay_population.csv`.
- Publish a barangay `pop_reliability` flag (C-06) and show it on the map as hatching.
- For persons-beyond-threshold counts, give a **range** across the WorldPop and census-calibrated weight variants (E4). Round to the nearest 100 to avoid false precision.
- Never describe 2026 values as current counts.

---

## 7. Recommended accessibility indicators

All thresholds below are **analytical reporting thresholds**. They are not official Philippine service standards. If an authoritative reference (for example a DOH, DepEd or LGU planning standard) is found, cite it and use its value. Otherwise, document the threshold set as "chosen for comparability".

### 7.1 Recommended indicator set (per barangay, mode and reportable category)

| Indicator | Definition | Priority | Rationale |
|---|---|---|---|
| `pop_beyond_T` | Persons in cells with time > T (T ∈ {5, 10, 15, 30, 60}) | **1** | Most directly actionable: how many people, and where |
| `pct_within_T` | Share of population with time ≤ T | **1** | Comparable across barangays of different size |
| `p50_min` | Population-weighted median | **2** | Robust central value; replaces the mean as headline |
| `p75_min`, `p90_min` | Population-weighted percentiles | **2** | Tail access; P90 replaces the unstable single-cell max |
| `mean_min` | Population-weighted mean | 3 | Keep for continuity, but not as headline |
| `rank_*` | Rank on `pct_within_T` (or P90) with ties and a reliability flag | 3 | Shown only for Tier A/B categories and non-flagged barangays |
| `access_leg_min`, `snap_flag_pop` | Off-network component; population beyond snap tolerance | **1 (QA)** | Makes C-03 and C-04 visible |
| `pop_cells`, `pop_reliability` | Support for each indicator | **1 (QA)** | Makes C-06 and C-07 visible |

**Weighted percentiles** should use one documented method. Sort cells by time and take the first time at which cumulative population weight is ≥ q × total (the "inverted cumulative weight" definition). Unit-test it against simple hand-computed cases.

**Not recommended as accessibility measures:**
- Facilities per barangay or per capita (`n_*`). This is a supply count, sensitive to boundaries and duplicates; keep it only as context.
- Composite multi-category indices. They hide which service is lacking and mix categories of different data quality.

### 7.2 Identifying underserved communities

Use a transparent rule-based classification rather than a statistical clustering method at first:

1. Work at **cell level** (100 m) for maps. Barangay level is for tables.
2. A barangay is **"potentially underserved for category X"** if `pct_within_T < threshold` **and** `pop_beyond_T` is above a stated minimum, **and** the classification holds in at least ~80% of sensitivity variants (Section 8).
3. Report how robust each classification is (for example "underserved in 6 of 7 scenarios").
4. Exclude or separately flag barangays with low population reliability or a high snap-flagged population.

Local spatial statistics (for example Getis-Ord Gi*) can be added later. With 180 barangays of very unequal size and the uncertainties above, they would add complexity without making results more defensible at this stage.

### 7.3 Indicators most useful for a public infrastructure DSS

The most decision-relevant are, in order:
1. **Persons beyond threshold**, mapped at cell level and summed per barangay.
2. **% within threshold**.
3. **Median and P90 travel time**.

All of them should be shown only for categories with a clear service definition and Tier A/B data. Each should come with a **robustness label** from the sensitivity analysis.

### 7.4 Feasibility of a future 2SFCA (not implemented in this milestone)

**Computational feasibility: high.** 2SFCA needs a cell-to-facility travel-time matrix limited to a catchment d₀. For example, about 7,800 cells × ~100 facilities per category within 30 minutes is a sparse matrix that can be built with bounded Dijkstra from each facility (`cutoff=d₀`), in seconds to a few minutes on the current laptop. Enhanced 2SFCA (distance-decay weights) adds negligible cost.

**Data feasibility: currently low.** Needed:

| Requirement | Why | Possible source |
|---|---|---|
| **Supply capacity** per facility (beds, physicians, classrooms or seats, evacuation capacity in persons) | The numerator of the supply-to-demand ratio | DOH NHFR (bed capacity for licensed hospitals), DepEd enrolment and classroom data, CDRRMO evacuation capacity |
| **Demand definition** (target population, e.g. school-age children by level, pregnant women, all residents for evacuation) | The correct denominator | WorldPop age/sex structure (R2025A has age/sex layers; large extra download), PSA 2020 single-age data (**already downloaded**: the census file is single-age by sex) |
| **Population beyond the city** | City hospitals serve Western Visayas. A city-only demand base would overstate supply ratios. | WorldPop cells for a wider region (a larger raster window from files already on disk) |
| **Catchment size and decay function** | Results are sensitive to d₀ | Literature plus sensitivity analysis |
| **Completeness ≥ Tier A** for the category | Missing facilities bias ratios more strongly than nearest-distance measures | Section 6.3 |

**Recommendation.** Plan 2SFCA first for **hospitals (beds)** and **public schools (enrolment and classrooms)**, and only after the completeness assessment.

---

## 8. Sensitivity analysis plan

### 8.1 Design principles

- **One-at-a-time (OAT) variation** around a fixed baseline, plus two combined bounding scenarios (optimistic and pessimistic). A full factorial design is not needed and would be hard to explain.
- **Fix the baseline to the corrected categories** (C-01, C-09) before running experiments. Otherwise the sensitivity analysis measures definition problems already known.
- **Cache distances, not just times.** For walk mode, the network leg in metres from each node to the nearest facility is independent of speed. Storing it lets E1 run without any new Dijkstra.
- **Run cost.** Each category needs one Dijkstra on a ~13k-node (walk) or ~7k-node (drive) graph. The audit ran dozens in a few minutes in total, and graph loading dominates. Every experiment below runs in seconds to a few minutes with < 2 GB RAM.

### 8.2 Experiments

| ID | Factor | Variants | Needs re-routing? | Existing data? |
|---|---|---|---|---|
| **E1** | Walking speed | 3.0 / 4.5 (baseline) / 5.0 km/h | No (rescale stored distances) | Yes |
| **E2** | Snapping | (a) nearest node (baseline); (b) nearest edge with interpolation; (c) snap tolerance 200 / 300 m with flagged cells excluded from "within T" | Yes for (b) | Yes |
| **E3** | Facility definitions | Health: broad (current) / primary care / hospital. Finance: bank+ATM / bank only. Market: all / public market only. Also with vs without flagged-ambiguous and duplicate features | Yes (per category; cheap) | Yes |
| **E4** | Population weights | WorldPop 2026 (baseline) / WorldPop 2020 / census-calibrated 2020 / census-calibrated 2020 × WorldPop growth | No (travel times unchanged; reweight only) | Yes |
| **E5** | Drive speed policy | Config-only speeds (maxspeed ignored) / current mixed / config × 0.6 congestion factor | Yes (drive only) | Yes |
| **E6** | Thresholds | 5 / 10 / 15 / 30 / 60 min | No | Yes |
| **E7** | Study-area buffer | 1 km (baseline) / 3 km | Yes, plus **one new Overpass fetch** (about the same size as the current one, under 15 MB of JSON) | No (small download, explained in advance) |

**Bounding scenarios**
- **Pessimistic:** 3.0 km/h walking, strict category definitions, snap tolerance applied, congestion factor.
- **Optimistic:** 5.0 km/h walking, broad definitions, no tolerance, free-flow speeds.

### 8.3 What to report for each experiment

For every variant compared with the baseline, per reportable category:

1. **Citywide:** P50, P90, % within T, and persons beyond T, as a table with absolute and relative change.
2. **Rank stability:** Spearman ρ between baseline and variant barangay rankings, plus the number of barangays that move more than 20 rank positions.
3. **Classification stability:** the number of barangays whose "potentially underserved" status changes. This feeds the robustness label in Section 7.2.
4. **Largest changes:** the top 10 barangays by absolute change in % within T, to show *where* the assumption matters.

Write all outputs to `data/processed/sensitivity/` as CSV plus a short Markdown summary with a one-sentence interpretation per experiment, for example: "Findings for walk access to public markets are robust to walking speed (ρ = 0.98) but not to the threshold choice."

### 8.4 How to report changes in assumptions

- State the baseline assumption and its source next to every headline figure.
- Present headline figures as **baseline (range across variants)**, for example "62% (48–71%) of residents within 15 minutes' walk of a primary-care facility".
- Call a finding **robust** only if its classification holds in the large majority of variants (proposed analytical rule: ≥ 80%). Otherwise call it **assumption-dependent** and name the assumption.
- Never pick the variant that gives the most striking result after the fact. Fix the baseline before running the experiments and record it in config.

---

## 9. Prioritised improvement roadmap

All items preserve the current CLI (`abot fetch | build | report`) and existing outputs. New columns and files are **added**, and nothing is removed or renamed without a deprecation note. No new heavy dependencies are needed: everything uses numpy, pandas, geopandas, networkx, osmnx and scipy, which are already installed.

### Priority 0: correctness of meaning (do first; existing data only)

| ID | Item | Addresses | Effort |
|---|---|---|---|
| R-01 | Add an `abot audit` command reproducing this report's diagnostics (snap quantiles, facility tag composition, duplicates, population error by size class) → `data/interim/qa/audit.json` | Reproducibility of this audit | S |
| R-02 | Refine category definitions into sub-types within the existing nine categories; explicit `healthcare` value list; veterinary exclusion; `shop=chemist` flagged | C-01, C-09 | M |
| R-03 | Mark evacuation and transport as Tier C: no quantitative indicators, a WARN in QA, and an explanation in the report | C-02, C-13 | S |
| R-04 | Fix QA semantics: rename PASS labels, remove the vacuous unreachable check, add snap max / tolerance / flagged population, add `fitness_for_reporting` | C-04, C-13 | S |
| R-05 | Record facility snap distances; add `snap_flag` per cell | C-04 | S |
| R-06 | Record the OSM snapshot timestamp, osmnx version and query tags in the manifest and QA report; export the facility table as CSV | C-16 | S |
| R-07 | Write `docs/METHODOLOGY.md`, `docs/DATA_DICTIONARY.md` and `docs/DATA_SOURCES.md` (see Section 9.1) | Part 6 | M |

### Priority 1: better indicators and population handling (existing data)

| ID | Item | Addresses | Effort |
|---|---|---|---|
| R-08 | Weighted P50/P75/P90, `pop_beyond_T`, thresholds 5/10/15/30/60 for both modes, consistent denominators | C-12 | S |
| R-09 | Population reliability flag; replace headline r with APE / bias by size class; add census-calibrated weight variant | C-06, C-07, C-08 | M |
| R-10 | Multi-category membership for facilities; unit test for `healthcare=pharmacy`-only | C-10 | M |
| R-11 | Duplicate-candidate report and `facility_overrides.csv` (manual decisions, versioned) | C-11 | S |
| R-12 | Single documented drive-speed policy; config entries for `*_link`; per-edge `speed_source` | C-05 | S |

### Priority 2: robustness (existing data, plus one small fetch for E7)

| ID | Item | Addresses | Effort |
|---|---|---|---|
| R-13 | Edge-based snapping and walk-network access leg for drive mode; report access and network legs separately | C-03, P-01 | M |
| R-14 | Sensitivity runner (`abot sensitivity`) implementing E1–E6; E7 after approval of the extra fetch | Section 8 | M |
| R-15 | Water-crossing check for snap segments (OSM water layer, small fetch) | P-01 | S–M |
| R-16 | Log dropped network components; access=no post-filter | P-03, C-17 | S |

### Priority 3: external validation (needs outside data; ask before acquiring)

| ID | Item | Addresses |
|---|---|---|
| R-17 | Facility completeness assessment against DOH NHFR, DepEd, CDRRMO/DSWD, PNP/BFP lists | Section 6.3 |
| R-18 | Confirm WorldPop R2025A input admin level for the Philippines from the release statement and census metadata | P-04 |
| R-19 | Barangay boundary comparison with official city maps, if obtainable | P-05 |
| R-20 | 2SFCA design for hospitals and public schools once capacity data and Tier A completeness exist | Section 7.4 |

Effort: S ≈ under half a day, M ≈ 1 to 2 days, for one developer familiar with the codebase.

### 9.1 Documentation and language

**Current state.** The repository has a README and the generated QA report. **There is no separate methodology document, data dictionary or data-source document.** The README's "Method" and "Limitations" sections are accurate but brief, and the column meanings exist only as a short README list.

**Required distinctions and recommended wording**

| Distinction | Avoid | Prefer |
|---|---|---|
| Observed vs modelled | "Population of barangay X is 1,125" | "WorldPop modelled estimate: ~1,100 (2020 census: 218)" |
| Mapped vs verified facilities | "Iloilo has 5 evacuation centres" | "5 features tagged as evacuation-related in OpenStreetMap (snapshot 2026-10-31); official count not assessed" |
| Network vs actual travel time | "It takes 3 minutes to drive to a hospital" | "Modelled free-flow travel time on the mapped road network, excluding congestion, waiting and parking" |
| Proximity vs adequacy | "Barangay X is well served by health facilities" | "Residents of X are within 10 minutes' walk of a mapped primary-care facility; capacity and service quality are not assessed" |
| Estimate vs census | "2026 population: 492,459" | "WorldPop 2026 projection: ~492,000 (modelled; not census-verified)" |
| Data gap vs infrastructure gap | "Barangay X lacks a barangay hall" | "No barangay hall is mapped in OSM for X; this may reflect incomplete mapping" |

**How to state limitations without undermining usefulness.** Pair each limitation with what the result *is* good for. For example:

> "These indicators identify where residents are farthest, along the mapped network, from the nearest mapped facility of each type. They are suitable for screening and prioritising areas for field verification. They are not measurements of service adequacy."

Put a short "How to read these results" box at the top of the README, the QA report and the HTML map, rather than leaving all caveats at the end.

---

## 10. References and technical documentation consulted

### Repository material inspected

- `README.md`, `pyproject.toml`, `config/settings.yaml`, `.gitignore`
- `src/abot/`: `accessibility.py`, `osm.py`, `population.py`, `boundaries.py`, `qa.py`, `report.py`, `cli.py`, `config.py`, `fetch/common.py`, `fetch/sources.py`
- `tests/test_core.py` (13 tests, all passing at audit time)
- `data/processed/qa_report.md`, `barangay_access.csv`, `barangay_population.csv`, `abot_iloilo.gpkg` (all layers)
- `data/interim/graph_walk.graphml`, `graph_drive.graphml`, `data/interim/qa/*.json`
- `data/raw/manifest.json`, `data/raw/osm_cache/*.json` (snapshot timestamps)
- osmnx 2.1.1 source (installed): `_overpass.py` (network filters), `routing.py` (`add_edge_speeds` imputation), `settings.py` (`bidirectional_network_types`, `default_access`)

### Data and software documentation

- WorldPop. *Global2 Release Statement R2025A v1*. https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/Global2_Release_Statement_R2025A_v1.pdf
- WorldPop. *WorldPop Unveils Global 2: Next-Generation Global Population Dataset*. https://www.worldpop.org/blog/worldpop-unveils-global-2-next-generation-global-population-dataset/
- WorldPop Hub, R2025A 100 m country population counts listing. https://hub.worldpop.org/geodata/listing?id=135
- Boeing, G. (2025). Modeling and analyzing urban networks and amenities with OSMnx. *Geographical Analysis*. Also the OSMnx documentation, https://osmnx.readthedocs.io
- OpenStreetMap Wiki: `Key:emergency` / `Tag:emergency=assembly_point`; `Tag:social_facility=shelter`; `Key:healthcare`; `Tag:amenity=hospital`; `Tag:amenity=veterinary`; `Tag:shop=chemist`; `Key:access`; `Key:maxspeed`. https://wiki.openstreetmap.org
- OCHA HDX. Philippines Subnational Administrative Boundaries (COD-AB). https://data.humdata.org/dataset/cod-ab-phl
- PSA via HDX. 2020 Census population by single-year age, sex and barangay. https://data.humdata.org/dataset/popn-single-year-age-sex-and-barangay-census-2020

### Methodological literature

- Stevens, F. R., Gaughan, A. E., Linard, C., & Tatem, A. J. (2015). Disaggregating census data for population mapping using random forests with remotely-sensed and ancillary data. *PLoS ONE*, 10(2), e0107042.
- Luo, W., & Wang, F. (2003). Measures of spatial accessibility to health care in a GIS environment: synthesis and a case study in the Chicago region. *Environment and Planning B*, 30(6), 865–884. (2SFCA)
- Luo, W., & Qi, Y. (2009). An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians. *Health & Place*, 15(4), 1100–1107.
- Higgs, G. (2004). A literature review of the use of GIS-based measures of access to health care services. *Health Services and Outcomes Research Methodology*, 5, 119–139.
- Apparicio, P., Abdelmajid, M., Riva, M., & Shearmur, R. (2008). Comparing alternative approaches to measuring the geographical accessibility of urban health services: distance types and aggregation-error issues. *International Journal of Health Geographics*, 7, 7.
- Hewko, J., Smoyer-Tomic, K. E., & Hodgson, M. J. (2002). Measuring neighbourhood spatial accessibility to urban amenities: does aggregation error matter? *Environment and Planning A*, 34(7), 1185–1206.
- Bohannon, R. W. (1997). Comfortable and maximum walking speed of adults aged 20–79 years: reference values and determinants. *Age and Ageing*, 26(1), 15–19.
- Weiss, D. J., et al. (2020). Global maps of travel time to healthcare facilities. *Nature Medicine*, 26, 1835–1838.

### Candidate authoritative sources for later validation (not accessed in this audit)

- DOH National Health Facility Registry (NHFR)
- DepEd public school masterlist / Learner Information System extracts
- Iloilo City Disaster Risk Reduction and Management Office (CDRRMO) evacuation-centre list
- DSWD DROMIC evacuation-centre and displacement reports
- PSA 2024 POPCEN barangay counts (if released at barangay level)

---

## Appendix A — Which current findings can be interpreted?

| Finding (Milestone 01) | Interpretable? | Condition |
|---|---|---|
| City-wide 2020 and 2026 population of ~468k / ~492k | **Yes, as modelled estimates** | 2026 is a projection; city agreement is partly by construction |
| Barangay populations, large barangays (Q3–Q4) | **Mostly** | ~12–32% typical error |
| Barangay populations, small barangays (Q1) | **No** | Systematic +70% median bias; ≤ 5 cells in 27 barangays |
| Walk times to mapped schools, pharmacies, public markets, banks | **Conditionally** | Labelled "access to mapped facilities"; definitions refined; speed stated |
| "Walk/drive to health" (current definition) | **No** | Dominated by dental, lab and therapy features; includes a veterinary hospital |
| Walk time to hospitals (recomputed) | **Conditionally** | Pending NHFR completeness check |
| Drive times | **Only as free-flow lower bounds** | Mixed speed policy; ~26% is a straight-line walk leg |
| Evacuation accessibility | **No** | 5 features, ill-defined tags |
| Transport accessibility | **No** | No jeepney data; ferries are special-purpose |
| Government accessibility | **No**, as currently defined | Mixes barangay halls and regional agencies; 56/180 barangays have a mapped hall |
| "0 unreachable population" | **No** (not informative) | True by construction |
| Barangay rankings | **Not yet** | Await category fixes, reliability flags and sensitivity robustness |
