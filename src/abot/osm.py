"""OpenStreetMap road networks (walk, drive), barrier features, and categorised public facilities.

Everything is fetched for the city boundary plus a buffer so that trips and facilities just
across the city limit are not cut off. Raw Overpass responses are cached under
data/raw/osm_cache (ODbL 1.0 — attribution required); every response used by a run is recorded
with its Overpass snapshot timestamp and SHA-256 in interim/osm_provenance.json and the raw manifest.

Facilities keep their OSM identity (type, id, tags). Each feature gets a primary category, the
list of every category it matches, and for each category a sub-type, a reporting tier, a
classification status and a human-readable reason. Nothing is dropped silently: merged
duplicates and unmatched features are written to facility_exclusions.csv.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from datetime import UTC, datetime
from importlib.metadata import version

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

from abot import boundaries, qa
from abot.config import Settings
from abot.fetch.common import load_manifest, sha256

log = logging.getLogger(__name__)

# Tags copied into their own columns for convenience. All tags are kept in `osm_tags` (JSON).
TAG_COLUMNS = [
    "amenity",
    "healthcare",
    "shop",
    "office",
    "emergency",
    "social_facility",
    "social_facility:for",
    "operator",
    "operator:type",
    "isced:level",
    "townhall:type",
    "admin_level",
    "government",
    "ref",
    "brand",
    "description",
]
NON_TAG_COLUMNS = {"element", "id", "osm_type", "osm_id", "geometry", "nodes", "ways"}
TIERS = ("indicative", "descriptive", "excluded")


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


# --- Overpass provenance -----------------------------------------------------------------


@contextlib.contextmanager
def track_overpass(label: str, used: list[dict]):
    """Record which cached Overpass responses a fetch reads or writes.

    osmnx keys its cache by the SHA-1 of the request URL; wrapping its two cache functions is the
    only way to learn which files a call used. osmnx is pinned in uv.lock, so the private API is
    stable for this project.
    """
    from osmnx import _http

    orig_get, orig_save = _http._retrieve_from_cache, _http._save_to_cache

    def _get(url):
        data = orig_get(url)
        if data is not None:
            used.append({"label": label, "file": _http._resolve_cache_filepath(url), "cache_hit": True})
        return data

    def _save(url, response_json, ok):
        orig_save(url, response_json, ok)
        used.append({"label": label, "file": _http._resolve_cache_filepath(url), "cache_hit": False})

    _http._retrieve_from_cache, _http._save_to_cache = _get, _save
    try:
        yield
    finally:
        _http._retrieve_from_cache, _http._save_to_cache = orig_get, orig_save


def provenance_records(s: Settings, used: list[dict]) -> list[dict]:
    records = []
    for u in used:
        f = u["file"]
        if not f.is_file():
            continue
        meta = json.loads(f.read_text(encoding="utf-8"))
        records.append(
            {
                "label": u["label"],
                "cache_file": f.relative_to(s.raw_dir).as_posix(),
                "cache_hit": u["cache_hit"],
                "overpass_timestamp_osm_base": (meta.get("osm3s") or {}).get("timestamp_osm_base"),
                "elements": len(meta.get("elements", [])),
                "file_written_utc": datetime.fromtimestamp(f.stat().st_mtime, UTC).isoformat(
                    timespec="seconds"
                ),
                "bytes": f.stat().st_size,
                "sha256": sha256(f),
            }
        )
    return records


def write_provenance(s: Settings, records: list[dict], query: dict) -> None:
    doc = {
        "run": s.run_name or "baseline",
        "boundary_buffer_m": s["osm"]["boundary_buffer_m"],
        "osmnx_version": version("osmnx"),
        "overpass_endpoint": ox.settings.overpass_url,
        "queries": query,
        "responses": records,
    }
    (s.interim_dir / "osm_provenance.json").write_text(
        json.dumps(doc, indent=2, default=str), encoding="utf-8"
    )

    # Also add each response to the shared raw manifest (adds keys; never rewrites other entries).
    manifest = load_manifest(s.raw_dir)
    run = s.run_name or "baseline"
    for r in records:
        previous = manifest.get(r["cache_file"], {})
        manifest[r["cache_file"]] = {
            "source": "OpenStreetMap via Overpass API (osmnx cache)",
            "url": ox.settings.overpass_url,
            "licence": "ODbL 1.0",
            "query_label": r["label"],
            "boundary_buffer_m": s["osm"]["boundary_buffer_m"],
            # A cached response can serve several runs (e.g. baseline and a speed variant).
            "used_by_runs": sorted(set(previous.get("used_by_runs", [])) | {run}),
            "overpass_timestamp_osm_base": r["overpass_timestamp_osm_base"],
            "retrieved_utc": r["file_written_utc"],
            "bytes": r["bytes"],
            "sha256": r["sha256"],
        }
    (s.raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# --- networks -----------------------------------------------------------------------------


def class_speed(highway, speeds: dict, fallback: float) -> tuple[float, str]:
    """Configured speed for an edge's highway class -> (km/h, source).

    A simplified edge that merges segments of several classes carries a list, whose order comes from a
    set inside osmnx and so changes between Python processes. Taking its first element (Milestone 02)
    made drive times non-reproducible; the slowest configured class is used instead (deterministic,
    and conservative for a lower-bound travel time).
    """
    classes = highway if isinstance(highway, list) else [highway]
    known = [speeds[h] for h in classes if h in speeds]
    return (float(min(known)), "config") if known else (float(fallback), "fallback")


def parse_maxspeed(value) -> float | None:
    """Numeric km/h from an OSM maxspeed value (lists from simplification -> lowest value)."""
    values = value if isinstance(value, list) else [value]
    speeds = []
    for v in values:
        if not isinstance(v, str | int | float) or (isinstance(v, float) and np.isnan(v)):
            continue
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(mph)?\s*$", str(v))
        if m:
            speeds.append(float(m.group(1)) * (1.609344 if m.group(2) else 1.0))
    return min(speeds) if speeds else None


def assign_drive_speeds(G: nx.MultiDiGraph, speeds: dict, fallback: float, policy: str) -> nx.MultiDiGraph:
    """Set `speed_kph`, `speed_source` and `travel_time` (s) on every edge.

    speed_source is one of: config, fallback (class not in config), maxspeed_cap (a lower legal
    limit reduced the configured speed) or maxspeed (override policy only).
    """
    if policy not in ("cap", "ignore", "override"):
        raise ValueError(f"unknown maxspeed_policy {policy!r}")
    for _, _, d in G.edges(data=True):
        speed, source = class_speed(d.get("highway"), speeds, fallback)
        tagged = parse_maxspeed(d.get("maxspeed")) if policy != "ignore" else None
        if tagged is not None and tagged > 0:
            if policy == "override" or (policy == "cap" and tagged < speed):
                speed, source = tagged, ("maxspeed" if policy == "override" else "maxspeed_cap")
        d["speed_kph"] = float(speed)
        d["speed_source"] = source
        d["travel_time"] = d["length"] / (speed / 3.6)
    return G


def build_graph(s: Settings, polygon, mode: str) -> tuple[nx.MultiDiGraph, dict]:
    acc = s["accessibility"]
    # retain_all=True uses the same Overpass query (and cache) as retain_all=False; it lets us
    # measure what the largest-component filter removes.
    G_all = ox.graph_from_polygon(polygon, network_type=mode, simplify=True, retain_all=True)
    comps = list(nx.weakly_connected_components(G_all))
    G = ox.truncate.largest_component(G_all, strongly=(mode == "drive"))
    stats = {
        "weak_components": len(comps),
        "nodes_all": G_all.number_of_nodes(),
        "nodes_kept": G.number_of_nodes(),
        "edges_all": G_all.number_of_edges(),
        "edges_kept": G.number_of_edges(),
        "length_dropped_km": round(
            (
                sum(d["length"] for *_, d in G_all.edges(data=True))
                - sum(d["length"] for *_, d in G.edges(data=True))
            )
            / 1000,
            2,
        ),
    }

    if mode == "drive":
        G = assign_drive_speeds(
            G, acc["drive_speeds_kmh"], acc["drive_speed_fallback_kmh"], acc["maxspeed_policy"]
        )
    else:
        mps = acc["walk_speed_kmh"] / 3.6
        times = {(u, v, k): d["length"] / mps for u, v, k, d in G.edges(keys=True, data=True)}
        nx.set_edge_attributes(G, times, "travel_time")

    return ox.projection.project_graph(G, to_crs=s.projected_crs), stats


def load_graph(s: Settings, mode: str) -> nx.MultiDiGraph:
    return ox.io.load_graphml(graph_path(s, mode))


def _edges_for_gpkg(G) -> gpd.GeoDataFrame:
    edges = ox.convert.graph_to_gdfs(G, nodes=False).reset_index()
    cols = [
        "u",
        "v",
        "key",
        "highway",
        "name",
        "length",
        "maxspeed",
        "speed_kph",
        "speed_source",
        "travel_time",
        "geometry",
    ]
    edges = edges[[c for c in cols if c in edges.columns]].copy()
    for c in ("highway", "name", "maxspeed"):  # simplified edges may hold lists, which GPKG cannot store
        if c in edges:
            edges[c] = edges[c].map(lambda v: ";".join(sorted(map(str, v))) if isinstance(v, list) else v)
    return edges


def features_in_area(polygon, tags: dict) -> gpd.GeoDataFrame:
    """OSM features with `tags` that intersect `polygon` (EPSG:4326).

    Queried by the polygon's bounding box and clipped locally: osmnx repeats the polygon in the
    Overpass query once per tag value, and the detailed coastline then makes the request too large
    for the server (HTTP 413). The selected features are the same.
    """
    west, south, east, north = polygon.bounds
    raw = ox.features_from_bbox((west, south, east, north), tags=tags)
    return raw[raw.intersects(polygon)].reset_index()


# --- barriers -----------------------------------------------------------------------------


def barrier_kind(row, spec: dict) -> str | None:
    """water_area | water_line | culverted_waterway (not a barrier) | wall (flag only) | None."""
    if _tags_match(row, spec["hard"]):
        if row.geometry.geom_type.endswith("Polygon"):
            return "water_area"
        # A culverted or tunnelled watercourse runs under the ground surface: walkable over it.
        if tag_values(row.get("tunnel")) and tag_values(row.get("tunnel")) != ["no"]:
            return "culverted_waterway"
        return "water_line"
    if _tags_match(row, spec["soft"]):
        return "wall"
    return None


def build_barriers(s: Settings, polygon) -> gpd.GeoDataFrame:
    """Water areas, watercourses/coastline (hard) and walls (soft) for connector checks."""
    spec = s["osm"]["barriers"]
    tags = _query_tags({"hard": spec["hard"], "soft": spec["soft"]})
    raw = features_in_area(polygon, tags)
    raw = raw.drop(columns=["osm_type", "osm_id"], errors="ignore").rename(
        columns={"element": "osm_type", "id": "osm_id"}
    )
    raw = raw[raw.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString"])].to_crs(
        s.projected_crs
    )

    raw["kind"] = raw.apply(barrier_kind, axis=1, spec=spec)
    keep = [
        "osm_type",
        "osm_id",
        "kind",
        "natural",
        "water",
        "waterway",
        "landuse",
        "barrier",
        "name",
        "geometry",
    ]
    out = raw[raw["kind"].notna()]
    return out[[c for c in keep if c in out.columns]].reset_index(drop=True)


def load_barriers(s: Settings) -> gpd.GeoDataFrame | None:
    try:
        return gpd.read_file(s.gpkg, layer="barriers")
    except Exception:  # noqa: BLE001 — older outputs have no barrier layer
        return None


# --- facility classification ----------------------------------------------------------------


def tag_values(value) -> list[str]:
    """OSM tag value -> list of values (`a;b` -> [a, b]); missing -> []."""
    if not isinstance(value, str):
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def _tags_match(row, tags: dict | None) -> list[str]:
    """Return the `key=value` strings in `row` that match `tags` (empty list = no match)."""
    hits = []
    for key, wanted in (tags or {}).items():
        for v in tag_values(row.get(key)):
            if wanted is True or v in [str(w) for w in wanted]:
                hits.append(f"{key}={v}")
    return hits


def _regex_match(row, patterns: dict | None) -> list[str]:
    hits = []
    for key, pattern in (patterns or {}).items():
        v = row.get(key)
        if isinstance(v, str) and re.search(pattern, v):
            hits.append(f"{key}~/{pattern}/")
    return hits


def _spec_tags(spec: dict) -> dict:
    """Category spec -> its tag mapping (a flat {key: values} dict is accepted for brevity)."""
    return spec["tags"] if "tags" in spec else spec


def category_hits(row, spec: dict) -> list[str]:
    if "tags" in spec and _tags_match(row, spec.get("exclude")):
        return []
    return _tags_match(row, _spec_tags(spec)) + _regex_match(
        row, spec.get("regex") if "tags" in spec else None
    )


def categorise(row: pd.Series, categories: dict, priority: list[str]) -> str | None:
    """Primary category: the first category in `priority` that the feature matches."""
    for cat in priority:
        if category_hits(row, categories[cat]):
            return cat
    return None


def all_categories(row: pd.Series, categories: dict, priority: list[str]) -> list[str]:
    return [cat for cat in priority if category_hits(row, categories[cat])]


def classify_subtype(row: pd.Series, rules: list[dict]) -> dict:
    """First matching sub-type rule -> {subtype, tier, status, reason}."""
    for rule in rules:
        all_ok = all(_tags_match(row, {k: v}) for k, v in (rule.get("all") or {}).items())
        if not all_ok:
            continue
        hits = _tags_match(row, rule.get("any")) + _regex_match(row, rule.get("regex"))
        if (rule.get("any") or rule.get("regex")) and not hits:
            continue
        evidence = _tags_match(row, rule.get("all")) + hits
        reason = "; ".join(evidence) if evidence else "fallback rule (no more specific rule matched)"
        if rule.get("note"):
            reason += f" — {rule['note']}"
        return {
            "subtype": rule["subtype"],
            "tier": rule["tier"],
            "status": rule.get("status", "tag_rule" if evidence else "fallback"),
            "reason": reason,
        }
    return {
        "subtype": "unclassified",
        "tier": "descriptive",
        "status": "ambiguous",
        "reason": "no sub-type rule matched",
    }


def validate_facility_config(s: Settings) -> None:
    cats = s["facilities"]
    for cat, spec in cats.items():
        for rule in spec.get("subtypes", []):
            if rule["tier"] not in TIERS:
                raise ValueError(f"{cat}.{rule['subtype']}: tier must be one of {TIERS}")
    for group, g in s["indicator_groups"].items():
        rules = {r["subtype"]: r["tier"] for r in cats[g["category"]].get("subtypes", [])}
        for st in g["subtypes"]:
            if rules.get(st) != "indicative":
                raise ValueError(
                    f"indicator group {group}: {g['category']}.{st} is not an indicative sub-type"
                )


def _query_tags(categories: dict) -> dict:
    tags: dict = {}
    for spec in categories.values():
        for key, vals in _spec_tags(spec).items():
            if vals is True or tags.get(key) is True:
                tags[key] = True
            else:
                tags[key] = sorted(set(tags.get(key, [])) | {str(v) for v in vals})
    return tags


def _osm_tags_json(row: pd.Series) -> str:
    tags = {
        k: v
        for k, v in row.items()
        if k not in NON_TAG_COLUMNS and isinstance(v, str | int | float) and pd.notna(v)
    }
    return json.dumps(tags, ensure_ascii=False, sort_keys=True, default=str)


def _merge_points_inside_polygons(fac: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """OSM often maps one facility as both a building polygon and a node inside it; keep the polygon.

    Returns the kept features and a record of every merged node (never dropped silently).
    """
    polys = fac[fac.geom_type.isin(["Polygon", "MultiPolygon"])]
    nodes = fac[fac["osm_type"] == "node"]
    empty = pd.DataFrame(columns=["osm_type", "osm_id", "name", "category", "reason"])
    if polys.empty or nodes.empty:
        return fac, empty
    hits = gpd.sjoin(nodes, polys[["category", "osm_type", "osm_id", "geometry"]], predicate="within")
    hits = hits[hits["category_left"] == hits["category_right"]]
    hits = hits[~hits.index.duplicated()]
    merged = pd.DataFrame(
        {
            "osm_type": hits["osm_type_left"],
            "osm_id": hits["osm_id_left"],
            "name": hits["name"],
            "category": hits["category_left"],
            "reason": "point inside a same-category polygon "
            + hits["osm_type_right"].astype(str)
            + "/"
            + hits["osm_id_right"].astype(str)
            + "; merged into the polygon",
        }
    )
    return fac.drop(index=hits.index), merged


def _normalise_name(name) -> str | None:
    return re.sub(r"[^a-z0-9]", "", name.lower()) if isinstance(name, str) and name.strip() else None


def possible_duplicates(fac: gpd.GeoDataFrame, max_m: float = 50.0) -> pd.DataFrame:
    """Same primary category, same normalised name, within `max_m`: flagged for review, kept."""
    from scipy.spatial import cKDTree

    cols = [
        "osm_type",
        "osm_id",
        "name",
        "category",
        "reason",
        "related_osm_type",
        "related_osm_id",
        "distance_m",
    ]
    if len(fac) < 2:
        return pd.DataFrame(columns=cols)
    xy = np.column_stack([fac.geometry.x, fac.geometry.y])
    names = fac["name"].map(_normalise_name).to_numpy()
    cats = fac["category"].to_numpy()
    rows = []
    for i, j in sorted(cKDTree(xy).query_pairs(max_m)):
        if cats[i] == cats[j] and names[i] is not None and names[i] == names[j]:
            a, b = fac.iloc[i], fac.iloc[j]
            d = float(np.hypot(*(xy[i] - xy[j])))
            rows.append(
                {
                    "osm_type": b["osm_type"],
                    "osm_id": b["osm_id"],
                    "name": b["name"],
                    "category": b["category"],
                    "reason": f"possible duplicate of {a['osm_type']}/{a['osm_id']} ({d:.0f} m, same name); kept, review",
                    "related_osm_type": a["osm_type"],
                    "related_osm_id": a["osm_id"],
                    "distance_m": round(d, 1),
                }
            )
    return pd.DataFrame(rows, columns=cols)


def classify_features(raw: pd.DataFrame, s: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add primary category, all categories, and per-category sub-type records.

    Returns (features with primary classification, long table of (feature, category) roles).
    """
    categories, priority = s["facilities"], s["category_priority"]
    raw = raw.copy()
    raw["categories"] = raw.apply(all_categories, axis=1, categories=categories, priority=priority)
    raw["category"] = raw["categories"].map(lambda c: c[0] if c else None)
    roles = []
    for idx, row in raw.iterrows():
        for cat in row["categories"]:
            c = classify_subtype(row, categories[cat].get("subtypes", []))
            roles.append(
                {
                    "fidx": idx,
                    "category": cat,
                    "primary": cat == row["category"],
                    **c,
                    "category_evidence": "; ".join(category_hits(row, categories[cat])),
                }
            )
    return raw, pd.DataFrame(roles)


