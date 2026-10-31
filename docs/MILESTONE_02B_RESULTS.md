# ABOT — Milestone 02B: baseline adoption, reliability flags, audit and manual review

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Implemented in the working tree. **Not committed** (the user reviews and commits). |
| **Builds on** | Milestone 02 working tree; validity assessment proposals P1, P2, P4–P7 ([MILESTONE_02_VALIDITY_ASSESSMENT.md](MILESTONE_02_VALIDITY_ASSESSMENT.md) §7) |
| **Archives (unchanged)** | `data/archive/m01_3edc0dd/` (Milestone 01). New: `data/archive/m02_wip_1km_20261031/` (the uncommitted M02 1 km outputs, copied before this rebuild). Both have SHA-256 records beside them (`<archive>.sha256.json`), which `abot audit` checks. |
| **Out of scope** | Frontend, backend, PostGIS, public transport, 2SFCA. No manual review decision has been applied. |

## 1. Proposal map

| ID | Approved change | Implemented as | Modules |
|---|---|---|---|
| — | 3 km default extraction buffer | `osm.boundary_buffer_m: 3000`. The 1 km value is preserved in `config/experiments/hist_buffer_1km.yaml` (`run_name: hist_buffer_1km`) | `config/settings.yaml`, `config/experiments/` |
| P1 | Census-anchored weights; original and adjusted estimates kept apart | `pop_census2020_adj` = PSA 2020 barangay total × WorldPop 2020 within-barangay pattern (primary). `pop_wp2020` and `pop_wp2026` are the original WorldPop values. `pop` is a copy of the configured primary weight (`population.primary_weight`). Validation wording rewritten | `population.py`, `accessibility.py`, `report.py`, `settings.yaml` |
| P2 | Measurable reliability flags; fractional allocation; p90; ranking rule | Area-weighted split of every cell between barangays (`pop_pieces`); `rel_population`, `rel_network`, `rel_facility_inventory`, `rel_overall` with reasons; `pop_ranking_eligible`; `<mode>_<group>_p90_min` replaces `_max_min`; `facility_inventory.csv` | `population.py`, `reliability.py` (new), `accessibility.py`, `report.py` |
| P3 (rest) | Unconnected population in denominators; review list | Shares now use **all** residents; `pct_not_connected` reported separately; review file and map (`abot review`) | `accessibility.py`, `compare.py`, `review.py` (new) |
| P4 | Boundary wording | QA note: "area of the COD-AB v03 polygon (land), not the official land area"; 78.34 km² no longer used as a comparison | `boundaries.py`, docs |
| P5 | "Modelled uncongested car travel time"; drive shares as lower bounds; speed sensitivity | Wording in report, map, QA notes, docs; `accessibility.drive_network_time_factors: [1.5, 2.0]` → `drive_speed_sensitivity.csv` and a report section | `accessibility.py`, `report.py`, `settings.yaml` |
| P6 | Proximity vs service level vs capacity | "How to read" box in report and map; definitions in METHODOLOGY and Documentation | `report.py`, docs |
| P7 | Read-only `abot audit` | `audit.py` (new), `abot audit [--output FILE] [--skip-hashes]` | `audit.py`, `cli.py`, `config.py`, `qa.py` |

Not implemented from P2: **district-level aggregates.** Neither COD-AB v03 nor the PSA 2020 file
carries the city district of each barangay, and inventing a lookup would be unverifiable. A
user-supplied barangay→district table is needed (see §8).

## 2. Baseline adoption: 3 km buffer

- **Default:** 3,000 m around the city for walk/drive networks, barriers and facilities. Population
  cells and every indicator remain restricted to Iloilo City (COD-AB v03).
- **External facilities** are destinations only when connected: in the 3 km run, 121 facilities
  outside the city are used, and 13 outside the city have no valid path (mostly Guimaras, across
  the strait) and are never used. No facility **inside** the city is unconnected. Lambuyao
  Elementary School (outside the city), unconnected with 1 km, is connected with 3 km.
- **Historical baseline:** `config/experiments/hist_buffer_1km.yaml` differs from the default only
  in `osm.boundary_buffer_m` (a test asserts this). Its outputs go to
  `data/{interim,processed}/hist_buffer_1km/`. Both runs were rebuilt from the cached Overpass
  responses (all cache hits, no download).

### E7 re-run under the Milestone 02B method (`comparisons/e7_buffer_1km_vs_3km_m02b/`)

