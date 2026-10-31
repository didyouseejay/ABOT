# ABOT — Milestone 02: implementation results

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Baseline compared against** | Milestone 01 (commit `3edc0dd`), archived in `data/archive/m01_3edc0dd/` |
| **Scope implemented** | Audit Priority 0 corrections, category refinement, origin-connection fix, drive-speed policy, Experiment E7 (OSM extraction buffer), registry availability research |
| **Not implemented (out of scope)** | Frontend, backend, PostGIS, machine learning, 2SFCA, new categories, registry integration |

> **Superseded baseline (2026-10-31).** Milestone 02B changed the default buffer to 3 km, the
> population weights to census-anchored 2020, and the share denominators to all residents. It also
> fixed a non-deterministic speed assignment. The figures below describe the Milestone 02 (1 km,
> WorldPop 2026) run, whose outputs are archived in `data/archive/m02_wip_1km_20261031/`. Current
> figures: [MILESTONE_02B_RESULTS.md](MILESTONE_02B_RESULTS.md).

This document reports **what changed, by how much, and why**. Methods are in
[METHODOLOGY.md](METHODOLOGY.md); the reasons for the changes are in
[MILESTONE_02_ANALYTICAL_AUDIT.md](MILESTONE_02_ANALYTICAL_AUDIT.md). A parallel
[MILESTONE_02_VALIDITY_ASSESSMENT.md](MILESTONE_02_VALIDITY_ASSESSMENT.md) examined six threats
to validity; where it overlaps with this work, it is cited below.

The new numbers are **not "better"**. Several are worse than in Milestone 01, because the earlier
numbers were optimistic for identifiable reasons.

## 1. What was implemented

| Audit item | Change | Status |
|---|---|---|
| C-01 health heterogeneity | Health split into hospital / primary care (indicative), dental / other (descriptive), veterinary (excluded) | Done |
| C-02 evacuation | Descriptive only. "Named" sub-type is never called official. QA no longer PASSes on count | Done |
| C-09 mixed categories | Sub-types in all nine categories; only coherent sub-types get indicators | Done |
| C-10 single category | Features can belong to several categories (`facility_roles`) | Done |
| C-11 duplicates | Merges and possible duplicates listed in `facility_exclusions.csv`, never silent | Done (manual review pending) |
| C-03 / P-01 straight-line access | Edge-based connection with water check (culverts crossable); drive access walked on the network | Done |
| Validity assessment P3 (part) | `pct_not_connected` and `indicators_flag_not_connected` (> 5%) per barangay | Done; the connector-sensitivity experiment and the blocked-cell review list are not done |
| C-04 snap validation | Connection status, tolerances and connector statistics in QA; facility connections recorded | Done |
| C-05 speeds | `maxspeed` may only lower configured speeds; `*_link` classes configured; per-edge `speed_source` | Done |
| C-13 QA semantics | Vacuous checks removed; checks that can fail added | Done |
| C-16 OSM provenance | Overpass timestamps, SHA-256, query tags, osmnx version, `used_by_runs` | Done |
| C-06 (part) | Population QA reports density r, small-barangay bias (WARN), error share | Done (calibration not done) |
| Docs | METHODOLOGY, DATA_DICTIONARY, DATA_SOURCES, this report | Done |
| E7 | 1 km vs 3 km extraction buffer | Done (§5) |

## 2. Facility classification outcome (baseline, 1 km buffer)

| Category | Sub-types: in city / incl. buffer (tier) |
|---|---|
| health | hospital 14/14 (I) · primary_care 50/51 (I) · dental 19/19 (D) · other_health 16/16 (D) · **veterinary 3/3 (excluded)** |
| pharmacy | pharmacy 85/88 (I) · chemist_only 7/9 (D, ambiguous) |
| education | school_public 69/78 · school_private 7/7 · school_ownership_unknown 40/40 · kindergarten 3/3 · higher_education 34/34 (all I) |
| safety | police 11/11 · fire_station 17/17 (I) |
| government | barangay 54/59 · city_government 4/4 · provincial_government 1/1 · other_government_office 103/104 (all D) |
| market | public_market 13/16 · supermarket 51/58 (I) |
| finance | bank 127/130 (I) · atm 45/48 (D) · other_finance 14/14 (D) |
| transport | land_terminal 6/8 · ferry_terminal 5/7 (D) |
| evacuation | named_evacuation_centre 5/5 (D, `osm_name_only`) · assembly_point 1/1 (D) |