def build_facilities(s: Settings, polygon) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    validate_facility_config(s)
    raw = features_in_area(polygon, _query_tags(s["facilities"]))
    # Some mappers add literal `osm_id`/`osm_type` tags; drop them so they can't clash.
    raw = raw.drop(columns=["osm_type", "osm_id"], errors="ignore")
    raw = raw.rename(columns={"element": "osm_type", "id": "osm_id"})
    raw["osm_tags"] = raw.apply(_osm_tags_json, axis=1)

    raw, roles = classify_features(raw, s)
    unmatched = raw[raw["category"].isna()]
    exclusions = [
        pd.DataFrame(
            {
                "osm_type": unmatched["osm_type"],
                "osm_id": unmatched["osm_id"],
                "name": unmatched.get("name"),
                "category": None,
                "reason": "returned by the Overpass tag query but matches no category (e.g. excluded tag)",
            }
        )
    ]
    fac = raw[raw["category"].notna()].copy()
    keep = ["osm_type", "osm_id", "name", "category", "categories", *TAG_COLUMNS, "osm_tags", "geometry"]
    fac = fac[[c for c in keep if c in fac.columns]]
    fac = gpd.GeoDataFrame(fac, geometry="geometry", crs=raw.crs).to_crs(s.projected_crs)
    n_before = len(fac)
    fac, merged = _merge_points_inside_polygons(fac)
    exclusions.append(merged)
    log.info("facilities: %d matched, %d after merging points inside polygons", n_before, len(fac))

    fac["geom_source"] = np.where(fac.geom_type == "Point", "node", "representative_point")
    fac["geometry"] = fac.geometry.representative_point()
    city, _ = boundaries.load(s)
    fac["inside_city"] = fac.within(city.union_all())

    roles = roles[roles["fidx"].isin(fac.index)]
    prim = roles[roles["primary"]].set_index("fidx")
    fac["subtype"] = prim["subtype"]
    fac["tier"] = prim["tier"]
    fac["class_status"] = prim["status"]
    fac["class_reason"] = prim["reason"]
    fac["categories"] = fac["categories"].map(";".join)

    exclusions.append(possible_duplicates(fac))
    fac = fac.reset_index(names="fidx")
    fac["fid_key"] = fac["osm_type"].astype(str) + "/" + fac["osm_id"].astype(str)

    role_cols = ["fidx", "category", "subtype", "tier", "status", "reason", "category_evidence", "primary"]
    roles = roles[role_cols].merge(
        fac[["fidx", "fid_key", "osm_type", "osm_id", "name", "inside_city", "geometry"]], on="fidx"
    )
    roles = gpd.GeoDataFrame(roles.drop(columns="fidx"), geometry="geometry", crs=fac.crs)
    fac = fac.drop(columns="fidx")
    excl = pd.concat([e for e in exclusions if not e.empty], ignore_index=True)
    return fac, roles, excl


