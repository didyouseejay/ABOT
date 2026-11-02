# M06.2C — Code Quality Enforcement and Technical Cleanup

- **Date:** 2026-11-02.
- **Base:** `main` at `ac90a6c` (CI passing on GitHub, run 41377198195).
- **Scope:** maintenance only. This milestone closes the remaining code-quality findings of
  [M06_TECHNICAL_AUDIT.md](M06_TECHNICAL_AUDIT.md) (L1, L2, L3 and M8) and makes CI enforce them.
  No analytical method, indicator, dataset, archive, dashboard bundle or data-contract version
  changed, and no runtime dependency was added.

The work is in four separately reviewable changes:

| # | Change | Audit item | Files |
|---|---|---|---|
| 1 | Python formatting only | L2 | 8 Python files |
| 2 | Frontend dead code and the shared `esc()` | L1, L3 | 7 dashboard source files, 1 test file |
| 3 | Pyright configuration and type fixes | M8 | `pyproject.toml`, `uv.lock`, 9 source files, 3 test files |
| 4 | CI enforcement and documentation | — | `.github/workflows/ci.yml`, documentation |

## 1. Formatting policy (L2)

- **Policy:** all Python code is formatted with `ruff format`, using the settings in `[tool.ruff]`
  (line length 110). From this milestone on, CI fails if any file is not formatted
  (`uv run ruff format --check .`).
- **Change:** `ruff format` was run on exactly the eight files the audit listed, and nothing else
  was changed in that step:
  - `src/abot/archive.py`
  - `src/abot/audit.py`
  - `src/abot/cli.py`
  - `src/abot/components.py`
  - `src/abot/fetch/targeted.py`
  - `src/abot/osm.py`
  - `src/abot/review.py`
  - `tests/test_m04.py`

  The diff (267 insertions, 75 deletions) only re-wraps long expressions, calls and literals.
- **Behaviour check:** for each file, the Python abstract syntax tree (`ast.dump`, which ignores
  layout and comments) of the formatted file is identical to that of `HEAD`. pytest gave 250
  passed before and after.
- **Line endings:** four of the files had CRLF line endings in the Windows working copy. Ruff keeps
  each file's existing ending, and `.gitattributes` (`eol=lf`) stores LF in Git, so the commit
  contains no line-ending changes.

## 2. Frontend cleanup (L1, L3)

### 2.1 Dead code removed (L1)

Each symbol was confirmed unused by searching `dashboard/src`, `dashboard/test` and
`dashboard/vite`. Each name appeared only at its own definition. (The one other hit for `txt` is
the string `"a b.txt"` in a test fixture.)

| Symbol | File | Note |
|---|---|---|
| `useHashRoute` | `src/router.ts` | Replaced by the routing in `App.tsx` during M05.3 |
| `hrefFor` | `src/router.ts` | Its only caller was `useHashRoute`. Removing that left it unused, so it was removed too. The `react` import of the file went with it |
| `GroupSelect` | `src/components/ui.tsx` | Its `groupLabel` import, used nowhere else in the file, was removed |
| `thresholdOptions` | `src/components/ui.tsx` | |
| `txt` | `src/components/ui.tsx` | |
| `printPage` | `src/components/ui.tsx` | |
| `statLabel`, `statCodes` | `src/model/view.ts` | |
| `RELIABILITY_DIMENSIONS` | `src/model/labels.ts` | |

`routeFromHash` and `isUnknownHash` remain: `App.tsx` and the tests use them. No CSS was changed;
the class names of the removed `GroupSelect` are shared with live controls.

### 2.2 Shared `esc()` helper (L3)

- The identical one-line `esc()` in `pages/MapPage.tsx` and `pages/NetworkPage.tsx` was replaced by
  one exported `esc` in `src/model/format.ts`. Both pages already imported `fixed` from that
  module.
- The implementation is unchanged character for character. It escapes `& < > " '` and maps
  null/undefined to `""`. It is used for the HTML strings passed to Leaflet tooltips, where
  OpenStreetMap names and tags are untrusted input.
- A unit test was added (`test/model.test.ts`, "format: map tooltip text is HTML-escaped"). It
  fixes the five escapes and the null handling, so a later edit cannot weaken them unnoticed.

### 2.3 Verification

| Check | Before | After |
|---|---|---|
| `npm run typecheck` (both tsconfigs, `noUnusedLocals`) | clean | clean |
| `npm test` (Vitest) | 82 passed | 83 passed (+1 `esc` test) |
| `npm run build` | OK | OK; the bundle plugin verified the 9 bundle files (sizes and SHA-256) |

