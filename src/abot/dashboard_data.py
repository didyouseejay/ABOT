"""`abot export-dashboard`: the static dashboard data bundle (contract `abot-dashboard v1.0.0`).

docs/DASHBOARD_DATA_CONTRACT.md is the authority; section and rule numbers below refer to it. The
exporter is read-only over the analytical outputs: it selects, renames, reshapes, reprojects and rounds
values ABOT has already computed and never computes a new accessibility indicator (R2). It writes only
under <processed>/dashboard/ (R14): the bundle is built in a temporary sibling of v1/, validated as
written, every source is re-hashed, and only then does it replace v1/ (§10.1). A failed export leaves
the previous bundle untouched.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon, mapping, shape

from abot import __version__
from abot import audit as audit_mod
from abot import components as C
from abot.config import Settings
from abot.fetch.common import sha256
from abot.fetch.targeted import LAT_RANGE, LON_RANGE

CONTRACT, CONTRACT_VERSION = "abot-dashboard", "1.0.0"
BUNDLE = "v1"
MAX_FILE_BYTES = 4_000_000  # §5.1: uncompressed bytes as written
BIN_WIDTH_MIN, CLOSED_MAX_MIN = 1, 60  # §7.2 walk_distribution (Q5)
SIMPLIFY_DEG = 2e-5  # §8.2: an angle in EPSG:4326, not metres (Q1)
CATS = C.CATEGORIES
LOCAL = C.LOCAL
OK = "connected"
DOCUMENTS = [
    ("Methodology", "docs/METHODOLOGY.md"),
    ("Dashboard data contract", "docs/DASHBOARD_DATA_CONTRACT.md"),
    ("Milestone 04 results", "docs/MILESTONE_04_RESULTS.md"),
    ("Milestone 04 follow-up results", "docs/MILESTONE_04_FOLLOWUP_RESULTS.md"),
    ("Milestone 04 access taxonomy", "docs/MILESTONE_04_ACCESS_TAXONOMY.md"),
    ("Milestone 04 snapshot review", "docs/MILESTONE_04_SNAPSHOT_REVIEW.md"),
]
AUDIT_IMPL = "abot.audit.Audit.run(hashes=True), in-process, read-only"
STATEMENTS = {  # §6.3: code -> (applies to, text); {…} figures are filled from the sources
    "DQ-SHARE-ALL": (
        "every pct_le*",
        "Share of all residents, including those without a network connection.",
    ),
    "DQ-MEAN-CONN": (
        "every mean_min, p90_min",
        (
            "A3: Describes residents connected to the main walk network only. "
            "A1: Describes A1-connected residents only."
        ),
    ),
    "DQ-A1-OPT": (
        "every A1 walking value",
        "A1 is an optimistic comparison scenario, not an observed result or a verified upper bound.",
    ),
    "DQ-DRIVE": (
        "every drive value",
        (
            "Modelled uncongested car travel time: a lower bound that assumes car availability; "
            "no congestion, parking or turn delays."
        ),
    ),
    "DQ-LOCAL": (
        "local / uncertain internal values",
        "Travel within an isolated network component only; never counted as citywide access.",
    ),
    "DQ-FAC-OSM": (
        "facility counts and maps",
        "Mapped OpenStreetMap features; completeness unverified against official registries.",
    ),
    "DQ-DUP": (
        "facilities, facility counts",
        (
            "{pending} of {pairs} possible duplicate pairs pending review; {likely} pairs judged likely "
            "duplicates but not merged (both records still counted). No pair is merged automatically."
        ),
    ),
    "DQ-POP-ALLOC": (
        "barangay values, cells",
        (
            "Barangay values use a fractional allocation of 100 m population cells; cell values cannot be "
            "summed to barangays."
        ),
    ),
    "DQ-RESOLVED": (
        "Calahunan, Hibao-an Sur",
        "Included in all totals; resolved separately in Milestone 03.",
    ),
    "DQ-ANALYSIS-ONLY": (
        "access impact, access taxonomy, corridors",
        "Analysis only: not applied to the network or to any indicator.",
    ),
    "DQ-PHYS-NOT-PUBLIC": (
        "gap evidence",
        "Physical connection in OSM topology is not public pedestrian access.",
    ),
    "DQ-BBOX": ("component boxes", "Bounding box of the component's nodes, not its network geometry."),
    "DQ-DIST": (
        "city.walk_distribution",
        (
            "Distribution of citywide walking times of network-connected residents; residents without a "
            "citywide time are outside the curve but inside the denominator."
        ),
    ),
    "DQ-SIMPLIFIED": (
        "barangay polygons",
        "Boundaries simplified for display; areas and all values use the original boundaries.",
    ),
}
A3B, A3C, A1B = (
    "component_aware/barangay_access_a3.csv",
    "component_aware/citywide_a3.csv",
    "barangay_access.csv",
)
DS = "drive_speed_sensitivity.csv"


class ExportError(Exception):
    """A rule of the contract cannot be met: nothing is written."""


# --- JSON helpers ---------------------------------------------------------------------------------


def dumps(obj) -> bytes:
    """§5.1 deterministic serialisation."""
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def nn(v):
    """A JSON scalar; NaN / NA become null, never 0 or "" (R11)."""
    if v is None or v is pd.NA:
        return None
    if isinstance(v, bool | np.bool_):
        return bool(v)
    if isinstance(v, int | np.integer):
        return int(v)
    if isinstance(v, float | np.floating):
        return None if math.isnan(v) else float(v)
    return v


def as_int(v):
    v = nn(v)
    if v is None:
        return None
    if float(v) != int(v):
        raise ExportError(f"expected an integer, got {v}")
    return int(v)


def records(df: pd.DataFrame, cols: list[str], ints: tuple = ()) -> list[dict]:
    return [{c: (as_int(r[c]) if c in ints else nn(r[c])) for c in cols} for _, r in df.iterrows()]


def round6(geom):
    """Coordinates rounded with Python round(x, 6) (§8.1)."""
    return shapely.transform(
        geom, lambda a: np.array([[round(float(x), 6), round(float(y), 6)] for x, y in a]).reshape(-1, 2)
    )


def rel(s: Settings, p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(s.root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- sources (§7.1.1) -----------------------------------------------------------------------------


def source_paths(s: Settings, config_path: Path) -> list[tuple[Path, list[str]]]:
    P, INTERIM = s.processed_dir, s.interim_dir
    m04 = P / "review" / "m04"
    out = [
        (P / A3B, ["A3 barangay values (R3)"]),
        (P / "component_aware" / "cells_a3.csv", ["cells (A3 part, coordinates)", "city.walk_distribution"]),
        (P / A3C, ["city A3/A1 walking and population"]),
        (P / "component_aware" / "run_info.json", ["a3_run_info", "scenario labels", "V-S2", "V-S3"]),
        (P / A1B, ["A1 barangay values (R4)"]),
        (P / "facility_inventory.csv", ["facility inventory"]),
        (P / "facilities.csv", ["V-G2 coordinate check"]),
        (P / DS, ["city A1 drive and sensitivity"]),
        (P / "barangay_population.csv", ["V-S2 baseline hash"]),
        (
            s.gpkg,
            ["layers barangays, access_cells, facilities, facility_roles", "V-S2 baseline hash"],
        ),
        (P / "review" / "possible_duplicates_review.csv", ["facility duplicate review", "DQ-DUP"]),
        (P / "review" / "m03" / "validation.gpkg", ["layers network_fragments, fragment_gaps"]),
        (m04 / "facilities_by_approach.csv", ["facilities.off_main_network_in"]),
        (m04 / "approach_comparison.csv", ["network.approaches", "network.approaches_by_group"]),
        (m04 / "transition_A1_to_A3_pop.csv", ["network.transition_a1_to_a3"]),
        (m04 / "component_inventory.csv", ["network.components", "network.component_classes"]),
        (m04 / "gap_investigation.csv", ["network.gap_evidence"]),
        (m04 / "snapshot_corridor_analysis.csv", ["network.gap_evidence"]),
        (m04 / "access_classification_summary.csv", ["network.access_classification"]),
        (m04 / "access_impact.csv", ["network.access_impact"]),
        (m04 / "access_impact_by_group.csv", ["network.access_impact_by_group"]),
        (m04 / "taxonomy_check.json", ["V-S4", "source_validation.component_classes_check"]),
        (INTERIM / "run_meta.json", ["stage_completed_utc", "V-S3"]),
        (INTERIM / "osm_provenance.json", ["provenance.osm"]),
        *[(p, ["provenance.qa"]) for p in sorted((INTERIM / "qa").glob("*.json"))],
        (s.raw_dir / "manifest.json", ["provenance.sources"]),
        (Path(config_path), ["indicator groups, thresholds", "config_sha256"]),
    ]
    return out


@dataclass
class Sources:
    a3: pd.DataFrame
    a1: pd.DataFrame
    city: pd.DataFrame
    c3: pd.DataFrame
    ac: pd.DataFrame
    inv: pd.DataFrame
    fcsv: pd.DataFrame
    ds: pd.DataFrame
    brgy: gpd.GeoDataFrame
    fac: gpd.GeoDataFrame
    roles: gpd.GeoDataFrame
    dup: pd.DataFrame
    frags: gpd.GeoDataFrame
    gaps: gpd.GeoDataFrame
    fba: pd.DataFrame
    appr: pd.DataFrame
    trans: pd.DataFrame
    comp: pd.DataFrame
    gapinv: pd.DataFrame
    corr: pd.DataFrame
    acs: pd.DataFrame
    imp: pd.DataFrame
    impg: pd.DataFrame
    taxonomy: dict
    run_info: dict
    run_meta: dict
    osm_prov: dict
    qa: dict
    raw_manifest: dict
    extra: dict = field(default_factory=dict)


def load(s: Settings) -> Sources:
    P, INTERIM = s.processed_dir, s.interim_dir
    m04 = P / "review" / "m04"
    ids = {"adm4_pcode": str, "cell_id": str}

    def csv(p, **kw):
        return pd.read_csv(p, dtype=ids, **kw)

    def js(p):
        return json.loads(Path(p).read_text(encoding="utf-8"))

    val = P / "review" / "m03" / "validation.gpkg"
    return Sources(
        a3=csv(P / A3B),
        a1=csv(P / A1B),
        city=pd.read_csv(P / A3C).set_index("metric"),
        c3=csv(P / "component_aware" / "cells_a3.csv"),
        ac=gpd.read_file(s.gpkg, layer="access_cells", ignore_geometry=True).astype({"cell_id": str}),
        inv=pd.read_csv(P / "facility_inventory.csv"),
        fcsv=pd.read_csv(P / "facilities.csv"),
        ds=pd.read_csv(P / DS),
        brgy=gpd.read_file(s.gpkg, layer="barangays"),
        fac=gpd.read_file(s.gpkg, layer="facilities"),
        roles=gpd.read_file(s.gpkg, layer="facility_roles", ignore_geometry=True),
        dup=pd.read_csv(P / "review" / "possible_duplicates_review.csv", dtype=str, keep_default_na=False),
        frags=gpd.read_file(val, layer="network_fragments"),
        gaps=gpd.read_file(val, layer="fragment_gaps"),
        fba=pd.read_csv(m04 / "facilities_by_approach.csv"),
        appr=pd.read_csv(m04 / "approach_comparison.csv"),
        trans=pd.read_csv(m04 / "transition_A1_to_A3_pop.csv"),
        comp=pd.read_csv(m04 / "component_inventory.csv"),
        gapinv=pd.read_csv(m04 / "gap_investigation.csv"),
        corr=pd.read_csv(m04 / "snapshot_corridor_analysis.csv"),
        acs=pd.read_csv(m04 / "access_classification_summary.csv"),
        imp=pd.read_csv(m04 / "access_impact.csv"),
        impg=pd.read_csv(m04 / "access_impact_by_group.csv"),
        taxonomy=js(m04 / "taxonomy_check.json"),
        run_info=js(P / "component_aware" / "run_info.json"),
        run_meta=js(INTERIM / "run_meta.json"),
        osm_prov=js(INTERIM / "osm_provenance.json"),
        qa={p.stem: js(p) for p in sorted((INTERIM / "qa").glob("*.json"))},
        raw_manifest=js(s.raw_dir / "manifest.json"),
    )


def source_checks(s: Settings, src: Sources) -> list[str]:
    """V-S2, V-S3, V-S4 (V-S1 is checked before loading)."""
    bad = []
    for f, h in src.run_info["baseline_sha256"].items():
        p = s.processed_dir / f
        if not p.exists() or sha256(p) != h:
            bad.append(f"V-S2: {f} differs from run_info.baseline_sha256")
    stages = {k: v.get("config_sha256") for k, v in src.run_meta.items()}
    if (
        any(v != s.config_sha256 for v in stages.values())
        or src.run_info.get("config_sha256") != s.config_sha256
    ):
        bad.append(f"V-S3: config_sha256 differs (config {s.config_sha256[:12]}, stages {stages}, run_info "
                   f"{str(src.run_info.get('config_sha256'))[:12]})")  # fmt: skip
    t = src.taxonomy
    if not (t.get("identical") is True and t.get("components_compared") == 112):
        bad.append(f"V-S4: taxonomy_check {t.get('identical')}, {t.get('components_compared')} components")
    return bad


# --- audit (§6.1.1) -------------------------------------------------------------------------------


def run_audit(s: Settings, config_path: Path, skip: bool) -> tuple[dict, list]:
    """(audit block, findings that block the export). Never invents a result."""
    base = {"implementation": AUDIT_IMPL, "findings": []}
    if skip:
        return {
            "status": "not_run", "ran_utc": None, "implementation": AUDIT_IMPL, "outcome": None,
            "counts": None, "findings": [], "reason": "skipped on request (--skip-audit)",
        }, []  # fmt: skip
    ran = now_utc()
    try:
        findings = audit_mod.Audit(s, Path(config_path), hashes=True).run()
    except Exception as e:  # noqa: BLE001 — recorded as status "error", which blocks the export
        block = {"status": "error", "ran_utc": ran, **base, "outcome": None, "counts": None,
                 "reason": f"{type(e).__name__}: {e}"}  # fmt: skip
        return audit_block_order(block), [block["reason"]]
    return audit_from_findings(findings, ran)


def audit_from_findings(findings: list, ran: str) -> tuple[dict, list]:
    st = [f.status for f in findings]
    counts = {
        k.lower(): st.count(k) for k in (audit_mod.PASS, audit_mod.WARN, audit_mod.FAIL, audit_mod.INFO)
    }
    outcome = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    warn = [
        {"section": f.section, "check": f.check, "status": f.status, "detail": f.detail, "action": f.action}
        for f in findings
        if f.status == audit_mod.WARN
    ]
    fail = [f"{f.section} {f.check}: {f.detail}" for f in findings if f.status == audit_mod.FAIL]
    block = {"status": "obtained", "ran_utc": ran, "implementation": AUDIT_IMPL, "outcome": outcome,
             "counts": counts, "findings": warn, "reason": None}  # fmt: skip
    return block, fail


def audit_block_order(b: dict) -> dict:
    keys = ["status", "ran_utc", "implementation", "outcome", "counts", "findings", "reason"]
    return {k: b.get(k) for k in keys}


def audit_allows_export(block: dict, skip: bool) -> bool:
    """§6.1.1: pass and warn allow, fail and error block, not_run only on request."""
    if block["status"] == "not_run":
        return skip
    return block["status"] == "obtained" and block["outcome"] in ("pass", "warn")


# --- catalogue (§4.1) -----------------------------------------------------------------------------


def catalog(s: Settings) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    """(catalogue entries, {barangay-level id: (source frame, column)})."""
    groups, th = list(s["indicator_groups"]), s["accessibility"]["thresholds_min"]
    cat, bsrc = [], {}

    def add(i, levels, scen, mode, g, stat, unit, num, den, popd, role, sfile, scol, stm, b=None):
        cat.append({"id": i, "levels": levels, "scenario": scen, "mode": mode, "group": g, "statistic": stat,
                    "unit": unit, "numerator": num, "denominator": den, "population_described": popd,
                    "role": role, "source_file": sfile, "source_column": scol, "statements": stm})  # fmt: skip
        if b:
            bsrc[i] = b

    BC, B, Ci = ["barangay", "city"], ["barangay"], ["city"]
    ALL = "all residents of the barangay or city"
    for g in groups:
        for n in th["walk"]:
            add(f"A3.walk.{g}.pct_le{n}", BC, "A3", "walk", g, f"pct_le{n}", "%",
                f"residents in network_connected cells with a citywide walking time <= {n} min", "all residents", ALL,
                "primary", f"{A3B}; {A3C}", f"walk_{g}_pct_le{n}; metric walk_{g}_pct_le{n} col A3",
                ["DQ-SHARE-ALL", "DQ-POP-ALLOC"], ("a3", f"walk_{g}_pct_le{n}"))  # fmt: skip
        add(f"A3.walk.{g}.mean_min", BC, "A3", "walk", g, "mean_min", "minutes",
            "population-weighted mean citywide walking time", None, "network-connected residents with a time",
            "primary", f"{A3B}; {A3C}", f"walk_{g}_mean_min; metric walk_{g}_mean_min col A3",
            ["DQ-MEAN-CONN", "DQ-POP-ALLOC"], ("a3", f"walk_{g}_mean_min"))  # fmt: skip
        add(f"A3.walk.{g}.p90_min", B, "A3", "walk", g, "p90_min", "minutes",
            "population-weighted 90th percentile of citywide walking time", None,
            "network-connected residents with a time", "primary", A3B, f"walk_{g}_p90_min",
            ["DQ-MEAN-CONN", "DQ-POP-ALLOC"], ("a3", f"walk_{g}_p90_min"))  # fmt: skip
        for short, catname in (("local", "locally_connected"), ("uncertain", "access_uncertain")):
            add(f"A3.walk.{g}.pop_{short}_internal", B, "A3", "walk", g, f"pop_{short}_internal", "residents",
                f"residents in {catname} cells with an internal time to a facility in their own component", None,
                f"{catname} residents of the barangay", "evidence_only", A3B, f"pop_{short}_internal_{g}",
                ["DQ-LOCAL", "DQ-POP-ALLOC"], ("a3", f"pop_{short}_internal_{g}"))  # fmt: skip
            add(f"A3.walk.{g}.pop_{short}_internal_le15", B, "A3", "walk", g, f"pop_{short}_internal_le15",
                "residents", f"residents in {catname} cells with an internal time <= 15 min", None,
                f"{catname} residents of the barangay", "evidence_only", A3B, f"pop_{short}_internal_{g}_le15",
                ["DQ-LOCAL", "DQ-POP-ALLOC"], ("a3", f"pop_{short}_internal_{g}_le15"))  # fmt: skip
            col = "A3_local_internal_pop" if short == "local" else "A3_uncertain_internal_pop"
            for n in th["walk"]:
                add(f"A3.walk.{g}.{short}_internal_pop_le{n}", Ci, "A3", "walk", g, f"{short}_internal_pop_le{n}",
                    "residents", f"{catname} residents with an internal time <= {n} min", None,
                    f"{catname} residents of the city", "evidence_only", A3C,
                    f"metric walk_{g}_pct_le{n} col {col}", ["DQ-LOCAL"])  # fmt: skip
        for n in th["walk"]:
            add(f"A1.walk.{g}.pct_le{n}", BC, "A1", "walk", g, f"pct_le{n}", "%",
                f"A1-connected residents with a walking time <= {n} min", "all residents", ALL, "comparative",
                f"{A1B}; {A3C}", f"walk_{g}_pct_le{n}; metric walk_{g}_pct_le{n} col A1",
                ["DQ-SHARE-ALL", "DQ-A1-OPT", "DQ-POP-ALLOC"], ("a1", f"walk_{g}_pct_le{n}"))  # fmt: skip
        add(f"A1.walk.{g}.mean_min", BC, "A1", "walk", g, "mean_min", "minutes",
            "population-weighted mean walking time", None, "A1-connected residents with a time", "comparative",
            f"{A1B}; {A3C}", f"walk_{g}_mean_min; metric walk_{g}_mean_min col A1",
            ["DQ-MEAN-CONN", "DQ-A1-OPT", "DQ-POP-ALLOC"], ("a1", f"walk_{g}_mean_min"))  # fmt: skip
        add(f"A1.walk.{g}.p90_min", B, "A1", "walk", g, "p90_min", "minutes",
            "population-weighted 90th percentile walking time", None, "A1-connected residents with a time",
            "comparative", A1B, f"walk_{g}_p90_min", ["DQ-MEAN-CONN", "DQ-A1-OPT", "DQ-POP-ALLOC"],
            ("a1", f"walk_{g}_p90_min"))  # fmt: skip
        for n in th["drive"]:
            add(f"A1.drive.{g}.pct_le{n}", BC, "A1", "drive", g, f"pct_le{n}", "%",
                f"A1-connected residents with a drive time <= {n} min", "all residents", ALL, "primary",
                f"{A1B}; {DS}", f"drive_{g}_pct_le{n}; pct_le{n} (network_time_factor 1.0)",
                ["DQ-SHARE-ALL", "DQ-DRIVE", "DQ-POP-ALLOC"], ("a1", f"drive_{g}_pct_le{n}"))  # fmt: skip
        add(f"A1.drive.{g}.mean_min", BC, "A1", "drive", g, "mean_min", "minutes",
            "population-weighted mean drive time", None, "A1-connected residents with a time", "primary",
            f"{A1B}; {DS}", f"drive_{g}_mean_min; mean_min (network_time_factor 1.0)",
            ["DQ-MEAN-CONN", "DQ-DRIVE", "DQ-POP-ALLOC"], ("a1", f"drive_{g}_mean_min"))  # fmt: skip
        add(f"A1.drive.{g}.p90_min", B, "A1", "drive", g, "p90_min", "minutes",
            "population-weighted 90th percentile drive time", None, "A1-connected residents with a time",
            "primary", A1B, f"drive_{g}_p90_min", ["DQ-MEAN-CONN", "DQ-DRIVE", "DQ-POP-ALLOC"],
            ("a1", f"drive_{g}_p90_min"))  # fmt: skip
        add(f"A1.drive_sensitivity.{g}.mean_min", Ci, "A1", "drive", g, "mean_min", "minutes",
            "population-weighted mean drive time, drive-network leg x network_time_factor", None,
            "A1-connected residents with a time", "evidence_only", DS, "mean_min (network_time_factor 1.5, 2.0)",
            ["DQ-MEAN-CONN", "DQ-DRIVE"])  # fmt: skip
        for n in th["drive"]:
            add(f"A1.drive_sensitivity.{g}.pct_le{n}", Ci, "A1", "drive", g, f"pct_le{n}", "%",
                f"A1-connected residents with a drive time <= {n} min, drive-network leg x network_time_factor",
                "all residents", "all residents of the city", "evidence_only", DS,
                f"pct_le{n} (network_time_factor 1.5, 2.0)", ["DQ-SHARE-ALL", "DQ-DRIVE"])  # fmt: skip
    for c in CATS:
        add(f"A3.population.pct_{c}", BC, "A3", "none", None, f"pct_{c}", "%", f"residents in {c} cells",
            "all residents", ALL, "primary", f"{A3B}; {A3C}", f"pct_{c}; metric pop_{c} col A3_pct",
            ["DQ-POP-ALLOC"], ("a3", f"pct_{c}"))  # fmt: skip
        add(f"A3.population.pop_{c}", BC, "A3", "none", None, f"pop_{c}", "residents", f"residents in {c} cells",
            None, "residents of the barangay or city", "primary", f"{A3B}; {A3C}", f"pop_{c}; metric pop_{c} col A3",
            ["DQ-POP-ALLOC"], ("a3", f"pop_{c}"))  # fmt: skip
    add("A1.population.pop_connected", BC, "A1", "none", None, "pop_connected", "residents",
        "A1-connected residents", None, "residents of the barangay or city", "comparative", f"{A1B}; {A3C}",
        "pop_connected; metric pop_connected_A1_optimistic col A1", ["DQ-A1-OPT", "DQ-POP-ALLOC"],
        ("a1", "pop_connected"))  # fmt: skip
    add("A1.population.pct_connected", Ci, "A1", "none", None, "pct_connected", "%", "A1-connected residents",
        "all residents", "all residents of the city", "comparative", A3C,
        "metric pop_connected_A1_optimistic col A1_pct", ["DQ-A1-OPT"])  # fmt: skip
    add("A1.population.pop_not_connected", B, "A1", "none", None, "pop_not_connected", "residents",
        "A1 not-connected residents", None, "residents of the barangay", "comparative", A1B, "pop_not_connected",
        ["DQ-A1-OPT", "DQ-POP-ALLOC"], ("a1", "pop_not_connected"))  # fmt: skip
    add("A1.population.pct_not_connected", BC, "A1", "none", None, "pct_not_connected", "%",
        "A1 not-connected residents", "all residents", ALL, "comparative", f"{A1B}; {DS}",
        "pct_not_connected; pct_not_connected (identical on every row)", ["DQ-A1-OPT", "DQ-POP-ALLOC"],
        ("a1", "pct_not_connected"))  # fmt: skip
    flag = s["accessibility"]["connection"]["drive_access_flag_m"]
    add("A1.drive.pop_drive_access_gt_flag", B, "A1", "drive", None, "pop_drive_access_gt_flag", "residents",
        f"residents whose routed walk to the drive network exceeds {flag} m", None, "residents of the barangay",
        "evidence_only", A1B, "pop_drive_access_gt_flag", ["DQ-DRIVE", "DQ-POP-ALLOC"],
        ("a1", "pop_drive_access_gt_flag"))  # fmt: skip
    return cat, bsrc


# --- builders -------------------------------------------------------------------------------------


@dataclass
class Ctx:
    s: Settings
    src: Sources
    generated: str
    source_validation: dict
    catalog: list
    bsrc: dict


def dq(ctx: Ctx, role, scenario, mode, statements, analysis_only=False) -> dict:
    return {"role": role, "scenario": scenario, "mode": mode, "analysis_only": analysis_only,
            "source_validation": ctx.source_validation, "statements": statements, "known_issues": []}  # fmt: skip


def envelope(ctx: Ctx, dataset: str, role: str, data_quality: dict) -> dict:
    return {"contract": CONTRACT, "contract_version": CONTRACT_VERSION, "dataset": dataset,
            "generated_utc": ctx.generated, "role": role, "data_quality": data_quality}  # fmt: skip


def dup_counts(dup: pd.DataFrame) -> dict:
    return {
        "pairs": len(dup),
        "pending": int((dup["review_status"] == "pending").sum()),
        "likely": int((dup["reviewer_decision"] == "likely_duplicate_not_merged").sum()),
    }


def statements(src: Sources) -> list[dict]:
    d = dup_counts(src.dup)
    return [
        {"code": k, "applies_to": a, "text": t.format(**d) if k == "DQ-DUP" else t}
        for k, (a, t) in STATEMENTS.items()
    ]


def limitations(src: Sources) -> list[dict]:
    """§11, figures from the sources."""
    d = dup_counts(src.dup)
    rp = src.a1["rel_population"].value_counts()
    city = src.city
    return [
        {"code": "L1", "text": "A1 is optimistic and A3 is a reporting scenario: neither is observed travel or a verified bound."},
        {"code": "L2", "text": "A3 is walking only; driving is A1 only, uncongested, a lower bound, assumes a car. No public transport."},
        {"code": "L3", "text": f"Facility inventory is OSM, unverified for all {len(src.a1)} barangays; evacuation, transport and "
         f"government are descriptive only; {d['pending']} of {d['pairs']} possible duplicate pairs pending review, "
         f"{d['likely']} likely duplicates not merged."},
        {"code": "L4", "text": "Population: census-anchored WorldPop with fractional barangay allocation; rel_population low in "
         f"{int(rp.get('low', 0))} and caution in {int(rp.get('caution', 0))} barangays; cells cannot be summed to barangays."},
        {"code": "L5", "text": f"{city.loc['pop_unconnected', 'A3']:,.1f} residents unconnected and "
         f"{city.loc['pop_locally_connected', 'A3']:,.1f} locally connected (A3); Calahunan and Hibao-an Sur resolved "
         "separately and included in all totals."},
        {"code": "L6", "text": "Access tags are reported, not applied; F001, F100, F101 are physically connected in OSM topology "
         "but mapped private, not_public, authorised group unspecified, pending field verification."},
        {"code": "L7", "text": "Travel times are to the nearest facility only: no capacity, quality, opening hours or catchment."},
        {"code": "L8", "text": f"Component geometry exists for {len(src.frags)} fragments only."},
    ]  # fmt: skip


def walk_distribution(t: np.ndarray, w: np.ndarray, total: float) -> dict:
    """§7.2: right-closed 1-minute bins 1..60, an open bin > 60, cumulative share of ALL residents."""
    ok = ~np.isnan(t)
    k = np.ceil(t[ok]).astype(int)
    k[k < 1] = 1  # t = 0 belongs to bin 1
    raw = np.bincount(np.minimum(k, CLOSED_MAX_MIN + 1), weights=w[ok], minlength=CLOSED_MAX_MIN + 2)
    bins = [
        {"lower_min": i - 1, "upper_min": i, "pop": round(float(raw[i]), 1)}
        for i in range(1, CLOSED_MAX_MIN + 1)
    ]
    bins.append(
        {"lower_min": CLOSED_MAX_MIN, "upper_min": None, "pop": round(float(raw[CLOSED_MAX_MIN + 1]), 1)}
    )
    cum = np.cumsum(raw[1 : CLOSED_MAX_MIN + 1])
    with_time = float(w[ok].sum())
    cumulative = [{"minutes": i, "pct_all_residents": round(100 * float(cum[i - 1]) / total, 2)}
                  for i in range(1, CLOSED_MAX_MIN + 1)]  # fmt: skip
    cumulative.append({"minutes": None, "pct_all_residents": round(100 * with_time / total, 2)})
    return {"bins": bins, "cumulative": cumulative, "pop_with_time": round(with_time, 1),
            "pop_open_bin": round(float(raw[CLOSED_MAX_MIN + 1]), 1), "pop_total": round(total, 1)}  # fmt: skip


def build_city(ctx: Ctx) -> dict:
    s, src = ctx.s, ctx.src
    city, th, groups = src.city, s["accessibility"]["thresholds_min"], list(s["indicator_groups"])
    nc = src.ds["pct_not_connected"].unique()
    if len(nc) != 1:
        raise ExportError(f"drive_speed_sensitivity.pct_not_connected differs between rows: {nc}")
    population = {
        "total": float(src.run_info["population_total"]),
        "a3": {
            c: {"pop": nn(city.loc[f"pop_{c}", "A3"]), "pct": nn(city.loc[f"pop_{c}", "A3_pct"])}
            for c in CATS
        },
        "a1": {
            "connected_pop": nn(city.loc["pop_connected_A1_optimistic", "A1"]),
            "connected_pct": nn(city.loc["pop_connected_A1_optimistic", "A1_pct"]),
            "not_connected_pct": float(nc[0]),
        },
    }
    walk, internal, dist = [], [], []
    w = src.c3["pop"].to_numpy(float)
    total = float(w.sum())
    for g in groups:
        for sc, role in (("A3", "primary"), ("A1", "comparative")):
            for stat in [*(f"pct_le{n}" for n in th["walk"]), "mean_min"]:
                walk.append({"indicator_id": f"{sc}.walk.{g}.{stat}", "group": g, "scenario": sc, "statistic": stat,
                             "value": nn(city.loc[f"walk_{g}_{stat}", sc]),
                             "unit": "minutes" if stat == "mean_min" else "%", "role": role})  # fmt: skip
        for short, catname, col in (("local", "locally_connected", "A3_local_internal_pop"),
                                    ("uncertain", "access_uncertain", "A3_uncertain_internal_pop")):  # fmt: skip
            for n in th["walk"]:
                internal.append({"indicator_id": f"A3.walk.{g}.{short}_internal_pop_le{n}", "group": g,
                                 "category": catname, "threshold_min": n,
                                 "value": nn(city.loc[f"walk_{g}_pct_le{n}", col]), "unit": "residents",
                                 "role": "evidence_only"})  # fmt: skip
        d = walk_distribution(src.c3[f"t_walk_{g}_citywide"].to_numpy(float), w, total)
        dist.append({"group": g, "scenario": "A3", **d})
    drive = []
    for _, r in src.ds.iterrows():
        k = float(r["network_time_factor"])
        prefix, role = ("A1.drive", "primary") if k == 1.0 else ("A1.drive_sensitivity", "evidence_only")
        for stat in ["mean_min", *(f"pct_le{n}" for n in th["drive"])]:
            drive.append({"indicator_id": f"{prefix}.{r['group']}.{stat}", "group": r["group"], "scenario": "A1",
                          "network_time_factor": k, "statistic": stat, "value": nn(r[stat]),
                          "unit": "minutes" if stat == "mean_min" else "%", "role": role})  # fmt: skip
    inv_cols = ["group", "n_in_city", "n_in_buffer_outside_city", "n_destinations_connected", "n_not_connected_not_used",
                "n_unnamed", "n_not_decided_by_tag_rule", "n_duplicate_review_pending", "registry_reference",
                "inventory_status", "note"]  # fmt: skip
    stm = [
        "DQ-SHARE-ALL",
        "DQ-MEAN-CONN",
        "DQ-A1-OPT",
        "DQ-DRIVE",
        "DQ-LOCAL",
        "DQ-DIST",
        "DQ-FAC-OSM",
        "DQ-DUP",
    ]
    return {
        **envelope(ctx, "city", "primary", dq(ctx, "primary", "mixed", "mixed", stm)),
        "population": population,
        "walk": walk,
        "walk_internal": internal,
        "walk_distribution": dist,
        "drive": drive,
        "facility_inventory": records(src.inv, inv_cols),
    }


def display_polygon(geom, tol: float = SIMPLIFY_DEG):
    """§8.2: simplify (EPSG:4326 input), wrap as MultiPolygon, round; never repaired."""
    simp = geom.simplify(tol, preserve_topology=True)
    parts = list(simp.geoms) if simp.geom_type == "MultiPolygon" else [simp]
    out = round6(MultiPolygon(parts))
    if out.is_empty or not out.is_valid or len(out.geoms) != shapely.get_num_geometries(geom):
        raise ExportError(f"display geometry invalid, empty or with another part count ({out.geom_type})")
    return out


def build_barangays(ctx: Ctx) -> dict:
    b = ctx.src.brgy.sort_values("adm4_pcode").to_crs(4326)
    feats, before, after = [], 0, 0
    for r in b.itertuples():
        try:
            g = display_polygon(r.geometry)
        except ExportError as e:
            raise ExportError(f"barangay {r.adm4_pcode}: {e}") from e
        before += int(shapely.get_num_coordinates(r.geometry))
        after += int(shapely.get_num_coordinates(g))
        props = {"adm4_pcode": r.adm4_pcode, "adm4_name": r.adm4_name, "adm3_pcode": r.adm3_pcode,
                 "adm3_name": r.adm3_name, "area_km2": float(r.area_km2)}  # fmt: skip
        feats.append({"type": "Feature", "geometry": mapping(g), "properties": props})
    simp = {"method": "shapely simplify, preserve_topology=True, after reprojection to EPSG:4326",
            "tolerance_deg": SIMPLIFY_DEG, "tolerance_unit": "degree", "display_only": True,
            "vertices_before": before, "vertices_after": after}  # fmt: skip
    data_quality = dq(ctx, "descriptive", "none", "none", ["DQ-SIMPLIFIED", "DQ-RESOLVED"])
    return {"type": "FeatureCollection", **envelope(ctx, "barangays", "descriptive", data_quality),
            "simplification": simp, "features": feats}  # fmt: skip


def reliability(r) -> dict:
    return {k: {"level": nn(r[f"rel_{c}"]), "reasons": nn(r[f"rel_{c}_reasons"])}
            for k, c in (("population", "population"), ("network", "network"),
                         ("facility_inventory", "facility_inventory"), ("overall", "overall"))}  # fmt: skip


def build_indicators(ctx: Ctx) -> dict:
    s, src = ctx.s, ctx.src
    a3, a1 = src.a3.set_index("adm4_pcode"), src.a1.set_index("adm4_pcode")
    frames = {"a3": a3, "a1": a1}
    ids = [e["id"] for e in ctx.catalog if "barangay" in e["levels"]]
    cats, groups = s["category_priority"], list(s["indicator_groups"])
    out = []
    for p in sorted(a3.index):
        r3, r1 = a3.loc[p], a1.loc[p]
        out.append({
            "adm4_pcode": p,
            "adm4_name": r3["adm4_name"],
            "pop_total": float(r3["pop_total"]),
            "a3_population": {c: {"pop": nn(r3[f"pop_{c}"]), "pct": nn(r3[f"pct_{c}"])} for c in CATS},
            "a1_population": {k: nn(r1[k]) for k in ("pop_connected", "pop_not_connected", "pct_not_connected")},
            "values": {i: nn(frames[ctx.bsrc[i][0]].loc[p, ctx.bsrc[i][1]]) for i in ids},
            "facility_counts": {f"n_{c}": as_int(r1[f"n_{c}"]) for c in [*cats, *groups]},
            "a1_drive_access": {"pop_drive_access_gt_flag": nn(r1["pop_drive_access_gt_flag"])},
            "data_quality": {
                "reliability": reliability(r1),
                "ranking_eligible": bool(r1["pop_ranking_eligible"]),
                "indicators_flag_not_connected": bool(r1["indicators_flag_not_connected"]),
                "resolved_separately": bool(r3["resolved_separately"]),
                "n_facilities_duplicate_review": as_int(r1["n_facilities_duplicate_review"]),
            },
        })  # fmt: skip
    stm = ["DQ-SHARE-ALL", "DQ-MEAN-CONN", "DQ-A1-OPT", "DQ-DRIVE", "DQ-LOCAL", "DQ-POP-ALLOC", "DQ-RESOLVED",
           "DQ-FAC-OSM", "DQ-DUP"]  # fmt: skip
    return {**envelope(ctx, "barangay_indicators", "primary", dq(ctx, "primary", "mixed", "mixed", stm)),
            "barangays": out}  # fmt: skip


def cell_features(s: Settings, src: Sources) -> list[dict]:
    """§7.5 logical dataset, ordered by cell_id (code points)."""
    groups = list(s["indicator_groups"])
    c3 = src.c3.set_index("cell_id", drop=False)
    ac = src.ac.set_index("cell_id")
    feats = []
    for cid in sorted(c3.index):
        r, a = c3.loc[cid], ac.loc[cid]
        local = r["a3_category"] in LOCAL
        props = {
            "cell_id": cid,
            "pop": float(r["pop"]),
            "display_adm4_pcode": r["adm4_pcode"],
            "a3_category": r["a3_category"],
            "a3_conn_status": r["conn_status"],
            "a3_conn_m": nn(r["conn_m"]),
            "component": nn(r["component"]),
            "component_class": nn(r["component_class"]),
            "walk_citywide": {g: nn(r[f"t_walk_{g}_citywide"]) for g in groups},
            "walk_internal": {g: nn(r[f"t_walk_{g}_internal"]) for g in groups} if local else None,
            "a1_conn_status": a["conn_status"],
            "drive_a1": {g: nn(a[f"t_drive_{g}"]) for g in groups},
            "drive_access_m": nn(a["drive_access_m"]),
        }
        geom = {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]}
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    return feats


def cells_file(ctx: Ctx, feats: list[dict], index: int, count: int) -> dict:
    data_quality = dq(ctx, "primary", "mixed", "mixed", ["DQ-POP-ALLOC", "DQ-LOCAL", "DQ-DRIVE"])
    chunk = {"index": index, "count": count, "features": len(feats),
             "first_cell_id": feats[0]["properties"]["cell_id"], "last_cell_id": feats[-1]["properties"]["cell_id"]}  # fmt: skip
    return {"type": "FeatureCollection", **envelope(ctx, "cells", "primary", data_quality), "chunk": chunk,
            "features": feats}  # fmt: skip


def split(feats: list, n: int) -> list[list]:
    m = math.ceil(len(feats) / n)
    return [feats[i * m : min((i + 1) * m, len(feats))] for i in range(n)]


def chunk_cells(
    ctx: Ctx, feats: list[dict], max_bytes: int = MAX_FILE_BYTES
) -> tuple[dict[str, bytes], dict]:
    """§7.5.1: the smallest number of contiguous, equal-count chunks with every file <= max_bytes."""
    single = dumps(cells_file(ctx, feats, 1, 1))
    n, files = 1, [single]
    if len(single) > max_bytes:
        for n in range(2, len(feats) + 1):
            parts = split(feats, n)
            files = [dumps(cells_file(ctx, p, i + 1, n)) for i, p in enumerate(parts)]
            if all(len(f) <= max_bytes for f in files):
                break
        else:
            raise ExportError("no chunking meets the size limit")
    parts = split(feats, n)
    out, chunks = {}, []
    for i, (p, data) in enumerate(zip(parts, files, strict=True), start=1):
        name = f"cells-{i:03d}.geojson"
        out[name] = data
        chunks.append({"index": i, "name": name, "features": len(p),
                       "first_cell_id": p[0]["properties"]["cell_id"], "last_cell_id": p[-1]["properties"]["cell_id"],
                       "bytes": len(data), "sha256": sha256_bytes(data)})  # fmt: skip
    layout = {"dataset": "cells", "features": len(feats), "order": "cell_id ascending (Unicode code points)",
              "max_file_bytes": max_bytes, "single_file_bytes": len(single), "count": n, "chunks": chunks}  # fmt: skip
    return out, layout


def sha256_bytes(b: bytes) -> str:
    import hashlib

    return hashlib.sha256(b).hexdigest()


def facility_groups(s: Settings, roles: list[dict], connected: bool) -> tuple[list[str], list[str]]:
    ind, dest = [], []
    for gname, g in s["indicator_groups"].items():
        match = [r for r in roles if r["category"] == g["category"] and r["subtype"] in g["subtypes"]]
        if match:
            ind.append(gname)
        if connected and any(r["tier"] == "indicative" for r in match):
            dest.append(gname)
    return ind, dest


def duplicate_review(dup: pd.DataFrame) -> dict[str, list]:
    out: dict[str, list] = {}
    for r in dup.sort_values("review_id").itertuples():
        for fid, other, role in (
            (r.flagged_fid, r.related_fid, "flagged"),
            (r.related_fid, r.flagged_fid, "related"),
        ):
            out.setdefault(fid, []).append({"review_id": r.review_id, "role": role, "other_fid": other,
                                            "review_status": r.review_status,
                                            "reviewer_decision": r.reviewer_decision or None})  # fmt: skip
    return out


def build_facilities(ctx: Ctx) -> dict:
    s, src = ctx.s, ctx.src
    fac = src.fac.to_crs(4326).sort_values("fid_key")
    roles: dict[str, list] = {}
    for r in src.roles.itertuples():
        roles.setdefault(r.fid_key, []).append({"category": r.category, "subtype": r.subtype, "tier": r.tier,
                                                "status": r.status, "primary": bool(r.primary)})  # fmt: skip
    fba = src.fba.set_index("fid_key")
    dups = duplicate_review(src.dup)
    feats = []
    for r in fac.itertuples():
        rl = roles.get(r.fid_key, [])
        ind, dest = facility_groups(s, rl, r.conn_status == OK)
        off = None
        if r.fid_key in fba.index:
            f = fba.loc[r.fid_key]
            off = {"A1": nn(f["components_A1_baseline"]), "A2": f["components_A2_all_eligible"],
                   "A3": f["components_A3_component_aware"]}  # fmt: skip
        props = {
            "fid_key": r.fid_key, "osm_type": r.osm_type, "osm_id": int(r.osm_id), "name": nn(r.name),
            "category": r.category, "subtype": r.subtype, "tier": r.tier, "class_status": r.class_status,
            "class_reason": r.class_reason, "geom_source": r.geom_source, "inside_city": bool(r.inside_city),
            "conn_status": r.conn_status, "conn_m": nn(r.conn_m), "drive_access_m": nn(r.drive_access_m),
            "nearest_edge_m": nn(r.nearest_edge_m), "roles": rl, "indicator_groups": ind, "destination_groups": dest,
            "off_main_network_in": off,
            "data_quality": {"duplicate_review": dups.get(r.fid_key, []),
                             "classification": {"class_status": r.class_status, "class_reason": r.class_reason}},
        }  # fmt: skip
        geom = {
            "type": "Point",
            "coordinates": [round(float(r.geometry.x), 6), round(float(r.geometry.y), 6)],
        }
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    data_quality = dq(ctx, "descriptive", "none", "none", ["DQ-FAC-OSM", "DQ-DUP"])
    return {
        "type": "FeatureCollection",
        **envelope(ctx, "facilities", "descriptive", data_quality),
        "features": feats,
    }


APPROACH_ROLE = {
    "A1_baseline": "comparative",
    "A2_all_eligible": "evidence_only",
    "A3_component_aware": "primary",
}
KM_ACCESS = ["km_no", "km_private", "km_residents", "km_customers", "km_unknown", "km_destination",
             "km_pedestrian_override", "km_untagged", "km_public"]  # fmt: skip


def build_network(ctx: Ctx) -> dict:
    src = ctx.src
    pop = src.appr[src.appr["group"] == "_population"]
    approaches = []
    for rec in records(pop, ["approach", "scenario_label", "components_retained", "network_km",
                             *[f"cells_{c}" for c in CATS], *[f"pop_{c}" for c in CATS]],
                       ints=("components_retained", *[f"cells_{c}" for c in CATS])):  # fmt: skip
        a, label = rec.pop("approach"), rec.pop("scenario_label")
        approaches.append({"approach": a, "scenario_label": label, "role": APPROACH_ROLE[a], **rec})
    by_group = records(src.appr[src.appr["group"] != "_population"],
                       ["approach", "group", "mean_min", "pct_le15_all_residents", "pct_le30_all_residents",
                        "pop_with_time", "pop_local_with_internal_time", "pop_local_internal_le15"])  # fmt: skip
    trans = []
    for _, r in src.trans.iterrows():
        for c in CATS:
            if c in r and not pd.isna(r[c]):
                trans.append({"a1_category": r["cat_A1_baseline"], "a3_category": c, "pop": float(r[c])})
    comp = src.comp
    classes = []
    for cls, g in sorted(comp.groupby("component_class"), key=lambda x: x[0]):
        classes.append({"component_class": cls, "components": len(g), "length_km": round(float(g["length_km"].sum()), 2),
                        "pop_attached_A3": round(float(g["pop_attached_A3"].sum()), 1)})  # fmt: skip
    ccols = ["fragment", "component_class", "class_reason", "length_km", "km_inside_city", "n_nodes", "n_edges",
             "gap_to_main_m", "gap_crosses_water", "noexit_at_gap", "retained_A2", "retained_A3", "cells_attached_A3",
             "pop_attached_A3", "pop_internal_health_primary_care_reachable",
             "pop_internal_education_basic_reachable", *KM_ACCESS, "gates_restricted", "gates_untagged"]  # fmt: skip
    components = []
    for rec, (_, r) in zip(records(comp, ccols), comp.iterrows(), strict=True):
        rec["bbox"] = {k: float(r[k]) for k in ("lon_min", "lat_min", "lon_max", "lat_max")}
        rec["geometry_kind"] = "bounding_box"
        components.append(rec)
    inv = comp.set_index("fragment")
    fr = src.frags.to_crs(4326).sort_values("fragment")
    gp = src.gaps.to_crs(4326).set_index("fragment")
    feats = []
    for r in fr.itertuples():
        feats.append({"type": "Feature", "geometry": mapping(round6(r.geometry)),
                      "properties": {"fragment": r.fragment, "n_edges": int(inv.loc[r.fragment, "n_edges"]),
                                     "length_km": float(inv.loc[r.fragment, "length_km"]),
                                     "gap_to_main_m": float(r.gap_to_main_m),
                                     "geometry_kind": "mapped_fragment_geometry"}})  # fmt: skip
    for f in fr["fragment"]:
        g = gp.loc[f]
        feats.append({"type": "Feature", "geometry": mapping(round6(g.geometry)),
                      "properties": {"fragment": f, "gap_to_main_m": float(g["gap_to_main_m"]), "geometry_kind": "gap_line"}})  # fmt: skip
    gi = src.gapinv
    cache = [c for c in gi.columns if c.startswith("cache_")]
    gcols = ["fragment", "component_class", "component_class_changed_by_snapshot", *cache,
             "snapshot_physical_connection", "snapshot_link_m", "snapshot_link_ways", "snapshot_link_access_tags",
             "snapshot_link_gates", "snapshot_corridor_gates", "snapshot_public_pedestrian_access",
             "snapshot_path_access_status", "snapshot_public_pedestrian_status", "snapshot_authorized_group",
             "snapshot_field_verification_required", "remaining_unverified"]  # fmt: skip
    corr = src.corr.set_index("fragment")
    if not corr.index.is_unique:
        raise ExportError("snapshot_corridor_analysis.csv has more than one row per fragment")
    gap_evidence = []
    for rec in records(gi, gcols):
        c = corr.loc[rec["fragment"]] if rec["fragment"] in corr.index else None
        for k in ("path_ways", "path_gates", "classification_reason"):
            rec[k] = None if c is None else nn(c[k])
        rec["applied"] = False if c is None else bool(c["applied"])
        gap_evidence.append(rec)
    acs_cols = ["kind", "access_class", "public_pedestrian_status", "treatment", "ways", "edges", "km", "km_main",
                "components", "cells_attached_A1", "pop_attached_A1", "nodes", "nodes_flag_for_review",
                "nodes_field_verification", "nodes_main"]  # fmt: skip
    ints = ("ways", "edges", "components", "cells_attached_A1", "nodes", "nodes_flag_for_review",
            "nodes_field_verification", "nodes_main")  # fmt: skip
    flags = {"analysis_only": True, "applied": False}
    access_classification = [{**r, **flags} for r in records(src.acs, acs_cols, ints=ints)]
    imp_cols = ["scenario", "definition", "ways_all_components", "km_all_components", "edges_removed_main",
                "km_removed_main", "pop_lose_network", "pop_become_local", "pop_become_unconnected",
                "pop_time_up_gt1min", "pop_lose_network_focus"]  # fmt: skip
    impact = [
        {**r, **flags} for r in records(src.imp, imp_cols, ints=("ways_all_components", "edges_removed_main"))
    ]
    impg_cols = [
        "scenario",
        "group",
        "pct_le15_baseline",
        "pct_le15_scenario",
        "mean_min_baseline",
        "mean_min_scenario",
    ]
    impact_g = [{**r, **flags} for r in records(src.impg, impg_cols)]
    data_quality = dq(
        ctx,
        "evidence_only",
        "mixed",
        "walk",
        ["DQ-PHYS-NOT-PUBLIC", "DQ-BBOX", "DQ-ANALYSIS-ONLY", "DQ-LOCAL"],
    )
    return {
        **envelope(ctx, "network", "evidence_only", data_quality),
        "approaches": approaches,
        "approaches_by_group": by_group,
        "transition_a1_to_a3": trans,
        "component_classes": classes,
        "components": components,
        "fragment_geometries": {"type": "FeatureCollection", "features": feats},
        "gap_evidence": gap_evidence,
        "access_classification": access_classification,
        "access_impact": impact,
        "access_impact_by_group": impact_g,
    }


MANIFEST_OPTIONAL = ["source", "release", "year", "hdx_dataset", "hdx_last_modified", "timestamp_osm_base",
                     "overpass_timestamp_osm_base", "query_file", "query_sha256", "query_label", "boundary_buffer_m",
                     "used_by_runs"]  # fmt: skip


def build_provenance(ctx: Ctx) -> dict:
    src = ctx.src
    sources = []
    for path, e in src.raw_manifest.items():
        sources.append({"path": path, "url": e.get("url"), "licence": e.get("licence"),
                        "retrieved_utc": e.get("retrieved_utc"), "bytes": e.get("bytes"), "sha256": e.get("sha256"),
                        **{k: e.get(k) for k in MANIFEST_OPTIONAL}})  # fmt: skip
    op = src.osm_prov
    osm = {"osmnx_version": op.get("osmnx_version"), "overpass_endpoint": op.get("overpass_endpoint"),
           "boundary_buffer_m": op.get("boundary_buffer_m"),
           "responses": [{k: r.get(k) for k in ("label", "cache_file", "overpass_timestamp_osm_base", "elements", "sha256")}
                         for r in op.get("responses", [])]}  # fmt: skip
    targeted = [(p, e) for p, e in src.raw_manifest.items() if p.startswith("osm_targeted/")]
    snap = None
    if targeted:
        p, e = targeted[-1]
        snap = {"file": p, "sha256": e.get("sha256"), "timestamp_osm_base": e.get("timestamp_osm_base"),
                "used_for": "evidence only"}  # fmt: skip
    return {
        **envelope(ctx, "provenance", "descriptive", dq(ctx, "descriptive", "none", "none", [])),
        "sources": sources,
        "osm": osm,
        "targeted_snapshot": snap,
        "qa": src.qa,
        "audit": ctx.source_validation,
        "limitations": limitations(src),
        "documents": [{"title": t, "path": p} for t, p in DOCUMENTS],
    }


def parse_porcelain_z(out: str) -> list[str]:
    """Paths of `git status --porcelain -z` entries (§7.1). Entries are NUL-separated `XY path` and
    never C-quoted, so spaces and unusual characters stay literal; a rename or copy (R or C in either
    status column) is followed by its original path, which is skipped (the entry counts once)."""
    tokens, paths, i = out.split("\0"), [], 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if not entry:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            i += 1
    return paths


def git_info(root: Path) -> dict:
    def git(*args):
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", check=True)  # fmt: skip
        return r.stdout

    try:
        commit = git("rev-parse", "HEAD").strip()
        paths = parse_porcelain_z(git("status", "--porcelain", "-z"))
    except (OSError, subprocess.CalledProcessError):
        return {
            "git_commit": None,
            "git_working_tree_clean": None,
            "git_dirty_count": None,
            "git_dirty_paths": [],
        }
    return {"git_commit": commit, "git_working_tree_clean": not paths, "git_dirty_count": len(paths),
            "git_dirty_paths": sorted(paths)[:50]}  # fmt: skip


def build_manifest(ctx: Ctx, files: dict[str, bytes], layout: dict, source_files: list, code: dict,
                   audit_block: dict) -> dict:  # fmt: skip
    s, src = ctx.s, ctx.src
    datasets = {"city.json": "city", "barangays.geojson": "barangays", "barangay_indicators.json": "barangay_indicators",
                "facilities.geojson": "facilities", "network.json": "network", "provenance.json": "provenance"}  # fmt: skip
    entries = [{"name": n, "sha256": sha256_bytes(b), "bytes": len(b), "dataset": datasets.get(n, "cells")}
               for n, b in files.items()]  # fmt: skip
    issues = []
    if audit_block["status"] == "obtained" and audit_block["outcome"] == "warn":
        issues.append({"code": "AUDIT-WARN", "text": f"abot audit reported {audit_block['counts']['warn']} warning(s): "
                       + "; ".join(f"{f['section']} {f['check']}" for f in audit_block["findings"]),
                       "affects": ["bundle"]})  # fmt: skip
    if audit_block["status"] == "not_run":
        issues.append({"code": "AUDIT-NOT-RUN", "text": "abot audit was not run for this bundle (--skip-audit).",
                       "affects": ["bundle"]})  # fmt: skip
    if code["git_working_tree_clean"] is False:
        issues.append({"code": "GIT-DIRTY", "text": f"Built from a working tree with {code['git_dirty_count']} "
                       "uncommitted change(s); the commit alone does not identify the code.", "affects": ["code"]})  # fmt: skip
    groups = s["indicator_groups"]
    labels = src.run_info["scenario_labels"]
    scenarios = [
        {"code": "A3", "mode": "walk", "role": "primary", "label_key": "A3_component_aware", "label": labels["A3_component_aware"]},
        {"code": "A1", "mode": "walk", "role": "comparative", "label_key": "A1_baseline", "label": labels["A1_baseline"]},
        {"code": "A1", "mode": "drive", "role": "primary", "label_key": None,
         "label": "A1 driving: modelled uncongested car travel time from A1-connected cells (a lower bound; assumes a car)"},
        {"code": "A2", "mode": "walk", "role": "evidence_only", "label_key": "A2_all_eligible", "label": labels["A2_all_eligible"]},
    ]  # fmt: skip
    acc = s["accessibility"]
    return {
        **envelope(ctx, "manifest", "descriptive", dq(ctx, "descriptive", "none", "none", [])),
        "files": entries,
        "cells_layout": layout,
        "source_files": source_files,
        "code": {**code, "abot_version": __version__},
        "config_sha256": s.config_sha256,
        "stage_completed_utc": {k: src.run_meta[k]["completed_utc"] for k in ("boundaries", "population", "osm", "accessibility", "report")},
        "a3_run_info": src.run_info,
        "population_total": float(src.run_info["population_total"]),
        "scenarios": scenarios,
        "indicator_groups": [{"id": k, "category": g["category"], "subtypes": list(g["subtypes"])} for k, g in groups.items()],
        "thresholds_min": {"walk": list(acc["thresholds_min"]["walk"]), "drive": list(acc["thresholds_min"]["drive"])},
        "walk_speed_kmh": float(acc["walk_speed_kmh"]),
        "drive_access_flag_m": float(acc["connection"]["drive_access_flag_m"]),
        "drive_network_time_factors": [1.0, *[float(x) for x in acc.get("drive_network_time_factors", [])]],
        "walk_distribution": {"bin_width_min": BIN_WIDTH_MIN, "closed_max_min": CLOSED_MAX_MIN},
        "indicator_catalog": ctx.catalog,
        "statements": statements(src),
        "known_issues": issues,
        "crs": "EPSG:4326",
    }  # fmt: skip


# --- validation (§10.2) ---------------------------------------------------------------------------


def _eq(a, b) -> bool:
    a, b = nn(a), nn(b)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and float(a) == float(b)
    return a == b


def distribution_failures(rec: dict, t: np.ndarray, w: np.ndarray, ref: dict | None = None) -> list[str]:
    """V-C1 for one walk_distribution record. Every written number is recomputed from the cell times
    `t` (NaN = no citywide time) and whole-cell populations `w` with plain masks, independently of
    `walk_distribution` (which bins with ceil and a cumulative sum). `ref` holds the citywide_a3 values
    (`pct_le{N}`, `mean_min`, `pop_network_connected`) when available."""
    g, bad = rec.get("group", "?"), []
    ok = ~np.isnan(t)
    total = float(w.sum())
    if rec["pop_total"] != round(total, 1):
        bad.append(f"V-C1: {g} pop_total {rec['pop_total']} != {round(total, 1)}")
    with_time = float(w[ok].sum())
    if rec["pop_with_time"] != round(with_time, 1):
        bad.append(f"V-C1: {g} pop_with_time {rec['pop_with_time']} != {round(with_time, 1)}")
    edges = [(k - 1, k) for k in range(1, CLOSED_MAX_MIN + 1)] + [(CLOSED_MAX_MIN, None)]
    bins = rec["bins"]
    if [(b["lower_min"], b["upper_min"]) for b in bins] != edges:
        bad.append(f"V-C1: {g} bin edges are not 1-minute bins 1..{CLOSED_MAX_MIN} plus an open bin")
    else:
        for k in range(1, CLOSED_MAX_MIN + 1):
            m = ok & (t <= k) & ((t > k - 1) | (k == 1))  # right-closed; t = 0 belongs to bin 1
            if bins[k - 1]["pop"] != round(float(w[m].sum()), 1):
                bad.append(
                    f"V-C1: {g} bin ({k - 1}, {k}] pop {bins[k - 1]['pop']} != {round(float(w[m].sum()), 1)}"
                )
        over = round(float(w[ok & (t > CLOSED_MAX_MIN)].sum()), 1)
        if bins[-1]["pop"] != over or rec["pop_open_bin"] != over:
            bad.append(
                f"V-C1: {g} open bin > {CLOSED_MAX_MIN} min {bins[-1]['pop']} / {rec['pop_open_bin']} != {over}"
            )
    cum = rec["cumulative"]
    if [c["minutes"] for c in cum] != [*range(1, CLOSED_MAX_MIN + 1), None]:
        bad.append(f"V-C1: {g} cumulative points are not minutes 1..{CLOSED_MAX_MIN} plus a final point")
        return bad
    for k in range(1, CLOSED_MAX_MIN + 1):
        exp = round(100 * float(w[ok & (t <= k)].sum()) / total, 2) if total else 0.0
        if cum[k - 1]["pct_all_residents"] != exp:
            bad.append(f"V-C1: {g} cumulative at {k} min {cum[k - 1]['pct_all_residents']} != {exp}")
    final = round(100 * with_time / total, 2) if total else 0.0
    if cum[-1]["pct_all_residents"] != final:
        bad.append(
            f"V-C1: {g} final cumulative point {cum[-1]['pct_all_residents']} != {final} (incl. > {CLOSED_MAX_MIN} min)"
        )
    if cum[-1]["pct_all_residents"] < cum[-2]["pct_all_residents"]:
        bad.append(f"V-C1: {g} final cumulative point below the {CLOSED_MAX_MIN}-minute point")
    if ref:
        by_min = {c["minutes"]: c["pct_all_residents"] for c in cum}
        for key, v in ref.items():
            if key.startswith("pct_le") and by_min[int(key[6:])] != v:
                bad.append(f"V-C1: {g} cumulative at {key[6:]} min != citywide_a3 {v}")
        if (
            "mean_min" in ref
            and ok.any()
            and round(float(np.average(t[ok], weights=w[ok])), 2) != ref["mean_min"]
        ):
            bad.append(f"V-C1: {g} mean of the cell times != citywide_a3 {ref['mean_min']}")
        if "pop_network_connected" in ref and abs(rec["pop_with_time"] - ref["pop_network_connected"]) > 0.05:
            bad.append(
                f"V-C1: {g} pop_with_time != citywide_a3 pop_network_connected {ref['pop_network_connected']}"
            )
    return bad


def validate(s: Settings, src: Sources, d: Path, ctx: Ctx, skip_audit: bool) -> list[str]:
    """Every check against the files as written (re-read from disk)."""
    bad: list[str] = []

    def read(name):
        return json.loads(
            (d / name).read_bytes().decode("utf-8"),
            parse_constant=lambda c: bad.append(f"V-N1: {c} in {name}"),
        )

    man = read("manifest.json")
    city, brgy, ind = read("city.json"), read("barangays.geojson"), read("barangay_indicators.json")
    fac, net, prov = read("facilities.geojson"), read("network.json"), read("provenance.json")
    lay = man["cells_layout"]
    chunks = [read(c["name"]) for c in lay["chunks"]]
    cells = [f for c in chunks for f in c["features"]]
    groups = list(s["indicator_groups"])
    th = s["accessibility"]["thresholds_min"]

    # envelope, version, manifest files (V-M1)
    for name in [*(f["name"] for f in man["files"]), "manifest.json"]:
        o = read(name)
        if (
            o["contract_version"] != CONTRACT_VERSION
            or o["contract"] != CONTRACT
            or o["generated_utc"] != ctx.generated
        ):
            bad.append(f"V-M1: envelope of {name}")
        if name.endswith(".geojson") and "crs" in o:  # §5.3 (RFC 7946 §4); manifest.crs is a plain field
            bad.append(f"V-G1: {name} carries a crs member")
    if "crs" in net["fragment_geometries"]:
        bad.append("V-G1: network.fragment_geometries carries a crs member")
    on_disk = {p.name for p in d.iterdir()}
    if on_disk != {f["name"] for f in man["files"]} | {"manifest.json"}:
        bad.append(f"V-M1: files on disk {sorted(on_disk)} differ from manifest.files")
    for f in man["files"]:
        b = (d / f["name"]).read_bytes()
        if sha256_bytes(b) != f["sha256"] or len(b) != f["bytes"]:
            bad.append(f"V-M1: hash/size of {f['name']}")

    # populations (V-P1..P3)
    tot = float(src.run_info["population_total"])
    sums = {"cells_a3": src.c3["pop"].sum(), "access_cells": src.ac["pop"].sum(), "A3": src.a3["pop_total"].sum(),
            "A1": src.a1["pop_total"].sum(), "cells bundle": sum(f["properties"]["pop"] for f in cells)}  # fmt: skip
    for k, v in sums.items():
        if abs(v - tot) > 0.5:
            bad.append(f"V-P1: {k} total {v} vs {tot}")
    for r in ind["barangays"]:
        if abs(sum(r["a3_population"][c]["pop"] for c in CATS) - r["pop_total"]) > 0.5:
            bad.append(f"V-P2: {r['adm4_pcode']} categories")
        if (
            abs(
                r["pop_total"]
                - (r["a1_population"]["pop_connected"] + r["a1_population"]["pop_not_connected"])
            )
            > 0.5
        ):
            bad.append(f"V-P2: {r['adm4_pcode']} A1 parts")
        if abs(sum(r["a3_population"][c]["pct"] for c in CATS) - 100) > 0.02 + 1e-9:
            bad.append(f"V-P3: {r['adm4_pcode']} pct sum")
    a1tot = src.a1.set_index("adm4_pcode")["pop_total"]
    if (
        src.a3.set_index("adm4_pcode")["pop_total"] - a1tot.reindex(src.a3["adm4_pcode"]).values
    ).abs().max() > 0.05:
        bad.append("V-P2: A3 and A1 pop_total differ")
    if abs(sum(city["population"]["a3"][c]["pct"] for c in CATS) - 100) > 0.02 + 1e-9:
        bad.append("V-P3: citywide pct sum")
    if abs(sum(city["population"]["a3"][c]["pop"] for c in CATS) - city["population"]["total"]) > 0.5:
        bad.append("city: category pops do not add up to the total")

    # identifiers and joins (V-I1, V-I2)
    pc = {f["properties"]["adm4_pcode"] for f in brgy["features"]}
    if not (len(brgy["features"]) == 180 == len(pc) and pc == set(src.a3["adm4_pcode"]) == set(src.a1["adm4_pcode"])
            == {r["adm4_pcode"] for r in ind["barangays"]} and len(ind["barangays"]) == 180):  # fmt: skip
        bad.append("V-I1: adm4_pcode sets")
    ids = [f["properties"]["cell_id"] for f in cells]
    if not (
        len(ids) == 8035 == len(set(ids)) and set(ids) == set(src.c3["cell_id"]) == set(src.ac["cell_id"])
    ):
        bad.append("V-I1: cell_id sets")
    fk = [f["properties"]["fid_key"] for f in fac["features"]]
    if not (
        len(fk) == 937 == len(set(fk)) and set(fk) == set(src.fac["fid_key"]) == set(src.roles["fid_key"])
    ):
        bad.append("V-I1: fid_key sets")
    if not (len(net["components"]) == 112 == len({c["fragment"] for c in net["components"]})):
        bad.append("V-I1: 112 components")
    if (
        len(src.c3) != len(src.ac)
        or len(fac["features"]) != len(src.fac)
        or len(src.roles) != sum(len(f["properties"]["roles"]) for f in fac["features"])
    ):
        bad.append("V-I2: a join dropped or duplicated records")

    # V-C1: the distribution, recomputed independently from cells_a3 (never from the written bins)
    w = src.c3["pop"].to_numpy(float)
    if [r["group"] for r in city["walk_distribution"]] != groups:
        bad.append("V-C1: walk_distribution groups")
    for rec in city["walk_distribution"]:
        g = rec["group"]
        ref = {f"pct_le{n}": src.city.loc[f"walk_{g}_pct_le{n}", "A3"] for n in th["walk"]}
        ref |= {"mean_min": src.city.loc[f"walk_{g}_mean_min", "A3"],
                "pop_network_connected": src.city.loc["pop_network_connected", "A3"]}  # fmt: skip
        bad += distribution_failures(rec, src.c3[f"t_walk_{g}_citywide"].to_numpy(float), w, ref)

    # V-C2: copies equal their sources
    a3, a1 = src.a3.set_index("adm4_pcode"), src.a1.set_index("adm4_pcode")
    frames = {"a3": a3, "a1": a1}
    bids = {e["id"] for e in man["indicator_catalog"] if "barangay" in e["levels"]}
    for r in ind["barangays"]:
        p = r["adm4_pcode"]
        if set(r["values"]) != bids:
            bad.append(f"V-C2: {p} values key set")
            continue
        for i, v in r["values"].items():
            fr, col = ctx.bsrc[i]
            if not _eq(v, frames[fr].loc[p, col]):
                bad.append(f"V-C2: {p} {i}")
        for c in CATS:
            if (
                r["a3_population"][c]["pop"] != r["values"][f"A3.population.pop_{c}"]
                or r["a3_population"][c]["pct"] != r["values"][f"A3.population.pct_{c}"]
            ):
                bad.append(f"V-C2: {p} a3_population copy")
        for k in ("pop_connected", "pop_not_connected", "pct_not_connected"):
            if r["a1_population"][k] != r["values"][f"A1.population.{k}"]:
                bad.append(f"V-C2: {p} a1_population copy")
        if (
            r["a1_drive_access"]["pop_drive_access_gt_flag"]
            != r["values"]["A1.drive.pop_drive_access_gt_flag"]
        ):
            bad.append(f"V-C2: {p} a1_drive_access copy")
        for k, v in r["facility_counts"].items():
            if v != int(a1.loc[p, k]):
                bad.append(f"V-C2: {p} {k}")
        q = r["data_quality"]
        if (q["ranking_eligible"] != bool(a1.loc[p, "pop_ranking_eligible"]) or q["resolved_separately"] != bool(a3.loc[p, "resolved_separately"])
                or q["reliability"]["network"]["level"] != a1.loc[p, "rel_network"]):  # fmt: skip
            bad.append(f"V-C2: {p} data_quality")
    for r in city["walk"]:
        if not _eq(r["value"], src.city.loc[f"walk_{r['group']}_{r['statistic']}", r["scenario"]]):
            bad.append(f"V-C2: city {r['indicator_id']}")
    for r in city["walk_internal"]:
        col = "A3_local_internal_pop" if r["category"] == "locally_connected" else "A3_uncertain_internal_pop"
        if not _eq(r["value"], src.city.loc[f"walk_{r['group']}_pct_le{r['threshold_min']}", col]):
            bad.append(f"V-C2: city {r['indicator_id']}")
    ds = src.ds.set_index(["group", "network_time_factor"])
    for r in city["drive"]:
        if not _eq(r["value"], ds.loc[(r["group"], r["network_time_factor"]), r["statistic"]]):
            bad.append(f"V-C2: city {r['indicator_id']} x{r['network_time_factor']}")
    c3 = src.c3.set_index("cell_id")
    ac = src.ac.set_index("cell_id")
    for f in cells:
        pr, cid = f["properties"], f["properties"]["cell_id"]
        r, a = c3.loc[cid], ac.loc[cid]
        same = (_eq(pr["pop"], r["pop"]) and pr["display_adm4_pcode"] == r["adm4_pcode"] and pr["a3_category"] == r["a3_category"]
                and pr["a3_conn_status"] == r["conn_status"] and _eq(pr["a3_conn_m"], r["conn_m"])
                and _eq(pr["component"], r["component"]) and _eq(pr["component_class"], r["component_class"])
                and pr["a1_conn_status"] == a["conn_status"] and _eq(pr["drive_access_m"], a["drive_access_m"])
                and all(_eq(pr["walk_citywide"][g], r[f"t_walk_{g}_citywide"]) for g in groups)
                and all(_eq(pr["drive_a1"][g], a[f"t_drive_{g}"]) for g in groups)
                and (pr["walk_internal"] is None or all(_eq(pr["walk_internal"][g], r[f"t_walk_{g}_internal"]) for g in groups)))  # fmt: skip
        if not same:
            bad.append(f"V-C2: cell {cid}")
        if f["geometry"]["coordinates"] != [float(r["lon"]), float(r["lat"])]:
            bad.append(f"V-G2: cell {cid}")
    sfac = src.fac.set_index("fid_key")
    fcsv = src.fcsv.set_index("fid_key")
    for f in fac["features"]:
        pr = f["properties"]
        r = sfac.loc[pr["fid_key"]]
        for k in ("osm_type", "osm_id", "name", "category", "subtype", "tier", "class_status", "class_reason",
                  "geom_source", "inside_city", "conn_status", "conn_m", "drive_access_m", "nearest_edge_m"):  # fmt: skip
            if not _eq(pr[k], r[k]):
                bad.append(f"V-C2: facility {pr['fid_key']} {k}")
        x, y = f["geometry"]["coordinates"]
        if abs(x - fcsv.loc[pr["fid_key"], "lon"]) > 1e-6 or abs(y - fcsv.loc[pr["fid_key"], "lat"]) > 1e-6:
            bad.append(f"V-G2: facility {pr['fid_key']}")
    for name, rows, srcdf in (("components", net["components"], src.comp), ("access_impact", net["access_impact"], src.imp),
                              ("access_classification", net["access_classification"], src.acs),
                              ("access_impact_by_group", net["access_impact_by_group"], src.impg)):  # fmt: skip
        for rec, (_, r) in zip(rows, srcdf.iterrows(), strict=True):
            for k, v in rec.items():
                if k in srcdf.columns and not _eq(v, r[k]):
                    bad.append(f"V-C2: network.{name} {k}")
    for rec in net["approaches"]:
        r = src.appr[(src.appr["approach"] == rec["approach"]) & (src.appr["group"] == "_population")].iloc[0]
        if any(not _eq(v, r[k]) for k, v in rec.items() if k in src.appr.columns):
            bad.append(f"V-C2: network.approaches {rec['approach']}")
    if abs(sum(t["pop"] for t in net["transition_a1_to_a3"]) - float(src.trans[CATS].sum().sum())) > 0.05:
        bad.append("V-C2: transition")
    inv = src.inv.set_index("group")
    for r in city["facility_inventory"]:
        if any(not _eq(v, inv.loc[r["group"], k]) for k, v in r.items() if k != "group"):
            bad.append(f"V-C2: facility_inventory {r['group']}")

    # V-C3: factor-1.0 drive row = recomputation from access_cells (validation only)
    w1 = src.ac["pop"].to_numpy(float)
    conn = (src.ac["conn_status"] == OK).to_numpy()
    for g in groups:
        t = src.ac[f"t_drive_{g}"].to_numpy(float)
        ok = conn & ~np.isnan(t)
        r = ds.loc[(g, 1.0)]
        exp = {"mean_min": round(float(np.average(t[ok], weights=w1[ok])), 2),
               **{f"pct_le{n}": round(100 * float(w1[ok & (t <= n)].sum()) / w1.sum(), 1) for n in th["drive"]},
               "pct_not_connected": round(100 * float(w1[~conn].sum()) / w1.sum(), 2)}  # fmt: skip
        if any(exp[k] != r[k] for k in exp):
            bad.append(f"V-C3: drive {g}")

    # V-N1, V-N2
    for f in cells:
        pr = f["properties"]
        net_c = pr["a3_category"] == "network_connected"
        if any((v is not None) != net_c for v in pr["walk_citywide"].values()):
            bad.append(f"V-N2: walk_citywide {pr['cell_id']}")
        if (pr["walk_internal"] is not None) != (pr["a3_category"] in LOCAL):
            bad.append(f"V-N2: walk_internal {pr['cell_id']}")
        if any((v is None) != (pr["a1_conn_status"] != OK) for v in pr["drive_a1"].values()):
            bad.append(f"V-N2: drive_a1 {pr['cell_id']}")
    keysets = {tuple(f["properties"]) for f in cells}
    if len(keysets) != 1 or len({tuple(f["properties"]) for f in fac["features"]}) != 1:
        bad.append("V-N1: records with differing field sets (a field was omitted)")

    # V-R1
    units = {e["id"]: e["unit"] for e in man["indicator_catalog"]}
    vals = [(i, v) for r in ind["barangays"] for i, v in r["values"].items()]
    vals += [
        (r["indicator_id"], r["value"]) for part in ("walk", "walk_internal", "drive") for r in city[part]
    ]
    for i, v in vals:
        if v is None:
            continue
        if (units[i] == "%" and not 0 <= v <= 100) or v < 0:
            bad.append(f"V-R1: {i} = {v}")

    # V-G1, V-G3
    (lat0, lat1), (lon0, lon1) = LAT_RANGE, LON_RANGE
    src_parts = src.brgy.set_index("adm4_pcode").geometry.map(shapely.get_num_geometries)
    geoms = [(f["geometry"], "barangays") for f in brgy["features"]] + [
        (f["geometry"], "cells") for f in cells
    ]
    geoms += [(f["geometry"], "facilities") for f in fac["features"]] + [
        (f["geometry"], "network") for f in net["fragment_geometries"]["features"]
    ]
    for gj, where in geoms:
        g = shape(gj)
        x0, y0, x1, y1 = g.bounds
        if g.is_empty or not g.is_valid or x0 < lon0 or x1 > lon1 or y0 < lat0 or y1 > lat1:
            bad.append(f"V-G1: {where} geometry invalid, empty or out of bounds")
    for f in brgy["features"]:
        if (
            f["geometry"]["type"] != "MultiPolygon"
            or len(f["geometry"]["coordinates"]) != src_parts[f["properties"]["adm4_pcode"]]
        ):
            bad.append(f"V-G1: barangay {f['properties']['adm4_pcode']} type or part count")
        if f["properties"]["area_km2"] != float(
            src.brgy.set_index("adm4_pcode").loc[f["properties"]["adm4_pcode"], "area_km2"]
        ):
            bad.append("V-C2: area_km2")
    kinds = [f["properties"]["geometry_kind"] for f in net["fragment_geometries"]["features"]]
    if kinds.count("mapped_fragment_geometry") != 9 or kinds.count("gap_line") != 9 or len(kinds) != 18:
        bad.append(f"V-G3: fragment geometry kinds {kinds}")
    if any("geometry" in c or c.get("geometry_kind") != "bounding_box" for c in net["components"]):
        bad.append("V-G3: a component box written as a geometry")
    inv_c = src.comp.set_index("fragment")
    for f in net["fragment_geometries"]["features"]:
        if (
            f["properties"]["fragment"] not in inv_c.index
            or f["properties"]["gap_to_main_m"] != inv_c.loc[f["properties"]["fragment"], "gap_to_main_m"]
        ):
            bad.append(f"§7.7: fragment {f['properties']['fragment']} gap_to_main_m")

    # V-K1
    n = lay["count"]
    exp_n = 1
    if lay["single_file_bytes"] > lay["max_file_bytes"]:
        exp_n = next(k for k in range(2, 8036) if all(len(dumps(cells_file(ctx, p, i + 1, k))) <= MAX_FILE_BYTES
                                                     for i, p in enumerate(split(cell_features(s, src), k))))  # fmt: skip
    if n != exp_n or len(chunks) != n or [c["index"] for c in lay["chunks"]] != list(range(1, n + 1)):
        bad.append(f"V-K1: chunk count {n}, expected {exp_n}")
    if ids != sorted(ids) or sum(c["features"] for c in lay["chunks"]) != 8035:
        bad.append("V-K1: chunks not contiguous in cell_id order")
    for c, o in zip(lay["chunks"], chunks, strict=True):
        if (
            (n > 1 and c["bytes"] > lay["max_file_bytes"])
            or o["chunk"]["index"] != c["index"]
            or len(o["features"]) != c["features"]
        ):
            bad.append(f"V-K1: chunk {c['name']}")

    # V-Q1, V-Q2, V-Q3
    cat_ids = {e["id"] for e in man["indicator_catalog"]}
    used = set(bids) | {r["indicator_id"] for p in ("walk", "walk_internal", "drive") for r in city[p]}
    if used - cat_ids:
        bad.append(f"V-Q1: ids not in catalogue {sorted(used - cat_ids)[:5]}")
    for e in man["indicator_catalog"]:
        if not (
            e["levels"]
            and e["unit"]
            and e["numerator"]
            and (e["denominator"] or e["population_described"])
            and e["role"]
        ):
            bad.append(f"V-Q1: catalogue entry {e['id']}")
    codes = {x["code"] for x in man["statements"]}
    for e in man["indicator_catalog"]:
        if set(e["statements"]) - codes:
            bad.append(f"V-Q1: unknown statement code in {e['id']}")
    for part in ("access_classification", "access_impact", "access_impact_by_group"):
        if any(r.get("analysis_only") is not True or r.get("applied") is not False for r in net[part]):
            bad.append(f"V-Q2: network.{part}")
    if any(r["applied"] is not False for r in net["gap_evidence"]):
        bad.append("V-Q2: network.gap_evidence applied")
    d_ = dup_counts(src.dup)
    raw = pd.read_csv(
        s.processed_dir / "review" / "possible_duplicates_review.csv", dtype=str, keep_default_na=False
    )
    exp_dup = STATEMENTS["DQ-DUP"][1].format(pairs=len(raw), pending=int((raw["review_status"] == "pending").sum()),
                                             likely=int((raw["reviewer_decision"] == "likely_duplicate_not_merged").sum()))  # fmt: skip
    if next(x["text"] for x in man["statements"] if x["code"] == "DQ-DUP") != exp_dup or d_["pairs"] != len(
        raw
    ):
        bad.append("V-Q3: DQ-DUP figures")
    lim = {x["code"]: x["text"] for x in prov["limitations"]}
    if f"{src.city.loc['pop_unconnected', 'A3']:,.1f} residents unconnected" not in lim["L5"]:
        bad.append("V-Q3: limitation L5 figures")

    # V-A1
    ab = man["data_quality"]["source_validation"]["audit"]
    codes_k = [k["code"] for k in man["known_issues"]]
    ok_state = (ab["status"] == "obtained" and ab["outcome"] in ("pass", "warn")) or (
        ab["status"] == "not_run" and skip_audit
    )
    if not ok_state:
        bad.append(f"V-A1: audit state {ab['status']}/{ab['outcome']} cannot be written")
    if ab["status"] == "obtained":
        if (
            ab["counts"] is None
            or ab["counts"]["warn"] != len(ab["findings"])
            or any(f["status"] != "WARN" for f in ab["findings"])
        ):
            bad.append("V-A1: audit counts/findings")
    elif ab["counts"] is not None:
        bad.append("V-A1: counts without an obtained audit")
    if ("AUDIT-WARN" in codes_k) != (ab["outcome"] == "warn") or ("AUDIT-NOT-RUN" in codes_k) != (
        ab["status"] == "not_run"
    ):
        bad.append("V-A1: audit known_issues")
    for o in (city, brgy, ind, fac, net, prov, man, *chunks):
        if o["data_quality"]["source_validation"] != man["data_quality"]["source_validation"]:
            bad.append(f"§6.1: source_validation differs in {o['dataset']}")
    return bad


# --- export / check (§10.1, §10.3) -----------------------------------------------------------------


def dashboard_root(s: Settings) -> Path:
    return s.processed_dir / "dashboard"


OWNED = re.compile(rf"^\.{BUNDLE}\.(tmp|old)-[0-9a-f]{{12}}$")  # §10.1.1: the only names ever touched


class RecoveryError(Exception):
    """An interrupted run left a state that needs a person (§10.1.1): nothing was changed."""


def owned(root: Path, kind: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and (m := OWNED.match(p.name)) and m.group(1) == kind
    )


def bundle_complete(d: Path) -> bool:
    """§10.1.1: a parsable manifest.json and every manifest file with the recorded size and SHA-256."""
    try:
        files = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["files"]
        return bool(files) and all(
            (d / f["name"]).is_file()
            and (d / f["name"]).stat().st_size == f["bytes"]
            and sha256(d / f["name"]) == f["sha256"]
            for f in files
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def recover(root: Path) -> list[str]:
    """§10.1.1, at the start of an export: drop temporaries, restore or drop backups of a crashed run."""
    notes, v1 = [], root / BUNDLE
    for t in owned(root, "tmp"):
        shutil.rmtree(t)
        notes.append(f"removed temporary {t.name}")
    olds = owned(root, "old")
    if v1.exists():
        if olds and bundle_complete(v1):
            for o in olds:
                shutil.rmtree(o)
                notes.append(f"removed backup {o.name} ({BUNDLE}/ is complete)")
        elif olds:
            notes.append(
                f"kept backups {[o.name for o in olds]}: {BUNDLE}/ is not complete; resolve manually"
            )
    elif len(olds) == 1 and bundle_complete(olds[0]):
        olds[0].rename(v1)
        notes.append(f"restored complete backup {olds[0].name} to {BUNDLE}/")
    elif olds:
        state = [f"{o.name} ({'complete' if bundle_complete(o) else 'incomplete'})" for o in olds]
        raise RecoveryError(f"{BUNDLE}/ is missing and the backups cannot be restored automatically: {state}")
    return notes


def install(tmp: Path, root: Path) -> None:
    """§10.1 step 6: two renames; the previous bundle comes back if the second fails."""
    v1, old = root / BUNDLE, root / f".{BUNDLE}.old-{tmp.name.rsplit('-', 1)[-1]}"
    if v1.exists():
        v1.rename(old)
    try:
        tmp.rename(v1)
    except OSError:
        if old.exists():
            old.rename(v1)
        raise
    if old.exists():
        shutil.rmtree(old)


def export(s: Settings, config_path: Path, skip_audit: bool = False, root: Path | None = None) -> int:
    if s.run_name:
        raise SystemExit(
            "abot export-dashboard describes the active baseline only: use the baseline configuration"
        )
    root = root or dashboard_root(s)
    try:  # §10.1 step 1
        for note in recover(root):
            print(note)
    except RecoveryError as e:
        return _fail([str(e)])
    paths = source_paths(s, config_path)
    missing = [rel(s, p) for p, _ in paths if not p.exists()]
    if missing:
        return _fail([f"V-S1: missing source {m}" for m in missing])
    before = {p: sha256(p) for p, _ in paths}
    src = load(s)
    bad = source_checks(s, src)
    if bad:
        return _fail(bad)
    block, blocking = run_audit(s, config_path, skip_audit)
    if not audit_allows_export(block, skip_audit):
        return _fail([f"audit {block['status']}/{block['outcome']}: export blocked", *blocking])
    print(
        f"audit: {block['status']}" + (f" / {block['outcome']} {block['counts']}" if block["counts"] else "")
    )
    t = src.taxonomy
    sv = {
        "audit": block,
        "a1_reproduces_baseline": bool(src.run_info["a1_reproduces_baseline"]),
        "baseline_outputs_unchanged": bool(src.run_info["baseline_outputs_unchanged"]),
        "baseline_hashes_match_disk": True,  # V-S2 passed above
        "component_classes_check": {
            "reference": t.get("reference"),
            "components_compared": t.get("components_compared"),
            "identical": t.get("identical"),
        },  # fmt: skip
    }
    cat, bsrc = catalog(s)
    ctx = Ctx(s, src, now_utc(), sv, cat, bsrc)
    try:
        files = {
            "city.json": dumps(build_city(ctx)),
            "barangays.geojson": dumps(build_barangays(ctx)),
            "barangay_indicators.json": dumps(build_indicators(ctx)),
        }
        chunk_files, layout = chunk_cells(ctx, cell_features(s, src))
        files |= chunk_files
        files |= {
            "facilities.geojson": dumps(build_facilities(ctx)),
            "network.json": dumps(build_network(ctx)),
            "provenance.json": dumps(build_provenance(ctx)),
        }
        source_files = [{"path": rel(s, p), "sha256": before[p], "bytes": p.stat().st_size,
                         "mtime_utc": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(timespec="seconds"),
                         "used_for": u} for p, u in paths]  # fmt: skip
        manifest = dumps(build_manifest(ctx, files, layout, source_files, git_info(s.root), block))
    except ExportError as e:
        return _fail([str(e)])
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".{BUNDLE}.tmp-{uuid.uuid4().hex[:12]}"
    tmp.mkdir()
    try:
        for name, data in files.items():
            (tmp / name).write_bytes(data)
        (tmp / "manifest.json").write_bytes(manifest)  # written last
        bad = validate(s, src, tmp, ctx, skip_audit)
        bad += [f"V-X1: {rel(s, p)} changed during the export" for p, h in before.items() if sha256(p) != h]
        if bad:
            shutil.rmtree(tmp)
            return _fail(bad)
        install(tmp, root)
    except BaseException:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise
    v1 = root / BUNDLE
    total = sum(p.stat().st_size for p in v1.iterdir())
    print(f"written {rel(s, v1)}/: {len(files) + 1} files, {total:,} bytes; all checks passed")
    for p in sorted(v1.iterdir()):
        print(f"  {p.name:<26} {p.stat().st_size:>12,}")
    for o in owned(root, "old"):
        print(f"note: backup {o.name} kept from an earlier interrupted run; resolve manually (§10.1.1)")
    return 0


def _fail(msgs: list[str]) -> int:
    """Every failed check is reported (§10.1): no truncation."""
    print(
        f"export-dashboard: nothing written (the previous bundle, if any, is unchanged); {len(msgs)} problem(s):"
    )
    for m in msgs:
        print(f"  X {m}")
    return 1


def check(s: Settings, root: Path | None = None) -> int:
    """§9.2 conditions 1, 2, 3, 5; read-only."""
    root = root or dashboard_root(s)
    v1 = root / BUNDLE
    mp = v1 / "manifest.json"
    if not mp.exists():
        print(f"no bundle: {rel(s, mp)} missing")
        olds = owned(root, "old")
        for o in olds:
            try:
                gen = json.loads((o / "manifest.json").read_text(encoding="utf-8"))["generated_utc"]
            except (OSError, ValueError, KeyError, TypeError):
                gen = "unknown"
            print(f"  backup {o.name}: {'complete' if bundle_complete(o) else 'incomplete'}, generated {gen}")
        if not v1.exists() and len(olds) == 1 and bundle_complete(olds[0]):
            print(f"  recoverable: the next `abot export-dashboard` restores it to {BUNDLE}/ before exporting "
                  "(--check changes nothing)")  # fmt: skip
        elif olds:
            print(
                "  not recoverable automatically (several or incomplete backups): resolve manually (§10.1.1)"
            )
        return 1
    man = json.loads(mp.read_text(encoding="utf-8"))
    stale = []
    for f in man["source_files"]:
        p = Path(f["path"]) if Path(f["path"]).is_absolute() else s.root / f["path"]
        if not p.exists():
            stale.append(f"1: source missing: {f['path']}")
        elif sha256(p) != f["sha256"]:
            stale.append(f"1: source changed: {f['path']}")
    if man["config_sha256"] != s.config_sha256:
        stale.append("2: configuration changed")
    gen = datetime.fromisoformat(man["generated_utc"])
    meta = s.interim_dir / "run_meta.json"
    if meta.exists():
        acc = json.loads(meta.read_text(encoding="utf-8")).get("accessibility", {}).get("completed_utc")
        if acc and datetime.fromisoformat(acc) > gen:
            stale.append("3: accessibility stage ran after the export")
    info = s.processed_dir / C.A3_DIR / "run_info.json"
    if info.exists():
        created = json.loads(info.read_text(encoding="utf-8")).get("created_utc")
        if created and datetime.fromisoformat(created) > gen:
            stale.append("3: A3 layer rebuilt after the export")
    for f in man["files"]:
        p = v1 / f["name"]
        if not p.exists() or sha256(p) != f["sha256"]:
            stale.append(f"5: bundle file missing or edited: {f['name']}")
    print(f"bundle {rel(s, v1)}/ generated {man['generated_utc']}, contract {man['contract_version']}, "
          f"commit {man['code']['git_commit']} (clean: {man['code']['git_working_tree_clean']})")  # fmt: skip
    if stale:
        print("STALE:")
        for x in stale:
            print(f"  ! {x}")
        return 1
    print("current: sources, configuration, stage times and bundle files match the manifest")
    return 0
