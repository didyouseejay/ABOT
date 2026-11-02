"""Regression tests for Milestone 02B: 3 km baseline, census-anchored weights, reliability flags,
total-population denominators, drive network-speed sensitivity, `abot audit` and `abot review`.
Offline; synthetic geometry, real configuration rules."""

import json
from datetime import datetime, timedelta

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from abot import accessibility as A
from abot import audit, osm, population, qa, reliability, review
from abot.compare import citywide
from abot.config import DEFAULT_CONFIG, PROJECT_ROOT, Settings, deep_merge, read_config

CFG = Settings(read_config(DEFAULT_CONFIG))
EXP = PROJECT_ROOT / "config" / "experiments"


# --- baseline configuration ------------------------------------------------------------------------


def test_default_buffer_is_3km_and_1km_baseline_is_preserved_separately():
    assert CFG["osm"]["boundary_buffer_m"] == 3000
    hist = Settings(read_config(EXP / "hist_buffer_1km.yaml"))
    assert hist["osm"]["boundary_buffer_m"] == 1000
    assert hist.run_name == "hist_buffer_1km"  # never writes to the baseline folders
    assert hist.processed_dir != CFG.processed_dir and "archive" not in str(hist.processed_dir)
    assert {k: v for k, v in hist.raw.items() if k not in ("osm", "paths")} == {
        k: v for k, v in CFG.raw.items() if k not in ("osm", "paths")
    }  # only the buffer differs: the comparison isolates it


def test_config_fingerprint_changes_with_the_buffer():
    other = Settings(deep_merge(CFG.raw, {"osm": {"boundary_buffer_m": 1000}}))
    assert other.config_sha256 != CFG.config_sha256


@pytest.mark.parametrize("order", [["tertiary", "secondary"], ["secondary", "tertiary"]])
def test_mixed_class_edge_speed_is_deterministic_and_slowest(order):
    speeds = CFG["accessibility"]["drive_speeds_kmh"]
    assert osm.class_speed(order, speeds, 20) == (25.0, "config")  # min(tertiary 25, secondary 25)
    assert osm.class_speed(["primary", "residential"], speeds, 20) == (20.0, "config")
    assert osm.class_speed(["residential", "primary"], speeds, 20) == (20.0, "config")
    assert osm.class_speed(["unknown_class"], speeds, 17) == (17.0, "fallback")


# --- population weights (P1) and fractional allocation (P2) -----------------------------------------


def _grid():
    """Two barangays side by side (x 0-150 and 150-300); three 100 m cells, one straddling both
    barangays and one half outside the city."""
    brgy = gpd.GeoDataFrame(
        {"adm4_pcode": ["B1", "B2"]}, geometry=[box(0, 0, 150, 100), box(150, 0, 300, 100)], crs=32651
    )
    cells = gpd.GeoDataFrame(
        {
            "cell_id": ["c1", "c2", "c3"],
            "wp2020_cell": [100.0, 40.0, 60.0],
            "wp2026_cell": [110.0, 44.0, 66.0],
        },
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(250, 0, 350, 100)],
        crs=32651,
    )
    return cells, brgy


def test_fractional_pieces_split_cells_by_area_and_drop_outside_part():
    cells, brgy = _grid()
    p = population.fractional_pieces(cells, brgy, [2020, 2026]).set_index(["cell_id", "adm4_pcode"])
    assert p.loc[("c2", "B1"), "frac"] == pytest.approx(0.5)
    assert p.loc[("c2", "B2"), "pop_wp2020"] == pytest.approx(20.0)
    assert p.loc[("c3", "B2"), "frac"] == pytest.approx(0.5)  # half of c3 lies outside the city
    assert p["pop_wp2020"].sum() == pytest.approx(100 + 40 + 30)