The rendered pages and their accessibility attributes are unchanged: only unused exports were
removed, and the tooltip HTML is produced by the same function.

## 3. Python static type checking (M8)

### 3.1 Tool and version

- **Pyright 1.1.414**, added to the `dev` dependency group with `uv add --dev pyright`
  (`"pyright>=1.1.414"` in `pyproject.toml`; exact version in `uv.lock`).
- It brings two development-only packages, `nodeenv` and `typing-extensions`. `uv.lock` gains 33
  lines; the runtime dependencies are unchanged.
- The PyPI wheel contains Pyright itself. It needs a Node.js binary and uses the one on `PATH` (the
  GitHub runner has one). Without one, it installs Node through `nodeenv`.

### 3.2 Configuration (`[tool.pyright]` in `pyproject.toml`)

| Setting | Value | Reason |
|---|---|---|
| `include` | `["src", "tests"]` | ABOT-owned code |
| `pythonVersion` | `"3.13"` | Matches `requires-python` and `.python-version` |
| `typeCheckingMode` | `"standard"` | Pyright's default, non-strict mode. It checks calls, attribute access, optional values and return types, but does not require every function to be annotated (strict mode would) |
| `venvPath`, `venv` | `"."`, `".venv"` | Resolves imports from the uv environment, the same locally and in CI |
| `useLibraryCodeForTypes` | `false` | See §3.3 |
| `reportUnnecessaryTypeIgnoreComment` | `"error"` | Every `# pyright: ignore[...]` must still be needed, so suppressions cannot go stale |

### 3.3 Why `useLibraryCodeForTypes = false`

- pandas, geopandas, rasterio, scipy and networkx ship no type information (no `py.typed` marker,
  PEP 561). By default, Pyright guesses their types from their implementation source. For pandas,
  that makes `df[col]` a union of `Series` and every scalar type, so ordinary code such as
  `df["x"].reindex(...)` or `int(row["n"])` is reported as an error.
- In the baseline, about 430 of the 617 errors were of this kind. Many more came from
  `itertuples()` rows typed as `tuple[Any, ...]`.
- Installing `pandas-stubs` (dev-only) was tried. It removed only 141 errors (617 to 476), and the
  remainder were the same union and indexing errors. It was therefore not adopted.
- With `useLibraryCodeForTypes = false`, untyped libraries are treated as unknown rather than
  guessed. The rest is still checked:
  - all of ABOT's own code;
  - its calls into the libraries that are typed: numpy, osmnx, pyproj, requests and folium;
  - shapely, through the stubs bundled with Pyright.

### 3.4 Baseline and result

| Run | Configuration | Errors |
|---|---|---|
| Baseline | `standard`, default library inference | **617** in 20 files (270 argument-type, 206 attribute-access, 59 index, 31 call, 51 other) |
| After §3.3 | `standard`, `useLibraryCodeForTypes = false` | **46** in 15 files |
| Final | same, after the fixes below | **0 errors, 0 warnings** |

### 3.5 Fixes in ABOT code (behaviour unchanged)

| File | Change | Errors |
|---|---|---|
| `src/abot/osm.py` | `_tags_match(row, tags: dict \| None)`, `_regex_match(row, patterns: dict \| None)`. Both functions already handled `None` (`tags or {}`); the annotations were wrong | 5 |
| `tests/test_m04.py` | The `_graph` helper takes `Mapping[int, Sequence[tuple[float, float]]]` instead of `dict[int, list[...]]`. It only reads its input, and `dict`/`list` are invariant, so integer coordinates were rejected | 11 |
| `tests/test_m06.py` | `_src()` returns `D.Sources` via `cast(...)` on its `SimpleNamespace` stand-in, in one place instead of at six call sites | 6 |
| `src/abot/components.py` | `if snapshot is None or not st.get("obtained")`. Equivalent: a `None` snapshot already gave `st = {"obtained": False}` | 1 |
| `src/abot/population.py` | `data: dict[str, object]` (the dict holds a list and arrays) | 1 |
| `src/abot/population.py` | `if grid is None: raise ValueError("no WorldPop years configured ...")`. Only reachable with an empty `sources.worldpop.years`, which previously raised `TypeError: cannot unpack non-iterable NoneType`. Valid configurations are unaffected | 1 |

For the nine files whose only change in this step is comments (`access`, `accessibility`,
`fetch/targeted`, `report`, `review`, `validation`, plus `archive`, `audit` and `cli` from step 1),
the AST is identical to `HEAD`.

### 3.6 Remaining suppressions (documented limitations)

