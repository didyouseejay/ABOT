# ABOT audit — run `baseline` (2026-10-31T20:56:25)

Read-only: nothing was downloaded, written to data/ or repaired.

PASS 57 | WARN 3 | FAIL 0 | INFO 11

| section | check | status | detail | action |
|---|---|---|---|---|
| config | osm.boundary_buffer_m | PASS | 3000 m |  |
| config | population.primary_weight | PASS | census_2020_anchored (column pop_census2020_adj) |  |
| config | facility_rules | PASS | 10 indicator groups, all indicative |  |
| config | reliability_thresholds | PASS | population cells low<=5, caution<=10; network caution>1%, low>5% |  |
| config | historical_1km_config | PASS | hist_buffer_1km.yaml: buffer 1000 m, run_name hist_buffer_1km |  |
| inputs | raw: COD-AB boundaries | PASS | data/raw/cod_ab/phl_admin_boundaries.gdb.zip |  |
| inputs | raw: PSA census 2020 | PASS | data/raw/census_2020/2020-census-total-popn_single-age_malefemale_admin4.xlsx |  |
| inputs | raw: WorldPop 2020 | PASS | data/raw/worldpop/phl_pop_2020_CN_100m_R2025A_v1.tif |  |
| inputs | raw: WorldPop 2026 | PASS | data/raw/worldpop/phl_pop_2026_CN_100m_R2025A_v1.tif |  |
| inputs | manifest_sha256 | PASS | 13 files checked |  |
| outputs | layers: boundaries | PASS | city, barangays |  |
| outputs | layers: population | PASS | pop_cells, pop_pieces |  |
| outputs | layers: osm | PASS | network_walk, network_drive, barriers, facilities, facility_roles |  |
| outputs | layers: accessibility | PASS | access_cells, barangay_access |  |
| outputs | files: population | PASS | barangay_population.csv |  |
| outputs | files: osm | PASS | facilities.csv, facility_exclusions.csv |  |
| outputs | files: accessibility | PASS | barangay_access.csv, facility_inventory.csv, drive_speed_sensitivity.csv |  |
| outputs | files: report | PASS | qa_report.md, abot_map.html |  |
| outputs | graph_walk | PASS | graph_walk.graphml |  |
| outputs | graph_drive | PASS | graph_drive.graphml |  |
| outputs | review_files | PASS | 3 files in review/ |  |
| staleness | order: population | PASS | after boundaries |  |
| staleness | order: osm | PASS | after boundaries |  |
| staleness | order: accessibility | PASS | after population, osm |  |
| staleness | order: report | PASS | after accessibility |  |
| staleness | config: boundaries | PASS | built with the current configuration |  |
| staleness | config: population | PASS | built with the current configuration |  |
| staleness | config: osm | PASS | built with the current configuration |  |
| staleness | config: accessibility | PASS | built with the current configuration |  |
| staleness | config: report | PASS | built with the current configuration |  |
| staleness | osm_buffer_matches_config | PASS | outputs 3000 m, config 3000 m |  |
| staleness | review_files_current | PASS | generated after the last accessibility build |  |
| staleness | validation_files_current | PASS | review/m03 generated after the last build, same configuration |  |
| staleness | component_aware_layer_current | PASS | A3 reporting layer built after the last build, same configuration, baseline unchanged |  |
| staleness | experiment: hist_buffer_1km | PASS | built with hist_buffer_1km.yaml and the current code |  |
| staleness | experiment: sens_maxspeed_override | PASS | built with sens_maxspeed_override.yaml and the current code |  |
| consistency | barangays | PASS | 180 barangays (expected 180), unique p-codes |  |
| consistency | pieces_fraction | PASS | max cell fraction allocated 1.000000 |  |
| consistency | weight_columns | PASS | original (pop_wp2020, pop_wp2026) and adjusted (pop_census2020_adj) kept apart; pop = pop_census2020_adj |  |
| consistency | census_anchoring | PASS | 180 barangays: adjusted totals equal PSA 2020 (max diff 0.000) |  |
| consistency | census_unallocated | PASS | 0 census residents not placed |  |
| consistency | barangay_population_matches_pieces | PASS | max difference 0.00 |  |
| consistency | connected_cells_have_times | PASS | 0 connected cells missing a time |  |
| consistency | unconnected_cells_have_no_time | PASS | 0 unconnected cells carry a time |  |
| consistency | cell_population_matches_pieces | PASS | max difference 0.0000 |  |
| consistency | barangay_conservation | PASS | connected + not connected = total (max diff 0.00) |  |
| consistency | barangay_total_equals_cells | PASS | barangays 457,626 vs cells 457,626 |  |
| consistency | shares_and_denominators | PASS | shares non-decreasing; within + not connected <= 100% (all residents) |  |
| consistency | csv_equals_geopackage | PASS | 137 numeric columns compared |  |
| consistency | reliability_flags_reproducible | PASS | recomputed from their inputs: identical |  |
| consistency | facility_connections_recorded | PASS | 937 facilities with a connection status |  |
| consistency | external_facilities | INFO | 134 outside the city; 13 not connected and never used as destinations |  |
| consistency | pipeline_qa_warnings | WARN | accessibility.facilities_connected, accessibility.facilities_not_connected | see qa_report.md for each warning's note |
| validity | worldpop_vs_census_city | INFO | WorldPop 2020 / census 2020 = 1.0216; 5 barangays within 0.5% of the national factor 1.022422. Agreement is by construction (census is a WorldPop input), not validation |  |
| validity | worldpop_vs_census_barangay | INFO | median |WP2020 - census| = 30.5% per barangay: unit alignment, not accuracy |  |
| validity | allocation_rule_effect | INFO | 27 barangays with few cell centres: median change centre rule vs fractional 15% |  |
| validity | rel_population | INFO | ok 102, caution 51, low 27 |  |
| validity | rel_network | INFO | ok 170, caution 6, low 4 |  |
| validity | rel_facility_inventory | INFO | unverified 180 |  |
| validity | rel_overall | INFO | ok 92, caution 57, low 31 |  |
| validity | priority_barangays_not_connected | WARN | Baybay Tanza 141 (6.7%); Calahunan 1556 (30.7%); Hibao-an Sur 1109 (23.7%); Tabuc Suba (La Paz) 250 (6.4%) | manual review pending: data/processed/review/unconnected_cells_review.csv |
| validity | not_connected_citywide | INFO | 3,969 of 457,626 residents (0.87%): kept in denominators, reported separately |  |
| validity | drive_network_speed_sensitivity | INFO | hospital, % of residents within 10 min: x1 79.6%, x1.5 55.5%, x2 38.5% (lower bounds) |  |
| validity | possible_duplicates | WARN | 14 flagged pairs; 7 pending manual review; none merged automatically | review possible_duplicates_review.csv (`abot review` creates it) |
| validity | boundary_area | INFO | 72.63 km2 = area of the COD-AB v03 polygon (land), not the official land area |  |
| archive | m01_archive_present | PASS | data/archive/m01_3edc0dd |  |
| archive | hist_e7_buffer_3km_m02 | PASS | 21 files match SHA-256 recorded 2026-10-31T12:03:01+00:00 |  |
| archive | m01_3edc0dd | PASS | 11 files match SHA-256 recorded 2026-10-31T08:03:03+00:00 |  |
| archive | m02_wip_1km_20261031 | PASS | 15 files match SHA-256 recorded 2026-10-31T08:03:03+00:00 |  |
| archive | review_pre_m04_decisions | PASS | 1 files match SHA-256 recorded 2026-10-31T12:43:10+00:00 |  |
| archive | stale_sens_maxspeed_override_m02_1km | PASS | 18 files match SHA-256 recorded 2026-10-31T10:41:14+00:00 |  |
