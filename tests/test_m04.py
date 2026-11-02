"""Regression tests for Milestone 04: component-aware network evaluation, access classification,
the targeted Overpass query, the historical archive and review-decision preservation. Offline;
synthetic data, real configuration rules."""

import json
from collections.abc import Mapping, Sequence

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pytest
import requests
from shapely.geometry import Point

from abot import accessibility as A
from abot import archive
from abot import components as C
from abot.config import DEFAULT_CONFIG, PROJECT_ROOT, Settings, deep_merge, read_config
from abot.fetch import targeted as T

CFG = Settings(read_config(DEFAULT_CONFIG))
NO_BARRIERS = A.BarrierChecker(None, 20)


def _graph(paths: Mapping[int, Sequence[tuple[float, float]]]) -> nx.MultiDiGraph:
    """Two-way walk graph from {first node id: [(x, y), ...]} polylines (node ids are consecutive)."""
    G = nx.MultiDiGraph()
    for start, pts in paths.items():
        ids = list(range(start, start + len(pts)))
        for n, (x, y) in zip(ids, pts, strict=True):
            G.add_node(n, x=x, y=y)
        for a, b in zip(ids, ids[1:], strict=False):
            d = float(np.hypot(G.nodes[a]["x"] - G.nodes[b]["x"], G.nodes[a]["y"] - G.nodes[b]["y"]))
            G.add_edge(a, b, length=d)
            G.add_edge(b, a, length=d)
    C.set_walk_time(G, CFG["accessibility"]["walk_speed_kmh"] / 3.6)
    return G


# main: y = 0 from x = 0 to 1000; isolated "subdivision" fragment: y = 200 from x = 0 to 200
MAIN = {1: [(0, 0), (250, 0), (500, 0), (750, 0), (1000, 0)]}
FRAG = {10: [(0, 200), (100, 200), (200, 200)]}


def _cells(*pts):
    return gpd.GeoDataFrame({"pop": [10.0] * len(pts)}, geometry=[Point(p) for p in pts])


def _roles(*recs):
    rows = [{"fid_key": k, "category": c, "subtype": st, "geometry": Point(p)} for k, c, st, p in recs]
    return gpd.GeoDataFrame(rows)


CLINIC = ("node/1", "health", "primary_care", (950, 5))  # on the main network only
SCHOOL = ("node/2", "education", "school_public", (150, 205))  # inside the fragment


def test_component_aware_cell_gets_internal_but_never_citywide_access():
    G = _graph(MAIN | FRAG)
    cells = _cells((100, 190))  # 10 m from the fragment, 190 m from the main network
    res, _ = C.evaluate(CFG, G, cells, _roles(CLINIC, SCHOOL), NO_BARRIERS)
    assert res.at[0, "status"] == A.OK and not res.at[0, "network_node"]
    assert res.at[0, "conn_m"] == pytest.approx(10)
    assert np.isnan(res.at[0, "t_walk_health_primary_care"])  # no route out of the fragment
    assert res.at[0, "t_walk_education_basic"] < 2  # internal access is kept, not discarded
    comp = res["u"].map({n: "main" for n in range(1, 6)} | dict.fromkeys(range(10, 13), "F001"))
    cat = C.categorise(res, comp, {"main": "main", "F001": "isolated_mapped_dead_end"})
    assert cat[0] == "locally_connected"


def test_baseline_attaches_the_same_cell_to_main_by_a_longer_straight_connector():
    # Documents the approximation the component-aware approach exposes (M03: 4,812 residents).
    G = _graph(MAIN)
    res, _ = C.evaluate(CFG, G, _cells((100, 190)), _roles(CLINIC, SCHOOL), NO_BARRIERS)
    assert res.at[0, "network_node"] and res.at[0, "conn_m"] == pytest.approx(190)
    assert not np.isnan(res.at[0, "t_walk_health_primary_care"])


def test_no_artificial_link_between_close_components():
    # Fragment 1 m from the main network: still two components, and no route across the gap.
    near = {10: [(0, 1), (100, 1)]}
    G = _graph(MAIN | near)
    before = [sorted(c) for c in C.ordered_components(G)]
    res, _ = C.evaluate(
        CFG, G, _cells((50, 30), (950, -5)), _roles(CLINIC), NO_BARRIERS, extra_fac_graph=_graph(MAIN)
    )
    assert [sorted(c) for c in C.ordered_components(G)] == before and len(before) == 2
    assert not res.at[0, "network_node"] and np.isnan(res.at[0, "t_walk_health_primary_care"])
    assert res.at[1, "network_node"] and res.at[1, "t_walk_health_primary_care"] < 1


def test_facility_near_a_fragment_keeps_its_main_connection_in_A3_only():
    # A campus/mall fragment: A2 pulls the facility onto it, A3 keeps the main connection too.
    hosp = ("node/3", "health", "hospital", (100, 195))
    G = _graph(MAIN | FRAG)
    cells = _cells((900, -5))
    a2, _ = C.evaluate(CFG, G, cells, _roles(hosp), NO_BARRIERS)
    a3, fc = C.evaluate(CFG, G, cells, _roles(hosp), NO_BARRIERS, extra_fac_graph=_graph(MAIN))
    assert np.isnan(a2.at[0, "t_walk_health_hospital"])  # A2: false loss of a citywide destination
    assert not np.isnan(a3.at[0, "t_walk_health_hospital"]) and len(fc.loc[["node/3"]]) == 2


def test_a_nearby_road_alone_gives_no_accessibility():
    G = _graph(MAIN | FRAG)
    res, _ = C.evaluate(CFG, G, _cells((100, 190)), _roles(CLINIC), NO_BARRIERS)
    times = res.filter(like="t_walk_").to_numpy(dtype=float)
    assert res.at[0, "status"] == A.OK and np.isnan(times).all()


