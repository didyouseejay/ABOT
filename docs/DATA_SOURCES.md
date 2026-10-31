# ABOT data sources and provenance

None of the data are committed to git. `uv run abot fetch` downloads the files, `uv run abot build`
queries OpenStreetMap (or reuses the cache), and `data/raw/manifest.json` records exactly what was
used.

## 1. Datasets in use

| Dataset | Provider | Version / date | Licence | Nature | Use |
|---|---|---|---|---|---|
| Administrative boundaries (COD-AB) | OCHA / HDX, from NAMRIA & PSA | v03; HDX modified 2026-05-28 | CC BY-IGO | Official humanitarian reference boundaries (not cadastral) | City and barangay polygons |
| 2020 Census population by barangay | PSA via HDX | CPH 2020 (reference date 1 May 2020); HDX modified 2023-09-21 | CC BY | **Observed counts** | Validation of WorldPop |
| Population counts, constrained 100 m | WorldPop Global2 | R2025A v1 (alpha), years 2020 and 2026 | CC BY 4.0 | **Modelled estimates**; 2026 is a projection | Origins and population weights |
| Road/path networks, barriers, facilities | © OpenStreetMap contributors via Overpass (osmnx 2.1.1) | Snapshots listed in §3 | ODbL 1.0 | **Volunteered mapped data**, not verified | Routing, connection checks, destinations |

### Downloaded files (Milestone 01 fetch, unchanged)

| File | Bytes | SHA-256 |
|---|---|---|
| `cod_ab/phl_admin_boundaries.gdb.zip` | 360,586,879 | `e7fc18f1383a21066ecfbe595c5c1d77375c93341dedf7284f09d66dbd28c5ad` |
| `census_2020/2020-census-total-popn_single-age_malefemale_admin4.xlsx` | 48,727,855 | `7865dc000fab8308a6f57f9fe087024b99e9df12df7e9ff61c47c4dbf2263a64` |
| `worldpop/phl_pop_2026_CN_100m_R2025A_v1.tif` | 63,798,093 | `23b71c8e196a072a55b8d3596d589e4a8c7bf295e9b8944a6b937620f99c6751` |
| `worldpop/phl_pop_2020_CN_100m_R2025A_v1.tif` | 63,095,801 | `6a98ec3e2b9389535d2b9d9708fb9f5700aabf2a34f5a7fbc093dbc32724cac2` |

**WorldPop method note.** Global2 R2025A is a top-down, random-forest dasymetric model (alpha
release, DOI 10.5258/SOTON/WP00839). WorldPop's census-source sheet shows that its Philippine
input was the **PSA 2020 census at barangay level**, aligned to UN WPP 2024 national totals. This
was verified in [MILESTONE_02_VALIDITY_ASSESSMENT.md](MILESTONE_02_VALIDITY_ASSESSMENT.md) §1 and
resolves audit item P-04. Agreement with the 2020 census is therefore not independent validation,
and years after 2020 are projections with no newer population input.

PSA 2024 POPCEN barangay counts (CC BY 4.0) were read manually for the validity assessment and are
kept outside the repository. **They are not used by the pipeline.**

## 2. OpenStreetMap: how a snapshot is pinned

OSM changes continuously, so a version number cannot pin it. ABOT pins it in three ways:

1. **The Overpass response cache** (`data/raw/osm_cache/<sha1-of-query>.json`, created by osmnx). A
   rebuild with the same configuration reuses these files and makes no network request. All
   Milestone 02 rebuilds were made from cache.
2. **`timestamp_osm_base`**: the OSM database time that Overpass reports for each response.
3. **SHA-256 of each response**, recorded in `manifest.json` together with the query label, the
   buffer, and `used_by_runs`. Per-run details, including the exact query tags and the osmnx
   version, are in `data/interim[/<run>]/osm_provenance.json`.

If the cache is deleted, a rebuild fetches a *new* snapshot. The manifest checksums then show that
the inputs changed.

## 3. OSM snapshots used (all retrieved 2026-10-31)

| Cache file (prefix) | Query | Buffer | `timestamp_osm_base` (UTC) | Used by |
|---|---|---|---|---|
| `5d669ac14ae2` | walk network | 1 km | 06:13:55 | Milestone 01, hist_buffer_1km (M02 baseline; stale sens_maxspeed_override, archived) |
| `2987b4935257` | drive network | 1 km | 06:16:04 | Milestone 01, hist_buffer_1km (M02 baseline; stale sens_maxspeed_override, archived) |
| `d81a70d6b287` | facilities (Milestone 01 tag set) | 1 km | 06:17:57 | Milestone 01 only (archived baseline) |
| `bce843d2d512` | barriers | 1 km | 07:15:04 | hist_buffer_1km (M02 baseline; stale sens_maxspeed_override, archived) |
| `b21199209fb7` | facilities (Milestone 02 tag set) | 1 km | 07:16:21 | hist_buffer_1km (M02 baseline; stale sens_maxspeed_override, archived) |
| `547bf6791e75` | walk network | 3 km | 07:23:18 | baseline (since M02B), e7_buffer_3km, sens_maxspeed_override (M03), `abot validate` |
| `5b51ed1ede82` | drive network | 3 km | 07:24:21 | baseline (since M02B), e7_buffer_3km, sens_maxspeed_override (M03) |
| `5eb220f49c1c` | barriers | 3 km | 07:26:22 | baseline (since M02B), e7_buffer_3km, sens_maxspeed_override (M03) |
| `662e760ef580` | facilities (Milestone 02 tag set) | 3 km | 07:27:27 | baseline (since M02B), e7_buffer_3km, sens_maxspeed_override (M03), `abot validate` |

