# ABOT — Milestone 04 follow-up: approved decisions and implementation

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Implemented in the working tree. **Not committed** (the user commits) |
| **Builds on** | [MILESTONE_04_RESULTS.md](MILESTONE_04_RESULTS.md) (read-only investigation) |
| **Active baseline** | **Unchanged**: largest-component network, osmnx walk filter and routing, 250 m connector, all baseline outputs (SHA-256 checked before and after every run). It is labelled the **A1 optimistic connectivity scenario** |
| **1 km historical run** | Unchanged (`hist_buffer_1km`, audit PASS) |

## 1. What was approved and what was done

| Item | Approved | Done |
|---|---|---|
| A. Overpass | One `fetch-gaps --allow-download` run **by the user** | Not yet run when this was written (no `data/raw/osm_targeted/`). Evidence analysis is ready and runs automatically in `abot components` once a snapshot exists (§2). No request was sent from this session |
| B. A3 reporting layer | As an additional layer; A1 kept as the optimistic scenario; A2 not preferred | `data/processed/component_aware/` (§3) |
| C. Access classification | Analysis and reporting only | Revised classes, per-class quantification, removal impact (§4). Routing unchanged |
| D. `e7_buffer_3km` cleanup | Remove the originals after verification | Verified, 20 originals removed, archive re-verified (§5) |
| E. Duplicate classifications | D01, D02, D07, D08, D09 distinct; D13, D14 likely duplicates; the other 7 pending | Recorded with checks, a log and a restore point (§6) |

## 2. Overpass snapshot (Phase A)

> **Update (later the same day):** the user ran the fetch once. The snapshot
> `m04_gaps_20261031T131445Z.json` (1,117 elements) shows F001 linked to the main network through the
> private, gated Gustilo Street corridor, and F100/F101 through private, gated fishport service
> roads. The links are physically connected in OSM topology, but public pedestrian access is
> restricted according to the mapped tags, and nothing was applied. See
> [MILESTONE_04_SNAPSHOT_REVIEW.md](MILESTONE_04_SNAPSHOT_REVIEW.md). The text below describes the
> state before the run.

- Command: `uv run abot fetch-gaps --allow-download`. It sends the validated M04 query once, to the
  same endpoint (`overpass-api.de`) with the same headers. On success it writes
  `data/raw/osm_targeted/m04_gaps_<UTC>.{json,overpassql,meta.json}` (query, endpoint, request time,
  `timestamp_osm_base`, SHA-256 of query and response) and a `manifest.json` entry. On failure nothing is
  written. The OSM cache is never touched.
- Then `uv run abot components` produces:
  - `review/m04/snapshot_gap_elements.csv`: every tagged way and node, with edit version and time, and whether the walk cache holds it;
  - `snapshot_link_candidates.csv`: chains of ways outside the walk network that touch both a fragment (e.g. F001) and the main network, with their tags. **Never applied**;
  - `snapshot_status.json`.
- **Current status [unverified]:** F001's entrance and the Baybay Tanza links are not established.
  The cache evidence is unchanged: F001's 4 near-contact dead ends are all tagged `noexit=yes`. If the
  request fails, it is documented and not retried; no other headers or servers are used without
  separate approval.

## 3. A3 component-aware reporting layer (Phase B)

Files in `data/processed/component_aware/`: `cells_a3.csv`, `barangay_access_a3.csv` (180
barangays, counts and percentages), `citywide_a3.csv` (A1 vs A3), `component_aware.gpkg`,
`run_info.json`, `README.md`. Rules: [METHODOLOGY.md](METHODOLOGY.md) §3.3.

| Residents [derived] | A1 optimistic (baseline) | A3 component-aware |
|---|---|---|
| Main-network connected | 453,656.9 (99.13%) | **448,855.8 (98.08%)** |
| Locally connected (isolated component) | — | **5,206.0 (1.14%)** |
| Access uncertain | — | **91.9 (0.02%)**: all in Ingore (2.16%), component F062 (Dock Access Road) |
| Unconnected | 3,969.1 (0.87%) | **3,472.3 (0.76%)** |
| Total (all in every denominator) | 457,626 | 457,626 |

Citywide walking share within 15 min (all residents as denominator; A3 = main-network residents only):

| Group | A1 | A3 | Locally connected residents with an **internal** facility ≤ 15 min (not citywide) |
|---|---|---|---|
| Hospital | 22.90% | 22.64% | 100.2 (St. Therese Hospital grounds, F003) |
| Primary care | 66.56% | 66.07% | 0 |
| Pharmacy | 62.74% | 62.17% | 0 |
| Basic education | 88.30% | 87.44% | 3,072.8 (mostly F001 → Santa Clarita Int. School) |
| Higher education | 37.27% | 37.01% | 29.3 |
| Police / fire | 37.82 / 46.11% | 37.59 / 45.87% | 0 |
| Public market / supermarket | 39.45 / 48.00% | 39.29 / 47.67% | 0 |
| Bank | 53.11% | 52.74% | 0 |

