# M06.2B — GitHub Actions Continuous Integration

- **Date:** 2026-11-02.
- **Base:** `main` at `86d9797` (Milestone 06.2A follow-up).
- **Files:**
  - `.github/workflows/ci.yml`: the workflow;
  - `.github/scripts/pytest_summary.py`: the test-summary script;
  - `.gitignore`: ignores the JUnit report;
  - `README.md`: CI badge and testing section.

## 1. Objectives

- **Verify every push and pull request to `main` automatically**, for both halves of ABOT: the
  Python package (lint and tests) and the dashboard (types, tests and production build).
- **Need no local data.** CI has no `data/`, no `data/archive/`, no dashboard bundle, and no
  OpenStreetMap or download step. Tests that need data skip by design, and the job summary lists
  them with their reasons, so nothing is hidden.
- **Be reproducible and cheap:**
  - dependencies come only from the lockfiles (`uv.lock`, `dashboard/package-lock.json`);
  - tool versions are pinned;
  - caches are keyed on the lockfiles;
  - each job has a timeout.

CI does **not** reproduce the analytical results. It checks that the code is consistent and that
its tests pass. Reproducing results needs the data pipeline, which CI does not run (§10).

## 2. Triggers

| Event | Branches |
|---|---|
| `push` | `main` |
| `pull_request` | targeting `main` |

**Concurrency:** group `ci-<workflow>-<ref>`. A newer push to the same pull request cancels the
older run. Runs on `main` are never cancelled (`cancel-in-progress` is true only for pull
requests), so every commit on `main` gets a complete result.

## 3. Python job ("Python (lint and tests)")

`ubuntu-latest`, 20-minute timeout.

| Step | Command / action |
|---|---|
| Checkout | `actions/checkout` v7.0.1, `persist-credentials: false` |
| uv | `astral-sh/setup-uv` v10.3.3 with `version: "0.13.6"`, cache enabled and keyed on `uv.lock` |
| Python | `uv python install`, which reads `.python-version` (3.13; `requires-python >=3.13`) |
| Dependencies | `uv sync --locked`: fails if `uv.lock` does not match `pyproject.toml`. Installs the project and the `dev` dependency group (pytest, ruff), which uv syncs by default |
| Lint | `uv run ruff check .` (rules from `[tool.ruff.lint]` in `pyproject.toml`) |
| Tests | `uv run pytest -ra --junitxml=pytest-results.xml` (test paths from `[tool.pytest.ini_options]`) |
| Summary | `python3 .github/scripts/pytest_summary.py pytest-results.xml`, run unless the job was cancelled (`if: !cancelled()`), so failures are summarised too |

The job **fails** if the lock check, lint or any test fails. The summary step never changes the
outcome.

**Formatting** (`ruff format --check`) is deliberately not run yet. Eight existing Python files
are known to need reformatting, and that cleanup is planned as a separate, behaviour-free commit.
After that, add `uv run ruff format --check .` as a step.

## 4. Dashboard job ("Dashboard (types, tests, build)")

`ubuntu-latest`, 15-minute timeout, every `run` in `dashboard/`.

| Step | Command / action |
|---|---|
| Checkout | `actions/checkout` v7.0.1, `persist-credentials: false` |
| Node.js | `actions/setup-node` v7.1.0, `node-version: "24"`, npm cache keyed on `dashboard/package-lock.json` |
| Dependencies | `npm ci` (exact lockfile install; fails on mismatch) |
| Types | `npm run typecheck`, which runs `tsc --noEmit` for `tsconfig.json` (app) and `tsconfig.node.json` (Vite configuration and plugin) |
| Tests | `npm test` (`vitest run`) |
| Build | `npm run build` (`vite build`) |

**Build without a bundle.** `data/` is not in Git, so CI has no `data/processed/dashboard/v1/`. The
existing Vite plugin (`dashboard/vite/bundlePlugin.ts`) handles this by design: the build
succeeds and prints `no bundle at …: the build has no data`. No application code was changed and
no fake data was created. The result proves that the code compiles and bundles. It is not a
deployable site with data.

## 5. Dependencies and runtime versions

| Item | Version | Source of truth |
|---|---|---|
| Runner | `ubuntu-latest` | GitHub |
| uv | 0.13.6 | workflow (`version`) |
| Python | 3.13 (latest patch uv provides) | `.python-version` |
| Python packages | 38 locked | `uv.lock` |
| Node.js | 24 (latest 24.x) | workflow (`node-version`); `package.json` `engines` requires ≥ 22.12 |
| npm packages | locked | `dashboard/package-lock.json` |
| `actions/checkout` | v7.0.1 = `3d3c42e5aac5ba805825da76410c181273ba90b1` | pinned by commit SHA |
| `actions/setup-node` | v7.1.0 = `949feb2413d6458794dcd2491c4babbbce0c15c1` | pinned by commit SHA |
| `astral-sh/setup-uv` | v10.3.3 = `68559e99cc807c1eb7e9238fd43a15bba460eec2` | pinned by commit SHA |

The action versions are the latest releases on 2026-11-02, read from the GitHub API. The SHAs
belong to those release tags. Their input names (`version`, `enable-cache`,
`cache-dependency-glob`, `node-version`, `cache`, `cache-dependency-path`,
`persist-credentials`) were checked against each action's `action.yml` at that tag.

No new project dependency was added.

## 6. Data-dependent test handling

