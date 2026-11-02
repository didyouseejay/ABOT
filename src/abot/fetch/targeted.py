"""Milestone 04 Phase A: one narrowly scoped Overpass snapshot around the walk-network gaps.

The osmnx walk filter drops `access=private`, `service=private`, `foot=no`, `highway=construction`
and similar ways BEFORE download, so the cached network responses cannot tell "missing from OSM" from
"mapped but excluded". This query fetches every highway way (no access filter) plus barriers,
entrances, bridges and `noexit` nodes in:
  - a 50 m corridor around each gap line (F001 Tabuc Suba, F100 / F101 Baybay Tanza), taken from
    review/m03/network_fragments.csv, and
  - the bounding box of fragment F001 (review/m03/validation.gpkg) expanded by 50 m.

The snapshot goes to data/raw/osm_targeted/ (never into osm_cache/), with the query text, a
metadata sidecar and a manifest entry (SHA-256). Downloading requires allow_download=True
(`abot fetch-gaps --allow-download`); without it the query is only built and validated.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from abot.config import Settings
from abot.fetch.common import USER_AGENT, record, sha256

log = logging.getLogger(__name__)

ENDPOINT = "https://overpass-api.de/api/interpreter"
CORRIDOR_M = 50
BBOX_PAD_M = 50
GAP_FRAGMENTS = {"F001": "Tabuc Suba subdivision", "F100": "Baybay Tanza", "F101": "Baybay Tanza"}
BBOX_FRAGMENT = "F001"
# Iloilo City plus the 3 km extraction buffer, loosely: a sanity bound for every coordinate.
LAT_RANGE, LON_RANGE = (10.6, 10.85), (122.45, 122.7)
# Way and node selectors fetched in every area. No access filter on purpose.
WAY_SELECTORS = ['["highway"]', '["barrier"]', '["bridge"]', '["man_made"="bridge"]', '["footway"]']
NODE_SELECTORS = ['["barrier"]', '["entrance"]', '["noexit"]', '["access"]', '["foot"]']


def corridors_from_fragments(frags: pd.DataFrame) -> list[dict]:
    rows = frags[frags["fragment"].isin(GAP_FRAGMENTS)].sort_values("fragment")
    return [
        {
            "label": f"{r.fragment} gap ({GAP_FRAGMENTS[r.fragment]}, {r.gap_to_main_m} m)",
            "coords": [(r.gap_from_lat, r.gap_from_lon), (r.gap_to_lat, r.gap_to_lon)],
        }
        for r in rows.itertuples()
    ]


def padded_bbox(bounds_lonlat, pad_m: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of lon/lat bounds expanded by pad_m metres."""
    w, s, e, n = bounds_lonlat
    dlat = pad_m / 110_574
    dlon = pad_m / (111_320 * math.cos(math.radians((s + n) / 2)))
    return (round(s - dlat, 6), round(w - dlon, 6), round(n + dlat, 6), round(e + dlon, 6))


def build_query(corridors: list[dict], bbox: tuple, radius_m: int = CORRIDOR_M, timeout: int = 90) -> str:
    areas = [
        (c["label"], f"around:{radius_m}," + ",".join(f"{lat:.6f},{lon:.6f}" for lat, lon in c["coords"]))
        for c in corridors
    ]
    areas.append((f"{BBOX_FRAGMENT} bbox + {BBOX_PAD_M} m", ",".join(f"{v:.6f}" for v in bbox)))
    lines = [f"[out:json][timeout:{timeout}];", "("]
    for label, area in areas:
        lines.append(f"  // {label}")
        lines += [f"  way{sel}({area});" for sel in WAY_SELECTORS]
        lines += [f"  node{sel}({area});" for sel in NODE_SELECTORS]
    lines += [");", "out meta;", ">;", "out meta qt;"]
    return "\n".join(lines) + "\n"