Mean times change by at most 0.06 min. Barangays: 34 have locally connected residents, and 9 have
≥ 5%. The largest local shares are Tabuc Suba (La Paz) 43.5%, San Agustin 29.2%, Baybay Tanza
26.8%, Alalasan Lapuz 15.6%, Santa Rosa 15.0% and Ticud 14.5%. Calahunan and Hibao-an Sur are included
in the totals and flagged `resolved_separately` (Calahunan 1.35% locally connected; not investigated).

**Interpretation.** For Tabuc Suba's F001 residents, A3 is conservative: they must have some way out,
but it is not in the data. A1 is optimistic: it routes them through a straight line to points mapped as
dead ends. Neither is observed travel.

## 4. Access classification (Phase C): analysis and reporting only

> **Superseded labels (2026-10-31, M04 methodology review).** The access labels in this section (`ineligible`, `resident_restricted`, `private_uncertain`, `uncertain`) were replaced by `no`, `private`, `residents`, `customers`, `unknown`, `destination`, `pedestrian_override`, `untagged`, `public`, with separate public-pedestrian and authorised-group fields. The road class no longer decides residents, and `access=private` names no group. Counts below are kept as recorded; numbers, component classes and A3 are unchanged. See [MILESTONE_04_ACCESS_TAXONOMY.md](MILESTONE_04_ACCESS_TAXONOMY.md).

Classes and treatments are in [METHODOLOGY.md](METHODOLOGY.md) §3.1, which also defines physical
traversability, public access and resident-restricted access. Changes from the M04 draft:
`foot=private` is now **ineligible** for general public walking; `access=private` is
**resident-restricted** on residential, service and living streets and **uncertain** elsewhere; private
gate nodes are **flagged for review**; untagged gates are not excluded.

**Counts** (`review/m04/access_classification_summary.csv`; "attached" = the cell's active A1
connection edge carries the class):

| Class | Ways | Edges | km (main) | Components | Cells / residents attached |
|---|---|---|---|---|---|
| ineligible | 52 | 66 | 7.64 (6.11) | 12 | 20 / 346.5 |
| resident_restricted, private_uncertain (ways) | 0 | 0 | 0 | 0 | 0 (osmnx drops these before download) |
| customers | 10 | 18 | 0.86 (0.86) | 1 | 2 / 150.8 |
| uncertain | 4 | 3 | 0.65 (0.02) | 2 | 0 |
| destination | 182 | 309 | 22.95 (22.32) | 3 | 144 / 6,991.9 |
| untagged | 10,245 | 19,144 | 1,361.57 (1,323.94) | 89 | 7,390 / 441,178.3 |
| public | 249 | 386 | 31.06 (30.86) | 3 | 177 / 4,989.4 |

| Gate nodes | Nodes (main) | Flagged | Cells / residents on a gated connection edge |
|---|---|---|---|
| ineligible (`access=no`, `foot=no`/`private`) | 35 (35) | 35 | 26 / 497.0 |
| private (uncertain: review) | 167 (164) | 167 | 90 / 3,807.6 |
| untagged (not excluded) | 275 (261) | 0 | 165 / 8,508.4 |
| destination / customers / uncertain / public | 30 / 6 / 2 / 188 | 0 | — |

**Removal impact** (`access_impact.csv`, not applied): residents who would lose their main-network
connection are 12.6 (`access=no`), 0 (`foot=private`), 61.7 (private gates), 204.1 (ineligible gates),
1,819.4 (untagged gates) and **218.3** (all ineligible plus private). Citywide ≤ 15 min shares move by at
most 0.75 pp. **The active routing still follows the osmnx filter and routes through all gates.**

## 5. `e7_buffer_3km` cleanup (Phase D)

1. `archive.verify`: 21 archived files and all originals matched their SHA-256 records (0 mismatches, no extra files).
2. `archive.remove_verified_originals` re-checked everything and refused on any mismatch or unrecorded file. It removed **20 originals**: `interim/e7_buffer_3km` (9), `processed/e7_buffer_3km` (7) and `comparisons/e7_buffer_1km_vs_3km` (4).
3. **Kept:** `config/experiments/e7_buffer_3km.yaml` (also in the archive), the current `comparisons/e7_buffer_1km_vs_3km_m02b`, and the archive with its provenance. The record now has `originals_kept: false` and lists the removed files and the verification result.
4. **Dependencies checked:** no code or configuration reads the originals. The only mentions are the run name in the shared cache's `used_by_runs` and historical milestone documents, which are left as written.
5. **After removal:** an independent `sha256sum -c` gave 21 OK / 0 failed. `abot audit` reports `hist_e7_buffer_3km_m02: 21 files match`, and the `experiment: e7_buffer_3km` WARN is gone.

**One deviation to note.** A further `sha256sum` pre-check, meant to run just before removal, was
launched in parallel with the removal and failed on a temporary-path error, so it did not run first.
The removal function's own hash check of all 21 archived files and 20 originals (0 mismatches) and the
earlier independent `sha256sum` (21/21) did run before deletion. The post-removal check passed.

