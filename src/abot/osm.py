"""OpenStreetMap road networks (walk, drive) and categorised public facilities.

Both are fetched for the city boundary plus a buffer so that trips and facilities just
across the city limit are not cut off. Raw Overpass responses are cached under
data/raw/osm_cache (ODbL 1.0 — attribution required).
"""

from __future__ import annotations

import logging

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

from abot import boundaries, qa
from abot.config import Settings

log = logging.getLogger(__name__)

TAG_COLUMNS = ["amenity", "healthcare", "shop", "office", "emergency", "social_facility"]


def _configure_osmnx(s: Settings) -> None:
    ox.settings.cache_folder = str(s.raw_dir / "osm_cache")
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.requests_timeout = 300


def study_area(s: Settings):
    """City polygon buffered by `boundary_buffer_m`, returned in EPSG:4326 for Overpass."""
    city, _ = boundaries.load(s)
    buffered = city.buffer(s["osm"]["boundary_buffer_m"]).union_all()
    return gpd.GeoSeries([buffered], crs=city.crs).to_crs(4326).iloc[0]


def graph_path(s: Settings, mode: str):
    return s.interim_dir / f"graph_{mode}.graphml"


def build_graph(s: Settings, polygon, mode: str) -> nx.MultiDiGraph:
    acc = s["accessibility"]
    G = ox.graph_from_polygon(polygon, network_type=mode, simplify=True, retain_all=False)
    # Keep only the main connected piece so every snapped point can reach every other.
    G = ox.truncate.largest_component(G, strongly=(mode == "drive"))

    if mode == "drive":
        G = ox.routing.add_edge_speeds(G, hwy_speeds=acc["drive_speeds_kmh"])
        G = ox.routing.add_edge_travel_times(G)
    else:
        mps = acc["walk_speed_kmh"] / 3.6
        times = {(u, v, k): d["length"] / mps for u, v, k, d in G.edges(keys=True, data=True)}
        nx.set_edge_attributes(G, times, "travel_time")

    return ox.projection.project_graph(G, to_crs=s.projected_crs)


def load_graph(s: Settings, mode: str) -> nx.MultiDiGraph:
    return ox.io.load_graphml(graph_path(s, mode))


def _edges_for_gpkg(G) -> gpd.GeoDataFrame:
    edges = ox.convert.graph_to_gdfs(G, nodes=False).reset_index()
    cols = ["u", "v", "key", "highway", "name", "length", "travel_time", "geometry"]
    edges = edges[[c for c in cols if c in edges.columns]].copy()
    for c in ("highway", "name"):  # simplified edges may hold lists, which GPKG cannot store
        if c in edges:
            edges[c] = edges[c].map(lambda v: ";".join(map(str, v)) if isinstance(v, list) else v)
    return edges


# --- facilities -------------------------------------------------------------------------


def _query_tags(categories: dict) -> dict:
    tags: dict = {}
    for spec in categories.values():
        for key, vals in spec.items():
            if vals is True or tags.get(key) is True:
                tags[key] = True
            else:
                tags[key] = sorted(set(tags.get(key, [])) | set(vals))
    return tags


def categorise(row: pd.Series, categories: dict, priority: list[str]) -> str | None:
    for cat in priority:
        for key, vals in categories[cat].items():
            value = row.get(key)
            if isinstance(value, str) and (vals is True or value in vals):
                return cat
    return None


def _drop_nodes_inside_polygons(fac: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """OSM often maps one hospital as both a building polygon and a node; keep one."""
    polys = fac[fac.geom_type.isin(["Polygon", "MultiPolygon"])]
    nodes = fac[fac["osm_type"] == "node"]
    if polys.empty or nodes.empty:
        return fac
    hits = gpd.sjoin(nodes, polys[["category", "geometry"]], predicate="within")
    dup_idx = hits.index[hits["category_left"] == hits["category_right"]].unique()
    return fac.drop(index=dup_idx)


def build_facilities(s: Settings, polygon) -> gpd.GeoDataFrame:
    categories, priority = s["facilities"], s["category_priority"]
    raw = ox.features_from_polygon(polygon, tags=_query_tags(categories)).reset_index()
    # Some mappers add literal `osm_id`/`osm_type` tags; drop them so they can't clash.
    raw = raw.drop(columns=["osm_type", "osm_id"], errors="ignore")
    raw = raw.rename(columns={"element": "osm_type", "id": "osm_id"})
    raw["category"] = raw.apply(categorise, axis=1, categories=categories, priority=priority)
    fac = raw[raw["category"].notna()].copy()

    keep = ["osm_type", "osm_id", "category", "name", *TAG_COLUMNS, "geometry"]
    fac = fac[[c for c in keep if c in fac.columns]].to_crs(s.projected_crs)
    n_before = len(fac)
    fac = _drop_nodes_inside_polygons(fac)
    log.info("facilities: %d matched, %d after de-duplication", n_before, len(fac))

    fac["geometry"] = fac.geometry.representative_point()
    city, _ = boundaries.load(s)
    fac["inside_city"] = fac.within(city.union_all())
    return fac.reset_index(drop=True)


def build(s: Settings) -> None:
    _configure_osmnx(s)
    polygon = study_area(s)
    checks = {}

    for mode in s["osm"]["network_types"]:
        log.info("fetching %s network ...", mode)
        G = build_graph(s, polygon, mode)
        ox.io.save_graphml(G, graph_path(s, mode))
        _edges_for_gpkg(G).to_file(s.gpkg, layer=f"network_{mode}", driver="GPKG")
        checks[f"{mode}_nodes"] = qa.check(G.number_of_nodes() > 1000, G.number_of_nodes())
        checks[f"{mode}_edges"] = qa.check(None, G.number_of_edges())
        checks[f"{mode}_length_km"] = qa.check(
            None,
            round(sum(d["length"] for *_, d in G.edges(data=True)) / 1000, 1),
            "directed edges: two-way streets are counted in both directions",
        )

    log.info("fetching facilities ...")
    fac = build_facilities(s, polygon)
    fac.to_file(s.gpkg, layer="facilities", driver="GPKG")
    inside = fac[fac["inside_city"]]
    for cat in s["category_priority"]:
        n_in = int((inside["category"] == cat).sum())
        n_all = int((fac["category"] == cat).sum())
        checks[f"facilities_{cat}"] = qa.check(
            n_in >= 5,
            f"{n_in} in city / {n_all} incl. buffer",
            "fewer than 5 in the city: treat results as unreliable" if n_in < 5 else "",
        )
    qa.write(s, "osm", checks)
