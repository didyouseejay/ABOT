# ABOT — Milestone 04: network connectivity refinement and manual validation

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Read-only investigation done in the working tree. **Not committed** (the user commits). **Paused for decisions** (§13) before any method or baseline change |
| **Builds on** | Milestone 03 (commit `8b464a4`): 103 tests, audit PASS 54 / WARN 4 / FAIL 0 / INFO 11 |
| **Applied decisions** | **None.** The active network, the largest-component policy, access defaults, the 250 m connector and every review decision are unchanged. The three review CSVs are byte-identical before and after (SHA-256 checked) |
| **Downloads** | One approved Overpass request: **failed** (the server closed the connection; nothing saved, cache untouched). One approved BPI branch-directory lookup: **HTTP 404**, inconclusive |
| **Follow-up** | Approved decisions implemented afterwards: see [MILESTONE_04_FOLLOWUP_RESULTS.md](MILESTONE_04_FOLLOWUP_RESULTS.md) (A3 reporting layer, revised access classes, `e7_buffer_3km` cleanup, 7 duplicate classifications recorded) |
| **Excluded** | Calahunan and Hibao-an Sur, resolved separately. They are kept in citywide totals and left out of every M04 barangay table and finding |

Labels used below: **[observed]** = in the OSM data or the census; **[assumption]** = a model rule;
**[derived]** = a computed indicator; **[verified]** = checked manually; **[unverified]** = open.
Every travel time is a *modelled* walking time on mapped ways at 4.5 km/h. None is an observed trip.

## 1. Scope and objectives

1. Find out why the walk network is broken at Tabuc Suba (fragment F001) and Baybay Tanza (F100, F101) (Phase A).
2. Inventory every connected component and compare three ways of using them (Phase B).
3. Measure how OSM access tags and gate nodes affect the current network before any policy is chosen (Phase C).
4. Summarise the 14 duplicate pairs for the reviewer, applying none of them (Phase D).
5. Archive the superseded `e7_buffer_3km` outputs with verified hashes (Phase E).
6. Rebuild, run sensitivity analysis and audit. Only the audit and the reproducibility checks were run, because no change was approved (Phases F and G).

## 2. Baseline configuration (unchanged)

3 km OSM extraction buffer (historical 1 km run kept in `hist_buffer_1km`); osmnx `walk` filter;
**largest weakly connected component only**; 100 m WorldPop cells, census-anchored to PSA 2020 (457,626
residents); 250 m water-aware origin connector (facilities 500 m); unconnected residents kept in every
denominator. Baseline walk network: 14,918 nodes, 1,371.2 km of ways. 7,733 of 8,035 cells are
connected (453,656.9 residents); 302 cells (3,969.1 residents) are not.

## 3. Overpass investigation (Phase A)

**Query.** `abot fetch-gaps` builds and validates the query (`src/abot/fetch/targeted.py`). Three
50 m corridors around the gap lines (F001 10.9 m; F100 183.5 m; F101 244.9 m) plus F001's bounding
box expanded by 50 m (10.717858–10.728288 N, 122.568977–122.578012 E, about 1.14 km²). In each area
it fetches **every** `highway=*` way with no access filter, plus `barrier`, `bridge=*`,
`man_made=bridge`, `footway` ways and `barrier`, `entrance`, `noexit`, `access`, `foot` nodes,
with `out meta`. Static validation passed: brackets balanced, lat/lon order and study-area bounds
checked, the F001 gap lies inside the box, no access filter, and the selector count is right.

**Result: not obtained.** The single approved POST to `overpass-api.de` was closed by the server
without a response. A later test with other request headers was refused by the session's safety
policy, so no workaround was tried. Nothing was written: no cache file, no snapshot, no manifest
entry. The command records the snapshot with a timestamp and hash only after a valid response.

**What the existing cache shows** [observed, walk response `547bf6791e75`]:

| | F001, Tabuc Suba subdivision | F100 / F101, Baybay Tanza |
|---|---|---|
| Size | 10.44 km of `highway=residential`/`service` (Puerto Del Mar, Pasacao St, Puerto Princesa St, Santa Clarita Lane, …), 61 ways | 0.17 km pedestrian way / 0.07 km service ways |
| Access tags | All 61 ways untagged (no `access`, `foot`, `service=private`) | Untagged |
| Gap to main network | 10.9 m, crosses no water, no mapped wall or barrier | 183.5 m / 244.9 m, no water |
| Dead ends near the main network | **4 dead ends within 20 m of main-network streets, all tagged `noexit=yes`** (10.9, 11.9, 13.5, 19.5 m). The main-network end at the 10.9 m gap (node 9204242396) is also `noexit=yes` | None within 20 m |
| Gates on the fragment | None | None |

