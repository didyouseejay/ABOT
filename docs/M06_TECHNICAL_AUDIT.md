# M06.0 — Technical Audit and Portfolio Baseline

- Audit date: 2026-11-01; independently re-verified on 2026-11-02 (Appendix A lists what was re-run
  and the corrections made).
- Repository state: `main` at `56fbd64` (Milestone 05.3) on both dates. On 2026-11-01 the working
  tree was clean except for an untracked `.vscode/` folder. On 2026-11-02 it also held this report
  (untracked) and its uncommitted change-log entry in `Documentation.md`. No application code, data
  or configuration was modified on either date.
- Scope: the whole repository (Python pipeline, dashboard exporter, React dashboard, tests,
  configuration and documentation), assessed for coherence, reliability and portfolio readiness.
- Method: read-only inspection plus the existing checks. Every result in §1.1 was run and observed
  during this audit. Nothing was installed, regenerated, staged or committed. The frontend build was
  written to a temporary folder outside the repository, so `dashboard/dist/` was not touched.

---

## 1. Executive Summary

ABOT is technically stronger than most student portfolio projects. Its weakness is how it presents
itself.

- **The engineering is sound.**
  - The Python pipeline is deterministic, configurable and audited.
  - The exporter produces a versioned, hashed data bundle. It validates the bundle independently,
    installs it in an all-or-nothing step, and can recover from an interrupted run.
  - The React dashboard checks every file it loads against the bundle's manifest, and degrades one
    dataset at a time instead of failing as a whole.
  - Both test suites pass and test behaviour, not just code paths.
- **The static-JSON architecture is the right choice.** A REST API, PostgreSQL or PostGIS would add
  cost without serving any current requirement (§3.7).
- **An internship evaluator cannot currently see or run the project.**
  - The README describes Milestone 02B and does not mention the dashboard.
  - No document explains how to start the frontend.
  - There are no screenshots, no hosted demo, no LICENSE and no CI.
  - All data is git-ignored. A fresh clone therefore builds a dashboard that shows only "data could
    not be loaded", unless the reviewer downloads about 550 MB and runs the whole pipeline.
- **No Critical issues were found. Five High issues were found, all about presentation and
  reproducibility for outsiders, not correctness.**

### 1.1 Checks run during this audit

| Check | Command | Observed 2026-11-01 | Re-run 2026-11-02 |
|---|---|---|---|
| Python tests | `.venv/Scripts/python.exe -m pytest -q` | **230 passed** in 63 s | **230 passed** in 40 s |
| Python lint | `ruff check src tests` | **All checks passed** | **All checks passed** |
| Python formatting | `ruff format --check src tests` | **8 files would be reformatted**, 20 already formatted | Same: 8 / 20 |
| Lockfile consistency | `uv lock --check --offline` | Lockfile matches `pyproject.toml` (38 packages) | **Not re-run**: `uv` is not on the PATH of either shell available on 2026-11-02 |
| Frontend tests | `npx vitest run` (in `dashboard/`) | **81 passed**, 5 files | **81 passed**, 5 files |
| Frontend types | `tsc --noEmit` (both tsconfigs) | **No errors** | **No errors** (exit 0 for both) |
| Frontend build | `npx vite build --outDir <temporary folder>` | **Built**; 9 bundle files (10,186,929 bytes) copied, size and SHA-256 checked | Same; output in a session scratch folder, `dashboard/dist/` untouched |
| Analytical audit | `abot audit --skip-hashes` | **PASS 51 · WARN 3 · FAIL 0 · INFO 18** (archive hash checks skipped for speed) | Same |
| Bundle staleness | `abot export-dashboard --check` (writes nothing) | **Current**: sources, configuration, stage times and files match the manifest. The manifest records commit `5ed16d2` with `clean: False` | Same |

The tools in `.venv/Scripts/` were called directly because `uv` was not on the PATH of the shells
used for this audit (Git Bash on 2026-11-01; both Git Bash and PowerShell on 2026-11-02). The README's
`uv run …` commands therefore assume `uv` is installed and on the PATH, which the README should state
(H1).

`abot audit` writes a file only when `--output` is given (`audit.py`), and `export-dashboard --check`
only reads (`dashboard_data.check`). Both were confirmed read-only in the code before they were run.

### 1.2 Headline findings

| ID | Severity | Finding |
|---|---|---|
| H1 | High | The README is two milestones out of date and has no dashboard instructions |
| H2 | High | Nobody can see the dashboard without running the full pipeline: no demo, no screenshots, no sample data |
| H3 | High | No continuous integration: the 311 passing tests are invisible to a reviewer |
| H4 | High | No LICENSE file; the licence obligations of the published data (ODbL) are not stated for the dashboard |
| H5 | High | No single entry-point document explains the architecture to a newcomer |
| M1–M10 | Medium | Unused or misdescribed dependencies; bundle provenance records uncommitted code; OSM snapshot not reproducible from a clone; very large modules; no frontend interaction tests; and others (§8) |

---

## 2. Current System Architecture

### 2.1 Components

