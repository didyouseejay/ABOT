# ABOT data dictionary

Outputs as of Milestone 02B (3 km buffer, census-anchored weights). The baseline run writes to `data/processed/` and `data/interim/`. An
experiment run named `<run>` writes to `data/processed/<run>/` and `data/interim/<run>/`.
`data/raw/` is shared by all runs. None of `data/` is committed to git.

**Conventions**
- Times are in minutes; distances in metres.
- Population columns say what they are:
  - `pop_wp2020` / `pop_wp2026` are **original** WorldPop R2025A modelled estimates (2026 is a
    projection).
  - `pop_census2020_adj` is **adjusted**: the PSA 2020 barangay total spread by the WorldPop 2020
    pattern.
  - `census_2020` is the observed PSA count.
  - `pop` / `pop_total` are the **primary weight** (`population.primary_weight`, default
    `census_2020_anchored`).
- `<mode>` is `walk` or `drive`.
- `<group>` is an indicator group (see [METHODOLOGY.md](METHODOLOGY.md) §6.5):
  - health: `health_hospital`, `health_primary_care`
  - `pharmacy`
  - education: `education_basic`, `education_higher`
  - safety: `safety_police`, `safety_fire`
  - market: `market_public`, `market_supermarket`
  - finance: `finance_bank`
- `<category>` is one of the nine categories: `pharmacy`, `health`, `education`, `safety`,
  `government`, `market`, `finance`, `transport`, `evacuation`.

## 1. `barangay_access.csv` (also GeoPackage layer `barangay_access`)

One row per barangay (180).

| Column | Type | Meaning |
|---|---|---|
| `adm4_pcode` | text | COD-AB barangay p-code (`PH0603022xxx`) |
| `adm4_name` | text | Barangay name (COD-AB) |
| `pop_total` | float | Residents (primary weight) of the barangay's fractional cell pieces |
| `pop_connected` | float | Residents in cells with a valid network connection |
| `pop_not_connected` | float | Residents in cells with no acceptable connection (beyond 250 m or across water): no travel time, kept in every denominator |
| `pct_not_connected` | float | `pop_not_connected` as a % of `pop_total` |
| `indicators_flag_not_connected` | bool | `pct_not_connected` > 5% (same rule as `rel_network = low`; kept for compatibility) |
| `pop_drive_access_gt_flag` | float | Residents whose walk to the drive network is longer than 500 m (kept, flagged) |
| `<mode>_<group>_mean_min` | float | Population-weighted mean time to the nearest mapped destination of the group, **connected** residents. Drive = modelled uncongested car travel time |
| `<mode>_<group>_p90_min` | float | Population-weighted 90th percentile, connected residents (replaces `max_min` since M02B) |
| `<mode>_<group>_pct_le<N>` | float | % of **all** residents within N minutes; not-connected residents are neither within nor beyond. Walk: N = 10, 15, 30; drive: N = 5, 10, 15 (lower bounds). Analytical thresholds, not official standards |
| `rel_population`, `rel_population_reasons` | text | Population-data reliability (ok / caution / low) and why. Rules in [METHODOLOGY.md](METHODOLOGY.md) §8 |
| `rel_network`, `rel_network_reasons` | text | Network-connection reliability (ok / caution / low) |
| `rel_facility_inventory`, `rel_facility_inventory_reasons` | text | `unverified` until an official registry is matched; reasons list duplicates pending review |
| `rel_overall`, `rel_overall_reasons` | text | Most restrictive of population and network, with every reason. Not a score |
| `pop_ranking_eligible` | bool | False if population or network reliability is low: leave out of rankings of population-based quantities |
| `n_facilities_duplicate_review` | int | Facilities in the barangay that belong to a possible-duplicate pair pending review |
| `n_<category>` | int | Mapped features of the category inside the barangay, any sub-type and tier |
| `n_<group>` | int | Mapped destinations of the indicator group inside the barangay |
| other columns | | Joined from `barangay_population.csv` (§2) |
| `psgc_2023` | text | 2023 10-digit PSGC from the census file (reference only) |
| `census_name` | text | Barangay name in the PSA file |
| `census_2020` | int | **PSA 2020 census count** (observed) |
| `wp2020_vs_census_pct` | float | (WorldPop 2020 − census 2020) / census 2020 × 100. Unit-alignment diagnostic, **not validation** |