There are 19 line-scoped `# pyright: ignore[rule]` comments. Each names its rule, and
`reportUnnecessaryTypeIgnoreComment` fails the check if one stops being needed.

| Where | Count | Rule | Reason |
|---|---|---|---|
| `accessibility.py` (`BarrierChecker.blocked`, `connect_point`) | 8 | attribute access, argument type | Third-party typing. Shapely geometries are held in numpy object arrays. numpy's stubs type an element as `ndarray`, not a geometry, so `.length`, `.project()` and `.contains()` look invalid. A local annotation does not help, because numpy's overload still returns `ndarray`. Rewriting the expressions (e.g. `float(...)`, `.tolist()`) would touch core analytical code, so it was not done |
| `report.py`, `review.py`, `validation.py` | 5 | attribute access | Third-party typing. folium types `Map.get_root()` as `Element`, but at run time it is the `Figure`, which has `.html` |
| `validation.py` (`assess_duplicate`) | 2 | optional operand | Third-party typing. `pd.notna(x)` guards the comparison, but pandas is untyped here, so Pyright cannot narrow `x` |
| `population.py` (`np.nonzero`) | 1 | assignment type | Third-party typing. numpy infers a 1-D array from an unknown shape and expects one index array, not two |
| `access.py:116` | 1 | argument type | Checker limitation. `cls == "pedestrian_override"` is only set when `acc` is in `GROUP_RESTRICTIONS`, so `acc` is not `None`. Pyright does not track that correlation |
| `fetch/targeted.py:297` | 1 | argument type | Latent edge case, left unchanged. `ll()` returns `None` for a node in neither the snapshot nor the cache, and `_m()` would then raise `TypeError`. It has not occurred (snapshot ways reference their own nodes). Handling it would change the targeted-gap code, which is outside this milestone |
| `tests/test_m05.py` (`_ctx`) | 1 | argument type | Test double. The chunking code under test never reads `Ctx.src`, so `None` is passed |

### 3.7 Other limitations

- **Untyped libraries are unchecked.** Misuse of the pandas, geopandas, rasterio, scipy or networkx
  APIs is not caught statically. Tests cover these paths instead.
- **Annotation coverage is essentially unchanged** from the audit's 212 of 299 functions. The only
  additions are the return type of the test helper `_src()` and one local variable. Standard mode
  does not require annotations, and no broad annotation pass was made only to satisfy the checker.
- **Strict mode is not used.** It would require annotations throughout and stubs for the untyped
  libraries. That is possible future work, not part of M8.
- **The type check is local to this platform.** Pyright was run on Windows. The CI run on
  `ubuntu-latest` is the first Linux run (§4).

## 4. CI enforcement

`.github/workflows/ci.yml`: the Python job now runs, in order:

1. `uv sync --locked`
2. `uv run ruff check .`
3. `uv run ruff format --check .` (**new**)
4. `uv run pyright` (**new**; configuration from `pyproject.toml`)
5. `uv run pytest -ra --junitxml=pytest-results.xml`
6. the test summary (`.github/scripts/pytest_summary.py`, unchanged, run unless cancelled)

- Each new step fails the job on any finding. `-ra` and the JUnit summary are unchanged, so every
  skipped test is still listed with its reason.
- **Job name kept** as "Python (lint and tests)". Renaming a job changes its check name, which
  would break any branch-protection rule that requires it.
- **The dashboard job is unchanged.**

**Status:** the workflow was validated locally (YAML parses; each command passes on Windows). It
has **not yet run on GitHub**. Whether it passes on the Linux runner is known only after the first
push with these changes.

## 5. Verification results (2026-11-02, Windows, working repository with `data/`)

| Check | Result |
|---|---|
| `uv lock --check`, `uv sync --locked` | OK (41 packages) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 53 files already formatted (before: 8 would be reformatted) |
| `uv run pyright` | 0 errors, 0 warnings, 0 informations (baseline: 617 errors) |
| `uv run pytest -ra` | 250 passed, 0 skipped (same as before) |
| `npm run typecheck` | clean |
| `npm test` | 83 passed (5 files) |
| `npm run build` | OK; 9 bundle files verified and copied to `dist/` |
| `data/` | 259 files with identical paths, sizes and modification times before and after; SHA-256 identical for the 142 files outside `raw/` and `archive/`, including the 9 files of the installed bundle `data/processed/dashboard/v1` |

**Effect on results:** none. No analytical output was regenerated. The bundle was not re-exported,
and the data-contract version is unchanged (`abot-dashboard` 1.1.0).