Totals:
- **Roles by tier:** 547 indicative, 295 descriptive, 3 excluded.
- **Classification status:** 120 roles were decided by name rules or are ambiguous or
  attribute-missing; all are listed with reasons.
- **Duplicates:** 108 points were merged into same-category polygons, and 14 possible duplicates
  were flagged.

Veterinary facilities found:
- *Cornerstone Pet Hospital* (tagged `amenity=hospital`, reclassified by name)
- *Tapales Veterinary Clinic* (reclassified by name)
- *TFJ Rebadulla Animal Clinic* (`amenity=veterinary`)

Multi-category example: *San Isidro Barangay Hall* is `government.barangay` and also
`evacuation.named_evacuation_centre`, because its OSM description mentions evacuation.

## 3. Origin connections: the straight-line problem, measured and fixed

**Did Milestone 01's straight connections cross barriers?** Yes. Applying the Milestone 02 water
test to the archived Milestone 01 snap legs (cell centre to nearest node):

| Milestone 01 mode | Snap legs crossing mapped water | Population | Median length of those legs |
|---|---|---|---|
| walk | 358 cells | 5,382 (1.09%) | 172 m |
| drive | 479 cells | 8,642 (1.75%) | 202 m |

These people were routed as if they could walk straight across a river, creek, fishpond or the
coastline to reach the network. This confirms audit issue P-01.

The validity assessment counted 4,695 (walk) and 7,800 (drive) people under nearly the same
rules. The small difference is in how a water polygon near the cell centre is treated: the
assessment ignores the part within 50 m, while the pipeline ignores only polygons that contain the
centre. Its sensitivity table shows the count varies about threefold (4,695–14,464) with these
parameters.

**Milestone 02 connections (baseline):**

| Measure | Value |
|---|---|
| Population with a valid connection | **99.08%** (487,921 of 492,459) |
| Not connected: no walkable edge within 250 m | 3,404 people (158 cells) |
| Not connected: every nearby edge across water | 1,134 people (128 cells) |
| Connected after rejecting a nearer edge across water | 1,902 people |
| Connector crosses a mapped wall (flag only) | 453 people |
| Connector length, p50 / p90 / p99 / max | 23 / 104 / 212 / 250 m (Milestone 01 node snap, walk: p50 47 m, p99 324 m, max 600 m) |
| Walk to the drive network, p50 / p90 / p99 / max | 92 / 351 / 913 / 1,323 m, on paths (Milestone 01: straight line, p50 66 m) |
| Walk to the drive network > 500 m (kept, flagged) | 4,623 people |
| Sensitivity: population whose nearest walkable edge is > 150 / 250 / 400 m | 8,114 / 3,404 / 589 |

Unconnected population is concentrated in a few barangays. **Calahunan** (1,665 of 5,607, the only
barangay above 25%) and **Hibao-an Sur** (1,288) are areas with fishponds and sparse mapped paths.
28 barangays have some unconnected population. Every barangay still has indicators, but **4
barangays are flagged** (`indicators_flag_not_connected`, > 5% not connected): Calahunan,
Hibao-an Sur, Tabuc Suba (La Paz) and Baybay Tanza. Their indicators describe only their connected
residents. Culverted watercourses (8 features) are not treated as barriers; this changed no
connection in the baseline.

Facilities:
- 843 of 844 are connected.
- **Lambuyao Elementary School** is not connected: every path within 500 m is across a mapped river
  (QA WARN). This is a gap in the mapped network, not a missing school.
- One ATM uses a 405 m connector (flagged).

### Verification

The new routing was compared with independent implementations on random samples:

