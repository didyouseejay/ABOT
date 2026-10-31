"""Travel time from every populated 100 m cell to the nearest facility of each indicator group.

Method (per indicator group; see docs/METHODOLOGY.md):
  1. Connection. Every cell centre and facility is joined by a straight connector to the
     nearest *edge* of the walk network (the point on the edge, not its end node). Candidate
     edges are tried nearest-first; a connector that crosses a hard barrier (water area,
     river/canal/stream, coastline) is rejected and the next edge is tried. Points with no
     acceptable edge within `max_connector_m` are flagged "not connected" and get no time.
  2. Walk. A virtual source is joined to both end nodes of every facility's edge (weight =
     connector + distance along the edge, walked), and one Dijkstra on the reversed graph gives
     every node's time to the nearest facility. A cell's time is its connector plus the cheaper
     of its edge's two ends.
  3. Drive. The walk from home to the car is routed on the walk network to the nearest node of
     the drive network (no straight line beyond the connector), likewise from the drive network
     to the facility. Driving between those nodes follows the drive graph with one-way streets.
Barangay indicators are population-weighted over the fractional pieces of every cell (see
population.py). Shares within a threshold use ALL residents as the denominator: residents without a
valid connection are neither "within" nor "beyond" and are reported separately (pct_not_connected),
so pct_le<N> + pct_gt<N> + pct_not_connected = 100. Means and p90 describe connected residents only.
Facilities outside the city (in the OSM buffer) are destinations only if they are connected.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from abot import boundaries, osm, population, qa, reliability
from abot.compare import weighted_quantile
from abot.config import Settings

log = logging.getLogger(__name__)

SOURCE = "__facilities__"
OK, BEYOND, BLOCKED = "connected", "beyond_tolerance", "barrier_blocked"


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


# --- connecting points to the network ------------------------------------------------------


class EdgeIndex:
    """Spatial index over the undirected edges of a network, with geometry oriented u -> v."""

    def __init__(self, G: nx.MultiDiGraph):
        seen, rows = set(), []
        for u, v, k, d in G.edges(keys=True, data=True):
            key = (min(u, v), max(u, v), k)
            if key in seen:
                continue
            seen.add(key)
            pu, pv = (G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])
            geom = d.get("geometry")
            if geom is None:
                geom = LineString([pu, pv])
            elif Point(geom.coords[0]).distance(Point(pu)) > Point(geom.coords[0]).distance(Point(pv)):
                geom = LineString(list(geom.coords)[::-1])
            rows.append((u, v, float(d["length"]), geom))
        self.u = np.array([r[0] for r in rows], dtype=object)
        self.v = np.array([r[1] for r in rows], dtype=object)
        self.length = np.array([r[2] for r in rows])
        self.geoms = np.array([r[3] for r in rows], dtype=object)
        self.tree = STRtree(self.geoms)

    def candidates(self, pt: Point, max_d: float, k: int) -> tuple[np.ndarray, np.ndarray]:
        idx = self.tree.query(pt, predicate="dwithin", distance=max_d)
        if len(idx) == 0:
            return idx, np.array([])
        d = shapely.distance(self.geoms[idx], pt)
        order = np.argsort(d, kind="stable")[:k]
        return idx[order], d[order]

    def nearest_distance(self, pt: Point) -> float:
        _, d = self.tree.query_nearest(pt, return_distance=True)
        return float(d[0])


class BarrierChecker:
    """Tests whether a straight connector crosses water or (soft) a wall."""

    def __init__(self, barriers: gpd.GeoDataFrame | None, water_tolerance_m: float):
        def geoms(kind):
            if barriers is None or barriers.empty:
                return np.array([], dtype=object)
            return np.array(list(barriers.loc[barriers["kind"] == kind, "geometry"]), dtype=object)

        self.areas, self.lines, self.walls = geoms("water_area"), geoms("water_line"), geoms("wall")
        self.area_tree = STRtree(self.areas) if len(self.areas) else None
        self.line_tree = STRtree(self.lines) if len(self.lines) else None
        self.wall_tree = STRtree(self.walls) if len(self.walls) else None
        self.tol = water_tolerance_m

    def blocked(self, origin: Point, connector: LineString, radius: float) -> bool:
        """True if the connector crosses a watercourse/coastline away from the origin, or runs
        more than `tol` metres through a water area that does not contain the origin."""
        zone = origin.buffer(radius) if radius > 0 else None
        if self.line_tree is not None:
            for i in self.line_tree.query(connector, predicate="intersects"):
                hit = connector.intersection(self.lines[i])
                if zone is None or not hit.difference(zone).is_empty:
                    return True
        if self.area_tree is not None:
            for i in self.area_tree.query(connector, predicate="intersects"):
                area = self.areas[i]
                if area.contains(origin):
                    continue
                if connector.intersection(area).length > self.tol:
                    return True
        return False

    def crosses_wall(self, connector: LineString) -> bool:
        return self.wall_tree is not None and len(self.wall_tree.query(connector, predicate="intersects")) > 0


@dataclass
class Connection:
    u: object = None
    v: object = None
    a_u: float = np.nan  # metres along the edge from the connection point to u
    a_v: float = np.nan
    conn_m: float = np.nan
    nearest_m: float = np.nan  # distance to the nearest edge, accepted or not
    status: str = BEYOND
    rerouted: bool = False  # nearer edge(s) rejected because the connector crossed a barrier
    crosses_wall: bool = False


def connect_point(
    pt: Point, edges: EdgeIndex, barriers: BarrierChecker, cfg: dict, radius: float, max_m: float
) -> Connection:
    idx, dist = edges.candidates(pt, max_m, cfg["max_candidates"])
    if len(idx) == 0:
        return Connection(nearest_m=edges.nearest_distance(pt), status=BEYOND)
    for n, (i, d) in enumerate(zip(idx, dist, strict=True)):
        line = edges.geoms[i]
        s = line.project(pt)
        cp = line.interpolate(s)
        connector = LineString([pt, cp]) if d > 0 else None
        if connector is not None and barriers.blocked(pt, connector, radius):
            continue
        frac = s / line.length if line.length > 0 else 0.0
        a_u = frac * edges.length[i]
        return Connection(
            u=edges.u[i],
            v=edges.v[i],
            a_u=a_u,
            a_v=edges.length[i] - a_u,
            conn_m=float(d),
            nearest_m=float(dist[0]),
            status=OK,
            rerouted=n > 0,
            crosses_wall=connector is not None and barriers.crosses_wall(connector),
        )
    return Connection(nearest_m=float(dist[0]), status=BLOCKED)


def connect_points(
    points: gpd.GeoSeries,
    edges: EdgeIndex,
    barriers: BarrierChecker,
    cfg: dict,
    radius: float,
    max_m: float | None = None,
) -> pd.DataFrame:
    max_m = cfg["max_connector_m"] if max_m is None else max_m
    rows = [connect_point(p, edges, barriers, cfg, radius, max_m).__dict__ for p in points]
    return pd.DataFrame(rows, index=points.index)


# --- travel times ------------------------------------------------------------------------------


def _best_of_ends(conn: pd.DataFrame, node_value: dict, per_m: float) -> np.ndarray:
    """min over the two edge ends of (distance along edge * per_m + value at node)."""
    tu = conn["a_u"].to_numpy() * per_m + np.array(
        [node_value.get(n, np.nan) for n in conn["u"]], dtype=float
    )
    tv = conn["a_v"].to_numpy() * per_m + np.array(
        [node_value.get(n, np.nan) for n in conn["v"]], dtype=float
    )
    return np.fmin(tu, tv)


def walk_times(GR: nx.MultiDiGraph, cells: pd.DataFrame, fac: pd.DataFrame, mps: float) -> np.ndarray:
    """Seconds from each connected cell to its nearest connected facility on the walk network."""
    f = fac[fac["status"] == OK]
    if f.empty:
        return np.full(len(cells), np.nan)
    nodes = np.concatenate([f["u"].to_numpy(), f["v"].to_numpy()])
    off = np.concatenate([(f["conn_m"] + f["a_u"]).to_numpy(), (f["conn_m"] + f["a_v"]).to_numpy()]) / mps
    node_t = time_to_nearest(GR, nodes, off)
    t = cells["conn_m"].to_numpy() / mps + _best_of_ends(cells, node_t, 1 / mps)

    # Cell and facility on the same edge: the direct walk along the edge can beat going via a node.
    by_edge: dict = {}
    for r in f.itertuples():
        by_edge.setdefault(frozenset((r.u, r.v)), []).append((r.u, r.a_u, r.conn_m))
    for i, r in enumerate(cells.itertuples()):
        if r.status != OK:
            continue
        for fu, fa_u, fconn in by_edge.get(frozenset((r.u, r.v)), []):
            pos_c = r.a_u if r.u == fu else r.a_v  # both measured from the same end node
            direct = (r.conn_m + abs(pos_c - fa_u) + fconn) / mps
            if direct < t[i]:
                t[i] = direct
    t[(cells["status"] != OK).to_numpy()] = np.nan
    return t


def nearest_source_dijkstra(G: nx.MultiDiGraph, sources, weight: str = "length") -> tuple[dict, dict]:
    """Multi-source Dijkstra returning (distance, nearest source) for every reachable node."""
    dist: dict = {}
    src: dict = {}
    heap = [(0.0, i, s, s) for i, s in enumerate(sources)]
    heapq.heapify(heap)
    counter = len(heap)
    while heap:
        d, _, node, origin = heapq.heappop(heap)
        if node in dist:
            continue
        dist[node], src[node] = d, origin
        for nbr, keys in G.succ[node].items():
            if nbr in dist:
                continue
            w = min(data.get(weight, np.inf) for data in keys.values())
            counter += 1
            heapq.heappush(heap, (d + w, counter, nbr, origin))
    return dist, src


def drive_access(conn: pd.DataFrame, walk_dist: dict, walk_src: dict) -> tuple[np.ndarray, np.ndarray]:
    """Walking metres from each connected point to the nearest drive node, and that node."""
    du = conn["a_u"].to_numpy() + np.array([walk_dist.get(n, np.nan) for n in conn["u"]], dtype=float)
    dv = conn["a_v"].to_numpy() + np.array([walk_dist.get(n, np.nan) for n in conn["v"]], dtype=float)
    use_v = np.nan_to_num(dv, nan=np.inf) < np.nan_to_num(du, nan=np.inf)
    metres = conn["conn_m"].to_numpy() + np.where(use_v, dv, du)
    entry = np.array(
        [walk_src.get(v if uv else u) for u, v, uv in zip(conn["u"], conn["v"], use_v, strict=True)],
        dtype=object,
    )
    bad = (conn["status"] != OK).to_numpy() | np.isnan(metres)
    metres[bad] = np.nan
    entry[bad] = None
    return metres, entry


def drive_times(
    GR_drive, cell_access_m, cell_entry, fac_access_m, fac_entry, walk_mps, network_factor: float = 1.0
) -> np.ndarray:
    """Seconds door to door. `network_factor` multiplies only the drive-network leg (sensitivity);
    min_f(walk_f + k * drive) = k * min_f(walk_f / k + drive), so one Dijkstra still suffices."""
    ok = ~np.isnan(fac_access_m)
    if not ok.any():
        return np.full(len(cell_access_m), np.nan)
    k = network_factor
    node_t = time_to_nearest(GR_drive, fac_entry[ok], fac_access_m[ok] / walk_mps / k)
    net = np.array([node_t.get(n, np.nan) if n is not None else np.nan for n in cell_entry], dtype=float)
    return cell_access_m / walk_mps + k * net


# --- orchestration -------------------------------------------------------------------------------


def group_facilities(s: Settings, roles: gpd.GeoDataFrame, group: str) -> gpd.GeoDataFrame:
    g = s["indicator_groups"][group]
    sel = roles[(roles["category"] == g["category"]) & roles["subtype"].isin(g["subtypes"])]
    return sel.drop_duplicates("fid_key")


def compute(
    s: Settings, cells: gpd.GeoDataFrame, roles: gpd.GeoDataFrame, barriers
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(cell times, facility connections, drive network-speed sensitivity times in minutes)."""
    acc = s["accessibility"]
    cfg = acc["connection"]
    walk_mps = acc["walk_speed_kmh"] / 3.6
    W = osm.load_graph(s, "walk")
    edges = EdgeIndex(W)
    checker = BarrierChecker(barriers, cfg["water_crossing_tolerance_m"])

    log.info(
        "connecting %d cells and %d facilities to the walk network ...",
        len(cells),
        roles["fid_key"].nunique(),
    )
    cc = connect_points(cells.geometry, edges, checker, cfg, cfg["origin_radius_m"])
    fac_pts = roles.drop_duplicates("fid_key").set_index("fid_key")
    fc = connect_points(
        fac_pts.geometry, edges, checker, cfg, cfg["facility_radius_m"], cfg["facility_max_connector_m"]
    )

    out = pd.DataFrame(index=cells.index)
    out["conn_status"] = cc["status"]
    out["conn_m"] = cc["conn_m"].round(1)
    out["nearest_edge_m"] = cc["nearest_m"].round(1)
    out["conn_rerouted"] = cc["rerouted"]
    out["conn_crosses_wall"] = cc["crosses_wall"]

    groups = list(s["indicator_groups"])
    modes = s["osm"]["network_types"]
    sens = pd.DataFrame(index=cells.index)
    if "walk" in modes:
        WR = W.reverse(copy=True)
        for gname in groups:
            sub = fc.loc[group_facilities(s, roles, gname)["fid_key"]]
            out[f"t_walk_{gname}"] = (walk_times(WR, cc, sub, walk_mps) / 60).round(2)
        del WR
    if "drive" in modes:
        D = osm.load_graph(s, "drive")
        shared = [n for n in D.nodes if n in W]
        wdist, wsrc = nearest_source_dijkstra(W, shared, weight="length")
        cell_m, cell_entry = drive_access(cc, wdist, wsrc)
        fac_m, fac_entry = drive_access(fc, wdist, wsrc)
        out["drive_access_m"] = np.round(cell_m, 1)
        DR = D.reverse(copy=True)
        for gname in groups:
            keys = group_facilities(s, roles, gname)["fid_key"]
            pos = fc.index.get_indexer(keys)
            out[f"t_drive_{gname}"] = (
                drive_times(DR, cell_m, cell_entry, fac_m[pos], fac_entry[pos], walk_mps) / 60
            ).round(2)
            for k in acc.get("drive_network_time_factors", []):
                sens[f"t_drive_{gname}_x{k:g}"] = (
                    drive_times(DR, cell_m, cell_entry, fac_m[pos], fac_entry[pos], walk_mps, k) / 60
                ).round(2)
        fc["drive_access_m"] = np.round(fac_m, 1)
    log.info("travel times computed for %d cells x %d groups", len(cells), len(groups))
    return out, fc, sens