Every test that needs local data guards itself and **skips with a reason**. No test was removed,
marked, or weakened for CI.

Observed in a fresh `git clone` of `86d9797` (no `data/`) on 2026-11-02, with `uv sync --locked`
and `uv run pytest -ra --junitxml=…`: **250 collected, 243 passed, 0 failed, 7 skipped.**

| Skip reason (from the test) | Tests | What they need |
|---|---|---|
| analytical outputs not present | `test_m05`: 2 end-to-end export tests; `test_m06`: 3 end-to-end export tests (no snapshot, no archives, incomplete archives) | `data/processed/` (A3 layer and GeoPackage) |
| A3 layer not built in this checkout | `test_m04::test_baseline_outputs_unchanged_by_the_a3_layer` | `data/processed/component_aware/run_info.json` |
| archive not present in this checkout | `test_m04::test_e7_archive_record_exists_and_names_the_superseded_run` | `data/archive/` |

**Dashboard in the same clone:** 82 tests, **80 passed, 2 skipped.** The 2 are
`test/realBundle.test.ts`, which `describe.skipIf`s without `data/processed/dashboard/v1/`. Vitest
prints its skip count in the log; there is no separate summary.

**What CI therefore does not exercise:**
- the end-to-end exports on real outputs, including the archive-aware and no-snapshot paths;
- the read-only checks of the real A3 layer and archive records;
- rendering of the real bundle.

These run, and pass, on the author's machine: **250 passed** and **82 passed** on 2026-11-02, with
data. The archive-aware and no-snapshot logic itself is still covered in CI by its synthetic unit
tests in `tests/test_m06.py`.

## 7. Test summary reporting

`.github/scripts/pytest_summary.py` uses the standard library only (`xml.etree`). It:
- reads the JUnit XML;
- counts results from the individual `<testcase>` elements, not the suite totals: passed, failed,
  errors, skipped;
- writes a Markdown table to `$GITHUB_STEP_SUMMARY` (or stdout when run locally).

It also lists:
- each failure or error, with the first line of its message;
- **every skip grouped by its reason**, with the test names.

If the report is missing, for example because pytest crashed, it says so. It always exits 0: the
pytest step decides pass or fail.

It was checked locally on:
- the fresh-clone report (243/7, the table above);
- a synthetic report with a failure and an error;
- a missing report;
- the full local run (250 passed).

## 8. Security and permissions

- **Permissions:** `permissions: contents: read` for the whole workflow. No write, deployment,
  package or token permission.
- **Credentials:** `persist-credentials: false` on checkout, so the token is not left in the
  local Git configuration for later steps.
- **Secrets:** none used or required.
- **Pull requests from forks:** `pull_request` (not `pull_request_target`), so fork code runs
  without access to secrets or a write token.
- **Supply chain:** third-party actions are pinned to full commit SHAs, with the version in a
  comment. Dependencies install only from the lockfiles (`--locked`, `npm ci`).
- **Outputs:** no artifact is uploaded and nothing is deployed. The JUnit file stays on the
  runner, and only the summary text is published.

## 9. Local equivalent commands

From the repository root, with `uv` on the PATH (`C:\Users\carlj\.local\bin` on the author's
machine).

```bash
uv sync --locked
uv run ruff check .
uv run pytest -ra --junitxml=pytest-results.xml
python .github/scripts/pytest_summary.py pytest-results.xml   # prints the summary

cd dashboard
npm ci
npm run typecheck
npm test
npm run build
```

`pytest-results.xml` is git-ignored. On Windows, run the npm scripts from PowerShell or cmd
(Documentation.md §4).

**Results on 2026-11-02:**

| Environment | Python | Dashboard |
|---|---|---|
| Fresh clone of `86d9797`, no `data/` (Windows) | `uv sync --locked` OK (13 s); `ruff check .` passed; pytest 243 passed, 7 skipped | `npm ci` OK; typecheck clean; Vitest 80 passed, 2 skipped; build OK with the "no bundle" warning |
| Working repository, with `data/` (Windows) | `uv lock --check` OK; `uv sync --locked --dry-run` OK (only the local `abot` package itself is refreshed); `ruff check .` passed; pytest 250 passed | typecheck clean; Vitest 82 passed; build OK, 9 bundle files verified |

The workflow file was parsed as YAML and its triggers, permissions, concurrency, jobs and steps were
checked. **GitHub Actions itself was not run locally** (no `act`, no runner). Whether the workflow
passes on GitHub's Ubuntu runners is known only after the first run on GitHub.

## 10. Known CI limitations

1. **No analytical reproduction.** CI runs no `abot fetch`, `fetch-gaps`, `build`, `components`,
   `audit` or `export-dashboard`. Those need about 550 MB of downloads, live Overpass queries and
   local outputs. The analytical results and the bundle are verified only on the author's machine.
2. **Data-dependent tests skip** (7 Python, 2 dashboard; §6). Their paths are covered locally,
   not in CI.
3. **Linux was not tried locally.** The local checks ran on Windows. Path handling, line endings
   and the Linux wheels of rasterio, pyogrio and shapely are exercised for the first time on the
   runner.
4. **No formatting gate yet** (§3).
5. **No browser test.** Pages are tested as static HTML (Vitest); Leaflet interaction is not
   covered.
6. **The build has no data.** The CI build proves compilation, not a deployable site.
7. **Floating minor versions.** `ubuntu-latest`, Python 3.13.x and Node 24.x float within their
   lines. The lockfiles fix every package.