## 6. Duplicate classifications (Phase E)

`review.record_duplicate_decisions` checks that each row exists, names exactly the approved OSM
records and is still `pending`; if any check fails, nothing is written. It then writes only the three
reviewer columns and appends to `review/review_decisions_log.csv`: UTC time, approval, rationale,
values before and after, and the full original row with coordinates and OSM tags.
`review.revert_duplicate_decision` restores a decision exactly. A byte-exact restore point is in
`data/archive/review_pre_m04_decisions/` (SHA-256 recorded and audited).

| Pair | OSM records (verified) | Recorded |
|---|---|---|
| D01 | node/3045671209 bank + node/625522918 ATM | `distinct_keep_both` |
| D02 | node/13120970446 bank + node/625522918 ATM | `distinct_keep_both` |
| D07 | node/4540496890 bank + node/4492520789 ATM | `distinct_keep_both` |
| D08 | way/70507036 bank + node/4492521189 ATM | `distinct_keep_both` |
| D09 | node/4956389421 ATM + node/4956389324 bank | `distinct_keep_both` |
| D13 | way/1323158946 + way/308681988 (DBP) | `likely_duplicate_not_merged` |
| D14 | way/810694465 + way/810694464 (Pakiad Talipapa) | `likely_duplicate_not_merged` |
| D03, D04, D05, D06, D10, D11, D12 | — | **pending** |

`likely_duplicate_not_merged` is a new documented value. The approval classified D13 and D14 as
likely duplicates but did not choose a record to keep, so nothing is merged, deleted or re-counted. No
pipeline stage reads these files. All other columns of the review file are cell-for-cell identical
to the restore point, and the other two review CSVs are byte-identical to before.

**Safeguard added (`review._keep_reviewer_columns`).** Duplicate ids (D01, …) are positional. Before
this change, an OSM update that added a pair could have moved a recorded decision onto a different
pair when `abot review` re-ran. A decision is now carried over only while the same two OSM records
form the pair; otherwise the row returns to pending and a warning is logged. This is data integrity,
not methodology.

## 7. Unchanged assumptions

Largest-component routing; osmnx walk filter (including routing through all gates and over
`access=no` ways); 250 m origin connector (1,407 residents still unconnected at 500 m, reported as a
sensitivity only); 500 m facility connector; 4.5 km/h; census-anchored weights; no link between
components; F001 not connected; drive indicators; all facility counts.

## 8. Tests, audit, reproducibility

| Check | Result |
|---|---|
| `pytest` | **159 passed** (138 + 21 new) |
| `ruff check` | clean |
| `abot audit` | **PASS 57, WARN 3, FAIL 0, INFO 11** ([MILESTONE_04_FOLLOWUP_AUDIT.md](MILESTONE_04_FOLLOWUP_AUDIT.md)). New PASS: `component_aware_layer_current`, `review_pre_m04_decisions`; cleared: `experiment: e7_buffer_3km`. Remaining WARNs: Guimaras facilities, priority barangays not connected, 7 duplicates pending |
| Determinism | `abot components` under `PYTHONHASHSEED` 0 and 12345: all 17 `review/m04` files and the A3 CSVs and README are byte-identical. The A3 GeoPackage layers are identical in content (the GeoPackage file embeds a write time), and `run_info.json` differs only in `created_utc` |
| A1 preserved | A1 reproduces the saved baseline on every run; baseline file hashes are equal before and after (`run_info.json`, and a test) |

New tests (`tests/test_m04.py`): A3 population accounting across all four categories and the
all-residents denominator; local vs citywide times in separate columns; internal facilities in an
isolated component; A1 vs A3 side by side; A1 labelled optimistic; baseline preserved and hash change
detected; revised access classes and pedestrian overrides; the classification summary; snapshot link
candidates (both sides required, never applied); decision recording, refusal, all-or-nothing writes,
exact revert, and no carry-over to a different pair; archive cleanup (config kept, refusal on a changed
original, a changed archive or unrecorded files).

## 9. Unresolved decisions

1. ~~**Overpass:** run `uv run abot fetch-gaps --allow-download` once.~~ Done; see [MILESTONE_04_SNAPSHOT_REVIEW.md](MILESTONE_04_SNAPSHOT_REVIEW.md) §6 for the decisions it raises.
2. **Duplicates D03, D04, D05, D06, D10, D11, D12:** street-level, imagery or registry evidence needed (D10: a working BPI branch list).
3. **D13 / D14:** if they are ever to be merged, which record to keep (suggested: D13 the site polygon `way/308681988`).
4. **Methodology (separate approval needed, not proposed for adoption here):** whether to make A3 the headline walking indicator, and whether to change routing for `access=no` ways and private or ineligible gates.
5. F001 entrance and Baybay Tanza links: site or imagery verification, depending on item 1.