def _pieces(cells: pd.DataFrame, pieces: pd.DataFrame | None) -> pd.DataFrame:
    """Weighted units for barangay aggregation: fractional pieces carrying their cell's results.

    Without `pieces` every cell counts whole in its own barangay (used by tests and old outputs).
    """
    if pieces is None:
        return cells.drop(columns="geometry", errors="ignore")
    res = cells.drop(columns=["geometry", "pop", "adm4_pcode"], errors="ignore").set_index("cell_id")
    return pieces[["cell_id", "adm4_pcode", "pop"]].join(res, on="cell_id")


def barangay_indicators(
    s: Settings, cells: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame, pieces: pd.DataFrame | None = None
) -> gpd.GeoDataFrame:
    """Population-weighted indicators. Shares use all residents; means and p90 connected residents."""
    thresholds = s["accessibility"]["thresholds_min"]
    flag_m = s["accessibility"]["connection"]["drive_access_flag_m"]
    low_pct = s["reliability"]["network"]["low_pct_not_connected"]
    rows = []
    for pcode, g in _pieces(cells, pieces).groupby("adm4_pcode"):
        w = g["pop"].to_numpy(dtype=float)
        total = float(w.sum())
        conn = (g["conn_status"] == OK).to_numpy()
        row = {
            "adm4_pcode": pcode,
            "pop_total": round(total, 1),
            "pop_connected": round(float(w[conn].sum()), 1),
            "pop_not_connected": round(float(w[~conn].sum()), 1),
            "pct_not_connected": round(100 * float(w[~conn].sum()) / total, 1) if total else 0.0,
        }
        # Means and p90 describe connected residents only; flag when that is a poor proxy.
        row["indicators_flag_not_connected"] = row["pct_not_connected"] > low_pct
        if "drive_access_m" in g:
            row["pop_drive_access_gt_flag"] = round(
                float(w[(g["drive_access_m"] > flag_m).to_numpy()].sum()), 1
            )
        for mode in s["osm"]["network_types"]:
            for gname in s["indicator_groups"]:
                t = g[f"t_{mode}_{gname}"].to_numpy(dtype=float)
                ok = conn & ~np.isnan(t)
                if not ok.any() or w[ok].sum() == 0:
                    continue
                row[f"{mode}_{gname}_mean_min"] = round(float(np.average(t[ok], weights=w[ok])), 2)
                row[f"{mode}_{gname}_p90_min"] = round(weighted_quantile(t[ok], w[ok], 0.9), 2)
                for th in thresholds[mode]:
                    row[f"{mode}_{gname}_pct_le{th}"] = round(100 * float(w[ok & (t <= th)].sum()) / total, 1)
        rows.append(row)
    ind = pd.DataFrame(rows)
    return brgy[["adm4_pcode", "adm4_name", "geometry"]].merge(ind, on="adm4_pcode", how="left")


