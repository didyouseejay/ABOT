"""Regression tests for the Milestone 02 corrections (offline; synthetic geometry, real config rules)."""

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from abot import accessibility as A
from abot import osm
from abot.compare import weighted_quantile
from abot.config import DEFAULT_CONFIG, Settings, deep_merge, read_config

CFG = Settings(read_config(DEFAULT_CONFIG))
CATS, PRIORITY = CFG["facilities"], CFG["category_priority"]


def classify(tags: dict) -> dict:
    """{category: subtype record} for one feature, using the project's real rules."""
    row = pd.Series(tags)
    return {
        c: osm.classify_subtype(row, CATS[c]["subtypes"]) for c in osm.all_categories(row, CATS, PRIORITY)
    }


# --- facility classification (audit C-01, C-02, C-09, C-10) -----------------------------------


def test_veterinary_hospital_is_excluded_from_human_health():
    r = classify({"amenity": "hospital", "name": "Cornerstone Pet Hospital"})
    assert r["health"]["subtype"] == "veterinary"
    assert r["health"]["tier"] == "excluded"
    assert r["health"]["status"] == "reclassified_by_name"


def test_animal_bite_centre_stays_human_health():
    r = classify({"amenity": "clinic", "name": "Animal Bite Treatment Center"})
    assert r["health"]["subtype"] == "primary_care"


def test_hospital_and_primary_care_are_separate():
    assert classify({"amenity": "hospital"})["health"]["subtype"] == "hospital"
    assert (
        classify({"amenity": "health_post", "healthcare": "community_health_worker"})["health"]["subtype"]
        == "primary_care"
    )
    assert classify({"healthcare": "laboratory"})["health"]["tier"] == "descriptive"
    assert classify({"amenity": "dentist"})["health"]["tier"] == "descriptive"


def test_multivalued_tags_are_split():
    assert (
        classify({"amenity": "doctors", "healthcare": "doctor;dentist"})["health"]["subtype"]
        == "primary_care"
    )


def test_healthcare_pharmacy_only_is_pharmacy_not_health():
    r = classify({"healthcare": "pharmacy"})
    assert set(r) == {"pharmacy"}


def test_feature_can_belong_to_several_categories():
    r = classify(
        {"amenity": "townhall", "townhall:type": "barangay", "description": "evacuate here in a disaster"}
    )
    assert r["government"]["subtype"] == "barangay"
    assert r["evacuation"]["subtype"] == "named_evacuation_centre"
    assert r["evacuation"]["status"] == "osm_name_only"  # never claimed as official


def test_school_ownership_comes_from_tags():
    assert (
        classify({"amenity": "school", "operator": "Molo District, DepEd"})["education"]["subtype"]
        == "school_public"
    )
    assert (
        classify({"amenity": "school", "operator:type": "private"})["education"]["subtype"]
        == "school_private"
    )
    unknown = classify({"amenity": "school"})["education"]
    assert (unknown["subtype"], unknown["status"]) == ("school_ownership_unknown", "attribute_missing")


def test_descriptive_categories_have_no_indicator_groups():
    routed = {g["category"] for g in CFG["indicator_groups"].values()}
    assert not routed & {"evacuation", "transport", "government"}
    for g in CFG["indicator_groups"].values():  # validate_facility_config also enforces this
        tiers = {r["subtype"]: r["tier"] for r in CATS[g["category"]]["subtypes"]}
        assert all(tiers[st] == "indicative" for st in g["subtypes"])


def test_config_rejects_descriptive_subtype_in_indicator_group():
    bad = deep_merge(CFG.raw, {"indicator_groups": {"x": {"category": "finance", "subtypes": ["atm"]}}})
    with pytest.raises(ValueError, match="not an indicative"):
        osm.validate_facility_config(Settings(bad))


def test_duplicates_and_merges_are_recorded_not_silently_dropped():
    fac = gpd.GeoDataFrame(
        {
            "osm_type": ["way", "node", "node", "node"],
            "osm_id": [1, 2, 3, 4],
            "name": ["Jaro Market", "Jaro Market", "PNB", "P.N.B."],
            "category": ["market", "market", "finance", "finance"],
        },
        geometry=[Polygon([(0, 0), (20, 0), (20, 20), (0, 20)]), Point(5, 5), Point(500, 0), Point(510, 0)],
        crs=32651,
    )
    kept, merged = osm._merge_points_inside_polygons(fac)
    assert list(merged["osm_id"]) == [2] and "merged" in merged["reason"].iloc[0]
    assert len(kept) == 3
    dups = osm.possible_duplicates(kept.assign(geometry=kept.geometry.representative_point()))
    assert list(dups["osm_id"]) == [4]  # same normalised name within 50 m: flagged, kept


