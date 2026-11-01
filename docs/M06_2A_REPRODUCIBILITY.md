# M06.2A — Fresh-Clone Workflow Audit and Reproducibility Engineering

- **Date:** 2026-11-02.
- **Base:** `main` at `3073524` (Milestone 06.1), clean working tree. The installed bundle was
  exported from that commit (`clean: True`).
- **Question:** M06.1 reported that `abot export-dashboard` fails on a fresh clone unless
  `abot fetch-gaps --allow-download` has run first. This milestone traces that dependency, decides
  whether it is intended, and fixes it only if justified.

**Summary**
- **Defect, not an intended requirement.** The targeted snapshot is optional evidence. It never
  changes an indicator: the code proves this, and a run without it produced byte-identical A3
  files. `abot components` explicitly supports running without it. Only the exporter's list of
  required sources (V-S1) demanded the snapshot-only corridor table.
- **Fixed with a small exporter change.** The snapshot is now an *explicitly declared optional*
  input, checked by a new rule V-S5 (contract 1.0.1).
- **Second latent defect fixed in the same change.** A snapshot with no link candidate would have
  crashed the export.
- **Two more fresh-clone blockers found.** They are documented, not changed, because both are
  integrity checks against the author's local archives (§3.3) and changing them needs the author's
  decision.

---

## 1. Existing command execution flow

| Order | Command | Reads | Writes | Network |
|---|---|---|---|---|
| 1 | `abot fetch` | HDX CKAN API, WorldPop | `data/raw/{cod_ab,census_2020,worldpop}/`, `data/raw/manifest.json` | Yes |
| 2 | `abot build` | raw files; Overpass (osmnx, cached in `data/raw/osm_cache/`) | `data/interim/`, `data/processed/abot_iloilo.gpkg`, CSVs | Yes, first run |
| 3 | `abot report` | processed outputs | `qa_report.md`, `abot_map.html` | No |
| 4 | `abot review` | processed outputs; existing review files (decisions carried over) | `data/processed/review/*` incl. `possible_duplicates_review.csv` | No |
| 5 | `abot validate` | Overpass cache only (inside `offline()`) | `data/processed/review/m03/` incl. `validation.gpkg`, `network_fragments.csv` | No (refused) |
| 6 (optional) | `abot fetch-gaps [--allow-download]` | `review/m03/network_fragments.csv`, `validation.gpkg` | without the flag: nothing (dry run). With it: one POST to `overpass-api.de` → `data/raw/osm_targeted/m04_gaps_<UTC>.{json,overpassql,meta.json}` + `osm_targeted/…` entry in `data/raw/manifest.json` | **Yes, only with the flag** |
| 7 | `abot components` | Overpass cache (inside `offline()`), GeoPackage, `osm_targeted/` (latest snapshot, if any), `data/archive/review_m04_pre_access_taxonomy/` (if present) | `data/processed/component_aware/*` (A3 layer), `data/processed/review/m04/*` | No (refused) |
| 8 | `abot audit` | everything above, `data/archive/` | nothing | No |
| 9 | `abot export-dashboard` | the sources of contract §7.1.1, in-process audit | `data/processed/dashboard/v1/` | No |

`fetch-gaps` must run **after** `validate` (it reads the M03 fragments) and **before** `components`
(which reads the snapshot). The M06.1 README order was correct.

## 2. The dependency and its missing-input behaviour

### 2.1 What the targeted snapshot produces

`abot components` → `gap_snapshot_evidence` (`components.py:831`):

| Snapshot present (`load_latest` finds `osm_targeted/m04_gaps_*Z.json`) | Snapshot absent |
|---|---|
| Writes `snapshot_gap_elements.csv`, `snapshot_link_candidates.csv`, `snapshot_corridor_analysis.csv` | **Deletes** those three files, so stale evidence can never be read as current (docstring) |
| `snapshot_status.json`: `obtained: true`, file, `response_sha256`, `timestamp_osm_base`, `link_candidates`, … | `snapshot_status.json`: `obtained: false` and a note naming `abot fetch-gaps --allow-download` |
| `gap_investigation.csv`: `snapshot_*` columns filled from the corridors | `snapshot_physical_connection = not_examined`; `remaining_unverified` says no snapshot is present |

