"""Manual-review files: possible duplicate facilities and population cells without a network connection.

`abot review` only READS the run's outputs and writes to <processed>/review/. It never merges,
deletes, reclassifies or reconnects anything: every row starts as review_status = "pending", and no
pipeline stage reads a reviewer's decision. When the files already exist, reviewer columns are
carried over by key so a re-run never erases decisions.

Outputs:
  possible_duplicates_review.csv   one row per flagged pair (both records side by side)
  unconnected_cells_review.csv     one row per cell with no valid walk-network connection
  unconnected_by_barangay.csv      the same, summarised per barangay
  review.gpkg                      the same as GIS layers (cells, connectors, duplicate links)
  unconnected_cells_map.html       cells, surrounding walk network and water barriers
  possible_duplicates_map.html     the flagged pairs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
from shapely.geometry import LineString
from shapely.strtree import STRtree

from abot import accessibility as A
from abot import osm
from abot.compare import access_layer
from abot.config import Settings
from abot.report import ATTRIBUTION

log = logging.getLogger(__name__)

REVIEW_COLUMNS = ["review_status", "reviewer_decision", "reviewer_notes"]
PEDESTRIAN = {"footway", "path", "pedestrian", "steps", "track", "living_street", "corridor", "bridleway"}
# Tags that indicate a fishpond in OSM. In Iloilo most fishponds are tagged water=pond (the validity
# assessment counted 436 fishpond/aquaculture polygons), so "pond" is included.
FISHPOND = {"water=fishpond", "water=pond", "landuse=aquaculture"}


def review_dir(s: Settings) -> Path:
    return s.processed_dir / "review"


def _keep_reviewer_columns(
    new: pd.DataFrame, path: Path, key: str, match: tuple[str, ...] = ()
) -> pd.DataFrame:
    """Carry reviewer columns over from an existing file so a re-run never erases decisions.

    `match`: columns that must also be equal (duplicate ids D01, ... are positional, so a decision is
    carried only when the same OSM records still form the pair). A mismatch leaves the row pending
    and is logged, so a decision can never move to a different pair.
    """
    for c in REVIEW_COLUMNS:
        new[c] = "pending" if c == "review_status" else ""
    if not path.exists():
        return new
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    if key not in old or not set(REVIEW_COLUMNS) <= set(old.columns):
        return new
    if match and set(match) <= set(old.columns):
        cur = new.set_index(key)[list(match)].astype(str)
        prev = old.set_index(key)[list(match)].reindex(cur.index)
        moved = prev.notna().all(axis=1) & (prev != cur).any(axis=1)
        if moved.any():
            log.warning("%s: ids now name other records, decisions not carried: %s", path.name, list(moved[moved].index))
            old = old[~old[key].isin(moved[moved].index)]
    old = old.set_index(key)[REVIEW_COLUMNS]
    hit = new[key].isin(old.index)
    for c in REVIEW_COLUMNS:
        new.loc[hit, c] = new.loc[hit, key].map(old[c])
    gone = sorted(set(old.index) - set(new[key]))
    if gone:
        log.warning("%s: %d previously reviewed rows no longer flagged: %s", path.name, len(gone), gone[:10])
    return new


# --- duplicates ----------------------------------------------------------------------------------


def _tags(js) -> dict:
    try:
        return json.loads(js) if isinstance(js, str) else {}
    except json.JSONDecodeError:
        return {}


def suggest_duplicate_action(a: pd.Series, b: pd.Series, distance_m: float) -> tuple[str, str]:
    """(suggested action, likely effect if they are the same facility). Suggestions only."""
    ta, tb = _tags(a["osm_tags"]), _tags(b["osm_tags"])
    diff = sorted(k for k in set(ta) | set(tb) if ta.get(k) != tb.get(k))
    if a["subtype"] != b["subtype"]:
        action = (
            f"Different sub-types ({a['subtype']} vs {b['subtype']}) under one name: probably distinct "
            "facilities (for example a branch and its ATM). Verify on imagery or street-level photos; "
            "likely keep both."
        )
    elif a["geom_source"] != b["geom_source"]:
        action = (
            "One record is a building outline, the other a separate point. Either the same facility "
            "mapped twice or two facilities in adjacent buildings. Verify on imagery."
        )
    elif not diff:
        more = a if len(ta) >= len(tb) else b
        action = (
            f"Identical tags {distance_m:.0f} m apart: most likely the same facility mapped twice. Verify; "
            f"if confirmed, keep the more complete record ({more['fid_key']}) and mark the other as a duplicate."
        )
    else:
        action = (
            f"Same name and sub-type, different tags ({', '.join(diff[:6])}): one facility mapped twice, or "
            "two branches/entrances. Verify which record is current."
        )
    effect = (
        f"travel times: negligible (records {distance_m:.0f} m apart); facility counts n_* over-count by 1"
        if distance_m <= 50
        else "travel times may change slightly; facility counts n_* over-count by 1"
    )
    return action, effect


def duplicates_review(s: Settings, fac: gpd.GeoDataFrame, excl: pd.DataFrame, brgy) -> gpd.GeoDataFrame:
    dup = excl[excl["reason"].astype(str).str.startswith("possible duplicate")].copy()
    if dup.empty:
        return gpd.GeoDataFrame()
    if "related_osm_id" not in dup or dup["related_osm_id"].isna().any():
        # Older outputs: the related record is only named in the reason text.
        ref = dup["reason"].str.extract(r"possible duplicate of (\w+)/(\d+) \((\d+) m")
        dup["related_osm_type"], dup["related_osm_id"], dup["distance_m"] = (
            ref[0],
            ref[1],
            ref[2].astype(float),
        )
    dup["fid_a"] = dup["osm_type"].astype(str) + "/" + dup["osm_id"].astype("int64").astype(str)
    dup["fid_b"] = (
        dup["related_osm_type"].astype(str) + "/" + dup["related_osm_id"].astype("int64").astype(str)
    )

    f = fac.to_crs(4326)
    f = f.assign(lon=f.geometry.x.round(7), lat=f.geometry.y.round(7))
    j = gpd.sjoin(
        fac[["fid_key", "geometry"]], brgy[["adm4_name", "geometry"]], predicate="within", how="left"
    )
    f["barangay"] = f["fid_key"].map(j.drop_duplicates("fid_key").set_index("fid_key")["adm4_name"])
    f = f.set_index("fid_key")
    fields = [
        "name",
        "lon",
        "lat",
        "category",
        "categories",
        "subtype",
        "tier",
        "class_status",
        "class_reason",
        "geom_source",
        "inside_city",
        "barangay",
        "conn_status",
        "osm_tags",
    ]
    rows, lines = [], []
    for i, r in enumerate(dup.itertuples(), start=1):
        a, b = f.loc[r.fid_a], f.loc[r.fid_b]
        a = pd.concat([a, pd.Series({"fid_key": r.fid_a})])
        b = pd.concat([b, pd.Series({"fid_key": r.fid_b})])
        action, effect = suggest_duplicate_action(a, b, float(r.distance_m))
        row = {
            "review_id": f"D{i:02d}",
            "flagged_fid": r.fid_a,
            "related_fid": r.fid_b,
            "distance_m": r.distance_m,
        }
        for side, rec in (("flagged", a), ("related", b)):
            for c in fields:
                row[f"{side}_{c}"] = rec.get(c)
        ta, tb = _tags(a["osm_tags"]), _tags(b["osm_tags"])
        row["tags_identical"] = ta == tb
        row["tag_differences"] = "; ".join(
            f"{k}: {ta.get(k, '—')} | {tb.get(k, '—')}"
            for k in sorted(set(ta) | set(tb))
            if ta.get(k) != tb.get(k)
        )
        row["reason_flagged"] = r.reason
        row["suggested_action"] = action
        row["effect_if_duplicate"] = effect
        rows.append(row)
        lines.append(LineString([(a["lon"], a["lat"]), (b["lon"], b["lat"])]))
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=lines, crs=4326)


# --- unconnected cells ---------------------------------------------------------------------------


def _edges_gdf(s: Settings) -> gpd.GeoDataFrame:
    G = osm.load_graph(s, "walk")
    e = ox.convert.graph_to_gdfs(G, nodes=False).reset_index()
    e = e.loc[~e[["u", "v"]].apply(lambda r: tuple(sorted((r["u"], r["v"]))), axis=1).duplicated()]
    for c in ("highway", "name", "bridge", "osmid"):
        if c in e:
            e[c] = e[c].map(lambda v: ";".join(sorted(map(str, v))) if isinstance(v, list) else v)
        else:
            e[c] = None
    return e[["u", "v", "highway", "name", "bridge", "osmid", "length", "geometry"]].reset_index(drop=True)


def _barrier_label(b: pd.Series) -> str:
    detail = " ".join(f"{k}={b[k]}" for k in ("water", "landuse", "waterway", "natural") if isinstance(b.get(k), str))
    name = f" '{b['name']}'" if isinstance(b.get("name"), str) else ""
    return f"{b['osm_type']}/{b['osm_id']} {b['kind']} {detail}{name}".strip()


def crossed_barriers(
    pt, connector, bar: gpd.GeoDataFrame, tree: STRtree, radius: float, tol: float
) -> list[int]:
    """Indices of hard barriers the straight connector crosses, using the pipeline's rules."""
    zone = pt.buffer(radius) if radius > 0 else None
    hits = []
    for i in tree.query(connector, predicate="intersects"):
        b = bar.iloc[i]
        if b["kind"] == "water_line":
            inter = connector.intersection(b.geometry)
            if zone is None or not inter.difference(zone).is_empty:
                hits.append(int(i))
        elif b["kind"] == "water_area" and not b.geometry.contains(pt):
            if connector.intersection(b.geometry).length > tol:
                hits.append(int(i))
    return hits