| Check | Reference implementation | Max difference |
|---|---|---|
| Walk, hospital and public market (40 cells each) | Connections inserted as nodes by splitting edges; plain Dijkstra on an undirected graph | 0.005 min (rounding) |
| Drive, hospital (25 cells) | Explicit walk-to-car route, forward (not reversed) drive graph per cell | 0.005 min (rounding) |

## 4. Before and after: city-wide results

Population-weighted; Milestone 02 values cover connected population (99.08%).

### Walking

| Milestone 01 category | M01 mean | M01 ≤15 / ≤30 min | Milestone 02 group | M02 mean | M02 ≤15 / ≤30 min |
|---|---|---|---|---|---|
| health | 12.67 | 70.1% / 93.2% | **health_hospital** | **27.26** | **24.9% / 62.5%** |
| | | | health_primary_care | 13.35 | 67.2% / 91.9% |
| pharmacy | 14.05 | 62.2% / 91.6% | pharmacy | 13.67 | 63.9% / 92.0% |
| education | 8.88 | 87.8% / 99.6% | education_basic | 8.61 | 88.9% / 99.8% |
| | | | education_higher | 23.41 | 37.7% / 69.2% |
| safety | 15.84 | 54.7% / 89.6% | safety_police | 18.71 | 42.0% / 84.0% |
| | | | safety_fire | 16.89 | 48.2% / 89.2% |
| market | 15.83 | 56.0% / 89.8% | market_public | 20.19 | 42.0% / 82.1% |
| | | | market_supermarket | 17.20 | 49.6% / 87.4% |
| finance | 14.79 | 58.6% / 90.3% | finance_bank | 15.60 | 55.7% / 88.8% |
| government | 10.06 | 82.8% / 95.9% | *descriptive only* | — | — |
| transport | 34.96 | 17.1% / 47.4% | *descriptive only* | — | — |
| evacuation | 37.16 | 11.9% / 32.3% | *descriptive only* | — | — |

### Driving (door-to-door, free-flow)

| Milestone 01 category | M01 mean | M01 ≤10 min | Milestone 02 group | M02 mean | M02 ≤10 min |
|---|---|---|---|---|---|
| health | 3.18 | 99.4% | health_hospital | 7.46 | 81.7% |
| | | | health_primary_care | 4.26 | 98.0% |
| pharmacy | 3.20 | 99.5% | pharmacy | 4.19 | 97.8% |
| education | 2.85 | 99.8% | education_basic | 3.82 | 99.0% |
| safety | 3.79 | 99.4% | safety_police / fire | 5.47 / 5.23 | 96.3% / 96.8% |
| market | 3.53 | 99.4% | market_public / supermarket | 5.80 / 5.23 | 92.5% / 97.0% |
| finance | 3.25 | 99.4% | finance_bank | 4.50 | 97.7% |

### Why the numbers moved

1. **Definitions (largest effect).** Milestone 01's "health" was dominated by dental, laboratory and
   therapy features. Access to a *hospital* on foot is more than twice as long, and only a quarter
   of residents are within 15 minutes. The same applies to public markets vs supermarkets, and
   police vs fire stations.

2. **Connection to edges rather than nodes (walk times fall slightly).** Pharmacy is the one group
   defined almost identically in both milestones:
   - The walk mean fell from 14.05 to 13.67 min.
   - Barangay ranks are stable (Spearman ρ = 0.987).
   - 23 barangays changed by more than 1 minute; the maximum change was 3.8 min.

3. **Drive access routed on paths, and speed cap (drive times rise).** Decomposition for
   **pharmacy** (comparable definition):

   | Step | Mean drive (min) | ≤5 min |
   |---|---|---|
   | Milestone 01 | 3.20 | 86.5% |
   | + Milestone 02 connection, routed walk to car, M01 speed rule (`sens_maxspeed_override` run) | 3.67 | 80.7% |
   | + speed cap: `maxspeed` may not raise configured speeds (baseline) | 4.19 | 72.2% |

   The two corrections contribute roughly equally. For hospitals, the speed cap alone adds 1.17 min
   on average (6.29 → 7.46) and lowers the share within 10 minutes from 93.1% to 81.7%. The
   override run is `config/experiments/sens_maxspeed_override.yaml`; full tables are in
   `data/processed/comparisons/speed_override_vs_cap/`.

