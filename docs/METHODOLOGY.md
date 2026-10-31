# ABOT methodology

This document describes how ABOT produces its accessibility indicators as of **Milestone 02B**
(3 km buffer, census-anchored weights, reliability flags; see
[MILESTONE_02B_RESULTS.md](MILESTONE_02B_RESULTS.md)). It
replaces the short method summary in the README as the reference description. Parameter values
are in [config/settings.yaml](../config/settings.yaml). Output columns are defined in
[DATA_DICTIONARY.md](DATA_DICTIONARY.md) and sources in [DATA_SOURCES.md](DATA_SOURCES.md).
[MILESTONE_02_ANALYTICAL_AUDIT.md](MILESTONE_02_ANALYTICAL_AUDIT.md) and
[MILESTONE_02_VALIDITY_ASSESSMENT.md](MILESTONE_02_VALIDITY_ASSESSMENT.md) explain why the method
changed, and [MILESTONE_02_RESULTS.md](MILESTONE_02_RESULTS.md) shows how much each change moved
the results.

## What the indicators mean, and what they do not mean

ABOT estimates **modelled travel time along the mapped OpenStreetMap (OSM) network, from where
people are estimated to live, to the nearest facility of a given type that is mapped in OSM.**

| ABOT measures | ABOT does not measure |
|---|---|
| Network travel time under stated speed assumptions | Real travel time (congestion, waiting, weather, flooding, safety) |
| Distance to *mapped* facilities | Whether facilities are complete, open, staffed or have capacity |
| Proximity | Service adequacy or quality |
| Barangay population = PSA 2020 census, spread within the barangay by a modelled grid (WorldPop 2020) | Observed population at cell level, or after 2020 |
| Gaps in mapped data | Proof of gaps in real infrastructure |

Three concepts are kept apart (validity assessment P6):

| Concept | Question | ABOT now |
|---|---|---|
| **Geographic proximity** | How far, in modelled time, is the nearest mapped facility of a type? | Measured: every indicator |
| **Service level** | Is that facility a substitute for the service (hospital vs health station; ATM vs bank)? | Only through indicator groups of substitutable sub-types; facility level and public/private status are **not verified** |
| **Capacity / availability** | Can it serve the people who depend on it? | **Not measured** (beds tagged for 3 of 16 hospitals; no enrolment) |

Reporting rules:
1. Label every indicator "access to the nearest mapped [sub-type]".
2. Do not write "served", "coverage", "adequate" or "underserved" without saying that only
   proximity is measured.
3. A shorter time is not better service.
4. `n_*` columns are counts of mapped features, not capacity.

Car times are always called **modelled uncongested (free-flow) car travel time** (P5). They are
measured on the mapped OSM road network, include the walk to and from the road, and exclude
congestion, signals, turning, parking and car availability. They describe households with a car,
and their threshold shares are lower bounds.

The indicators are suitable for **screening**: finding areas where mapped access is poor and that
deserve field verification. They are not suitable for allocating resources on their own.

## 1. Study area and coordinate system

- Iloilo City (COD-AB p-code `PH0603022`) and its 180 barangays, from OCHA COD-AB v03.
- All distances and areas are computed in **WGS 84 / UTM zone 51N (EPSG:32651)**, in metres.
- OSM data are fetched for the city polygon plus an **extraction buffer** (default 3,000 m since
  Milestone 02B; the 1,000 m value of Milestones 01–02 is kept in
  `config/experiments/hist_buffer_1km.yaml`). This lets trips and facilities just across the city
  limit count. **Origins (population) and all reporting stay inside the city.** Facilities in the
  buffer are destinations only if they have a valid network connection.
- 72.63 km² is the area of the COD-AB v03 polygon (land), **not the official land area**. The
  often-cited 78.34 km² has no reproducible geometry and is not used as a comparison.

## 2. Population origins and weights

1. The WorldPop R2025A constrained 100 m rasters for 2020 and 2026 (same grid, checked) are windowed
   to the city polygon. Every cell that **touches** the city and has a positive count in either year
   is kept. One cell is 3 arc-seconds, about 92.6 m × 91.0 m here. The origin point is the cell centre.
