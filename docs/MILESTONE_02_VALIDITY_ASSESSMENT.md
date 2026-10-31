# ABOT — Milestone 02: Focused Validity Assessment

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Baseline assessed** | Milestone 01 outputs, commit `3edc0dd` (frozen copy in `data/archive/m01_3edc0dd/`) |
| **Also checked** | Milestone 02 working tree as of 15:22 (uncommitted; being implemented in a parallel session). Snapshot figures are marked **[M02 snapshot]** |
| **Follows** | [MILESTONE_02_ANALYTICAL_AUDIT.md](MILESTONE_02_ANALYTICAL_AUDIT.md) (C-03, C-04, C-06, C-07, C-08, P-01, P-04, P-05) |
| **Status** | Assessment and proposals only. **No pipeline code, configuration or project dataset was changed.** All diagnostics are read-only scripts run outside the repository. |

---

## How to read this report

- Each of the six issues has the same parts: **Evidence**, **Quantified impact**, **New data needed?**, **Correctable with existing data?**, **Recommended treatment** and **Remaining uncertainty**.
- **Verified** means checked against a primary document or measured from the data. **Inferred** means a reasoned explanation that has not been confirmed by the data provider.
- Population figures are WorldPop 2026 modelled estimates unless stated otherwise.
- Section 7 lists the proposed changes that need your approval. Nothing in it has been implemented.

### Data used by the diagnostics

| Data | Status |
|---|---|
| M01 GeoPackage, CSVs, GraphML networks (archive) | Existing; read only |
| WorldPop R2025A 2020 and 2026 rasters | Existing (`data/raw/worldpop`) |
| WorldPop R2025A **2024** raster | **Downloaded for this assessment**, into a temporary folder outside the repository |
| WorldPop R2025A release statement and census-source sheet (`global2_census_data_sources_R2025A_v1.xlsx`) | Downloaded and read |
| OSM water features (`natural=water/coastline/wetland`, `landuse=aquaculture/…`, `waterway=*`) | Fetched with osmnx, outside the repository |
| OSM coastline and the Iloilo City admin relation (r3499101) | Fetched with osmnx |
| GADM 4.1 level 2; geoBoundaries gbOpen PHL ADM3 (simplified) | Downloaded |
| PSA 2024 POPCEN barangay counts | **Not obtained**: psa.gov.ph refuses automated requests (HTTP 403). Only the city total, 473,728 (as shown on the PSA PSGC page in search results), is used |

---

## Summary

| # | Issue | Main finding | Severity for misleading results | New data? | Fix with existing data? |
|---|---|---|---|---|---|
| 1 | WorldPop product | R2025A is officially **alpha**. For the Philippines, WorldPop's input was the **PSA 2020 census at barangay level**. This means the WorldPop-vs-census check is **not independent validation**. No non-alpha gridded product is more appropriate. | High (interpretation) | Optional (PSA 2024 POPCEN, manual download) | Yes |
| 2 | Straight connectors across water | M01: **4,695 people (0.95%) walk** and **7,800 (1.58%) drive** have connectors crossing rivers, fishponds or coastline. The problem is local, concentrated in Calahunan, Hibao-an Sur and Ticud. The M02 edge-based, barrier-aware connector is a defensible fix, but it **silently drops** 4,538 people. | High locally, low city-wide | No (imagery check helps) | Yes |
| 3 | Boundary (72.6 vs 78.3 km²) | **Not coastline treatment.** COD-AB is a land polygon that closely follows the OSM coastline. Against OSM, there is a real inland mismatch of about 2.6 km² on the northern boundary. The 78.34 km² figure has no reproducible geometry behind it. | Low (≤0.5% population) | Yes, to resolve fully (official boundary) | Partly (documentation) |
| 4 | 100 m cells in small barangays | 27 barangays have ≤ 5 cells. In them, almost all population comes from cells that **straddle a boundary**, so their population totals depend on the allocation rule by **15–26%**. Their **travel times are stable** (median change 0.2 min). | Medium (population metrics only) | No | Yes |
| 5 | Free-flow driving | Drive threshold shares are extremely sensitive to the speed assumption. Hospital "≤ 10 min" falls from **81.7% to 31.4%** if network legs take twice as long. The wording is not consistent. | High (interpretation) | No (yes for calibration) | Yes (wording, sensitivity) |
| 6 | Proximity vs service level vs capacity | ABOT measures **proximity to the nearest mapped facility of a defined type**. Capacity is not measured: of 16 hospitals, `beds` is tagged for 3 in OSM. | Medium (interpretation) | Yes, for capacity (DOH NHFR, DepEd) | Yes (definitions, rules) |

---

## 1. WorldPop product: release, reference years, projection status, documentation

### Evidence

**Exact product (verified from the file headers and the provider):**

