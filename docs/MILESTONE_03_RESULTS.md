# ABOT — Milestone 03: manual spatial validation and analytical finalization

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Implemented in the working tree. **Not committed** (the user reviews and commits). |
| **Builds on** | Milestone 02B (commit `3e85764`): 3 km baseline, 85 tests, audit PASS 50 / WARN 3 / FAIL 0 / INFO 11 |
| **Applied decisions** | **None.** No facility was merged or excluded, no cell or facility was connected, and every `review_status` is still `pending`. The three review CSVs are byte-identical before and after this milestone (SHA-256 checked). |
| **Downloads** | None. Every OSM read came from `data/raw/osm_cache/`. The new command refuses HTTP requests, and the runs also had an unreachable proxy set. Imagery was **not** inspected; the maps carry an Esri imagery layer for the reviewer. |
| **Archives** | `m01_3edc0dd` and `m02_wip_1km_20261031` are unchanged (SHA-256 verified). New: `stale_sens_maxspeed_override_m02_1km` (see §5). |

## 1. Summary

| Review item | Desk finding | Still needs |
|---|---|---|
| 14 duplicate pairs | 2 the same facility (desk evidence), 5 distinct (bank vs ATM), 6 likely duplicates, 1 uncertain | Your decision on all 14; verification for 7 |
| 302 unconnected cells (3,969 residents, 28 barangays) | 40 cells (528 residents) lie next to mapped ways that OSM does not link to the main network. 121 cells (2,537) have no mapped way of any kind within 250 m: 2,326 of these residents are one cluster in Calahunan and Hibao-an Sur. 94 cells (832) are cut off by a mapped creek or river. 47 cells (72) have their centre in mapped water | Imagery and local verification; nothing was connected |
| 38 cells in mapped ponds | 53 residents in 30 polygons, 8 barangays, none a priority barangay. No mapped walkway crosses any of these polygons, so the OSM data does not contradict them; polygon ids suggest they were first mapped around 2018 | Imagery check (low priority: 1.3% of the unconnected residents) |
| 13 disconnected external facilities | All 13 are on **Guimaras** (Jordan and Buenavista), on local road networks with no land link to Iloilo. They are separated by the Iloilo Strait. Their coordinates and classes are plausible | No action; they stay excluded |
| Stale `sens_maxspeed_override` | Moved to an archive with hashes, rebuilt on the current 3 km baseline and code, comparison regenerated. Reproducible across hash seeds | — |
| Final audit | PASS 54, WARN 4, FAIL 0, INFO 11. All 4 WARNs are legitimate open items, not defects | Decisions in §7 |

**New finding (not in the original review list).** The walk network keeps only the largest connected
piece of the OSM network. The dropped pieces are 111 fragments, 39.5 km of ways (QA counts this as
79 km, both directions). One of them, **F001**, is a 10.4 km residential subdivision in Tabuc Suba
(La Paz) (Puerto Del Mar, Pasacao St, Puerto Princesa St, …). Only a **10.9 m gap** that crosses no
water separates it from the main network. Besides the 6 unconnected Tabuc Suba cells, **160
*connected* cells (4,812 residents, 1.05%)** have an unlinked fragment as their nearest mapped way.
They were attached instead to a farther main-network edge by a straight connector (median 104 m),
2,134 of them inside F001. Their travel times rest on that approximation. This is how the method is
designed to work, not a code defect, but it is a validity caveat that needs your decision (§7, item 2).

## 2. New tool: `abot validate` (read-only)

`src/abot/validation.py` builds the evidence below from the run's outputs, the review files and the
Overpass cache. It writes only to `data/processed/review/m03/`:

| File | Contents |
|---|---|
| `duplicates_assessment.csv` | Per pair: polygon overlap (way/way), OSM-id gap, tag identity, sub-type relation, desk assessment and reason, verification needed, effect if merged. Reviewer columns copied unchanged (`pending`) |
| `unconnected_cells_diagnostics.csv` | Per cell: everything in the review file, plus the nearest unlinked fragment (via a barrier-checked connector), the fragment's gap to the main network, the share of the cell footprint in water, the smallest connector tolerance (300/400/500 m) at which it would connect, the diagnostic class, the verification needed and a decision rank |
| `unconnected_diagnostics_by_barangay.csv` | Residents per barangay and diagnostic class |
| `network_fragments.csv` | Fragments next to unconnected cells or facilities: length, highway types, names, OSM way ids, gap line endpoints, water crossed by the gap, whether the extraction boundary cuts the fragment |
| `pond_polygons.csv` | Pond polygons holding an unconnected cell centre: area, residents, mean water share, mapped ways inside |
| `disconnected_facilities_diagnostics.csv` | Per unconnected facility: fragment, gap to the main network, coastline crossings, whether it would be a destination, distance to the city and to the extraction edge, diagnosis |
| `connected_cells_nearer_to_fragment.csv` | The 160 connected cells described in §1 |
| `connector_tolerance_sensitivity.csv` | §3.4 |
| `validation.gpkg`, **`validation_map.html`** | All of the above as layers over OpenStreetMap and Esri imagery: cells by diagnostic class, fragments and gap lines, pond polygons, Guimaras facilities, duplicate pairs coloured by assessment |