| Measure | Result |
|---|---|
| City-wide mean, any group | change ≤ 0.08 min (largest: walk primary care 13.29 → 13.21) |
| City-wide share within 15 / 30 min | change ≤ 0.2 percentage points |
| Barangay Spearman ρ (mean time) | ≥ 0.9999 for all 20 mode × group combinations |
| Overlap of the 20 worst barangays | 20 / 20 for every group |
| Cells slower with 3 km | **0** for every group (more network and destinations can only shorten trips) |
| Largest barangay change | Hibao-an Norte, walk to primary care 42.49 → 29.98 min; walk to hospital −2.35 min; Ungka walk to police −2.27 min; Hibao-an Norte car to primary care −1.95 min |

Conclusion (unchanged from Milestone 02): the buffer does not move city-wide results or rankings,
but 1 km understates access for border barangays. Adopting 3 km removes that bias at about 20%
more network nodes (walk 12,927 → 14,918; drive 6,794 → 8,049).

**Bug found and fixed while re-running E7.** The first re-run showed 81 residents with slightly
*slower* car times under 3 km. This was traced to the Milestone 02 speed assignment: osmnx stores
the classes of a merged edge as a list built from a set, so its order changes between Python
processes, and the code took the first element. Two identical builds could give different car times
(total network time 330,974 vs 331,146 s). The fix uses the slowest configured class of the merged
edge (deterministic; conservative for a lower-bound measure). It affects 32 of 20,021 drive edges
(9 km). After the fix, builds under different `PYTHONHASHSEED` values are identical, and no cell
is slower with 3 km. QA records `drive_edges_mixed_class`.

## 3. Population weights (P1)

| Weight set (column) | City total | Status |
|---|---|---|
| `pop_census2020_adj` (**primary**) | 457,626 | **Adjusted:** equals PSA 2020 in all 180 barangays (0 unallocated) |
| `pop_wp2020` | 467,501 | Original WorldPop R2025A 2020, fractional allocation |
| `pop_wp2026` | 491,633 | Original WorldPop R2025A 2026 projection (sensitivity) |

- Anchoring factor (census / WorldPop 2020) per barangay: min 0.19, median 0.96, max 4.48.
- **Wording rule.** Agreement with the census is never called validation. WorldPop R2025A used the
  PSA 2020 barangay census as an input for the Philippines, so the city-level difference (+2.16%
  here) is by construction. The barangay median |difference| (30.5%) measures how WorldPop's input
  units align with COD-AB barangays; it is not an accuracy test. These notes are in the QA report,
  the map legend and the docs.
- **Why 2020 and not POPCEN 2024:** the assessment's preferred option (c) needs the 2024 barangay
  table as a file in `data/raw/`. It was read in a browser but is not in the repository, and PSA
  refuses automated download. `population.primary_weight` is the switch point when it is added.

**Effect of weights and denominators** (1 km runs, M02 snapshot → M02B; `comparisons/m02_vs_m02b_1km_weights_and_denominators/`):

| Group | Walk mean | Walk ≤ 15 min (all residents) | Car mean |
|---|---|---|---|
| health_hospital | 27.26 → 27.93 | 24.7% → 22.9% | 7.46 → 7.61 |
| health_primary_care | 13.35 → 13.29 | 66.6% → 66.6% | 4.26 → 4.26 |
| market_public | 20.19 → 20.48 | 41.6% → 39.4% | 5.80 → 5.85 |
| safety_police | 18.71 → 19.35 | 41.6% → 37.8% | 5.47 → 5.59 |

Barangay ranks are stable (walk ρ ≥ 0.993, drive ρ ≥ 0.988; 19–20 of the 20 worst barangays
unchanged). The car-time changes combine the new weights and the mixed-class speed fix; they were
not separated.

## 4. Reliability flags (P2)

Four dimensions, each with a level, the measured values and a reason. There is no combined score.

| Dimension | Rule (configurable in `reliability:`) | ok | caution | low |
|---|---|---|---|---|
| `rel_population` | low: ≤ 5 cell centres, or census population that cannot be placed; caution: 6–10 cell centres, or census/WorldPop factor outside 0.5–2.0 | 102 | 51 | 27 |
| `rel_network` | low: > 5% of residents not connected; caution: > 1% | 170 | 6 | 4 |
| `rel_facility_inventory` | always `unverified` (no official registry matched); reasons list duplicates pending review | — | — | (180 unverified) |
| `rel_overall` | most restrictive of population and network, with all reasons | 92 | 57 | 31 |

- `rel_network = low`: **Calahunan 30.7%** (1,556 residents), **Hibao-an Sur 23.7%** (1,109),
  **Baybay Tanza 6.7%** (141), **Tabuc Suba (La Paz) 6.4%** (250). Caution: Tacas, Hinactacan,
  Hibao-an Norte, Lanit, Ungka, Ingore.