def load_roles(s: Settings) -> gpd.GeoDataFrame:
    return gpd.read_file(s.gpkg, layer="facility_roles")


def build(s: Settings) -> None:
    _configure_osmnx(s)
    polygon = study_area(s)
    checks: dict = {}
    used: list[dict] = []

    for mode in s["osm"]["network_types"]:
        log.info("fetching %s network ...", mode)
        with track_overpass(f"network_{mode}", used):
            G, comp = build_graph(s, polygon, mode)
        ox.io.save_graphml(G, graph_path(s, mode))
        _edges_for_gpkg(G).to_file(s.gpkg, layer=f"network_{mode}", driver="GPKG")
        checks[f"{mode}_nodes"] = qa.check(G.number_of_nodes() > 1000, G.number_of_nodes())
        checks[f"{mode}_edges"] = qa.check(None, G.number_of_edges())
        checks[f"{mode}_length_km"] = qa.check(
            None,
            round(sum(d["length"] for *_, d in G.edges(data=True)) / 1000, 1),
            "directed edges: two-way streets are counted in both directions",
        )
        kept_share = comp["nodes_kept"] / comp["nodes_all"]
        checks[f"{mode}_components_before_filter"] = qa.check(
            None, comp["weak_components"], "weakly connected pieces fetched"
        )
        checks[f"{mode}_nodes_kept_pct"] = qa.check(
            kept_share > 0.95,
            round(100 * kept_share, 2),
            f"largest {'strongly' if mode == 'drive' else 'weakly'} connected component; "
            f"{comp['nodes_all'] - comp['nodes_kept']} nodes, {comp['length_dropped_km']} km dropped",
        )
        if mode == "drive":
            src = pd.Series([d["speed_source"] for *_, d in G.edges(data=True)]).value_counts()
            mixed = sum(isinstance(d.get("highway"), list) for *_, d in G.edges(data=True))
            checks["drive_edges_mixed_class"] = qa.check(
                None, mixed, "merged edges spanning several highway classes: slowest configured class used"
            )
            checks["drive_speed_policy"] = qa.check(
                None, s["accessibility"]["maxspeed_policy"], "use of OSM maxspeed"
            )
            for name in ("config", "maxspeed_cap", "maxspeed", "fallback"):
                checks[f"drive_edges_speed_{name}"] = qa.check(
                    None if name != "fallback" else int(src.get(name, 0)) == 0,
                    int(src.get(name, 0)),
                    {
                        "config": "speed from the configured class table",
                        "maxspeed_cap": "lower tagged maxspeed reduced the configured speed",
                        "maxspeed": "tagged maxspeed replaced the configured speed (override policy)",
                        "fallback": "highway class missing from the config table",
                    }[name],
                )

    log.info("fetching barrier features ...")
    with track_overpass("barriers", used):
        bar = build_barriers(s, polygon)
    bar.to_file(s.gpkg, layer="barriers", driver="GPKG")
    for k, n in bar["kind"].value_counts().items():
        checks[f"barriers_{k}"] = qa.check(None, int(n), "features used to test straight connectors")

    log.info("fetching facilities ...")
    with track_overpass("facilities", used):
        fac, roles, excl = build_facilities(s, polygon)
    fac.to_file(s.gpkg, layer="facilities", driver="GPKG")
    roles.to_file(s.gpkg, layer="facility_roles", driver="GPKG")
    out = fac.drop(columns="geometry").assign(
        lon=fac.to_crs(4326).geometry.x.round(7), lat=fac.to_crs(4326).geometry.y.round(7)
    )
    out.to_csv(s.processed_dir / "facilities.csv", index=False)
    excl.to_csv(s.processed_dir / "facility_exclusions.csv", index=False)

    inside = roles[roles["inside_city"]]
    for cat in s["category_priority"]:
        sub = roles[roles["category"] == cat]
        tiers = sorted(sub["tier"].unique())
        checks[f"facilities_{cat}"] = qa.check(
            None,
            f"{int((inside['category'] == cat).sum())} in city / {len(sub)} incl. buffer",
            "count of mapped features only; says nothing about completeness. tiers: " + ", ".join(tiers),
        )
        for st, g in sub.groupby("subtype"):
            checks[f"facilities_{cat}.{st}"] = qa.check(
                None,
                f"{int(g['inside_city'].sum())} in city / {len(g)}",
                f"tier={g['tier'].iloc[0]}; status={', '.join(sorted(g['status'].unique()))}",
            )
    for tier in TIERS:
        checks[f"facility_roles_{tier}"] = qa.check(None, int((roles["tier"] == tier).sum()))
    checks["facility_roles_ambiguous_or_name_based"] = qa.check(
        None,
        int(
            roles["status"]
            .isin(["ambiguous", "reclassified_by_name", "osm_name_only", "level_not_tagged"])
            .sum()
        ),
        "see class_status / class_reason in facilities.csv",
    )
    checks["facility_points_merged_into_polygons"] = qa.check(
        None, int(excl["reason"].str.startswith("point inside").sum()), "listed in facility_exclusions.csv"
    )
    checks["facility_possible_duplicates"] = qa.check(
        None,
        int(excl["reason"].str.startswith("possible duplicate").sum()),
        "kept, never merged automatically; review file: abot review",
    )
    checks["facility_unmatched_features"] = qa.check(
        None, int(excl["reason"].str.startswith("returned by").sum()), "listed in facility_exclusions.csv"
    )
    qa.write(s, "osm", checks)
    qa.record_stage(s, "osm")

    records = provenance_records(s, used)
    write_provenance(
        s,
        records,
        {
            "network_types": s["osm"]["network_types"],
            "barrier_tags": s["osm"]["barriers"],
            "facility_tags": _query_tags(s["facilities"]),
        },
    )
    stamps = sorted({r["overpass_timestamp_osm_base"] for r in records if r["overpass_timestamp_osm_base"]})
    qa.write(
        s,
        "provenance",
        {
            "osm_snapshot_timestamps": qa.check(
                bool(stamps), ", ".join(stamps) or "unknown", "Overpass timestamp_osm_base"
            ),
            "osm_responses": qa.check(
                None, len(records), "cached responses used; SHA-256 in osm_provenance.json"
            ),
            "osm_boundary_buffer_m": qa.check(None, s["osm"]["boundary_buffer_m"]),
            "osmnx_version": qa.check(None, version("osmnx")),
        },
    )
