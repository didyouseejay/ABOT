# ABOT — Milestone 04 follow-up: targeted Overpass candidate review

| | |
|---|---|
| **Date** | 2026-10-31 |
| **Status** | Evidence review and documentation fix in the working tree; **not committed** |
| **Snapshot** | `data/raw/osm_targeted/m04_gaps_20261031T131445Z.json`, 1,117 elements, OSM base 2026-10-31T13:14:07Z, response SHA-256 `12922cd2d2c891594cec1ba51e043d48734f4cb00f7f46cba4594bf4a5c7ba86` (re-hashed: matches the sidecar and `manifest.json`; query SHA-256 `843479353ed4…` also matches). Not modified |
| **Applied** | **Nothing.** No way added to any graph, `access=private` not overridden, component classes, A1/A2/A3, population and accessibility results unchanged. No new download |

> **Note (2026-10-31):** access labels were revised after this review; see [MILESTONE_04_ACCESS_TAXONOMY.md](MILESTONE_04_ACCESS_TAXONOMY.md). The findings below are unchanged.

Labels: **[observed]** in the OSM snapshot or cache; **[derived]** computed from them;
**[unverified]** not established. "Physical connection" means connection in OSM topology (shared node
ids), which is a mapper's claim, not a site observation. Public pedestrian access is never inferred
from it.

## 1. Corridor geometry and endpoints

Method (`targeted.corridor_analysis`, reproducible with `abot components`): contact nodes are OSM
node ids shared between a candidate way and a way of a component in the walk cache. Routes are the
shortest path along candidate ways only. Crossings without a shared node were also searched, and
barrier ways crossing the corridor were searched separately (none found for either group).

### Group 1: Baybay Tanza (F100, F101) via the Iloilo Fishport service roads

- **15 ways [observed], all `highway=service` + `access=private`**, including `service=driveway`
  (way/821502012) and `service=parking_aisle` (way/1479306991). Named ways are "Iloilo Fishport
  Access Road" (way/70510020, 821502000 with `oneway=yes`, `sidewalk=right`, `lit=yes`, concrete;
  143471848, 821502001). Last edits 2026-07-08 and 2026-07-16 (versions 2–14).
- **Main-network contacts [observed]: 2 nodes, both gates.** node/13997351389 (10.691284 N,
  122.556270 E) and node/13997351390 (10.691281, 122.556371) are tagged `barrier=gate` +
  `access=private`. Each is the end node of a main-network way (way/1536557833, 1536557834: the
  untagged public section of "Iloilo Fishport Access Road").
- **F100 contact:** node/13997365110 (10.689621, 122.556331), the end node of F100's
  `highway=pedestrian` way/1536495016. **F101 contact:** node/13997365180 (10.689075, 122.559407),
  the end node of F101's `service=driveway` way/1536495025.
- **Shortest routes [derived]:** F100 → main 184.1 m (way/821502001 → way/70510020). F101 → main
  579.0 m (way/143471848 → 821502012 → 143471848 → 821502001 → 70510020). **Both end at the private
  gate node/13997351390.** Since every main-network contact is a private gate, every route passes one.
  Two more private gates lie on the corridor (node/13570471150, node/13570471151).
- Crossings without a shared node: none.

### Group 2: Tabuc Suba subdivision (F001) via Gustilo Street

- **4 ways [observed], all `access=private`:** way/675593702 **Gustilo Street**
  (`highway=tertiary`, `maxspeed=30`, 1,006 m, v12, 2024-12-19); way/821331717 (`tertiary`,
  unnamed, 258 m); way/224757876 and way/224757880 (`residential`, 99 m and 68 m, each ending in a
  `noexit=yes` node: dead-end private spurs).
- **Gustilo Street is the subdivision's spine.** It shares **8 nodes with F001 streets** (Pasacao St,
  Nasipit/Pagadian, Santa Clarita Lane, Bislig St and unnamed residential ways); 6 of the 8 are
  end nodes of those streets. The F001 streets hang off a road the walk filter removed, which is why
  F001 appeared as an isolated network.
- **South entrance:** Gustilo Street's first node, node/8370360597 (10.717599, 122.572326), is
  `barrier=gate` + `access=private`. It is also the end node of the **public** section of Gustilo
  Street in the main network (way/1149566668, `tertiary`, no access tag). The mapped public road ends
  at a private gate, and the road continues as private.
- **North link [derived]: 86.9 m along way/821331717** from F001 node/1135567593 (10.724542,
  122.576275; end of F001 way/222411748 and of Gustilo Street) to main node/2335022254 (10.724974,
  122.576931; an interior node of main residential way/224708063). It also touches main
  node/2335022195 and node/2335022234 (ends of ways 996818775 and 224708045). **No gate is mapped on
  this link**, but the way is `access=private`.
- Crossings without a shared node: none.
- The earlier cache-only finding still stands: the 10.9 m gap further north (10.7276 N) is a pair
  of `noexit=yes` dead ends with no way between them. The snapshot adds no way there. F001's mapped
  connections are the private Gustilo Street corridor, not that gap.

## 2. Candidate classification (evidence-based; component classes not changed)