def drive_sensitivity(s: Settings, cells: pd.DataFrame, sens: pd.DataFrame) -> pd.DataFrame:
    """City-wide shares of ALL residents within each drive threshold, by network-time factor."""
    w = cells["pop"].to_numpy(dtype=float)
    total = w.sum()
    conn = (cells["conn_status"] == OK).to_numpy()
    rows = []
    for gname in s["indicator_groups"]:
        for k in [1.0, *s["accessibility"].get("drive_network_time_factors", [])]:
            col = f"t_drive_{gname}" if k == 1.0 else f"t_drive_{gname}_x{k:g}"
            src = cells if k == 1.0 else sens
            if col not in src:
                continue
            t = src[col].to_numpy(dtype=float)
            ok = conn & ~np.isnan(t)
            row = {
                "group": gname,
                "network_time_factor": k,
                "mean_min": round(float(np.average(t[ok], weights=w[ok])), 2),
            }
            for th in s["accessibility"]["thresholds_min"]["drive"]:
                row[f"pct_le{th}"] = round(100 * float(w[ok & (t <= th)].sum()) / total, 1)
            row["pct_not_connected"] = round(100 * float(w[~conn].sum()) / total, 2)
            rows.append(row)
    return pd.DataFrame(rows)


def facility_counts(s: Settings, roles: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame) -> pd.DataFrame:
    """n_<category>: all mapped features by category (any tier); n_<group>: indicator-group destinations."""
    inside = roles[roles["inside_city"]]
    j = gpd.sjoin(inside, brgy[["adm4_pcode", "geometry"]], predicate="within")
    counts = j.groupby(["adm4_pcode", "category"])["fid_key"].nunique().unstack(fill_value=0)
    counts = counts.reindex(columns=s["category_priority"], fill_value=0).add_prefix("n_")
    for gname, g in s["indicator_groups"].items():
        sel = j[(j["category"] == g["category"]) & j["subtype"].isin(g["subtypes"])]
        counts[f"n_{gname}"] = sel.groupby("adm4_pcode")["fid_key"].nunique()
    return counts.reindex(brgy["adm4_pcode"]).fillna(0).astype(int).reset_index()