Columns removed since Milestone 01:
- `<mode>_<category>_*` for the old undifferentiated categories. They are replaced by the
  indicator groups above.
- Travel-time columns for the descriptive categories (evacuation, transport, government).
- Milestone 02B: `pop_cells` (now `pop_cells_centre`), `wp_2026` / `wp_2020` (now `pop_wp2026` /
  `pop_wp2020`, fractional), `<mode>_<group>_max_min` (now `_p90_min`).

## 2. `barangay_population.csv`

One row per barangay.

| Column | Meaning |
|---|---|
| `census_2020`, `census_name`, `psgc_2023` | PSA 2020 census (observed count) |
| `pop_census2020_adj` | **Adjusted** total; equals `census_2020` wherever WorldPop 2020 has population |
| `census_adj_factor` | `census_2020` / `pop_wp2020` (the within-barangay scaling) |
| `census_unallocated` | Census residents that could not be placed (no WorldPop 2020 cells); 0 in the baseline |
| `pop_wp2020`, `pop_wp2026` | **Original** WorldPop estimates, fractional allocation |
| `pop_wp2020_centre_rule` | WorldPop 2020 with the Milestone 01 centre rule (to show the allocation effect) |
| `pop` | Primary weight; `primary_weight` names it |
| `pop_cells_centre`, `pop_cells_touching` | Cells whose centre is inside / cells overlapping the barangay |
| `pct_pop_from_straddling_cells` | % of the barangay's residents in cells split with another barangay |
| `wp2020_vs_census_pct` | Unit-alignment diagnostic (not validation) |

## 3. `facilities.csv` (also GeoPackage layer `facilities`)

One row per mapped feature (after merging points inside same-category polygons).

| Column | Meaning |
|---|---|
| `osm_type`, `osm_id` | OSM element type (`node`, `way`, `relation`) and id: the permanent link back to OSM |
| `fid_key` | `osm_type/osm_id` |
| `name` | OSM `name` |
| `category` | Primary category (first match in `category_priority`) |
| `categories` | Every matching category, `;`-separated |
| `subtype`, `tier`, `class_status`, `class_reason` | Classification for the primary category (see `facility_roles` for others) |
| `amenity` … `description` | Copies of selected OSM tags: `amenity`, `healthcare`, `shop`, `office`, `emergency`, `social_facility`, `social_facility:for`, `operator`, `operator:type`, `isced:level`, `townhall:type`, `admin_level`, `government`, `ref`, `brand`, `description` |
| `osm_tags` | **All** OSM tags of the feature as JSON |
| `geom_source` | `node` (OSM point) or `representative_point` (point inside the OSM polygon) |
| `inside_city` | Location inside the city polygon (`False` = in the extraction buffer) |
| `conn_status` | `connected`, `beyond_tolerance` or `barrier_blocked` (set by the accessibility stage) |
| `conn_m` | Straight connector to the walk network (m) |
| `nearest_edge_m` | Distance to the nearest walkable edge, accepted or not |
| `conn_rerouted` | A nearer edge was rejected because the connector crossed water |
| `drive_access_m` | Walking distance on the network to the nearest drive-network node |
| `lon`, `lat` | WGS 84 coordinates (CSV only) |

`ref` is worth noting for later registry matching. Some health features carry DOH NHFR-style codes
(`DOH000000000046347`), and many schools carry 6-digit DepEd school IDs.

### `class_status` values

| Value | Meaning |
|---|---|
| `tag_rule` | Decided by OSM tags |
| `fallback` | No specific rule matched; the category's catch-all sub-type was used |
| `reclassified_by_name` | Tags said one thing, the OSM name another (e.g. a pet hospital tagged `amenity=hospital`) |
| `osm_name_only` | Evacuation centre by OSM name or description only; **not an official designation** |
| `attribute_missing` | A needed attribute is not tagged (e.g. school ownership) |
| `level_not_tagged` | Government level not tagged |
| `ambiguous` | Tag meaning is unclear (e.g. `shop=chemist`) |