| Property | Value |
|---|---|
| Files | `phl_pop_2020_CN_100m_R2025A_v1.tif`, `phl_pop_2026_CN_100m_R2025A_v1.tif` |
| Product | WorldPop **Global2**, "Constrained estimates of 2015-2030 total number of people per grid square", release **R2025A v1** |
| Release status | "The dataset currently represents an **alpha version** (R2025A) product and may change over the coming year as improvements are made" (hub listing id=135 and release statement, September 2025) |
| DOI / citation | 10.5258/SOTON/WP00839 (Bondarenko M., Priyatikanto R., Tejedor-Garavito N., … Tatem A., Sorichetta A.) |
| Produced | TIFF timestamps 2025-08-01 (2020) and 2025-08-02 (2026); licence CC-BY-4.0 |
| Grid | EPSG:4326, 3 arc-seconds (91.1 m × 92.2 m at Iloilo), float32, persons per cell |
| Method | Top-down random-forest dasymetric disaggregation (popRF) of administrative-unit counts. Settlement constraint from a modelled annual built-settlement layer: GHSL BUILT-S/BUILT-V R2023, Google Open Buildings v3, Microsoft footprints, World Settlement Footprint |
| National totals | Aligned to **UN WPP 2024**, at a **1 January** reference date |

**Philippine inputs (verified from the R2025A census-source sheet, PHL row):**

| | First timepoint | Second timepoint |
|---|---|---|
| Source | PSA 2010 Census | PSA **2020 Census** (CPH 2020) |
| Highest admin level | 3 (city/municipality), 41,954 units | **4 (barangay), 42,058 units** |
| Used? | **No**: "Modelled with second timepoint only: [YES]" | Yes. After "nesting", **38,911 units** |

**What this means for the reference years:**
- **2020** in WorldPop is a modelled 1 January 2020 estimate, scaled to the WPP national total. The census reference date is 1 May 2020.
- **2026** is a **projection**. No population input after 2020 was used. The release statement says uncertainty "will increase for population datasets representing reference years further away from the input population dataset timepoints". It also says comparisons between years "should be undertaken with care especially at small area scales".

**Evidence that WorldPop reproduces barangay census totals where its units match COD-AB (verified from data; interpretation inferred):**
- 8 of 180 barangays have WorldPop-2020 / census-2020 within 0.5% of **1.0224**. Six of them are at exactly **1.022422**: Airport, Buhang, Lanit, Navais, San Isidro (Jaro) and Tagbac.
- This is what census × one national adjustment factor (WPP / PSA) would produce.
- The other 172 barangays form one contiguous block, whose combined ratio is 1.0235, also ≈ the national factor.
- **Inferred:** in most of Iloilo City, WorldPop's input units do not coincide with COD-AB v03 barangays. They may be "nested" (aggregated) units or an older boundary set. Inside those units, the random-forest weights decide how people are split between barangays.

### Quantified impact

| Check | Result |
|---|---|
| City total, WP2020 vs census 2020 | +2.33%. This is ≈ the national WPP adjustment, so it is **true by construction**, not evidence of accuracy |
| City total, WP2024 vs PSA POPCEN 2024 (473,728) | **+2.29%**: the same offset |
| City growth 2020→2024 | WorldPop +3.48% vs PSA +3.52%. This is the **first independent check** (the 2024 count was not a WorldPop input), and it agrees at city level |
| Barangay-level APE (median 32%) | Measures **unit and boundary mismatch plus within-unit random-forest allocation**. It is not an independent accuracy test, in either direction |
| 2026 vs 2020 spatial pattern | Barangay growth ratio 1.040–1.077 (audit C-08). The pattern is essentially 2020's |

**Sensitivity of M01 results to the choice of population weights** (M01 travel times, five weight sets):

| Indicator | WP2026 (M01) | WP2020 | WP2024 | Census-2020-anchored¹ | Census-anchored + WP growth to 2026 |
|---|---|---|---|---|---|
| Total population | 492,459 | 468,282 | 484,568 | 457,626 | 481,241 |
| Walk to "health": % ≤ 15 min | 70.1 | 70.1 | 70.1 | 69.2 | 69.2 |
| Walk to market: % ≤ 15 min | 56.0 | 56.0 | 56.0 | **53.6** | **53.6** |
| Walk to pharmacy: % ≤ 15 min | 62.2 | 62.2 | 62.2 | 61.4 | 61.4 |
| Walk to education: % ≤ 15 min | 87.8 | 87.8 | 87.8 | 88.2 | 88.2 |
| Barangay rank correlation, persons > 15 min walk to health (vs WP2026) | — | 1.000 | 1.000 | 0.998 | 0.998 |
| Overlap of the 20 barangays with most persons > 15 min | — | 20/20 | 20/20 | 18/20 | 18/20 |
| Largest change in one barangay's persons > 15 min | — | 456 | 149 | **4,498** | 4,870 |