```
 External sources                    Python pipeline (src/abot, CLI `abot`)              Frontend (dashboard/)
 ─────────────────                   ───────────────────────────────────────            ─────────────────────
 OCHA COD-AB boundaries ─┐           fetch ──► data/raw (+ manifest.json, SHA-256)
 PSA 2020 census ────────┤             │
 WorldPop R2025A rasters ┤           build: boundaries → population → osm → accessibility
 OpenStreetMap/Overpass ─┘             │        (data/interim, data/processed/abot_iloilo.gpkg, CSVs)
                                       ├─ report / review / validate / components  (evidence, A3 layer)
                                       ├─ audit  (read-only PASS/WARN/FAIL, exit 1 on FAIL)
                                       └─ export-dashboard ──► data/processed/dashboard/v1/
                                              (contract abot-dashboard v1.0.0:            ──► vite/bundlePlugin.ts
                                               manifest + 8 datasets, SHA-256,                 dev: serves files
                                               audit gate, all-or-nothing install)             build: copies + verifies
                                                                                                  │
                                                                                     src/data/loadBundle.ts (verify,
                                                                                     validate, degrade per dataset)
                                                                                                  │
                                                                                     React pages + Leaflet maps
                                                                                     (+ OSM / Esri background tiles)
```

### 2.2 Size and layout (git-tracked files)

| Area | Files | Notes |
|---|---|---|
| `src/abot/` | 22 | About 8,800 lines of Python. The largest modules are `dashboard_data.py` (1,742), `components.py` (1,157), `audit.py` (877), `osm.py` (738), `validation.py` (737) and `review.py` (695) |
| `tests/` | 6 | 230 tests, organised by milestone (`test_m02.py` … `test_m05.py`) plus `test_core.py` |
| `dashboard/` | 63 | React 19, TypeScript 7 (strict), Vite 8; 81 Vitest tests |
| `config/` | 4 | `settings.yaml` (252 lines) and the `experiments/` configurations |
| `docs/` | 16 | About 400 KB of Markdown; with `Documentation.md` (114 KB) about 516 KB in total |
| `data/` | not tracked | About 920 MB locally: raw 535 MB, interim 88 MB, processed 102 MB, archive 195 MB |

### 2.3 Is the architecture coherent? (Phase 1)

**Yes.** The separation between the pipeline and the frontend is unusually clean.

- **The contract is the only interface.**
  - The frontend reads only the bundle described in `docs/DASHBOARD_DATA_CONTRACT.md`.
  - It never imports Python output files, never recomputes an indicator, and does not depend on the
    GeoPackage.
  - `src/contract/types.ts` and `version.ts` mirror the contract. Unknown major versions are
    rejected, and newer minor versions produce a warning.
- **Clear direction of ownership.**
  - Pipeline stages write only under `data/interim` and `data/processed`.
  - `export-dashboard` writes only under `data/processed/dashboard/`.
  - `audit` and `export-dashboard --check` write nothing (`load_settings(create_dirs=False)`).
  - The Vite plugin only reads the bundle.
- **Appropriate scope.** One city, 180 barangays and 8,035 population cells in the bundle.
  Everything runs on an 8 GB laptop (Documentation.md §4: a full build from the cache takes about
  40 s).

**One coherence gap:** the brief for this milestone lists Chart.js and react-leaflet as part of the
frontend. Neither is imported anywhere in `dashboard/src` (M2). The repository's own changelog says
so (Documentation.md: "Leaflet is used directly … not through react-leaflet"; charts are SVG), but
`package.json` and the environment section still list them.

---

## 3. Backend and Data Architecture Assessment (Phase 2)

### 3.1 Can the pipeline be run reproducibly?

**Yes for the author; only partly for an outsider.**

- **Code and dependencies.** `uv.lock` pins 38 packages, `.python-version` pins 3.13, and the lock
  check passes.
- **Determinism.** Documentation.md §9 reports byte-identical outputs under different
  `PYTHONHASHSEED` values. This audit did not re-run the pipeline to re-check it.
- **Parameters.** All parameters are in `config/settings.yaml`. A hash of the resolved
  configuration is recorded with each stage (`Settings.config_sha256`). Experiments `extends:` the
  baseline and write to their own folders.
- **Inputs.**
  - Census, boundary and WorldPop downloads are recorded in `data/raw/manifest.json` with SHA-256.
  - OpenStreetMap is fetched live from Overpass and cached by osmnx in `data/raw/osm_cache/`.
    Each response's `timestamp_osm_base` is recorded (`osm.track_overpass`).
  - Because `data/` is git-ignored and Overpass queries are not pinned to a date, **a fresh clone
    reproduces the method but not the published numbers.** Documentation.md §9 states this honestly.
    It is a real limitation for outside reproduction (M3).

### 3.2 Ownership and provenance of datasets

**Strong.**

- `data/raw/manifest.json` records the source URL, licence and SHA-256 of each download.
- Stage provenance and the configuration hash are written with each build.
- `data/archive/<name>.sha256.json` records hashes for every archived milestone, and `abot audit`
  verifies them.
- The bundle's `provenance.json` carries sources, licences, retrieval times and SHA-256, plus
  documents, limitations and QA checks.
- **Gap:** the current bundle's `manifest.code` records commit `5ed16d2` with
  `git_working_tree_clean: false`, which the dashboard shows as known issue `GIT-DIRTY` (M1).

### 3.3 Does the exporter validate its output adequately?

**Yes. This is the strongest part of the system.**

`src/abot/dashboard_data.py`:
- **Audit gate.** `abot audit` runs in-process before export, and a FAIL blocks the export. Skipping
  it requires `--skip-audit`, and the skip is recorded as `not_run`, never as passed.
- **Independent re-validation.** `validate()` (about 350 lines) re-reads every written file and
  re-checks it against the sources. This includes an independent recomputation check of the
  walking-time distribution (`distribution_failures`).
- **Determinism and size limits.** Output uses compact JSON that rejects NaN (`dumps`). Cell chunks
  are equal-count and stay under the 4,000,000-byte limit.