Consistency check: the main component rebuilt from the cache is node-for-node identical to the
saved walk graph (14,918 nodes), so the fragments are exactly what the build dropped.

## 3. Phase 1 — Duplicate facility review

Method: compare tags, sub-types and coordinates (as before), then add the polygon footprints from
the cached facility response, the OSM-id gap and the effect on counts. The desk assessment follows
explicit rules (`validation.assess_duplicate`, tested). A merge would move a destination by at
most 41 m, so travel times are essentially unaffected. The real effect is on facility counts `n_*`.

### Confirmed duplicates (desk evidence sufficient that it is one facility)

| Pair | Records | Evidence | Effect if merged |
|---|---|---|---|
| D13 | DBP, `way/1323158946` (building) / `way/308681988` (site) | The 599 m² building lies **100% inside** the 1,466 m² site polygon: one bank, outlined twice. The site record is more complete (address, branch, `atm=yes`) | `n_finance`, `n_finance_bank` −1 in Muelle Loney-Montes |
| D14 | Pakiad Talipapa, `way/810694465` / `way/810694464` | Identical tags; **consecutive OSM ids** (one upload); two hut structures 16.5 m apart: one market of two sheds | Outside the city: no count changes; destination moves ≤ 23 m |

### Distinct facilities (separate service at the same site)

D01, D02 (PNB San Felix: bank and ATM), D07 (PSBank: bank and ATM), D08 (PNB Danao: bank building
and an ATM 1.9 m outside it), D09 (UnionBank: ATM and bank). An ATM is `descriptive` and never a
destination. It is counted in `n_finance` only, so keeping both changes no indicator.

### Uncertain cases

| Pair | Lean | Why uncertain | Verification |
|---|---|---|---|
| D03 | likely duplicate | Two PNB **bank** nodes 9 m apart (plus the ATM of D01/D02). `node/13120970446` is recent and has fewer tags; `node/3045671209` has the address and `atm=yes` | Street-level: one PNB branch on General Luna St or two? |
| D04, D05 | likely duplicate | Metrobank and BPI each have an older node (Laguda) and a newer node about 19–20 m north (Rizal (La Paz)). The two new nodes were added together (ids 10789081660 / 10789117777) and shifted the same way. This looks like one mapper re-placing both branches, not two new branches. The records sit on a barangay boundary, so the record you keep decides which barangay is counted | Imagery or street level: which position is the building? |
| D06 | likely duplicate | Ledi Supermart, 5.5 m apart, differs only in `addr:street` | Street-level |
| D11 | likely duplicate | TGP pharmacy, 5 m apart, differs only in `check_date` (2026-07-02). Straddles Katilingban / Poblacion Molo | Street-level; keep the checked record? |
| D12 | likely duplicate | Alpha Star Christian Preschool, identical minimal tags, 16 m apart. The ids are not consecutive (gap 333,500), so they were mapped separately | Imagery or school list |
| D10 | uncertain | BPI 41 m apart in Buhang Taft North. One record is the "Megaworld" branch on Festive Walk Rd with opening hours; the other was checked 2025-12-03. Two branches in the business district are plausible | BPI branch list (external) |

If all 6 likely duplicates and D10 were merged, `n_finance_bank` would fall by up to 4 (D03, D04,
D05, D10), and `n_market_supermarket`, `n_pharmacy` and `n_education_basic` by 1 each. Travel times
would change only by the ≤ 41 m shift of the remaining record.

## 4. Phase 2 — Unconnected population review

302 cells, 3,968.8 residents (0.87%), 28 barangays. Diagnostic classes are mutually exclusive and
applied in this order:

| Class | Cells | Residents | Barangays | Meaning |
|---|---|---|---|---|
| `osm_fragment_not_linked` | 40 | 527.6 | 6 | A mapped way lies within 250 m by a barrier-free connector, but OSM does not link it to the main network |
| `centre_in_pond_polygon` | 34 | 50.3 | 6 | Cell centre in a mapped pond/fishpond (4 more pond cells are in the class above) |
| `centre_in_river_or_sea` | 13 | 21.8 | 3 | Cell centre in a mapped river polygon (Iloilo River, Calajunan Creek) |
| `blocked_by_watercourse` | 94 | 831.7 | 22 | Every edge within 250 m lies across a creek or river: Calajunan Creek 291, Tigum River 155, Batiano River 84, Jaro River 33 |
| `no_mapped_way_within_tolerance` | 121 | 2,537.4 | 13 | No walkable way, linked or not, within 250 m |

178 of the 302 cells hold fewer than 5 residents each (302 residents in total). Many of these are
probably WorldPop spill-over at settlement edges.

### 4.1 Priority barangays

| Barangay | Residents not connected | Finding |
|---|---|---|
| **Calahunan** (1,556; 30.7%) and **Hibao-an Sur** (1,109; 23.7%) | Diagnostics count 1,460 + 1,206 by the barangay holding most of each cell | **One contiguous cluster** (lon 122.516–122.528, lat 10.720–10.741, 86 cells, 2,614 residents). 2,326 residents have **no mapped way of any kind** within 250 m (nearest 250–490 m; median cell 16 residents, 17 cells ≥ 50). Another 288 are cut off by **Calajunan Creek** (`way/187759379`, no mapped crossing). There are no pond polygons here and no fragment except a 30 m stub across the creek (F060, 51 residents). WorldPop's barangay totals agree with the census here (anchoring factors 0.97 and 0.92), so this is not a scaling artefact. The open question is whether the dwellings are where WorldPop puts them, and whether there are unmapped lanes. The city's sanitary landfill (Calajunan) is in this barangay, so the reviewer should check whether part of the cluster coincides with it. **This cannot be decided from mapped data.** |
| **Tabuc Suba (La Paz)** (250; 6.4%) | All 6 cells: `osm_fragment_not_linked` → F001 | The cells are next to the subdivision streets of F001. F001's gap to the main network is 10.9 m (lon/lat 122.57463, 10.72756 → 122.57455, 10.72762) and crosses no water. That pattern fits a gated entrance mapped with `access=private` or as a gate-only connection: the osmnx walk filter excludes `access=private` ways. **Hypothesis, unverified**: the cached responses contain only ways that passed the filter, so they cannot show what fills the gap |
| **Baybay Tanza** (141; 6.7%) | All 7 cells: `osm_fragment_not_linked` → F100 (98) and F101 (43) | Two short, recently mapped coastal ways (ids ≈ 1.536 × 10⁹; a pedestrian way and service ways). They are 183 m and 245 m from Iloilo Fishport Access Road and Rizal Pala-pala Seaside Lane, with no water in between. The joining paths are probably not mapped |

### 4.1a Reviewer imagery check: Calahunan / Hibao-an Sur cluster (2026-10-31)

The user inspected the cluster centre (10.7243 N, 122.5221 E) in Google Earth Pro on two dates:
Maxar imagery of 2020-05-15 and Airbus imagery of 2026-07-22.

- **Observed:** established residential subdivisions with a complete paved street grid
  (Monterosa Estate with its clubhouse and roundabout, Anaros Village and surrounding blocks). They
  are already densely built in 2020 and denser in 2026.
- **Landfill hypothesis: ruled out** for this cluster.
- **Population placement: consistent with imagery.** Houses are visible where WorldPop 2020 places
  residents, so `no_dwellings_visible` is unlikely.
- **Network:** the walk network has no edge within 250–490 m of the cluster cells, although streets
  are visible on the imagery, and no cached OSM response contains the names "Monterosa" or "Anaros".
  The not-connected status of these residents is therefore a **network-data artefact**, not an
  absence of access. The Calahunan (30.7%) and Hibao-an Sur (23.7%) not-connected shares overstate
  the real situation.
- **Still open:** whether the streets are absent from OSM or present but excluded by the osmnx walk
  filter (for example `access=private` on a gated subdivision). The cache cannot distinguish the two,
  because excluded ways are never downloaded. This needs a check on openstreetmap.org or an approved
  Overpass query (decision 2).