def investigation_hint(row: dict) -> str:
    hints = []
    if row["centre_in_water_feature"]:
        if any(k in row["centre_in_water_feature"] for k in FISHPOND):
            hints.append(
                "cell centre lies in a mapped pond/fishpond polygon: check recent imagery for houses or dikes; "
                "the polygon may be outdated (record an OSM note; do not edit silently)"
            )
        else:
            hints.append(
                "cell centre lies in a mapped water area: check whether residents live here (stilt houses?)"
            )
    if row["conn_status"] == A.BLOCKED:
        kinds = row["blocking_barriers"]
        if "water_line" in kinds:
            hints.append(
                "check imagery/ground for a footbridge, crossing or culvert over the blocking watercourse"
            )
        if "coastline" in kinds:
            hints.append("coastal settlement: check for boardwalks or shore paths missing from OSM")
        if "water_area" in kinds and not row["centre_in_water_feature"]:
            hints.append("check for dikes or paths across the blocking water/fishpond area")
    else:
        hints.append(
            f"no mapped path within {row['max_connector_m']:.0f} m: check imagery for unmapped alleys or "
            "footpaths; if no dwellings are visible, the WorldPop cell may be misplaced"
        )
    if row["pop"] < 5:
        hints.append("low modelled population (< 5): possibly a modelling artefact; low priority")
    return "; ".join(hints)


