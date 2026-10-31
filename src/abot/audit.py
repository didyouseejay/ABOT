"""`abot audit`: a read-only check of a run's inputs, outputs and analytical consistency.

The audit never downloads, never writes into data/ (raw, interim, processed or archive) and never
repairs anything. It reports each check as PASS, WARN, FAIL or INFO (a measured value with no
threshold) with an actionable explanation, and exits with status 1 when any check FAILs.
Sections:
  config        settings are valid; the 1 km historical config is preserved
  inputs        raw files exist; their SHA-256 matches data/raw/manifest.json
  outputs       every expected layer and file exists
  staleness     stages ran in order, with the current configuration, after the last code change
  consistency   population conservation, census anchoring, denominators, flags, CSV = GeoPackage
  validity      the validity-assessment diagnostics, recomputed from the outputs
  archive       archived outputs still match their recorded SHA-256
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from abot import accessibility as A
from abot import osm, population, qa, reliability
from abot.config import PROJECT_ROOT, Settings, read_config
from abot.fetch.common import load_manifest, sha256

log = logging.getLogger(__name__)

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"
STAGE_LAYERS = {
    "boundaries": ["city", "barangays"],
    "population": [population.CELLS_LAYER, population.PIECES_LAYER],
    "osm": ["network_walk", "network_drive", "barriers", "facilities", "facility_roles"],
    "accessibility": ["access_cells", "barangay_access"],
}
STAGE_FILES = {
    "population": ["barangay_population.csv"],
    "osm": ["facilities.csv", "facility_exclusions.csv"],
    "accessibility": ["barangay_access.csv", "facility_inventory.csv", "drive_speed_sensitivity.csv"],
    "report": ["qa_report.md", "abot_map.html"],
}
UPSTREAM = {
    "population": ["boundaries"],
    "osm": ["boundaries"],
    "accessibility": ["population", "osm"],
    "report": ["accessibility"],
}
STAGE_CODE = {
    "boundaries": ["boundaries.py"],
    "population": ["population.py"],
    "osm": ["osm.py"],
    "accessibility": ["accessibility.py", "reliability.py"],
    "report": ["report.py"],
}
REVIEW_FILES = [
    "possible_duplicates_review.csv",
    "unconnected_cells_review.csv",
    "unconnected_cells_map.html",
]
NATIONAL_FACTOR = 1.022422  # WorldPop 2020 / PSA 2020 where WorldPop units equal barangays (assessment §1)


@dataclass
class Finding:
    section: str
    check: str
    status: str
    detail: str
    action: str = ""


class Audit:
    def __init__(self, s: Settings, config_path: Path, hashes: bool = True):
        self.s, self.config_path, self.hashes = s, Path(config_path), hashes
        self.findings: list[Finding] = []
        self.layers: list[str] = []

    def add(self, section, check, status, detail, action=""):
        self.findings.append(Finding(section, check, status, str(detail), action))

    # -- helpers ---------------------------------------------------------------------------------

    def layer(self, name: str, **kw):
        return gpd.read_file(self.s.gpkg, layer=name, **kw) if name in self.layers else None

    def csv(self, name: str) -> pd.DataFrame | None:
        p = self.s.processed_dir / name
        return pd.read_csv(p, dtype={"adm4_pcode": str}) if p.exists() else None

    # -- sections ----------------------------------------------------------------------------------

    def check_config(self):
        s, sec = self.s, "config"
        buf = s["osm"].get("boundary_buffer_m")
        ok = isinstance(buf, int | float) and buf > 0
        self.add(
            sec,
            "osm.boundary_buffer_m",
            PASS if ok else FAIL,
            f"{buf} m",
            "" if ok else "set osm.boundary_buffer_m to a positive number of metres",
        )
        try:
            name, col = population.primary_weight(s)
            self.add(sec, "population.primary_weight", PASS, f"{name} (column {col})")
        except ValueError as e:
            self.add(
                sec, "population.primary_weight", FAIL, e, "fix population.primary_weight in settings.yaml"
            )
        try:
            osm.validate_facility_config(s)
            self.add(
                sec, "facility_rules", PASS, f"{len(s['indicator_groups'])} indicator groups, all indicative"
            )
        except ValueError as e:
            self.add(
                sec, "facility_rules", FAIL, e, "only indicative sub-types may be indicator destinations"
            )
        r = s.get("reliability") or {}
        try:
            p, n = r["population"], r["network"]
            ok = (
                p["low_max_centre_cells"] < p["caution_max_centre_cells"]
                and n["caution_pct_not_connected"] < n["low_pct_not_connected"]
            )
            self.add(
                sec,
                "reliability_thresholds",
                PASS if ok else FAIL,
                f"population cells low<={p['low_max_centre_cells']}, caution<={p['caution_max_centre_cells']}; "
                f"network caution>{n['caution_pct_not_connected']}%, low>{n['low_pct_not_connected']}%",
                "" if ok else "caution thresholds must be less strict than low thresholds",
            )
        except (KeyError, TypeError) as e:
            self.add(
                sec,
                "reliability_thresholds",
                FAIL,
                f"missing key {e}",
                "add the reliability section (see settings.yaml)",
            )
        hist = PROJECT_ROOT / "config" / "experiments" / "hist_buffer_1km.yaml"
        if hist.exists():
            h = read_config(hist)
            ok = h["osm"]["boundary_buffer_m"] == 1000 and h["paths"].get("run_name")
            self.add(
                sec,
                "historical_1km_config",
                PASS if ok else FAIL,
                f"{hist.name}: buffer {h['osm']['boundary_buffer_m']} m, run_name {h['paths'].get('run_name')}",
                "" if ok else "restore boundary_buffer_m: 1000 and a run_name in hist_buffer_1km.yaml",
            )
        else:
            self.add(
                sec,
                "historical_1km_config",
                WARN,
                "config/experiments/hist_buffer_1km.yaml missing",
                "restore it from version control to keep the Milestone 01 buffer reproducible",
            )

    def check_inputs(self):
        s, sec = self.s, "inputs"
        from abot.boundaries import cod_ab_path
        from abot.fetch.sources import worldpop_path

        required = {"COD-AB boundaries": cod_ab_path(s)}
        census = (
            sorted((s.raw_dir / "census_2020").glob("*.xlsx")) if (s.raw_dir / "census_2020").exists() else []
        )
        required["PSA census 2020"] = census[0] if census else s.raw_dir / "census_2020" / "*.xlsx"
        for y in s["sources"]["worldpop"]["years"]:
            required[f"WorldPop {y}"] = worldpop_path(s, y)
        for label, p in required.items():
            ok = Path(p).exists()
            self.add(
                sec,
                f"raw: {label}",
                PASS if ok else FAIL,
                Path(p).relative_to(s.root).as_posix(),
                "" if ok else "run `abot fetch` (the audit never downloads)",
            )
        manifest = load_manifest(s.raw_dir)
        if not manifest:
            self.add(
                sec,
                "manifest",
                WARN,
                "data/raw/manifest.json missing or empty",
                "run `abot fetch` to record provenance",
            )
            return
        if not self.hashes:
            self.add(sec, "manifest_sha256", INFO, "skipped (--skip-hashes)")
            return
        bad, checked = [], 0
        for rel, entry in manifest.items():
            p = s.raw_dir / rel
            if "sha256" not in entry or not p.exists():
                continue
            checked += 1
            if sha256(p) != entry["sha256"]:
                bad.append(rel)
        self.add(
            sec,
            "manifest_sha256",
            FAIL if bad else PASS,
            f"{checked} files checked" + (f"; changed: {', '.join(bad)}" if bad else ""),
            "a raw file changed after download: restore it or re-fetch and rebuild" if bad else "",
        )

    def check_outputs(self):
        s, sec = self.s, "outputs"
        if not s.gpkg.exists():
            self.add(
                sec,
                "geopackage",
                FAIL,
                f"{s.gpkg.relative_to(s.root).as_posix()} missing",
                "run `abot build`",
            )
        else:
            self.layers = [n for n, _ in pyogrio.list_layers(s.gpkg)]
            for stage, layers in STAGE_LAYERS.items():
                missing = [x for x in layers if x not in self.layers]
                self.add(
                    sec,
                    f"layers: {stage}",
                    FAIL if missing else PASS,
                    f"missing {missing}" if missing else ", ".join(layers),
                    f"run `abot build --only {stage}` and the stages after it" if missing else "",
                )
        for stage, files in STAGE_FILES.items():
            missing = [f for f in files if not (s.processed_dir / f).exists()]
            status = (WARN if stage == "report" else FAIL) if missing else PASS
            cmd = "`abot report`" if stage == "report" else f"`abot build --only {stage}`"
            self.add(
                sec,
                f"files: {stage}",
                status,
                f"missing {missing}" if missing else ", ".join(files),
                f"run {cmd}" if missing else "",
            )
        for mode in s["osm"]["network_types"]:
            p = osm.graph_path(s, mode)
            self.add(
                sec,
                f"graph_{mode}",
                PASS if p.exists() else FAIL,
                p.name,
                "" if p.exists() else "run `abot build --only osm`",
            )
        review = s.processed_dir / "review"
        missing = [f for f in REVIEW_FILES if not (review / f).exists()]
        self.add(
            sec,
            "review_files",
            WARN if missing else PASS,
            f"missing {missing}" if missing else f"{len(REVIEW_FILES)} files in {review.name}/",
            "run `abot review` to prepare the manual-review files" if missing else "",
        )

    def check_staleness(self):
        s, sec = self.s, "staleness"
        meta = qa.read_run_meta(s)
        if not meta:
            self.add(
                sec,
                "run_meta",
                WARN,
                "no data/interim/.../run_meta.json: outputs predate stage recording",
                "rebuild with `abot build` so staleness can be checked",
            )
        stamp = {k: datetime.fromisoformat(v["completed_utc"]) for k, v in meta.items()}
        for stage, ups in UPSTREAM.items():
            if stage not in stamp:
                continue
            late = [u for u in ups if u in stamp and stamp[u] > stamp[stage]]
            self.add(
                sec,
                f"order: {stage}",
                FAIL if late else PASS,
                f"upstream {late} rebuilt after {stage}" if late else f"after {', '.join(ups)}",
                f"re-run `abot build --only {stage}` (and later stages)" if late else "",
            )
        for stage, m in meta.items():
            same = m.get("config_sha256") == s.config_sha256
            self.add(
                sec,
                f"config: {stage}",
                PASS if same else WARN,
                "built with the current configuration"
                if same
                else f"built with a different configuration (buffer {m.get('boundary_buffer_m')} m, "
                f"weight {m.get('primary_weight')})",
                "" if same else f"re-run `abot build` from {stage} onwards",
            )
            code = [PROJECT_ROOT / "src" / "abot" / f for f in STAGE_CODE.get(stage, [])]
            newer = [
                c.name
                for c in code
                if c.exists() and datetime.fromtimestamp(c.stat().st_mtime).astimezone() > stamp[stage]
            ]
            if newer:
                self.add(
                    sec,
                    f"code: {stage}",
                    WARN,
                    f"{', '.join(newer)} changed after the stage ran",
                    f"re-run `abot build --only {stage}` (and later stages) if the change affects results",
                )
        prov = s.interim_dir / "osm_provenance.json"
        if prov.exists():
            b = json.loads(prov.read_text(encoding="utf-8")).get("boundary_buffer_m")
            ok = b == s["osm"]["boundary_buffer_m"]
            self.add(
                sec,
                "osm_buffer_matches_config",
                PASS if ok else FAIL,
                f"outputs {b} m, config {s['osm']['boundary_buffer_m']} m",
                ""
                if ok
                else "outputs were extracted with another buffer: run `abot build` (OSM stage onwards)",
            )
        review = s.processed_dir / "review" / "unconnected_cells_review.csv"
        if review.exists() and "accessibility" in stamp:
            ok = datetime.fromtimestamp(review.stat().st_mtime).astimezone() >= stamp["accessibility"]
            self.add(
                sec,
                "review_files_current",
                PASS if ok else WARN,
                "generated after the last accessibility build"
                if ok
                else "older than the last accessibility build",
                "" if ok else "re-run `abot review` (reviewer columns are kept)",
            )
        info_path = s.processed_dir / "review" / "m03" / "run_info.json"
        if info_path.exists() and "accessibility" in stamp:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            late = datetime.fromtimestamp(info_path.stat().st_mtime).astimezone() < stamp["accessibility"]
            problems = [
                *(["older than the last accessibility build"] if late else []),
                *(
                    ["built with another configuration"]
                    if info.get("config_sha256") != s.config_sha256
                    else []
                ),
                *(
                    ["rebuilt walk graph did not match the saved graph"]
                    if not info.get("matches_saved")
                    else []
                ),
            ]
            self.add(
                sec,
                "validation_files_current",
                WARN if problems else PASS,
                "; ".join(problems) or "review/m03 generated after the last build, same configuration",
                "re-run `abot validate`" if problems else "",
            )
        if s.run_name is None:
            self.check_experiment_runs(sec)

    def check_experiment_runs(self, sec: str):
        """Outputs of config/experiments/* runs: built with their current config and current code?
        A stale experiment folder next to fresh baseline outputs is easy to cite by mistake."""
        exp_dir = self.s.root / "config" / "experiments"
        for path in sorted(exp_dir.glob("*.yaml")) if exp_dir.exists() else []:
            es = Settings(read_config(path), root=self.s.root)
            if not es.run_name or not es.processed_dir.exists():
                continue
            meta = qa.read_run_meta(es)
            problems = []
            if not meta:
                problems.append("no run_meta.json: built before stage recording (Milestone 02 or earlier)")
            for stage, m in meta.items():
                if m.get("config_sha256") != es.config_sha256:
                    problems.append(f"{stage} built with another configuration")
                done = datetime.fromisoformat(m["completed_utc"])
                newer = [
                    c
                    for c in STAGE_CODE.get(stage, [])
                    if (PROJECT_ROOT / "src" / "abot" / c).exists()
                    and datetime.fromtimestamp(
                        (PROJECT_ROOT / "src" / "abot" / c).stat().st_mtime
                    ).astimezone()
                    > done
                ]
                if newer:
                    problems.append(f"{', '.join(newer)} changed after {stage}")
            self.add(
                sec,
                f"experiment: {es.run_name}",
                WARN if problems else PASS,
                "; ".join(problems) or f"built with {path.name} and the current code",
                f"re-run `abot --config {path.relative_to(self.s.root).as_posix()} build`, or archive the folder"
                if problems
                else "",
            )

    def check_consistency(self):
        s, sec = self.s, "consistency"
        brgy = self.layer("barangays")
        if brgy is not None:
            n, exp = len(brgy), s["city"]["expected_barangays"]
            ok = n == exp and brgy["adm4_pcode"].is_unique
            self.add(
                sec,
                "barangays",
                PASS if ok else FAIL,
                f"{n} barangays (expected {exp}), unique p-codes",
                "" if ok else "re-run `abot build --only boundaries`",
            )
        pieces = self.layer(population.PIECES_LAYER, ignore_geometry=True)
        cells = self.layer("access_cells")
        if pieces is not None:
            frac = pieces.groupby("cell_id")["frac"].sum()
            ok = bool((frac <= 1 + 1e-6).all())
            self.add(
                sec,
                "pieces_fraction",
                PASS if ok else FAIL,
                f"max cell fraction allocated {frac.max():.6f}",
                "" if ok else "a cell is allocated more than once: re-run `abot build --only population`",
            )
            name, col = population.primary_weight(s)
            needed = ["pop_wp2020", "pop_wp2026", "pop_census2020_adj", "pop"]
            miss = [c for c in needed if c not in pieces]
            if miss:
                self.add(
                    sec, "weight_columns", FAIL, f"missing {miss}", "re-run `abot build --only population`"
                )
            else:
                ok = np.allclose(pieces["pop"], pieces[col])
                self.add(
                    sec,
                    "weight_columns",
                    PASS if ok else FAIL,
                    f"original (pop_wp2020, pop_wp2026) and adjusted (pop_census2020_adj) kept apart; pop = {col}",
                    ""
                    if ok
                    else "`pop` does not equal the configured primary weight: re-run the population stage",
                )
            bp = self.csv("barangay_population.csv")
            if bp is not None and "census_adj_factor" in bp:
                adj = pieces.groupby("adm4_pcode")["pop_census2020_adj"].sum()
                alloc = bp.set_index("adm4_pcode")
                alloc = alloc[alloc["census_unallocated"] == 0]
                d = (adj.reindex(alloc.index).fillna(0) - alloc["census_2020"]).abs()
                ok = bool((d < 0.5).all())
                self.add(
                    sec,
                    "census_anchoring",
                    PASS if ok else FAIL,
                    f"{len(alloc)} barangays: adjusted totals equal PSA 2020 (max diff {d.max():.3f})",
                    "" if ok else "re-run `abot build --only population`",
                )
                un = float(bp["census_unallocated"].sum())
                self.add(
                    sec,
                    "census_unallocated",
                    WARN if un else PASS,
                    f"{un:.0f} census residents not placed",
                    "these barangays have no WorldPop 2020 cells; see rel_population" if un else "",
                )
                d2 = (
                    pieces.groupby("adm4_pcode")["pop"].sum().reindex(bp["adm4_pcode"]).fillna(0).values
                    - bp["pop"].values
                )
                ok = bool(np.abs(d2).max() < 1)
                self.add(
                    sec,
                    "barangay_population_matches_pieces",
                    PASS if ok else FAIL,
                    f"max difference {np.abs(d2).max():.2f}",
                    "" if ok else "re-run `abot build --only population`",
                )
            elif bp is not None:
                self.add(
                    sec,
                    "census_anchoring",
                    FAIL,
                    "barangay_population.csv has no census_adj_factor (pre-M02B output)",
                    "re-run `abot build`",
                )
        if cells is not None and "conn_status" in cells:
            conn = cells["conn_status"] == A.OK
            tcols = [c for c in cells.columns if c.startswith(("t_walk_", "t_drive_"))]
            miss = int((cells.loc[conn, tcols].isna()).any(axis=1).sum())
            extra = int((cells.loc[~conn, tcols].notna()).any(axis=1).sum())
            self.add(
                sec,
                "connected_cells_have_times",
                FAIL if miss else PASS,
                f"{miss} connected cells missing a time",
                "routing failed for connected cells: inspect the network components" if miss else "",
            )
            self.add(
                sec,
                "unconnected_cells_have_no_time",
                FAIL if extra else PASS,
                f"{extra} unconnected cells carry a time",
                "re-run `abot build --only accessibility`" if extra else "",
            )
            if pieces is not None and "cell_id" in cells:
                d = (
                    pieces.groupby("cell_id")["pop"].sum().reindex(cells["cell_id"]).values
                    - cells["pop"].values
                )
                ok = bool(np.nanmax(np.abs(d)) < 0.01)
                self.add(
                    sec,
                    "cell_population_matches_pieces",
                    PASS if ok else FAIL,
                    f"max difference {np.nanmax(np.abs(d)):.4f}",
                    ""
                    if ok
                    else "access_cells is older than pop_pieces: re-run `abot build --only accessibility`",
                )
        ind = self.csv("barangay_access.csv")
        if ind is not None and "pop_total" in ind:
            d = (ind["pop_connected"] + ind["pop_not_connected"] - ind["pop_total"]).abs().max()
            self.add(
                sec,
                "barangay_conservation",
                PASS if d < 0.5 else FAIL,
                f"connected + not connected = total (max diff {d:.2f})",
                "" if d < 0.5 else "re-run accessibility",
            )
            if cells is not None:
                d = abs(ind["pop_total"].sum() - cells["pop"].sum())
                self.add(
                    sec,
                    "barangay_total_equals_cells",
                    PASS if d < 1 + 0.05 * len(ind) else FAIL,
                    f"barangays {ind['pop_total'].sum():,.0f} vs cells {cells['pop'].sum():,.0f}",
                    "" if d < 1 + 0.05 * len(ind) else "re-run accessibility",
                )
            bad = []
            for mode, ths in s["accessibility"]["thresholds_min"].items():
                for g in s["indicator_groups"]:
                    cols = [f"{mode}_{g}_pct_le{t}" for t in ths]
                    if not all(c in ind for c in cols):
                        continue
                    v = ind[cols].to_numpy()
                    if (np.diff(v, axis=1) < -0.05).any() or (
                        v[:, -1] + ind["pct_not_connected"].to_numpy() > 100.15
                    ).any():
                        bad.append(f"{mode}_{g}")
            self.add(
                sec,
                "shares_and_denominators",
                FAIL if bad else PASS,
                f"inconsistent: {bad}"
                if bad
                else "shares non-decreasing; within + not connected <= 100% (all residents)",
                "re-run accessibility" if bad else "",
            )
            gp = self.layer("barangay_access")
            if gp is not None:
                ok = len(gp) == len(ind) and list(gp["adm4_pcode"]) == list(ind["adm4_pcode"])
                num = [c for c in ind.columns if c in gp and pd.api.types.is_numeric_dtype(ind[c])]
                if ok:
                    ok = np.allclose(gp[num].to_numpy(float), ind[num].to_numpy(float), equal_nan=True)
                self.add(
                    sec,
                    "csv_equals_geopackage",
                    PASS if ok else FAIL,
                    f"{len(num)} numeric columns compared",
                    "" if ok else "barangay_access.csv and the GeoPackage layer differ: re-run accessibility",
                )
            if "rel_overall" in ind and gp is not None:
                fac = self.layer("facilities")
                excl = self.csv("facility_exclusions.csv")
                redo = reliability.add_flags(
                    s,
                    gp.drop(
                        columns=[
                            c
                            for c in gp
                            if c.startswith("rel_")
                            or c in ("pop_ranking_eligible", "n_facilities_duplicate_review")
                        ]
                    ),
                    fac,
                    excl,
                )
                diff = [
                    c
                    for c in ("rel_population", "rel_network", "rel_overall", "pop_ranking_eligible")
                    if not (redo[c].astype(str).values == gp[c].astype(str).values).all()
                ]
                self.add(
                    sec,
                    "reliability_flags_reproducible",
                    FAIL if diff else PASS,
                    f"differ: {diff}" if diff else "recomputed from their inputs: identical",
                    "flags are stale or the rules changed: re-run `abot build --only accessibility`"
                    if diff
                    else "",
                )
            elif "rel_overall" not in ind:
                self.add(
                    sec,
                    "reliability_flags_reproducible",
                    FAIL,
                    "no reliability columns (pre-M02B output)",
                    "re-run `abot build`",
                )
        fac = self.layer("facilities")
        if fac is not None:
            ok = "conn_status" in fac and fac["conn_status"].notna().all()
            self.add(
                sec,
                "facility_connections_recorded",
                PASS if ok else FAIL,
                f"{len(fac)} facilities with a connection status" if ok else "facilities lack conn_status",
                "" if ok else "re-run `abot build --only accessibility`",
            )
            if ok:
                ext = fac[~fac["inside_city"].astype(bool)]
                nc = ext[ext["conn_status"] != A.OK]
                self.add(
                    sec,
                    "external_facilities",
                    INFO,
                    f"{len(ext)} outside the city; {len(nc)} not connected and never used as destinations",
                )
        warns = (
            [
                f"{st}.{k}"
                for st, checks in qa.read_all(s).items()
                for k, c in checks.items()
                if c.get("ok") is False
            ]
            if (s.interim_dir / "qa").exists()
            else []
        )
        self.add(
            sec,
            "pipeline_qa_warnings",
            WARN if warns else PASS,
            ", ".join(warns) or "no pipeline QA check failed",
            "see qa_report.md for each warning's note" if warns else "",
        )

    def check_validity(self):
        s, sec = self.s, "validity"
        bp = self.csv("barangay_population.csv")
        if bp is not None and "pop_wp2020" in bp:
            t = bp.dropna(subset=["census_2020"])
            ratio = t["pop_wp2020"].sum() / t["census_2020"].sum()
            near = int(
                (
                    ((t["pop_wp2020"] / t["census_2020"]) - NATIONAL_FACTOR).abs() / NATIONAL_FACTOR < 0.005
                ).sum()
            )
            self.add(
                sec,
                "worldpop_vs_census_city",
                INFO,
                f"WorldPop 2020 / census 2020 = {ratio:.4f}; {near} barangays within 0.5% of the national "
                f"factor {NATIONAL_FACTOR}. Agreement is by construction (census is a WorldPop input), not validation",
            )
            ape = ((t["pop_wp2020"] - t["census_2020"]).abs() / t["census_2020"].clip(lower=1)).median()
            self.add(
                sec,
                "worldpop_vs_census_barangay",
                INFO,
                f"median |WP2020 - census| = {100 * ape:.1f}% per barangay: unit alignment, not accuracy",
            )
            small = t["pop_cells_centre"] <= s["reliability"]["population"]["low_max_centre_cells"]
            ch = ((t["pop_wp2020"] - t["pop_wp2020_centre_rule"]).abs() / t["pop_wp2020"].replace(0, np.nan))[
                small
            ]
            self.add(
                sec,
                "allocation_rule_effect",
                INFO,
                f"{int(small.sum())} barangays with few cell centres: median change centre rule vs fractional "
                f"{100 * ch.median():.0f}%",
            )
        ind = self.csv("barangay_access.csv")
        if ind is not None and "rel_overall" in ind:
            for d in ("rel_population", "rel_network", "rel_facility_inventory", "rel_overall"):
                self.add(sec, d, INFO, ", ".join(f"{k} {v}" for k, v in ind[d].value_counts().items()))
            prio = s["reliability"].get("review_priority_barangays") or {}
            p = ind[ind["adm4_pcode"].isin(list(prio))]
            self.add(
                sec,
                "priority_barangays_not_connected",
                WARN if (p["rel_network"] == "low").any() else PASS,
                "; ".join(
                    f"{r.adm4_name} {r.pop_not_connected:.0f} ({r.pct_not_connected}%)"
                    for r in p.itertuples()
                ),
                "manual review pending: data/processed/review/unconnected_cells_review.csv" if len(p) else "",
            )
            tot = ind["pop_total"].sum()
            self.add(
                sec,
                "not_connected_citywide",
                INFO,
                f"{ind['pop_not_connected'].sum():,.0f} of {tot:,.0f} residents "
                f"({100 * ind['pop_not_connected'].sum() / tot:.2f}%): kept in denominators, reported separately",
            )
        sens = self.csv("drive_speed_sensitivity.csv")
        if sens is not None:
            h = sens[sens["group"] == "health_hospital"]
            col = "pct_le10" if "pct_le10" in h else h.columns[-2]
            self.add(
                sec,
                "drive_network_speed_sensitivity",
                INFO,
                "hospital, % of residents within 10 min: "
                + ", ".join(f"x{r.network_time_factor:g} {getattr(r, col)}%" for r in h.itertuples())
                + " (lower bounds)",
            )
        dup = s.processed_dir / "review" / "possible_duplicates_review.csv"
        excl = self.csv("facility_exclusions.csv")
        if excl is not None:
            n = int(excl["reason"].astype(str).str.startswith("possible duplicate").sum())
            pending = n
            if dup.exists():
                r = pd.read_csv(dup, dtype=str, keep_default_na=False)
                pending = int((r["review_status"] == "pending").sum())
            self.add(
                sec,
                "possible_duplicates",
                WARN if pending else PASS,
                f"{n} flagged pairs; {pending} pending manual review; none merged automatically",
                "review possible_duplicates_review.csv (`abot review` creates it)" if pending else "",
            )
        bq = qa.read_all(s).get("boundaries", {}) if (s.interim_dir / "qa").exists() else {}
        if "city_area_km2" in bq:
            self.add(
                sec,
                "boundary_area",
                INFO,
                f"{bq['city_area_km2']['value']} km2 = area of the COD-AB v03 polygon (land), not the official land area",
            )

    def check_archive(self):
        sec, arch = "archive", self.s.data_dir / "archive"
        m01 = arch / "m01_3edc0dd"
        self.add(
            sec,
            "m01_archive_present",
            PASS if m01.is_dir() else FAIL,
            m01.relative_to(self.s.root).as_posix(),
            "" if m01.is_dir() else "the Milestone 01 archive is missing: restore it from backup",
        )
        for man in sorted(arch.glob("*.sha256.json")) if arch.exists() else []:
            rec = json.loads(man.read_text(encoding="utf-8"))
            d = arch / rec["archive"]
            if not self.hashes:
                self.add(sec, rec["archive"], INFO, "hash check skipped (--skip-hashes)")
                continue
            changed = [f for f, h in rec["files"].items() if not (d / f).exists() or sha256(d / f) != h]
            extra = (
                [
                    p.relative_to(d).as_posix()
                    for p in d.rglob("*")
                    if p.is_file() and p.relative_to(d).as_posix() not in rec["files"]
                ]
                if d.exists()
                else []
            )
            status = FAIL if changed else (WARN if extra else PASS)
            self.add(
                sec,
                rec["archive"],
                status,
                f"{len(rec['files'])} files match SHA-256 recorded {rec['recorded_utc']}"
                if status == PASS
                else f"changed/missing {changed}; unexpected {extra}",
                "" if status == PASS else "an archived output was modified: restore it from backup",
            )
        if m01.is_dir() and not (arch / "m01_3edc0dd.sha256.json").exists():
            self.add(
                sec,
                "m01_archive_hashes",
                WARN,
                "no SHA-256 record for the M01 archive",
                "record one (see docs)",
            )

    def run(self) -> list[Finding]:
        for step in (
            self.check_config,
            self.check_inputs,
            self.check_outputs,
            self.check_staleness,
            self.check_consistency,
            self.check_validity,
            self.check_archive,
        ):
            try:
                step()
            except Exception as e:  # noqa: BLE001 — an audit must report, not crash
                self.add(
                    step.__name__.removeprefix("check_"),
                    "audit_error",
                    FAIL,
                    f"{type(e).__name__}: {e}",
                    "the outputs are probably from an older pipeline version: re-run `abot build`",
                )
        return self.findings


def to_markdown(s: Settings, findings: list[Finding]) -> str:
    counts = pd.Series([f.status for f in findings]).value_counts()
    lines = [
        f"# ABOT audit — run `{s.run_name or 'baseline'}` ({datetime.now().isoformat(timespec='seconds')})",
        "",
        "Read-only: nothing was downloaded, written to data/ or repaired.",
        "",
        " | ".join(f"{k} {int(counts.get(k, 0))}" for k in (PASS, WARN, FAIL, INFO)),
        "",
        "| section | check | status | detail | action |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {f.section} | {f.check} | {f.status} | {f.detail} | {f.action} |" for f in findings]
    return "\n".join(lines) + "\n"


def run(s: Settings, config_path: Path, output: Path | None = None, hashes: bool = True) -> int:
    findings = Audit(s, config_path, hashes).run()
    data_dir = s.data_dir.resolve()
    for f in findings:
        mark = {PASS: " ", INFO: "i", WARN: "!", FAIL: "X"}[f.status]
        print(
            f"{mark} {f.status:<4} {f.section:<11} {f.check}: {f.detail}"
            + (f"\n         -> {f.action}" if f.action else "")
        )
    text = to_markdown(s, findings)
    if output:
        output = Path(output).resolve()
        if data_dir in output.parents:
            raise SystemExit(
                "abot audit is read-only: write the report outside data/ (e.g. --output audit.md)"
            )
        output.write_text(text, encoding="utf-8")
        print(f"\nwritten to {output}")
    n_fail = sum(f.status == FAIL for f in findings)
    print(f"\n{text.splitlines()[4]}")
    return 1 if n_fail else 0