- `pop_ranking_eligible`: 149 of 180 barangays. The 31 others keep and map their travel-time
  indicators, but are left out of rankings of population-based quantities.
- Facility inventory (measurable parts, `facility_inventory.csv`): e.g. `finance_bank` has 13
  destinations pending duplicate review; `education_basic` has 44 schools with ownership not tagged
  and 4 destinations unconnected (outside the city).

## 5. Denominators (P3)

`pct_le<N>` now divides by **all** residents. Residents with no valid connection count neither as
within nor as beyond, so `pct_le<N> + pct_gt<N> + pct_not_connected = 100`. Means and p90 describe
connected residents. City-wide: 3,969 of 457,626 residents (0.87%) are not connected (2,983 with
no walkable edge within 250 m, 986 blocked by water). Their population is not forced onto the
network.

## 6. Car times: network-speed sensitivity (P5)

Share of all residents within 10 minutes (modelled uncongested car travel time; network leg × factor,
walk legs unchanged). Factors are illustrative, not calibrated.

| Group | × 1.0 | × 1.5 | × 2.0 |
|---|---|---|---|
| health_hospital | 79.6% | 55.5% | 38.5% |
| education_higher | 81.9% | 63.9% | 51.6% |
| market_public | 91.9% | 76.7% | 61.5% |
| safety_police | 95.7% | 79.7% | 63.2% |
| pharmacy | 97.2% | 90.1% | 81.9% |

Full table: `data/processed/drive_speed_sensitivity.csv`.

## 7. `abot audit` (P7)

Read-only. It never downloads, never writes under `data/` (writing its `--output` there is refused),
and creates no directory. A test checks this on an empty project, and a before/after listing of
every file under `data/` was identical. Exit status 1 if any check FAILs.

| Section | Checks |
|---|---|
| config | buffer, primary weight, facility rules, reliability thresholds, 1 km historical config |
| inputs | raw files present; SHA-256 against `data/raw/manifest.json` |
| outputs | GeoPackage layers and files per stage, graphs, review files |
| staleness | stage order, configuration fingerprint per stage, code changed after a stage, OSM buffer of the outputs = configured buffer, review files newer than the last accessibility build |
| consistency | barangays; piece fractions ≤ 1; original vs adjusted columns; census anchoring exact; barangay CSV = pieces; connected cells have times and unconnected cells none; conservation; shares and denominators; CSV = GeoPackage; reliability flags reproducible from their inputs; facility connections; pipeline QA WARNs |
| validity | the assessment diagnostics recomputed from outputs (WorldPop vs census as non-validation, unit alignment, allocation effect, reliability counts, priority barangays, not-connected population, drive sensitivity, duplicates pending, boundary wording) |
| archive | M01 archive present; every recorded SHA-256 still matches |

Result on the 3 km baseline: **PASS 50, WARN 3, FAIL 0, INFO 11.** The three WARNs are real open
items: 13 external facilities not connected, the 4 priority barangays above 5% not connected, and
14 duplicate pairs pending review. Each finding carries an action.

## 8. Manual review files (`data/processed/review/`, `abot review`)

Nothing in these files is applied. Every row is `review_status = pending`, no pipeline stage reads
them, and re-running `abot review` keeps the reviewer columns. **Awaiting your review.**

**Possible duplicate facilities:** `possible_duplicates_review.csv`, `possible_duplicates_map.html`,
layer `duplicate_pairs` in `review.gpkg`. There are 14 flagged pairs (13 distinct records; the PNB
group has three records). Each row gives both OSM ids, names, coordinates, distance, full OSM tags,
current category / sub-type / tier / status / connection, tag differences, the flagging reason, a
suggested action and the likely effect if confirmed.

| Suggestion | Pairs |
|---|---|
| Probably distinct (bank vs ATM sub-type): likely keep both | 5 (D01, D02, D07, D08, D09) |
| Identical tags: most likely mapped twice | 2 (D12 Alpha Star Christian Preschool, D14 Pakiad Talipapa) |
| Same sub-type, differing tags: verify | 7 |

If confirmed as duplicates, travel times change negligibly (records 4–41 m apart); facility counts
`n_*` over-count by one per pair.

**Unconnected population cells:** `unconnected_cells_review.csv`, `unconnected_by_barangay.csv`,
`unconnected_cells_map.html`, layers `unconnected_cells` and `unconnected_nearest_edge_lines`.
There are 302 cells (3,969 residents; 133 barrier-blocked, 169 beyond 250 m), priority barangays
first. Each row gives the cell id and coordinates; the population (primary, census-adjusted,
original WorldPop 2020 and 2026); the barangay; the nearest walk edge (OSM id, class, name, nodes)
and the snapping distance; the edges within tolerance; the blocking barriers (OSM id, tags, name);
any water feature containing the cell centre; nearby pedestrian edges, bridges and highway classes
within 500 m; the reason; and a suggested investigation.