def test_cell_beyond_tolerance_stays_unconnected():
    G = _graph(MAIN)
    res, _ = C.evaluate(CFG, G, _cells((500, 400)), _roles(CLINIC), NO_BARRIERS)
    assert res.at[0, "status"] == A.BEYOND and not res.at[0, "network_node"]


def test_component_order_is_deterministic():
    a = _graph({20: [(0, 0), (1, 0)], 1: [(0, 5), (1, 5), (2, 5)], 7: [(0, 9), (1, 9)]})
    b = _graph({7: [(0, 9), (1, 9)], 1: [(0, 5), (1, 5), (2, 5)], 20: [(0, 0), (1, 0)]})
    order = [sorted(c) for c in C.ordered_components(a)]
    assert order == [sorted(c) for c in C.ordered_components(b)] == [[1, 2, 3], [7, 8], [20, 21]]


# --- A3 component-aware reporting layer ----------------------------------------------------------

COMP_OF = {n: "main" for n in range(1, 6)} | dict.fromkeys(range(10, 13), "F001")
COMP_CLASS = {"main": "main", "F001": "isolated_mapped_dead_end"}


def _a3(tmp_cells=((100, 190), (900, -5), (500, 400))):
    G = _graph(MAIN | FRAG)
    cells = _cells(*tmp_cells).set_crs(32651)
    cells["cell_id"] = [f"c{i}" for i in range(len(cells))]
    cells["adm4_pcode"] = "B1"
    res, _ = C.evaluate(CFG, G, cells, _roles(CLINIC, SCHOOL), NO_BARRIERS, extra_fac_graph=_graph(MAIN))
    cat = C.categorise(res, res["u"].map(COMP_OF), COMP_CLASS)
    return cells, res, C.a3_cells(CFG, cells, res, cat, COMP_OF, COMP_CLASS)


def test_a3_keeps_local_and_citywide_times_in_separate_columns():
    _, _, a3c = _a3()
    local, main = a3c.iloc[0], a3c.iloc[1]
    assert list(a3c["a3_category"]) == ["locally_connected", "network_connected", "unconnected"]
    assert np.isnan(local["t_walk_education_basic_citywide"]) and local["t_walk_education_basic_internal"] < 2
    assert np.isnan(local["t_walk_health_primary_care_internal"])  # the clinic is not in its component
    assert main["t_walk_health_primary_care_citywide"] < 2 and np.isnan(
        main["t_walk_health_primary_care_internal"]
    )
    assert a3c.filter(like="t_walk_").iloc[2].isna().all()  # unconnected: no time of either kind


def test_a3_barangay_accounts_for_every_resident_across_categories():
    _, _, a3c = _a3()
    pieces = pd.DataFrame({"cell_id": ["c0", "c0", "c1", "c2"], "adm4_pcode": ["B1", "B2", "B1", "B2"],
                           "pop": [6.0, 4.0, 10.0, 10.0]})  # fmt: skip
    brgy = pd.DataFrame({"adm4_pcode": ["B1", "B2"], "adm4_name": ["One", "Two"]})
    bt = C.a3_barangay(CFG, a3c, pieces, brgy).set_index("adm4_pcode")
    assert bt.at["B1", "pop_total"] == 16 and bt.at["B2", "pop_total"] == 14
    for b in ("B1", "B2"):
        parts = sum(bt.at[b, f"pop_{c}"] for c in C.CATEGORIES)
        assert parts == pytest.approx(bt.at[b, "pop_total"])
        assert sum(bt.at[b, f"pct_{c}"] for c in C.CATEGORIES) == pytest.approx(100, abs=0.05)
    # citywide share in B1 counts only the network-connected 10 of 16 residents (all stay in the denominator)
    assert bt.at["B1", "walk_health_primary_care_pct_le15"] == pytest.approx(62.5)
    assert bt.at["B2", "pop_local_internal_education_basic"] == 4.0  # internal access kept, reported apart
    assert bt.at["B2", "walk_education_basic_pct_le15"] == 0.0  # and never counted as citywide


def test_a3_citywide_reports_a1_and_a3_side_by_side():
    cells, res, a3c = _a3()
    city = C.a3_citywide(CFG, cells, res.assign(status=A.OK), a3c).set_index("metric")
    assert city.at["pop_network_connected", "A3"] + city.at["pop_locally_connected", "A3"] + city.at[
        "pop_unconnected", "A3"] + city.at["pop_access_uncertain", "A3"] == pytest.approx(30)  # fmt: skip
    assert city.at["walk_education_basic_pct_le15", "A3_local_internal_pop"] == 10.0


def test_scenario_labels_call_a1_optimistic_not_an_upper_bound():
    lab = C.SCENARIO_LABELS["A1_baseline"]
    assert "optimistic" in lab and "not a verified upper bound" in lab
    assert "not preferred" in C.SCENARIO_LABELS["A2_all_eligible"]


def test_baseline_outputs_unchanged_by_the_a3_layer():
    info = PROJECT_ROOT / "data" / "processed" / "component_aware" / "run_info.json"
    if not info.exists():
        pytest.skip("A3 layer not built in this checkout")
    s = Settings(read_config(DEFAULT_CONFIG))
    assert json.loads(info.read_text(encoding="utf-8"))["baseline_sha256"] == C.baseline_hashes(s)


def test_baseline_hashes_detect_a_changed_output(tmp_path):
    s = _project(tmp_path)
    s.ensure_dirs()
    (s.processed_dir / "barangay_access.csv").write_text("a\n1\n", encoding="utf-8")
    h = C.baseline_hashes(s)
    (s.processed_dir / "barangay_access.csv").write_text("a\n2\n", encoding="utf-8")
    assert C.baseline_hashes(s) != h


# --- access classification --------------------------------------------------------------------