2. **Fractional allocation.** Each cell square is split between the barangays it overlaps, in
   proportion to area (`pop_pieces`). The part outside the city is not counted. Barangay totals and
   indicators are sums over pieces; each piece carries its cell's travel time.
3. **Weights.** `pop_census2020_adj` (primary): within each barangay, WorldPop 2020 piece values are
   scaled so that the barangay equals its PSA 2020 census count. The original WorldPop values are
   kept as `pop_wp2020` and `pop_wp2026`. The configured weight (`population.primary_weight`) is
   copied to `pop`. Census residents in a barangay without WorldPop 2020 population would be
   reported as `census_unallocated`, never moved; there are none.
4. **Reference year 2020.** Barangay totals are observed (census). The within-barangay pattern is
   modelled. WorldPop 2026 is a projection with no post-2020 barangay information and is used as a
   sensitivity only.

## 3. Road and path networks

- **Walk network:** the osmnx `walk` network type. It excludes ways tagged `foot=no`,
  `access=private`, motorways and cycleways. It is **bidirectional**, because pedestrians are not
  bound by one-way rules. Edge time = length ÷ 4.5 km/h.
- **Drive network:** the osmnx `drive` network type. It excludes service roads, driveways, parking
  aisles and `motor_vehicle=no`, and respects `oneway`. It is reduced to the largest *strongly*
  connected component, so every node can reach every other node.
- **Connectivity check.** The full fetch is kept long enough to measure what the largest-component
  filter removes:
  - walk: 93 pieces fetched; 97.1% of nodes kept (385 nodes, 52 km dropped)
  - drive: 28 pieces fetched; 97.0% of nodes kept (210 nodes, 36 km dropped)

### 3.1 What the walk filter does and does not exclude (Milestone 04, observed)

The osmnx 2.1.1 walk filter is
`["highway"]["area"!~"yes"]["access"!~"private"]["highway"!~"abandoned|bus_guideway|construction|cycleway|motor|no|planned|platform|proposed|raceway|razed|rest_area|services"]["foot"!~"no"]["service"!~"private"]["sidewalk"!~"separate"]…`.
Consequences:
- `access=private`, `service=private`, `foot=no` and `highway=construction` ways are **never
  downloaded**. The cache therefore cannot tell "missing from OSM" from "mapped but excluded".
- `access=no`, `access=destination`, `access=customers` and `foot=private` ways **are** kept and
  routed (main network: 5.3, 22.3, 0.9 and 0.8 km).
- Access tags on **nodes** are ignored. The router passes through 703 gate-type nodes (171
  `access=private`, 31 `access=no`, 275 untagged).

**Four separate concepts (M04 methodology review).** They are never collapsed into one label:
1. *Physical connectivity:* do mapped geometries share nodes (OSM topology)? This is a mapper's
   claim, not a site observation. The router also assumes every mapped walk way is physically
   traversable, although OSM rarely records surface, walls or whether a gate is open.
2. *Mapped access status:* what `access`, `foot` (and `service=private`) say.
3. *Public pedestrian status:* whether the general public may walk it, as far as the tags say.
4. *Authorised-user access:* which group a restriction admits (residents, customers, employees,
   visitors), as far as the tags **name** it.

Physical connectivity never implies public access. Public access is never inferred from a missing
tag or a missing gate. An authorised group is never inferred from the road class, a road name,
nearby land use or facility proximity.

**Access taxonomy (for analysis and reporting only; routing unchanged).** `abot.access.access_assessment`
returns, for each way or gate node, `mapped_access_status`, `deciding_tag`, `public_pedestrian_status`,
`authorized_group`, `field_verification_required` and `classification_reason`.

| Status | Tags | Public pedestrian status | Authorised group |
|---|---|---|---|
| no | `access=no` without a pedestrian override; `foot=no` | prohibited | none_permitted |
| private | `access=private`; `foot=private`; `service=private` without access/foot tags | not_public | unspecified: the tag names no group |
| residents | `access=residents`; `foot=residents` | not_public | residents_named_by_tag |
| customers | `access=customers` | customers_only (documented customer-access assumption) | customers_named_by_tag |
| unknown | permit, delivery, unknown, other values | unknown: flag for review | unknown |
| destination | `access=destination` | destination_only_assumed (entering to reach a destination, not through-walking) | destination_traffic |
| pedestrian_override | `access` = private/residents/customers **and** a public `foot` value | permitted_by_foot_tag_conflicting: flagged, verify | the group named by `access` |
| untagged | no access/foot tag | not_restricted_by_tags_unverified (OSM default for the highway class) | not_applicable |
| public | `access`/`foot` = yes, designated, permissive, public, official | permitted_by_tag | not_applicable |