def unconnected_review(s: Settings) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    cfg = s["accessibility"]["connection"]
    priority = s["reliability"].get("review_priority_barangays") or {}
    cells = gpd.read_file(s.gpkg, layer=access_layer(s.gpkg))
    brgy = gpd.read_file(s.gpkg, layer="barangays")
    bar = gpd.read_file(s.gpkg, layer="barriers")
    hard = bar[bar["kind"].isin(["water_area", "water_line"])].reset_index(drop=True)
    hard_tree = STRtree(hard.geometry.values)
    edges = _edges_gdf(s)
    etree = STRtree(edges.geometry.values)
    names = brgy.set_index("adm4_pcode")["adm4_name"]

    bad = cells[cells["conn_status"] != A.OK].copy()
    rows, connectors = [], []
    for _, c in bad.iterrows():
        pt = c.geometry
        ei, ed = etree.query_nearest(pt, return_distance=True)
        e = edges.iloc[int(ei[0])]
        cp = e.geometry.interpolate(e.geometry.project(pt))
        conn_line = LineString([pt, cp])
        near_idx = etree.query(pt, predicate="dwithin", distance=500)
        near = edges.iloc[near_idx]
        dist = shapely.distance(near.geometry.values, pt) if len(near) else np.array([])
        within_tol = near[dist <= cfg["max_connector_m"]] if len(near) else near
        ped = near[near["highway"].astype(str).str.split(";").map(lambda v: bool(set(v) & PEDESTRIAN))]
        bridges = near[near["bridge"].notna() & (near["bridge"].astype(str) != "no")]
        # Barriers blocking each candidate edge within tolerance (same rule as the pipeline)
        block = set()
        cand_idx = etree.query(pt, predicate="dwithin", distance=cfg["max_connector_m"])
        cand_d = shapely.distance(edges.geometry.values[cand_idx], pt)
        for i in cand_idx[np.argsort(cand_d)][: cfg["max_candidates"]]:
            g = edges.geometry.iloc[int(i)]
            line = LineString([pt, g.interpolate(g.project(pt))])
            block |= set(
                crossed_barriers(
                    pt, line, hard, hard_tree, cfg["origin_radius_m"], cfg["water_crossing_tolerance_m"]
                )
            )
        inside = [int(i) for i in hard_tree.query(pt, predicate="within")] if len(hard) else []
        types = near["highway"].astype(str).str.split(";").explode().value_counts()
        row = {
            "cell_id": c["cell_id"],
            "lon": None,
            "lat": None,
            "pop": round(float(c["pop"]), 1),
            "pop_census2020_adj": round(float(c.get("pop_census2020_adj", np.nan)), 1),
            "pop_wp2020": round(float(c.get("pop_wp2020", np.nan)), 1),
            "pop_wp2026": round(float(c.get("pop_wp2026", np.nan)), 1),
            "adm4_pcode": c["adm4_pcode"],
            "barangay": names.get(c["adm4_pcode"]),
            "priority_barangay": c["adm4_pcode"] in priority,
            "conn_status": c["conn_status"],
            "snapping_distance_m": round(float(ed[0]), 1),
            "max_connector_m": float(cfg["max_connector_m"]),
            "nearest_edge_osmid": e["osmid"],
            "nearest_edge_highway": e["highway"],
            "nearest_edge_name": e["name"],
            "nearest_edge_nodes": f"{e['u']}-{e['v']}",
            "candidate_edges_within_tolerance": int(len(within_tol)),
            "blocking_barriers": "; ".join(_barrier_label(hard.iloc[i]) for i in sorted(block)),
            "centre_in_water_feature": "; ".join(_barrier_label(hard.iloc[i]) for i in inside),
            "walk_edges_within_500m": int(len(near)),
            "pedestrian_edges_within_500m": int(len(ped)),
            "nearest_pedestrian_edge_m": round(float(shapely.distance(ped.geometry.values, pt).min()), 1)
            if len(ped)
            else None,
            "bridges_within_500m": int(len(bridges)),
            "highway_types_within_500m": "; ".join(f"{k} {v}" for k, v in types.items()),
        }
        if c["conn_status"] == A.BLOCKED:
            row["reason_not_connected"] = (
                f"{row['candidate_edges_within_tolerance']} walkable edge(s) within {cfg['max_connector_m']} m, but "
                f"every straight connector crosses a hard barrier ({len(block)} feature(s))"
            )
        else:
            row["reason_not_connected"] = (
                f"no walkable OSM edge within {cfg['max_connector_m']} m (nearest {row['snapping_distance_m']:.0f} m)"
            )
        row["suggested_investigation"] = investigation_hint(row)
        rows.append(row)
        connectors.append(conn_line)

    out = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=list(bad.geometry), crs=cells.crs)
    ll = out.to_crs(4326).geometry
    out["lon"], out["lat"] = ll.x.round(7), ll.y.round(7)
    out = out.sort_values(["priority_barangay", "pop"], ascending=[False, False]).reset_index(drop=True)
    conn_gdf = gpd.GeoDataFrame(
        {"cell_id": [r["cell_id"] for r in rows], "length_m": [round(g.length, 1) for g in connectors]},
        geometry=connectors,
        crs=cells.crs,
    )

    # Per-barangay summary. Cells are counted in the barangay holding most of their area; the
    # population figures are the fractional ones used by the indicators and reliability flags.
    # Unconnected residents stay in every denominator; they are reported here separately.
    ind = pd.read_csv(s.processed_dir / "barangay_access.csv", dtype={"adm4_pcode": str}).set_index("adm4_pcode")
    summ = (
        out.groupby("adm4_pcode")
        .agg(
            cells_not_connected=("cell_id", "size"),
            pop_not_connected_cells=("pop", "sum"),
            cells_barrier_blocked=("conn_status", lambda v: int((v == A.BLOCKED).sum())),
            cells_beyond_tolerance=("conn_status", lambda v: int((v == A.BEYOND).sum())),
        )
        .reset_index()
    )
    # Every barangay with unconnected residents, including those that only hold part of such a cell.
    base = ind.loc[ind["pop_not_connected"] > 0, ["pop_total", "pop_not_connected", "pct_not_connected", "rel_network"]]
    summ = base.reset_index().merge(summ, on="adm4_pcode", how="left")
    counts = ["cells_not_connected", "cells_barrier_blocked", "cells_beyond_tolerance"]
    summ[counts] = summ[counts].fillna(0).astype(int)
    summ["pop_not_connected_cells"] = summ["pop_not_connected_cells"].fillna(0).round(1)
    summ.insert(1, "barangay", summ["adm4_pcode"].map(names))
    summ["priority_barangay"] = summ["adm4_pcode"].isin(list(priority))
    summ = summ.sort_values(["priority_barangay", "pop_not_connected"], ascending=[False, False])
    return out, conn_gdf, summ