def test_census_anchoring_matches_census_and_keeps_originals_apart():
    cells, brgy = _grid()
    p = population.fractional_pieces(cells, brgy, [2020, 2026])
    census = pd.Series({"B1": 240.0, "B2": 25.0, "B3": 50.0})  # B3: no WorldPop cells at all
    adj, table = population.anchor_to_census(p, census)
    sums = adj.groupby("adm4_pcode")["pop_census2020_adj"].sum()
    assert sums["B1"] == pytest.approx(240) and sums["B2"] == pytest.approx(25)
    assert table.loc["B1", "census_adj_factor"] == pytest.approx(2.0)  # 240 / (100 + 20)
    assert table.loc["B3", "census_unallocated"] == 50  # reported, never spread to other barangays
    assert np.allclose(adj["pop_wp2020"], p["pop_wp2020"])  # original WorldPop values untouched
    within_b1 = adj[adj["adm4_pcode"] == "B1"].set_index("cell_id")
    assert within_b1.loc["c1", "pop_census2020_adj"] / within_b1.loc[
        "c2", "pop_census2020_adj"
    ] == pytest.approx(5)


def test_primary_weight_must_be_a_known_option():
    assert population.primary_weight(CFG) == ("census_2020_anchored", "pop_census2020_adj")
    bad = Settings(deep_merge(CFG.raw, {"population": {"primary_weight": "census_2024"}}))
    with pytest.raises(ValueError, match="primary_weight"):
        population.primary_weight(bad)


# --- indicators: pieces, p90, denominators -------------------------------------------------------------


def _cells(times, status, pop, ids=None):
    groups = CFG["indicator_groups"]
    return gpd.GeoDataFrame(
        {
            "cell_id": ids or [f"c{i}" for i in range(len(times))],
            "adm4_pcode": ["B1"] * len(times),
            "pop": pop,
            "conn_status": status,
            **{f"t_{m}_{g}": times for m in ("walk", "drive") for g in groups},
        },
        geometry=[Point(i, 0) for i in range(len(times))],
        crs=32651,
    )


BRGY = gpd.GeoDataFrame(
    {"adm4_pcode": ["B1", "B2"], "adm4_name": ["One", "Two"]},
    geometry=[Point(0, 0).buffer(10), Point(50, 0).buffer(10)],
    crs=32651,
)


def test_indicators_use_fractional_pieces_and_report_p90_not_max():
    cells = _cells([5.0, 20.0], [A.OK, A.OK], [100.0, 100.0])
    pieces = pd.DataFrame(
        {"cell_id": ["c0", "c1", "c1"], "adm4_pcode": ["B1", "B1", "B2"], "pop": [100.0, 25.0, 75.0]}
    )
    ind = A.barangay_indicators(CFG, cells, BRGY, pieces).set_index("adm4_pcode")
    assert ind.loc["B1", "pop_total"] == 125 and ind.loc["B2", "pop_total"] == 75
    assert ind.loc["B1", "walk_pharmacy_mean_min"] == pytest.approx((5 * 100 + 20 * 25) / 125)
    assert ind.loc["B2", "walk_pharmacy_mean_min"] == 20.0  # B2 gets c1's time through its piece
    assert ind.loc["B1", "walk_pharmacy_p90_min"] == 20.0
    assert not any(c.endswith("_max_min") for c in ind.columns)


def test_unconnected_residents_stay_in_the_denominator():
    cells = _cells([5.0, np.nan], [A.OK, A.BLOCKED], [80.0, 20.0])
    row = A.barangay_indicators(CFG, cells, BRGY).set_index("adm4_pcode").loc["B1"]
    assert row["walk_pharmacy_pct_le10"] == 80.0  # not 100%: 20% are not connected
    assert row["pct_not_connected"] == 20.0
    city = citywide(cells.drop(columns="geometry")).set_index(["mode", "group"]).loc[("walk", "pharmacy")]
    assert city["pct_le10"] == 80.0 and city["pct_not_connected"] == 20.0