- **Not applied:** no cell was connected, and no reviewer column was filled by the tool. The user
  records decisions per cell (likely `missing_osm_path`).

### 4.2 Ponds (the 38 cells inside mapped ponds)

- 38 cells, 53.2 residents, 30 `water=pond` polygons, 8 barangays (So-oc, Navais, Ingore,
  Hinactacan, Airport, Loboc-Lapuz, Santo Domingo, Tacas). None is a priority barangay.
- The cell footprint is 21–98% water (median about 0.7). Population per cell: 0.0–8.8.
- **Internal consistency:** no mapped walkable way runs through any of the 30 polygons, so the OSM data
  does not contradict them. Absence of a contradiction is not confirmation.
- **Age:** 26 of the 30 polygons have ids between 595 M and 601 M, consistent with one mapping
  effort around 2018 (ids indicate when a way was created, not when it was last edited). WorldPop's settlement
  layer is newer. The likely reading is a few caretaker huts on dikes or model spill-over, not
  outdated ponds, but only imagery can tell.
- **Potentially outdated barrier geometries:** 0 shown by mapped data; 30 polygons unverified
  (`pond_polygons.csv` + the imagery layer). Resolving all of them changes at most 53 residents.

### 4.3 Connector-tolerance sensitivity (not applied)

| Max connector | Extra cells connected | Extra residents | Still not connected |
|---|---|---|---|
| 250 m (current) | — | — | 3,968.8 |
| 300 m | 78 | 1,133.6 | 2,835.2 |
| 400 m | 130 | 2,046.9 | 1,921.9 |
| 500 m | 146 | 2,562.0 | 1,406.8 |

Tested on the main network with the same barrier rules. The not-connected count depends strongly on
the tolerance, because most of these cells lie 250–400 m from a mapped way. Raising the tolerance
would not supply evidence that a path exists. It would only accept a longer straight line, so it is
reported as a sensitivity and nothing was changed.

### 4.4 Extraction boundary

Not a factor for the cells. Every population cell is inside the city, at least 3 km from the edge of
the OSM extraction, and the main component matches the saved graph. The relevant network limit is
the largest-component filter (§1), not the buffer.

## 5. Phase 3 — Disconnected external facilities

| Question | Answer |
|---|---|
| Genuinely isolated? | **Yes, from Iloilo City by land.** All 13 sit on Guimaras road networks (fragment F004, Jordan, 3.8 km; fragment F002, Buenavista, 11.0 km), within 0–125 m of a local way |
| Separated by a barrier? | **Yes: the Iloilo Strait.** The shortest gaps to the main network are 2.37 km (F004) and 1.82 km (F002), and they cross the mapped Guimaras coastline |
| Wrong coordinates or classes? | **No evidence.** No point lies in a water area. The names fit their places (Jordan Wharf, Jordan RORO Port, Buenavista Wharf, Jordan Public Market, Zaldivar / Dagsa-an Elementary School, …). They are 1.7–2.9 km from the city |
| Insufficient extraction? | **Partly, but it does not matter.** F002 is cut by the 3 km extraction boundary. A larger buffer would add more Guimaras roads but no land link: crossing the strait means a ferry or pumpboat, which is public transport and out of scope |
| Would they be destinations? | 6 of 13 would be (Landbank Buenavista, 4 public schools, Jordan Public Market). The other 7 are descriptive (wharves, barangay halls, remittance, ATM) |

**Recommendation:** keep all 13 excluded. The audit WARN `pipeline_qa_warnings
(accessibility.facilities_connected / _not_connected)` is this finding, and it is a legitimate
limitation.

## 6. Phase 4 — Sensitivity output consistency (`sens_maxspeed_override`)

**What was stale:** the run was built at 15:30–15:52 with the 1 km buffer and the Milestone 02
code. It used connected-only denominators (its `pct_le60` was 100%) and predates the mixed-class
speed fix. Its comparison mixed those definitions with the 02B baseline.

**What was done:**
1. Moved, not deleted: `data/interim/sens_maxspeed_override/`, `data/processed/sens_maxspeed_override/` and
   `data/processed/comparisons/speed_override_vs_cap/` now live in
   `data/archive/stale_sens_maxspeed_override_m02_1km/` (18 files, SHA-256 record verified by `abot audit`).
2. Rebuilt with `abot --config config/experiments/sens_maxspeed_override.yaml build` and `report`
   (3 km, current code; 4 of 4 Overpass responses were cache hits). Regenerated with
   `abot compare data/processed/sens_maxspeed_override data/processed --name speed_override_vs_cap`.