# --- maps --------------------------------------------------------------------------------------------


def _base_map(gdf4326) -> folium.Map:
    c = gdf4326.union_all().centroid
    m = folium.Map(location=[c.y, c.x], zoom_start=14, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Imagery (Esri)",
    ).add_to(m)
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;bottom:4px;left:4px;z-index:9999;background:rgba(255,255,255,.85);'
            f'padding:2px 6px;font:11px sans-serif;max-width:70%">ABOT review · {ATTRIBUTION}</div>'
        )
    )
    return m


def unconnected_map(s: Settings, cells: gpd.GeoDataFrame, connectors: gpd.GeoDataFrame, path: Path) -> None:
    brgy = gpd.read_file(s.gpkg, layer="barangays")
    bar = gpd.read_file(s.gpkg, layer="barriers")
    edges = gpd.read_file(s.gpkg, layer="network_walk")
    priority = s["reliability"].get("review_priority_barangays") or {}
    area = cells.buffer(600).union_all()
    edges = edges[edges.intersects(area)]
    edges = edges.loc[
        ~edges[["u", "v"]].apply(lambda r: tuple(sorted((r["u"], r["v"]))), axis=1).duplicated()
    ]
    bar = bar[bar.intersects(area) & bar["kind"].isin(["water_area", "water_line", "wall"])]

    m = _base_map(cells.to_crs(4326))
    b = brgy.to_crs(4326)
    b["geometry"] = b.geometry.simplify(0.00003)
    folium.GeoJson(
        b[["adm4_name", "geometry"]],
        name="Barangays",
        style_function=lambda f: {"fill": False, "color": "#555", "weight": 0.7},
        tooltip=folium.GeoJsonTooltip(["adm4_name"], aliases=["Barangay"]),
    ).add_to(m)
    pb = b[b["adm4_pcode"].isin(list(priority))]
    folium.GeoJson(
        pb[["adm4_name", "geometry"]],
        name="Priority barangays",
        style_function=lambda f: {
            "fillColor": "#ffff00",
            "fillOpacity": 0.08,
            "color": "#ff00ff",
            "weight": 3,
        },
        tooltip=folium.GeoJsonTooltip(["adm4_name"], aliases=["Priority barangay"]),
    ).add_to(m)

    wa = bar[bar["kind"] == "water_area"].to_crs(4326)
    wl = bar[bar["kind"].isin(["water_line", "wall"])].to_crs(4326)
    cols = [
        c
        for c in ("osm_type", "osm_id", "kind", "natural", "water", "landuse", "waterway", "name")
        if c in bar
    ]
    if len(wa):
        folium.GeoJson(
            wa[[*cols, "geometry"]],
            name="Water areas / fishponds (hard barrier)",
            style_function=lambda f: {
                "fillColor": "#3182bd",
                "fillOpacity": 0.35,
                "color": "#08519c",
                "weight": 0.5,
            },
            tooltip=folium.GeoJsonTooltip(cols),
        ).add_to(m)
    if len(wl):
        folium.GeoJson(
            wl[[*cols, "geometry"]],
            name="Watercourses / coastline (hard) and walls (flag)",
            style_function=lambda f: {
                "color": "#7f7f7f" if f["properties"]["kind"] == "wall" else "#08519c",
                "weight": 2 if f["properties"]["kind"] == "wall" else 3,
            },
            tooltip=folium.GeoJsonTooltip(cols),
        ).add_to(m)
    e = edges.to_crs(4326)
    e["ped"] = e["highway"].astype(str).str.split(";").map(lambda v: bool(set(v) & PEDESTRIAN))
    folium.GeoJson(
        e[["highway", "name", "ped", "geometry"]],
        name="Walk network (OSM)",
        style_function=lambda f: {"color": "#31a354" if f["properties"]["ped"] else "#e6550d", "weight": 2},
        tooltip=folium.GeoJsonTooltip(["highway", "name"]),
    ).add_to(m)
    folium.GeoJson(
        connectors.to_crs(4326),
        name="Line to nearest walk edge (not used: rejected or too long)",
        style_function=lambda f: {"color": "#000", "weight": 1.5, "dashArray": "4 4"},
    ).add_to(m)

    sq = cells.copy()
    sq["geometry"] = sq.geometry.buffer(46, cap_style="square")  # approximate 92 m cell outline
    show = [
        "cell_id",
        "barangay",
        "pop",
        "conn_status",
        "snapping_distance_m",
        "blocking_barriers",
        "centre_in_water_feature",
        "pedestrian_edges_within_500m",
        "reason_not_connected",
        "suggested_investigation",
    ]
    sq = sq.to_crs(4326)
    colour = {A.BLOCKED: "#d7301f", A.BEYOND: "#7a0177"}
    folium.GeoJson(
        sq[[*show, "geometry"]],
        name="Unconnected population cells",
        style_function=lambda f: {
            "fillColor": colour.get(f["properties"]["conn_status"], "#000"),
            "fillOpacity": 0.55,
            "color": "#000",
            "weight": 1,
        },
        tooltip=folium.GeoJsonTooltip(show),
    ).add_to(m)
    legend = (
        '<div style="position:fixed;top:8px;left:50px;z-index:9999;background:rgba(255,255,255,.92);'
        'padding:6px 8px;font:12px sans-serif;max-width:430px"><b>Unconnected population cells (review)</b><br>'
        '<span style="color:#d7301f">&#9632;</span> barrier_blocked: every nearby path across water/coastline<br>'
        '<span style="color:#7a0177">&#9632;</span> beyond_tolerance: no mapped path within '
        f"{s['accessibility']['connection']['max_connector_m']} m<br>"
        '<span style="color:#31a354">&#9644;</span> footway/path &nbsp; <span style="color:#e6550d">&#9644;</span> road '
        '&nbsp; <span style="color:#08519c">&#9644;</span> water barrier &nbsp; dashed: line to nearest edge<br>'
        "Magenta outline: priority barangays. Nothing here changes the analysis; these residents stay in "
        "every denominator and are reported as not connected.</div>"
    )
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(path)