Notes:
- **The Milestone 02 facility query differs from Milestone 01.** It adds `amenity=health_post`,
  `veterinary`, `money_transfer`, `bureau_de_change`, `payment_centre` and `healthcare=pharmacy`,
  and it is queried by bounding box. It is therefore a new snapshot, taken about one hour after the
  Milestone 01 one. The road networks are the same responses as in Milestone 01.
- One further cache file (`6fbea713a434…`, 15:12 local time) is an unused barrier response. It came
  from a first attempt that queried by polygon, before the switch to bounding-box queries
  ([METHODOLOGY.md](METHODOLOGY.md) §6.1). It is left in place, because raw data are never deleted,
  and it is not referenced by any run.
- E7 used a separate facility snapshot taken 11 minutes after the baseline's. The facilities inside
  the city are identical in both (803 features with the same OSM ids), so the E7 comparison is not
  confounded by OSM edits.

**Licence obligation.** Any database derived from OSM that is shared publicly must be released
under the ODbL. Maps and figures must credit "© OpenStreetMap contributors".

## 4. External facility registries: availability research (not integrated)

Researched on 2026-10-31 by web search. **No registry data has been downloaded or reconciled.**
Every statement below should be confirmed on the live official site before the data are used.
Until a registry is obtained and matched, no ABOT category may be described as independently
verified.

### 4.1 DOH National Health Facility Registry (NHFR)

| Aspect | Finding |
|---|---|
| Responsible agency | Department of Health (DOH), Knowledge Management and Information Technology Service. Governed by DOH Administrative Order 2019-0060. |
| Official source | `https://nhfr.doh.gov.ph` (facility lists such as `rfacilities2list.php`, `VActivefacilitiesList`) |
| Downloadable data | Reported in DOH replies to FOI requests: lists can be filtered by facility type and region and downloaded as **Excel or CSV**. AO 2019-0060 states that the public can access and download the updated list. Coordinates are reported (by a third-party project) to be on facility *detail* pages, not in the list export. |
| Geographic coverage | National; all public and private facilities assigned an NHFR code |
| Reference year / updates | Continuously maintained. One source says the registry is validated and updated every March. The download date must be recorded. |
| Attributes / identifiers | Health facility code (long form `DOH000000000xxxxxx`, short form), name, facility type, ownership, region/province/city/barangay (incl. PSGC), and, for hospitals, bed capacity per FOI replies. Latitude/longitude are collected by DOH in decimal degrees (HF Geo Form). |
| Licence / restrictions | **Not found.** No explicit open licence was identified. DOH's terms and data-sharing policy must be checked, or permission requested, before redistribution. Internal research use for validation is likely lower-risk, but this is unconfirmed. |
| Useful for independent validation? | **Yes, the strongest candidate.** It is an official, coded, georeferenced registry, and **25 of the 103 OSM health features already carry an NHFR-style code in `ref`** (7 hospitals, 17 primary care), which enables exact matching. Caveats: registry coordinates have known quality issues (e.g. 0,0 entries), and "licensed" is not the same as "operating". |

### 4.2 DepEd school directory / masterlist

| Aspect | Finding |
|---|---|
| Responsible agency | Department of Education (DepEd); the Planning Service holds the Learner Information System (LIS) and the school masterlist. The DRRM Service lists "List of DepEd Schools" among its common operational datasets. |
| Official source | **No current official open download found.** Masterlists are mostly obtained through FOI requests (`foi.gov.ph`, agency DepEd) or regional or division web pages (one region or division each). |
| Other sources | HDX "Philippines – School locations" (DepEd via OCHA): **reference period 2008**, added 2015, update frequency "never". It is too old for validation. HDX "Philippines Education Facilities (OpenStreetMap Export)" (HOTOSM) is OSM-derived, so it is **not independent**. |
| Geographic coverage | National (masterlist); the 2008 HDX file is national but historical |
| Reference year | Masterlists are per school year (SY). The FOI responses seen were not dated in the search results. |
| Attributes / identifiers | 6-digit **School ID**, school name, sector (public/private), level/curricular offering, region/division/district, address. **Coordinates are not confirmed** to be published. |
| Licence / restrictions | Not found; FOI releases are usually provided for the requester's use. Confirm before redistribution. |
| Useful for independent validation? | **Yes, if a current masterlist is obtained.** Matching is easy: **85 of 125 OSM schools carry a 6-digit `ref` matching the DepEd School ID pattern** (73 tagged public). Without coordinates, the registry still supports *completeness* checks (which schools are missing from OSM) but not *positional* checks. |