- **Safe install.** The bundle is written to `.v1.tmp-<id>`, validated, then swapped in. Recovery
  from a crash touches only directories that match `^\.v1\.(tmp|old)-[0-9a-f]{12}$`.
- **Staleness check.** `--check` compares sources, configuration, stage times and file hashes with
  the manifest, and writes nothing.
- **Tests.** `tests/test_m05.py` (30 tests) covers the audit gate, NaN rejection, chunking,
  crash/restore, owned-directory safety, Git parsing, and an end-to-end export with failed
  validation. The end-to-end test skips without data.

### 3.4 Does the frontend handle missing, invalid or unavailable data correctly?

**Yes, and it is thoroughly tested.**

- **Load order** (`dashboard/src/data/loadBundle.ts`): manifest → compatibility → per-file size and
  SHA-256 → envelope → cell reconstruction → structural validation.
- **Fatal versus per-dataset failure.** A failed manifest or `city.json` is fatal. Any other dataset
  is marked failed with its reasons, and the rest of the dashboard keeps working. The cell layer is
  complete or disabled, never partial.
- **Without Web Crypto** (pages not served over https or localhost), the loader shows a visible
  "not verified" state but still checks sizes.
- **Tests** (`test/loadBundle.test.ts`, 32 cases) cover:
  - wrong hash;
  - a different `generated_utc`;
  - a missing, duplicated, out-of-order or miscounted chunk;
  - unknown indicator ids;
  - unresolved statement codes;
  - a string where a number was expected;
  - a malformed distribution;
  - a bundle claiming a failed audit;
  - another major version.

### 3.5 Are data integrity and bundle versioning enforced?

**Yes, at three independent points:**
1. the exporter validates before installing;
2. the Vite build re-checks each file's size and SHA-256 while copying (`vite/bundlePlugin.ts`,
   tested);
3. the browser checks again before showing anything.

The contract has a semantic version (`abot-dashboard 1.0.0`) with a compatibility policy.

### 3.6 Limitations of the static JSON design (to be documented)

None of these is a defect at the current scale, but they belong in the architecture document:

1. **Everything loads up front.** About 10.2 MB raw (about 1.1 MB gzipped) is fetched and hashed
   before the first page renders. It is acceptable on desktop and slow on a weak mobile connection.
   The two cell chunks (3.5 MB each) dominate.
2. **Results are precomputed only.** No query for an arbitrary point, no new facility, no "what if
   we add a clinic here". Each change means re-running the pipeline, re-exporting and redeploying.
3. **One city, one snapshot.** The bundle path is `v1/`, and there is no catalogue of several
   bundles or dates.
4. **Map backgrounds are outside requests** (OpenStreetMap and Esri tiles, since M05.3). These are
   subject to the tile providers' usage policies; fine for a portfolio demo, not for heavy public
   traffic.
5. **ODbL share-alike.** The published bundle is a derived OpenStreetMap database. Publishing a demo
   publishes the bundle, so it must carry ODbL attribution and terms (H4).

### 3.7 Would a REST API or a database help?

**No, not for ABOT's current requirements.** Each requirement compared with what the current design
delivers:

| Requirement | Current static design | Would FastAPI, PostgreSQL or PostGIS help? |
|---|---|---|
| Serve fixed, audited results for 180 barangays | Static files, any host, no running server | No: a server adds hosting, uptime and security work for identical answers |
| Integrity and provenance | SHA-256 manifest checked at three points | No: a database would need its own equivalent checks |
| Spatial analysis | GeoPandas, Shapely and NetworkX in batch; network routing is the bottleneck | No: PostGIS does not route on OSM graphs better than NetworkX here (pgRouting would be a rewrite) |
| Reproducibility | Pipeline plus lockfile plus contract | Worse: database state is harder to version than files |
| Cost of a portfolio demo | Free static hosting (GitHub Pages works: relative `base: "./"`, hash routing) | Worse: needs a paid or sleeping server |

An API or database becomes justified only if a **new** requirement appears:
- interactive "what-if" scenarios (adding a facility and re-routing);
- several cities or dates queried on demand;
- user-submitted corrections;
- data too large to ship to the browser.

None of these is in scope. **Recommendation:** in the architecture document, write this comparison
down as an explicit design decision with its trade-offs. A reviewer reading "why no PostGIS"
answered with evidence learns more than from a stack checklist.

---

## 4. Code Quality Assessment (Phase 3)

### 4.1 Strengths

- **Separation of concerns.**
  - The CLI imports stages lazily.
  - Configuration is isolated in `config.py`, with an `extends:` merge and per-run output folders.
  - The frontend separates contract types, loading and validation, pure models (`src/model/`), view
    state, components and pages.
- **TypeScript.**
  - `strict`, `noUncheckedIndexedAccess`, `noUnusedLocals` and `verbatimModuleSyntax` are on.
  - No `any` and no `@ts-…` directive in `dashboard/src`. The only two `any`s are
    `Record<string, any>` in test code (`test/fixtures/bundle.ts`, `test/loadBundle.test.ts`).
    There are 8 `as unknown as` casts in `src`.
- **Error handling.**
  - Errors are named and explicit (`ExportError`, `RecoveryError`).
  - A malformed configuration raises clear `ValueError`s (for example unknown `maxspeed_policy`, or
    an invalid tier).
  - The frontend `guard()` reports a panel the bundle cannot fill instead of crashing the page.
