"""Offline unit tests for the pure logic (no downloads, no data/ directory needed)."""

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from abot.accessibility import time_to_nearest
from abot.osm import _query_tags, categorise
from abot.population import old_psgc_to_cod

CATEGORIES = {
    "pharmacy": {"amenity": ["pharmacy"]},
    "health": {"amenity": ["hospital", "clinic"], "healthcare": True},
    "education": {"amenity": ["school"]},
}
PRIORITY = ["pharmacy", "health", "education"]


@pytest.mark.parametrize(
    ("old", "cod"),
    [("PH063022001", "PH0603022001"), ("PH063022180", "PH0603022180"), ("PH133901001", "PH1303901001")],
)
def test_old_psgc_to_cod(old, cod):
    assert old_psgc_to_cod(old) == cod


def test_query_tags_merges_lists_and_any_value():
    tags = _query_tags(CATEGORIES)
    assert tags["amenity"] == ["clinic", "hospital", "pharmacy", "school"]
    assert tags["healthcare"] is True


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"amenity": "hospital"}, "health"),
        ({"healthcare": "laboratory"}, "health"),  # `true` = any value
        ({"amenity": "pharmacy", "healthcare": "pharmacy"}, "pharmacy"),  # priority wins
        ({"amenity": "school"}, "education"),
        ({"amenity": "bench"}, None),
        ({"amenity": np.nan, "healthcare": np.nan}, None),  # missing tags from a wide frame
    ],
)
def test_categorise(tags, expected):
    assert categorise(pd.Series(tags), CATEGORIES, PRIORITY) == expected


def _line_graph(one_way: bool) -> nx.MultiDiGraph:
    """A - B - C, 60 s per hop. If one_way, traffic flows only A -> B -> C."""
    G = nx.MultiDiGraph()
    for u, v in [("A", "B"), ("B", "C")]:
        G.add_edge(u, v, travel_time=60.0)
        if not one_way:
            G.add_edge(v, u, travel_time=60.0)
    return G


def test_time_to_nearest_includes_facility_offset():
    G = _line_graph(one_way=False)
    times = time_to_nearest(G.reverse(copy=True), np.array(["C"]), np.array([30.0]))
    assert times == {"C": 30.0, "B": 90.0, "A": 150.0}


def test_time_to_nearest_respects_one_way_streets():
    # Facility at C on a one-way A -> B -> C street: A and B can reach it, nothing flows back.
    G = _line_graph(one_way=True)
    times = time_to_nearest(G.reverse(copy=True), np.array(["A"]), np.array([0.0]))
    assert times == {"A": 0.0}  # B and C cannot drive back to A
    times = time_to_nearest(G.reverse(copy=True), np.array(["C"]), np.array([0.0]))
    assert times == {"C": 0.0, "B": 60.0, "A": 120.0}


def test_time_to_nearest_picks_closest_of_many_and_cleans_up():
    G = _line_graph(one_way=False)
    GR = G.reverse(copy=True)
    times = time_to_nearest(GR, np.array(["A", "C", "C"]), np.array([0.0, 50.0, 10.0]))
    assert times == {"A": 0.0, "B": 60.0, "C": 10.0}
    assert "__facilities__" not in GR  # virtual source removed
