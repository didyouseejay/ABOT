# ABOT — Milestone 04 methodology review: access taxonomy

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Approved and implemented in the working tree; **not committed** |
| **Scope** | Labels and evidence columns only. Walk graph, component membership and classes, A1/A2/A3 routing and categories, population allocation and facility travel times are **unchanged** (verified, §6) |
| **Offline** | No Overpass query. The targeted snapshot `data/raw/osm_targeted/m04_gaps_20261031T131445Z.json` is unchanged (response and query SHA-256 match its sidecar; audit `manifest_sha256` PASS) |
| **Code** | `src/abot/access.py` (new, shared), `src/abot/components.py`, `src/abot/fetch/targeted.py`, `src/abot/archive.py` |

## 1. The problem

The approved M04 follow-up classes mixed road function, mapped restriction and presumed user groups:

- `access=private` became **resident_restricted** on `residential`, `service` and `living_street`
  roads. `highway=service` describes what a road does, not who may use it. The Iloilo Fishport
  service roads would have been labelled "residents and visitors", which no tag supports. Only
  `access=residents` names residents.
- `access=private` on any other road became **private_uncertain**. Gustilo Street (`highway=tertiary`
  + `access=private`) was called "uncertain" although its restriction is explicit.
- **ineligible** mixed "prohibited" (`access=no`, `foot=no`) with "private" (`foot=private`).
- `access=customers` + `foot=permissive` was labelled plain **public** without a flag.
- `access=delivery` was labelled **destination**. Delivery is a purpose or vehicle restriction, not
  a pedestrian destination permission.
- The snapshot corridor analysis had its own rules, and marked a path restricted only when **all**
  of its ways were restrictive. One private way on the path is enough to make it non-public.

In the routed cache these labels had little numeric reach, because the osmnx walk filter drops
`access=private` and `service=private` ways before download. The cache held 0 `resident_restricted`
ways and 0 `private_uncertain` ways. The labels mattered on the 167 private **gate nodes** and in the
methodology text.

## 2. Four separate concepts

| Concept | Question | Where it is recorded |
|---|---|---|
| Physical connectivity | Do mapped geometries share nodes? | `physical_connection` (corridors), `snapshot_physical_connection` (gap table), component membership |
| Mapped access status | What do `access` / `foot` (and `service=private`) say? | `access_class` / `mapped_access_status`, `deciding_tag` |
| Public pedestrian status | May the general public walk it, as far as the tags say? | `public_pedestrian_status` |
| Authorised group | Which users does a restriction admit, as far as the tags name them? | `authorized_group` |

Plus `field_verification_required` and a traceable `classification_reason`. Connectivity is a
property of the topology, not of one way's tags, so it is not a per-way field.

## 3. Taxonomy (`abot.access`)

| Status | Tags | Public pedestrian status | Authorised group | Verify |
|---|---|---|---|---|
| `no` | `access=no` (no foot tag); `foot=no` | prohibited | none_permitted | no |
| `private` | `access=private`; `foot=private`; `service=private` with no access/foot tag | not_public | unspecified | yes |
| `residents` | `access=residents`; `foot=residents` | not_public | residents_named_by_tag | yes |
| `customers` | `access=customers`; `foot=customers` | customers_only | customers_named_by_tag | yes |
| `unknown` | `permit`, `delivery`, `unknown`, other values | unknown | unknown | yes |
| `destination` | `access=destination`; `foot=destination` | destination_only_assumed | destination_traffic | no (gates: yes) |
| `pedestrian_override` | `access` ∈ {private, residents, customers} with `foot` ∈ {yes, designated, permissive, public, official} | permitted_by_foot_tag_conflicting | the group named by `access` | yes |
| `untagged` | no access/foot tag | not_restricted_by_tags_unverified | not_applicable | no (gates: yes) |
| `public` | `access`/`foot` = yes, designated, permissive, public, official | permitted_by_tag | not_applicable | no |

**Precedence** (first match wins; the result does not depend on tag order):
1. `foot=*` decides for pedestrians. A public foot value combined with a group restriction in
   `access` (private, residents, customers) is a conflict, `pedestrian_override`. It is flagged and
   never treated as unrestricted public access. A public foot value with any other `access` value
   (`no`, a vehicle category such as `emergency`) is the standard pedestrian override and gives
   `public`. The reason records the override ("foot=yes takes precedence over access=no").