- **Logging.** Pipeline modules log through the standard `logging` module (15 modules), with
  `-v/--verbose`. `print` appears only for command output (`audit`, `export-dashboard`,
  `fetch-gaps`), which is appropriate.
- **Security.**
  - No secrets anywhere.
  - Downloads are written to a `.part` file and then renamed.
  - The Vite dev middleware serves only names matching
    `^[A-Za-z0-9][A-Za-z0-9._-]*\.(json|geojson)$` (no path traversal; tested).
  - OpenStreetMap strings (names, tags) are HTML-escaped (`esc()`) before being placed in Leaflet
    tooltips, the only place raw HTML is built.
  - No `dangerouslySetInnerHTML` or `eval`. No TODO or FIXME markers remain.
- **Naming.** Consistent within each language; contract ids such as
  `A3.walk.<group>.pct_le15` are uniform.

### 4.2 Weaknesses

Full entries are in §8. The significant ones are first.

| Weakness | Evidence | Significant or stylistic? |
|---|---|---|
| Unused dependencies, and docs that list them as used | `chart.js`, `react-leaflet` in `package.json`; no import in `dashboard/src` | **Significant** for a portfolio: the stack list is inaccurate |
| Very large modules and functions | `dashboard_data.py` 1,742 lines, of which `validate()` is about 350; `components.py` 1,157 | **Significant** for maintainability, though well tested |
| No static type checker for Python | No mypy or pyright configuration; 212 of 299 functions (71%) fully annotated; lowest coverage in `audit.py` (4/15) and `osm.py` (18/36) | Moderate |
| No frontend linter | No ESLint, Prettier or Biome configuration | Moderate; `tsc` strict covers much of it |
| Dead code left by the M05.3 redesign | No callers for `useHashRoute`, `GroupSelect`, `thresholdOptions`, `txt`, `printPage` (dashboard `router.ts`, `ui.tsx`), `statLabel`, `statCodes` (`model/view.ts`) or `RELIABILITY_DIMENSIONS` (`model/labels.ts`) | Minor |
| Inconsistent formatting | `ruff format --check`: 8 files, e.g. `archive.py`, `audit.py`, `cli.py`, `components.py` | Minor (cosmetic) |
| Duplicated helper | `esc()` is defined in both `MapPage.tsx` and `NetworkPage.tsx` | Minor |
| Settings have no schema | `Settings.__getitem__` reads `raw[key]`, so a typo in `settings.yaml` fails late with a `KeyError` | Minor |

---

## 5. Testing and Reliability Assessment (Phase 4)

### 5.1 What exists

| Suite | Count | Character |
|---|---|---|
| Python (`tests/`) | 230 passing | Behaviour tests on synthetic graphs and frames: one-way streets, connecting to an edge's interior, river barriers, connection tolerance, multi-source Dijkstra, unconnected residents kept in denominators, drive-speed policy, the veterinary exclusion, duplicate recording, config `extends` isolation, archive and review decisions, the exporter gate, recovery and validation |
| Frontend (`dashboard/test/`) | 81 passing | Loader and contract validation (32), the Vite plugin (dev and build, 7), models (15), shell and pages rendered to static HTML (25), the real bundle (2) |
| Analytical audit | `abot audit` | 51 PASS · 3 WARN · 0 FAIL: inputs, staleness, consistency, archive hashes |

Data-dependent tests skip cleanly when `data/` is absent (`HAVE_DATA`, `pytest.skip("archive not
present …")`, `describe.skipIf(!HAVE)`). Their skipping on a fresh clone was inferred from the code,
not observed, because no clean clone was made.

### 5.2 Important behaviour that is not tested

| Gap | Why it matters | Severity |
|---|---|---|
| **No continuous integration** | Tests run only on the author's machine; regressions are caught only if someone remembers to run them | High (H3) |
| **No end-to-end pipeline test on a tiny synthetic area** | `boundaries.build`, `population.build`, `osm.build` and `accessibility.build` are tested piecewise but never chained; the only end-to-end export test needs the real 900 MB of data | Medium (M6) |
| **No browser or interaction tests** | Pages are tested as static HTML only. Leaflet layers, the basemap switch, the barangay drawer, keyboard use of the radio groups and focus moves are verified manually only | Medium (M7) |
| Real-bundle tests always skip outside the author's machine | Without a small committed sample bundle, CI could never exercise the real-data render path | Medium (part of H2/M6) |
| Download behaviour without a network or with drifted upstream files | `download()` makes a `HEAD` request even for cached files, and recorded hashes are not compared with pinned expectations | Low (M9) |

### 5.3 Reliability

The code that keeps errors from reaching users (audit gate → exporter validation → build-time copy
check → browser verification) is well designed and tested at each layer. The main reliability risk
is **process, not code**: nothing enforces that tests and formatting pass before a commit.

---

## 6. Reproducibility Assessment

| Question | Answer | Evidence |
|---|---|---|
| Can the author re-run everything? | Yes | Lockfile, configuration hash, cached OSM, documented commands (Documentation.md §9), deterministic outputs |
| Can an outsider re-run the method? | Yes, given time | `uv sync` → `abot fetch` (about 550 MB) → `abot build` → `abot export-dashboard`, but the export and dashboard steps are not in the README (H1) |
| Can an outsider reproduce the **published numbers**? | No | The Overpass snapshot is not distributed and queries are not date-pinned (M3) |
| Can an outsider see the dashboard quickly? | No | `data/` is ignored; a fresh build warns "no bundle … the build has no data" (`vite/bundlePlugin.ts`) and the page shows the fatal state (H2) |
| Are the environments pinned? | Mostly | Python via `uv.lock`; frontend via `package-lock.json` and exact versions; Node `>=22.12.0` (Documentation.md records 24.18.0). No `.nvmrc` |
| Is provenance of the shipped bundle clean? | No | `manifest.code`: commit `5ed16d2`, working tree not clean (M1) |