4. **Drive barangay ranks changed more than walk ranks.** For pharmacy, Spearman ρ = 0.947 and 63
   barangays changed by more than 1 minute. Drive-mode barangay rankings from Milestone 01 should
   not be reused.

### Barangays with the longest mean walking time (Milestone 02 baseline)

| Group | Five longest (mean min) |
|---|---|
| health_hospital | Santo Niño Sur 75.8 · Santa Cruz 70.4 · Mohon 69.5 · Santo Domingo 62.1 · Bonifacio (Arevalo) 58.6 |
| health_primary_care | Hibao-an Norte 42.3 · Tacas 36.2 · So-oc 35.9 · Ingore 35.3 · Lanit 32.5 |
| market_public | Buntatala 57.8 · Lanit 57.1 · Bito-on 55.1 · Ingore 47.2 · Tagbac 47.1 |

These describe access to **mapped** facilities, and they are not yet checked for robustness (other
than E7). Before reporting any barangay ranking, also check its `pop_cells` and its WorldPop vs
census error.

## 5. Experiment E7: does the 1 km extraction buffer matter?

**Design.**
- **Changed:** the OSM extraction buffer (networks, barriers, facilities), 1 km → 3 km.
- **Unchanged:** every other assumption; population cells and barangay aggregation (city only).
- **Setup:** config `config/experiments/e7_buffer_3km.yaml`, outputs in
  `data/processed/e7_buffer_3km/`, new Overpass downloads recorded in the manifest. The original
  1 km responses were not touched.
- **Confound check:** the facilities inside the city are identical in both runs (803 features, same
  OSM ids).

**What the wider buffer adds:** walk nodes 12,927 → 14,918; drive nodes 6,794 → 8,049. Destinations
in the buffer:

| Group | 1 km run | 3 km run |
|---|---|---|
| Pharmacy | 97 | 104 |
| Health | 103 | 122 |
| Education | 162 | 190 |
| Market | 74 | 80 |

**Results**

| Measure | Result |
|---|---|
| City-wide mean, any group | Change ≤ 0.07 min (largest: walk primary care 13.35 → 13.28) |
| City-wide % within 15 / 30 min | Change ≤ 0.2 percentage points |
| Barangay rank correlation (Spearman ρ) | **1.0000** for all 20 mode × group combinations |
| Overlap of the 20 worst barangays | 20 of 20 for every group |
| Cells slower with 3 km | **0** (as expected: more options can only shorten trips) |
| Population faster by > 0.1 min | 0 to 3,437 people depending on group (≤ 0.7%) |
| Largest barangay change | **Hibao-an Norte**, walk to primary care 42.3 → 30.1 min (a mapped primary-care facility 1–3 km beyond the city limit becomes reachable). Also Hibao-an Norte drive primary care 10.3 → 8.4; Ungka police 46.0 → 43.9; Tacas police 40.7 → 38.9. |
| Facilities unconnected in the 3 km run | 13, **all outside the city**, mostly on **Guimaras** (Jordan and Buenavista wharves, schools, a market). They are across Iloilo Strait with no road link, so correctly they have no path. A straight-line method would have connected them. |

**Conclusion.** The 1 km buffer does **not** materially affect city-wide results or barangay
rankings. It does understate access for a handful of **border barangays**, notably Hibao-an Norte
(primary care) and, to a lesser degree, Tacas, Ungka and Hibao-an Sur. Recommendation: either adopt
3 km for the baseline, or report border barangays with a note. The extra cost is small: about 20%
more network nodes, and a build still takes a few minutes on the target laptop.

## 6. QA changes, before and after