¹ Each barangay's WorldPop 2020 cell pattern is rescaled so that its sum equals the PSA 2020 count. Barangay **mean times** do not change under this rescaling, because rescaling a whole barangay leaves its weighted mean unchanged. Only counts and city-level shares change.

So the WorldPop year (2020, 2024 or 2026) barely matters. The census anchoring changes city shares by up to 2.4 percentage points and individual barangay counts by thousands.

**Addendum: PSA 2024 POPCEN barangay counts.**
- The full table was read from the PSA PSGC page in the user's browser on 2026-10-31: 180 rows; sum 473,728, equal to the PSA city total; all 180 join to COD-AB through the correspondence code; licence CC BY 4.0; "PSGC as of 30 September 2026".
- This is the first **barangay-level independent test**, because POPCEN 2024 was not a WorldPop input:

| Check | Result |
|---|---|
| PSA barangay growth 2020→2024 | Median +3.0%, p10 −3.8%, p90 +14.5%, range −42.6% to +65.7%. **34 barangays declined** |
| WorldPop barangay growth 2020→2024 | **+2.7% to +5.0%** for every barangay |
| Rank correlation, PSA growth vs WorldPop growth | **0.05**: WorldPop has no information on differences in post-2020 change between barangays |
| Median \|WP2024 − POPCEN 2024\| per barangay | 30.8% (2020: 32.0%) |

This settles the projection question. For anything after 2020, WorldPop only scales up the 2020 pattern. Official 2024 barangay counts are the better source for barangay totals, so **option (c), POPCEN-2024-anchored weights, is now feasible and preferred**.

### Is a more appropriate non-alpha product available?

| Candidate | Status | Assessment |
|---|---|---|
| WorldPop Global1 (2000–2020, constrained 2020) | Not labelled alpha | Older generation. WorldPop states that Global2 adds the c2020 census round, building footprints and better projections. Its grid is misaligned with Global2. Its Philippine inputs were **not verified** here. Not preferable |
| JRC GHS-POP R2023A (100 m, 5-year epochs) | Released product | Built from CIESIN GPWv4.11 inputs, not anchored to the 2020 barangay census. Mollweide grid. Not preferable for barangay work; useful as an alternative-surface sensitivity |
| Meta HRSL Philippines (30 m) | Released | Reference year 2015 (stated). Not preferable |
| **PSA 2020 census** (barangay) | Official count | Already in ABOT. Observed totals, but not gridded |
| **PSA 2024 POPCEN** (barangay, reference 1 July 2024) | Official count | The only post-2020 observed source. Barangay values are on the PSA PSGC page, but **automated download is refused**; it must be downloaded manually |

**Conclusion:** no non-alpha gridded product is more appropriate. The alpha status matters less than it seems, because for the Philippines the barangay totals come from the 2020 census. What is modelled is (a) how population is split within WorldPop's units and (b) everything after 2020.

### New data needed?
Not for the recommended treatment. **Optional:** PSA 2024 POPCEN barangay table, downloaded by hand from the PSA PSGC page or the official release. Check the licence and terms before use.

### Correctable with existing data?
Yes.

### Recommended treatment (for approval, see P1)
1. **Do not replace WorldPop.** Change what it is used for:
   - **Primary weights:** census-2020-anchored. Barangay totals = PSA 2020 counts (observed); within-barangay pattern = WorldPop R2025A 2020.
   - **Sensitivity:** WP2026 projection.
   - If POPCEN 2024 is obtained, a 2024-anchored variant becomes the preferred "current" weight set.
2. Rewrite the population validation text. City-level agreement is by construction. Barangay agreement measures unit alignment. The 2020→2024 city growth comparison is the only independent check.
3. Record the full provenance in Documentation §3: alpha status, DOI, PHL inputs (admin-4 2020 census, 38,911 nested units, WPP 2024, 1 January).

### Remaining uncertainty after correction
- The within-barangay distribution is still modelled. It is likely biased towards commercial built-up cells downtown (audit P-07).
- Barangay totals are fixed at 2020 (or 2024).
- Census anchoring inherits any mismatch between PSA enumeration areas and COD-AB polygons (issue 3).
- WorldPop may revise R2025A. Pin the file SHA-256 (already recorded) and cite the version.

---

## 2. Straight connectors across rivers, waterways and fishponds

### Evidence

- **M01 code:** cells and facilities were snapped to the nearest graph **node** with a KD-tree and joined by an unchecked straight line ([accessibility.py at `3edc0dd`](../src/abot/accessibility.py)).
- **Test method:** every M01 connector was tested against OSM hard barriers. Hard barriers are water and fishpond polygons (`natural=water`, `landuse=aquaculture|reservoir|basin`, `waterway=riverbank`), plus river, canal and stream lines and the coastline. Culverted or tunnelled watercourses are excluded.
- **Rules** (the same defaults as the M02 configuration): a crossing counts if the connector runs **> 20 m inside a water polygon** or **intersects a watercourse or coastline line**, ignoring the part within **50 m of the cell centre**.
- **Reproduction check:** the diagnostic reproduced all 18 published M01 time columns to within 0.005 min.
- OSM water features in the study area: 436 fishpond/aquaculture polygons (4.22 km² inside the city), 8 river areas, 14 other water areas, 87 river/canal lines, 18 streams and 33 coastline ways.