# --- drive speeds (audit C-05) ---------------------------------------------------------------


def _speed_graph(edges):
    G = nx.MultiDiGraph()
    for i, (hw, maxspeed) in enumerate(edges):
        G.add_edge(i, i + 100, highway=hw, maxspeed=maxspeed, length=1000.0)
    return G


@pytest.mark.parametrize(
    ("policy", "hw", "maxspeed", "speed", "source"),
    [
        ("cap", "primary", "60", 30, "config"),  # legal limit above assumption: never raises
        ("cap", "primary", "20", 20, "maxspeed_cap"),  # lower limit caps
        ("cap", "primary", ["80", "40"], 30, "config"),  # lists -> lowest value, still above 30
        ("cap", "primary", "10 mph", 16.09344, "maxspeed_cap"),
        ("override", "primary", "60", 60, "maxspeed"),  # Milestone 01 behaviour, opt-in only
        ("ignore", "primary", "20", 30, "config"),
        ("cap", "primary_link", None, 25, "config"),  # *_link classes are configured
        ("cap", "busway", None, 20, "fallback"),
        ("cap", ["secondary", "primary"], None, 25, "config"),  # simplified lists: first class
    ],
)
def test_drive_speed_policy(policy, hw, maxspeed, speed, source):
    acc = CFG["accessibility"]
    G = osm.assign_drive_speeds(_speed_graph([(hw, maxspeed)]), acc["drive_speeds_kmh"], 20, policy)
    d = next(iter(G.edges(data=True)))[2]
    assert d["speed_kph"] == pytest.approx(speed)
    assert d["speed_source"] == source
    assert d["travel_time"] == pytest.approx(1000 / (speed / 3.6))


# --- connections to the network (audit C-03, C-04, P-01) ---------------------------------------


def _grid_graph():
    """Two parallel east-west streets at y=0 and y=200, each 0..400 m, bidirectional."""
    G = nx.MultiDiGraph()
    pts = {"a": (0, 0), "b": (400, 0), "c": (0, 200), "d": (400, 200)}
    for n, (x, y) in pts.items():
        G.add_node(n, x=x, y=y)
    for u, v in [("a", "b"), ("c", "d"), ("a", "c")]:
        length = float(np.hypot(pts[u][0] - pts[v][0], pts[u][1] - pts[v][1]))
        for s, t in ((u, v), (v, u)):
            G.add_edge(s, t, length=length, travel_time=length / 1.25)
    return G


CONN = {"max_connector_m": 250, "max_candidates": 12, "water_crossing_tolerance_m": 20}


def _checker(**kinds):
    rows = [(k, g) for k, geoms in kinds.items() for g in geoms]
    if not rows:
        return A.BarrierChecker(None, 20)
    bar = gpd.GeoDataFrame({"kind": [k for k, _ in rows]}, geometry=[g for _, g in rows], crs=32651)
    return A.BarrierChecker(bar, 20)


def test_connects_to_edge_interior_not_node():
    c = A.connect_point(Point(100, 40), A.EdgeIndex(_grid_graph()), _checker(), CONN, 50, 250)
    assert c.status == A.OK
    assert c.conn_m == pytest.approx(40)
    assert {c.u, c.v} == {"a", "b"}
    assert (c.a_u if c.u == "a" else c.a_v) == pytest.approx(100)  # 100 m along from node a


def test_river_forces_connection_to_other_side():
    river = LineString([(-50, 70), (450, 70)])  # east-west river at y=70
    c = A.connect_point(
        Point(200, 120), A.EdgeIndex(_grid_graph()), _checker(water_line=[river]), CONN, 0, 250
    )
    assert c.status == A.OK and c.rerouted is False  # y=200 street: nearest (80 m), same side
    c = A.connect_point(
        Point(200, 80), A.EdgeIndex(_grid_graph()), _checker(water_line=[river]), CONN, 0, 250
    )
    assert c.status == A.OK and c.rerouted is True  # y=0 street (80 m) is across the river
    assert c.conn_m == pytest.approx(120)  # y=200 street instead


def test_point_surrounded_by_water_is_not_connected():
    pond = Polygon([(150, 20), (250, 20), (250, 180), (150, 180)]).difference(Point(200, 100).buffer(10))
    c = A.connect_point(
        Point(200, 100), A.EdgeIndex(_grid_graph()), _checker(water_area=[pond]), CONN, 0, 250
    )
    assert c.status == A.BLOCKED