---

## 7. Documentation Assessment (Phase 5)

| Document | Quality | Gap for a reviewer |
|---|---|---|
| `README.md` | Good content, **out of date** | Says "Status: Milestone 02B". Missing: the dashboard, `export-dashboard`, A3, M03–M05, screenshots, a demo link, the frontend commands, an architecture overview, a licence section (H1) |
| Installation | Pipeline: clear (`uv sync`, `uv run abot …`) | Frontend: no instructions anywhere (`npm install`, `npm run dev`, `npm run build`); the only mention is a shell caveat in Documentation.md §4 |
| Architecture | Pieces exist: Documentation.md §4 (pipeline, code layout), `DASHBOARD_DATA_CONTRACT.md` (900 lines) | No 1–2 page overview with a diagram; no recorded design decisions such as "why static JSON" (H5) |
| Methodology | **Excellent**: `docs/METHODOLOGY.md`, audits, validity assessment, results per milestone | Long; a newcomer needs a summary page |
| Data provenance | **Excellent**: `DATA_SOURCES.md`, manifests, licences, Overpass timestamps | — |
| Known limitations | **Excellent**: Documentation.md §8, `provenance.limitations`, the dashboard's About page | — |
| Dashboard usage | The in-app About page is good for residents | No developer-facing dashboard README |
| Screenshots and demo | **None** | No images, GIF or hosted URL (H2) |
| QGIS validation | Mentioned only as "open in QGIS with imagery" (`review.py`) and the M03 reviewer imagery check | If QGIS is a portfolio claim, the repository shows no screenshots or procedure. Document the manual review procedure with one or two images |
| Licence, contributing, changelog | **No LICENSE**; the changelog is inside Documentation.md | H4 |

The research documentation is a strength for the thesis but a barrier for recruiters: there are about
516 KB of Markdown and no "start here" path through it.

---

## 8. Technical Debt and Risks

### 8.1 Confirmed problems

**H1 — README is out of date (High)**
- *Evidence:* `README.md` line 7 says "Status: **Milestone 02B**"; no mention of `dashboard/`,
  `export-dashboard`, the A3 layer or Milestones 03–05. The README itself was last edited on
  2026-10-31; the dashboard milestones followed on 2026-11-01.
- *Why it matters:* the README is the first and often the only file an evaluator reads. It currently
  hides the most visible half of the project.
- *Action:* rewrite as a portfolio landing page: one-paragraph pitch, screenshot, demo link,
  architecture diagram, quick start for both halves, key results, tech stack (accurate), links into
  docs, licence. Move the "how to read the results" caveats into a short section.

**H2 — The dashboard cannot be seen without running the full pipeline (High)**
- *Evidence:* `.gitignore` ignores `data/` and `dist/`; `vite/bundlePlugin.ts` `closeBundle` warns
  "no bundle … the build has no data"; no screenshots or hosted URL exist.
- *Why it matters:* a reviewer spends minutes, not hours. They will not download 550 MB and run a
  pipeline to see a UI.
- *Action:*
  1. Publish the built dashboard on static hosting (GitHub Pages fits: `base: "./"`, hash routing,
     about 1.1 MB gzipped data).
  2. Add three to five screenshots and a short GIF to the README.
  3. Optionally attach the bundle to a GitHub Release so `npm run dev` can work without the
     pipeline.

  All three publish ODbL-derived data, so do H4 first.

**H3 — No continuous integration (High)**
- *Evidence:* no `.github/` directory.
- *Why it matters:* the test suites are a major asset but invisible. A green badge is the cheapest
  credible signal of engineering discipline, and CI protects the code against regressions.
- *Action:* add one GitHub Actions workflow. It should run `uv sync` + `ruff check` +
  `ruff format --check` + `pytest`, and `npm ci` + `tsc` + `vitest` + `vite build`. All of these run
  without `data/`, and data-dependent tests skip.

**H4 — No licence file (High)**
- *Evidence:* no `LICENSE*` in the repository root; `pyproject.toml` has no `license` field.
- *Why it matters:*
  - Without a licence the code is "all rights reserved", which deters reviewers from running it
    and is a common portfolio red flag.
  - The dashboard bundle is a derived OpenStreetMap database. Publishing it (H2) requires ODbL
    attribution and share-alike terms (README already notes this obligation).
- *Action:* choose a code licence (for example MIT or Apache-2.0) and add `LICENSE`. Add a short
  "Data licences" note (ODbL for OSM-derived outputs, CC BY 4.0 / CC BY-IGO for the other sources).
  Confirm with the university whether thesis code has ownership conditions before choosing.

**H5 — No entry-point architecture document (High)**
- *Evidence:* architecture is spread across Documentation.md §4 (114 KB file),
  `DASHBOARD_DATA_CONTRACT.md` (900 lines) and milestone documents; no diagram exists.
- *Why it matters:* the clean pipeline → contract → frontend separation is the project's strongest
  engineering story, and a reviewer cannot find it in under five minutes.
- *Action:* add `docs/ARCHITECTURE.md` (1–2 pages): the diagram from §2.1, data flow, ownership
  rules, the three integrity checkpoints, and a short "design decisions" section (static JSON vs API
  or database per §3.7; Leaflet without react-leaflet; contract versioning).