## 4. GeoPackage layer `facility_roles`

One row per (feature, category), so a multi-role feature has several rows. Columns:
- `fid_key`, `osm_type`, `osm_id`, `name`, `inside_city`, point geometry
- `category`, `subtype`, `tier`, `status`, `reason`
- `category_evidence`: the tags or patterns that put the feature in the category
- `primary`: whether this is the feature's primary category

Routing uses this layer.

## 5. `facility_exclusions.csv`

Every feature not kept as-is, with `osm_type`, `osm_id`, `name`, `category` and `reason`:
- merged points (`point inside a same-category polygon …; merged into the polygon`)
- flagged possible duplicates (`possible duplicate of …; kept, review`), with `related_osm_type`,
  `related_osm_id` and `distance_m` since M02B; never merged automatically
- features matching no category

## 6. GeoPackage layer `access_cells` (Milestone 01/02: `access_cells_2026`)

One row per populated WorldPop cell touching the city (point at cell centre).

| Column | Meaning |
|---|---|
| `cell_id` | `r<row>c<col>` in the national WorldPop grid |
| `wp2020_cell`, `wp2026_cell` | Original WorldPop value of the whole cell |
| `pop_wp2020`, `pop_wp2026`, `pop_census2020_adj`, `pop` | In-city part of the cell: original, adjusted, primary weight |
| `frac_in_city` | Area share of the cell inside the city's barangays |
| `adm4_pcode` | Barangay holding most of the cell; `centre_adm4_pcode` = barangay of the centre (empty if outside the city) |
| `conn_status` | `connected`, `beyond_tolerance`, `barrier_blocked` |
| `conn_m` | Straight connector to the chosen walkable edge (m) |
| `nearest_edge_m` | Distance to the nearest walkable edge, accepted or not |
| `conn_rerouted` | A nearer edge was rejected because the connector crossed water |
| `conn_crosses_wall` | Connector crosses a mapped wall (flag only) |
| `drive_access_m` | Walking distance on the network from the cell to the drive network (connector included) |
| `t_<mode>_<group>` | Travel time in minutes; empty if the cell is not connected |

Milestone 01 columns `snap_m_walk` and `snap_m_drive` (straight line to the nearest node) are
replaced by `conn_m` and `drive_access_m`.

## 7. Other GeoPackage layers

| Layer | Contents |
|---|---|
| `city`, `barangays` | COD-AB polygons (EPSG:32651); `barangays.area_km2` |
| `pop_cells` | Cell centres with the population columns of §6 |
| `pop_pieces` | Table (no geometry): `cell_id`, `adm4_pcode`, `frac` and the weight columns of each cell–barangay piece; barangay totals and indicators are sums over pieces |
| `network_walk`, `network_drive` | Directed edges: `u`, `v`, `key`, `highway`, `name`, `length`, `maxspeed`, `speed_kph` and `speed_source` (drive only), `travel_time` (s) |
| `barriers` | `kind` (`water_area`, `water_line`, `wall`; `culverted_waterway` is recorded but is not a barrier), OSM ids and tags (incl. `tunnel`) |

## 8. QA and provenance