3. **Assumption documented and tested:** the experiment differs from the baseline *only* in
   `accessibility.maxspeed_policy: override` (plus `run_name`). `test_maxspeed_sensitivity_differs_from_baseline_only_in_speed_policy`.
4. **Reproducible:** a second build with `PYTHONHASHSEED=12345` (the first used 0), into a temporary
   run folder, gave byte-identical `barangay_access.csv`, `barangay_population.csv`, `facilities.csv`,
   `facility_exclusions.csv`, `facility_inventory.csv`, `drive_speed_sensitivity.csv` and an identical
   `access_cells` layer. The temporary folders were then removed, and their run label was taken out
   of `data/raw/manifest.json`'s `used_by_runs`.

**Result** (override = M01 rule, where a tagged maxspeed replaces the class speed; cap = baseline):

| Car (modelled uncongested) | Override mean | Cap mean | Override ≤ 10 min | Cap ≤ 10 min | Stale M02 1 km, override → cap ≤ 10 min |
|---|---|---|---|---|---|
| health_hospital | 6.38 | 7.61 | 92.0% | 79.6% | 93.1% → 81.7% |
| education_higher | 5.84 | 6.96 | 95.3% | 81.9% | 96.1% → 83.5% |
| market_public | 4.99 | 5.85 | 97.1% | 91.9% | 97.7% → 92.5% |
| safety_police | 4.73 | 5.58 | 97.7% | 95.7% | 98.4% → 96.3% |
| finance_bank | 3.88 | 4.58 | 98.1% | 97.1% | 98.8% → 97.7% |

- Walk results are **identical** in the two runs, as they must be: the speed policy affects only
  driving.
- **No cell is faster under the cap.** Barangay ρ ≥ 0.979; 15–19 of the 20 worst barangays are the
  same. The speed-policy effect on "hospital ≤ 10 min" is 12.4 percentage points, against 11.4 in
  the stale run. The stale shares were of connected residents only.

## 7. Prioritized decisions for you

Ranked by residents affected and by whether the evidence is ready.

| # | Decision | Affects | Evidence ready? | Recommendation |
|---|---|---|---|---|
| 1 | **Calahunan / Hibao-an Sur cluster:** imagery check done (§4.1a): paved subdivisions, populated since at least 2020, not a landfill. Remaining question: are the streets missing from OSM or excluded by the walk filter? | 2,614 residents; two `rel_network = low` barangays | Imagery: yes. OSM status: **no** (same check as item 2) | Record `reviewer_decision` per cell (likely `missing_osm_path`). Resolve together with item 2, because one cause may explain both. Do not connect cells until the cause is known |
| 2 | **Unlinked fragment F001 (Tabuc Suba subdivision)** and the network-filter rule | 250 unconnected + 2,134 connected-by-approximation residents (4,812 citywide across all fragments) | Gap located (10.9 m). **The cause is not knowable from the cache** | Approve a *small* new Overpass query (all `highway=*` ways within about 50 m of the F001 gap and the Baybay Tanza gaps, including `access=private` and construction) to see what fills them. Separately decide the method question: should private-access subdivision ways count as walkable for residents? |
| 3 | **Duplicates D13, D14** (desk-confirmed) | `n_finance_bank` −1 (Muelle Loney-Montes); D14 none | Yes | Set `reviewer_decision = same_keep_related` for D13 (keep the site polygon `way/308681988`, which has the address and branch) and `same_keep_flagged` or `same_keep_related` for D14 (either one) |
| 4 | **Baybay Tanza F100 / F101** | 141 residents | Partly | Imagery or local check for paths between the coastal ways and the Fishport road; this is covered by the query in item 2 |
| 5 | **Calajunan Creek crossings** (blocked cells) and F060 stub | 288 + 51 residents (part of item 1) | No | Local check for footbridges; `missing_osm_bridge` vs `real_barrier` |
| 6 | **Likely duplicates D03, D04, D05, D06, D11, D12; uncertain D10** | Up to 4 bank + 3 other facility counts; D04/D05/D11 decide which barangay is counted | Partly | Street-level or imagery check. For D10, the BPI branch list |
| 7 | **Distinct pairs D01, D02, D07, D08, D09** | none | Yes | Confirm `distinct_keep_both` |
| 8 | **`e7_buffer_3km` outputs** (Milestone 02 code, superseded) | none (not cited) | Yes | Archive them the same way as the speed run (move + SHA-256), so the audit WARN clears. Not done, because it was outside this milestone's scope |
| 9 | **Connector tolerance** (250 m) | 1,134–2,562 residents (§4.3) | Yes | Keep 250 m, and report §4.3 as a sensitivity in the paper |
| 10 | **Pond cells** | 53 residents | Desk only | Low priority; optional imagery check |
| 11 | **Guimaras facilities** | none | Yes | Keep excluded (no action) |