def duplicates_map(dups: gpd.GeoDataFrame, path: Path) -> None:
    m = _base_map(dups)
    folium.GeoJson(
        dups[["review_id", "distance_m", "geometry"]],
        name="Pair link",
        style_function=lambda f: {"color": "#d7301f", "weight": 3},
    ).add_to(m)
    for _, r in dups.iterrows():
        for side, colour in (("flagged", "#d7301f"), ("related", "#2171b5")):
            folium.CircleMarker(
                [r[f"{side}_lat"], r[f"{side}_lon"]],
                radius=6,
                color=colour,
                fill=True,
                fill_opacity=0.8,
                tooltip=(
                    f"{r['review_id']} {side}: {r[f'{side}_name']} ({r[f'{side}_fid' if side == 'flagged' else 'related_fid']}); "
                    f"{r[f'{side}_category']}.{r[f'{side}_subtype']}; {r['distance_m']} m apart. "
                    f"Suggested: {r['suggested_action']}"
                ),
            ).add_to(m)
    folium.LayerControl().add_to(m)
    m.save(path)


def write_readme(path: Path, n_dup: int, n_cells: int, pop: float) -> None:
    path.write_text(
        f"""# Manual review files (generated by `abot review`; nothing here has been applied)

Rows start as `review_status = pending`. No pipeline stage reads these files: records are **not**
merged, deleted, excluded, reclassified or reconnected until a reviewer's decision is implemented
deliberately in a later, documented change. Re-running `abot review` keeps the reviewer columns
(`review_status`, `reviewer_decision`, `reviewer_notes`) for rows that are still flagged; a duplicate
decision is kept only while the same two OSM records form the pair. Approved decisions are entered
with `review.record_duplicate_decisions` and logged, with the values before and after and the
original row, in `review_decisions_log.csv` (reversible with `review.revert_duplicate_decision`).

| File | Rows | What to decide |
|---|---|---|
| `possible_duplicates_review.csv` | {n_dup} flagged pairs | same facility mapped twice, or distinct facilities? |
| `unconnected_cells_review.csv` | {n_cells} cells, {pop:,.0f} residents | real barrier, missing OSM path/bridge, outdated fishpond polygon, or misplaced population? |
| `unconnected_by_barangay.csv` | per barangay | (summary) |
| `review.gpkg` | GIS layers of the above | open in QGIS with imagery |
| `unconnected_cells_map.html`, `possible_duplicates_map.html` | maps | (imagery layer included) |

Suggested `reviewer_decision` values. Duplicates: `same_keep_flagged`, `same_keep_related`,
`likely_duplicate_not_merged` (same facility likely, no record chosen, nothing merged),
`distinct_keep_both`, `unsure`. Cells: `real_barrier`, `missing_osm_path`, `missing_osm_bridge`,
`outdated_water_polygon`, `no_dwellings_visible`, `unsure`.

Population columns: `pop` is the primary weight (census-adjusted 2020 by default); `pop_wp2020` and
`pop_wp2026` are the original WorldPop estimates for the in-city part of the cell.
""",
        encoding="utf-8",
    )