**Precedence** (first match wins; tag order is irrelevant):
1. `foot=*` decides for pedestrians. A public foot value with `access=no` or a vehicle category is
   the standard pedestrian override: `public`, with the override recorded in the reason. A public
   foot value with a group restriction (private, residents, customers) is a conflict:
   `pedestrian_override`, never unrestricted public access.
2. Otherwise `access=*`.
3. Otherwise `service=private`, a road-function subtag implying private use.
4. Otherwise untagged.

**Rules that hold throughout:**
- **The road class never changes the status.** `highway=service` describes function, so a private
  service road is not a residents' road (the Iloilo Fishport roads are service roads in a port
  compound). A `tertiary` road tagged `access=private` (Gustilo Street) is private, not uncertain.
- **Permissive** access is mapped permission that the owner may withdraw. Mapped permission is not
  independently verified real-world access.
- **A simplified edge** takes its most restrictive way.
- **A corridor or path** takes the most restrictive status of **any** way or gate on it.

**Gates.** A mapped gate is evidence of a physical access-control point. It does not establish the
operating rules (hours, pedestrian wicket, staffing), and `locked=*` is only quoted. A gate is
assessed from its own tags:
- Private gates are `private` / not_public and are flagged for review.
- Untagged, destination, customers and unknown gates require field verification but are **not**
  excluded.
- A route **without** a mapped gate gains nothing from that: missing gate data is not evidence of
  public access.

The per-status counts (ways, edges, km, gate nodes, components, cells and residents whose active
connection edge carries the status) are in `review/m04/access_classification_summary.csv`. The effect
of removing each raw-tag restriction is in `review/m04/access_impact.csv`. Changing the routing
default needs separate approval.

The old labels `ineligible`, `resident_restricted`, `private_uncertain` and `uncertain` are retired.
They inferred residents from `highway=service`, called an explicit `access=private` uncertain, and
mixed prohibited with private. The old-to-new crosswalk and the verification that no component class,
A3 output, population or travel time changed are in
[MILESTONE_04_ACCESS_TAXONOMY.md](MILESTONE_04_ACCESS_TAXONOMY.md).

**Public-access results vs authorised-user scenarios.** A1 and A3 describe access for the general
public on the walk network. Access for an authorised group, for example F001 residents leaving
through their own private Gustilo Street, would be a separate, named scenario with a stated user
group, authorisation source, gate assumptions and bounds. It would never change public-access
indicators. No such scenario is implemented.

**Unresolved field verification:**
- **F001:** the subdivision's links to the main network (Gustilo St, way/821331717) are physically
  connected but `access=private`. Who is authorised, and how the gates operate, is unverified.
- **F100 / F101:** the fishport service corridor is physically connected, but `access=private` with
  private gates on every route. Pedestrian permissions are unverified, pending the operator's access
  rules or documented field verification.

### 3.2 Largest-component filter: alternatives evaluated (Milestone 04, not applied)

The 3 km walk fetch has 112 weakly connected components (main: 14,918 nodes, 1,371.2 km). Each
non-main component is classified by a desk rule, first match wins: separated by water; restricted
access; access-uncertain; mapped dead end (`noexit=yes` at the gap); likely geometry error (≤ 2 m,
not joined); isolated local network (≥ 0.5 km); small fragment. Three approaches were compared,
all with the baseline connection and routing code and **without adding any link**:
- **A1 (current):** largest component; a cell whose nearest way is on a fragment is joined to the
  main network by a longer straight connector.
- **A2:** all non-restricted components; cells and facilities attach to the nearest eligible edge.
- **A3:** as A2, plus access-uncertain components; facilities also keep their main-network
  connection; residents are network-connected, locally connected, access-uncertain or
  unconnected; citywide indicators use network-connected residents; internal times are reported
  separately and never count as citywide access.