### 2.2 The snapshot cannot change an indicator

- **Order of operations.** In `components.build` the component classes come from the Overpass cache
  only (`component_inventory`, lines 651–653). The A3 layer is written at line 687
  (`write_a3_layer`). The snapshot is read only at line 815, after every indicator file has been
  written.
- **Stated intent.** `gap_investigation`'s docstring says "The component class is never changed by
  the snapshot", and the column `component_class_changed_by_snapshot` is hard-coded `False`. The
  `targeted.py` metadata records "Evidence only; never used by the network build."
- **Observed.** In the isolated run (§6.2), `abot components` without the snapshot produced
  **byte-identical** files to the real snapshot run for:
  - `cells_a3.csv`, `barangay_access_a3.csv`, `citywide_a3.csv`;
  - `approach_comparison.csv`, `component_inventory.csv`, `transition_A1_to_A3_pop.csv`,
    `access_impact.csv`.

  Only `gap_investigation.csv` differed.

### 2.3 What the exporter did with the absence (before this milestone)

| Exporter step | Behaviour without a snapshot | Verdict |
|---|---|---|
| `source_paths` (contract §7.1.1, check V-S1) | listed `snapshot_corridor_analysis.csv` unconditionally | **Blocks:** `V-S1: missing source data/processed/review/m04/snapshot_corridor_analysis.csv`, nothing written (observed, §6.2) |
| `load` | `pd.read_csv(…snapshot_corridor_analysis.csv)` unconditionally | would raise `FileNotFoundError` (unreachable behind V-S1) |
| `build_network` › `gap_evidence` | already handles a fragment with no corridor row (`c is None` → path fields `null`, `applied: false`) | ready |
| `build_provenance` › `targeted_snapshot` | already `None` when the raw manifest has no `osm_targeted/` entry | ready (contract typed it as non-null) |
| Frontend | `NetworkPage` renders missing gap fields as "—" or empty (React renders `null` as nothing); `validate.ts` does not check them; `targeted_snapshot` is not read. The TypeScript type of `classification_reason` says `string`, but the value can be `null` | works; a type correction is noted as a follow-up |

**Second latent defect.** With a snapshot that yields **no** link candidate, `components` writes
`pd.DataFrame().to_csv()`, a file containing only a line break. `pd.read_csv` raises
`EmptyDataError` on it (reproduced), so the export would have crashed.

### 2.4 Classification

Was the requirement intended? The evidence says no:
- `components` deliberately supports the absent state and deletes the tables;
- the exporter's builders already handle absence;
- the snapshot never changes an indicator.

The contract's source list was written from the discovery run, in which the snapshot existed, so
it recorded an optional input as required. This is a **missing optionality declaration**, not a
methodological requirement.

## 3. Fresh-clone reproducibility assessment

### 3.1 What a fresh clone needs

- **Downloads:** about 550 MB from HDX and WorldPop, plus live Overpass queries for the network,
  facilities and barriers. The OSM results depend on the day (not pinned).
- **Manual inputs** that live only in git-ignored `data/`:
  - reviewer decisions (`review/review_decisions_log.csv`, 7 approved duplicate decisions);
  - the Milestone 03 review files.

  On a fresh clone `abot review` starts with all **14** duplicate pairs pending (the published
  bundle says 7). This changes the `DQ-DUP` statement, not any indicator.
- **Local archives** (`data/archive/`): see §3.3.

### 3.2 Can a fresh clone produce a valid bundle without the targeted query?

| Blocker | Before M06.2A | After M06.2A |
|---|---|---|
| Corridor table required (V-S1) | Blocks | **Resolved** (§5) |
| Snapshot without link candidates (`EmptyDataError`) | Would crash | **Resolved** |
| V-S4: `taxonomy_check.json` must report `identical: true`, 112 components | Blocks: without `data/archive/review_m04_pre_access_taxonomy/`, `components` writes "reference absent: not compared" (observed) | **Still blocks** (§3.3) |
| Audit gate: `m01_archive_present` is **FAIL** without `data/archive/m01_3edc0dd/` | Blocks | **Still blocks** (§3.3) |