**Reading.** At F001, mappers have marked both sides of the closest gaps as deliberate dead ends.
That is evidence **against** an unmapped link at those points. It fits a walled subdivision whose
entrance lies elsewhere. The cache cannot show whether the entrance is a way the walk filter drops
(`access=private`, `service=private`, `foot=no`, `highway=construction`) or a way that was never
mapped. **[unverified]** Baybay Tanza has no evidence either way.

**Still needed:** the targeted snapshot (§13, decision 1) or a site/imagery check of the F001
perimeter and the Baybay Tanza seaside ways.

## 4. Connected-component inventory (Phase B1)

`abot components` rebuilds the unfiltered walk graph from the cache. The main component matches the
saved graph node for node, and the 112 components keep M03's fragment ids. Inventory:
`review/m04/component_inventory.csv` (nodes, edges, km, extent and bounding box, km inside the city,
pedestrian-infrastructure km, km by access class, gates, gap to main, water on the gap, `noexit` at
the gap, cells and residents attached, internal facility reach).

Classes are desk heuristics, applied first match wins [assumption]:

| Class | Rule | Components | km | Residents attached (A3) |
|---|---|---|---|---|
| `main` | largest component | 1 | 1,371.2 | 448,855.8 |
| `separated_by_water` | gap crosses a mapped watercourse or coastline (incl. Guimaras) | 10 | 15.7 | 68.6 |
| `restricted_access` | ≥ 50% of length `access=no`/private | 7 | 1.3 | 0 |
| `access_uncertain` | ≥ 50% customers/unknown, or a private or no-access gate | 1 (F062, Dock Access Road) | 0.6 | 91.9 |
| `isolated_mapped_dead_end` | `noexit=yes` at the gap | 1 (**F001**) | 10.4 | 2,382.9 |
| `likely_geometry_error` | ≤ 2 m from main but not joined | 6 | 0.3 | 0 |
| `isolated_local_network` | ≥ 0.5 km otherwise | 5 (e.g. F003, St. Therese Hospital grounds, 1.75 km of footways) | 4.8 | 207.7 |
| `small_fragment` | < 0.5 km | 81 | 6.5 | 2,546.9 |

Notes. Several small fragments are **campus or mall internal paths**, including UP Visayas, the
University of San Agustin, PSHS, Angelicum and Robinsons. Their entrance is unmapped or excluded by
the filter. F024 (Robinsons) touches the main network at 0.0 m without a shared node, a classic
mapping error. Dead ends within 20 m of the main network: `dead_end_near_misses.csv`.

## 5. Comparison of the three approaches (Phase B2)

All three use the baseline connection and routing code. A1 reproduces the saved baseline exactly
(the build stops otherwise). **No link between components is ever added.** A facility connection is
a destination, never a through-route.

- **A1 (current):** largest component only.
- **A2:** all eligible components (not `restricted_access`). Cells **and facilities** attach to the
  nearest eligible edge, and one indicator mixes internal and citywide times.
- **A3 (component-aware):** as A2, plus `access_uncertain` components, which are labelled. Each
  facility *also* keeps its main-network connection. Citywide indicators use network-connected
  residents only. Internal (within-component) times are reported separately.

| Residents | A1 baseline | A2 all eligible | A3 component-aware |
|---|---|---|---|
| Components retained | 1 | 104 | 105 |
| Network km | 1,371.2 | 1,408.9 | 1,409.5 |
| **Network-connected** (citywide) | **453,656.9** (7,733 cells) | 448,925.1 | **448,855.8** (7,576) |
| **Locally connected** (isolated component only) | — | 5,206.0 | **5,206.0** (187) |
| **Access-uncertain** | — | — | **91.9** (9) |
| **Unconnected** | **3,969.1** (302) | 3,494.8 | **3,472.3** (263) |