# --- recording approved decisions (explicit, logged, reversible) ---------------------------------

DUPLICATES_FILE = "possible_duplicates_review.csv"
DECISION_LOG = "review_decisions_log.csv"


def _log_rows(s: Settings) -> pd.DataFrame:
    p = review_dir(s) / DECISION_LOG
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame()


def record_duplicate_decisions(s: Settings, decisions: dict[str, dict], approval: str) -> pd.DataFrame:
    """Write reviewer columns for approved duplicate pairs. Nothing is merged or deleted.

    `decisions`: review_id -> {flagged_fid, related_fid, decision, notes, rationale}. Every pair is
    checked first: the row must exist, name exactly these OSM records, and still be `pending`. If any
    check fails nothing is written. Each change is appended to review_decisions_log.csv with the
    values before and after and the full original row (coordinates, tags) as provenance.
    """
    path = review_dir(s) / DUPLICATES_FILE
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    idx = df.set_index("review_id")
    problems = []
    for rid, d in decisions.items():
        if rid not in idx.index:
            problems.append(f"{rid}: no such row")
            continue
        r = idx.loc[rid]
        if (r["flagged_fid"], r["related_fid"]) != (d["flagged_fid"], d["related_fid"]):
            problems.append(f"{rid}: row names {r['flagged_fid']} / {r['related_fid']}, not the approved records")
        if r["review_status"] != "pending" or r["reviewer_decision"]:
            problems.append(f"{rid}: already decided ({r['review_status']}, {r['reviewer_decision']})")
    if problems:
        raise ValueError("no decision recorded: " + "; ".join(problems))
    now = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    log_rows = []
    for rid, d in sorted(decisions.items()):
        i = df.index[df["review_id"] == rid][0]
        before = {c: df.at[i, c] for c in REVIEW_COLUMNS}
        after = {"review_status": "reviewed", "reviewer_decision": d["decision"], "reviewer_notes": d["notes"]}
        log_rows.append(
            {
                "logged_utc": now, "action": "record", "file": DUPLICATES_FILE, "review_id": rid,
                "flagged_fid": d["flagged_fid"], "related_fid": d["related_fid"],
                **{f"before_{c}": before[c] for c in REVIEW_COLUMNS},
                **{f"after_{c}": after[c] for c in REVIEW_COLUMNS},
                "approval": approval, "rationale": d["rationale"],
                "original_row_json": json.dumps(df.loc[i].to_dict(), ensure_ascii=False),
            }
        )  # fmt: skip
        for c in REVIEW_COLUMNS:
            df.at[i, c] = after[c]
    df.to_csv(path, index=False)
    log = pd.concat([_log_rows(s), pd.DataFrame(log_rows)], ignore_index=True)
    log.to_csv(review_dir(s) / DECISION_LOG, index=False)
    return pd.DataFrame(log_rows)