**Answer: not yet.** The snapshot is no longer required. A fresh clone is still blocked by two
archive-dependent integrity checks.

### 3.3 The archive-dependent checks (documented, not changed)

Both checks are deliberate regression guards for the author's machine:
- V-S4 proves the M04 access-taxonomy refactor left all 112 component classes unchanged.
- `m01_archive_present` proves the Milestone 01 record has not been lost.

On a fresh clone they cannot pass, because the archives are made from earlier runs and are not
distributed (`data/` is git-ignored). Two problems follow:
- "restore it from backup" is the wrong advice on a fresh clone;
- the only way round them is `--skip-audit`, which is recorded as `not_run`, and V-S4 cannot be
  skipped at all.

Changing them weakens a safeguard the author relies on, so it is a policy decision for the author.
The smallest safe correction (proposed, **not implemented**):
- **V-S4:** accept `taxonomy_check.reference: null` (the archive was absent and the comparison not
  made) as a *visible* state:
  - record `component_classes_check.identical: null`;
  - add a known issue, for example `TAXONOMY-NOT-COMPARED`;
  - keep refusing `identical: false`.

  This is a contract minor change (1.1.0) because the dashboard should display the new known issue.
- **Audit:** report `m01_archive_present` as **WARN** ("no archives in this checkout: historical
  comparisons unavailable") when `data/archive/` does not exist at all. Keep **FAIL** when
  `data/archive/` exists but the M01 archive is missing, which is the author's real loss case.

## 4. Alternatives considered

| | Option | Methodology | Reproducibility | Network | User experience | Verdict |
|---|---|---|---|---|---|---|
| A | Declare the snapshot a **required** input, with validation and setup instructions | Unchanged | Every reproduction needs a live, dated query, so results differ by date for evidence that never affects an indicator | Mandatory extra request | Clear, but forces a download for optional evidence | Rejected: it hard-codes an optional input as required |
| B | Exporter **handles absence** where the outputs do not need it | Unchanged; the snapshot never affects indicators (§2.2) | Fresh clone no longer needs the query | None added | Works offline; absence visible as `not_examined` / `targeted_snapshot: null` | **Chosen, with A's explicit declaration**, so absence is never silent |
| C | Offline workflow with a **versioned, licensed fixture** | Unchanged | Pins the evidence | None at run time | Best for exact reproduction | Deferred. The snapshot is OSM-derived (ODbL 1.0). Redistribution needs ODbL terms and attribution, and the project has no data-distribution policy or release channel yet. Belongs with the broader snapshot-release decision (audit M3), not this fix |
| D | Exporter **runs `fetch-gaps` automatically** | Unchanged | Results depend on the export date | **Hidden network request** in a "read-only" command | Surprising; fails offline | Rejected: contradicts the exporter's read-only design (R14) and the brief |

## 5. Recommended solution and justification

**B with an explicit declaration** (contract **1.0.1**, patch):
1. `snapshot_status.json`, which `abot components` already writes on every run, becomes the
   **declaration** and a listed source (§7.1.1).
2. The corridor table is a source **only when a snapshot is declared**. When it is declared and
   missing, V-S1 still blocks.
3. New check **V-S5** refuses every inconsistent state, with "re-run `abot components`":
   - `obtained` missing or not boolean;
   - a corridor table left over while no snapshot is declared;
   - an empty corridor table while the status records link candidates;
   - `gap_investigation.snapshot_obtained` disagrees with the declaration;
   - the latest `osm_targeted/` entry in `data/raw/manifest.json` is not the snapshot that was used
     (a snapshot downloaded after `components`, or a newer one).
4. A snapshot with zero link candidates is read as an empty table, as the status declares.

**Why this approach:**
- Indicators are untouched.
- No input is silently omitted: absence must be declared, and it is visible in the bundle.
- No network request is added.
- The change is confined to the exporter's input handling.

**Contract version:** §14 lists validation additions as a patch.
- `targeted_snapshot: null` and `null` path fields were already produced by the 1.0.0 code. 1.0.1
  documents them.
- The dashboard treats any patch difference as compatible, so no frontend change is needed.

## 6. Changes implemented

| File | Change |
|---|---|
| `src/abot/dashboard_data.py` | `SNAPSHOT_STATUS`, `CORRIDORS`, `CORRIDOR_COLUMNS`; `snapshot_declared()`, `load_corridors()`, `snapshot_checks()` (V-S5, called from `source_checks`); conditional corridor source; `Sources.snapshot_status`; `CONTRACT_VERSION` 1.0.1 |
| `src/abot/cli.py` | Help text: contract 1.0.1 |
| `tests/test_m06.py` | 10 new tests (§7.1) |
| `docs/DASHBOARD_DATA_CONTRACT.md` | 1.0.1: §7.1.1 conditional source, `gap_evidence` and `targeted_snapshot` nullability, V-S5, revision record; header no longer lists Chart.js |
| `README.md`, `docs/ARCHITECTURE.md` | `fetch-gaps` documented as optional; the archive-dependent blockers stated; contract 1.0.1 |
| `Documentation.md` | Change-log entry |

**Not changed:**
- `components.py`, `targeted.py`, `audit.py` and the frontend;
- every analytical output and the installed bundle (still 1.0.0, from `3073524`, current);
- `data/archive/`.

### 6.1 Effect on the current validated dataset

The current data declares a snapshot (`obtained: true`, 3 corridor rows), and V-S5 passes on it
(observed, read-only). A re-export will differ from the installed bundle only in:
- `contract_version` 1.0.1;
- one more `source_files` entry (`snapshot_status.json`);
- timestamps and commit.

No indicator changes. An export with the real data to a temporary folder, through the
no-snapshot path, gave identical `city`, `barangay_indicators`, cells and facilities values
(test below).

## 7. Tests and verification

### 7.1 New tests (`tests/test_m06.py`, all passing)

1. No snapshot declared: an empty corridor table with the expected columns. The corridor table is
   not a source, the declaration is, and V-S5 passes.
2. Snapshot declared: the corridor table is a required source and is read; V-S5 passes.
3. Snapshot with zero link candidates: the exact file `components` writes is read as empty, and is
   refused if the status claims candidates.
4. Missing or invalid declaration: both files are reported by V-S1, and V-S5 refuses `{}` and a
   non-boolean `obtained`.
5. to 9. Five inconsistent states, each refused by V-S5:
   - a stale corridor table;
   - a mismatched gap table in each direction;
   - a snapshot downloaded after `components`;
   - a newer snapshot than the one used.
10. End to end on the real outputs (skipped without data): the export succeeds with a simulated
    no-snapshot state, written to a temporary folder only. The gap evidence is `not_examined` with
    `null` path fields, `targeted_snapshot` is `null`, and the indicators equal the installed
    bundle's.

### 7.2 Isolated workflow run (not a fresh clone)

Performed in a scratch folder outside the repository, with:
- the code extracted with `git archive HEAD`;
- a copy of `data/raw`, `data/interim` and `data/processed` **without** `osm_targeted/`, its
  manifest entry, or `data/archive/`.

`PROJECT_ROOT` resolved to the scratch folder, so nothing in the repository was read or written.
`abot components` ran inside its `offline()` guard, so no request was possible.

| Step | Code | Result |
|---|---|---|
| `abot components` (no snapshot, no archives) | HEAD | exit 0, 160 s; `snapshot_status.obtained: false`; corridor table removed; A3 files byte-identical to the real run |
| `abot export-dashboard` | HEAD | **exit 1**: `V-S1: missing source …/snapshot_corridor_analysis.csv` (the M06.1 finding, reproduced) |
| `abot export-dashboard` | fixed | **exit 1**: `V-S4: taxonomy_check None, None components` (archive blocker, §3.3) |
| archives copied in, `abot components` re-run, `abot export-dashboard` | fixed | **exit 0**: audit 56 PASS · 10 WARN · 0 FAIL; all checks passed; 9 files |

In the resulting scratch bundle:
- `gap_evidence` is `not_examined` for F001, F100 and F101;
- `targeted_snapshot` is `null`;
- `city.json` (population, walk, walk_internal, walk_distribution, drive, facility_inventory),
  `barangay_indicators.json`, both cell chunks and `facilities.geojson` equal the installed bundle;
- in `network.json`, only `gap_evidence` differs.

The 7 extra WARNs are artifacts of copying: the copied code files are newer than the copied stage
outputs ("changed after the stage ran"). The `7 pending` duplicates come from the copied review
decisions.

**Not performed:** a true fresh clone with `abot fetch` and `abot build`. Those would download data,
which this milestone excludes.

### 7.3 Repository checks (run after the change)

- **pytest:** 240 passed (230 existing + 10 new).
- **ruff check:** passed. **ruff format --check:** the same 8 pre-existing files; the new test file
  is formatted.
- **Dashboard:** Vitest 81 passed; `npm run typecheck` clean. There is no frontend change.
- **Installed bundle:** `export-dashboard --check` still current, commit `3073524`, `clean: True`.

## 8. Remaining external data requirements

| Requirement | Needed for | Distributable? |
|---|---|---|
| HDX / WorldPop downloads (~550 MB) | everything | Yes, re-downloadable (CC BY / CC BY-IGO); hashes recorded |
| Live Overpass network, barriers, facilities | build | Re-queryable but not pinned. The original snapshot is ODbL; redistribution requires ODbL terms |
| Targeted gap snapshot | **optional** gap evidence | As above; now optional |
| Reviewer decisions (`review_decisions_log.csv`, M03 review files) | `DQ-DUP` and review status | Small, author-made, not OSM data; could be committed (decision for M06.2C) |
| `data/archive/m01_3edc0dd/`, `data/archive/review_m04_pre_access_taxonomy/` | audit gate, V-S4 | Derived from OSM (ODbL); not distributed. The checks need the change proposed in §3.3 |

## 9. Recommended next steps (M06.2B: GitHub Actions CI)

CI should verify what runs **without data**, and not pretend to reproduce the pipeline.

1. **Workflow** `.github/workflows/ci.yml`, on push and pull request to `main`, with two jobs.
2. **Python job** (`ubuntu-latest`):
   - `astral-sh/setup-uv` pinned to 0.13.6;
   - `uv sync --locked`;
   - `uv run ruff check src tests`;
   - `uv run pytest`.

   Data-dependent tests skip without `data/` (`HAVE_DATA`), including the end-to-end test above.
   Report the skip count in the job summary so a reviewer sees what ran.
3. **Dashboard job:**
   - `actions/setup-node` with Node 24 and npm cache;
   - in `dashboard/`, run `npm ci`, `npm run typecheck`, `npm test` and `npm run build`. The build
     succeeds without a bundle and prints a warning.
4. **Formatting:** either run `ruff format` once in its own behaviour-free commit and then enforce
   `ruff format --check`, or leave format out of CI until then. Do not make CI red on the 8 known
   files.
5. **Not in CI:**
   - `abot fetch`, `build`, `components`, `fetch-gaps` and `export-dashboard`: network, 550 MB and
     archives;
   - `uv lock --check`, which is covered by `uv sync --locked`.
6. **Badge:** add the CI status badge to the README.
7. **Small follow-up:** type `GapEvidence.classification_reason` (and the other path fields) as
   `string | null` in `dashboard/src/contract/types.ts`, so the types match contract 1.0.1.
8. **Before M06.2B, decide the §3.3 proposal**, the archive-dependent V-S4 and audit checks. It
   does not block CI, but it decides whether a later "fresh-clone export" job (M06.2C, with a small
   committed fixture or a release asset under the ODbL) is possible at all.