def test_unconnected_external_facility_is_never_a_destination():
    G = nx.MultiDiGraph()
    for n, x in {"a": 0, "b": 100, "c": 1000}.items():
        G.add_node(n, x=x, y=0)
    for u, v in [("a", "b"), ("b", "c")]:
        length = abs(G.nodes[u]["x"] - G.nodes[v]["x"])
        G.add_edge(u, v, length=length, travel_time=length)
        G.add_edge(v, u, length=length, travel_time=length)
    cells = pd.DataFrame([{"u": "a", "v": "b", "a_u": 0.0, "a_v": 100.0, "conn_m": 0.0, "status": A.OK}])
    fac = pd.DataFrame(
        [
            {
                "u": "a",
                "v": "b",
                "a_u": 50.0,
                "a_v": 50.0,
                "conn_m": 0.0,
                "status": A.BLOCKED,
            },  # across water
            {"u": "b", "v": "c", "a_u": 900.0, "a_v": 0.0, "conn_m": 0.0, "status": A.OK},
        ]
    )
    t = A.walk_times(G.reverse(copy=True), cells, fac, 1.0)
    assert t[0] == pytest.approx(1000)  # the nearer, unconnected facility is ignored


def test_drive_network_factor_scales_only_the_network_leg():
    D = nx.MultiDiGraph()
    D.add_edge("n1", "n2", travel_time=100.0)
    DR = D.reverse(copy=True)
    args = (
        np.array([10.0]),
        np.array(["n1"], dtype=object),
        np.array([20.0]),
        np.array(["n2"], dtype=object),
        1.0,
    )
    base = A.drive_times(DR, *args)
    double = A.drive_times(DR, *args, network_factor=2.0)
    assert base[0] == pytest.approx(10 + 100 + 20)
    assert double[0] == pytest.approx(10 + 200 + 20)  # walk legs unchanged


# --- reliability flags (P2) -------------------------------------------------------------------------


REL = CFG["reliability"]


@pytest.mark.parametrize(
    ("cells", "factor", "level"),
    [
        (3, 1.0, "low"),
        (5, 1.0, "low"),
        (8, 1.0, "caution"),
        (40, 1.0, "ok"),
        (40, 3.5, "caution"),
        (40, 0.3, "caution"),
    ],
)
def test_population_reliability_rules(cells, factor, level):
    row = {"pop_cells_centre": cells, "census_adj_factor": factor, "census_unallocated": 0.0}
    got, reasons = reliability.population_level(row, REL["population"], census_anchored=True)
    assert got == level
    assert (got == "ok") == (not reasons)  # every non-ok level says why


def test_population_reliability_error_criterion_only_without_census_anchoring():
    row = {
        "pop_cells_centre": 40,
        "census_adj_factor": 1.0,
        "census_unallocated": 0.0,
        "wp2020_vs_census_pct": 80.0,
    }
    assert reliability.population_level(row, REL["population"], census_anchored=True)[0] == "ok"
    assert reliability.population_level(row, REL["population"], census_anchored=False)[0] == "low"
    row = {"pop_cells_centre": 40, "census_adj_factor": np.nan, "census_unallocated": 12.0}
    assert reliability.population_level(row, REL["population"], census_anchored=True)[0] == "low"


@pytest.mark.parametrize(
    ("pct", "level"), [(0.0, "ok"), (1.0, "ok"), (2.5, "caution"), (5.0, "caution"), (6.4, "low")]
)
def test_network_reliability_rules(pct, level):
    assert (
        reliability.network_level({"pct_not_connected": pct, "pop_not_connected": 10}, REL["network"])[0]
        == level
    )