**M1 — The shipped bundle records uncommitted code (Medium)**
- *Evidence:* `export-dashboard --check` reports commit `5ed16d2…` with `clean: False`; the
  dashboard lists known issue `GIT-DIRTY`.
- *Why it matters:* the provenance chain is the project's selling point, and the live bundle cannot
  be tied to an exact commit.
- *Action:* after the next commit, run `abot export-dashboard` from a clean tree. This audit did not,
  because it regenerates outputs.

**M2 — Unused dependencies and an inaccurate stack description (Medium)**
- *Evidence:* `chart.js` 4.6.1 and `react-leaflet` 5.0.0 are in `dashboard/package.json`, with no
  import anywhere in `dashboard/src`; Documentation.md §4 lists them as runtime dependencies; the
  M06 brief lists both as part of the frontend.
- *Why it matters:* a reviewer who checks the code against claimed skills will notice the mismatch.
  Unused packages also add install weight and security-audit surface.
- *Related (informational):* the M06 brief also lists PyProj in the stack. `pyproj` is a declared
  dependency but is never imported in `src/`. Projections go through GeoPandas (`to_crs`,
  `estimate_utm_crs`), which uses PyProj underneath. That is legitimate, but the stack description
  should say "PyProj (via GeoPandas)" rather than imply direct use. Conversely, `folium` (the QA map in
  `report.py`) is used but not mentioned in the brief's stack list.
- *Action:* remove both packages, or keep them only if a planned feature uses them. Correct the
  stack description everywhere: Leaflet used directly, charts as hand-built SVG.

**M3 — Published numbers cannot be reproduced from a clone (Medium)**
- *Evidence:* the Overpass queries (`osm.py`, through osmnx) have no `[date:…]` pin; the cache in
  `data/raw/osm_cache/` is git-ignored; Documentation.md §9 notes that results can differ on a new
  fetch.
- *Why it matters:* reproducibility is a central claim of the project. Today it holds only on the
  author's machine.
- *Action (choose one):*
  - publish the OSM cache (or the processed GeoPackage) as a versioned Release asset under ODbL;
  - pin Overpass queries to the recorded `timestamp_osm_base`, if osmnx's Overpass settings allow
    it without changing the method, and verify that outputs are byte-identical.

  Either way, document the exact reproduction path.

**M4 — Very large modules (Medium)**
- *Evidence:* `dashboard_data.py` 1,742 lines with `validate()` at about 350 lines (lines
  1161–1518); `components.py` 1,157; `audit.py` 877.
- *Why it matters:* such files are hard to review or extend. Reviewers reading the code see this
  first.
- *Action:* split along existing seams without behaviour changes, under the existing tests. For
  example, `dashboard_data/` with `build.py`, `validate.py`, `install.py` and `provenance.py`, and
  `validate()` split per dataset. Do this only with tests green before and after.

**M5 — Tests organised by milestone, not by module (Medium)**
- *Evidence:* `tests/test_m02.py`, `test_m02b.py`, `test_m03.py`, `test_m04.py`, `test_m05.py`.
- *Why it matters:* it is hard to find the tests for a module, and the layout reads as a project
  diary rather than a maintained codebase.
- *Action:* reorganise into `tests/test_<module>.py` (moving tests unchanged), or at least add a
  short index in `tests/README.md`.

**M6 — No end-to-end smoke test on synthetic data (Medium)**
- *Evidence:* stage `build()` functions are not chained in any test; the only end-to-end export test
  needs real data (`HAVE_DATA`).
- *Why it matters:* a regression in how stages hand data to each other would pass CI.
- *Action:* add a tiny synthetic fixture area (a few cells, a toy network, two facilities) and one
  test that runs build → export → frontend loader. A committed sample bundle would also let the
  real-render frontend test run in CI.

**M7 — No browser or interaction tests for the dashboard (Medium)**
- *Evidence:* every frontend test renders static HTML (`react-dom/server`); Leaflet code
  (`MapPage.tsx`, `map/leaflet.ts`) is exercised only manually.
- *Why it matters:* the map is the product's centrepiece, and regressions in layer styling, the
  basemap choice, the drawer or keyboard operation would not be caught.
- *Action:* add a small Playwright smoke suite (pages load, basemap switch, drawer opens, no console
  errors) against `vite preview` with a sample bundle. This needs a new dev dependency, so it is
  deferred to an implementation milestone.

**M8 — No Python type checker; partial annotations (Medium)**
- *Evidence:* no mypy or pyright configuration; 212 of 299 functions fully annotated.
- *Why it matters:* reviewers from software roles look for it, and it catches interface errors
  between stages.
- *Action:* add mypy or pyright in non-strict mode to CI; annotate `audit.py`, `osm.py` and
  `validation.py` first.

**M9 — Download checks rely on size, not pinned hashes (Medium)**
- *Evidence:* `fetch/common.py` `download()` checks `Content-Length` with a `HEAD` request even for
  cached files; SHA-256 values are recorded but not compared with expected values at fetch time
  (`abot audit` later compares with the manifest).
- *Why it matters:* an upstream file that changes at the same size goes unnoticed at fetch time, and
  an offline re-run of `fetch` fails even when everything is cached.
- *Action:* store expected SHA-256 values for the fixed sources in configuration and verify after
  download; skip the `HEAD` request when a cached file already matches its pinned hash.