def validate_query(q: str, corridors: list[dict], bbox: tuple) -> list[str]:
    """Static checks (no request is sent). Returns a list of problems; empty means valid."""
    problems = []
    body = re.sub(r"//[^\n]*", "", q)
    if body.count("(") != body.count(")") or body.count("[") != body.count("]"):
        problems.append("unbalanced brackets")
    if not q.startswith("[out:json]"):
        problems.append("output format is not JSON")
    stmts = [ln.strip() for ln in body.splitlines() if ln.strip() and ln.strip() not in ("(",)]
    if any(not ln.endswith(";") for ln in stmts):
        problems.append("a statement does not end with ';'")
    if '["access"!' in q or '["foot"!' in q:
        problems.append("access/foot exclusion found: the query must not filter on access")
    s, w, n, e = bbox
    if not (s < n and w < e):
        problems.append("bbox is not (south, west, north, east)")
    for c in corridors:
        for lat, lon in c["coords"]:
            if not (LAT_RANGE[0] < lat < LAT_RANGE[1] and LON_RANGE[0] < lon < LON_RANGE[1]):
                problems.append(
                    f"{c['label']}: coordinate {lat},{lon} outside the study area (lat/lon swapped?)"
                )
    for v, rng in ((s, LAT_RANGE), (n, LAT_RANGE), (w, LON_RANGE), (e, LON_RANGE)):
        if not rng[0] < v < rng[1]:
            problems.append(f"bbox value {v} outside the study area")
    f001 = [c for c in corridors if c["label"].startswith(BBOX_FRAGMENT)]
    for c in f001:
        if not all(s <= lat <= n and w <= lon <= e for lat, lon in c["coords"]):
            problems.append("the F001 gap is not inside the F001 bbox")
    n_areas = len(corridors) + 1
    if q.count("way[") != n_areas * len(WAY_SELECTORS) or q.count("node[") != n_areas * len(NODE_SELECTORS):
        problems.append("selector count mismatch")
    return problems


def plan(s: Settings) -> dict:
    m03 = s.processed_dir / "review" / "m03"
    frags = pd.read_csv(m03 / "network_fragments.csv")
    corridors = corridors_from_fragments(frags)
    geo = gpd.read_file(m03 / "validation.gpkg", layer="network_fragments")
    bounds = geo.loc[geo["fragment"] == BBOX_FRAGMENT].to_crs(4326).total_bounds
    bbox = padded_bbox(bounds, BBOX_PAD_M)
    q = build_query(corridors, bbox)
    s_, w_, n_, e_ = bbox
    area_km2 = (n_ - s_) * 110.574 * (e_ - w_) * 111.320 * math.cos(math.radians((s_ + n_) / 2))
    return {
        "query": q,
        "corridors": corridors,
        "bbox_swne": bbox,
        "bbox_area_km2": round(area_km2, 3),
        "problems": validate_query(q, corridors, bbox),
    }


def fetch(s: Settings, allow_download: bool = False) -> dict:
    p = plan(s)
    if p["problems"]:
        raise ValueError(f"query failed validation: {p['problems']}")
    if not allow_download:
        log.info("dry run: query built and validated, nothing downloaded")
        return p
    out_dir = s.raw_dir / "osm_targeted"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir / f"m04_gaps_{stamp}"
    dest, qfile, meta = (base.with_suffix(x) for x in (".json", ".overpassql", ".meta.json"))
    if dest.exists():
        raise FileExistsError(dest)
    log.info("POST %s (%d bytes of query)", ENDPOINT, len(p["query"]))
    r = requests.post(ENDPOINT, data={"data": p["query"]}, headers={"User-Agent": USER_AGENT}, timeout=180)
    r.raise_for_status()
    data = r.json()  # fails loudly on an Overpass error page
    # Written only after a valid response, so a failed attempt leaves nothing behind.
    qfile.write_text(p["query"], encoding="utf-8")
    dest.write_bytes(r.content)
    osm3s = data.get("osm3s", {})
    info = {
        "endpoint": ENDPOINT,
        "requested_utc": stamp,
        "timestamp_osm_base": osm3s.get("timestamp_osm_base"),
        "remark": data.get("remark"),
        "elements": len(data.get("elements", [])),
        "query_file": qfile.name,
        "query_sha256": sha256(qfile),
        "response_sha256": sha256(dest),
        "corridor_radius_m": CORRIDOR_M,
        "bbox_swne": p["bbox_swne"],
        "corridors": p["corridors"],
        "purpose": "Milestone 04 Phase A: tags of ways and nodes in the walk-network gaps, including "
        "ways the osmnx walk filter excludes. Evidence only; never used by the network build.",
    }
    meta.write_text(json.dumps(info, indent=2), encoding="utf-8")
    record(
        s.raw_dir,
        dest,
        ENDPOINT,
        "ODbL 1.0 (OpenStreetMap contributors)",
        source="OpenStreetMap via Overpass API (targeted query, Milestone 04)",
        timestamp_osm_base=info["timestamp_osm_base"],
        query_file=f"osm_targeted/{qfile.name}",
        query_sha256=info["query_sha256"],
    )
    return {**p, "snapshot": dest, "meta": info}