def test_classification_summary_counts_ways_gates_cells_and_residents():
    et = pd.DataFrame(
        {
            "u": [1, 2, 3, 4], "v": [2, 1, 4, 3], "k": [0] * 4, "osmids": [[101], [101], [102], [102]],
            "length": [100.0, 100.0, 50.0, 50.0], "way_class": ["no", "no", "untagged", "untagged"],
            "gates": [["private"], ["private"], [], []],
        }
    )  # fmt: skip
    ways = {101: {"tags": {"access": "no"}}, 102: {"tags": {"highway": "residential"}}}
    gates = pd.DataFrame({"node": [9], "gate_class": ["private"], "flag_for_review": [True],
                          "field_verification_required": [True], "component": ["main"]})  # fmt: skip
    a1 = pd.DataFrame({"status": [A.OK, A.OK, A.BEYOND], "u": [2, 3, None], "v": [1, 4, None]})
    out = C.classification_summary(
        et, gates, ways, dict.fromkeys([1, 2, 3, 4], "main"), a1, pd.Series([5.0, 7.0, 9.0])
    )
    w = out[out["kind"] == "way"].set_index("access_class")
    assert w.at["no", "ways"] == 1 and w.at["no", "km"] == 0.1
    assert (
        w.at["no", "public_pedestrian_status"] == "prohibited"
        and w.at["no", "pop_attached_A1"] == 5.0
        and w.at["untagged", "pop_attached_A1"] == 7.0
    )
    g = out[out["kind"] == "gate node"].set_index("access_class")
    assert g.at["private", "nodes_flag_for_review"] == 1 and g.at["private", "cells_attached_A1"] == 1
    assert (
        g.at["private", "nodes_field_verification"] == 1 and "flag for review" in g.at["private", "treatment"]
    )


# --- targeted snapshot evidence ------------------------------------------------------------------


def test_snapshot_evidence_finds_only_links_that_touch_both_sides():
    walk_ways = {1: {"nodes": [11, 12]}, 2: {"nodes": [21, 22]}}  # F001 way, main way
    snap = {"elements": [
        {"type": "way", "id": 1, "nodes": [11, 12], "tags": {"highway": "residential"}},
        {"type": "way", "id": 7, "nodes": [12, 30], "tags": {"highway": "service", "access": "private"}},
        {"type": "way", "id": 8, "nodes": [30, 21], "tags": {"highway": "footway"}},  # chain to main
        {"type": "way", "id": 9, "nodes": [11, 40], "tags": {"highway": "path"}},  # touches F001 only
        {"type": "node", "id": 30, "lon": 1.0, "lat": 2.0, "tags": {"barrier": "gate", "access": "private"}},
    ]}  # fmt: skip
    elements, links = T.snapshot_evidence(snap, walk_ways, {1: "F001", 2: "main"})
    assert len(links) == 1 and links.at[0, "ways"] == "way/7;way/8" and links.at[0, "connects"] == "F001;main"
    assert not links.at[0, "applied"]
    e = elements.set_index("id")
    assert e.at[7, "access"] == "private" and e.at[7, "in_walk_cache"] == False  # noqa: E712
    assert e.at[30, "barrier"] == "gate"


def _corridor_snap(link_tags: dict, gate_tags: dict | None, tags8: dict | None = None):
    """F001 way (nodes 1-2) and main way (3-4) in the walk cache; links 7 (2-5) and 8 (5-3) outside it."""
    pts = {
        1: (122.5700, 10.72),
        2: (122.5710, 10.72),
        5: (122.5715, 10.72),
        3: (122.5720, 10.72),
        4: (122.5730, 10.72),
    }
    nodes = [{"type": "node", "id": n, "lon": x, "lat": y, **({"tags": gate_tags} if n == 5 and gate_tags else {})}
             for n, (x, y) in pts.items()]  # fmt: skip
    ways = [{"type": "way", "id": 7, "nodes": [2, 5], "tags": {"highway": "service", **link_tags}},
            {"type": "way", "id": 8, "nodes": [5, 3], "tags": {"highway": "service", **(link_tags if tags8 is None else tags8)}}]  # fmt: skip
    walk_ways = {1: {"nodes": [1, 2]}, 2: {"nodes": [3, 4]}}
    walk_nodes = {n: {"lon": x, "lat": y} for n, (x, y) in pts.items()}
    snap = {"elements": nodes + ways}
    _, links = T.snapshot_evidence(snap, walk_ways, {1: "F001", 2: "main"})
    return T.corridor_analysis(snap, walk_ways, walk_nodes, {1: "F001", 2: "main"}, links)


def test_corridor_physical_link_with_private_tags_is_not_public_access():
    cor = _corridor_snap({"access": "private"}, {"barrier": "gate", "access": "private"})
    r = cor.iloc[0]
    assert r["fragment"] == "F001" and r["physical_connection"] == "confirmed_in_osm_topology"
    assert r["path_ways"] == "way/7;way/8" and r["path_m"] == pytest.approx(109.4, abs=0.5)
    assert "node/5" in r["path_gates"] and '"access": "private"' in r["path_gates"]
    assert r["public_pedestrian_access"] == "restricted_by_mapped_tags"
    assert bool(r["field_verification_needed"]) and not bool(r["applied"])
    # 3. physical connectivity does not imply public pedestrian access; the group is not inferred
    assert r["path_mapped_access_status"] == "private" and r["public_pedestrian_status"] == "not_public"
    assert r["authorized_group"] == "unspecified"


def test_corridor_one_private_way_on_the_path_is_enough():
    # way 7 private, way 8 untagged: the old all-ways rule called this unverified
    r = _corridor_snap({"access": "private"}, None, tags8={}).iloc[0]
    assert (
        r["path_mapped_access_status"] == "private"
        and r["public_pedestrian_access"] == "restricted_by_mapped_tags"
    )
    assert "way/7" in r["classification_reason"]


def test_corridor_gate_restriction_applies_even_on_untagged_ways():
    r = _corridor_snap({}, {"barrier": "gate", "access": "private"}).iloc[0]
    assert r["path_mapped_access_status"] == "private" and "node/5" in r["classification_reason"]