**M10 — No frontend lint or format configuration (Medium)**
- *Evidence:* no ESLint, Prettier or Biome configuration in `dashboard/`.
- *Why it matters:* React hook-dependency mistakes are not caught by `tsc`. Six effects deliberately
  leave inputs out of their dependency arrays and justify it only in a comment (`App.tsx:59`,
  `map/leaflet.ts:140`, `BarangaysPage.tsx:39`, `FacilitiesPage.tsx:89` and `:102`,
  `MapPage.tsx:319`). The reasoning may be sound, but nothing checks it. There are no
  `eslint-disable` comments, because there is no ESLint.
- *Action:* add ESLint with `eslint-plugin-react-hooks` (a new dev dependency, so deferred) and run
  it in CI.

**L1 — Dead code after the M05.3 redesign (Low)**
- *Evidence:* `useHashRoute` (`router.ts`), `GroupSelect`, `thresholdOptions`, `txt`, `printPage`
  (`ui.tsx`), `statLabel`, `statCodes` (`model/view.ts`) and `RELIABILITY_DIMENSIONS`
  (`model/labels.ts`) have no remaining callers.
- *Action:* remove them in the next frontend milestone.

**L2 — Formatter not applied to 8 Python files (Low)**
- *Evidence:* `ruff format --check` lists 8 files.
- *Action:* run `ruff format` in a dedicated, behaviour-free commit, then enforce it in CI.

**L3 — Duplicated `esc()` helper (Low)**
- *Evidence:* defined in both `MapPage.tsx` and `NetworkPage.tsx`.
- *Action:* move it to one shared module.

**L4 — Settings have no schema validation (Low)**
- *Evidence:* `config.py` returns the raw dictionary, so a misspelt key fails late.
- *Action:* validate required keys at load with a short explicit check. Avoid adding a new
  dependency for it.

**L5 — Node version not pinned for tools (Low)**
- *Evidence:* `engines: >=22.12.0` but no `.nvmrc` or `.node-version`.
- *Action:* add `.nvmrc` with the version in Documentation.md (24.18.0; the same version was
  observed on 2026-11-02).

**L6 — Production build ships source maps (Low)** *(added 2026-11-02)*
- *Evidence:* `dashboard/vite.config.ts` sets `build.sourcemap: true`. The observed build emitted
  about 2.1 MB of `.map` files (1,447 kB for the app bundle, 676 kB for Leaflet) next to about
  510 kB of JavaScript.
- *Why it matters:* nothing secret is exposed, because the source is meant to be public. But a
  hosted demo (H2) would serve maps that roughly triple the JavaScript payload, and the setting
  looks unintentional to a reviewer.
- *Action:* decide deliberately. Either keep the maps and note why (debuggable public demo), or set
  `sourcemap: false` (or `"hidden"`) for the Pages deployment.

### 8.2 Risks (not defects)

- **Tile-provider dependence:** if the OpenStreetMap or Esri tile policies change, the map
  backgrounds fail. The map still works with "No background".
- **Research and recruiting documentation pull in different directions:** the thesis needs detail;
  recruiters need brevity. Keep both by layering (README → ARCHITECTURE → METHODOLOGY → milestone
  documents), not by deleting.
- **Single maintainer process:** commits are made manually, with no enforced checks (H3).

---

## 9. Recommended Improvements

### 9.1 Fixes for confirmed problems (do these)

1. Rewrite `README.md` as a portfolio landing page (H1).
2. Add `LICENSE` and a data-licence note (H4).
3. Add a GitHub Actions CI workflow for both halves (H3).
4. Add `docs/ARCHITECTURE.md` with the diagram and design decisions (H5).
5. Publish the dashboard (GitHub Pages) with screenshots and a GIF (H2), after H4.
6. Re-export the bundle from a clean commit (M1).
7. Remove `chart.js` and `react-leaflet`, and correct the stack description (M2).
8. Apply `ruff format`, remove dead frontend code, deduplicate `esc()` (L1–L3).

### 9.2 Recommendations (should do)

- Make the published numbers reproducible: a Release asset or a pinned snapshot (M3).
- Add an end-to-end synthetic smoke test and a small committed sample bundle (M6).
- Reorganise or index the tests by module (M5).
- Add a Python type checker to CI (M8).
- Pin and verify source hashes at fetch time (M9).
- Document the QGIS manual-review procedure with one or two screenshots.

### 9.3 Optional enhancements (nice to have)

- Playwright smoke tests (M7) and ESLint (M10). Both need new dev dependencies.
- Split `dashboard_data.py` and `components.py` along existing seams (M4).
- Lazy-load the cell chunks only when the 100 m grid is switched on, to cut the first load from about
  10 MB to about 3 MB (§3.6).
- A short "Findings" page or README section with the three headline results and one map image.
- `.nvmrc`; a schema check for the settings (L4, L5).
- A deliberate source-map setting for the hosted build (L6).

### 9.4 Explicitly not recommended

FastAPI, PostgreSQL, PostGIS, authentication or containers for the current scope (§3.7). Revisit
only if a requirement listed in §3.7 appears.

---

## 10. Portfolio Readiness Scorecard