### Quantified impact

**M01 connectors that cross a hard barrier:**

| | Walk | Drive |
|---|---|---|
| Cells | 355 | 495 |
| Population | **4,695 (0.95%)** | **7,800 (1.58%)** |
| Crossing type (population) | line only 3,227; area only 577; both 890 | line 4,762; area 902; both 2,135 |
| Median connector length of crossing cells | 176 m | 209 m |
| Barangays affected | 46 (3 with ≥ 10% of population) | 56 (8 with ≥ 10%) |
| Crossing only drains or ditches (not treated as barriers) | 1,114 people | 1,268 people |
| Facility connectors crossing | 3 (one bank/ATM, Lambuyao ES, Bulwagang Barangay ng Ortiz) | 16 (5 are ferry terminals on piers, which is expected) |

Most affected barangays (walk, share of WP2026 population): Calahunan 17%, West Habog-habog 13%, Hibao-an Sur 10%, Ticud (La Paz) 9%, Baybay Tanza 7%. Drive: Calahunan 22%, Progreso-Lapuz 21%, Ingore 11%, Ticud 10%.

**Populated cells inside water polygons:**
- 370 cells (6,212 people) have their centre inside a hard water polygon. 200 of them (2,278 people) are in fishpond polygons.
- Fishpond cells are sparse: 11.4 people per cell, against a city mean of 63. This is consistent with dike huts or a cell centre falling on a pond edge.
- A few fishpond cells hold 125–226 people. This suggests **some OSM fishpond polygons are outdated** (the land has since been built on), which would wrongly block real residents.

**Sensitivity to the two tolerance parameters** (M01 walk connectors, population crossing):

| Origin radius | Tolerance 0 m | Tolerance 20 m |
|---|---|---|
| 0 m | 14,464 | 10,661 |
| 25 m | 8,242 | 6,418 |
| 50 m (default) | 5,349 | **4,695** |

The count varies about **threefold** with these parameters. The 50 m origin radius is the main lever. It is defensible, because the cell centre is an arbitrary point within a ~92 m cell, but it must be reported as an assumption.

**Effect of a correction.** Two corrections were evaluated:

| | Prototype on M01 (barrier-aware nearest **node**, k = 12, ≤ 250 m) | M02 implementation [M02 snapshot] (barrier-aware nearest **edge**, walk-routed drive access) |
|---|---|---|
| Not connected | walk 4,951 (1.01%); drive 10,526 (2.14%) | **4,538 (0.92%)**: 1,134 barrier-blocked (128 cells) and 3,404 beyond 250 m (158 cells) |
| Rerouted around water | — | 1,902 people |
| Change in city-wide mean time | ≤ 0.2 min, all categories | (cannot be compared directly, because the categories changed) |
| Crossing cells that reconnect | walk to "health": median +0.3 min, p90 +8.1 min, max +12.9 min | — |
| Largest shares not connected | — | **Calahunan 1,665 (≈ 30% of its population); Hibao-an Sur 1,288 (≈ 23%)**; Tabuc Suba 319; Tacas 284; Baybay Tanza 240 |

The problem is local. City averages hardly move, but for some cells the error is up to 13 minutes, and the residents involved are concentrated in a few riverside and coastal barangays. In the M02 snapshot, the not-connected residents are **excluded from the indicators**. This makes Calahunan's and Hibao-an Sur's indicators describe only 70–77% of their residents, without saying so in the indicator itself.

### New data needed?
No. A manual imagery check of the 286 not-connected cells (mostly in 5 barangays) would separate real barriers from missing OSM footpaths and bridges and from outdated fishpond polygons. This is a desk task, not a dataset.

### Correctable with existing data?
Yes. The M02 approach (edge snapping, barrier test, routed drive access) already implements the core correction.

### Recommended treatment (for approval, see P3)
1. **Accept the M02 connector method** as the correction for C-03, C-04 and P-01.
2. **Do not drop not-connected residents silently.**
   - Report `pop_not_connected` and `pct_not_connected` per barangay next to every indicator.
   - Flag a barangay's indicators when more than **5%** of its population is not connected. In the M02 snapshot this flags Calahunan, Hibao-an Sur, Tabuc Suba (La Paz) and Baybay Tanza.
   - In city totals, report the not-connected count as its own category, not as a threshold failure or success.
3. Add a **connector sensitivity experiment**: origin radius {0, 25, 50} m × water tolerance {0, 20} m. Report the range of crossing, blocked and rerouted population.
4. Produce a **review list** of blocked cells with coordinates for an imagery check. Correct or flag obviously outdated fishpond polygons (record the review; do not edit OSM silently).

