"""Travel time from every populated 100 m cell to the nearest facility of each category.

Method (per mode, per category):
  1. Snap facilities and population cells to the nearest network node (KD-tree).
  2. Connect a virtual source to every facility node, weighted by the facility's
     off-network walking time, and run one Dijkstra on the *reversed* graph — this
     gives time from each node *to* its nearest facility (matters for one-way streets).
  3. Cell time = off-network walk to its node + network time.
Barangay indicators are population-weighted from the cells.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from abot import boundaries, osm, population, qa
from abot.config import Settings

log = logging.getLogger(__name__)

SOURCE = "__facilities__"


class Snapper:
    def __init__(self, G: nx.MultiDiGraph):
        self.ids = np.array(list(G.nodes))
        self.tree = cKDTree(np.array([(G.nodes[n]["x"], G.nodes[n]["y"]) for n in self.ids]))

    def __call__(self, points: gpd.GeoSeries) -> tuple[np.ndarray, np.ndarray]:
        dist, idx = self.tree.query(np.column_stack([points.x, points.y]))
        return self.ids[idx], dist


def time_to_nearest(GR: nx.MultiDiGraph, fac_nodes: np.ndarray, fac_offset_s: np.ndarray) -> dict:
    """Seconds from every node to the nearest facility. GR must be the reversed graph."""
    best: dict = {}
    for node, off in zip(fac_nodes, fac_offset_s, strict=True):
        best[node] = min(off, best.get(node, np.inf))
    GR.add_node(SOURCE)
    GR.add_edges_from((SOURCE, n, {"travel_time": t}) for n, t in best.items())
    try:
        times = nx.single_source_dijkstra_path_length(GR, SOURCE, weight="travel_time")
    finally:
        GR.remove_node(SOURCE)
    times.pop(SOURCE, None)
    return times


def cell_times(s: Settings, cells: gpd.GeoDataFrame, fac: gpd.GeoDataFrame) -> pd.DataFrame:
    snap_mps = s["accessibility"]["snap_speed_kmh"] / 3.6
    out = pd.DataFrame(index=cells.index)

    for mode in s["osm"]["network_types"]:
        G = osm.load_graph(s, mode)
        snap = Snapper(G)
        GR = G.reverse(copy=True)
        cell_nodes, cell_d = snap(cells.geometry)
        out[f"snap_m_{mode}"] = cell_d.round(1)

        for cat in s["category_priority"]:
            sub = fac[fac["category"] == cat]
            col = f"t_{mode}_{cat}"
            if sub.empty:
                out[col] = np.nan
                continue
            f_nodes, f_d = snap(sub.geometry)
            node_time = time_to_nearest(GR, f_nodes, f_d / snap_mps)
            net = np.array([node_time.get(n, np.nan) for n in cell_nodes])
            out[col] = ((cell_d / snap_mps + net) / 60).round(2)  # minutes
        log.info("%s: travel times computed for %d cells", mode, len(cells))
    return out


def barangay_indicators(s: Settings, cells: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    thresholds = s["accessibility"]["thresholds_min"]
    rows = []
    for pcode, g in cells.groupby("adm4_pcode"):
        w = g["pop"].to_numpy()
        row = {"adm4_pcode": pcode, "pop_cells": len(g)}
        for mode in s["osm"]["network_types"]:
            for cat in s["category_priority"]:
                t = g[f"t_{mode}_{cat}"].to_numpy()
                ok = ~np.isnan(t)
                if not ok.any() or w[ok].sum() == 0:
                    continue
                row[f"{mode}_{cat}_mean_min"] = round(float(np.average(t[ok], weights=w[ok])), 2)
                row[f"{mode}_{cat}_max_min"] = round(float(t[ok].max()), 2)
                for th in thresholds[mode]:
                    row[f"{mode}_{cat}_pct_le{th}"] = round(100 * float(w[ok & (t <= th)].sum() / w.sum()), 1)
        rows.append(row)
    ind = pd.DataFrame(rows)
    return brgy[["adm4_pcode", "adm4_name", "geometry"]].merge(ind, on="adm4_pcode", how="left")


def facility_counts(s: Settings, fac: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame) -> pd.DataFrame:
    j = gpd.sjoin(fac[fac["inside_city"]], brgy[["adm4_pcode", "geometry"]], predicate="within")
    counts = j.groupby(["adm4_pcode", "category"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=s["category_priority"], fill_value=0).add_prefix("n_")
    return counts.reindex(brgy["adm4_pcode"], fill_value=0).reset_index()


def build(s: Settings) -> None:
    year = s["sources"]["worldpop"]["analysis_year"]
    _, brgy = boundaries.load(s)
    cells = population.load_cells(s, year)
    fac = gpd.read_file(s.gpkg, layer="facilities")

    times = cell_times(s, cells, fac)
    cells = cells.join(times)
    cells.to_file(s.gpkg, layer=f"access_cells_{year}", driver="GPKG")

    ind = barangay_indicators(s, cells, brgy)
    ind = ind.merge(facility_counts(s, fac, brgy), on="adm4_pcode", how="left")
    pop = population.load_barangay_population(s).drop(columns="adm4_name")
    ind = ind.merge(pop, on="adm4_pcode", how="left")
    ind.to_file(s.gpkg, layer="barangay_access", driver="GPKG")
    ind.drop(columns="geometry").to_csv(s.processed_dir / "barangay_access.csv", index=False)

    checks = {}
    total = cells["pop"].sum()
    for mode in s["osm"]["network_types"]:
        checks[f"{mode}_median_snap_m"] = qa.check(
            None, round(float(cells[f"snap_m_{mode}"].median()), 1), "cell centre to nearest node"
        )
        for cat in s["category_priority"]:
            col = f"t_{mode}_{cat}"
            unreachable = cells[col].isna()
            checks[f"{mode}_{cat}_unreachable_pop"] = qa.check(
                unreachable.sum() == 0 or fac[fac["category"] == cat].empty,
                round(float(cells.loc[unreachable, "pop"].sum())),
            )
            ok = ~unreachable
            if ok.any():
                checks[f"{mode}_{cat}_citywide_mean_min"] = qa.check(
                    None,
                    round(float(np.average(cells.loc[ok, col], weights=cells.loc[ok, "pop"])), 2),
                    f"population-weighted, {year}",
                )
    checks["population_total"] = qa.check(None, round(float(total)))
    qa.write(s, "accessibility", checks)