def revert_duplicate_decision(s: Settings, review_id: str, reason: str) -> None:
    """Restore the reviewer columns a logged decision replaced (only if they are still as recorded)."""
    log = _log_rows(s)
    rec = log[(log["review_id"] == review_id) & (log["action"] == "record")]
    if rec.empty:
        raise ValueError(f"{review_id}: no recorded decision to revert")
    last = rec.iloc[-1]
    path = review_dir(s) / DUPLICATES_FILE
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    i = df.index[df["review_id"] == review_id][0]
    if any(df.at[i, c] != last[f"after_{c}"] for c in REVIEW_COLUMNS):
        raise ValueError(f"{review_id}: current values differ from the logged decision; not reverted")
    entry = {**last.to_dict(), "logged_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
             "action": "revert", "rationale": reason}  # fmt: skip
    for c in REVIEW_COLUMNS:
        df.at[i, c] = last[f"before_{c}"]
        entry[f"before_{c}"], entry[f"after_{c}"] = last[f"after_{c}"], last[f"before_{c}"]
    df.to_csv(path, index=False)
    pd.concat([log, pd.DataFrame([entry])], ignore_index=True).to_csv(review_dir(s) / DECISION_LOG, index=False)


def build(s: Settings) -> None:
    out = review_dir(s)
    out.mkdir(parents=True, exist_ok=True)
    gpkg = out / "review.gpkg"
    if gpkg.exists():
        gpkg.unlink()  # derived file, fully rewritten (the CSVs hold reviewer decisions)

    brgy = gpd.read_file(s.gpkg, layer="barangays")
    fac = gpd.read_file(s.gpkg, layer="facilities")
    excl = pd.read_csv(s.processed_dir / "facility_exclusions.csv")
    dups = duplicates_review(s, fac, excl, brgy)
    if len(dups):
        p = out / "possible_duplicates_review.csv"
        table = _keep_reviewer_columns(
            pd.DataFrame(dups.drop(columns="geometry")), p, "review_id", match=("flagged_fid", "related_fid")
        )
        table.to_csv(p, index=False)
        dups.to_file(gpkg, layer="duplicate_pairs", driver="GPKG")
        duplicates_map(dups, out / "possible_duplicates_map.html")

    cells, connectors, summ = unconnected_review(s)
    p = out / "unconnected_cells_review.csv"
    table = _keep_reviewer_columns(pd.DataFrame(cells.drop(columns="geometry")), p, "cell_id")
    table.to_csv(p, index=False)
    summ.to_csv(out / "unconnected_by_barangay.csv", index=False)
    cells.to_file(gpkg, layer="unconnected_cells", driver="GPKG")
    connectors.to_file(gpkg, layer="unconnected_nearest_edge_lines", driver="GPKG")
    unconnected_map(s, cells, connectors, out / "unconnected_cells_map.html")
    write_readme(out / "README.md", len(dups), len(cells), float(cells["pop"].sum()))
    log.info(
        "review files written to %s (%d duplicate pairs, %d unconnected cells)", out, len(dups), len(cells)
    )