2. Otherwise `access=*` decides.
3. Otherwise `service=private` gives `private`. The reason notes that this is a road-function
   subtag, not an access tag.
4. Otherwise `untagged`. The reason states that this is not evidence of public access.

**Rules that hold throughout:**
- `highway=*` never changes the status. It is recorded in the reason as "recorded, not used".
- `access=private` names no group: `authorized_group=unspecified`.
- `permissive` means mapped permission that the owner may withdraw. It is not verified
  real-world access.
- **Gates** are assessed from their own tags with `gate=True`. A gate is a mapped access-control
  point. Its operating rules (hours, pedestrian wicket, staffing) are not mapped, and `locked=*` is
  quoted in the reason. Untagged, destination, customers, unknown and private gates require
  verification. Untagged gates are still **not excluded**.
- **Paths and corridors** take the most restrictive status of **any** way or gate on them. A path with
  no mapped gate gains nothing from that. F001's 87 m private way has no gate and is still `private`.
- **Merged edges** take the most restrictive status of their ways (`RANK`, as before).
- **Component rules** use the same groups as before: restricted = {no, private, residents}
  (formerly {ineligible, resident_restricted, private_uncertain}); customers/unknown share =
  {customers, unknown} (formerly {customers, uncertain}). `pedestrian_override` is in neither,
  as it previously counted as public.
- **Removal scenarios** (`access_impact.csv`) are defined on raw tags (`way_tag_flags`,
  `gate_tag_flags`), not on status labels, so their selections did not move.

## 4. Old-to-new crosswalk (every cached walk way and gate node)

The full table is `data/archive/review_m04_pre_access_taxonomy/crosswalk/access_taxonomy_crosswalk.csv`
(47 tag combinations, 11,851 elements). Changed labels:

| Element | Old class | New status | Tags | Count |
|---|---|---|---|---|
| way | ineligible | no | `access=no` | 52 |
| way | ineligible | private | `access=no` + `foot=private` | 2 |
| way | public | pedestrian_override | `access=customers` + `foot=permissive` (parking aisles, main component, 0.12 km) | 3 |
| way | uncertain | unknown | `access=permit` / `unknown` | 4 |
| gate | private_uncertain | private | `access=private` | 167 |
| gate | ineligible | no | `access=no`; `access=private` + `foot=no` | 31 |
| gate | ineligible | private | `foot=private` (with or without access) | 4 |
| gate | uncertain | unknown | `access=permit` | 2 |
| gate | destination | unknown | `access=delivery` | 1 |

**Component-rule group changed: 0 elements.**

## 5. F001, F100 and F101: unchanged findings, corrected labels

| | F001 (Tabuc Suba) | F100 / F101 (Baybay Tanza) |
|---|---|---|
| Physical connection | confirmed_in_osm_topology | confirmed_in_osm_topology |
| Path access status | private (shortest path: way/821331717, 86.9 m, no gate mapped; the corridor also holds Gustilo St way/675593702 and private gate node/8370360597) | private (fishport service ways; private gate node/13997351390) |
| Public pedestrian status | not_public | not_public |
| Authorised group | **unspecified** (the earlier "plausibly residents" reading is withdrawn as an inference) | **unspecified** |
| Component class | isolated_mapped_dead_end (unchanged) | small_fragment (unchanged) |
| A3 category of attached residents | locally_connected, 2,382.9 | locally_connected, 560.7 / 79.6 |
| Applied to any graph | no | no |
| Field verification | required | required |

### 5.1 Future F001 resident-egress scenario (documented, not implemented)

The question "can F001 residents leave through their own private roads?" is an **authorised-user**
question. It is not a public-access question, so it must never change A1, A3 or a citywide indicator.
A future implementation would be:

- **A separate, named scenario** (e.g. `S_auth_F001_egress`), written to its own folder and columns.
  It sits next to A3 and never inside it.
- **A manifest that states its assumptions:**
  - user group: residents of cells attached to F001
  - authorisation assumed, and its source (none yet)
  - ways opened: way/675593702 Gustilo St, way/821331717
  - one assumption per gate (open / pedestrian wicket / closed) and the time window
  - the population subset it applies to.