| Milestone 01 check | Milestone 02 |
|---|---|
| `facilities_<cat>` PASS if ≥ 5 | info: count + tiers ("says nothing about completeness") |
| `<mode>_<cat>_unreachable_pop` PASS (true by construction) | `origins_connected_pop_pct` (≥ 99%), `origins_beyond_tolerance_pop`, `origins_barrier_blocked_pop`, `<mode>_<group>_connected_without_time` (can fail), `origins_conservation` |
| median snap distance | connector quantiles, tolerance sensitivity, rerouted and wall-crossing population, facility connections, drive access walk |
| `wp2020_vs_census_barangay_r` PASS (> 0.7) | r is info only; added density r, \|error\| > 50% count, small-barangay bias (**WARN at +69.9%**), error share |
| — | Network component filter share, speed sources and fallbacks, OSM snapshot timestamps |

Remaining WARNs (all real findings): Lambuyao Elementary School not connected; small-barangay
population bias.

## 7. Tests

- **53 tests pass:** the 13 original tests plus 40 regression tests in `tests/test_m02.py`.
- **Classification:** veterinary vs animal-bite centres, hospital vs primary care,
  `healthcare=pharmacy`, multi-valued tags, multi-category membership, school ownership,
  descriptive categories not routed, and config validation.
- **Records:** merges and duplicates are recorded.
- **Speed policy:** 9 cases.
- **Connections:** edge interior vs node, rerouting around a river, enclosure by water, tolerance
  near the cell centre, beyond tolerance.
- **Routing:** same-edge shortcut, drive access walked on the network, nearest-source Dijkstra.
- **Indicators and QA:** unconnected population excluded from denominators; QA can fail.
- **Configuration and provenance:** experiment config isolation, provenance accumulation, weighted
  quantile, maxspeed parsing.
- **Barriers:** barrier kinds, including culverts as crossable, and the not-connected flag.

## 8. Reproducing these results

```bash
uv run abot build && uv run abot report                       # baseline (1 km), from the OSM cache
uv run abot --config config/experiments/e7_buffer_3km.yaml build
uv run abot --config config/experiments/e7_buffer_3km.yaml report
uv run abot --config config/experiments/sens_maxspeed_override.yaml build
uv run abot compare data/archive/m01_3edc0dd data/processed --name m01_vs_m02_baseline
uv run abot compare data/processed data/processed/e7_buffer_3km --name e7_buffer_1km_vs_3km
uv run abot compare data/processed/sens_maxspeed_override data/processed --name speed_override_vs_cap
uv run pytest
```

All runs were rebuilt from cache after the last code change, with no new downloads, and produced
the figures above.

## 9. Remaining limitations and recommended next steps

**Still true after Milestone 02:**
1. **No facility category is independently verified.** Registry availability is documented in
   [DATA_SOURCES.md](DATA_SOURCES.md) §4. NHFR codes (25 features) and DepEd School IDs (85
   schools) already in OSM `ref` make matching feasible.
2. **Evacuation:** about 450 designated centres are reported by the city (press figure, unverified)
   against 6 OSM features. Evacuation accessibility cannot be estimated from OSM.
3. **Population weights:** not calibrated to the census; small barangays are biased +70%. See the
   validity assessment's P1/P2 (awaiting your decision).
4. **Indicators:** still mean, max and % within. Medians, P90 and persons beyond threshold exist
   only in `abot compare` (audit Priority 1).
5. **Sensitivity:** only E7 and the speed-policy attribution were run. E1 (walking speed), E3
   (definitions), E4 (population weights) and E6 (thresholds) remain.
6. **Network barriers:** taken from OSM. Gates, mangroves, flooding and unmapped paths are not
   modelled. The 14 flagged possible duplicates await manual review.
7. **Travel:** drive times are free-flow lower bounds, and there is no public transport.

**Validity-assessment proposals still open:**
- P1: census-anchored weights
- P2: reliability flag and fractional allocation
- the rest of P3: radius × tolerance experiment, blocked-cell review list
- P4: boundary wording
- P5: drive terminology and speed-sensitivity experiment
- P6: proximity vs capacity wording
- P7: `abot audit`

**Suggested order for the next milestone:**
1. Obtain the NHFR export and request the DepEd masterlist and the CDRRMO list.
2. Run E1, E3, E4 and E6.
3. Add census-calibrated weights and P50/P90/persons-beyond-threshold to the barangay table.
4. Decide on the 3 km buffer.