The rationale and results are in [MILESTONE_04_RESULTS.md](MILESTONE_04_RESULTS.md) §4–§6. A3 is
the recommended *candidate* and is pending approval.

### 3.3 Component-aware reporting layer (A3; approved M04 follow-up, additional to the baseline)

The active baseline is unchanged and is labelled the **A1 optimistic connectivity scenario**:
every cell within 250 m of the main network gets citywide times, also through a straight connector
past an unlinked fragment. It is not a verified upper bound. `abot components` writes the A3 layer to
`data/processed/component_aware/`, never into the baseline files, and checks the baseline file hashes
before and after:
1. Each cell is **network_connected**, **locally_connected** (on an eligible isolated component),
   **access_uncertain** (on an access-uncertain component) or **unconnected**.
2. Citywide walking indicators use network-connected residents only. Every share divides by **all**
   residents of the barangay; nobody is dropped from a denominator.
3. Internal accessibility exists only when the cell and a facility share an isolated component. It
   is reported in separate columns (`*_internal`, `pop_local_internal_*`), with access-uncertain
   residents kept apart (`pop_uncertain_internal_*`), and is **never** counted as citywide access.
4. No link between components is created; F001 is not connected to the main network.
5. Walking only. Drive indicators stay as in the baseline.
Barangay counts and percentages: `barangay_access_a3.csv`. Citywide A1 vs A3: `citywide_a3.csv`.
`abot audit` checks that the layer is newer than the last build, uses the same configuration, and was
built with A1 reproducing the baseline.

### Drive speeds

Speeds are **assumed free-flow urban speeds by road class**. They are analytical assumptions, not
measurements, and there is no congestion, turn or signal delay.

| Class | km/h | Class | km/h |
|---|---|---|---|
| motorway | 60 | motorway_link | 40 |
| trunk | 40 | trunk_link | 30 |
| primary | 30 | primary_link | 25 |
| secondary | 25 | secondary_link | 20 |
| tertiary | 25 | tertiary_link | 20 |
| unclassified, residential, road | 20 | living_street | 10 |

Any class not listed falls back to 20 km/h and is counted in QA (currently 0 edges).

**OSM `maxspeed` policy: `cap`.** A tagged `maxspeed` can only **lower** the configured speed
(234 drive edges). It never raises it.

- **Why:** a legal limit is an upper bound on speed, not a typical urban speed.
- **Problem it fixes:** in Milestone 01, osmnx let tags replace the configured speed on 17% of
  edges. Corridors that happened to be tagged (up to 80 km/h) became artificially fast compared
  with untagged roads of the same class.
- **Options:** the policy can be switched to `ignore` or `override` in the config. The effect of
  the choice is measured in [MILESTONE_02_RESULTS.md](MILESTONE_02_RESULTS.md).

Each drive edge records `speed_kph` and `speed_source` (`config`, `maxspeed_cap`, `maxspeed`,
`fallback`).

## 4. Barrier features

Straight connectors (Section 5) are tested against OSM features that a person cannot simply walk
across:

| Kind | OSM tags | Use |
|---|---|---|
| `water_area` (polygons) | `natural=water` (includes `water=fishpond`, river areas), `landuse=aquaculture\|reservoir\|basin`, `waterway=riverbank` | Hard barrier |
| `water_line` (lines) | `waterway=river\|canal\|stream`, `natural=coastline` | Hard barrier |
| `culverted_waterway` (lines) | the same waterways tagged `tunnel=culvert\|yes\|…` | **Not a barrier**: the water runs under the surface |
| `wall` (lines) | `barrier=wall` | Flag only, because gates are not mapped reliably |

Not used as barriers: `natural=wetland` (mangroves), small `waterway=drain\|ditch`, fences and
buildings. These are known simplifications.

## 5. Connecting origins and facilities to the network

This is the step most changed in Milestone 02.

### 5.1 Connection rule

Each point (cell centre or facility) is joined by a **straight connector to the nearest point on
an edge** of the walk network. It is joined to the edge's interior, not to its end node, because
simplified OSM edges can be hundreds of metres long.