| File | Contents |
|---|---|
| `data/interim[/<run>]/qa/<stage>.json` | Checks: `{"ok": true/false/null, "value": …, "note": …}` for stages `boundaries`, `population`, `osm`, `accessibility`, `provenance` |
| `data/interim[/<run>]/osm_provenance.json` | Every Overpass response used by the run: query label, cache file, `timestamp_osm_base`, element count, SHA-256, query tags, osmnx version |
| `data/raw/manifest.json` | URL, retrieval time, size and SHA-256 of every downloaded file, plus each Overpass response with `used_by_runs` |
| `data/processed[/<run>]/qa_report.md` | Human-readable QA report |
| `data/processed[/<run>]/abot_map.html` | Interactive map (includes reliability layers) |
| `data/interim[/<run>]/run_meta.json` | Per stage: completion time, configuration SHA-256, buffer, primary weight (used by `abot audit`) |
| `data/processed[/<run>]/facility_inventory.csv` | Per indicator group: `n_in_city`, `n_in_buffer_outside_city`, `n_destinations_connected`, `n_not_connected_not_used`, `n_unnamed`, `n_not_decided_by_tag_rule`, `n_duplicate_review_pending`, `registry_reference` (none), `inventory_status` (unverified) |
| `data/processed[/<run>]/drive_speed_sensitivity.csv` | Per group and network-time factor (1, 1.5, 2): `mean_min`, `pct_le5/10/15` of all residents, `pct_not_connected` |

## 8a. Manual review (`abot review`, `data/processed[/<run>]/review/`)

Nothing here is applied to the analysis. Reviewer columns `review_status` (`pending`),
`reviewer_decision`, `reviewer_notes` are kept when the files are regenerated.

| File | One row per | Key columns |
|---|---|---|
| `possible_duplicates_review.csv` | flagged pair (`review_id` D01…) | `flagged_*` / `related_*`: fid, name, lon, lat, category, categories, subtype, tier, class_status, class_reason, geom_source, inside_city, barangay, conn_status, osm_tags; `distance_m`, `tags_identical`, `tag_differences`, `reason_flagged`, `suggested_action`, `effect_if_duplicate` |
| `unconnected_cells_review.csv` | cell without a valid connection | `cell_id`, `lon`, `lat`, `pop` (+ adjusted and original), `barangay`, `priority_barangay`, `conn_status`, `snapping_distance_m`, `nearest_edge_osmid/highway/name/nodes`, `candidate_edges_within_tolerance`, `blocking_barriers`, `centre_in_water_feature`, `walk_edges_within_500m`, `pedestrian_edges_within_500m`, `nearest_pedestrian_edge_m`, `bridges_within_500m`, `highway_types_within_500m`, `reason_not_connected`, `suggested_investigation` |
| `unconnected_by_barangay.csv` | barangay with unconnected residents | residents (fractional, as in the indicators), `rel_network`, cell counts by reason |
| `review.gpkg` | — | layers `duplicate_pairs`, `unconnected_cells`, `unconnected_nearest_edge_lines` |
| `*_map.html` | — | review maps with an imagery layer |

## 9. Comparisons (`abot compare`)

`data/processed/comparisons/<name>/` contains:

| File | Contents |
|---|---|
| `citywide.csv` | Per mode and group, for each run: `pop_used_pct`, `pct_not_connected`, `mean_min`, `p50_min`, `p90_min` (population-weighted, connected residents), `pct_le5/10/15/30/60` (of all residents, since M02B) |
| `barangay_changes.csv` | Groups in both runs: Spearman ρ of barangay means, median and max absolute change, barangays changing > 1 min, overlap of the 20 worst barangays |
| `cell_changes.csv` | Groups in both runs: population faster or slower by > 0.1 min, largest decrease or increase |
| `comparison.md` | All of the above as Markdown |

## 10. Archive

`data/archive/m01_3edc0dd/` holds a byte-for-byte copy of the Milestone 01 processed outputs, QA
JSON and graphs (commit `3edc0dd`). It is the fixed baseline for comparisons.
`data/archive/m02_wip_1km_20261031/` holds the uncommitted Milestone 02 1 km outputs, copied before
the M02B rebuild. `data/archive/review_m04_pre_access_taxonomy/` holds `review/m04/` and `component_aware/` as built with the pre-review access labels, plus `crosswalk/access_taxonomy_crosswalk.csv` (old class to new status for every cached walk way and gate node); its `review_m04/component_inventory.csv` is the reference for the exact component-class check in `abot components` (`review/m04/taxonomy_check.json`). `data/archive/<name>.sha256.json` records the SHA-256 of every archived file;
`abot audit` fails if one changes.