def _pct(x: float, total: float) -> float:
    return round(100 * x / total, 2) if total else 0.0


def build(s: Settings) -> None:
    _, brgy = boundaries.load(s)
    cells = population.load_cells(s)
    pieces = population.load_pieces(s)
    roles = osm.load_roles(s)
    barriers = osm.load_barriers(s)

    times, fc, sens = compute(s, cells, roles, barriers)
    cells = cells.join(times)
    cells.to_file(s.gpkg, layer="access_cells", driver="GPKG")
    drive_sensitivity(s, cells, sens).to_csv(s.processed_dir / "drive_speed_sensitivity.csv", index=False)

    conn_cols = fc[
        ["status", "conn_m", "nearest_m", "rerouted", *(["drive_access_m"] if "drive_access_m" in fc else [])]
    ]
    conn_cols = conn_cols.rename(
        columns={"status": "conn_status", "nearest_m": "nearest_edge_m", "rerouted": "conn_rerouted"}
    ).round(1)
    fac = gpd.read_file(s.gpkg, layer="facilities")
    # Replace (never stack) connection columns so the stage can be re-run.
    stale = [
        c
        for c in fac.columns
        if c.split("_x")[0].split("_y")[0] in conn_cols.columns or c in conn_cols.columns
    ]
    fac = fac.drop(columns=stale).merge(conn_cols, left_on="fid_key", right_index=True, how="left")
    fac.to_file(s.gpkg, layer="facilities", driver="GPKG")

    ind = barangay_indicators(s, cells, brgy, pieces)
    ind = ind.merge(facility_counts(s, roles, brgy), on="adm4_pcode", how="left")
    pop = population.load_barangay_population(s).drop(columns=["adm4_name", "pop"])
    ind = ind.merge(pop, on="adm4_pcode", how="left")
    excl = pd.read_csv(s.processed_dir / "facility_exclusions.csv")
    ind = reliability.add_flags(s, ind, fac, excl)
    ind.to_file(s.gpkg, layer="barangay_access", driver="GPKG")
    ind.drop(columns="geometry").to_csv(s.processed_dir / "barangay_access.csv", index=False)
    reliability.facility_inventory(s, roles, fac, excl).to_csv(
        s.processed_dir / "facility_inventory.csv", index=False
    )

    qa.write(s, "accessibility", accessibility_checks(s, cells, fc, roles))
    qa.record_stage(s, "accessibility")