def test_crossing_near_the_cell_centre_is_tolerated():
    creek = LineString([(-50, 95), (450, 95)])  # 5 m from a cell centre at y=100, inside its 50 m radius
    pt = Point(200, 100)
    edges, checker = A.EdgeIndex(_grid_graph()), _checker(water_line=[creek])
    assert A.connect_point(pt, edges, checker, CONN, 50, 250).rerouted is False
    assert A.connect_point(pt, edges, checker, CONN, 0, 250).rerouted is True


def test_far_point_is_beyond_tolerance_and_gets_no_time():
    c = A.connect_point(Point(200, 600), A.EdgeIndex(_grid_graph()), _checker(), CONN, 50, 250)
    assert c.status == A.BEYOND and c.nearest_m == pytest.approx(400)


# --- travel times ------------------------------------------------------------------------------


def test_walk_time_uses_position_along_edge_and_same_edge_shortcut():
    G = _grid_graph()
    edges, checker = A.EdgeIndex(G), _checker()
    cells = A.connect_points(
        gpd.GeoSeries([Point(100, 10), Point(390, 210), Point(200, 600)]), edges, checker, CONN, 0
    )
    fac = A.connect_points(gpd.GeoSeries([Point(300, 0)]), edges, checker, CONN, 0)
    t = A.walk_times(G.reverse(copy=True), cells, fac, 1.25)
    assert t[0] == pytest.approx((10 + 200) / 1.25)  # same street: direct, not via a node
    assert t[1] == pytest.approx((10 + 390 + 200 + 300) / 1.25)  # around via node c and a
    assert np.isnan(t[2])  # not connected -> no time


def test_drive_access_is_walked_on_the_network_not_a_straight_line():
    # Walk network: home H on a footpath that only joins the drive network at node 'far'.
    W = nx.MultiDiGraph()
    for n, (x, y) in {"near": (0, 0), "far": (600, 0), "h1": (0, 50), "h2": (600, 50)}.items():
        W.add_node(n, x=x, y=y)
    for u, v, length in [("h1", "h2", 600.0), ("h2", "far", 50.0), ("near", "far", 600.0)]:
        W.add_edge(u, v, length=length)
        W.add_edge(v, u, length=length)
    # 'near' is the closest drive node in a straight line (50 m), but a wall/river separates them.
    dist, src = A.nearest_source_dijkstra(W, ["near", "far"])
    conn = pd.DataFrame([{"u": "h1", "v": "h2", "a_u": 0.0, "a_v": 600.0, "conn_m": 0.0, "status": A.OK}])
    metres, entry = A.drive_access(conn, dist, src)
    # h1 has no path to 'near' except via 'far' (1250 m); the walked access is h1-h2-far = 650 m.
    assert entry[0] == "far" and metres[0] == pytest.approx(650.0)


def test_nearest_source_dijkstra():
    G = _grid_graph()
    dist, src = A.nearest_source_dijkstra(G, ["b", "c"])
    assert src["a"] == "c" and dist["a"] == pytest.approx(200)
    assert src["d"] in {"b", "c"} and dist["d"] == pytest.approx(400)


# --- indicators and QA (audit C-04, C-12, C-13) ---------------------------------------------------


def _cells(times, status, pop):
    return gpd.GeoDataFrame(
        {
            "adm4_pcode": ["B1"] * len(times),
            "pop": pop,
            "conn_status": status,
            **{f"t_{m}_{g}": times for m in ("walk", "drive") for g in CFG["indicator_groups"]},
        },
        geometry=[Point(i, 0) for i in range(len(times))],
        crs=32651,
    )


def test_unconnected_population_is_reported_not_counted_as_within_or_beyond():
    cells = _cells([5.0, 20.0, np.nan], [A.OK, A.OK, A.BEYOND], [100.0, 100.0, 300.0])
    brgy = gpd.GeoDataFrame(
        {"adm4_pcode": ["B1"], "adm4_name": ["One"]}, geometry=[Point(0, 0).buffer(10)], crs=32651
    )
    row = A.barangay_indicators(CFG, cells, brgy).iloc[0]
    assert row["pop_not_connected"] == 300 and row["pop_connected"] == 200
    # Milestone 02B: shares use ALL residents (100 of 500 within 10 min); the 300 unconnected count
    # neither as within nor beyond: within 20% + beyond 20% + not connected 60% = 100%.
    assert row["walk_pharmacy_pct_le10"] == 20.0
    assert row["pct_not_connected"] == 60.0
    assert row["walk_pharmacy_mean_min"] == 12.5  # means describe connected residents only


