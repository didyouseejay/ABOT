"""Milestone 04: walk-network component inventory, network-approach comparison, access-tag impact.

`abot components` READS the Overpass cache (offline: a cache miss raises), the baseline outputs and
the Milestone 03 review files, and writes evidence tables to <processed>/review/m04/. It changes no
network, no indicator and no review decision. Every scenario below is computed side by side with
the baseline using the baseline's own connection and routing functions (accessibility.py), so the
only thing that differs between scenarios is the graph and the attachment rule.

Phase B: component inventory and three approaches
  A1 baseline         largest weakly connected component only (the active method)
  A2 all_eligible     every eligible component kept; cells and facilities attach to the nearest
                      eligible edge; one travel time per cell to whatever facility its component
                      reaches (internal and citywide times are mixed in one indicator)
  A3 component_aware  as A2 for cells, plus access-uncertain components; each facility ALSO keeps its
                      baseline main-network connection; cells are labelled network_connected /
                      locally_connected / access_uncertain / unconnected, and citywide indicators
                      use network_connected cells only. Internal (within-component) times of the
                      other cells are reported separately and never as citywide access.
  No link is ever added between components. A verified-connection scenario exists only where
  evidence supports a link (none in the cache; see gap_investigation.csv).

Phase C: access classification (way tags + gate nodes) and, per restriction tag, the effect of
removing those edges from the baseline network (C1: analysis only, not applied).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
from shapely.geometry import Point

from abot import accessibility as A
from abot import osm, review, validation
from abot.access import (  # noqa: F401  (re-exported: the M04 tables and tests use these names)
    ACCESS_CLASSES,
    CUSTOMERS_UNKNOWN,
    POLICY,
    PUBLIC_PEDESTRIAN,
    PUBLIC_VALUES,
    RANK,
    RESTRICTED,
    access_assessment,
    access_class,
    gate_tag_flags,
    most_restrictive,
    way_tag_flags,
)
from abot.config import Settings

log = logging.getLogger(__name__)

# Calahunan and Hibao-an Sur were resolved separately (M03 §4.1a): excluded from M04 tables.
EXCLUDED_BARANGAYS = {"PH0603022030": "Calahunan", "PH0603022067": "Hibao-an Sur"}
FOCUS_BARANGAYS = {"PH0603022201": "Tabuc Suba (La Paz)", "PH0603022017": "Baybay Tanza"}

# The access taxonomy lives in abot.access (shared with the targeted-snapshot corridor analysis).
# Approved for analysis and reporting only; routing is NOT changed (see docs/METHODOLOGY.md §3.1).
GATE_BARRIERS = {"gate", "swing_gate", "sliding_gate", "lift_gate"}
PED_INFRA = {"footway", "path", "pedestrian", "steps", "corridor"}
TAG_SCENARIOS = {
    "access=no": "way access=no without a more specific foot tag",
    "foot=no": "way foot=no (osmnx removes these before download)",
    "foot=private": "way foot=private",
    "access=private": "way access=private (osmnx removes these before download)",
    "access=destination": "way access=destination",
    "access=customers": "way access=customers",
    "gate private": "edge carries a gate node with access=private/residents or foot=residents (flag for review)",
    "gate ineligible": "edge carries a gate node with access=no (no foot tag), foot=no or foot=private",
    "gate untagged": "edge carries a gate node with no access/foot tag (not excluded by the policy)",
}
COMBINED = {
    "combined ineligible + private gates (access=no, foot=no/private, private and ineligible gates)": [
        "access=no", "foot=no", "foot=private", "gate private", "gate ineligible",
    ],
}  # fmt: skip
NEAR_MISS_M = 20
GEOMETRY_ERROR_M = 2.0
LOCAL_NETWORK_KM = 0.5
REPORT_GROUPS = ["health_hospital", "health_primary_care", "education_basic", "market_public", "pharmacy"]


def m04_dir(s: Settings) -> Path:
    return review.review_dir(s) / "m04"


# --- tags from the cached walk response ---------------------------------------------------------


def walk_cache_elements(s: Settings) -> tuple[dict, dict]:
    """(way id -> way element, node id -> node element) from the cached walk-network response."""
    prov = json.loads((s.interim_dir / "osm_provenance.json").read_text(encoding="utf-8"))
    files = [r["cache_file"] for r in prov["responses"] if r["label"] == "network_walk"]
    ways, nodes = {}, {}
    for f in files:
        for e in json.loads((s.raw_dir / f).read_text(encoding="utf-8"))["elements"]:
            (ways if e["type"] == "way" else nodes if e["type"] == "node" else {})[e["id"]] = e
    return ways, nodes


def _ids(v) -> list[int]:
    return [int(x) for x in v] if isinstance(v, list) else [int(v)]


def edge_table(G: nx.MultiDiGraph, ways: dict, nodes: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per directed edge with its way access class, tag flags and gates; and the gate table."""
    rows = []
    for u, v, k, d in G.edges(keys=True, data=True):
        wids = _ids(d["osmid"])
        tags = [ways.get(w, {}).get("tags", {}) for w in wids]
        classes = [access_class(t) for t in tags]
        flags = set().union(*(way_tag_flags(t) for t in tags))
        hw = d.get("highway")
        rows.append(
            {
                "u": u, "v": v, "k": k, "osmids": wids, "length": float(d["length"]),
                "highway": ";".join(sorted(hw)) if isinstance(hw, list) else hw,
                "way_class": most_restrictive(classes),
                "mixed_classes": len(set(classes)) > 1,
                "flags": flags,
            }
        )  # fmt: skip
    e = pd.DataFrame(rows)

    # Gate nodes: simplification removes interstitial nodes, so a gate is matched to the edge whose
    # geometry passes within 1 m of it AND whose OSM ways contain the gate node.
    edge_geoms = []
    for u, v, _k, d in G.edges(keys=True, data=True):
        g = d.get("geometry")
        if g is None:
            g = shapely.LineString([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])
        edge_geoms.append(g)
    tree = shapely.STRtree(edge_geoms)
    node_ways: dict[int, set] = {}
    for w in ways.values():
        for n in w.get("nodes", []):
            node_ways.setdefault(n, set()).add(w["id"])
    gates = [
        n for n in nodes.values()
        if n.get("tags", {}).get("barrier") in GATE_BARRIERS and n["id"] in node_ways
    ]  # fmt: skip
    pts = gpd.GeoSeries([Point(n["lon"], n["lat"]) for n in gates], crs=4326).to_crs(G.graph["crs"])
    e["gates"] = [[] for _ in range(len(e))]
    grow = []
    for n, p in zip(gates, pts, strict=True):
        hit = [
            i for i in tree.query(p, predicate="dwithin", distance=1.0)
            if node_ways[n["id"]] & set(e.at[i, "osmids"])
        ]  # fmt: skip
        a = access_assessment(n["tags"], gate=True)
        cls, flags = a.pop("mapped_access_status"), gate_tag_flags(n["tags"])
        for i in hit:
            e.at[i, "gates"].append(cls)
            e.at[i, "flags"].update(flags)  # each row holds its own set
        grow.append(
            {
                "node": n["id"], "barrier": n["tags"]["barrier"], "access": n["tags"].get("access"),
                "foot": n["tags"].get("foot"), "locked": n["tags"].get("locked"), "gate_class": cls,
                "lon": n["lon"], "lat": n["lat"],
                "is_graph_node": n["id"] in G.nodes, "junction": n["id"] in G.nodes and G.degree(n["id"]) > 4,
                "directed_edges_matched": len(hit),
                "edge_u": e.at[min(hit), "u"] if hit else None,  # gates mid-way are not graph nodes
                "flag_for_review": cls in RESTRICTED,
                **a,
            }
        )  # fmt: skip
    e["gate_class"] = [most_restrictive(g) if g else "" for g in e["gates"]]
    return e, pd.DataFrame(grow)


# --- evaluation of one graph + attachment rule ---------------------------------------------------


def set_walk_time(G: nx.MultiDiGraph, mps: float) -> None:
    nx.set_edge_attributes(G, {(u, v, k): d["length"] / mps for u, v, k, d in G.edges(keys=True, data=True)}, "travel_time")


def ordered_components(G: nx.MultiDiGraph) -> list[set]:
    """Weakly connected components, largest first, ties by smallest node id (deterministic)."""
    return sorted(nx.weakly_connected_components(G), key=lambda c: (-len(c), min(c)))