def test_corridor_without_access_tags_stays_unverified_never_public():
    r = _corridor_snap({}, None).iloc[0]  # connected in topology, but no tag says who may walk it
    assert r["physical_connection"] == "confirmed_in_osm_topology"
    assert r["public_pedestrian_access"] == "unverified" and r["path_gates"] == "none"
    # 5. a missing gate does not establish public access
    assert r["public_pedestrian_status"] == "not_restricted_by_tags_unverified"
    assert "no gate mapped on the path: not evidence of public access" in r["classification_reason"]


def test_corridor_foot_yes_override_is_not_restricted_but_still_needs_field_check():
    r = _corridor_snap({"access": "private", "foot": "yes"}, None).iloc[0]
    assert r["public_pedestrian_access"] == "unverified" and bool(r["field_verification_needed"])
    assert r["public_pedestrian_status"] == "permitted_by_foot_tag_conflicting"


# 9. The F001 / F100 / F101 pattern: physically connected through private ways and private gates,
# kept apart from the public network; the snapshot never changes a component class or a cell category.
@pytest.mark.parametrize(
    "link, gate",
    [
        (
            {"highway": "tertiary", "access": "private"},
            {"barrier": "gate", "access": "private"},
        ),  # Gustilo St
        ({"access": "private"}, None),  # F001 northern private way, no gate mapped
        ({"access": "private"}, {"barrier": "gate", "access": "private"}),  # fishport service corridor
    ],
)
def test_gap_fragments_keep_connectivity_without_public_promotion(link, gate):
    r = _corridor_snap(link, gate).iloc[0]
    assert r["physical_connection"] == "confirmed_in_osm_topology" and not bool(r["applied"])
    assert r["public_pedestrian_status"] == "not_public" and r["authorized_group"] == "unspecified"
    assert bool(r["field_verification_needed"])
    text = C.remaining_unverified(True, r.to_dict())
    assert "physical connection is not public pedestrian access" in text and "names no group" in text
    assert "residents, workers" not in text


def test_remaining_unverified_reflects_snapshot_state():
    absent = C.remaining_unverified(False, None)
    none_found = C.remaining_unverified(True, None)
    linked = C.remaining_unverified(True, {"path_ways": "way/7"})
    assert "no targeted snapshot present" in absent
    for text in (none_found, linked):
        assert "not obtained" not in text and "no targeted snapshot" not in text
    assert "physical connection is not public pedestrian access" in linked


def test_snapshot_evidence_absent_removes_stale_tables_and_reports_cache_only(tmp_path):
    s = _project(tmp_path)
    out = tmp_path / "m04"
    out.mkdir()
    for f in C.SNAPSHOT_FILES:
        (out / f).write_text("stale", encoding="utf-8")
    snap = C.gap_snapshot_evidence(s, out, {}, {}, {})
    assert snap["status"]["obtained"] is False and snap["corridors"].empty
    assert not any((out / f).exists() for f in C.SNAPSHOT_FILES)
    assert json.loads((out / "snapshot_status.json").read_text(encoding="utf-8"))["obtained"] is False


def test_readme_snapshot_section_matches_the_evidence():
    gap = pd.DataFrame(
        {"fragment": ["F001"], "remaining_unverified": [C.remaining_unverified(True, {"x": 1})]}
    )
    cor = _corridor_snap({"access": "private"}, {"barrier": "gate", "access": "private"})
    present = "\n".join(C.snapshot_readme_lines(
        {"status": {"obtained": True, "snapshot": "m04_gaps_X.json", "link_candidates": 1, "elements": 7,
                    "response_sha256": "ab" * 32, "timestamp_osm_base": "2026-10-31T13:14:07Z"}, "corridors": cor}, gap))  # fmt: skip
    assert "**Obtained:** `m04_gaps_X.json`" in present and "Candidate corridors identified: **1**" in present
    assert "never inferred from connectivity" in present and "restricted_by_mapped_tags" in present
    assert "not obtained" not in present and "No targeted snapshot present" not in present
    absent = "\n".join(C.snapshot_readme_lines(None, gap))
    assert "No targeted snapshot present" in absent


# --- access classification (tags) ------------------------------------------------------------------


# Labels describe the mapped tags, never the road class or a presumed user group (M04 methodology
# review). The pre-review labels resident_restricted / private_uncertain / ineligible / uncertain were
# replaced: they inferred residents from highway=service and called an explicit restriction uncertain.
@pytest.mark.parametrize(
    "tags, expected",
    [
        ({"highway": "residential"}, "untagged"),
        ({"access": "yes"}, "public"),
        ({"access": "permissive"}, "public"),
        ({"access": "no"}, "no"),
        ({"access": "no", "foot": "yes"}, "public"),  # the more specific pedestrian tag decides
        ({"access": "no", "foot": "designated"}, "public"),
        ({"access": "emergency", "foot": "yes"}, "public"),  # vehicle-category access, pedestrian override
        ({"highway": "residential", "access": "private"}, "private"),
        ({"highway": "service", "access": "private"}, "private"),
        ({"highway": "service", "service": "private"}, "private"),
        ({"highway": "tertiary", "access": "private"}, "private"),
        ({"highway": "footway", "access": "private"}, "private"),
        ({"barrier": "gate", "access": "private"}, "private"),
        ({"access": "residents"}, "residents"),
        ({"foot": "residents"}, "residents"),
        ({"foot": "private"}, "private"),
        ({"access": "yes", "foot": "private"}, "private"),
        ({"access": "no", "foot": "private"}, "private"),
        ({"foot": "no"}, "no"),
        ({"access": "private", "foot": "no"}, "no"),
        ({"access": "private", "foot": "yes"}, "pedestrian_override"),
        ({"access": "customers", "foot": "permissive"}, "pedestrian_override"),
        ({"access": "residents", "foot": "designated"}, "pedestrian_override"),
        ({"access": "destination"}, "destination"),
        ({"access": "delivery"}, "unknown"),  # a purpose/vehicle restriction, not a pedestrian destination
        ({"access": "customers"}, "customers"),
        ({"access": "permit"}, "unknown"),
        ({"foot": "use_sidepath"}, "unknown"),
    ],
)
def test_access_class(tags, expected):
    assert C.access_class(tags) == expected