1. The candidate edges within the tolerance are tried **nearest first** (at most 12).
2. A connector is **rejected** if:
   - it crosses a watercourse or coastline line, unless the crossing is within the *origin
     radius* of the cell centre; or
   - it runs more than 20 m through a water area that does not contain the starting point.
3. The first acceptable edge is used. If nearer edges were rejected, the point is flagged
   `conn_rerouted`.
4. If no acceptable edge exists within the tolerance, the point is **not connected**:
   - `beyond_tolerance`: no walkable edge within reach;
   - `barrier_blocked`: every nearby edge is across water.

   A cell that is not connected gets **no travel time**. Its population is reported separately and
   is never counted as being within, or beyond, any threshold.
5. Because a barangay's indicators then describe only its connected residents, the barangay
   table carries `pct_not_connected`. Its indicators are **flagged**
   (`indicators_flag_not_connected`) when more than 5% of its residents are not connected. This
   currently flags 4 barangays: Calahunan, Hibao-an Sur, Tabuc Suba (La Paz) and Baybay Tanza.

| Parameter | Value | Rationale |
|---|---|---|
| Origin tolerance | 250 m | About 2.5 cell widths. If the nearest mapped walkable way is farther, the cell has no mapped path nearby and a straight line would be a guess. |
| Origin radius | 50 m | About half a cell. The residents of a 92 m cell can live on either side of a creek that runs through it, so a crossing very close to the centre is not evidence of a barrier. |
| Facility tolerance | 500 m | A mapped facility exists with more certainty than modelled population in a cell. Dropping a mapped school because its footpath is unmapped would create a false gap. Connectors longer than 250 m are kept but listed in QA. |
| Facility radius | 0 m | Facility points are exact. |
| Water tolerance | 20 m | Ignores slivers where a connector clips the edge of a mapped water polygon. |
| Not-connected flag | 5% | Analytical threshold, the same as proposed in the validity assessment (P3). |

The QA report shows how many people lie beyond 150, 250 and 400 m. This lets readers judge how
sensitive the tolerance is.

**Worked example.** *Lambuyao Elementary School* is 293 m from the nearest mapped path, and every
path within 500 m is across a mapped river. It is therefore `barrier_blocked` and is not used as a
destination. A straight line to it would mean wading the river. The real school is presumably
reached by a path that OSM does not map. This is a **network-data gap, and it is reported as one**
(QA WARN, `facilities.conn_status`).

### 5.2 Walking time

A virtual source node is linked to both end nodes of each destination's edge. The link weight is
the walking time of (connector + distance along the edge to that end). One **Dijkstra** search on
the reversed walk graph then gives every node's time to the nearest destination, using one search
per indicator group instead of one per facility. A cell's time is:

```
t_walk = connector/v + min( along_u/v + T(u),  along_v/v + T(v) )
```

If a cell and a destination are on the same edge, the direct walk along that edge is used when it
is shorter.

### 5.3 Driving time: the walk to and from the car is routed

1. From every point, the **walking route on the walk network** to the nearest drive-network node is
   found. This is a multi-source Dijkstra from all drive nodes that are also walk nodes, by
   distance, and it records which drive node is reached (the "entry node").
2. The drive leg is a Dijkstra on the reversed drive graph, so one-way streets are followed. It
   starts from the destinations' entry nodes, each weighted by its walking egress time.
3. Total: `t_drive = walk_access/v_walk + drive(entry_cell → entry_facility) + walk_egress/v_walk`.

In Milestone 01 the access leg was a straight line to the nearest drive *node*, which could cut
across rivers or blocks. It is now walked along mapped paths. Access walks longer than 500 m are
flagged (4,623 people) but kept, because they follow the network. Drive times are therefore
**door-to-door, free-flow**: a lower bound on real car travel.

### 5.4 Verification

The routing was checked against independent implementations on random samples of cells:
- **Walk:** each connection inserted as a real node by splitting edges, then a plain Dijkstra.
- **Drive:** an explicit walk–drive–walk route per cell, using the *forward* graph.