def test_reliability_dimensions_stay_separate_and_overall_is_the_most_restrictive():
    ind = gpd.GeoDataFrame(
        {
            "adm4_pcode": ["B1", "B2", "B3"],
            "pop_cells_centre": [3, 40, 40],
            "census_adj_factor": [1.0, 1.0, 1.0],
            "census_unallocated": [0.0, 0.0, 0.0],
            "pct_not_connected": [0.0, 30.0, 0.0],
            "pop_not_connected": [0.0, 300.0, 0.0],
        },
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10), box(20, 0, 30, 10)],
        crs=32651,
    )
    fac = gpd.GeoDataFrame({"fid_key": ["node/1"], "inside_city": [True]}, geometry=[Point(5, 5)], crs=32651)
    excl = pd.DataFrame(
        {
            "osm_type": ["node"],
            "osm_id": [1],
            "reason": ["possible duplicate of node/2 (5 m, same name); kept, review"],
            "related_osm_type": ["node"],
            "related_osm_id": [2],
        }
    )
    out = reliability.add_flags(CFG, ind, fac, excl).set_index("adm4_pcode")
    assert list(out["rel_population"]) == ["low", "ok", "ok"]
    assert list(out["rel_network"]) == ["ok", "low", "ok"]
    assert list(out["rel_overall"]) == ["low", "low", "ok"]
    assert set(out["rel_facility_inventory"]) == {"unverified"}  # no registry: never "ok"
    assert list(out["pop_ranking_eligible"]) == [False, False, True]
    assert out.loc["B1", "n_facilities_duplicate_review"] == 1
    assert "population:" in out.loc["B1", "rel_overall_reasons"]
    assert "network:" in out.loc["B2", "rel_overall_reasons"]
    assert not any("score" in c for c in out.columns)


# --- duplicates: structured record ------------------------------------------------------------------


def test_possible_duplicates_record_both_identifiers_and_distance():
    fac = gpd.GeoDataFrame(
        {
            "osm_type": ["node", "node"],
            "osm_id": [3, 4],
            "name": ["PNB", "P.N.B."],
            "category": ["finance"] * 2,
        },
        geometry=[Point(500, 0), Point(510, 0)],
        crs=32651,
    )
    d = osm.possible_duplicates(fac).iloc[0]
    assert (d["osm_id"], d["related_osm_type"], d["related_osm_id"], d["distance_m"]) == (4, "node", 3, 10.0)


# --- review files: suggestions only, decisions preserved -------------------------------------------------


def _rec(fid, subtype, tags, geom="node"):
    return pd.Series({"fid_key": fid, "subtype": subtype, "geom_source": geom, "osm_tags": json.dumps(tags)})


def test_duplicate_suggestions():
    a = _rec("node/1", "bank", {"amenity": "bank", "name": "PNB"})
    assert (
        "probably distinct"
        in review.suggest_duplicate_action(a, _rec("node/2", "atm", {"amenity": "atm"}), 5)[0]
    )
    assert (
        "mapped twice"
        in review.suggest_duplicate_action(a, _rec("node/2", "bank", {"amenity": "bank", "name": "PNB"}), 5)[
            0
        ]
    )
    assert (
        "building outline"
        in review.suggest_duplicate_action(a, _rec("way/2", "bank", {}, "representative_point"), 5)[0]
    )


def test_review_rerun_keeps_reviewer_decisions(tmp_path):
    path = tmp_path / "r.csv"
    first = review._keep_reviewer_columns(pd.DataFrame({"review_id": ["D01", "D02"]}), path, "review_id")
    assert list(first["review_status"]) == ["pending", "pending"]
    first.loc[0, ["review_status", "reviewer_decision"]] = ["reviewed", "distinct_keep_both"]
    first.to_csv(path, index=False)
    again = review._keep_reviewer_columns(
        pd.DataFrame({"review_id": ["D01", "D02", "D03"]}), path, "review_id"
    )
    assert list(again["review_status"]) == ["reviewed", "pending", "pending"]
    assert again.loc[0, "reviewer_decision"] == "distinct_keep_both"