### Remaining uncertainty after correction
- Missing footbridges, footpaths and informal paths in OSM. Blocked cells may be reachable in reality.
- Outdated fishpond polygons.
- The choice of origin radius.
- Walls and gates are flagged only, not blocked (453 people in the M02 snapshot).
- OSM drains are treated as crossable.

---

## 3. Boundary discrepancy (72.63 km² vs "≈ 78 km²")

### Evidence

| Source | Area (km²) | Land part² (km²) | Sea part² (km²) | Vertices | IoU with COD-AB | Hausdorff |
|---|---|---|---|---|---|---|
| **COD-AB v03** (valid 2025-02-13; attribute `area_sqkm` 72.68) | **72.63** | 72.59 | 0.045 | — | 1 | — |
| OSM admin relation r3499101 (`admin_level=6`) | 109.51 | **71.40** | **38.11** | 505 | 0.635 | 4.7 km |
| geoBoundaries ADM3 2023 (simplified; derived from the earlier NAMRIA/PSA/OCHA COD-AB) | 72.69 | 72.49 | 0.20 | 85 | 0.984 | 97 m |
| GADM 4.1 level 2 (coarse) | 70.71 | 69.98 | 0.74 | 58 | 0.920 | 701 m |
| "78.34 km²" (PhilAtlas, dated 2013; Rappler; city investment portal) | 78.34 | — | — | no geometry | — | — |

² Land and sea split by polygonising the OSM `natural=coastline` lines (Panay, Guimaras and the strait between them).

**Where COD-AB and OSM differ on land:**
- **Only in OSM:** 0.70 km², including Lanit 0.24 km² and a coastal sliver near Calaparan about 58 m wide.
- **Only in COD-AB:** 1.88 km², mainly on the **northern inland boundary**: near Dungon 0.94 km² (up to about 565 m wide), Lanit 0.48 km² and Bito-on 0.38 km².

### Diagnosis

- **Coastline treatment does not explain the gap.**
  - COD-AB is a land polygon; only 0.045 km² lies seaward of the OSM coastline.
  - The only source that includes sea, OSM, adds 38 km² of municipal waters, which is far more than the 5.7 km² gap.
  - Coastal disagreement between COD-AB and OSM is limited to slivers under about 60 m wide.
- **Land-area definitions do not explain it either.** COD-AB already includes rivers and fishponds (4.2 km² of fishponds). Excluding water would make the area *smaller*, not closer to 78 km².
- **There is a real boundary mismatch, but it is inland, not coastal.** COD-AB and OSM disagree by about 2.6 km² along the northern city limit (Dungon, Lanit, Bito-on, Tacas).
- **The 78.34 km² figure is unresolved.** It appears only in secondary sources, dated 2013. No open geometry reproduces it, and the PSA or LMB primary source was not reached. It is probably a statutory or cadastral land-area figure, not the area of the NAMRIA/PSA digital polygon.

### Quantified impact

| | WorldPop 2026 population |
|---|---|
| Inside COD-AB but outside OSM | 2,571 (0.52%) |
| Inside OSM but outside COD-AB (mostly sea) | 2,084 (0.42%) |
| COD-AB vs GADM | 9,841 / 3,655 (GADM is coarse and not suitable) |

The effect on city totals and city-wide indicators is small, under 0.6%. For the edge barangays, the inland mismatch can move hundreds of residents and some facilities in or out of the study area. The 1 km network and facility buffer already protects their travel times.

### New data needed?
Yes, but only to settle which boundary is legally correct: the official city boundary or a cadastral map from the City Planning and Development Office or LMB/DENR, and the primary source of 78.34 km².

### Correctable with existing data?
Partly: the documentation and a QA measure.

### Recommended treatment (for approval, see P4)
1. **Keep COD-AB v03.** It is official NAMRIA/PSA-derived data, and its p-codes join to the census 180/180. Neither alternative has better provenance: OSM is volunteered, GADM is coarse, and geoBoundaries is an older COD-AB.
2. Describe 72.63 km² as **"area of the COD-AB v03 polygon (land), not the official land area"**. Stop citing "≈ 78 km²" as a comparison until a primary source is found. Fix the QA note in `boundaries.py` accordingly.
3. Optionally, add a boundary-sensitivity QA record (land IoU with OSM, population in the mismatch zones). This needs one small OSM fetch, which is already cached by osmnx.

### Remaining uncertainty after correction
- The legal position of the northern boundary (up to about 0.5 km).
- The origin of 78.34 km².
- Whether PSA enumeration areas follow COD-AB in Dungon, Lanit, Bito-on and Tacas.

---

## 4. Effect of 100 m population cells on small barangays

