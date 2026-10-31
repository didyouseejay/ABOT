"""Regression tests for Milestone 03: desk-validation rules (`abot validate`) and the regenerated
maxspeed sensitivity configuration. Offline; synthetic data, real configuration rules."""

import networkx as nx
import numpy as np
import pandas as pd
import pytest
import requests

from abot import accessibility as A
from abot import validation as V
from abot.config import DEFAULT_CONFIG, PROJECT_ROOT, Settings, read_config

CFG = Settings(read_config(DEFAULT_CONFIG))
EXP = PROJECT_ROOT / "config" / "experiments"


def _pair(**kw):
    row = {
        "flagged_subtype": "bank",
        "related_subtype": "bank",
        "flagged_category": "finance",
        "distance_m": 10.0,
        "tags_identical": False,
        "tag_differences": "brand: — | X",
        "polygon_overlap_of_smaller": np.nan,
        "osm_id_gap": 5_000_000,
        "flagged_inside_city": True,
        "flagged_barangay": "B1",
        "related_barangay": "B1",
    }
    row.update(kw)
    return row


# --- duplicate desk assessment --------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw, expected",
    [
        ({"related_subtype": "atm"}, "distinct"),  # a bank and its ATM are separate services
        ({"polygon_overlap_of_smaller": 1.0, "distance_m": 4}, "same_facility_confirmed_desk"),
        ({"tags_identical": True, "osm_id_gap": 1, "distance_m": 23}, "same_facility_confirmed_desk"),
        ({"tags_identical": True, "osm_id_gap": 333_500, "distance_m": 16}, "uncertain_likely_duplicate"),
        ({"distance_m": 19.5}, "uncertain_likely_duplicate"),
        ({"distance_m": 41}, "uncertain"),
    ],
)
def test_duplicate_desk_assessment_rules(kw, expected):
    assert V.assess_duplicate(_pair(**kw))[0] == expected


def test_distinct_subtypes_win_over_geometry():
    # Different sub-types are never called duplicates, even when the polygons coincide.
    row = _pair(related_subtype="atm", polygon_overlap_of_smaller=1.0, tags_identical=True, osm_id_gap=1)
    assert V.assess_duplicate(row)[0] == "distinct"


def test_merge_effect_names_both_barangays_when_they_differ():
    groups = CFG["indicator_groups"]
    same = V._effect(_pair(), groups)
    assert "n_finance and n_finance_bank over-count by 1 in B1" in same
    split = V._effect(_pair(related_barangay="B2"), groups)
    assert "city-wide" in split and "B1 and B2" in split
    assert (
        V._effect(
            _pair(flagged_category="pharmacy", flagged_subtype="pharmacy", related_subtype="pharmacy"), groups
        ).count("n_pharmacy")
        == 1
    )
    assert "outside the city" in V._effect(_pair(flagged_inside_city=False), groups)
    assert V._effect(_pair(related_subtype="atm"), groups).startswith("none")


# --- unconnected-cell diagnostics -----------------------------------------------------------------


@pytest.mark.parametrize(
    "row, expected",
    [
        (
            {
                "fragment_conn_status": A.OK,
                "centre_in_water_feature": "way/1 water_area water=pond",
                "conn_status": A.BLOCKED,
            },
            "osm_fragment_not_linked",
        ),
        (
            {
                "fragment_conn_status": A.BEYOND,
                "centre_in_water_feature": "way/1 water_area water=pond natural=water",
                "conn_status": A.BLOCKED,
            },
            "centre_in_pond_polygon",
        ),
        (
            {
                "fragment_conn_status": A.BEYOND,
                "centre_in_water_feature": "way/2 water_area water=river natural=water",
                "conn_status": A.BEYOND,
            },
            "centre_in_river_or_sea",
        ),
        (
            {"fragment_conn_status": A.BLOCKED, "centre_in_water_feature": np.nan, "conn_status": A.BLOCKED},
            "blocked_by_watercourse",
        ),
        (
            {"fragment_conn_status": A.BEYOND, "centre_in_water_feature": np.nan, "conn_status": A.BEYOND},
            "no_mapped_way_within_tolerance",
        ),
    ],
)
def test_cell_diagnostic_class_order(row, expected):
    assert V.classify_cell(row) == expected
    assert expected in V.CELL_CLASSES