Agreement was within 0.005 min, which is rounding. The checks are described in
[MILESTONE_02_RESULTS.md](MILESTONE_02_RESULTS.md), and the synthetic cases are unit-tested in
`tests/test_m02.py`.

## 6. Facilities

### 6.1 Extraction

All OSM features whose tags match any category are fetched with Overpass for the bounding box of
the buffered study area. Only those that intersect the buffered polygon are kept. The bounding box
is used because osmnx repeats the polygon once per tag value, and with the detailed coastline the
polygon query exceeds Overpass's request size limit (HTTP 413). The resulting selection is the
same.

Every feature keeps its OSM type, id, `ref`, selected tags as columns, and **all tags** as JSON
(`osm_tags`). Polygons are reduced to a representative point (always inside the polygon).

### 6.2 Categories, sub-types and tiers

The nine Milestone 01 categories are kept. Within each, ordered **sub-type rules** decide what a
feature is (first matching rule wins). Rules use OSM tags only, apart from a few explicit name
rules (veterinary names; barangay or city office names), which are recorded as such. Multi-valued
tags (`doctor;dentist`) are split.

Each sub-type has a **reporting tier**:

| Tier | Meaning |
|---|---|
| `indicative` | Travel-time indicators are computed. Read them as access to *mapped* facilities. |
| `descriptive` | Mapped, counted and shown on the map; **no travel-time statistics**. |
| `excluded` | Recorded, never used as a destination for that category. |

No category is **verified**: none has yet been reconciled with an official registry (see
[DATA_SOURCES.md](DATA_SOURCES.md) §5). The "quantitative" tier proposed in the audit is therefore
not used.