def test_restricted_and_uncertain_are_never_silently_public():
    for tags in ({"access": "private"}, {"highway": "residential", "access": "private"}, {"access": "customers"},
                 {"access": "unknown"}, {"access": "no"}, {"foot": "private"}, {"access": "private", "foot": "yes"}):  # fmt: skip
        a = C.access_assessment(tags)
        assert a["public_pedestrian_status"] not in ("permitted_by_tag", "not_restricted_by_tags_unverified")


def test_access_classes_are_ordered_and_documented():
    from abot import access

    assert set(C.ACCESS_CLASSES) == set(C.POLICY) == set(access.PUBLIC_PEDESTRIAN)
    assert C.ACCESS_CLASSES[0] == "no" and C.ACCESS_CLASSES[-1] == "public"
    assert C.RESTRICTED == {"no", "private", "residents"} and C.CUSTOMERS_UNKNOWN == {"customers", "unknown"}
    assert not {"resident_restricted", "private_uncertain", "ineligible", "uncertain"} & set(C.ACCESS_CLASSES)


# 1. A private service road is not a residents' road.
def test_private_service_road_is_not_resident_only():
    a = C.access_assessment({"highway": "service", "access": "private"})
    assert a["mapped_access_status"] == "private" and a["authorized_group"] == "unspecified"
    assert a["public_pedestrian_status"] == "not_public" and a["field_verification_required"]
    assert (
        "resident" not in a["authorized_group"] and "names no authorised group" in a["classification_reason"]
    )
    res = C.access_assessment({"highway": "service", "access": "residents"})
    assert res["authorized_group"] == "residents_named_by_tag"


# 2. The road class never weakens (or changes) a mapped restriction.
@pytest.mark.parametrize(
    "hw", ["tertiary", "primary", "service", "residential", "footway", "living_street", None]
)
def test_highway_class_never_changes_the_status(hw):
    tags = {"access": "private"} | ({"highway": hw} if hw else {})
    a = C.access_assessment(tags)
    assert a["mapped_access_status"] == "private" and a["public_pedestrian_status"] == "not_public"
    if hw:
        assert f"highway={hw} recorded, not used" in a["classification_reason"]


# 4. A private gate is an access-control point, not evidence of public access.
def test_private_gate_is_not_public_and_needs_verification():
    a = C.access_assessment({"barrier": "gate", "access": "private", "locked": "yes"}, gate=True)
    assert a["mapped_access_status"] == "private" and a["public_pedestrian_status"] == "not_public"
    assert a["field_verification_required"] and "locked=yes" in a["classification_reason"]
    assert "operating rules" in a["classification_reason"]


def test_untagged_gate_is_unverified_not_public():
    a = C.access_assessment({"barrier": "gate"}, gate=True)
    assert a["mapped_access_status"] == "untagged"
    assert (
        a["public_pedestrian_status"] == "not_restricted_by_tags_unverified"
        and a["field_verification_required"]
    )


# 6. Missing tags are not explicit public access.
def test_missing_tags_stay_distinct_from_explicit_public():
    none = C.access_assessment({"highway": "service"})
    yes = C.access_assessment({"highway": "service", "access": "yes"})
    assert none["mapped_access_status"] == "untagged" and yes["mapped_access_status"] == "public"
    assert none["public_pedestrian_status"] != yes["public_pedestrian_status"]
    assert "not evidence of public access" in none["classification_reason"]


# 7. Pedestrian tags are handled separately from general access, and the override is recorded.
def test_foot_tag_decides_and_the_override_is_recorded():
    a = C.access_assessment({"access": "no", "foot": "yes"})
    assert a["mapped_access_status"] == "public" and a["deciding_tag"] == "foot=yes"
    assert "takes precedence over access=no" in a["classification_reason"]
    b = C.access_assessment({"access": "yes", "foot": "private"})
    assert b["mapped_access_status"] == "private" and b["deciding_tag"] == "foot=private"


def test_permissive_is_permitted_but_revocable():
    a = C.access_assessment({"access": "permissive"})
    assert (
        a["public_pedestrian_status"] == "permitted_by_tag"
        and "may be withdrawn" in a["classification_reason"]
    )


# 8. Conflicts are deterministic, transparent and flagged, never unrestricted public.
def test_conflicting_tags_are_flagged_and_order_independent():
    t1 = {"access": "private", "foot": "yes", "highway": "service"}
    t2 = dict(reversed(list(t1.items())))
    a = C.access_assessment(t1)
    assert a == C.access_assessment(t2)
    assert a["mapped_access_status"] == "pedestrian_override"
    assert a["public_pedestrian_status"] == "permitted_by_foot_tag_conflicting"
    assert a["field_verification_required"] and a["authorized_group"] == "unspecified"
    assert "conflict" in a["classification_reason"]


def test_component_class_comparison_is_exact():
    ref = pd.DataFrame({"fragment": ["main", "F001", "F002"], "component_class": ["main", "isolated_mapped_dead_end",
                        "small_fragment"], "n_nodes": [10, 4, 2], "gates_restricted": [3, 0, 0]})  # fmt: skip
    out = C.compare_component_classes(ref, ref.copy())
    assert out["identical"] and out["components_compared"] == 3
    changed = ref.copy()
    changed.loc[2, "component_class"] = "access_uncertain"
    with pytest.raises(RuntimeError, match="F002 component_class"):
        C.compare_component_classes(ref, changed)
    with pytest.raises(RuntimeError, match="component ids differ"):
        C.compare_component_classes(ref, ref.iloc[:2])
    gates = ref.copy()
    gates.loc[1, "gates_restricted"] = 1
    with pytest.raises(RuntimeError, match="F001 gates_restricted"):
        C.compare_component_classes(ref, gates)