def evaluate(
    s: Settings,
    G: nx.MultiDiGraph,
    cells: gpd.GeoDataFrame,
    roles: gpd.GeoDataFrame,
    checker: A.BarrierChecker,
    extra_fac_graph: nx.MultiDiGraph | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Connect cells and facilities to G and compute walk minutes per indicator group.

    Returns (per-cell frame: status, conn_m, u, network_node (in G's largest component), t_walk_*;
    facility connections). With `extra_fac_graph`, each facility also keeps a connection to that
    graph (A3: the main network), so a facility next to a fragment stays a citywide destination.
    Facility connections are destinations only: routes never pass through a facility, so no link
    between components is created.
    """
    cfg = s["accessibility"]["connection"]
    mps = s["accessibility"]["walk_speed_kmh"] / 3.6
    edges = A.EdgeIndex(G)
    cc = A.connect_points(cells.geometry, edges, checker, cfg, cfg["origin_radius_m"])
    fac_pts = roles.drop_duplicates("fid_key").set_index("fid_key")
    fc = A.connect_points(fac_pts.geometry, edges, checker, cfg, cfg["facility_radius_m"], cfg["facility_max_connector_m"])
    if extra_fac_graph is not None:
        fm = A.connect_points(
            fac_pts.geometry, A.EdgeIndex(extra_fac_graph), checker, cfg, cfg["facility_radius_m"],
            cfg["facility_max_connector_m"],
        )  # fmt: skip
        same = (fm["u"] == fc["u"]) & (fm["v"] == fc["v"])
        fc = pd.concat([fc, fm[~same & (fm["status"] == A.OK)]])
    main = ordered_components(G)[0]
    out = pd.DataFrame(index=cells.index)
    out["status"] = cc["status"]
    out["conn_m"] = cc["conn_m"].round(1)
    out["u"] = cc["u"]
    out["v"] = cc["v"]
    out["network_node"] = [u in main if st == A.OK else False for u, st in zip(cc["u"], cc["status"], strict=True)]
    GR = G.reverse(copy=True)
    for gname in s["indicator_groups"]:
        sub = fc.loc[fc.index.intersection(A.group_facilities(s, roles, gname)["fid_key"])]
        out[f"t_walk_{gname}"] = (A.walk_times(GR, cc, sub, mps) / 60).round(2)
    return out, fc


# --- component inventory (B1) -------------------------------------------------------------------


def classify_component(r: dict) -> tuple[str, str]:
    """(class, reason). First match wins; thresholds are documented desk heuristics."""
    if r["fragment"] == "main":
        return "main", "largest weakly connected component (the active network)"
    if r["gap_crosses_water"]:
        return "separated_by_water", f"shortest gap to the main network crosses {r['gap_crosses_water']}"
    if r["share_restricted"] >= 0.5:
        return "restricted_access", "at least half the length is mapped no, private or residents"
    if r["share_customers_uncertain"] >= 0.5 or r["gates_restricted"] > 0:
        return "access_uncertain", "mostly customers/unknown access, or a gate mapped no, private or residents"
    if r["noexit_at_gap"]:
        return "isolated_mapped_dead_end", "noexit=yes at the gap: a mapper asserted there is no link there"
    if r["gap_to_main_m"] <= GEOMETRY_ERROR_M:
        return "likely_geometry_error", f"within {GEOMETRY_ERROR_M} m of the main network but not joined"
    if r["length_km"] >= LOCAL_NETWORK_KM:
        return "isolated_local_network", f"at least {LOCAL_NETWORK_KM} km of public/untagged ways"
    return "small_fragment", f"under {LOCAL_NETWORK_KM} km"


ELIGIBLE_A2 = {"main", "separated_by_water", "isolated_mapped_dead_end", "likely_geometry_error",
               "isolated_local_network", "small_fragment"}  # fmt: skip
ELIGIBLE_A3 = ELIGIBLE_A2 | {"access_uncertain"}

# The access-taxonomy revision (M04 methodology review) relabels access statuses only. Every component
# must keep its class and the inputs of its class rule exactly; the pre-revision inventory is archived.
TAXONOMY_REFERENCE = "review_m04_pre_access_taxonomy"
INVARIANT_COLUMNS = ["component_class", "n_nodes", "n_edges", "length_km", "gates_restricted", "gates_untagged",
                     "share_restricted", "share_customers_uncertain", "gap_to_main_m", "noexit_at_gap"]  # fmt: skip


def compare_component_classes(reference: pd.DataFrame, inv: pd.DataFrame) -> dict:
    """Exact per-component equality of the class and its rule inputs against a reference inventory.
    Raises on any difference (a deliberate class change needs a new reference, not a silent rerun)."""
    old, new = reference.set_index("fragment"), inv.set_index("fragment")
    if set(old.index) != set(new.index):
        raise RuntimeError(f"component ids differ from the reference: {sorted(set(old.index) ^ set(new.index))[:10]}")
    cols = [c for c in INVARIANT_COLUMNS if c in old.columns]
    diff = [
        f"{f} {c}: {old.at[f, c]!r} -> {new.at[f, c]!r}"
        for f in old.index for c in cols
        if not (old.at[f, c] == new.at[f, c] or (pd.isna(old.at[f, c]) and pd.isna(new.at[f, c])))
    ]  # fmt: skip
    if diff:
        raise RuntimeError(f"component classification changed against the reference: {diff[:10]}")
    return {"components_compared": len(old), "columns_compared": cols, "identical": True}


def component_inventory(
    s: Settings, G_all, comps: list[set], et: pd.DataFrame, nodes: dict, bar: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    main = comps[0]
    frag = {n: f"F{i:03d}" for i, c in enumerate(comps[1:], start=1) for n in c}
    main_edges = ox.convert.graph_to_gdfs(G_all.subgraph(main), nodes=False).reset_index()
    frags, gaps = validation.fragments_table(s, G_all, frag, main_edges, bar)
    frags = frags.set_index("fragment")
    gaps = gaps.set_index("fragment")
    noexit = [Point(n["lon"], n["lat"]) for n in nodes.values() if n.get("tags", {}).get("noexit") == "yes"]
    nx_tree = shapely.STRtree(gpd.GeoSeries(noexit, crs=4326).to_crs(s.projected_crs).values)
    city = gpd.read_file(s.gpkg, layer="city").to_crs(s.projected_crs).union_all()

    comp_of = {n: "main" for n in main} | frag
    et = et.assign(comp=et["u"].map(comp_of))
    rows = []
    by_comp = dict(tuple(et.groupby("comp", sort=False)))
    members: dict[str, set] = {}
    for n, f in frag.items():
        members.setdefault(f, set()).add(n)
    for cid in ["main", *(f"F{i:03d}" for i in range(1, len(comps)))]:
        g = by_comp.get(cid, et.iloc[0:0])  # a component can be a lone node with no edge
        nodes_c = main if cid == "main" else members[cid]
        km = g["length"].sum() / 2000  # both directions of every walk edge
        by_cls = g.groupby("way_class")["length"].sum() / 2000
        xs = [G_all.nodes[n]["x"] for n in nodes_c]
        ys = [G_all.nodes[n]["y"] for n in nodes_c]
        bb = gpd.GeoSeries([shapely.box(min(xs), min(ys), max(xs), max(ys))], crs=s.projected_crs).to_crs(4326).total_bounds
        gate_counts = pd.Series([c for gl in g["gates"] for c in gl]).value_counts() / 2
        r = {
            "fragment": cid,
            "n_nodes": len(nodes_c),
            "n_edges": len(g) // 2,
            "length_km": round(km, 2),
            "km_inside_city": None,
            "lon_min": round(bb[0], 6), "lat_min": round(bb[1], 6), "lon_max": round(bb[2], 6), "lat_max": round(bb[3], 6),
            "extent_m": round(float(np.hypot(max(xs) - min(xs), max(ys) - min(ys))), 0),
            "ped_infra_km": round(g.loc[g["highway"].fillna("").str.split(";").map(lambda h: bool(PED_INFRA & set(h))), "length"].sum() / 2000, 2),
            **{f"km_{c}": round(float(by_cls.get(c, 0.0)), 2) for c in ACCESS_CLASSES},
            "gates_restricted": int(sum(gate_counts.get(c, 0) for c in RESTRICTED)),
            "gates_untagged": int(gate_counts.get("untagged", 0)),
            "share_restricted": round(float(sum(by_cls.get(c, 0) for c in RESTRICTED) / km), 3) if km else 0.0,
            "share_customers_uncertain": round(float(sum(by_cls.get(c, 0) for c in CUSTOMERS_UNKNOWN) / km), 3) if km else 0.0,
        }  # fmt: skip
        if cid == "main":
            r.update(gap_to_main_m=0.0, gap_crosses_water="", noexit_at_gap=False, highway_types="", names="",
                     km_inside_city=None, touches_extraction_edge=True)  # fmt: skip
        elif cid not in frags.index:  # lone node: no way geometry, gap measured from the node
            p = Point(xs[0], ys[0])
            r.update(
                gap_to_main_m=round(float(main_edges.distance(p).min()), 1), gap_crosses_water="",
                noexit_at_gap=bool(len(nx_tree.query(p, predicate="dwithin", distance=3.0))),
                highway_types="(no edge)", names="", km_inside_city=0.0,
                touches_extraction_edge=False,
            )  # fmt: skip
        else:
            f, gap = frags.loc[cid], gaps.loc[cid].geometry
            ends = [Point(gap.coords[0]), Point(gap.coords[-1])]
            r.update(
                gap_to_main_m=float(f["gap_to_main_m"]),
                gap_crosses_water=f["gap_crosses_water"] or "",
                noexit_at_gap=any(len(nx_tree.query(p, predicate="dwithin", distance=3.0)) for p in ends),
                highway_types=f["highway_types"], names=f["names"], km_inside_city=float(f["km_inside_city"]),
                touches_extraction_edge=bool(f["touches_extraction_edge"]),
            )  # fmt: skip
        rows.append(r)
    inv = pd.DataFrame(rows)
    main_geom = main_edges.geometry.union_all()
    inv.loc[inv["fragment"] == "main", "km_inside_city"] = round(main_geom.intersection(city).length / 1000, 2)
    cls = [classify_component(r) for r in inv.to_dict("records")]
    inv["component_class"] = [c for c, _ in cls]
    inv["class_reason"] = [r for _, r in cls]
    inv["retained_A2"] = inv["component_class"].isin(ELIGIBLE_A2)
    inv["retained_A3"] = inv["component_class"].isin(ELIGIBLE_A3)
    inv["order"] = inv["fragment"].map(lambda f: -1 if f == "main" else int(f[1:]))
    return inv.sort_values("order").drop(columns="order").reset_index(drop=True)


def near_misses(s: Settings, G_all, comps: list[set], nodes: dict) -> pd.DataFrame:
    """Dead ends of fragments that lie within NEAR_MISS_M of the main network ("roads that stop short")."""
    main = comps[0]
    frag = {n: f"F{i:03d}" for i, c in enumerate(comps[1:], start=1) for n in c}
    main_edges = ox.convert.graph_to_gdfs(G_all.subgraph(main), nodes=False).reset_index()
    tree = shapely.STRtree(main_edges.geometry.values)
    rows = []
    for n, f in sorted(frag.items(), key=lambda x: (x[1], x[0])):
        if len(set(G_all.successors(n)) | set(G_all.predecessors(n))) != 1:
            continue
        p = Point(G_all.nodes[n]["x"], G_all.nodes[n]["y"])
        i, d = tree.query_nearest(p, return_distance=True)
        if d[0] > NEAR_MISS_M:
            continue
        me = main_edges.iloc[int(i[0])]
        ll = gpd.GeoSeries([p], crs=s.projected_crs).to_crs(4326).iloc[0]
        rows.append(
            {
                "fragment": f, "dead_end_node": n, "lon": round(ll.x, 6), "lat": round(ll.y, 6),
                "dist_to_main_m": round(float(d[0]), 1), "dead_end_tags": json.dumps(nodes.get(n, {}).get("tags", {})),
                "main_edge_osmid": validation._label(me["osmid"]), "main_edge_highway": validation._label(me["highway"]),
                "main_edge_name": validation._label(me.get("name")),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


# --- summaries -----------------------------------------------------------------------------------


def _w(cells, mask) -> float:
    return round(float(cells.loc[mask, "pop"].sum()), 1)


def approach_summary(s: Settings, name: str, cells, res: pd.DataFrame, category: pd.Series, G, n_comp: int) -> list[dict]:
    total = float(cells["pop"].sum())
    rows = [{
        "approach": name, "group": "_population", "components_retained": n_comp,
        "network_km": round(sum(d["length"] for *_, d in G.edges(data=True)) / 2000, 1),
        **{f"cells_{c}": int((category == c).sum()) for c in CATEGORIES},
        **{f"pop_{c}": _w(cells, category == c) for c in CATEGORIES},
    }]  # fmt: skip
    citywide = (category == "network_connected").to_numpy()
    for g in s["indicator_groups"]:
        t = res[f"t_walk_{g}"].to_numpy(dtype=float)
        w = cells["pop"].to_numpy(dtype=float)
        # A2 mixes internal and citywide times in one indicator (that is the approach); A1/A3 use
        # citywide (network-connected) times only.
        use = (~np.isnan(t)) & (citywide if name != "A2_all_eligible" else res["status"].eq(A.OK).to_numpy())
        loc = (~np.isnan(t)) & (category != "network_connected").to_numpy() & res["status"].eq(A.OK).to_numpy()
        rows.append(
            {
                "approach": name, "group": g,
                "mean_min": round(float(np.average(t[use], weights=w[use])), 2) if use.any() else np.nan,
                "pct_le15_all_residents": round(100 * w[use & (t <= 15)].sum() / total, 2),
                "pct_le30_all_residents": round(100 * w[use & (t <= 30)].sum() / total, 2),
                "pop_with_time": round(float(w[use].sum()), 1),
                "pop_local_with_internal_time": round(float(w[loc].sum()), 1),
                "pop_local_internal_le15": round(float(w[loc & (t <= 15)].sum()), 1),
            }
        )  # fmt: skip
    return rows


CATEGORIES = ["network_connected", "locally_connected", "access_uncertain", "unconnected"]


def categorise(res: pd.DataFrame, u_comp: pd.Series, comp_class: dict) -> pd.Series:
    out = pd.Series("unconnected", index=res.index)
    ok = res["status"] == A.OK
    out[ok & res["network_node"]] = "network_connected"
    other = ok & ~res["network_node"]
    cls = u_comp.map(comp_class)
    out[other & (cls == "access_uncertain")] = "access_uncertain"
    out[other & (cls != "access_uncertain")] = "locally_connected"
    return out


# --- A3 component-aware reporting layer (approved M04 follow-up; additional, never the baseline) ---

A3_DIR = "component_aware"
SCENARIO_LABELS = {
    "A1_baseline": "A1 optimistic connectivity scenario (the active baseline): every cell within 250 m of "
    "the main network gets citywide times, also through a straight connector past an unlinked "
    "fragment. Optimistic, not a verified upper bound",
    "A2_all_eligible": "A2 all eligible components (comparison only; not preferred)",
    "A3_component_aware": "A3 component-aware reporting scenario: citywide times only for residents "
    "connected to the main network; internal times reported separately",
}
LOCAL = ("locally_connected", "access_uncertain")
# Baseline outputs that the reporting layer must never change (checked by hash on every run).
BASELINE_FILES = ["abot_iloilo.gpkg", "barangay_access.csv", "facilities.csv", "facility_inventory.csv",
                  "drive_speed_sensitivity.csv", "barangay_population.csv"]  # fmt: skip


def a3_dir(s: Settings) -> Path:
    return s.processed_dir / A3_DIR


def baseline_hashes(s: Settings) -> dict:
    from abot.fetch.common import sha256

    return {f: sha256(s.processed_dir / f) for f in BASELINE_FILES if (s.processed_dir / f).exists()}


def a3_cells(s: Settings, cells: gpd.GeoDataFrame, res: pd.DataFrame, cat: pd.Series, comp_of: dict,
             comp_class: dict) -> pd.DataFrame:  # fmt: skip
    """One row per cell. Citywide and internal times are separate columns: a local time is never a
    citywide time (rule 4)."""
    ll = cells.geometry.to_crs(4326)
    out = pd.DataFrame(
        {
            "cell_id": cells["cell_id"], "pop": cells["pop"], "adm4_pcode": cells["adm4_pcode"],
            "lon": ll.x.round(6), "lat": ll.y.round(6), "a3_category": cat,
            "component": res["u"].map(comp_of).where(res["status"] == A.OK),
            "conn_status": res["status"], "conn_m": res["conn_m"],
        }
    )  # fmt: skip
    out["component_class"] = out["component"].map(comp_class)
    for g in s["indicator_groups"]:
        t = res[f"t_walk_{g}"]
        out[f"t_walk_{g}_citywide"] = t.where(cat == "network_connected")
        out[f"t_walk_{g}_internal"] = t.where(cat.isin(LOCAL))
    return out


def a3_barangay(s: Settings, a3c: pd.DataFrame, pieces: pd.DataFrame, brgy: pd.DataFrame) -> pd.DataFrame:
    """Population by A3 category, citywide walking indicators (network-connected residents; shares of
    ALL residents) and internal accessibility (locally connected and access-uncertain apart)."""
    from abot.compare import weighted_quantile

    ths = s["accessibility"]["thresholds_min"]["walk"]
    p = pieces[["cell_id", "adm4_pcode", "pop"]].join(
        a3c.drop(columns=["pop", "adm4_pcode", "lon", "lat"]).set_index("cell_id"), on="cell_id"
    )
    rows = []
    for pcode, g in p.groupby("adm4_pcode", sort=True):
        w = g["pop"].to_numpy(dtype=float)
        total = float(w.sum())
        row = {"adm4_pcode": pcode, "pop_total": round(total, 1)}
        for c in CATEGORIES:
            m = (g["a3_category"] == c).to_numpy()
            row[f"pop_{c}"] = round(float(w[m].sum()), 1)
            row[f"pct_{c}"] = round(100 * float(w[m].sum()) / total, 2) if total else 0.0
        for grp in s["indicator_groups"]:
            t = g[f"t_walk_{grp}_citywide"].to_numpy(dtype=float)
            ok = ~np.isnan(t)
            if ok.any() and w[ok].sum() > 0:
                row[f"walk_{grp}_mean_min"] = round(float(np.average(t[ok], weights=w[ok])), 2)
                row[f"walk_{grp}_p90_min"] = round(weighted_quantile(t[ok], w[ok], 0.9), 2)
            for th in ths:
                row[f"walk_{grp}_pct_le{th}"] = round(100 * float(w[ok & (t <= th)].sum()) / total, 2) if total else 0.0
            ti = g[f"t_walk_{grp}_internal"].to_numpy(dtype=float)
            for c, short in (("locally_connected", "local"), ("access_uncertain", "uncertain")):
                m = (g["a3_category"] == c).to_numpy() & ~np.isnan(ti)
                row[f"pop_{short}_internal_{grp}"] = round(float(w[m].sum()), 1)
                row[f"pop_{short}_internal_{grp}_le15"] = round(float(w[m & (ti <= 15)].sum()), 1)
        rows.append(row)
    out = brgy[["adm4_pcode", "adm4_name"]].merge(pd.DataFrame(rows), on="adm4_pcode", how="left")
    out["resolved_separately"] = out["adm4_pcode"].isin(EXCLUDED_BARANGAYS)
    parts = out[[f"pop_{c}" for c in CATEGORIES]].sum(axis=1)
    if ((parts - out["pop_total"]).abs() > 0.5).any():  # rounding of four parts
        raise RuntimeError("A3 population categories do not add up to the barangay totals")
    return out


def a3_citywide(s: Settings, cells: pd.DataFrame, a1: pd.DataFrame, a3c: pd.DataFrame) -> pd.DataFrame:
    w = cells["pop"].to_numpy(dtype=float)
    total = float(w.sum())
    rows = [{"metric": f"pop_{c}", "A3": round(float(w[(a3c["a3_category"] == c).to_numpy()].sum()), 1),
             "A3_pct": round(100 * float(w[(a3c["a3_category"] == c).to_numpy()].sum()) / total, 2)}
            for c in CATEGORIES]  # fmt: skip
    a1_conn = a1["status"].eq(A.OK).to_numpy()
    rows.append({"metric": "pop_connected_A1_optimistic", "A1": round(float(w[a1_conn].sum()), 1),
                 "A1_pct": round(100 * float(w[a1_conn].sum()) / total, 2)})  # fmt: skip
    for g in s["indicator_groups"]:
        t1, t3 = a1[f"t_walk_{g}"].to_numpy(dtype=float), a3c[f"t_walk_{g}_citywide"].to_numpy(dtype=float)
        ti = a3c[f"t_walk_{g}_internal"].to_numpy(dtype=float)
        for th in s["accessibility"]["thresholds_min"]["walk"]:
            rows.append(
                {
                    "metric": f"walk_{g}_pct_le{th}",
                    "A1": round(100 * float(w[t1 <= th].sum()) / total, 2),
                    "A3": round(100 * float(w[t3 <= th].sum()) / total, 2),
                    "A3_local_internal_pop": round(float(w[(a3c["a3_category"] == "locally_connected").to_numpy() & (ti <= th)].sum()), 1),
                    "A3_uncertain_internal_pop": round(float(w[(a3c["a3_category"] == "access_uncertain").to_numpy() & (ti <= th)].sum()), 1),
                }
            )  # fmt: skip
        def mean(t):
            ok = ~np.isnan(t)
            return round(float(np.average(t[ok], weights=w[ok])), 2) if ok.any() and w[ok].sum() > 0 else np.nan

        rows.append({"metric": f"walk_{g}_mean_min", "A1": mean(t1), "A3": mean(t3)})
    return pd.DataFrame(rows)


def write_a3_layer(s: Settings, cells, results, cats, comp_of, comp_class, before: dict) -> dict:
    out = a3_dir(s)
    out.mkdir(parents=True, exist_ok=True)
    a3c = a3_cells(s, cells, results["A3_component_aware"], cats["A3_component_aware"], comp_of, comp_class)
    if abs(a3c["pop"].sum() - cells["pop"].sum()) > 0.01:
        raise RuntimeError("A3 cells do not hold the full population")
    brgy = gpd.read_file(s.gpkg, layer="barangays")
    from abot import population

    bt = a3_barangay(s, a3c, population.load_pieces(s), brgy)
    city = a3_citywide(s, cells, results["A1_baseline"], a3c)
    a3c.to_csv(out / "cells_a3.csv", index=False)
    bt.to_csv(out / "barangay_access_a3.csv", index=False)
    city.to_csv(out / "citywide_a3.csv", index=False)
    gpkg = out / "component_aware.gpkg"
    if gpkg.exists():
        gpkg.unlink()  # derived file, fully rewritten
    brgy[["adm4_pcode", "geometry"]].merge(bt, on="adm4_pcode").to_file(gpkg, layer="barangay_access_a3", driver="GPKG")
    gpd.GeoDataFrame(a3c, geometry=gpd.points_from_xy(a3c["lon"], a3c["lat"]), crs=4326).to_file(
        gpkg, layer="cells_a3", driver="GPKG"
    )
    after = baseline_hashes(s)
    if after != before:
        raise RuntimeError("baseline outputs changed while building the A3 layer")
    info = {
        "config_sha256": s.config_sha256,
        "created_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "a1_reproduces_baseline": True,  # build() raises otherwise
        "baseline_outputs_unchanged": True,
        "baseline_sha256": after,
        "population_total": round(float(cells["pop"].sum()), 1),
        "scenario_labels": SCENARIO_LABELS,
    }
    (out / "run_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    pops = city.set_index("metric")["A3"]
    (out / "README.md").write_text(
        "\n".join([
            "# Component-aware reporting layer (A3): additional to the active baseline",
            "",
            ("Generated by `abot components`. The active baseline (`data/processed/`) is A1, the "
            "**optimistic connectivity scenario**, and is unchanged (hash-checked on every run). A1 is not a "
            "verified upper bound. A3 is a reporting scenario approved in the Milestone 04 follow-up; it is "
            "not the baseline."),
            "",
            "| A3 category | Residents | Meaning |",
            "|---|---|---|",
            f"| network_connected | {pops['pop_network_connected']:,.1f} | on the main walk network: citywide times |",
            f"| locally_connected | {pops['pop_locally_connected']:,.1f} | on an eligible isolated component: internal times only |",
            f"| access_uncertain | {pops['pop_access_uncertain']:,.1f} | on a component with uncertain access: internal times reported apart |",
            f"| unconnected | {pops['pop_unconnected']:,.1f} | no acceptable edge within 250 m |",
            "",
            ("Rules: citywide indicators use network-connected residents only; every share divides by ALL "
            "residents; internal times (`*_internal`, `pop_local_internal_*`, `pop_uncertain_internal_*`) exist "
            "only when the cell and a facility share an isolated component and never count as citywide "
            "access; no link between components is added; F001 is not connected to the main network. "
            "Walking only (drive times are unchanged in the baseline). Calahunan and Hibao-an Sur are "
            "included in the totals and flagged `resolved_separately`."),
            "",
            ("Files: `cells_a3.csv`, `barangay_access_a3.csv` (counts and percentages by barangay), "
            "`citywide_a3.csv` (A1 vs A3), `component_aware.gpkg`, `run_info.json`."),
            "",
        ]),
        encoding="utf-8",
    )  # fmt: skip
    return info


# --- driver -------------------------------------------------------------------------------------


def build(s: Settings) -> None:
    out = m04_dir(s)
    out.mkdir(parents=True, exist_ok=True)
    before = baseline_hashes(s)  # the baseline (A1) outputs must not change
    mps = s["accessibility"]["walk_speed_kmh"] / 3.6
    cfg = s["accessibility"]["connection"]

    log.info("rebuilding the unfiltered walk graph from the cache ...")
    G_all = validation.walk_graph_all(s)
    set_walk_time(G_all, mps)
    comps = ordered_components(G_all)
    main = comps[0]
    saved = osm.load_graph(s, "walk")
    if set(saved.nodes) != set(main):
        raise RuntimeError("main component differs from the saved walk graph: rebuild the baseline first")
    ways, nodes = walk_cache_elements(s)
    et, gates = edge_table(G_all, ways, nodes)
    bar = osm.load_barriers(s)
    checker = A.BarrierChecker(bar, cfg["water_crossing_tolerance_m"])
    cells = gpd.read_file(s.gpkg, layer="access_cells")
    roles = osm.load_roles(s)

    # B1 inventory
    log.info("component inventory (%d components) ...", len(comps))
    inv = component_inventory(s, G_all, comps, et, nodes, bar)
    comp_of = {n: "main" for n in main} | {n: f"F{i:03d}" for i, c in enumerate(comps[1:], start=1) for n in c}
    comp_class = dict(zip(inv["fragment"], inv["component_class"], strict=True))
    ref = s.data_dir / "archive" / TAXONOMY_REFERENCE / "review_m04" / "component_inventory.csv"
    check = {"reference": None, "note": "pre-taxonomy reference archive absent: not compared"}
    if ref.exists():
        check = {"reference": ref.relative_to(s.root).as_posix(), **compare_component_classes(pd.read_csv(ref), inv)}
        log.info("component classes identical to the pre-taxonomy reference (%d components)", len(inv))
    (out / "taxonomy_check.json").write_text(json.dumps(check, indent=2), encoding="utf-8")

    # B2 approaches
    results, cats, summary = {}, {}, []
    G1 = G_all.subgraph(main).copy()
    keep2 = {n for n in G_all if comp_class[comp_of[n]] in ELIGIBLE_A2}
    keep3 = {n for n in G_all if comp_class[comp_of[n]] in ELIGIBLE_A3}
    G2, G3 = G_all.subgraph(keep2).copy(), G_all.subgraph(keep3).copy()
    fac = roles.drop_duplicates("fid_key").set_index("fid_key")[["name", "category", "subtype", "tier", "inside_city"]]
    for name, G, extra in (("A1_baseline", G1, None), ("A2_all_eligible", G2, None), ("A3_component_aware", G3, G1)):
        log.info("evaluating %s ...", name)
        res, fc = evaluate(s, G, cells, roles, checker, extra)
        cat = categorise(res, res["u"].map(comp_of), comp_class)
        results[name], cats[name] = res, cat
        ok = fc[fc["status"] == A.OK]
        fac[f"components_{name}"] = ok["u"].map(comp_of).groupby(level=0).agg(lambda x: ";".join(sorted(set(x))))
        n_comp = sum(1 for c in inv.itertuples() if c.fragment == "main" or (name != "A1_baseline" and (
            c.retained_A2 if name == "A2_all_eligible" else c.retained_A3)))
        summary += approach_summary(s, name, cells, res, cat, G, n_comp)
    # Approach 1 must reproduce the saved baseline exactly.
    base_cols = [f"t_walk_{g}" for g in s["indicator_groups"]]
    diff = (results["A1_baseline"][base_cols] - cells[base_cols]).abs().max().max()
    if not (results["A1_baseline"]["status"] == cells["conn_status"]).all() or diff > 0.011:
        raise RuntimeError(f"A1 does not reproduce the baseline (max diff {diff} min)")
    summ = pd.DataFrame(summary)
    summ.insert(1, "scenario_label", summ["approach"].map(SCENARIO_LABELS))
    summ.to_csv(out / "approach_comparison.csv", index=False)
    log.info("writing the A3 component-aware reporting layer ...")
    write_a3_layer(s, cells, results, cats, comp_of, comp_class, before)
    # Facilities not attached to the main network alone in some approach (A2 can pull a facility
    # off the main network onto a fragment; A3 keeps the main connection as well).
    fac_off = fac[fac.filter(like="components_").fillna("").ne("main").any(axis=1)]
    fac_off.reset_index().sort_values("fid_key").to_csv(out / "facilities_by_approach.csv", index=False)

    # Inventory: cells and residents per component under A3 attachment (nearest eligible component)
    a3 = results["A3_component_aware"]
    att = a3["u"].map(comp_of).where(a3["status"] == A.OK)
    inv["cells_attached_A3"] = inv["fragment"].map(att.value_counts()).fillna(0).astype(int)
    inv["pop_attached_A3"] = inv["fragment"].map(cells["pop"].groupby(att).sum()).fillna(0).round(1)
    for g in ("health_primary_care", "education_basic"):
        reach = a3[f"t_walk_{g}"].notna() & att.ne("main")
        inv[f"pop_internal_{g}_reachable"] = inv["fragment"].map(cells["pop"][reach].groupby(att[reach]).sum()).fillna(0).round(1)
    inv.drop(columns=[]).to_csv(out / "component_inventory.csv", index=False)

    # Per-cell comparison (focus: cells whose category or times differ)
    pc = cells[["cell_id", "pop", "adm4_pcode", "centre_adm4_pcode"]].copy()
    names = gpd.read_file(s.gpkg, layer="barangays", ignore_geometry=True).set_index("adm4_pcode")["adm4_name"]
    pc["barangay"] = pc["adm4_pcode"].map(names)
    pc["excluded_resolved_separately"] = pc["adm4_pcode"].isin(EXCLUDED_BARANGAYS) | pc["centre_adm4_pcode"].isin(EXCLUDED_BARANGAYS)
    for name, cat in cats.items():
        pc[f"cat_{name}"] = cat.values
        pc[f"conn_m_{name}"] = results[name]["conn_m"].values
        pc[f"component_{name}"] = results[name]["u"].map(comp_of).where(results[name]["status"] == A.OK).values
        for g in ("health_hospital", "health_primary_care", "education_basic"):
            pc[f"t_{g}_{name}"] = results[name][f"t_walk_{g}"].values
    # fillna: two unconnected cells (no component) must compare equal, not NaN != NaN
    changed = (pc["cat_A1_baseline"] != pc["cat_A3_component_aware"]) | (pc["cat_A1_baseline"] != pc["cat_A2_all_eligible"]) | (
        pc["component_A1_baseline"].fillna("") != pc["component_A3_component_aware"].fillna(""))
    pc[changed].sort_values("pop", ascending=False).to_csv(out / "cells_changed_by_approach.csv", index=False)

    tr = pd.crosstab(pc["cat_A1_baseline"], pc["cat_A3_component_aware"], values=pc["pop"], aggfunc="sum").round(1)
    tr.to_csv(out / "transition_A1_to_A3_pop.csv")
    by_b = (
        pc[changed & ~pc["excluded_resolved_separately"]]
        .groupby(["barangay", "cat_A1_baseline", "cat_A3_component_aware"])["pop"].agg(["size", "sum"]).round(1)
        .rename(columns={"size": "cells", "sum": "pop"}).reset_index().sort_values("pop", ascending=False)
    )  # fmt: skip
    by_b.to_csv(out / "changes_by_barangay.csv", index=False)
    excluded_delta = round(float(pc.loc[changed & pc["excluded_resolved_separately"], "pop"].sum()), 1)

    # C1 access impact
    log.info("access-tag impact scenarios ...")
    et_main = et[et["u"].isin(main)]
    impact, impact_g = [], []
    base = results["A1_baseline"]
    scen = {k: [k] for k in TAG_SCENARIOS} | COMBINED
    for name, flags in scen.items():
        sel = et_main[et_main["flags"].map(lambda f, fl=flags: bool(f & set(fl)))]
        row = {
            "scenario": name,
            "definition": TAG_SCENARIOS.get(name, " + ".join(flags)),
            "ways_all_components": int(len({w for ids, f in zip(et["osmids"], et["flags"], strict=True) if f & set(flags) for w in ids})),
            "km_all_components": round(et.loc[et["flags"].map(lambda f, fl=flags: bool(f & set(fl))), "length"].sum() / 2000, 2),
            "edges_removed_main": len(sel) // 2,
            "km_removed_main": round(sel["length"].sum() / 2000, 2),
        }  # fmt: skip
        if sel.empty:
            row.update(pop_lose_network=0.0, pop_become_local=0.0, pop_become_unconnected=0.0, pop_time_up_gt1min=0.0)
            impact.append(row)
            continue
        Gs = G1.copy()
        Gs.remove_edges_from(list(zip(sel["u"], sel["v"], sel["k"], strict=True)))
        Gs.remove_nodes_from([n for n in list(Gs) if Gs.degree(n) == 0])
        res, _ = evaluate(s, Gs, cells, roles, checker)
        was = base["status"].eq(A.OK) & base["network_node"]
        now_net = res["status"].eq(A.OK) & res["network_node"]
        lose = was & ~now_net
        up = pd.Series(False, index=cells.index)
        for g in s["indicator_groups"]:
            up |= (res[f"t_walk_{g}"] - base[f"t_walk_{g}"]) > 1.0
        row.update(
            pop_lose_network=_w(cells, lose),
            pop_become_local=_w(cells, lose & res["status"].eq(A.OK)),
            pop_become_unconnected=_w(cells, lose & ~res["status"].eq(A.OK)),
            pop_time_up_gt1min=_w(cells, now_net & up),
            pop_lose_network_focus=_w(cells, lose & cells["adm4_pcode"].isin(FOCUS_BARANGAYS)),
        )
        impact.append(row)
        total = float(cells["pop"].sum())
        for g in REPORT_GROUPS:
            t0, t1 = base[f"t_walk_{g}"], res[f"t_walk_{g}"].where(now_net)
            impact_g.append(
                {
                    "scenario": name, "group": g,
                    "pct_le15_baseline": round(100 * cells["pop"][t0 <= 15].sum() / total, 2),
                    "pct_le15_scenario": round(100 * cells["pop"][t1 <= 15].sum() / total, 2),
                    "mean_min_baseline": round(float(np.average(t0[was & t0.notna()], weights=cells["pop"][was & t0.notna()])), 2),
                    "mean_min_scenario": round(float(np.average(t1[t1.notna()], weights=cells["pop"][t1.notna()])), 2),
                }
            )  # fmt: skip
    pd.DataFrame(impact).to_csv(out / "access_impact.csv", index=False)
    pd.DataFrame(impact_g).to_csv(out / "access_impact_by_group.csv", index=False)

    # access classification tables
    und = et[[u < v or (u == v) for u, v in zip(et["u"], et["v"], strict=True)]].copy()  # one direction
    und["in_main"] = und["u"].isin(main)
    cls_tab = und.groupby(["way_class", "in_main"])["length"].agg(["size", "sum"]).reset_index()
    cls_tab["km"] = (cls_tab["sum"] / 1000).round(2)
    cls_tab["policy_provisional"] = cls_tab["way_class"].map(POLICY)
    cls_tab.drop(columns="sum").rename(columns={"size": "edges"}).to_csv(out / "access_classes.csv", index=False)
    restricted = []
    for wid, w in sorted(ways.items()):
        t = w.get("tags", {})
        a = access_assessment(t)
        if a["mapped_access_status"] not in ("public", "untagged"):
            in_graph = any(wid in ids for ids in et["osmids"])  # small table, clarity over speed
            restricted.append({"way": wid, "highway": t.get("highway"), "access": t.get("access"), "foot": t.get("foot"),
                               "service": t.get("service"), "name": t.get("name"),
                               "access_class": a.pop("mapped_access_status"), **a,
                               "flags": ";".join(sorted(way_tag_flags(t))), "in_walk_graph": in_graph})  # fmt: skip
    rw = pd.DataFrame(restricted)
    comp_by_way = {}
    for ids, u in zip(et["osmids"], et["u"], strict=True):
        for w in ids:
            comp_by_way.setdefault(w, comp_of[u])
    rw["component"] = rw["way"].map(comp_by_way)
    rw.to_csv(out / "restricted_ways.csv", index=False)
    gates["component"] = gates["edge_u"].map(comp_of)
    gates.to_csv(out / "gate_nodes.csv", index=False)
    classification_summary(et, gates, ways, comp_of, results["A1_baseline"], cells["pop"]).to_csv(
        out / "access_classification_summary.csv", index=False
    )

    nm = near_misses(s, G_all, comps, nodes)
    nm.to_csv(out / "dead_end_near_misses.csv", index=False)
    # Snapshot evidence first, so the gap table and README describe what is actually present.
    snapshot = gap_snapshot_evidence(s, out, ways, nodes, comp_by_way)
    gap = gap_investigation(s, G_all, comps, inv, nm, ways, nodes, gates, snapshot)
    gap.to_csv(out / "gap_investigation.csv", index=False)

    facility_review_summary(s).to_csv(out / "facility_review_summary.csv", index=False)

    write_readme(out, inv, summ, tr, by_b, excluded_delta, pd.DataFrame(impact), gap, len(comps), snapshot)
    log.info("wrote %s", out)


# --- Phase A: targeted snapshot evidence (when the user's approved fetch has produced one) -------


SNAPSHOT_FILES = ["snapshot_gap_elements.csv", "snapshot_link_candidates.csv", "snapshot_corridor_analysis.csv"]


def gap_snapshot_evidence(s: Settings, out: Path, ways: dict, nodes: dict, comp_by_way: dict) -> dict:
    """Read the latest targeted snapshot (if any) and write its evidence tables.

    Returns {"status": <snapshot_status.json content>, "corridors": DataFrame}. With no snapshot, the
    evidence tables of an earlier run are removed so that stale evidence can never be read as current.
    """
    from abot.fetch import targeted

    latest = targeted.load_latest(s)
    status_file = out / "snapshot_status.json"
    if latest is None:
        for f in SNAPSHOT_FILES:
            (out / f).unlink(missing_ok=True)
        status = {"obtained": False, "snapshot": None, "note": "no targeted snapshot in data/raw/osm_targeted/: "
                  "F001 and the Baybay Tanza gaps are measured on the cache only (run `abot fetch-gaps "
                  "--allow-download` once, if approved)"}  # fmt: skip
        status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
        return {"status": status, "corridors": pd.DataFrame()}
    snap, meta = latest
    elements, links = targeted.snapshot_evidence(snap, ways, comp_by_way)
    corridors = targeted.corridor_analysis(snap, ways, nodes, comp_by_way, links) if len(links) else pd.DataFrame()
    elements.to_csv(out / "snapshot_gap_elements.csv", index=False)
    links.to_csv(out / "snapshot_link_candidates.csv", index=False)
    corridors.to_csv(out / "snapshot_corridor_analysis.csv", index=False)
    status = {
        "obtained": True,
        "snapshot": meta.get("query_file", "").replace(".overpassql", ".json"),
        "response_sha256": meta.get("response_sha256"),
        "timestamp_osm_base": meta.get("timestamp_osm_base"),
        "requested_utc": meta.get("requested_utc"),
        "elements": meta.get("elements"),
        "elements_tagged": len(elements),
        "ways_not_in_walk_cache": int((elements["in_walk_cache"] == False).sum()) if len(elements) else 0,  # noqa: E712
        "link_candidates": len(links),
        "note": "evidence only: no link is added to any network; physical connection in OSM topology is not "
        "public pedestrian access",
    }
    status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return {"status": status, "corridors": corridors}


# --- access classification summary (approved for analysis and reporting only) -------------------


def classification_summary(
    et: pd.DataFrame, gates: pd.DataFrame, ways: dict, comp_of: dict, a1: pd.DataFrame, pop: pd.Series
) -> pd.DataFrame:
    """Per access class: ways, edges, km, components, and the population cells (and residents) whose
    active (A1) connection edge carries that class. Way rows count each way once by its own tags;
    edge rows use the most restrictive class of a simplified edge. Nothing is excluded from routing."""
    und = et[[u < v or u == v for u, v in zip(et["u"], et["v"], strict=True)]]
    edge_cls: dict = {}
    edge_gate: dict = {}
    for u, v, c, g in zip(und["u"], und["v"], und["way_class"], und["gates"], strict=True):
        k = frozenset((u, v))
        edge_cls[k] = min(edge_cls.get(k, c), c, key=RANK.__getitem__)
        edge_gate.setdefault(k, set()).update(g)
    ok = a1["status"] == A.OK
    cell_edge = [frozenset((u, v)) if o else None for u, v, o in zip(a1["u"], a1["v"], ok, strict=True)]
    cell_cls = pd.Series([edge_cls.get(k) if k else None for k in cell_edge], index=a1.index)
    cell_gates = pd.Series([edge_gate.get(k, set()) if k else set() for k in cell_edge], index=a1.index)
    in_graph = {w for ids in und["osmids"] for w in ids}
    way_cls = pd.Series({w: access_class(ways.get(w, {}).get("tags", {})) for w in sorted(in_graph)})
    way_comp = {}
    for ids, u in zip(und["osmids"], und["u"], strict=True):
        for w in ids:
            way_comp.setdefault(w, comp_of.get(u))
    rows = []
    for c in ACCESS_CLASSES:
        e = und[und["way_class"] == c]
        wc = way_cls[way_cls == c].index
        hit = cell_cls == c
        rows.append(
            {
                "kind": "way", "access_class": c, "public_pedestrian_status": PUBLIC_PEDESTRIAN[c],
                "treatment": POLICY[c], "ways": len(wc),
                "edges": len(e), "km": round(e["length"].sum() / 1000, 2),
                "km_main": round(e.loc[e["u"].map(comp_of).eq("main"), "length"].sum() / 1000, 2),
                "components": len({way_comp[w] for w in wc}),
                "cells_attached_A1": int(hit.sum()), "pop_attached_A1": round(float(pop[hit].sum()), 1),
            }
        )  # fmt: skip
    for c in ACCESS_CLASSES:
        g = gates[gates["gate_class"] == c]
        if g.empty:
            continue
        hit = cell_gates.map(lambda s, c=c: c in s)
        rows.append(
            {
                "kind": "gate node", "access_class": c, "public_pedestrian_status": PUBLIC_PEDESTRIAN[c],
                "treatment": ("flag for review: " if c in RESTRICTED else "") + POLICY[c],
                "nodes": len(g), "nodes_flag_for_review": int(g["flag_for_review"].sum()),
                "nodes_field_verification": int(g["field_verification_required"].sum()),
                "nodes_main": int(g["component"].eq("main").sum()), "components": int(g["component"].nunique()),
                "cells_attached_A1": int(hit.sum()), "pop_attached_A1": round(float(pop[hit].sum()), 1),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


# --- Phase D: facility review summary (nothing applied) ----------------------------------------

REVIEW_GROUPS = {
    "D13": "likely_duplicate", "D14": "likely_duplicate",
    **dict.fromkeys(["D01", "D02", "D07", "D08", "D09"], "distinct_bank_and_atm"),
    **dict.fromkeys(["D03", "D04", "D05", "D06", "D10", "D11", "D12"], "uncertain"),
}  # fmt: skip
REVIEW_RATIONALE = {
    "D13": "599 m2 DBP building polygon lies 100% inside the 1,466 m2 DBP site polygon: one bank outlined "
    "twice; the site record carries the address, branch and atm=yes",
    "D14": "identical tags and consecutive OSM ids (one upload); two shed outlines 23 m apart: one market "
    "mapped as two structures",
    "D01": "bank vs ATM: an ATM is a descriptive sub-type and never a destination; two services at one site",
    "D02": "bank vs ATM (the same ATM as D01)",
    "D07": "PSBank bank vs ATM",
    "D08": "PNB Danao bank building vs an ATM 1.9 m outside it",
    "D09": "UnionBank ATM vs bank",
    "D03": "two PNB bank nodes 9 m apart, one recent with fewer tags: one branch or two on General Luna St?",
    "D04": "Metrobank old node (Laguda) and a new node ~20 m north (Rizal La Paz), added together with D05's: "
    "likely a re-placement, but the record kept decides the barangay",
    "D05": "BPI, same pattern as D04",
    "D06": "Ledi Supermart 5.5 m apart, differs only in addr:street",
    "D10": "BPI 41 m apart in Buhang Taft North: one is the 'Megaworld' branch on Festive Walk Rd with opening "
    "hours, the other a minimal node checked 2025-12-03; two branches or business centres are plausible",
    "D11": "TGP pharmacy 5 m apart, differs only in check_date; straddles Katilingban / Poblacion Molo",
    "D12": "Alpha Star Christian Preschool, identical minimal tags 16 m apart, ids not consecutive",
}
REVIEW_EVIDENCE_NEEDED = {
    "D10": "BPI official branch list naming one or two branches at Festive Walk / Megaworld (M04: the one "
    "approved lookup, bpi.com.ph/locator, returned HTTP 404: inconclusive); otherwise a street-level check",
    "D03": "street-level: one or two PNB branches on General Luna St",
    "D04": "imagery or street level: which position is the Metrobank building",
    "D05": "imagery or street level: which position is the BPI building",
    "D06": "street-level check",
    "D11": "street-level check; keep the record with check_date?",
    "D12": "imagery or a school list",
}


def facility_review_summary(s: Settings) -> pd.DataFrame:
    """M04 review summary of the 14 pairs. Reviewer columns come from the live review file (only where
    the same two OSM records form the pair) and are copied unchanged; nothing is applied here."""
    d = pd.read_csv(review.review_dir(s) / "m03" / "duplicates_assessment.csv", encoding="utf-8")
    live = review.review_dir(s) / review.DUPLICATES_FILE
    if live.exists():
        cur = pd.read_csv(live, dtype=str, keep_default_na=False).set_index("review_id")
        same = d["review_id"].map(cur["flagged_fid"]).eq(d["flagged_fid"]) & d["review_id"].map(
            cur["related_fid"]
        ).eq(d["related_fid"])
        for c in review.REVIEW_COLUMNS:
            d[c] = d["review_id"].map(cur[c]).where(same, d[c])
    dist = d.set_index("review_id")["distance_m"]
    grp = d["review_id"].map(REVIEW_GROUPS)
    return pd.DataFrame(
        {
            "review_id": d["review_id"],
            "m04_group": grp,
            "m04_rationale": d["review_id"].map(REVIEW_RATIONALE),
            "affects_facility_counts": d["effect_if_merged"],
            "affects_travel_time": [
                "no: an ATM is never a destination" if g == "distinct_bank_and_atm"
                else f"negligible: the destination moves at most {dist[r]:.0f} m"
                for r, g in zip(d["review_id"], grp, strict=True)
            ],
            "evidence_still_needed": d["review_id"].map(REVIEW_EVIDENCE_NEEDED).fillna("reviewer confirmation only"),
            "m03_desk_assessment": d["desk_assessment"],
            "flagged_fid": d["flagged_fid"], "related_fid": d["related_fid"], "flagged_name": d["flagged_name"],
            **{c: d[c] for c in review.REVIEW_COLUMNS},
        }
    )  # fmt: skip


CACHE_SCOPE = ("walk-filtered ways only: the cache cannot contain access=private, service=private, foot=no "
               "or construction ways")  # fmt: skip


def remaining_unverified(snapshot_obtained: bool, link: dict | None) -> str:
    """What is still open for one gap, given the targeted-snapshot evidence actually present."""
    if not snapshot_obtained:
        return ("whether a way excluded by the walk filter (access=private, gated, construction) fills the gap: "
                "no targeted snapshot present; a snapshot or a site/imagery check is needed")  # fmt: skip
    if not link:
        return ("the targeted snapshot shows no excluded way linking this fragment to the main network in the "
                "queried area; whether an unmapped path exists needs a site/imagery check")  # fmt: skip
    return ("a link is mapped in OSM topology through access-restricted ways (see snapshot_* columns): which "
            "users the restriction admits (access=private names no group), whether its gates are open and pass "
            "pedestrians, and when, needs field verification or authoritative access information; physical "
            "connection is not public pedestrian access")  # fmt: skip


def gap_investigation(s, G_all, comps, inv, nm, ways, nodes, gates, snapshot: dict | None = None) -> pd.DataFrame:
    """Tabuc Suba (F001) and Baybay Tanza (F100, F101) gaps.

    `cache_*` columns are measured on the walk-filtered cache; `snapshot_*` columns come from the
    targeted snapshot when one is present. The component class is never changed by the snapshot.
    """
    snapshot = snapshot or {"status": {"obtained": False}, "corridors": pd.DataFrame()}
    obtained = bool(snapshot["status"].get("obtained"))
    cor = snapshot["corridors"]
    rows = []
    frag = {n: f"F{i:03d}" for i, c in enumerate(comps[1:], start=1) for n in c}
    for fid in ("F001", "F100", "F101"):
        r = inv.set_index("fragment").loc[fid]
        fn = [n for n, f in frag.items() if f == fid]
        fw = sorted({w for u, v, d in G_all.subgraph(fn).edges(data=True) for w in _ids(d["osmid"])})
        tagsets = pd.Series([access_class(ways[w].get("tags", {})) for w in fw if w in ways]).value_counts()
        gn = gates[gates["component"] == fid]
        misses = nm[nm["fragment"] == fid]
        link = cor[cor["fragment"] == fid].iloc[0].to_dict() if len(cor) and (cor["fragment"] == fid).any() else None
        rows.append(
            {
                "fragment": fid, "length_km": r["length_km"], "component_class": r["component_class"],
                "component_class_changed_by_snapshot": False,
                "cache_scope": CACHE_SCOPE,
                "cache_gap_to_main_m": r["gap_to_main_m"], "cache_noexit_at_gap": r["noexit_at_gap"],
                "cache_gap_crosses_water": r["gap_crosses_water"],
                "cache_way_access_classes": "; ".join(f"{k} {v}" for k, v in tagsets.items()),
                "cache_gates_on_fragment": "; ".join(f"node/{g.node} {g.barrier} access={g.access}" for g in gn.itertuples()) or "none",
                "cache_dead_ends_within_20m_of_main": len(misses),
                "cache_dead_ends_detail": "; ".join(
                    f"node/{m.dead_end_node} {m.dist_to_main_m} m tags={m.dead_end_tags} -> {m.main_edge_highway} '{m.main_edge_name}'"
                    for m in misses.itertuples()
                ),
                "snapshot_obtained": obtained,
                "snapshot_file": snapshot["status"].get("snapshot") or "",
                "snapshot_physical_connection": (link or {}).get("physical_connection", "none_found" if obtained else "not_examined"),
                "snapshot_link_m": (link or {}).get("path_m"),
                "snapshot_link_ways": (link or {}).get("path_ways", ""),
                "snapshot_link_access_tags": (link or {}).get("corridor_access_tags", ""),
                "snapshot_link_gates": (link or {}).get("path_gates", ""),
                "snapshot_corridor_gates": (link or {}).get("corridor_gates", ""),
                "snapshot_public_pedestrian_access": (link or {}).get("public_pedestrian_access", "unverified"),
                "snapshot_path_access_status": (link or {}).get("path_mapped_access_status", ""),
                "snapshot_public_pedestrian_status": (link or {}).get("public_pedestrian_status", "unknown"),
                "snapshot_authorized_group": (link or {}).get("authorized_group", "unknown"),
                "snapshot_field_verification_required": True,
                "remaining_unverified": remaining_unverified(obtained, link),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def _md(df: pd.DataFrame, index: bool = True) -> str:
    """Markdown table without the optional `tabulate` dependency."""
    d = df.reset_index() if index else df
    cells = [[str(c) for c in d.columns]] + [["" if pd.isna(v) else str(v) for v in r] for r in d.itertuples(index=False)]
    cells = [[c.replace("|", "/").replace("\n", " ") for c in r] for r in cells]
    lines = ["| " + " | ".join(cells[0]) + " |", "|" + "---|" * len(cells[0])]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in cells[1:]])


def snapshot_readme_lines(snapshot: dict | None, gap: pd.DataFrame) -> list[str]:
    """README section for the targeted snapshot: what was obtained and what it does and does not show."""
    st = (snapshot or {}).get("status", {"obtained": False})
    if not st.get("obtained"):
        return ["## Targeted snapshot evidence", "",
                (f"**No targeted snapshot present.** The gap measurements above use the cache only "
                 f"({CACHE_SCOPE})."), ""]  # fmt: skip
    cor = snapshot["corridors"]
    lines = [
        "## Targeted snapshot evidence",
        "",
        (
            f"**Obtained:** `{st['snapshot']}` (OSM base {st.get('timestamp_osm_base')}, {st.get('elements')} "
            f"elements, response SHA-256 `{str(st.get('response_sha256'))[:16]}…`). Candidate corridors "
            f"identified: **{st.get('link_candidates', 0)}** (`snapshot_link_candidates.csv`, "
            "`snapshot_corridor_analysis.csv`). Nothing was added to any network."
        ),
        "",
        (
            "Physical connection is judged from OSM topology (shared node ids); public pedestrian access is "
            "judged from mapped tags only and is never inferred from connectivity. A path takes the most "
            "restrictive status of any way or gate on it; a path with no mapped gate gains nothing from that. "
            "`authorized_group=unspecified` means the tags restrict access without naming who is authorised."
        ),
        "",
    ]
    if len(cor):
        cols = ["candidate", "fragment", "physical_connection", "path_m", "path_ways", "corridor_access_tags",
                "path_gates", "path_mapped_access_status", "public_pedestrian_status", "authorized_group",
                "public_pedestrian_access", "field_verification_needed", "applied"]  # fmt: skip
        lines += [_md(cor[[c for c in cols if c in cor]], index=False), ""]
    lines += [f"- {r.fragment}: {r.remaining_unverified}" for r in gap.itertuples()] + [""]
    return lines


def write_readme(out, inv, summ, tr, by_b, excluded_delta, impact, gap, n_comp, snapshot: dict | None = None) -> None:
    pop = summ[summ["group"] == "_population"].set_index("approach")
    lines = [
        "# Milestone 04 component and access evidence (generated by `abot components`; nothing applied)",
        "",
        (
            f"Walk graph rebuilt from the Overpass cache: {n_comp} weakly connected components; the main component "
            "matches the saved walk graph node for node. Approach A1 reproduces the saved baseline times exactly."
        ),
        "",
        "## Component classes",
        "",
        _md(inv.groupby("component_class").agg(components=("fragment", "size"), km=("length_km", "sum"),
            pop_attached_A3=("pop_attached_A3", "sum")).round(1)),  # fmt: skip
        "",
        "## Approaches (residents)",
        "",
        _md(pop[[c for c in pop.columns if c.startswith(("components", "network_km", "pop_", "cells_"))]].T),
        "",
        "## Transition A1 -> A3 (residents)",
        "",
        _md(tr.fillna(0)),
        "",
        (
            "Calahunan and Hibao-an Sur are excluded from the barangay tables (resolved separately); "
            f"residents there whose category changes: {excluded_delta}."
        ),
        "",
        "## Access-tag impact on the baseline network (not applied)",
        "",
        _md(impact, index=False),
        "",
        "## Gap investigation: cache-only measurements",
        "",
        f"Measured on the walk-filtered Overpass cache ({CACHE_SCOPE}).",
        "",
        _md(gap.set_index("fragment").filter(like="cache_").drop(columns="cache_scope").T),
        "",
        *snapshot_readme_lines(snapshot, gap),
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")