### 4.3 Official Iloilo City evacuation-centre inventory

| Aspect | Finding |
|---|---|
| Responsible agency | Iloilo City Disaster Risk Reduction and Management Office (CDRRMO), with barangay DRRM committees. Nationally, DSWD DROMIC monitors evacuation-centre use. |
| Official source | **No published inventory found.** Press reports from the November 2025 Typhoon Tino response cite **450 evacuation centres** "ready to accommodate" about 47,342 families (≈226,741 people). An earlier, undated PNA report cites 317. These figures are from news reports and are not verified here. |
| Downloadable data | None found. DSWD DROMIC has had an "Evacuation Center Master List" post (2016); its download and coverage are unconfirmed. Historical HDX evacuation-centre datasets cover other cities (e.g. Zamboanga 2013). |
| Geographic coverage | City-level inventory presumed to exist at CDRRMO; designations are per barangay and can change per event |
| Reference year | Unknown |
| Attributes | Unknown. Typical sites are schools, gyms, covered courts, day-care centres and barangay halls, so many already exist in OSM under *other* categories. |
| Licence / restrictions | Unknown; requires a request to CDRRMO (or an FOI request to the City Government) |
| Useful for independent validation? | **Yes, and essential.** With about 450 designated centres reported against 6 OSM evacuation features, OSM coverage of designated evacuation centres is **on the order of 1%**. The current evacuation layer cannot support any accessibility statement. Because most centres are likely schools and halls, a CDRRMO list (names plus barangay) could be matched to existing OSM features and recorded as multi-category membership, without inventing coordinates. |

### 4.4 Summary

| Registry | Availability | Matching hook in current data | Recommended next step |
|---|---|---|---|
| DOH NHFR | Online list export (Excel/CSV), coordinates on detail pages | 25 NHFR codes in OSM `ref` | Download the Western Visayas / Iloilo City list; check terms; match by code, then by name and distance |
| DepEd masterlist | FOI / regional pages; no current open file | 85 School IDs in OSM `ref` | FOI request for the current Iloilo City Division masterlist, with coordinates if available |
| Iloilo City evacuation centres | Not published; CDRRMO holds it | Names of schools and halls | Formal request to CDRRMO |

### Sources consulted

- PSA, National Health Facility Registry: https://psa.gov.ph/node/120275
- DOH AO 2019-0060, *Guidelines on the Implementation of the NHFR*: https://legaldex.com/laws/guidelines-on-the-implementation-of-the-national-health-facility-registry ; https://jurisprudence.ph/laws/guidelines-on-the-implementation-of-the-national-health-facility-registry
- NHFR facility list: https://nhfr.doh.gov.ph/VActivefacilitiesList?start=25001
- DOH NHFR HF Geo collection form: https://caro.doh.gov.ph/wp-content/uploads/2025/01/National-Health-Facility-Registry-Collection-Form-1-10-2025.pdf
- FOI requests to DOH for facility lists: https://foi.gov.ph/requests/list-of-hospitals-in-the-philippines ; https://foi.gov.ph/agencies/doh/request-for-list-of-hospitals-and-healthcare-personnel-in-cavite
- Third-party NHFR scraping notes (coordinates on detail pages): https://github.com/Georgebruh/Project-Lepton/pull/7
- DOH GIS/GPS guidelines: https://healthgeolab.net/KNOW_REP/DOH_GIS-GPS_Guidelines_Standards_011714.pdf
- FOI requests to DepEd for masterlists: https://foi.gov.ph/requests/masterlist-of-all-deped-accredited-schools-both-public-and-private-in-the-country ; https://foi.gov.ph/requests/school-masterlist-for-2022-2023-or-2023-2024if-available
- HDX Philippines – School locations (2008): https://data.humdata.org/dataset/philippines-education-0-0
- HDX HOTOSM Philippines Education Facilities: https://data.humdata.org/dataset/hotosm_phl_education_facilities
- DepEd DRRMS common operational datasets: https://sites.google.com/deped.gov.ph/drrms/information-management/common-datasets
- OSM wiki, DepEd schools import: https://wiki.openstreetmap.org/wiki/Philippines/Data_import/DepEd_Schools
- Panay News, *Thousands flee homes as 450 city evacuation centers open*: https://www.panaynews.net/thousands-flee-homes-as-450-city-evacuation-centers-open
- SunStar Iloilo, red alert and evacuation reports: https://www.sunstar.com.ph/iloilo/tre%C3%B1as-orders-red-alert-status-in-iloilo-city-amid-tino-threat
- PNA, Iloilo City evacuation reporting: https://www.pna.gov.ph/articles/1162949
- DSWD DROMIC: https://dromic.dswd.gov.ph/?p=304
- HDX, Zamboanga evacuation centres (2013), via BTAA Geoportal: https://geo.btaa.org/catalog/c88ecb28-955b-4d0f-a773-1886a9c9d499