# 10. The taxonomy labels edges; it never changes the graph it reads.
def test_edge_table_leaves_topology_untouched():
    G = _graph(MAIN | FRAG)
    G.graph["crs"] = "EPSG:32651"
    for i, (_u, _v, d) in enumerate(G.edges(data=True)):
        d["osmid"] = 100 + i // 2
    before = sorted((u, v, k, d["length"]) for u, v, k, d in G.edges(keys=True, data=True))
    ways = {100: {"id": 100, "nodes": [], "tags": {"highway": "tertiary", "access": "private"}}}
    et, gates = C.edge_table(G, ways, {})
    assert sorted((u, v, k, d["length"]) for u, v, k, d in G.edges(keys=True, data=True)) == before
    assert len(et) == G.number_of_edges() and gates.empty
    assert set(et.loc[et["osmids"].map(lambda x: x == [100]), "way_class"]) == {"private"}
    assert set(et["way_class"]) == {"private", "untagged"}


def test_gate_scenario_flags_follow_raw_tags_as_before():
    assert C.gate_tag_flags({"access": "private"}) == {"gate private"}
    assert C.gate_tag_flags({"foot": "private"}) == {"gate ineligible"}
    assert C.gate_tag_flags({"access": "no"}) == {"gate ineligible"}
    assert C.gate_tag_flags({}) == {"gate untagged"}
    assert C.gate_tag_flags({"access": "no", "foot": "yes"}) == set()
    assert C.gate_tag_flags({"access": "customers"}) == set()


def test_tag_flags_respect_foot_override():
    assert C.way_tag_flags({"access": "no"}) == {"access=no"}
    assert C.way_tag_flags({"access": "no", "foot": "designated"}) == set()
    assert C.way_tag_flags({"foot": "private"}) == {"foot=private"}
    assert C.way_tag_flags({"access": "no", "foot": "private"}) == {"foot=private"}


@pytest.mark.parametrize(
    "kw, expected",
    [
        ({"gap_crosses_water": "river"}, "separated_by_water"),
        ({"share_restricted": 0.6}, "restricted_access"),
        ({"gates_restricted": 1}, "access_uncertain"),
        ({"noexit_at_gap": True}, "isolated_mapped_dead_end"),
        ({"gap_to_main_m": 0.5}, "likely_geometry_error"),
        ({"length_km": 2.0}, "isolated_local_network"),
        ({}, "small_fragment"),
    ],
)
def test_component_class_order(kw, expected):
    row = {"fragment": "F001", "gap_crosses_water": "", "share_restricted": 0.0,
           "share_customers_uncertain": 0.0, "gates_restricted": 0, "noexit_at_gap": False,
           "gap_to_main_m": 10.9, "length_km": 0.1} | kw  # fmt: skip
    assert C.classify_component(row)[0] == expected


def test_restricted_components_are_not_retained():
    assert "restricted_access" not in C.ELIGIBLE_A2 | C.ELIGIBLE_A3
    assert "access_uncertain" in C.ELIGIBLE_A3 and "access_uncertain" not in C.ELIGIBLE_A2


# --- targeted Overpass query ---------------------------------------------------------------------

CORR = [{"label": "F001 gap", "coords": [(10.727562, 122.574629), (10.727615, 122.574545)]}]
BBOX = (10.717858, 122.568977, 10.728288, 122.578012)


def test_targeted_query_is_valid_and_has_no_access_filter():
    q = T.build_query(CORR, BBOX)
    assert T.validate_query(q, CORR, BBOX) == []
    assert '["access"!' not in q and 'way["man_made"="bridge"]' in q and 'way["bridge"]' in q
    assert "around:50,10.727562,122.574629" in q  # lat before lon


def test_targeted_query_validation_catches_swapped_coordinates():
    swapped = [{"label": "F001 gap", "coords": [(122.574629, 10.727562), (122.574545, 10.727615)]}]
    assert any("swapped" in p for p in T.validate_query(T.build_query(swapped, BBOX), swapped, BBOX))


def test_targeted_fetch_never_downloads_without_permission(monkeypatch):
    monkeypatch.setattr(T, "plan", lambda s: {"query": T.build_query(CORR, BBOX), "problems": []})
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("download attempted"))
    assert "query" in T.fetch(CFG, allow_download=False)


# --- archive and review preservation -------------------------------------------------------------


def _project(tmp_path) -> Settings:
    return Settings(deep_merge(CFG.raw, {"paths": {"data_dir": "data", "run_name": None}}), root=tmp_path)