### Evidence
- WorldPop cell: 91.1 × 92.2 m (≈ 0.0084 km²).
- COD-AB barangays range from 0.0141 km² (about 1.7 cells) to 3.65 km². 7 barangays are smaller than 3 cells in area.
- **Method:** the M01 centre rule was compared with fractional, area-weighted allocation (each cell polygon split by barangay area), with the same M01 travel times.

### Quantified impact

| Centre-rule cells per barangay | Barangays | Census 2020 population | Median area (km²) | Median \|WP2020 − census\| | Median change in total, centre vs fractional | Median share of population from boundary-straddling cells | Median change in mean walk time to "health" |
|---|---|---|---|---|---|---|---|
| 1–2 | 6 | 3,700 | 0.02 | 51% | **26%** | **100%** | 0.18 min |
| 3–5 | 21 | 17,078 | 0.04 | **71%** | **15%** | **100%** | 0.20 min |
| 6–10 | 39 | 42,734 | 0.06 | 42% | 7% | 80% | 0.18 min |
| 11–20 | 31 | 45,195 | 0.13 | 43% | 7% | 70% | 0.17 min |
| 21–50 | 40 | 133,995 | 0.25 | 29% | 3% | 45% | 0.06 min |
| > 50 | 43 | 214,924 | 1.01 | 15% | 1% | 24% | 0.08 min |

- **27 barangays have ≤ 5 cells** (4.5% of census population) and **66 have ≤ 10** (63,512 people). They are concentrated in the dense old urban core, mostly in the City Proper.
- Cell count and census error are clearly related (Spearman −0.50).
- **Travel-time indicators are stable:**
  - The barangay rank correlation of mean walk time, centre vs fractional, is 0.995.
  - The 20 worst-served barangays are identical under both rules.
  - p90 change in the smallest bins: 0.9 min.
  - Small barangays are central, so all their cells are close to facilities.
- **Population quantities are not stable.** Examples: Timawa Tanza I (1 cell) has 145 people under the centre rule and 315 under fractional allocation. Delgado-Jalandoni-Bagumbayan has 1,175 vs 817, against a census count of 218.
- `max_min` in these barangays is the value of one or two cells.

### New data needed?
No.

### Correctable with existing data?
Yes.

### Recommended treatment (for approval, see P2)
1. Add a per-barangay **`pop_reliability`** flag:
   - **low**: ≤ 5 centre cells, or > 5% of population not connected. Add \|WP2020 − census\| > 50% as a third criterion **only if WorldPop totals remain the primary weights**. Under census-anchored weights (P1), barangay totals equal the census, so that criterion no longer applies.
   - **caution**: 6–10 cells.
   - **ok**: otherwise.

   Counts on the current data:
   - Cells ≤ 5: 27 barangays. Not connected > 5%: 4. \|error\| > 50%: 58.
   - With all three criteria, **71 barangays (93,640 census residents, 20%)** would be `low`. That many flags is itself a sign that raw WorldPop barangay totals should not be the primary weights.
   - Without the error criterion, about 31 would be `low`, and 25 more would be `caution`.
2. **Keep and map** travel-time indicators for all barangays, with the flag shown.
3. **Exclude `low` barangays from rankings of population-based quantities**: persons beyond a threshold, density, and future per-capita supply ratios.
4. For population-based comparisons, also report results **aggregated to the 7 city districts**, or to groups of contiguous small barangays, where 100 m cells are adequate.
5. Use **fractional allocation** for barangay population totals. It is cheap (about 7,800 cells), and it removes the arbitrary centre-point effect for small units.
6. Replace `max_min` with a population-weighted p90, as already planned in the audit (C-07).

### Remaining uncertainty after correction
- Within-barangay placement is still modelled (issue 1).
- Fractional allocation assumes population is spread evenly within a cell.
- Barangay census counts can themselves differ from the COD-AB polygon footprint (issue 3).

---

## 5. Free-flow driving times

### Evidence
- Drive edge speeds are assumed values by road class. In M02, a tagged `maxspeed` can only lower the assumed speed (cap policy).
- There is no congestion, signal delay, turn penalty, parking or vehicle-availability model.
- Wording is inconsistent. Limitations sections say "free-flow", but result tables and column names say "Drive ≤ 10 min" and `drive_*_pct_le10` ("share of residents within N minutes"). These read as observed journey times available to all residents.
- The M02 report and map label hospital drive times as "free-flow" but not elsewhere.

### Quantified impact
These are illustrative only, not a measured congestion level. The M02 snapshot drive times were recomputed with the network leg slowed by a factor; the walk access leg was kept fixed.

| Destination | Mean, free-flow | Walk-access share of time | % ≤ 10 min, free-flow | Network leg ×1.5 | ×2 | ×3 |
|---|---|---|---|---|---|---|
| Hospital | 7.46 min | 20% | **81.7%** | 51.9% | **31.4%** | 13.7% |
| Public market | 5.80 min | 26% | 92.5% | 76.8% | 59.0% | 29.2% |
| Pharmacy | 4.19 min | 36% | 97.8% | 90.9% | 82.2% | 61.4% |