EVIDENCE_TAGS = ["highway", "access", "foot", "service", "barrier", "name", "surface", "bridge",
                 "man_made", "tunnel", "noexit", "entrance", "layer"]  # fmt: skip


def snapshot_evidence(
    snap: dict, walk_ways: dict, way_component: dict[int, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evidence from a targeted snapshot (never applied to the network).

    Returns (elements, link_candidates). `elements`: every tagged way and node with its tags, edit
    version/timestamp, and whether the walk cache holds it (False = excluded by the osmnx filter or
    new since the cache). `link_candidates`: groups of ways that are NOT in the walk network, chained by
    shared nodes, that touch both a fragment and the main network. Each is a possible link to verify
    (its tags decide its mapped access status, see abot.access); none is added.
    """
    els = snap.get("elements", [])
    ways = [e for e in els if e["type"] == "way"]
    comp_nodes: dict[str, set] = {}
    for wid, comp in way_component.items():
        comp_nodes.setdefault(comp, set()).update(walk_ways.get(wid, {}).get("nodes", []))
    rows = []
    for e in els:
        t = e.get("tags", {})
        if not t:
            continue
        rows.append(
            {
                "type": e["type"], "id": e["id"], "in_walk_cache": e["id"] in walk_ways if e["type"] == "way" else None,
                **{k: t.get(k) for k in EVIDENCE_TAGS}, "version": e.get("version"), "timestamp": e.get("timestamp"),
                "lon": e.get("lon"), "lat": e.get("lat"),
                "touches": ";".join(sorted(c for c, ns in comp_nodes.items() if set(e.get("nodes", [])) & ns)),
            }
        )  # fmt: skip
    excluded = [w for w in ways if w["id"] not in walk_ways and "highway" in w.get("tags", {})]
    # union-find over excluded ways that share a node
    parent = {w["id"]: w["id"] for w in excluded}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_node: dict[int, int] = {}
    for w in excluded:
        for n in w["nodes"]:
            if n in by_node:
                parent[find(w["id"])] = find(by_node[n])
            else:
                by_node[n] = w["id"]
    groups: dict[int, list] = {}
    for w in excluded:
        groups.setdefault(find(w["id"]), []).append(w)
    links = []
    for ws in groups.values():
        nodes = {n for w in ws for n in w["nodes"]}
        touched = sorted(c for c, ns in comp_nodes.items() if nodes & ns)
        if "main" in touched and any(c != "main" for c in touched):
            links.append(
                {
                    "ways": ";".join(f"way/{w['id']}" for w in sorted(ws, key=lambda x: x["id"])),
                    "connects": ";".join(touched),
                    "tags": json.dumps([w.get("tags", {}) for w in sorted(ws, key=lambda x: x["id"])], ensure_ascii=False),
                    "applied": False,
                }
            )  # fmt: skip
    return pd.DataFrame(rows), pd.DataFrame(links, columns=["ways", "connects", "tags", "applied"])


# Legacy column `public_pedestrian_access` (kept so earlier references read the same): restricted when
# the path's public pedestrian status is one of these; otherwise unverified (never "public").
RESTRICTED_PUBLIC_STATUS = {"prohibited", "not_public", "customers_only", "destination_only_assumed"}


def _m(a: tuple, b: tuple) -> float:
    """Metres between two (lon, lat) points (equirectangular; fine at corridor scale)."""
    return math.hypot((a[0] - b[0]) * 111_320 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110_574)


def corridor_analysis(
    snap: dict, walk_ways: dict, walk_nodes: dict, way_component: dict[int, str], candidates: pd.DataFrame
) -> pd.DataFrame:
    """Geometry and access evidence for each link candidate, one row per (candidate, fragment).

    Physical connection is judged from OSM topology only (shared node ids between the candidate ways
    and the ways of each component; crossings without a shared node are counted, not used). Public
    pedestrian access is judged from mapped tags only: it is never inferred from connectivity. The path
    takes the most restrictive status of ANY way or gate on it (one private way is enough); a path with
    no mapped gate gains nothing from that. Nothing is applied to any network.
    """
    import networkx as nx

    from abot.access import access_assessment, most_restrictive

    snodes = {e["id"]: e for e in snap.get("elements", []) if e["type"] == "node"}
    sways = {e["id"]: e for e in snap.get("elements", []) if e["type"] == "way"}

    def ll(n):
        e = snodes.get(n) or walk_nodes.get(n)
        return (e["lon"], e["lat"]) if e else None

    node_comp: dict[int, set] = {}
    for wid, comp in way_component.items():
        for n in walk_ways.get(wid, {}).get("nodes", []):
            node_comp.setdefault(n, set()).add(comp)
    rows = []
    for k, cand in enumerate(candidates.itertuples(), start=1):
        ids = [int(w.split("/")[1]) for w in cand.ways.split(";")]
        H = nx.Graph()
        for wid in ids:
            ns = sways[wid]["nodes"]
            for a, b in zip(ns, ns[1:], strict=False):
                H.add_edge(a, b, length=_m(ll(a), ll(b)), way=wid)
        touch: dict[str, list] = {}
        for n in sorted(H.nodes):
            for c in sorted(node_comp.get(n, ())):
                touch.setdefault(c, []).append(n)
        gates_all = sorted(n for n in H.nodes if "barrier" in snodes.get(n, {}).get("tags", {}))
        access_tags = sorted({json.dumps({t: sways[w]["tags"][t] for t in ("access", "foot") if t in sways[w]["tags"]})
                              for w in ids})  # fmt: skip
        for frag in sorted(c for c in touch if c != "main"):
            best = None
            for a in touch[frag]:
                for b in touch.get("main", []):
                    try:
                        d = nx.shortest_path_length(H, a, b, weight="length")
                    except nx.NetworkXNoPath:
                        continue
                    if best is None or (d, a, b) < best:
                        best = (d, a, b)
            row = {
                "candidate": k, "fragment": frag, "candidate_ways": len(ids),
                "fragment_contact_nodes": ";".join(f"node/{n}" for n in touch[frag]),
                "main_contact_nodes": ";".join(f"node/{n}" for n in touch.get("main", [])),
                "corridor_access_tags": " | ".join(access_tags),
                "corridor_gates": "; ".join(f"node/{n} {json.dumps(snodes[n]['tags'], sort_keys=True)}" for n in gates_all) or "none",
            }  # fmt: skip
            if best is None:
                row.update(path_m=None, path_ways="", path_gates="", physical_connection="not_confirmed",
                           path_mapped_access_status="", public_pedestrian_status="unknown",
                           authorized_group="unknown", classification_reason="no path in OSM topology",
                           public_pedestrian_access="unverified")  # fmt: skip
            else:
                d, a, b = best
                path = nx.shortest_path(H, a, b, weight="length")
                pw = []
                for x, y in zip(path, path[1:], strict=False):
                    if not pw or pw[-1] != H[x][y]["way"]:
                        pw.append(H[x][y]["way"])
                pg = [n for n in path if "barrier" in snodes.get(n, {}).get("tags", {})]
                assessed = [(f"way/{w}", access_assessment(sways[w]["tags"])) for w in dict.fromkeys(pw)]
                assessed += [(f"node/{n}", access_assessment(snodes[n]["tags"], gate=True)) for n in pg]
                worst = most_restrictive(x["mapped_access_status"] for _, x in assessed)
                el, dec = next((e, x) for e, x in assessed if x["mapped_access_status"] == worst)
                why = f"most restrictive on the path: {el} {dec['classification_reason']}"
                if not pg:
                    why += "; no gate mapped on the path: not evidence of public access"
                row.update(
                    path_m=round(d, 1), path_from=f"node/{a}", path_to=f"node/{b}",
                    path_ways=";".join(f"way/{w}" for w in pw),
                    path_gates="; ".join(f"node/{n} {json.dumps(snodes[n]['tags'], sort_keys=True)}" for n in pg) or "none",
                    physical_connection="confirmed_in_osm_topology",
                    path_mapped_access_status=worst,
                    public_pedestrian_status=dec["public_pedestrian_status"],
                    authorized_group=dec["authorized_group"],
                    classification_reason=why,
                    public_pedestrian_access="restricted_by_mapped_tags"
                    if dec["public_pedestrian_status"] in RESTRICTED_PUBLIC_STATUS else "unverified",
                )  # fmt: skip
            row["field_verification_needed"] = True  # topology and tags are mapped claims, not site facts
            row["applied"] = False
            rows.append(row)
    return pd.DataFrame(rows)


def load_latest(s: Settings) -> tuple[dict, dict] | None:
    files = sorted((s.raw_dir / "osm_targeted").glob("m04_gaps_*Z.json"))
    if not files:
        return None
    f = files[-1]
    return json.loads(f.read_text(encoding="utf-8")), json.loads(
        Path(str(f).replace(".json", ".meta.json")).read_text(encoding="utf-8")
    )