def test_archive_copies_hashes_keeps_originals_and_detects_changes(tmp_path):
    from abot import audit

    s = _project(tmp_path)
    run = tmp_path / "data" / "processed" / "old_run"
    run.mkdir(parents=True)
    (run / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (run / "sub").mkdir()
    (run / "sub" / "b.json").write_text("{}", encoding="utf-8")
    rec = archive.copy_and_record(s, "hist_old", {"processed": run}, "test")
    assert set(rec["files"]) == {"processed/a.csv", "processed/sub/b.json"} and rec["originals_kept"]
    assert (run / "a.csv").exists()  # copied, not moved
    assert archive.verify(s, "hist_old") == {
        "files": 2,
        "archive_mismatch": [],
        "source_mismatch": [],
        "extra_in_archive": [],
    }
    a = audit.Audit(s, DEFAULT_CONFIG)
    a.check_archive()
    assert {f.check: f.status for f in a.findings}["hist_old"] == audit.PASS
    with pytest.raises(FileExistsError):
        archive.copy_and_record(s, "hist_old", {"processed": run}, "again")  # never overwritten
    (tmp_path / "data" / "archive" / "hist_old" / "processed" / "a.csv").write_text(
        "x\n2\n", encoding="utf-8"
    )
    assert archive.verify(s, "hist_old")["archive_mismatch"] == ["processed/a.csv"]


def _archived_run(tmp_path):
    s = _project(tmp_path)
    run = tmp_path / "data" / "processed" / "old_run"
    (run / "qa").mkdir(parents=True)
    (run / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (run / "qa" / "b.json").write_text("{}", encoding="utf-8")
    cfg = tmp_path / "old_run.yaml"
    cfg.write_text("paths: {}\n", encoding="utf-8")
    archive.copy_and_record(s, "hist_old", {"processed": run, "config": cfg}, "test")
    return s, run, cfg


def test_cleanup_removes_only_verified_originals_and_keeps_config(tmp_path):
    s, run, cfg = _archived_run(tmp_path)
    removed = archive.remove_verified_originals(s, "hist_old", ("processed",))
    assert sorted(removed) == ["data/processed/old_run/a.csv", "data/processed/old_run/qa/b.json"]
    assert not run.exists() and cfg.exists()  # experiment configuration preserved
    rec = json.loads((tmp_path / "data" / "archive" / "hist_old.sha256.json").read_text(encoding="utf-8"))
    assert rec["originals_kept"] is False and rec["originals_removed"]["files"] == sorted(removed)
    assert archive.verify(s, "hist_old")["archive_mismatch"] == []  # archive intact after removal


def test_cleanup_refuses_when_an_original_changed(tmp_path):
    s, run, _ = _archived_run(tmp_path)
    (run / "a.csv").write_text("x\n2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="nothing removed"):
        archive.remove_verified_originals(s, "hist_old", ("processed",))
    assert (run / "qa" / "b.json").exists()


def test_cleanup_refuses_when_the_archive_changed_or_unrecorded_files_exist(tmp_path):
    s, run, _ = _archived_run(tmp_path)
    (run / "new.csv").write_text("added later", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unrecorded"):
        archive.remove_verified_originals(s, "hist_old", ("processed",))
    (run / "new.csv").unlink()
    (tmp_path / "data" / "archive" / "hist_old" / "processed" / "a.csv").write_text(
        "tampered", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="not verified"):
        archive.remove_verified_originals(s, "hist_old", ("processed",))
    assert (run / "a.csv").exists()


def test_e7_archive_record_exists_and_names_the_superseded_run():
    rec_path = PROJECT_ROOT / "data" / "archive" / "hist_e7_buffer_3km_m02.sha256.json"
    if not rec_path.exists():
        pytest.skip("archive not present in this checkout")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    assert "config/e7_buffer_3km.yaml" in rec["files"]
    assert (PROJECT_ROOT / "config" / "experiments" / "e7_buffer_3km.yaml").exists()  # config never removed
    if not rec["originals_kept"]:  # M04 follow-up: originals removed after verification
        assert "config" not in rec["originals_removed"]["prefixes"]
        assert not (PROJECT_ROOT / "data" / "processed" / "e7_buffer_3km").exists()
    assert any(f.startswith("interim/") for f in rec["files"]) and any(
        f.startswith("processed/") for f in rec["files"]
    )


def test_facility_review_summary_preserves_reviewer_columns(tmp_path):
    s = _project(tmp_path)
    m03 = s.processed_dir / "review" / "m03"
    m03.mkdir(parents=True)
    pd.DataFrame(
        {
            "review_id": ["D10", "D13"], "flagged_fid": ["node/1", "way/2"], "related_fid": ["node/3", "way/4"],
            "flagged_name": ["BPI", "DBP"], "distance_m": [40.6, 4.0], "desk_assessment": ["uncertain", "same"],
            "effect_if_merged": ["x", "y"], "review_status": ["pending", "decided"],
            "reviewer_decision": [None, "same_keep_related"], "reviewer_notes": [None, "user note"],
        }
    ).to_csv(m03 / "duplicates_assessment.csv", index=False)  # fmt: skip
    out = C.facility_review_summary(s)
    assert out["review_status"].tolist() == ["pending", "decided"]
    assert (
        out.at[1, "reviewer_decision"] == "same_keep_related" and out.at[1, "reviewer_notes"] == "user note"
    )
    assert pd.isna(out.at[0, "reviewer_decision"]) and "404" in out.at[0, "evidence_still_needed"]


def test_facility_review_summary_uses_live_decisions_only_for_the_same_pair(tmp_path):
    s = _project(tmp_path)
    m03 = s.processed_dir / "review" / "m03"
    m03.mkdir(parents=True)
    base = {
        "review_id": ["D01", "D13"],
        "flagged_fid": ["node/1", "way/2"],
        "related_fid": ["node/3", "way/4"],
    }
    pd.DataFrame({**base, "flagged_name": ["PNB", "DBP"], "distance_m": [5.1, 4.0], "desk_assessment": ["d", "s"],
                  "effect_if_merged": ["x", "y"], "review_status": ["pending"] * 2, "reviewer_decision": [None] * 2,
                  "reviewer_notes": [None] * 2}).to_csv(m03 / "duplicates_assessment.csv", index=False)  # fmt: skip
    pd.DataFrame({**base, "related_fid": ["node/3", "way/999"], "review_status": ["reviewed", "reviewed"],
                  "reviewer_decision": ["distinct_keep_both", "likely_duplicate_not_merged"],
                  "reviewer_notes": ["", ""]}).to_csv(m03.parent / "possible_duplicates_review.csv", index=False)  # fmt: skip
    out = C.facility_review_summary(s).set_index("review_id")
    assert out.at["D01", "reviewer_decision"] == "distinct_keep_both"  # live decision, same pair
    assert out.at["D13", "review_status"] == "pending"  # live row names another record: not copied


def _dup_review(tmp_path):
    from abot import review

    s = _project(tmp_path)
    d = review.review_dir(s)
    d.mkdir(parents=True)
    pd.DataFrame(
        {
            "review_id": ["D01", "D13", "D10"],
            "flagged_fid": ["node/1", "way/1323158946", "node/12260361103"],
            "related_fid": ["node/2", "way/308681988", "node/5077872221"],
            "flagged_osm_tags": ['{"amenity": "bank"}', '{"name": "DBP"}', '{"name": "BPI"}'],
            "review_status": ["pending"] * 3, "reviewer_decision": [""] * 3, "reviewer_notes": [""] * 3,
        }
    ).to_csv(d / review.DUPLICATES_FILE, index=False)  # fmt: skip
    return s, review


DEC = {
    "D01": {"flagged_fid": "node/1", "related_fid": "node/2", "decision": "distinct_keep_both",
            "notes": "bank and ATM", "rationale": "different sub-types"},
    "D13": {"flagged_fid": "way/1323158946", "related_fid": "way/308681988",
            "decision": "likely_duplicate_not_merged", "notes": "no merge", "rationale": "polygon inside"},
}  # fmt: skip


def test_decisions_are_recorded_logged_and_leave_others_pending(tmp_path):
    s, review = _dup_review(tmp_path)
    review.record_duplicate_decisions(s, DEC, "test approval")
    df = pd.read_csv(review.review_dir(s) / review.DUPLICATES_FILE, dtype=str, keep_default_na=False)
    got = df.set_index("review_id")
    assert (
        got.at["D01", "reviewer_decision"] == "distinct_keep_both"
        and got.at["D01", "review_status"] == "reviewed"
    )
    assert got.at["D10", "review_status"] == "pending" and got.at["D10", "reviewer_decision"] == ""
    assert len(df) == 3 and got.at["D13", "flagged_osm_tags"] == '{"name": "DBP"}'  # nothing deleted
    log = pd.read_csv(review.review_dir(s) / review.DECISION_LOG, dtype=str, keep_default_na=False)
    assert list(log["review_id"]) == ["D01", "D13"] and set(log["before_review_status"]) == {"pending"}
    assert json.loads(log.loc[1, "original_row_json"])["flagged_fid"] == "way/1323158946"  # provenance


def test_decision_refused_when_osm_ids_differ_or_already_decided(tmp_path):
    s, review = _dup_review(tmp_path)
    bad = {"D13": {**DEC["D13"], "related_fid": "way/999"}}
    with pytest.raises(ValueError, match="not the approved records"):
        review.record_duplicate_decisions(s, {**DEC, **bad}, "x")
    df = pd.read_csv(review.review_dir(s) / review.DUPLICATES_FILE, dtype=str, keep_default_na=False)
    assert set(df["review_status"]) == {"pending"}  # all-or-nothing
    review.record_duplicate_decisions(s, DEC, "x")
    with pytest.raises(ValueError, match="already decided"):
        review.record_duplicate_decisions(s, {"D01": DEC["D01"]}, "x")


def test_decision_can_be_reverted_exactly(tmp_path):
    s, review = _dup_review(tmp_path)
    path = review.review_dir(s) / review.DUPLICATES_FILE
    before = pd.read_csv(path, dtype=str, keep_default_na=False)
    review.record_duplicate_decisions(s, DEC, "x")
    review.revert_duplicate_decision(s, "D13", "test")
    after = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert after.set_index("review_id").loc["D13"].equals(before.set_index("review_id").loc["D13"])
    log = pd.read_csv(review.review_dir(s) / review.DECISION_LOG, dtype=str, keep_default_na=False)
    assert list(log["action"]) == ["record", "record", "revert"]


def test_decision_is_not_carried_to_a_different_pair_on_rerun(tmp_path):
    from abot import review

    path = tmp_path / "r.csv"
    pd.DataFrame({"review_id": ["D01"], "flagged_fid": ["node/1"], "related_fid": ["node/2"],
                  "review_status": ["reviewed"], "reviewer_decision": ["distinct_keep_both"],
                  "reviewer_notes": [""]}).to_csv(path, index=False)  # fmt: skip
    same = review._keep_reviewer_columns(
        pd.DataFrame({"review_id": ["D01"], "flagged_fid": ["node/1"], "related_fid": ["node/2"]}),
        path, "review_id", match=("flagged_fid", "related_fid"),
    )  # fmt: skip
    assert same.at[0, "reviewer_decision"] == "distinct_keep_both"
    shifted = review._keep_reviewer_columns(
        pd.DataFrame({"review_id": ["D01"], "flagged_fid": ["node/7"], "related_fid": ["node/8"]}),
        path, "review_id", match=("flagged_fid", "related_fid"),
    )  # fmt: skip
    assert shifted.at[0, "review_status"] == "pending" and shifted.at[0, "reviewer_decision"] == ""


def test_audit_flags_an_experiment_built_with_another_configuration(tmp_path):
    from abot import audit, qa

    exp = tmp_path / "config" / "experiments"
    exp.mkdir(parents=True)
    path = exp / "sens.yaml"
    path.write_text(
        f"extends: {DEFAULT_CONFIG.as_posix()}\npaths:\n  data_dir: data\n  run_name: sens\n",
        encoding="utf-8",
    )
    es = Settings(read_config(path), root=tmp_path)
    es.ensure_dirs()
    qa.record_stage(es, "report")
    path.write_text(path.read_text(encoding="utf-8") + "osm:\n  boundary_buffer_m: 999\n", encoding="utf-8")
    a = audit.Audit(_project(tmp_path), DEFAULT_CONFIG, hashes=False)
    a.check_experiment_runs("staleness")
    got = {f.check: f for f in a.findings}["experiment: sens"]
    assert got.status == audit.WARN and "another configuration" in got.detail