| Barangay | Cells | Residents not connected | Blocked / beyond |
|---|---|---|---|
| Calahunan | 23 | 1,556 (30.7%) | 5 / 18 |
| Hibao-an Sur | 65 | 1,109 (23.7%) | 20 / 45 |
| Tabuc Suba (La Paz) | 6 | 250 (6.4%) | 1 / 5 |
| Baybay Tanza | 7 | 141 (6.7%) | 0 / 7 |

Cell counts use the barangay holding most of each cell; residents are the fractional figures used
by the indicators. 38 cells have their centre inside a mapped pond/fishpond polygon. In Iloilo,
fishponds are mostly tagged `water=pond`. These cells are flagged as possibly outdated polygons,
to be checked on imagery. The map includes an Esri imagery layer, the walk network (paths vs
roads), water barriers, the rejected line to the nearest edge, and highlighted priority barangays.

## 9. Tests

85 tests pass: the 53 earlier tests, with one assertion updated for the approved denominator change,
plus 32 new tests in `tests/test_m02b.py`. They cover:

- **Configuration:** the 3 km default and 1 km isolation, and the configuration fingerprint.
- **Speeds:** deterministic mixed-class speed.
- **Population:** fractional pieces, census anchoring that keeps the original values, and
  primary-weight validation.
- **Indicators:** piece-weighted indicators with p90, all-resident denominators in barangay and
  city-wide figures, and unconnected external facilities that are never destinations.
- **Car times:** the drive factor scales only the network leg.
- **Reliability:** population and network reliability rules, separate dimensions and the most
  restrictive overall level.
- **Duplicates:** structured duplicate records and the duplicate suggestions.
- **Review files:** reviewer decisions kept on re-run, and the investigation hints.
- **Audit:** FAILs with actions and nothing created on an empty project, the exit code, refusal to
  write into `data/`, stale stage order, and a modified archive.

## 10. Reproduce

```bash
uv run abot build && uv run abot report && uv run abot review          # 3 km baseline (cache)
uv run abot --config config/experiments/hist_buffer_1km.yaml build     # 1 km historical baseline
uv run abot --config config/experiments/hist_buffer_1km.yaml report
uv run abot compare data/processed/hist_buffer_1km data/processed --name e7_buffer_1km_vs_3km_m02b
uv run abot compare data/archive/m01_3edc0dd data/processed --name m01_vs_m02b_baseline
uv run abot compare data/archive/m02_wip_1km_20261031 data/processed/hist_buffer_1km --name m02_vs_m02b_1km_weights_and_denominators
uv run abot audit                                                     # read-only
uv run pytest
```

## 11. Remaining limitations

1. **Manual reviews pending.** The 14 duplicate pairs and the 302 unconnected cells are undecided.
   Until then, Calahunan and Hibao-an Sur indicators describe only 69–76% of their residents.
2. **Census anchoring fixes barangay totals at 2020.** The within-barangay pattern is still WorldPop's
   model, likely biased toward built-up commercial cells. POPCEN 2024 is not yet integrated (the
   file is needed), and the 2026 projection carries no post-2020 barangay information.
3. **27 barangays have ≤ 5 cell centres.** Fractional allocation removes the arbitrary centre-point
   effect on totals, but assumes people are spread evenly within a cell.
4. **No district aggregates** (P2 item 4): no district lookup is available.
5. **Facility inventory unverified:** no DOH NHFR / DepEd / CDRRMO reconciliation. Facility level
   and capacity are not measured; indicators are proximity only.
6. **Car times are uncalibrated free-flow lower bounds.** The sensitivity factors are illustrative.
   There is no public transport.
7. **Boundary:** the legal northern boundary and the origin of 78.34 km² remain unresolved. The
   optional boundary-sensitivity QA against OSM (P4) was not added, because it needs a new OSM
   fetch.
8. **Ported diagnostics are partial.** `abot audit` recomputes the assessment figures that depend on
   project outputs. Those needing external data (GADM, geoBoundaries, the WorldPop 2024 raster, the
   M01 connector re-test against freshly fetched water features) are not re-run, because the audit
   never downloads.
9. **`sens_maxspeed_override` and `e7_buffer_3km` outputs are stale.** They were built with the M02
   code. E7 is superseded by `hist_buffer_1km`; re-run the speed attribution if it is cited.