Moves from A1 to A3 [derived]: **4,731.7 network-connected → locally connected** (M03's straight-connector
residents; 2,134 of M03's 4,812 were in F001), 69.3 → access-uncertain, **474.3 unconnected →
locally connected**, 22.6 → access-uncertain. Largest by barangay (excluding Calahunan and Hibao-an Sur):
Tabuc Suba 1,434.7 + 249.6, Ticud 552.9, Baybay Tanza 499.1 + 141.1, Alalasan Lapuz 468.8, Tacas 232.3
(`changes_by_barangay.csv`). In the excluded barangays, 68.6 residents change (the F060 creek stub);
not investigated.

Citywide walking indicators (share of **all** residents ≤ 15 min; A3 counts network-connected only):

| Group | A1 | A2 | A3 | A1 → A3 mean (min) |
|---|---|---|---|---|
| Hospital | 22.90% | 22.66% | 22.64% | 27.92 → 27.95 |
| Primary care | 66.56% | 66.07% | 66.07% | 13.21 → 13.17 |
| Basic education | 88.30% | 87.77% | 87.44% | 8.66 → 8.63 |
| Public market | 39.45% | 39.29% | 39.29% | 20.47 → 20.41 |
| Pharmacy | 62.74% | 62.17% | 62.17% | 13.81 → 13.78 |

**Internal access is kept** [derived]: of the 5,206 locally connected residents, 3,086.4 reach a school
inside their component (3,072.8 within 15 min). These are mainly F001 residents, who reach Santa
Clarita International School. 100.2 reach a hospital internally (F003, St. Therese Hospital grounds)
and 29.3 a higher-education campus. None reaches a primary-care facility internally.

**False-access implications:**
- **A1 overstates access:** 4,731.7 residents get citywide times through a straight connector of
  median ~104 m to a street they may not be able to walk to. At F001 the mapped data mark the nearest
  points as dead ends.
- **A2 understates access:** it pulls **9 citywide destinations** off the main network onto
  campus/mall fragments (St. Therese Hospital, UP Visayas, University of San Agustin, PSHS-WVC,
  Jalandoni Memorial NHS, Angelicum School, Santa Clarita Int. School, Robinsons supermarket and bank)
  and mixes internal with citywide times. **Not recommended.**
- **A3** keeps both kinds of information apart. Its remaining assumption is that a fragment's cells
  cannot leave it [assumption]. For F001 this is likely too strict, because residents must have some
  way out, but the route is not in the data.

**Verified-connection scenario: none.** No link is supported by evidence: the cache shows `noexit`
at F001 and nothing at Baybay Tanza, the Overpass snapshot was not obtained, and no imagery was
checked. This scenario is therefore identical to A3 and was not run separately.

## 6. Private-road access policy (Phase C1: analysis only)

**Way classification** (`components.access_class`; `foot` overrides `access`) [assumption,
provisional, **not applied**]:

| Class | Tags | Provisional treatment | Main network km |
|---|---|---|---|
| public | `access`/`foot` = yes, designated, permissive | eligible | 30.9 |
| untagged | no access tags | eligible by OSM default for the highway class; **not verified** | 1,323.9 |
| destination | `access=destination`/delivery | potentially eligible (entry to reach a destination) | 22.3 |
| private | `access`/`foot` = private/residents, `service=private` | resident-only: explicit assumption needed | 0.8 |
| customers | `access=customers` | uncertain: flag | 0.9 |
| uncertain | permit, unknown, … | uncertain: flag | 0.02 |
| no_access | `access=no` (no foot override), `foot=no` | ineligible | 5.3 |

Gate-type nodes (`gate`, `lift_gate`, `swing_gate`, `sliding_gate`) on walk ways: 703. Classes: 171
private, 31 no-access, 275 untagged, 188 public, 30 destination, 6 customers, 2 uncertain. osmnx
ignores node access tags, so **the current walk network routes through all of them**
[observed]. 693 are matched to an edge; 10 are not; 3 sit at junctions.

**Effect of removing each restriction from the baseline network** (`access_impact.csv`;
component-aware, not applied):

| Tag | Ways (all) | km removed (main) | Residents losing citywide connection | Residents with any time +1 min or more | Hospital ≤ 15 min |
|---|---|---|---|---|---|
| `access=no` | 66 | 6.11 | 12.6 | 678 | 22.90 → 22.89% |
| `access=private` (ways) | 0 | 0 | 0 | 0 | — (osmnx drops them before download) |
| `access=destination` | 201 | 22.28 | 1,589.8 | 55,930 | 22.90 → 22.88% |
| `access=customers` | 10 | 0.76 | 0 | 2,974 | unchanged |
| `foot=private` | 4 | 1.20 | 0 | 0 | unchanged |
| private gate nodes | 191 | 7.20 | 205.5 | 13,374 | 22.90 → 22.88% |
| no-access gate nodes | 44 | 2.94 | 60.3 | 27,702 | 22.90 → 22.76% |
| untagged gate nodes | 303 | 18.87 | 1,819.4 | 124,959 | 22.90 → 22.15% |
| combined: no + foot=private + private/no gates | 287 | 14.18 | 218.3 | 39,308 | 22.90 → 22.72% |

Reading [derived]: in the five groups reported (`access_impact_by_group.csv`), citywide ≤ 15 min
shares move by at most 0.75 pp. Local effects are large for some
residents, and the untagged-gate scenario is the most sensitive. Removing the whole simplified edge
that carries a gate somewhat overstates the effect. The "time +1 min" column counts a resident if any
of the 10 groups gets slower.

**Proposal (for decision, §13):** treat `access=no` (no foot override) as ineligible, since the
impact is negligible and the tag is explicit. Keep `destination` and untagged ways eligible, because
removing them would deny residents their own streets. Report private and no-access gate edges as
**resident-only / access-uncertain** in a component-aware layer rather than delete them. Leave untagged
gates eligible but count them. Keep public access and resident-accessible infrastructure as separate
columns in reports.

## 7. Manual facility review (Phase D): all 14 still pending

`review/m04/facility_review_summary.csv` copies the M03 evidence, adds the M04 rationale and the
evidence still needed, and copies the reviewer columns unchanged.

- **Likely duplicates.** D13 (the DBP building outline lies 100% inside the DBP site outline) and
  D14 (Pakiad Talipapa: identical tags, consecutive ids). Merging D13 lowers `n_finance_bank` by 1
  in Muelle Loney-Montes. D14 lies outside the city, so no count changes.
- **Distinct: bank vs ATM.** D01, D02, D07, D08, D09. An ATM is descriptive and never a
  destination, so keeping both records changes no indicator.
- **Uncertain.** D03, D04, D05, D06, D10, D11, D12 need street-level, imagery or registry evidence.
  Together they move up to 4 bank counts and 3 other counts. D04, D05 and D11 decide which barangay
  is counted.
- **Travel times:** affected by at most the 4–41 m shift of the record kept. Negligible.
- **D10 (BPI, 41 m apart, Buhang Taft North).** The evidence that would decide it is BPI's official
  list showing one or two branches or business centres at Festive Walk / Megaworld, or a site check of
  both positions. The one approved lookup (`bpi.com.ph/locator`) returned **HTTP 404**:
  inconclusive. **D10 stays pending.**

## 8. Historical experiment archive (Phase E)

`data/archive/hist_e7_buffer_3km_m02/` (record `hist_e7_buffer_3km_m02.sha256.json`, `src/abot/archive.py`):
21 files = `interim/` (9), `processed/` (7), `comparison_e7_buffer_1km_vs_3km/` (4, the
M02-era comparison), `config/e7_buffer_3km.yaml`. The record also holds each source path, its size
and mtime, the git HEAD at archive time, the experiment overrides, the code context (M02 working tree,
between `3edc0dd` and `3e85764`), the OSM cache used and why the outputs are historical (M02
definitions: unanchored WorldPop 2026 weights, connected-only denominators, pre-fix drive speeds).
`comparisons/e7_buffer_1km_vs_3km_m02b` is a current comparison, so it was **not** archived.

Verification: the copy step hashes both sides. `archive.verify` re-hashes both, and a separate
`sha256sum -c` run outside Python matched 21/21 with 0 failures. `abot audit` reports
`hist_e7_buffer_3km_m02: 21 files match`. **Originals kept**, so the audit WARN `experiment:
e7_buffer_3km` remains until you decide whether to remove them (§13).

## 9. Population and accessibility changes

**None to the active baseline.** All figures in §5–§6 are side-by-side scenarios in
`data/processed/review/m04/`. `data/processed/` (baseline), `hist_buffer_1km` (1 km historical) and
`sens_maxspeed_override` were not rebuilt, so no sensitivity output is stale relative to the baseline.

## 10. Sensitivity results

- Connector tolerance (M03, unchanged, reported separately): residents not connected would be 3,969 at
  250 m (default), 2,835 at 300 m, 1,922 at 400 m and **1,407 at 500 m**. The **250 m default is kept**.
- Component policy (§5) and access tags (§6) are the M04 sensitivities.

## 11. Tests, audit and reproducibility

| Check | Result |
|---|---|
| `pytest` | **138 passed** (103 + 35 new in `tests/test_m04.py`) |
| `ruff check` | clean |
| `abot audit` | **PASS 55, WARN 4, FAIL 0, INFO 11** ([MILESTONE_04_AUDIT.md](MILESTONE_04_AUDIT.md)); the new PASS is the archive |
| Determinism | `abot components` under `PYTHONHASHSEED=0` and `12345`: all 15 output files byte-identical |
| A1 = baseline | Checked on every run: statuses equal, walk times within rounding |
| Review files | 3 review CSVs: SHA-256 identical to before the milestone |

New tests cover: multiple components; isolated networks that keep internal access; cells on a
secondary component getting no citywide time; no link across a 1 m gap; A2 losing and A3 keeping a
fragment-side facility; a nearby road alone giving no accessibility; deterministic component order;
access classes, foot override and the rule that restricted or uncertain is never public; component
class order; the query having no access filter and lat/lon validation; no download without
`--allow-download`; archive copy/verify/refuse-overwrite/audit; reviewer columns preserved; experiment
built with another configuration flagged (sensitivity freshness).

## 12. Remaining limitations and unresolved items

- F001's real entrance and the Baybay Tanza links are **unverified**. The cache cannot show ways the
  walk filter drops.
- Fragment classes are heuristics. 81 small fragments (2,547 residents attached under A3) were not
  reviewed one by one.
- Gate access is recorded on 703 nodes and is not used by the router. 275 gates have no access tag.
- A3's "cannot leave the fragment" is conservative for gated subdivisions; A1's straight connector is
  optimistic (the follow-up labels A1 the *optimistic connectivity scenario*, not a verified upper
  bound). Neither is observed.
- The connector-tolerance result (1,407 at 500 m) shows the unconnected count depends on tolerance.
  It is evidence about tolerance, not about paths.

## 13. Decisions requiring your approval

1. **Overpass snapshot.** Retry the same validated query, run by you (`uv run abot fetch-gaps --allow-download`) or by me once more, or allow another public Overpass instance. Otherwise F001/F100/F101 stay unverified.
2. **Network method.** Adopt A3 as an *additional reporting layer* (recommended: barangay columns `pop_locally_connected`, `pop_access_uncertain`; citywide indicators on network-connected residents; A1 kept as the labelled optimistic connectivity scenario), keep A1 unchanged, or wait for decision 1. A2 is not recommended.
3. **Access policy.** (a) exclude `access=no` without a foot override; (b) report private/no-access gate edges as resident-only/uncertain; (c) keep `destination` and untagged ways and gates eligible. Approve, amend or defer.
4. **`e7_buffer_3km` originals.** The archive is verified. Remove `data/interim/e7_buffer_3km`, `data/processed/e7_buffer_3km` and `comparisons/e7_buffer_1km_vs_3km` (clears the WARN), or keep them.
5. **Duplicates.** D13 and D14 are recommended as same facility (`same_keep_related`). Confirm D01, D02, D07, D08, D09 as `distinct_keep_both`. D03–D06, D10–D12 need field or imagery evidence. Nothing has been entered.
6. **D10:** a different BPI URL, or a site check. Otherwise it stays pending.

## 14. Recommended next milestone

Decide items 1 to 3. If A3 is approved, implement it in `accessibility.py` as a component-aware
layer with migration tests, rebuild the baseline, 1 km and speed runs, archive the previous outputs,
and regenerate comparisons. Then do field or imagery verification of F001's entrance, Baybay Tanza
and the campus fragments, and add any confirmed links as recorded, reversible network corrections
with evidence ids.

## 15. Files

| File | Change |
|---|---|
| `src/abot/components.py` (new) | `abot components`: inventory, A1/A2/A3, access classes, gate matching, access impact, gap evidence, facility review summary |
| `src/abot/archive.py` (new) | Copy + SHA-256 record + independent verify; `e7_buffer_3km` archive |
| `src/abot/fetch/targeted.py` (new) | `abot fetch-gaps`: targeted query, validation, gated download, snapshot + manifest |
| `src/abot/cli.py` | `components`, `fetch-gaps` commands |
| `tests/test_m04.py` (new) | 35 tests |
| `data/processed/review/m04/` (new) | Evidence tables and README |
| `data/archive/hist_e7_buffer_3km_m02/` (+ `.sha256.json`) | Archive (originals kept) |
| Docs | This file, `MILESTONE_04_AUDIT.md`, `Documentation.md`, `METHODOLOGY.md`, `DATA_SOURCES.md` |

```bash
uv run abot components                 # offline; writes data/processed/review/m04/
uv run abot fetch-gaps                 # dry run: prints and validates the query
uv run abot fetch-gaps --allow-download   # one request; snapshot to data/raw/osm_targeted/
uv run abot audit --output docs/MILESTONE_04_AUDIT.md
uv run pytest
```