Threshold shares for driving depend mostly on the speed assumption, not on facility location. Rankings between barangays are much less sensitive than absolute shares.

### New data needed?
No for wording and sensitivity. **Yes** for calibration: probe or GPS speeds, travel-time surveys, or a routing-service sample; check licences first.

### Correctable with existing data?
Yes.

### Recommended treatment (for approval, see P5)
1. **Standard terminology** everywhere (report, map, Documentation, README, column descriptions): **"modelled uncongested car travel time"**.
   - First use in each output: "modelled uncongested (free-flow) car travel time on the mapped OSM road network, including the walk to and from the road; excludes congestion, signals, turning, parking and car availability".
   - Never write "journey time", "travel time by car" without the qualifier, or "residents within N minutes' drive".
2. **Do not headline drive threshold shares.** Report them as **lower bounds**, next to a network-speed sensitivity (×1.5 and ×2 network leg) as an experiment.
3. State plainly that car times describe access **for households with a car**. They are not population access, because jeepneys, tricycles and walking dominate (no public transport model yet).
4. Column names can stay `drive_*` for compatibility, but display labels and the documentation glossary should use the standard term.

### Remaining uncertainty after correction
- Real speeds are unknown; the sensitivity factors are not calibrated.
- Time-of-day variation.
- Access legs assume 4.5 km/h walking.

---

## 6. Geographic proximity, service level and capacity

### Evidence
- The M01 "health" category mixed hospitals, clinics, dentists, laboratories and one veterinary hospital (audit C-01).
- M02 splits categories into sub-types with reporting tiers (hospital, primary care, school ownership, and so on). This addresses **service level** in part.
- **Capacity attributes in OSM** (raw cache):

| Facility type | Features | Capacity or level attributes |
|---|---|---|
| Hospital | 16 | `beds` 3, `capacity` 2, `emergency` 10, `operator:type` 4 |
| Primary care | 62 | `healthcare:speciality` 20, `emergency` 13, `operator:type` 27 |
| School and college | 193 | `isced:level` 101, `operator:type` 107, `grades` 6, **enrolment 0** |
| Pharmacy | 94 | `opening_hours` 10 |
| Public market | 17 | none |

Capacity, staffing, opening hours and affordability are essentially absent.

### Definitions to adopt (for approval, see P6)

| Concept | What it answers | How ABOT measures it now | Data required |
|---|---|---|---|
| **Geographic proximity** (potential spatial access) | How far, in modelled time, is the nearest mapped facility of a given type? | Network travel time to the nearest facility in an indicator group | OSM network and facilities (have) |
| **Service level** (what is offered) | Is the nearest facility a substitute for the service in question? (A barangay health station is not a hospital; a kindergarten is not a high school; an ATM is not a bank.) | Only by defining indicator groups of substitutable sub-types. **Facility level is not verified** (for example DOH hospital level 1–3, or public vs private) | DOH NHFR (facility type and level), DepEd school masterlist (level, public/private) |
| **Capacity / availability** (whether supply meets demand) | Can the facility serve the people who depend on it? | **Not measured** | Beds, staff, enrolment or classrooms, opening hours. Needed later for 2SFCA, which is out of scope for this task |

### Reporting rules to adopt
1. Every indicator is labelled **"access to the nearest mapped [sub-type]"**. Never write "served by", "coverage", "adequate access" or "underserved" without stating that only proximity is measured.
2. Each indicator group names its service level explicitly: "hospital (any level, public or private; level not verified)".
3. A shorter time is **not** better service. A barangay close to a small clinic may still lack hospital access, and a nearby facility may be over capacity, closed or unaffordable.
4. Facility counts per barangay (`n_*`) are counts of mapped facilities, not capacity.

### New data needed?
For service level (verified hospital level, school level) and for any capacity measure: yes (DOH NHFR, DepEd). For definitions and reporting rules: no.

### Correctable with existing data?
Yes, the definitions and wording.

### Remaining uncertainty after correction
- OSM completeness and attribute accuracy.
- Private vs public access (cost).
- Opening hours.
- Services that people actually use often bypass the nearest facility, which proximity indicators cannot capture.

---

## 7. Proposed changes for approval

Ordered by how much each prevents misleading results. None has been implemented. Items marked † touch files the parallel M02 session is editing, so they should be coordinated with that work.