- **Bounds, not a point estimate:** report at least 0% and 100% of F001 residents authorised. Any
  intermediate share needs evidence.
- **Outputs:** travel times for the authorised subset only, labelled "under authorisation assumption
  X". They are never added to `network_connected` and never used for non-residents.
- **Limitations stated with the result:** tags do not establish membership, gate operation or hours.
  Visitors and non-residents are excluded by construction.

Until such evidence and approval exist, F001 residents stay `locally_connected` in A3.

### 5.2 Fishport access (F100, F101): evidence that would resolve it (not sought)

Retained: physical connection in OSM topology, mapped `access=private`, and private gates on every
route to the main network. The record does not say that nearby residents may pass, nor that every
pedestrian is barred at all times. Any one of the following would settle it:

1. The written access policy of the fishport operator (the Philippine Fisheries Development
   Authority / Iloilo Fishport Complex): gate hours, pedestrian rules, ID or pass requirements, and
   whether non-workers may pass.
2. A dated field verification at each private gate on the routes (node/13997351390 and the other
   corridor gates). It would record whether pedestrians pass, at which hours, under which conditions,
   and whether F100/F101 residents live inside or outside the compound, with photos and the
   observer named.
3. A city or barangay ordinance, or an official letter, on public passage through the compound.

Imagery alone cannot establish permission. Until then: `public_pedestrian_status=not_public` and
`authorized_group=unspecified`.

## 6. Verification

| Check | Result |
|---|---|
| Archive `review_m04_pre_access_taxonomy` (review/m04 20 files, component_aware 6, crosswalk 1) | 27 files; `archive.verify`: 0 archive mismatches, 0 source mismatches at archive time, 0 extra; audit PASS |
| Component classes, all 112 components (`taxonomy_check.json`, run inside `abot components`) | identical. Also identical: n_nodes, n_edges, length_km, gates_restricted, gates_untagged, share_restricted, share_customers_uncertain, gap_to_main_m, noexit_at_gap |
| Walk-graph topology fingerprint (nodes, edges with lengths, node set of each component, saved walk graph) | identical before and after: 15,376 nodes, 39,698 edges, 112 components |
| A3 CSVs (`cells_a3`, `barangay_access_a3`, `citywide_a3`) and A3 README | byte-identical |
| A3 GeoPackage | content-identical (180 and 8,035 rows); bytes differ because the file is rewritten |
| A3 `run_info.json` | only `created_utc` differs; `baseline_sha256` identical and equal to the files on disk; population 457,626.0 |
| Other M04 evidence (approach comparison, transitions, changes by barangay, cells changed, facilities by approach, near misses, facility review, snapshot elements/links/status, access impact by group) | byte-identical |
| `access_impact.csv` | numbers identical; only the clarified `definition` text of the two gate scenarios differs |
| Relabelled outputs | `access_classes.csv`, `access_classification_summary.csv`, `restricted_ways.csv`, `gate_nodes.csv` (new columns), `component_inventory.csv` (`km_*` renamed; restricted km sums equal; `class_reason` text), `gap_investigation.csv`, `snapshot_corridor_analysis.csv` (new columns), README |

Expected differences of the timestamp-only kind: A3 `run_info.json` `created_utc`, and the byte
content of the rewritten GeoPackage (same layers and values).

## 7. Tests

`tests/test_m04.py` 62 → 97 tests. All 200 pass. Tests that changed because they encoded the old
semantics:
- `test_access_class`: old labels; new cases added for tertiary/service + private, conflicts,
  delivery and unknown foot values.
- `test_access_classes_are_ordered_and_documented`: the new order and groups, and the old labels
  are absent.
- the `classification_summary` fixture: gate label.

New tests:
- private service road ≠ residents
- the highway class never changes the status (7 classes)
- private and untagged gates are not public and need verification
- missing tags ≠ explicit public
- `foot` override recorded
- permissive is revocable
- conflicts are flagged and order-independent
- the gate scenario flags match the old raw-tag definitions
- the exact component-class comparison raises on any difference
- `edge_table` leaves the graph topology untouched
- one private way (or a private gate) on a path makes it not public
- a path without a gate is not public evidence
- the F001 and fishport tag patterns stay physically connected, not public, group unspecified, not applied.