def test_investigation_hint_for_pond_and_beyond_tolerance():
    row = {
        "centre_in_water_feature": "way/1 water_area water=pond natural=water",
        "conn_status": A.BLOCKED,
        "blocking_barriers": "way/1 water_area water=pond",
        "pop": 120.0,
        "max_connector_m": 250,
    }
    assert "outdated" in review.investigation_hint(row)
    row = {
        "centre_in_water_feature": "",
        "conn_status": A.BEYOND,
        "blocking_barriers": "",
        "pop": 2.0,
        "max_connector_m": 250,
    }
    hint = review.investigation_hint(row)
    assert "unmapped" in hint and "low priority" in hint


# --- abot audit: read-only, PASS/WARN/FAIL with actions ---------------------------------------------------


def _empty_project(tmp_path) -> Settings:
    return Settings(deep_merge(CFG.raw, {"paths": {"data_dir": "data", "run_name": None}}), root=tmp_path)


def test_audit_on_missing_outputs_fails_with_actions_and_creates_nothing(tmp_path):
    s = _empty_project(tmp_path)
    findings = audit.Audit(s, DEFAULT_CONFIG, hashes=False).run()
    fails = [f for f in findings if f.status == audit.FAIL]
    assert fails and all(f.action for f in fails)  # every failure says what to do
    assert any("abot fetch" in f.action for f in fails) and any("abot build" in f.action for f in fails)
    assert not (tmp_path / "data").exists()  # nothing was created
    assert {f.status for f in findings} <= {audit.PASS, audit.WARN, audit.FAIL, audit.INFO}


def test_audit_exit_code_and_refuses_to_write_into_data(tmp_path, capsys):
    s = _empty_project(tmp_path)
    assert audit.run(s, DEFAULT_CONFIG, hashes=False) == 1
    with pytest.raises(SystemExit, match="read-only"):
        audit.run(s, DEFAULT_CONFIG, tmp_path / "data" / "audit.md", hashes=False)
    assert not (tmp_path / "data").exists()


def test_audit_detects_stale_stage_order(tmp_path):
    s = _empty_project(tmp_path)
    s.ensure_dirs()
    qa.record_stage(s, "accessibility")
    qa.record_stage(s, "population")  # population rebuilt after accessibility
    # Stamps have millisecond resolution, so two back-to-back records can tie (seen on the Linux CI
    # runner). Set population's stamp explicitly to 1 s after accessibility to make the order certain.
    meta = qa.read_run_meta(s)
    acc = datetime.fromisoformat(meta["accessibility"]["completed_utc"])
    meta["population"]["completed_utc"] = (acc + timedelta(seconds=1)).isoformat(timespec="milliseconds")
    qa.run_meta_path(s).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    a = audit.Audit(s, DEFAULT_CONFIG, hashes=False)
    a.check_staleness()
    order = {f.check: f for f in a.findings}["order: accessibility"]
    assert order.status == audit.FAIL and "abot build --only accessibility" in order.action


def test_audit_detects_a_modified_archive(tmp_path):
    s = _empty_project(tmp_path)
    arch = tmp_path / "data" / "archive"
    (arch / "m01_3edc0dd").mkdir(parents=True)
    f = arch / "m01_3edc0dd" / "barangay_access.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    from abot.fetch.common import sha256

    rec = {"archive": "m01_3edc0dd", "recorded_utc": "x", "files": {"barangay_access.csv": sha256(f)}}
    (arch / "m01_3edc0dd.sha256.json").write_text(json.dumps(rec), encoding="utf-8")
    a = audit.Audit(s, DEFAULT_CONFIG)
    a.check_archive()
    assert {x.check: x.status for x in a.findings}["m01_3edc0dd"] == audit.PASS
    f.write_text("a,b\n1,3\n", encoding="utf-8")
    a = audit.Audit(s, DEFAULT_CONFIG)
    a.check_archive()
    assert {x.check: x.status for x in a.findings}["m01_3edc0dd"] == audit.FAIL