| ID | Change | Files (expected) | Effect on results |
|---|---|---|---|
| **P1** | **Population weights.** Add a census-2020-anchored weight set (PSA barangay totals × WorldPop 2020 within-barangay pattern). **Decision needed:** (a) census-anchored 2020 as primary, WP2026 as sensitivity (**recommended**); (b) keep WP2026 primary, census-anchored as sensitivity; or (c) wait for a manual POPCEN 2024 download and anchor to 2024. Rewrite the validation wording (city agreement by construction; barangay APE measures unit alignment). Record the full WorldPop provenance. | `population.py`†, `accessibility.py`†, `config/settings.yaml`†, Documentation §3/§5.2/§6 | Barangay mean times unchanged. City shares within ±2.4 pp. Barangay counts change by up to about 4,500 people |
| **P2** | **`pop_reliability` flag** (cells ≤ 5 or not connected > 5%; plus \|error\| > 50% only if WorldPop totals stay primary) and **fractional allocation** for barangay totals. Exclude `low` barangays from population-based rankings. Add district-level aggregates. Population-weighted p90 instead of max. | `population.py`†, `accessibility.py`†, `report.py`† | New columns. About 31 barangays `low` (71 if WorldPop totals stay primary) |
| **P3** | **Connectors.** Keep the M02 method. Add per-barangay `pop_not_connected` / `pct_not_connected` and flag indicators when > 5%. Add a radius × tolerance sensitivity experiment. Produce a review list of blocked cells for an imagery check. | `accessibility.py`†, `config/experiments/`†, `report.py`† | No change to times. 4 barangays flagged (Calahunan, Hibao-an Sur, Tabuc Suba, Baybay Tanza) |
| **P4** | **Boundary wording.** Describe 72.63 km² as the COD-AB polygon area and drop the unverified 78 km² comparison. Optionally add a boundary-sensitivity QA record against OSM. | `boundaries.py` (QA note), Documentation §2/§8 | None |
| **P5** | **Terminology:** "modelled uncongested car travel time" everywhere. Do not headline drive threshold shares. Add a network-speed sensitivity experiment (×1.5, ×2). | `report.py`†, README, Documentation, `config/experiments/`† | Wording; new experiment outputs |
| **P6** | **Proximity, service level and capacity** definitions and reporting rules, in the Documentation methods and the report "How to read" box. | Documentation §5, `report.py`† | Wording |
| P7 | Port the diagnostics in this report into a reproducible `abot audit` command (audit item R-01), so that every number here can be regenerated. | new module | None |

**Not proposed in this task:** a public transport model, 2SFCA, replacing WorldPop, or editing OSM data.

---

## Appendix A — Diagnostic scripts

The diagnostics ran from a temporary scratch folder, not the repository. They used the project's virtual environment and the archived M01 outputs.

| Script | Purpose |
|---|---|
| `wp_groups.py` | WorldPop/census ratio structure (the 1.022422 barangays) |
| `pdftext2.py` | Text extraction from the WorldPop release statement |
| `connectors.py`, `conn_summary.py`, `conn_extra.py` | Barrier crossings, barrier-aware prototype, fishpond cells, radius × tolerance sensitivity |
| `boundary.py` | Boundary comparison with OSM, geoBoundaries and GADM; land/sea split; population in mismatch zones |
| `resolution.py` | Cells per barangay; centre vs fractional allocation; indicator stability |
| `weights.py` | Five population-weight variants; WP2024 vs POPCEN 2024 city total |

P7 proposes rebuilding these as `abot audit`. Until then, these figures cannot be regenerated from the repository alone.

## Appendix B — Sources

- WorldPop Global2 R2025A v1 release statement (September 2025): <https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/Global2_Release_Statement_R2025A_v1.pdf>
- WorldPop R2025A census data sources sheet: <https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/census/global2_census_data_sources_R2025A_v1.xlsx>
- WorldPop hub, Population Counts 2015–2030, 100 m, R2025A v1 (alpha disclaimer, citation, DOI 10.5258/SOTON/WP00839): <https://hub.worldpop.org/geodata/listing?id=135>
- Google Earth Engine catalogue entry, WorldPop GP 100m R2025A: <https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_R2025A_v1_pop>
- PSA PSGC, City of Iloilo barangays (2024 POPCEN; automated access refused): <https://psa.gov.ph/classification/psgc/barangays/0631000000>
- geoBoundaries gbOpen PHL ADM3 (source: NAMRIA, PSA, OCHA; build 2023): <https://www.geoboundaries.org/api/current/gbOpen/PHL/ADM3/>
- GADM 4.1: <https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PHL_2.json.zip>
- Secondary sources for 78.34 km²: <https://www.philatlas.com/visayas/r06/iloilo-city.html>; <https://ph.rappler.com/elections/2022/western-visayas-iloilo-city>
- JRC GHS-POP R2023A: <https://data.jrc.ec.europa.eu/dataset/2ff68a52-5b5b-4a22-8f40-c41da8332cfe>
- Meta HRSL Philippines (reference year 2015): <https://data.humdata.org/dataset/6d9f35c0-4764-49ee-b364-329db0b7a47d>
- OpenStreetMap contributors (ODbL), via Overpass/osmnx, retrieved 2026-10-31.