| | F001 (Tabuc Suba) | F100 (Baybay Tanza) | F101 (Baybay Tanza) |
|---|---|---|---|
| Residents attached (A3) | 2,382.9 (69 cells) | 560.7 (14 cells) | 79.6 (3 cells) |
| **Physical connection** | **Confirmed in OSM topology** (shared nodes; south via the gated Gustilo St, north via way/821331717). Not field-verified | **Confirmed in OSM topology** (shared node with the fishport road). Not field-verified | **Confirmed in OSM topology**. Not field-verified |
| **OSM access restriction (exact tags)** | Ways: `access=private` (+ `highway=tertiary`, `maxspeed=30`, `name=Gustilo Street`; `highway=tertiary`; `highway=residential` ×2). Gate node/8370360597: `barrier=gate`, `access=private`. No `foot` tag anywhere | Ways: `access=private` + `highway=service` (one `service=driveway`, one `service=parking_aisle`). Route gate node/13997351390: `barrier=gate`, `access=private`. No `foot` tag | As F100 (same corridor, same gate) |
| **Public pedestrian access** | **Restricted according to mapped tags** | **Restricted according to mapped tags** | **Restricted according to mapped tags** |
| Field / authoritative information needed | **Yes**: whether residents walk out through Gustilo St (likely their own roads, but not verified), whether non-residents may enter, gate operation and hours, and whether the north link is gated on site | **Yes**: fishport pedestrian access rules (workers, vendors, neighbours), gate operation, and whether the attached residents live inside or beside the fishport compound | **Yes** (as F100) |
| Reading [derived] | Not a missing link: a **private, gated subdivision** whose access roads are mapped and removed by the walk filter. For non-residents it is not public. For its own residents it is plausibly their exit (resident-restricted access), which is an **assumption** | A **restricted non-residential facility** (fishport compound) between the fragments and the public road. Use by the attached residents is **unverified** | As F100 |

**Not changed:** F001 stays `isolated_mapped_dead_end` and F100/F101 stay `small_fragment` in the
inventory (`component_class_changed_by_snapshot = False`). A3 still reports these residents as
locally connected. No candidate way was added to any graph.

## 3. Why the generated documentation was stale, and the fix

**Cause.** In `components.build`, `gap_investigation()` ran **before** the snapshot was read, and
it wrote two fixed values: `cache_can_show_private_ways = False` and *"requires the targeted Overpass
snapshot (not obtained)"*. `write_readme()` received no snapshot information, and its section title
was fixed as "Gap investigation (cache evidence only)". The snapshot's results reached
`snapshot_*.csv` and `snapshot_status.json` but never the gap table or the README.

**Fix** (`src/abot/components.py`, `src/abot/fetch/targeted.py`):
- The snapshot is read first. `gap_snapshot_evidence()` returns its status and corridor analysis, and
  both feed the gap table and the README.
- `gap_investigation.csv` separates `cache_*` columns (measured on the walk-filtered cache, with its
  scope stated) from `snapshot_*` columns (obtained, file, physical connection, link length, ways,
  access tags, gates, public pedestrian access). `component_class_changed_by_snapshot = False` is
  explicit. `remaining_unverified` now depends on the actual state (no snapshot / snapshot without a
  link / snapshot with a restricted link).
- The README has a "cache-only measurements" section and a "Targeted snapshot evidence" section
  (obtained, SHA-256, OSM base, candidates identified, the corridor table). It states that physical
  connection is judged from topology and public access from tags only.
- `snapshot_status.json` gains `obtained`, `requested_utc` and `elements`. When no snapshot is present,
  stale `snapshot_*.csv` files from an earlier run are deleted, so old evidence can never be read as
  current.
- New output `snapshot_corridor_analysis.csv` (§1, §2).

**Regeneration check.** Before and after re-running `abot components`, 33 of 35 hashed files were
byte-identical: the baseline outputs, the A3 layer, all other M04 evidence, the raw snapshot and the
review CSVs. Only `gap_investigation.csv` and `snapshot_status.json` changed, as intended, plus the
new corridor file and the README. Under `PYTHONHASHSEED` 0 and 12345, all 20 `review/m04` files are
byte-identical.

## 4. Methodology observation (reported, not implemented)

> **Resolved (2026-10-31, M04 methodology review).** The labels below were replaced (see [MILESTONE_04_ACCESS_TAXONOMY.md](MILESTONE_04_ACCESS_TAXONOMY.md)). The refinement suggested here (deciding a residential context from land use or from the component) was **not** adopted: access permissions are not inferred from land use, road names or road class. `access=private` is now `private` with `authorized_group=unspecified` on every road class, Gustilo Street included. The "plausibly their exit" reading in §2 is an assumption for a future authorised-user scenario, not a classification.

The approved access classes treat `access=private` as **resident-restricted** on `residential`,
`service` and `living_street` roads. The fishport's `highway=service` + `access=private` roads are
therefore labelled `resident_restricted`, but a fishport is not a residential area: the restriction
applies to its workers and authorised users. Gustilo Street (`tertiary` + `access=private`) is
labelled `private_uncertain`, although it is the spine of a residential subdivision. **Possible
refinement, requiring your approval:** decide residential context from the surrounding land use or
from the component (e.g. a fragment made of residential streets), not from the highway class of the
private way alone. Until then, read these labels with this caveat.

## 5. Tests and checks

| Check | Result |
|---|---|
| `pytest` | **165 passed** (159 + 6 new) |
| `ruff check` | clean |
| Snapshot integrity | SHA-256 of response and query match the sidecar and the manifest |

New tests: a private, gated corridor is physically connected but `restricted_by_mapped_tags`, never
applied, and field verification is required; a corridor without access tags stays `unverified`
(never public); a `foot=yes` override does not mark it restricted but still requires field
verification; the wording of `remaining_unverified` for each snapshot state (no "not obtained" when a
snapshot exists); an absent snapshot removes stale tables and reports cache-only; the README section
matches the evidence (obtained, candidate count, physical vs public distinction).

## 6. Decisions for you

1. **F001:** whether, and how, to represent "resident-restricted connection for the subdivision's own
   residents" (e.g. a separate A3 category or scenario). This is a methodology change; not done.
2. **F100 / F101:** field or authoritative information on fishport pedestrian access before any change.
3. **Access-context rule (§4):** refine, or keep with the caveat.