| Category | Sub-types (tier) | Notes |
|---|---|---|
| health | hospital (I), primary_care (I), dental (D), other_health (D), **veterinary (excluded)** | A feature tagged `amenity=hospital` whose name indicates a pet or veterinary facility is reclassified as veterinary (status `reclassified_by_name`). "Animal bite" centres are deliberately *not* matched, because they are human rabies clinics. |
| pharmacy | pharmacy (I), chemist_only (D, ambiguous) | `shop=chemist` may be a toiletries shop |
| education | school_public (I), school_private (I), school_ownership_unknown (I, `attribute_missing`), kindergarten (I), higher_education (I) | Ownership from `operator:type` or a DepEd `operator` |
| safety | police (I), fire_station (I) | Reported separately |
| government | barangay (D), city_government (D), provincial_government (D), other_government_office (D, `level_not_tagged`) | Only 54 of 180 barangays contain a mapped barangay hall or office (the audit's 56 counted any `amenity=townhall`) |
| market | public_market (I), supermarket (I) | Reported separately |
| finance | bank (I), atm (D), other_finance (D) | An ATM is not a bank |
| transport | land_terminal (D), ferry_terminal (D) | **Descriptive only**: jeepney routes, the main mode, are not mapped as destinations |
| evacuation | named_evacuation_centre (D, `osm_name_only`), assembly_point (D), other_emergency_location (D) | **Descriptive only.** "Named" means named or described as an evacuation centre in OSM. It does **not** mean an official evacuation centre. |

### 6.3 Multiple categories per feature

A feature belongs to **every** category it matches. For example, a barangay hall described in OSM
as an evacuation site is both `government.barangay` and `evacuation.named_evacuation_centre`. The
`category_priority` list only chooses its *primary* category for display and de-duplication. The
`facility_roles` layer holds one row per (feature, category).

### 6.4 Duplicates and exclusions (never silent)

- **Merged:** a point inside a polygon of the same primary category is treated as the same
  facility and merged into the polygon (108 points).
- **Flagged, kept:** pairs with the same primary category, the same normalised name and within
  50 m (14).
- **Unmatched:** features returned by the query that match no category (currently 0).

All three are listed with reasons in `facility_exclusions.csv`.

### 6.5 Indicator groups

Travel times are computed for these groups of indicative sub-types:

| Group | Category: sub-types |
|---|---|
| `health_hospital` | health: hospital |
| `health_primary_care` | health: primary_care |
| `pharmacy` | pharmacy: pharmacy |
| `education_basic` | education: school_public, school_private, school_ownership_unknown, kindergarten |
| `education_higher` | education: higher_education |
| `safety_police` / `safety_fire` | safety: police / fire_station |
| `market_public` / `market_supermarket` | market: public_market / supermarket |
| `finance_bank` | finance: bank |

The configuration refuses to run if a group lists a sub-type that is not `indicative`.

## 7. WorldPop 2020 vs PSA census 2020: a diagnostic, not validation

> Since Milestone 02B the census provides the barangay totals, so the comparison below explains why
> anchoring is needed. It is never presented as evidence that WorldPop is accurate: WorldPop R2025A
> used this census as its Philippine input. Figures below are Milestone 02 (centre rule); with
> fractional allocation the city difference is +2.16% and the barangay median 30.5%.

| Measure | Value | Reading |
|---|---|---|
| City total | +2.33% | **Not independent**: WorldPop's Philippine input *was* the PSA 2020 census at barangay level (verified in the validity assessment §1), so this is close to true by construction |
| Pearson r, raw counts | 0.916 | Inflated by the size range of barangays (info only) |
| Pearson r, density | 0.506 | Shows weak agreement in *where* people are within the city |
| Median absolute error per barangay | 32.0% | |
| Barangays with \|error\| > 50% | 58 | |
| Median bias, smallest quarter of barangays | **+69.9% (WARN)** | Small, mostly downtown barangays are systematically overestimated |
| Σ\|barangay error\| / census total | 26.9% | |

Because the input was itself barangay-level, the barangay differences mostly reflect how
WorldPop's input units line up with COD-AB barangays, plus WorldPop's within-unit modelling.
Barangay-level indicators for small barangays rest on weak population weights. The validity
assessment also shows that post-2020 WorldPop years carry no information on differences in
barangay change (rank correlation 0.05 with PSA POPCEN 2024 growth). Census-anchored weights
(its proposal P1) are implemented since Milestone 02B (Section 2).

## 8. Barangay indicators and reliability flags

For every barangay, mode and indicator group, weighted by the primary weights of the barangay's
cell pieces:

- `mean_min`: population-weighted mean time, **connected** residents
- `p90_min`: population-weighted 90th percentile, connected residents (replaces `max_min`, which was
  the value of one cell)
- `pct_le<N>`: share of **all** residents within N minutes (walk 10/15/30; drive 5/10/15).
  Residents without a valid connection are neither within nor beyond, so
  `pct_le<N> + pct_gt<N> + pct_not_connected = 100`. They are never forced onto the network.

Also reported: `pop_total`, `pop_connected`, `pop_not_connected`, `pct_not_connected`,
`pop_drive_access_gt_flag`, and the population columns of `barangay_population.csv`.

The thresholds are **analytical reporting thresholds, not official service standards**.

**Reliability** is reported per dimension, with the values and a reason, and never as a single
score:

| Column | Measures | low | caution |
|---|---|---|---|
| `rel_population` | Barangay totals and population-based quantities | ≤ 5 cell centres (totals change 15–26% with the allocation rule), or census residents that cannot be placed | 6–10 cell centres, or census / WorldPop 2020 factor outside 0.5–2.0 (WorldPop's units do not match the barangay, so its within-barangay pattern is uncertain) |
| `rel_network` | Residents without a valid walk connection | > 5% | > 1% |
| `rel_facility_inventory` | Completeness of mapped facilities | `unverified` everywhere until an official registry is matched; measurable parts in `facility_inventory.csv` and the reasons | |
| `rel_overall` | Most restrictive of population and network, with every reason | | |

The criterion "|WorldPop − census| > 50%" applies only when WorldPop totals are the primary weights:
under census anchoring, barangay totals equal the census. `pop_ranking_eligible` (population and
network not `low`) marks which barangays may be ranked on population-based quantities. Travel-time
means of the others are kept and mapped, because they are stable to the allocation rule (median
change 0.2 min). Thresholds are in `reliability:` in `settings.yaml`.

District aggregates (validity assessment P2) need a barangay→district table, which no current
source provides; they are not computed.

## 9. Quality assurance

Every stage writes checks to `data/interim[/<run>]/qa/<stage>.json`, collected in `qa_report.md`.
**PASS/WARN** means a stated condition was tested; **info** means a value is reported without a
threshold. Milestone 02 removed two checks that could not fail:
- facility counts "≥ 5 = PASS";
- "unreachable population = 0", which was true by construction.

It added checks that can fail:
- origin connection share
- facilities not connected
- connected cells without a time
- conservation of population
- speed-class fallback
- largest-component share
- small-barangay population bias

Milestone 02B adds: census anchoring equals the census, unallocated census residents, piece
fractions ≤ 1, external destinations used / not connected, and merged-edge speed classes. In the
3 km baseline the only WARNs are the 13 unconnected facilities, all outside the city (mostly on
Guimaras).

**`abot audit`** re-checks a finished run without changing anything: no download, no write under
`data/`. It covers the configuration; raw-file SHA-256 against the manifest; presence of every layer
and file; staleness (stage order, configuration fingerprint per stage, code changed after a stage,
OSM buffer of the outputs = configured buffer); consistency (conservation, census anchoring,
denominators, CSV = GeoPackage, reliability flags reproducible); the validity diagnostics; and
archive hashes. Each finding is PASS / WARN / FAIL / INFO with an action; the exit status is 1 on any
FAIL.

**`abot review`** writes manual-review files for possible duplicate facilities and unconnected
cells, with maps (Section 6.4 and 5). Their decisions are not read by the pipeline.

## 10. Experiments

Experiment configs in `config/experiments/` extend the baseline and write to their own folders:
`data/interim/<run>`, `data/processed/<run>`. `abot compare` produces a city-wide, barangay-level
and cell-level comparison of two runs.

| Config | Purpose |
|---|---|
| `hist_buffer_1km.yaml` | Historical 1 km buffer; with the default (3 km) it is the current E7 comparison |
| `e7_buffer_3km.yaml` | The original E7 run (now identical to the default). Its Milestone 02 outputs are archived with SHA-256 in `data/archive/hist_e7_buffer_3km_m02/` (Milestone 04). The originals were removed after verification in the M04 follow-up; the config is kept, and a rebuild would write new outputs with the current code |
| `sens_maxspeed_override.yaml` | Attribution: the Milestone 01 speed rule (tagged maxspeed replaces the class speed) on the current baseline. Regenerated in Milestone 03; the stale 1 km outputs are archived in `data/archive/stale_sens_maxspeed_override_m02_1km/` |

Built-in sensitivity: `accessibility.drive_network_time_factors: [1.5, 2.0]` multiplies the
drive-network leg (walk legs unchanged) and writes `drive_speed_sensitivity.csv`. A simplified edge
that spans several road classes takes the slowest configured class, which makes builds
deterministic (Milestone 02B fix).

## 11. Known limitations (current)

1. **Facility inventories are not verified** against any registry. All results are "access to
   mapped facilities".
2. **No public transport.** Jeepneys and tricycles are the main modes for many residents.
3. **Car times are modelled uncongested lower bounds.** There are no delays, and the speeds are
   assumptions. Hospital ≤ 10 min falls from 79.6% to 38.5% of residents at 2× network time.
4. **One walking speed (4.5 km/h).** Results for slower walkers, such as older adults or people
   carrying loads, would be considerably worse; see the audit (C-14).
5. **Population within barangays is modelled.** Barangay totals are fixed at the 2020 census;
   POPCEN 2024 is not yet integrated. 27 barangays have `rel_population = low`.
6. **Barrier data come from OSM.** Missing water features or missing paths affect connections in
   both directions. Gates, fences, mangroves and flooding are not modelled. *Milestone 04:* gate
   access tags are recorded (703 gates) but not used by the router, and `access=no` ways are routed
   (§3.1).
7. **Representative points** stand in for facility entrances.
8. **Same-edge shortcuts** are handled for walking only.
9. **Largest-component filter (Milestone 04).** 4,731.7 connected residents get citywide times only
   through a straight connector past an unlinked fragment. The active baseline (A1) is therefore the
   **optimistic connectivity scenario** (not a verified upper bound). The A3 reporting layer treats
   them as locally connected, which is conservative for gated subdivisions whose real exit is
   unmapped. Neither is observed (§3.2, §3.3).