## 8. Phase 5 — Final analytical audit

| Check | Result |
|---|---|
| Tests | **103 passed** (85 earlier + 18 new in `tests/test_m03.py`), offline, about 7 s. `ruff check` clean |
| `abot audit` (3 km baseline) | **PASS 54, WARN 4, FAIL 0, INFO 11**. Full output: [MILESTONE_03_AUDIT.md](MILESTONE_03_AUDIT.md) |
| `abot audit`, `hist_buffer_1km` / `sens_maxspeed_override` configs | PASS 47 / 45, WARN 3 / 4, **FAIL 0** / 0 (`--skip-hashes`). Their WARNs are the same open review items; the experiment runs have no review files of their own |
| Archive integrity | `m01_3edc0dd` 11 files, `m02_wip_1km_20261031` 15 files and `stale_sens_maxspeed_override_m02_1km` 18 files all match their SHA-256 records |
| Output freshness | All baseline stages built with the current configuration, in order. Review files and `review/m03` are newer than the last accessibility build. **New check:** every `config/experiments/*` run is tested against its own configuration fingerprint and the code dates |
| Reproducibility | Byte-identical rebuild under a different `PYTHONHASHSEED` (§6). The rebuilt walk component equals the saved graph |
| Review files untouched | SHA-256 of the three review CSVs identical before and after |

**The 4 WARNs:**

| WARN | Verdict |
|---|---|
| `experiment: e7_buffer_3km` has no `run_meta.json` (built with Milestone 02 code) | **Legitimate stale output**, made visible by the new check. Housekeeping, not a pipeline defect (decision 8) |
| `pipeline_qa_warnings`: facilities not connected | **Legitimate limitation**: the 13 Guimaras facilities (§5) |
| `priority_barangays_not_connected` | **Legitimate unresolved limitation**, pending decisions 1, 2, 4 |
| `possible_duplicates` 14 pending | **Legitimate**, pending decisions 3, 6, 7 |

**Defects found in this milestone:** one gap in the tooling. `abot audit` did not check experiment
runs, which is how the stale speed outputs went unnoticed. Fixed by `check_experiment_runs`. No
analytical defect was found. The fragment issue in §1 is a limitation of the network model and the
OSM data, and it is documented, not changed.

## 9. Changes in this milestone

| File | Change |
|---|---|
| `src/abot/validation.py` (new) | `abot validate`: desk evidence for the review items (read-only, offline) |
| `src/abot/cli.py` | `validate` command |
| `src/abot/audit.py` | `validation_files_current` and `experiment: <run>` freshness checks |
| `tests/test_m03.py` (new) | 18 tests: duplicate rules and merge effects, cell classes, tolerance sensitivity, fragment ids, the offline guard, sensitivity-config isolation, experiment staleness |
| `data/archive/stale_sens_maxspeed_override_m02_1km/` (+ `.sha256.json`) | Stale run outputs moved here |
| `data/{interim,processed}/sens_maxspeed_override/`, `comparisons/speed_override_vs_cap/` | Regenerated |
| `data/processed/review/m03/` | New evidence files and map |
| `data/raw/manifest.json` | `used_by_runs` updated by the rebuild; the temporary repro label removed |
| Docs | This file, `MILESTONE_03_AUDIT.md`, `Documentation.md`, `METHODOLOGY.md`, `DATA_SOURCES.md` |

No pipeline stage (boundaries, population, osm, accessibility, report, review) was changed. Baseline
outputs and indicators are unchanged.

## 10. Reproduce

```bash
uv run abot --config config/experiments/sens_maxspeed_override.yaml build
uv run abot --config config/experiments/sens_maxspeed_override.yaml report
uv run abot compare data/processed/sens_maxspeed_override data/processed --name speed_override_vs_cap
uv run abot validate          # reads the Overpass cache only; writes data/processed/review/m03/
uv run abot audit --output docs/MILESTONE_03_AUDIT.md
uv run pytest
```
