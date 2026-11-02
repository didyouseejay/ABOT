"""Milestone 03 spatial validation: desk evidence for the open manual-review items.

`abot validate` READS the run's outputs, the manual-review files and the cached Overpass responses,
and writes evidence tables to <processed>/review/m03/. It never downloads (a cache miss raises), never
writes outside that folder, and applies nothing: no record is merged or excluded, no cell is
connected, and the reviewer columns of the review files are copied, never changed. Every assessment
below is a *desk* assessment from mapped data; the decision stays with the reviewer.

Evidence produced:
  1. Duplicate pairs: polygon overlap for way/way pairs, OSM id gap (same editing session), tag
     identity and sub-type relation, with a rule-based desk assessment.
  2. Network fragments: the walk-network pieces dropped by the largest-component filter
     (osm.build_graph), rebuilt from the same cached Overpass response, with the gap from each piece
     to the main network and the water barriers that gap crosses.
  3. Unconnected cells: whether a dropped fragment lies within the connector tolerance (mapped ways
     exist but are not linked), pond/river polygon diagnostics, and a connector-tolerance
     sensitivity (how many cells a longer connector would reach; NOT applied).
  4. Disconnected facilities: which fragment each one sits on, whether that fragment is separated
     from the main network by water, and whether the extraction boundary cuts it.

Outputs (<processed>/review/m03/):
  duplicates_assessment.csv            one row per flagged pair, evidence + desk assessment
  unconnected_cells_diagnostics.csv    one row per unconnected cell, diagnostic class + evidence
  unconnected_diagnostics_by_barangay.csv
  pond_polygons.csv                    pond/fishpond polygons that contain an unconnected cell centre
  network_fragments.csv                dropped walk-network fragments near cells or facilities
  disconnected_facilities_diagnostics.csv
  connector_tolerance_sensitivity.csv
  connected_cells_nearer_to_fragment.csv  connected cells whose nearest mapped way is an unlinked fragment
  validation.gpkg, validation_map.html
  README.md
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path

import folium
import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import requests
import shapely
from shapely.geometry import LineString
from shapely.ops import nearest_points

from abot import accessibility as A
from abot import osm, review
from abot.compare import access_layer
from abot.config import Settings

log = logging.getLogger(__name__)

HALF_CELL_M = 46  # WorldPop 3 arc-second cells are ~92 m wide at Iloilo's latitude
TOLERANCE_STEPS_M = [300, 400, 500]  # connector-tolerance sensitivity (not applied)
SAME_SESSION_ID_GAP = 10  # consecutive OSM ids: created in one upload
CONTAINED_SHARE = 0.9  # smaller polygon at least this much inside the larger: one site mapped twice
LIKELY_DUPLICATE_M = 25

CELL_CLASSES = {
    "osm_fragment_not_linked": "mapped ways within tolerance, but not linked to the main network in OSM",
    "centre_in_pond_polygon": "cell centre inside a mapped pond/fishpond polygon",
    "centre_in_river_or_sea": "cell centre inside a mapped river or other water area",
    "blocked_by_watercourse": "every edge within tolerance lies across a mapped watercourse",
    "no_mapped_way_within_tolerance": "no mapped walkable way (linked or not) within tolerance",
}


def m03_dir(s: Settings) -> Path:
    return review.review_dir(s) / "m03"


@contextlib.contextmanager
def offline():
    """Refuse every HTTP request: validation must run from the Overpass cache only."""
    original = requests.sessions.Session.request

    def refuse(self, method, url, *args, **kwargs):
        raise RuntimeError(f"abot validate never downloads (cache miss: {url}); run `abot build` first")

    requests.sessions.Session.request = refuse
    try:
        yield
    finally:
        requests.sessions.Session.request = original


# --- 1. duplicate pairs ---------------------------------------------------------------------------


def _id_gap(a: str, b: str) -> float:
    (ta, ia), (tb, ib) = a.split("/"), b.split("/")
    return abs(int(ia) - int(ib)) if ta == tb else np.nan


def assess_duplicate(row: dict) -> tuple[str, str, str]:
    """Rule-based desk assessment of one flagged pair -> (assessment, reason, verification needed).

    Order: different sub-types are separate services; a polygon inside the other, or identical tags
    created in one upload, is one site mapped twice; same sub-type close together is a likely
    duplicate; anything else stays uncertain."""
    if row["flagged_subtype"] != row["related_subtype"]:
        return (
            "distinct",
            (
                f"different sub-types ({row['flagged_subtype']} / {row['related_subtype']}): a separate "
                "service at the same site, not the same facility mapped twice"
            ),
            "none for the indicators (an ATM is never a destination); optional street-level check",
        )
    overlap = row.get("polygon_overlap_of_smaller")
    if pd.notna(overlap) and overlap >= CONTAINED_SHARE:  # pyright: ignore[reportOptionalOperand]
        return (
            "same_facility_confirmed_desk",
            (
                f"{overlap:.0%} of the smaller polygon lies inside the other: one site mapped twice "
                "(e.g. a site outline and its building)"
            ),
            "choose which record to keep",
        )
    gap = row.get("osm_id_gap")
    if row["tags_identical"] and pd.notna(gap) and gap <= SAME_SESSION_ID_GAP:  # pyright: ignore[reportOptionalOperand]
        return (
            "same_facility_confirmed_desk",
            (
                f"identical tags and consecutive OSM ids (gap {gap:.0f}): created in one upload as parts "
                "of one facility"
            ),
            "choose which record to keep",
        )
    if row["distance_m"] <= LIKELY_DUPLICATE_M:
        return (
            "uncertain_likely_duplicate",
            f"same name and sub-type {row['distance_m']:.0f} m apart; tags "
            + ("identical" if row["tags_identical"] else f"differ ({row['tag_differences']})"),
            "imagery or street-level check: one branch/site or two? which position is current?",
        )
    return (
        "uncertain",
        (
            f"same name and sub-type but {row['distance_m']:.0f} m apart with differing tags "
            f"({row['tag_differences']}): two branches are plausible"
        ),
        "external verification (operator branch list or site visit)",
    )


def _effect(row: dict, groups: dict) -> str:
    if row["flagged_subtype"] != row["related_subtype"]:
        return "none: the records are counted in different sub-types"
    sub, cat = row["flagged_subtype"], row["flagged_category"]
    hit = [g for g, spec in groups.items() if sub in spec["subtypes"] and spec["category"] == cat]
    counts = " and ".join(dict.fromkeys([f"n_{cat}", *(f"n_{g}" for g in hit)]))
    a, b = str(row["flagged_barangay"]), str(row["related_barangay"])
    if not row["flagged_inside_city"]:
        where = "outside the city: no barangay count changes"
    elif a == b:
        where = f"{counts} over-count by 1 in {a}"
    else:
        where = f"{counts} over-count by 1 city-wide; the records fall in {a} and {b}, so the dropped record decides which barangay loses 1"
    return (
        f"if merged: {where}; nearest-facility times change by at most {row['distance_m']:.0f} m of walking"
    )


def duplicates_assessment(s: Settings) -> pd.DataFrame:
    path = review.review_dir(s) / "possible_duplicates_review.csv"
    dup = pd.read_csv(path, keep_default_na=False, na_values=[""])
    ways = {f for f in pd.concat([dup["flagged_fid"], dup["related_fid"]]) if f.startswith("way/")}
    polys = {}
    if ways:
        with offline():
            raw = osm.features_in_area(osm.study_area(s), osm._query_tags(s["facilities"]))
        raw["fid"] = raw["element"] + "/" + raw["id"].astype(str)
        raw = raw[raw["fid"].isin(ways) & raw.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(
            s.projected_crs
        )
        polys = dict(zip(raw["fid"], raw.geometry, strict=True))

    rows = []
    for _, r in dup.iterrows():
        row = r.to_dict()
        row["tags_identical"] = str(row["tags_identical"]).lower() == "true"
        row["flagged_inside_city"] = str(row["flagged_inside_city"]).lower() == "true"
        a, b = polys.get(r["flagged_fid"]), polys.get(r["related_fid"])
        overlap = np.nan
        if a is not None and b is not None:
            small = a if a.area <= b.area else b
            overlap = round(a.intersection(b).area / small.area, 2)
        row["polygon_overlap_of_smaller"] = overlap
        row["osm_id_gap"] = _id_gap(r["flagged_fid"], r["related_fid"])
        row["desk_assessment"], row["desk_reason"], row["verification_needed"] = assess_duplicate(row)
        row["effect_if_merged"] = _effect(row, s["indicator_groups"])
        rows.append(row)
    out = pd.DataFrame(rows)
    out["osm_id_gap"] = out["osm_id_gap"].astype("Int64")
    cols = [
        "review_id", "flagged_fid", "related_fid", "flagged_name", "flagged_subtype", "related_subtype",
        "flagged_barangay", "related_barangay", "distance_m", "tags_identical", "tag_differences",
        "polygon_overlap_of_smaller", "osm_id_gap", "desk_assessment", "desk_reason",
        "verification_needed", "effect_if_merged", *review.REVIEW_COLUMNS,
    ]  # fmt: skip
    return out[cols]


# --- 2. network fragments -----------------------------------------------------------------------


def walk_graph_all(s: Settings) -> nx.MultiDiGraph:
    """The unfiltered walk graph (all components), projected, from the cached Overpass response."""
    osm._configure_osmnx(s)
    with offline():
        G = ox.graph_from_polygon(osm.study_area(s), network_type="walk", simplify=True, retain_all=True)
    return ox.projection.project_graph(G, to_crs=s.projected_crs)


def split_components(G_all: nx.MultiDiGraph) -> tuple[set, dict]:
    """Main (largest weakly connected) component and a fragment id (F001, ...) for every other node.
    Ordered by size, then smallest node id, so ids do not depend on set iteration order."""
    comps = sorted(nx.weakly_connected_components(G_all), key=lambda c: (-len(c), min(c)))
    frag = {n: f"F{i:03d}" for i, c in enumerate(comps[1:], start=1) for n in c}
    return comps[0], frag


def _label(v) -> str:
    return ";".join(sorted(map(str, v))) if isinstance(v, list) else ("" if v is None or v != v else str(v))


def fragments_table(
    s: Settings, G_all, frag: dict, main_edges: gpd.GeoDataFrame, bar: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """One row per fragment (dissolved edges) and the shortest gap line from it to the main network."""
    e = ox.convert.graph_to_gdfs(G_all, nodes=False).reset_index()
    e["fragment"] = e["u"].map(frag)
    e = e[e["fragment"].notna()].copy()
    for c in ("highway", "name", "osmid"):
        e[c] = e[c].map(_label) if c in e else ""
    city = gpd.read_file(s.gpkg, layer="city").to_crs(s.projected_crs).union_all()
    edge_of_extraction = city.buffer(s["osm"]["boundary_buffer_m"]).boundary
    hard = bar[bar["kind"].isin(["water_area", "water_line"])].reset_index(drop=True)
    htree = shapely.STRtree(hard.geometry.values)
    mtree = shapely.STRtree(main_edges.geometry.values)

    rows, gaps = [], []
    for fid, g in e.groupby("fragment", sort=True):
        geom = g.geometry.union_all()
        i = int(mtree.query_nearest(geom)[0])
        p, q = nearest_points(geom, main_edges.geometry.iloc[i])
        gap = LineString([p, q])
        crossed = [review._barrier_label(hard.iloc[j]) for j in htree.query(gap, predicate="intersects")]
        n_coast = sum("coastline" in c for c in crossed)
        pq = gpd.GeoSeries([p, q], crs=s.projected_crs).to_crs(4326)
        rows.append(
            {
                "fragment": fid,
                "n_edges": len(g),
                "length_km": round(g["length"].sum() / 1000 / 2, 2),  # two directed edges per way
                "km_inside_city": round(geom.intersection(city).length / 1000, 2),
                "highway_types": "; ".join(f"{k} {v}" for k, v in g["highway"].value_counts().items()),
                "names": "; ".join(sorted({n for n in g["name"] if n}))[:200],
                "osm_way_ids": ";".join(sorted({w for o in g["osmid"] for w in o.split(";") if w}, key=int)),
                "gap_to_main_m": round(gap.length, 1),
                "gap_from_lon": round(pq.iloc[0].x, 6),
                "gap_from_lat": round(pq.iloc[0].y, 6),
                "gap_to_lon": round(pq.iloc[1].x, 6),
                "gap_to_lat": round(pq.iloc[1].y, 6),
                "gap_main_edge": f"{_label(main_edges['highway'].iloc[i])} '{_label(main_edges['name'].iloc[i])}'",
                "gap_crosses_water": "; ".join(crossed),
                "gap_coastline_crossings": n_coast,
                "touches_extraction_edge": bool(geom.distance(edge_of_extraction) < 50),
                "geometry": geom,
            }
        )
        gaps.append({"fragment": fid, "gap_to_main_m": round(gap.length, 1), "geometry": gap})
    return (
        gpd.GeoDataFrame(rows, crs=s.projected_crs),
        gpd.GeoDataFrame(gaps, crs=s.projected_crs),
    )


# --- 3. unconnected cells -----------------------------------------------------------------------


def classify_cell(row: dict) -> str:
    """Diagnostic class of one unconnected cell (first match wins, see CELL_CLASSES)."""
    if row.get("fragment_conn_status") == A.OK:
        return "osm_fragment_not_linked"
    water = row.get("centre_in_water_feature")
    if isinstance(water, str) and water:
        return (
            "centre_in_pond_polygon" if any(k in water for k in review.FISHPOND) else "centre_in_river_or_sea"
        )
    if row["conn_status"] == A.BLOCKED:
        return "blocked_by_watercourse"
    return "no_mapped_way_within_tolerance"


def _verification(row: dict) -> str:
    c = row["diagnostic_class"]
    if c == "osm_fragment_not_linked":
        return (
            f"OSM gap of {row['fragment_gap_to_main_m']:.0f} m between fragment {row['fragment']} and the "
            "main network: check on imagery/site whether a link exists (gate, private access, unmapped "
            "lane or footbridge)"
        )
    if c == "centre_in_pond_polygon":
        return (
            "imagery: is the pond still a pond at this cell, or are there dwellings/dikes? then local check"
        )
    if c == "centre_in_river_or_sea":
        return "imagery/site: houses over water (stilts) with boardwalks, or a misplaced population cell?"
    if c == "blocked_by_watercourse":
        return "site/local: is there a footbridge or crossing over the blocking watercourse?"
    return "imagery then local check: unmapped lanes/paths, or no dwellings (misplaced population)?"


def unconnected_diagnostics(
    s: Settings, G_all, main: set, frag: dict, frags: gpd.GeoDataFrame, bar: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    cfg = s["accessibility"]["connection"]
    path = review.review_dir(s) / "unconnected_cells_review.csv"
    u = pd.read_csv(path, keep_default_na=False, na_values=[""], dtype={"adm4_pcode": str})
    cells = gpd.GeoDataFrame(u, geometry=gpd.points_from_xy(u["lon"], u["lat"]), crs=4326).to_crs(
        s.projected_crs
    )
    barriers = A.BarrierChecker(bar, cfg["water_crossing_tolerance_m"])

    # (a) is a dropped fragment within the origin tolerance, by a barrier-free connector?
    G_frag = G_all.subgraph([n for n in G_all.nodes if n not in main])
    fidx = A.EdgeIndex(G_frag)
    fc = A.connect_points(cells.geometry, fidx, barriers, cfg, cfg["origin_radius_m"])
    cells["fragment_conn_status"] = fc["status"].values
    cells["fragment_nearest_m"] = fc["nearest_m"].round(1).values
    cells["fragment"] = [
        frag.get(u_) if st == A.OK else None for u_, st in zip(fc["u"], fc["status"], strict=True)
    ]
    gap = frags.set_index("fragment")["gap_to_main_m"]
    cells["fragment_gap_to_main_m"] = cells["fragment"].map(gap)

    # (b) water coverage of the cell footprint
    water = bar[bar["kind"] == "water_area"].union_all()
    sq = cells.geometry.buffer(HALF_CELL_M, cap_style="square")
    cells["cell_water_share"] = (sq.intersection(water).area / sq.area).round(2)

    # (c) connector-tolerance sensitivity on the main network (not applied to any indicator)
    G_main = G_all.subgraph(main)
    midx = A.EdgeIndex(G_main)
    reach = pd.Series(np.nan, index=cells.index)
    for m in TOLERANCE_STEPS_M:
        todo = reach.isna()
        st = A.connect_points(cells.geometry[todo], midx, barriers, cfg, cfg["origin_radius_m"], max_m=m)
        reach[st.index[st["status"] == A.OK]] = m
    cells["connects_on_main_within_m"] = reach

    rows = cells.to_dict("records")
    cells["diagnostic_class"] = [classify_cell(r) for r in rows]
    cells["verification_needed"] = [
        _verification({**r, "diagnostic_class": c})
        for r, c in zip(rows, cells["diagnostic_class"], strict=True)
    ]
    cells = cells.sort_values(["priority_barangay", "pop"], ascending=[False, False]).reset_index(drop=True)
    cells["decision_rank"] = np.arange(1, len(cells) + 1)

    by = (
        cells.groupby(["barangay", "diagnostic_class"])
        .agg(cells=("cell_id", "size"), pop=("pop", "sum"))
        .round(1)
        .reset_index()
    )
    summary = by.pivot_table(index="barangay", columns="diagnostic_class", values="pop", fill_value=0)
    summary["pop_total"] = summary.sum(axis=1)
    summary["cells"] = cells.groupby("barangay").size()
    summary["priority_barangay"] = cells.groupby("barangay")["priority_barangay"].first()
    summary = summary.sort_values(["priority_barangay", "pop_total"], ascending=False).round(1).reset_index()
    return cells, summary


def connected_near_fragments(s: Settings, frags: gpd.GeoDataFrame) -> pd.DataFrame:
    """Connected cells whose nearest mapped way is an unlinked fragment: they were attached by a longer
    straight connector to the main network, so their times rest on that approximation."""
    cells = gpd.read_file(s.gpkg, layer=access_layer(s.gpkg))
    c = cells[cells["conn_status"] == A.OK]
    idx, dist = shapely.STRtree(frags.geometry.values).query_nearest(c.geometry.values, return_distance=True)
    out = pd.DataFrame(
        {
            "cell_id": c["cell_id"].values[idx[0]],
            "pop": c["pop"].values[idx[0]].round(1),
            "connector_to_main_m": c["conn_m"].values[idx[0]].round(1),
            "fragment": frags["fragment"].values[idx[1]],
            "fragment_m": dist.round(1),
        }
    ).drop_duplicates("cell_id")
    return out[out["fragment_m"] < out["connector_to_main_m"]].sort_values("pop", ascending=False)


def pond_polygons(s: Settings, cells: gpd.GeoDataFrame, bar: gpd.GeoDataFrame, G_all) -> gpd.GeoDataFrame:
    """Pond polygons containing an unconnected cell centre, with internal consistency evidence:
    a mapped walkable way inside a 'pond' would contradict the polygon (none means no contradiction,
    not confirmation)."""
    pc = cells[cells["diagnostic_class"] == "centre_in_pond_polygon"].copy()
    pc["pond"] = pc["centre_in_water_feature"].str.extract(r"^(\w+/\d+)")[0]
    bar = bar.set_index(bar["osm_type"] + "/" + bar["osm_id"].astype(str))
    edges = ox.convert.graph_to_gdfs(G_all, nodes=False).reset_index()
    etree = shapely.STRtree(edges.geometry.values)
    rows = []
    for fid, g in pc.groupby("pond"):
        poly = bar.loc[fid].geometry
        inner = poly.buffer(-5)
        hit = etree.query(inner, predicate="intersects")
        rows.append(
            {
                "pond": fid,
                "tags": review._barrier_label(bar.loc[fid]),
                "area_ha": round(poly.area / 1e4, 2),
                "cells": len(g),
                "pop": round(g["pop"].sum(), 1),
                "barangays": "; ".join(sorted(g["barangay"].unique())),
                "mean_cell_water_share": round(g["cell_water_share"].mean(), 2),
                "walkable_ways_inside": len(hit),
                "internal_evidence": "contradicted: mapped way inside the polygon"
                if len(hit)
                else "no contradiction in OSM data (imagery not checked)",
                "geometry": poly,
            }
        )
    return gpd.GeoDataFrame(rows, crs=s.projected_crs).sort_values("pop", ascending=False)


def tolerance_sensitivity(cells: gpd.GeoDataFrame, base_m: float) -> pd.DataFrame:
    rows = [{"max_connector_m": base_m, "cells_connected_extra": 0, "pop_connected_extra": 0.0}]
    for m in TOLERANCE_STEPS_M:
        hit = cells["connects_on_main_within_m"] <= m
        rows.append(
            {
                "max_connector_m": m,
                "cells_connected_extra": int(hit.sum()),
                "pop_connected_extra": round(float(cells.loc[hit, "pop"].sum()), 1),
            }
        )
    out = pd.DataFrame(rows)
    out["pop_still_not_connected"] = (cells["pop"].sum() - out["pop_connected_extra"]).round(1)
    out["note"] = "sensitivity only: not applied to any indicator"
    return out


# --- 4. disconnected facilities -----------------------------------------------------------------


def facility_diagnostics(
    s: Settings, G_all, main: set, frag: dict, frags: gpd.GeoDataFrame, bar: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    cfg = s["accessibility"]["connection"]
    fac = gpd.read_file(s.gpkg, layer="facilities")
    bad = fac[fac["conn_status"] != A.OK].copy()
    barriers = A.BarrierChecker(bar, cfg["water_crossing_tolerance_m"])
    fidx = A.EdgeIndex(G_all.subgraph([n for n in G_all.nodes if n not in main]))
    fc = A.connect_points(
        bad.geometry, fidx, barriers, cfg, cfg["facility_radius_m"], cfg["facility_max_connector_m"]
    )
    bad["fragment"] = [
        frag.get(u) if st == A.OK else None for u, st in zip(fc["u"], fc["status"], strict=True)
    ]
    bad["fragment_connector_m"] = fc["conn_m"].round(1).values
    F = frags.set_index("fragment")
    for c in (
        "length_km",
        "gap_to_main_m",
        "gap_coastline_crossings",
        "gap_crosses_water",
        "touches_extraction_edge",
    ):
        bad[f"fragment_{c}"] = bad["fragment"].map(F[c])
    water = bar[bar["kind"] == "water_area"]
    bad["point_in_water_area"] = bad.geometry.apply(lambda p: bool(water.contains(p).any()))
    city = gpd.read_file(s.gpkg, layer="city").to_crs(s.projected_crs).union_all()
    bad["distance_to_city_m"] = bad.distance(city).round(0)
    edge = city.buffer(s["osm"]["boundary_buffer_m"]).boundary
    bad["distance_to_extraction_edge_m"] = bad.distance(edge).round(0)
    groups = s["indicator_groups"]
    bad["would_be_destination"] = [
        any(r.category == g["category"] and r.subtype in g["subtypes"] for g in groups.values())
        for r in bad.itertuples()
    ]

    def diagnose(r) -> str:
        if r["point_in_water_area"]:
            return "check_coordinates: point lies in a mapped water area"
        if not isinstance(r["fragment"], str):
            return "no_mapped_way: no walkable way of any component within the facility tolerance"
        if r["fragment_gap_coastline_crossings"] >= 2 or (
            r["fragment_gap_crosses_water"] and r["fragment_gap_to_main_m"] > cfg["facility_max_connector_m"]
        ):
            return "separated_by_water: on a local road network with no land link to the main network"
        return "fragment_not_linked: on a mapped network piece that OSM does not link to the main network"

    bad["diagnosis"] = bad.apply(diagnose, axis=1)
    b4 = bad.to_crs(4326).geometry
    bad["lon"], bad["lat"] = b4.x.round(6), b4.y.round(6)
    keep = [
        "fid_key", "name", "category", "subtype", "tier", "would_be_destination", "inside_city",
        "conn_status", "nearest_edge_m", "fragment", "fragment_connector_m", "fragment_length_km",
        "fragment_gap_to_main_m", "fragment_gap_coastline_crossings", "fragment_gap_crosses_water",
        "fragment_touches_extraction_edge", "point_in_water_area", "distance_to_city_m",
        "distance_to_extraction_edge_m", "diagnosis", "lon", "lat", "geometry",
    ]  # fmt: skip
    return bad[keep].reset_index(drop=True)


# --- map and README -----------------------------------------------------------------------------

CLASS_COLOURS = {
    "osm_fragment_not_linked": "#d95f02",
    "centre_in_pond_polygon": "#1f78b4",
    "centre_in_river_or_sea": "#a6cee3",
    "blocked_by_watercourse": "#7570b3",
    "no_mapped_way_within_tolerance": "#e7298a",
}
DUP_COLOURS = {
    "same_facility_confirmed_desk": "#d7191c",
    "uncertain_likely_duplicate": "#fdae61",
    "uncertain": "#ffff33",
    "distinct": "#1a9641",
}


def validation_map(s, cells, frags, gaps, ponds, facs, dup_pairs, path: Path) -> None:
    c4 = cells.to_crs(4326)
    m = review._base_map(c4)
    folium.GeoJson(
        ponds.to_crs(4326)[["pond", "pop", "internal_evidence", "geometry"]],
        name="Pond polygons with unconnected cells",
        style_function=lambda _: {"color": "#08519c", "weight": 1, "fillOpacity": 0.25},
        tooltip=folium.GeoJsonTooltip(["pond", "pop", "internal_evidence"]),
    ).add_to(m)
    folium.GeoJson(
        frags.to_crs(4326)[["fragment", "length_km", "highway_types", "names", "gap_to_main_m", "geometry"]],
        name="Walk-network fragments (dropped: not linked)",
        style_function=lambda _: {"color": "#d95f02", "weight": 3},
        tooltip=folium.GeoJsonTooltip(["fragment", "length_km", "highway_types", "names", "gap_to_main_m"]),
    ).add_to(m)
    folium.GeoJson(
        gaps.to_crs(4326),
        name="Gap from fragment to main network",
        style_function=lambda _: {"color": "#000000", "weight": 2, "dashArray": "4 4"},
        tooltip=folium.GeoJsonTooltip(["fragment", "gap_to_main_m"]),
    ).add_to(m)
    show = [
        "cell_id",
        "barangay",
        "pop",
        "conn_status",
        "diagnostic_class",
        "fragment",
        "connects_on_main_within_m",
    ]
    for cls, colour in CLASS_COLOURS.items():
        sub = c4[c4["diagnostic_class"] == cls]
        if sub.empty:
            continue
        fg = folium.FeatureGroup(name=f"Cells: {cls} ({len(sub)})")
        for r in sub.itertuples():
            folium.CircleMarker(
                [r.geometry.y, r.geometry.x],
                radius=3 + min(float(r.pop), 150) ** 0.5,
                color=colour,
                fill=True,
                fill_opacity=0.8,
                weight=1,
                tooltip="<br>".join(f"{k}: {getattr(r, k)}" for k in show),
            ).add_to(fg)
        fg.add_to(m)
    fg = folium.FeatureGroup(name=f"Disconnected facilities ({len(facs)})")
    for r in facs.to_crs(4326).itertuples():
        folium.Marker(
            [r.geometry.y, r.geometry.x],
            icon=folium.Icon(color="red" if r.would_be_destination else "gray", icon="info-sign"),
            tooltip=f"{r.name} ({r.subtype}, {r.tier})<br>{r.diagnosis}",
        ).add_to(fg)
    fg.add_to(m)
    fg = folium.FeatureGroup(name="Duplicate pairs (desk assessment)")
    for r in dup_pairs.to_crs(4326).itertuples():
        colour = DUP_COLOURS[r.desk_assessment]
        folium.PolyLine(
            [(y, x) for x, y in r.geometry.coords],
            color=colour,
            weight=6,
            tooltip=f"{r.review_id}: {r.desk_assessment}",
        ).add_to(fg)
        for x, y in r.geometry.coords:
            folium.CircleMarker(
                [y, x], radius=5, color=colour, fill=True, tooltip=f"{r.review_id} {r.flagged_name}"
            ).add_to(fg)
    fg.add_to(m)
    legend = (
        '<div style="position:fixed;top:10px;left:50px;z-index:9999;background:white;padding:6px 8px;'
        'font:12px sans-serif;border:1px solid #888;max-width:340px"><b>ABOT Milestone 03 validation</b><br>'
        + "".join(f'<span style="color:{c}">&#9679;</span> {k}<br>' for k, c in CLASS_COLOURS.items())
        + "Dashed: shortest gap from a dropped fragment to the main network.<br>"
        "Desk evidence only; nothing here is applied.</div>"
    )
    m.get_root().html.add_child(folium.Element(legend))  # pyright: ignore[reportAttributeAccessIssue]  (get_root() is the Figure)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(path))


def write_readme(path: Path, dup: pd.DataFrame, cells, facs, sens, ponds, near, qa_info: dict) -> None:
    a = dup["desk_assessment"].value_counts()
    k = cells.groupby("diagnostic_class")["pop"].agg(["size", "sum"]).round(1)
    lines = [
        "# Milestone 03 validation evidence (generated by `abot validate`; nothing here has been applied)",
        "",
        "Desk evidence from mapped data for the open review items. Reviewer columns are copied from the",
        "review files unchanged; every decision is still **pending**. No record was merged or excluded and",
        "no cell or facility was connected. Imagery was not inspected by the tool.",
        "",
        (
            f"- Walk graph rebuilt from the Overpass cache: {qa_info['components']} components; main "
            f"component {qa_info['main_nodes']} nodes "
            f"({'matches' if qa_info['matches_saved'] else 'DOES NOT match'} the saved graph)."
        ),
        "",
        "## Duplicate pairs (`duplicates_assessment.csv`)",
        "",
        "| Desk assessment | Pairs |",
        "|---|---|",
        *[
            f"| {k_} | {a.get(k_, 0)}: {', '.join(dup.loc[dup.desk_assessment == k_, 'review_id'])} |"
            for k_ in DUP_COLOURS
        ],
        "",
        "## Unconnected cells (`unconnected_cells_diagnostics.csv`)",
        "",
        "| Diagnostic class | Cells | Residents | Meaning |",
        "|---|---|---|---|",
        *[
            f"| {c} | {int(k.loc[c, 'size']) if c in k.index else 0} | {k.loc[c, 'sum'] if c in k.index else 0} | {d} |"
            for c, d in CELL_CLASSES.items()
        ],
        "",
        (
            f"Pond polygons containing an unconnected cell centre: {len(ponds)} (`pond_polygons.csv`); "
            f"with a mapped way inside: {int((ponds['walkable_ways_inside'] > 0).sum())}."
        ),
        "",
        "Connector-tolerance sensitivity (`connector_tolerance_sensitivity.csv`, not applied):",
        "",
        "| Max connector (m) | Extra cells | Extra residents |",
        "|---|---|---|",
        *[
            f"| {r.max_connector_m} | {r.cells_connected_extra} | {r.pop_connected_extra} |"
            for r in sens.itertuples()
        ],
        "",
        f"Connected cells whose nearest mapped way is an unlinked fragment "
        f"(`connected_cells_nearer_to_fragment.csv`): {len(near)} cells, {near['pop'].sum():,.1f} residents; "
        f"they reach the main network by a longer straight connector (median "
        f"{near['connector_to_main_m'].median():.0f} m). Largest: "
        + ", ".join(f"{k} {v:,.0f}" for k, v in near.groupby("fragment")["pop"].sum().nlargest(3).items())
        + ".",
        "",
        "## Disconnected facilities (`disconnected_facilities_diagnostics.csv`)",
        "",
        "| Diagnosis | Facilities |",
        "|---|---|",
        *[f"| {d.split(':')[0]} | {n} |" for d, n in facs["diagnosis"].value_counts().items()],
        "",
        "`validation_map.html` shows all layers over OpenStreetMap or Esri imagery.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(s: Settings) -> None:
    out = m03_dir(s)
    out.mkdir(parents=True, exist_ok=True)
    gpkg = out / "validation.gpkg"
    if gpkg.exists():
        gpkg.unlink()  # derived file, fully rewritten

    bar = gpd.read_file(s.gpkg, layer="barriers")
    G_all = walk_graph_all(s)
    main, frag = split_components(G_all)
    saved = osm.load_graph(s, "walk")
    qa_info = {
        "components": len(set(frag.values())) + 1,
        "main_nodes": len(main),
        "matches_saved": set(saved.nodes) == main,
    }
    if not qa_info["matches_saved"]:
        log.warning("rebuilt main walk component differs from the saved graph: rebuild the OSM stage")
    main_edges = review._edges_gdf(s)

    dup = duplicates_assessment(s)
    dup.to_csv(out / "duplicates_assessment.csv", index=False)
    pairs = gpd.read_file(review.review_dir(s) / "review.gpkg", layer="duplicate_pairs")
    pairs = pairs[["review_id", "flagged_name", "geometry"]].merge(
        dup[["review_id", "desk_assessment"]], on="review_id"
    )

    frags, gaps = fragments_table(s, G_all, frag, main_edges, bar)
    cells, by_brgy = unconnected_diagnostics(s, G_all, main, frag, frags, bar)
    facs = facility_diagnostics(s, G_all, main, frag, frags, bar)
    ponds = pond_polygons(s, cells, bar, G_all)
    sens = tolerance_sensitivity(cells, s["accessibility"]["connection"]["max_connector_m"])
    near = connected_near_fragments(s, frags)
    near.to_csv(out / "connected_cells_nearer_to_fragment.csv", index=False)

    relevant = set(cells["fragment"].dropna()) | set(facs["fragment"].dropna())
    frags_rel = frags[frags["fragment"].isin(relevant)]
    gaps_rel = gaps[gaps["fragment"].isin(relevant)]
    pd.DataFrame(cells.drop(columns="geometry")).to_csv(
        out / "unconnected_cells_diagnostics.csv", index=False
    )
    by_brgy.to_csv(out / "unconnected_diagnostics_by_barangay.csv", index=False)
    pd.DataFrame(ponds.drop(columns="geometry")).to_csv(out / "pond_polygons.csv", index=False)
    pd.DataFrame(frags_rel.drop(columns="geometry")).to_csv(out / "network_fragments.csv", index=False)
    pd.DataFrame(facs.drop(columns="geometry")).to_csv(
        out / "disconnected_facilities_diagnostics.csv", index=False
    )
    sens.to_csv(out / "connector_tolerance_sensitivity.csv", index=False)

    cells.to_file(gpkg, layer="unconnected_cells", driver="GPKG")
    frags_rel.to_file(gpkg, layer="network_fragments", driver="GPKG")
    gaps_rel.to_file(gpkg, layer="fragment_gaps", driver="GPKG")
    ponds.to_file(gpkg, layer="pond_polygons", driver="GPKG")
    facs.to_file(gpkg, layer="disconnected_facilities", driver="GPKG")
    pairs.to_file(gpkg, layer="duplicate_pairs", driver="GPKG")
    validation_map(s, cells, frags_rel, gaps_rel, ponds, facs, pairs, out / "validation_map.html")
    write_readme(out / "README.md", dup, cells, facs, sens, ponds, near, qa_info)
    (out / "run_info.json").write_text(
        json.dumps({"config_sha256": s.config_sha256, **qa_info}, indent=2), encoding="utf-8"
    )
    log.info("validation evidence written to %s", out)