| Area | Rating | Basis |
|---|---|---|
| Architecture and separation of concerns | **Ready** | Contract-only interface, clear data ownership, three integrity checkpoints (§2.3, §3.5) |
| Analytical pipeline | **Ready** | Deterministic, configurable, audited; 230 tests pass |
| Data provenance and integrity | **Ready** | Manifests, SHA-256, archive hashes, audit gate (§3.2) |
| Dashboard data handling and error states | **Ready** | Per-dataset degradation, verification state, 32 loader tests (§3.4) |
| Frontend code quality | **Needs Improvement** | Strict TypeScript and clean structure; unused dependencies, dead code, no linter (M2, M10, L1) |
| Python code quality | **Needs Improvement** | Lint clean; very large modules, 71% annotated, formatter not applied (M4, M8, L2) |
| Automated testing | **Needs Improvement** | Strong unit and contract tests; no end-to-end or interaction tests (M6, M7) |
| Continuous integration | **Incomplete** | None (H3) |
| Reproducibility for outsiders | **Needs Improvement** | Method reproducible; published numbers and the dashboard are not (M3, H2) |
| README | **Needs Improvement** | Good content, two milestones stale, no dashboard (H1) |
| Installation and run instructions | **Needs Improvement** | Pipeline yes; frontend missing (H1) |
| Architecture documentation | **Incomplete** | No overview or diagram (H5) |
| Methodology documentation | **Ready** | `METHODOLOGY.md`, audits, validity assessment |
| Known limitations | **Ready** | Documentation.md §8, in-app About, bundle limitations |
| Screenshots and demo | **Incomplete** | None (H2) |
| Licensing | **Incomplete** | No LICENSE (H4) |
| API / database layer | **Not Applicable** | Deliberately absent and justified (§3.7) |
| Authentication and multi-user features | **Not Applicable** | Read-only public tool |

---

## 11. Recommended M06 Implementation Roadmap

The order follows impact on a reviewer per hour of work, and keeps every change behaviour-free for
the analytics.

**M06.1 — Make it visible (presentation, no code behaviour changes)**
1. `LICENSE` + data-licence note (H4).
2. `docs/ARCHITECTURE.md` with the diagram and design decisions (H5).
3. README rewrite with screenshots and quick start for both halves (H1).
4. Correct the stack description; remove `chart.js` and `react-leaflet` (M2).
5. Re-export the bundle from a clean commit (M1).

*Exit criterion:* a reviewer understands what ABOT is, how it is built and what it found within five
minutes of opening the repository.

**M06.2 — Make it verifiable (quality gates)**
1. GitHub Actions CI: ruff (lint and format), pytest, tsc, vitest, vite build (H3).
2. Apply `ruff format`; remove dead code; deduplicate `esc()` (L1–L3).
3. Add a type checker in non-strict mode (M8).

*Exit criterion:* a green CI badge on `main`, and every check from §1.1 enforced on each push.

**M06.3 — Make it runnable and reproducible by others**
1. Deploy the dashboard to GitHub Pages and link it from the README (H2).
2. Publish the bundle and the OSM snapshot as Release assets, or pin the snapshot; document the
   exact reproduction path (M3).
3. Small committed sample bundle plus an end-to-end synthetic smoke test (M6).
4. Pinned source hashes at fetch time (M9).

*Exit criterion:* a reviewer can open a live demo, and a technical reviewer can reproduce the
published bundle from the documented assets.

**M06.4 — Optional depth**
- Playwright smoke tests and ESLint (M7, M10).
- Module splits (M4) and test reorganisation (M5).
- Lazy-loaded cell grid (§3.6).
- QGIS review-procedure write-up.

---

---

## Appendix A — Re-verification on 2026-11-02

The 2026-11-01 report was re-checked against the same commit (`56fbd64`) instead of being rewritten.
Every check in §1.1 except `uv lock --check` was re-run, with the same results (§1.1). The evidence
for each finding was re-inspected.

**Confirmed unchanged:**
- H1: README line 7 still says "Status: Milestone 02B".
- H3, H4, L5: there is no `.github/`, `LICENSE*`, `.nvmrc` or `.node-version` in the root.
- M2: no import of `chart.js` or `react-leaflet` anywhere in `dashboard/src`, `test` or `vite`.
  Documentation.md line 241 still lists both as runtime dependencies.
- M4: the module line counts are as stated (8,849 lines in total).
- M8: 212 of 299 functions are fully annotated (71%). The counts for `audit.py` (4/15) and `osm.py`
  (18/36) match, and `validation.py` is 12/22.
- M9: `download()` issues a `HEAD` request before using a cached file (`fetch/common.py:56`).
- L1: the eight dead symbols each appear only at their own definition.
- L3: `esc()` is duplicated verbatim (`MapPage.tsx:26`, `NetworkPage.tsx:22`).
- Logging: 15 modules use `logging`.
- No `dangerouslySetInnerHTML`, `eval`, `innerHTML`, TODO or FIXME.

**Corrected:**

| Where | Was | Now | Basis |
|---|---|---|---|
| §1.1 | "In PowerShell, `uv run …` works" | `uv` was not on the PATH of PowerShell either | `Get-Command uv` found nothing |
| §3.4, §5.1, §10 | Loader 30, plugin 6, models 12 (these sum to 75, not 81) | Loader 32, plugin 7, models 15, shell 25, real bundle 2 = 81 | `vitest list --json`, grouped by file |
| §4.1 | "2 `any`/`@ts-…` escapes in the whole frontend" | 0 in `src`; 2 in test code; no `@ts-` directives | grep over `src`, `test`, `vite` |
| M10 | "suppresses dependency arrays with comments" | Six effects omit inputs and justify it in comments; no lint suppressions exist | grep for comments preceding `}, [...]);` |

**Added:** L6 (production source maps) and an informational note under M2 about PyProj and folium.

**Severity changes:** none. No finding was disproved, and the headline conclusions and the roadmap
stand.

---

*This audit changed no application code, methodology, analytical output or Git state. Its only
outputs are this report and change-log entries in `Documentation.md`.*