def test_valid_assignment_check_can_fail():
    cells = _cells([5.0, np.nan], [A.OK, A.OK], [100.0, 100.0])
    cells["conn_m"], cells["nearest_edge_m"] = 10.0, 10.0
    cells["conn_rerouted"], cells["conn_crosses_wall"] = False, False
    fc = pd.DataFrame({"status": [A.OK], "conn_m": [5.0]}, index=["node/1"])
    checks = A.accessibility_checks(CFG, cells, fc, None)
    assert checks["walk_pharmacy_connected_without_time"]["ok"] is False
    assert checks["walk_pharmacy_connected_without_time"]["value"] == 1


# --- config and comparison helpers ---------------------------------------------------------------


def test_experiment_config_extends_and_isolates_outputs(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text(
        "paths: {data_dir: data, run_name: null}\nosm: {boundary_buffer_m: 1000, network_types: [walk]}\n"
    )
    exp = tmp_path / "exp" / "e7.yaml"
    exp.parent.mkdir()
    exp.write_text("extends: ../base.yaml\npaths: {run_name: e7}\nosm: {boundary_buffer_m: 3000}\n")
    s = Settings(read_config(exp), root=tmp_path)
    assert s["osm"] == {"boundary_buffer_m": 3000, "network_types": ["walk"]}
    assert s.raw_dir == tmp_path / "data" / "raw"  # shared
    assert s.processed_dir == tmp_path / "data" / "processed" / "e7"
    assert s.interim_dir == tmp_path / "data" / "interim" / "e7"


def test_weighted_quantile():
    v, w = np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.0, 1.0, 1.0, 7.0])
    assert weighted_quantile(v, w, 0.5) == 4.0
    assert weighted_quantile(v, w, 0.1) == 1.0


def test_parse_maxspeed():
    assert osm.parse_maxspeed("40") == 40
    assert osm.parse_maxspeed(["50", "30"]) == 30
    assert osm.parse_maxspeed("PH:urban") is None
    assert osm.parse_maxspeed(np.nan) is None


def test_provenance_manifest_accumulates_runs_and_keeps_other_entries(tmp_path):
    raw = tmp_path / "data" / "raw"
    (raw / "osm_cache").mkdir(parents=True)
    (raw / "manifest.json").write_text('{"worldpop/x.tif": {"sha256": "abc"}}', encoding="utf-8")
    cache = raw / "osm_cache" / "q.json"
    cache.write_text(
        '{"osm3s": {"timestamp_osm_base": "2026-10-31T06:13:55Z"}, "elements": [1, 2]}', encoding="utf-8"
    )
    for run in (None, "e7"):
        s = Settings(deep_merge(CFG.raw, {"paths": {"data_dir": "data", "run_name": run}}), root=tmp_path)
        s.ensure_dirs()
        recs = osm.provenance_records(s, [{"label": "network_walk", "file": cache, "cache_hit": True}])
        osm.write_provenance(s, recs, {"network_types": ["walk"]})
    import json

    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["osm_cache/q.json"]
    assert entry["used_by_runs"] == ["baseline", "e7"]
    assert entry["overpass_timestamp_osm_base"] == "2026-10-31T06:13:55Z"
    assert manifest["worldpop/x.tif"] == {"sha256": "abc"}  # other provenance untouched


@pytest.mark.parametrize(
    ("tags", "geom", "kind"),
    [
        ({"waterway": "river"}, LineString([(0, 0), (1, 0)]), "water_line"),
        ({"waterway": "stream", "tunnel": "culvert"}, LineString([(0, 0), (1, 0)]), "culverted_waterway"),
        ({"waterway": "canal", "tunnel": "no"}, LineString([(0, 0), (1, 0)]), "water_line"),
        ({"natural": "water", "water": "fishpond"}, Polygon([(0, 0), (1, 0), (1, 1)]), "water_area"),
        ({"barrier": "wall"}, LineString([(0, 0), (1, 0)]), "wall"),
        ({"waterway": "drain"}, LineString([(0, 0), (1, 0)]), None),
    ],
)
def test_barrier_kinds_and_culverts_are_crossable(tags, geom, kind):
    row = pd.Series({**tags, "geometry": geom})
    assert osm.barrier_kind(row, CFG["osm"]["barriers"]) == kind


def test_barangay_indicators_flag_when_many_residents_not_connected():
    cells = _cells([5.0, 6.0, np.nan], [A.OK, A.OK, A.BLOCKED], [90.0, 0.0, 10.0])
    brgy = gpd.GeoDataFrame(
        {"adm4_pcode": ["B1"], "adm4_name": ["One"]}, geometry=[Point(0, 0).buffer(10)], crs=32651
    )
    row = A.barangay_indicators(CFG, cells, brgy).iloc[0]
    assert row["pct_not_connected"] == 10.0
    assert bool(row["indicators_flag_not_connected"]) is True  # 10% > 5% threshold