def test_tolerance_sensitivity_is_cumulative_and_not_applied():
    cells = pd.DataFrame(
        {"pop": [10.0, 20.0, 30.0, 40.0], "connects_on_main_within_m": [300, 400, 500, np.nan]}
    )
    out = V.tolerance_sensitivity(cells, 250)
    assert out["max_connector_m"].tolist() == [250, 300, 400, 500]
    assert out["pop_connected_extra"].tolist() == [0.0, 10.0, 30.0, 60.0]
    assert out["pop_still_not_connected"].tolist() == [100.0, 90.0, 70.0, 40.0]
    assert (out["note"].str.contains("not applied")).all()


def test_fragment_ids_are_deterministic_and_main_is_largest():
    G = nx.MultiDiGraph()
    nx.add_path(G, [1, 2, 3, 4])  # main
    nx.add_path(G, [10, 11])
    nx.add_path(G, [7, 8])  # same size as 10-11, smaller node id -> F001
    main, frag = V.split_components(G)
    assert main == {1, 2, 3, 4}
    assert frag == {7: "F001", 8: "F001", 10: "F002", 11: "F002"}


def test_offline_guard_refuses_downloads_and_restores():
    original = requests.sessions.Session.request
    with V.offline(), pytest.raises(RuntimeError, match="never downloads"):
        requests.get("https://overpass-api.de/api/status")
    assert requests.sessions.Session.request is original


# --- regenerated sensitivity run ------------------------------------------------------------------


def test_maxspeed_sensitivity_differs_from_baseline_only_in_speed_policy():
    sens = Settings(read_config(EXP / "sens_maxspeed_override.yaml"))
    assert sens["accessibility"]["maxspeed_policy"] == "override"
    assert sens["osm"]["boundary_buffer_m"] == CFG["osm"]["boundary_buffer_m"]  # same 3 km baseline
    assert sens.run_name == "sens_maxspeed_override" and sens.processed_dir != CFG.processed_dir
    strip = lambda raw: {  # noqa: E731
        k: ({kk: vv for kk, vv in v.items() if kk != "maxspeed_policy"} if k == "accessibility" else v)
        for k, v in raw.items()
        if k != "paths"
    }
    assert strip(sens.raw) == strip(CFG.raw)


# --- audit: experiment-run freshness --------------------------------------------------------------


def test_audit_flags_stale_and_accepts_fresh_experiment_runs(tmp_path):
    from abot import audit, qa
    from abot.config import deep_merge

    exp = tmp_path / "config" / "experiments"
    exp.mkdir(parents=True)
    (tmp_path / "config" / "settings.yaml").write_text("", encoding="utf-8")
    for name in ("old_run", "new_run"):
        (exp / f"{name}.yaml").write_text(
            f"extends: {DEFAULT_CONFIG.as_posix()}\npaths:\n  data_dir: data\n  run_name: {name}\n",
            encoding="utf-8",
        )
    s = Settings(deep_merge(CFG.raw, {"paths": {"data_dir": "data", "run_name": None}}), root=tmp_path)
    old = Settings(read_config(exp / "old_run.yaml"), root=tmp_path)
    new = Settings(read_config(exp / "new_run.yaml"), root=tmp_path)
    old.ensure_dirs()  # outputs without run_meta.json: built before stage recording
    new.ensure_dirs()
    qa.record_stage(new, "report")  # report.py is not changed by the test: fresh
    a = audit.Audit(s, DEFAULT_CONFIG, hashes=False)
    a.check_experiment_runs("staleness")
    got = {f.check: f for f in a.findings}
    assert got["experiment: old_run"].status == audit.WARN and "archive" in got["experiment: old_run"].action
    assert got["experiment: new_run"].status == audit.PASS