def accessibility_checks(s: Settings, cells: pd.DataFrame, fc: pd.DataFrame, roles) -> dict:
    cfg = s["accessibility"]["connection"]
    low_pct = s["reliability"]["network"]["low_pct_not_connected"]
    w = cells["pop"]
    total = float(w.sum())
    conn = cells["conn_status"] == OK
    weight = (s.get("population") or {}).get("primary_weight", "census_2020_anchored")
    checks: dict = {"population_total": qa.check(None, round(total), f"primary weight: {weight}")}

    # Origin connections
    checks["origins_connected_pop_pct"] = qa.check(
        _pct(w[conn].sum(), total) >= 99.0,
        _pct(w[conn].sum(), total),
        "share of population with a valid network connection",
    )
    for status, note in [
        (BEYOND, f"no walkable edge within {cfg['max_connector_m']} m"),
        (BLOCKED, "every nearby edge is across water/coastline"),
    ]:
        sel = cells["conn_status"] == status
        checks[f"origins_{status}_pop"] = qa.check(
            None,
            round(float(w[sel].sum())),
            f"{int(sel.sum())} cells; {note}; no travel time, kept in every denominator, "
            "reported as not connected (review: abot review)",
        )
    by_b = cells.assign(nc=w.where(~conn, 0)).groupby("adm4_pcode").agg(nc=("nc", "sum"), p=("pop", "sum"))
    flagged = by_b[100 * by_b["nc"] / by_b["p"] > low_pct]
    checks["barangays_flag_not_connected"] = qa.check(
        None,
        len(flagged),
        f"barangays (cell home barangay) with > {low_pct}% of residents not connected; see rel_network",
    )
    checks["origins_conservation"] = qa.check(
        abs(w[conn].sum() + w[~conn].sum() - total) < 1e-6,
        round(float(w[conn].sum() + w[~conn].sum())),
        "connected + not connected = total",
    )
    q = cells.loc[conn, "conn_m"].quantile([0.5, 0.9, 0.99, 1.0]).round(1)
    checks["origin_connector_m"] = qa.check(
        None,
        f"p50 {q[0.5]} / p90 {q[0.9]} / p99 {q[0.99]} / max {q[1.0]}",
        "straight connector to nearest acceptable edge",
    )
    for th in cfg["report_connector_thresholds_m"]:
        sel = cells["nearest_edge_m"] > th
        checks[f"origins_nearest_edge_gt{th}m_pop"] = qa.check(
            None, round(float(w[sel].sum())), "sensitivity of the connection tolerance"
        )
    checks["origins_rerouted_around_water_pop"] = qa.check(
        None,
        round(float(w[conn & cells["conn_rerouted"]].sum())),
        "nearest edge rejected because the connector crossed water",
    )
    checks["origins_connector_crosses_wall_pop"] = qa.check(
        None,
        round(float(w[conn & cells["conn_crosses_wall"]].sum())),
        "flag only: gates are not mapped reliably",
    )

    # Facility connections
    ok_f = fc["status"] == OK
    checks["facilities_connected"] = qa.check(
        bool(ok_f.all()),
        f"{int(ok_f.sum())} of {len(fc)}",
        "unconnected facilities are not used as destinations",
    )
    if (~ok_f).any():
        checks["facilities_not_connected"] = qa.check(
            False, "; ".join(fc.index[~ok_f].astype(str)), "osm_type/osm_id"
        )
    if roles is not None:
        inside = roles.drop_duplicates("fid_key").set_index("fid_key")["inside_city"].reindex(fc.index)
        outside = inside.eq(False).to_numpy()
        checks["external_destinations_connected"] = qa.check(
            None,
            int((outside & ok_f.to_numpy()).sum()),
            "facilities in the OSM buffer outside the city that are used as destinations",
        )
        checks["external_facilities_not_connected"] = qa.check(
            None,
            int((outside & ~ok_f.to_numpy()).sum()),
            "outside the city with no valid connection (e.g. Guimaras): never used as destinations",
        )
    qf = fc.loc[ok_f, "conn_m"].quantile([0.5, 0.9, 1.0]).round(1)
    checks["facility_connector_m"] = qa.check(None, f"p50 {qf[0.5]} / p90 {qf[0.9]} / max {qf[1.0]}")
    long_f = ok_f & (fc["conn_m"] > cfg["max_connector_m"])
    checks["facilities_long_connector"] = qa.check(
        None,
        "; ".join(fc.index[long_f].astype(str)) or "none",
        f"kept as destinations, connector > {cfg['max_connector_m']} m (≤ {cfg['facility_max_connector_m']} m)",
    )

    # Drive access legs (walk network from home to the nearest drive-network node)
    if "drive_access_m" in cells:
        qd = cells.loc[conn, "drive_access_m"].quantile([0.5, 0.9, 0.99, 1.0]).round(0)
        checks["drive_access_walk_m"] = qa.check(
            None,
            f"p50 {qd[0.5]} / p90 {qd[0.9]} / p99 {qd[0.99]} / max {qd[1.0]}",
            "walked on the network, not a straight line",
        )
        flag = cells["drive_access_m"] > cfg["drive_access_flag_m"]
        checks["drive_access_gt_flag_pop"] = qa.check(
            None,
            round(float(w[flag].sum())),
            f"walk to the drive network > {cfg['drive_access_flag_m']} m (kept, flagged)",
        )

    # Valid assignments: every connected cell must get a finite time for every group. Can fail.
    for mode in s["osm"]["network_types"]:
        for gname in s["indicator_groups"]:
            col = f"t_{mode}_{gname}"
            missing = conn & cells[col].isna()
            checks[f"{mode}_{gname}_connected_without_time"] = qa.check(
                not missing.any(), int(missing.sum()), "connected cells with no finite travel time"
            )
            t, ww = cells.loc[conn, col], w[conn]
            okt = t.notna()
            if okt.any():
                th = s["accessibility"]["thresholds_min"][mode]
                within = ", ".join(f"≤{x}: {_pct(ww[okt & (t <= x)].sum(), total)}%" for x in th)
                label = "modelled uncongested car travel time, lower bound" if mode == "drive" else "walk"
                checks[f"{mode}_{gname}_citywide"] = qa.check(
                    None,
                    f"mean {np.average(t[okt], weights=ww[okt]):.2f} min; {within}",
                    f"{label}; mean over connected residents, shares of ALL residents "
                    f"({_pct(w[~conn].sum(), total)}% not connected)",
                )
    return checks
