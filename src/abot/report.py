"""QA report (Markdown) and a quick-look interactive map (folium HTML)."""

from __future__ import annotations

import json
import logging
from datetime import date

import branca.colormap as cm
import folium
import geopandas as gpd
import pandas as pd

from abot import qa
from abot.config import Settings
from abot.fetch.common import load_manifest

log = logging.getLogger(__name__)

ATTRIBUTION = (
    "Boundaries: OCHA COD-AB (NAMRIA/PSA), CC BY-IGO · Population: WorldPop R2025A (alpha), CC BY 4.0 · "
    "Census: PSA 2020 via HDX, CC BY · Roads & facilities: © OpenStreetMap contributors, ODbL"
)
CATEGORY_COLOURS = {
    "health": "#d62728",
    "pharmacy": "#ff7f0e",
    "education": "#1f77b4",
    "safety": "#17becf",
    "government": "#7f7f7f",
    "market": "#2ca02c",
    "finance": "#bcbd22",
    "transport": "#9467bd",
    "evacuation": "#8c564b",
}


def _status(ok) -> str:
    return {True: "PASS", False: "WARN", None: "info"}[ok]


READ_ME = (
    "**How to read these results.** Every indicator is *access to the nearest mapped facility* of a "
    "defined sub-type, that is, **geographic proximity** in modelled time on the mapped OpenStreetMap "
    "network. It is not service level (facility level and public/private status are not verified) and "
    "not capacity (beds, staff and enrolment are not measured). A short time does not mean adequate "
    "service, and the counts `n_*` are counts of mapped features. Walk = 4.5 km/h on mapped paths. "
    "Drive = **modelled uncongested (free-flow) car travel time** on the mapped OSM road network, "
    "including the walk to and from the road; it excludes congestion, signals, turning, parking and car "
    "availability, describes households with a car, and its threshold shares are lower bounds (see the "
    "network-speed sensitivity). Population weights: PSA 2020 census barangay totals spread within each "
    "barangay by the WorldPop R2025A 2020 pattern (*census-adjusted*). Original WorldPop estimates are "
    "kept beside them; agreement with the census is not validation, because the census is a WorldPop "
    "input. Shares within N minutes are of **all** residents; residents with no valid network "
    "connection are reported separately. Reliability is given per dimension (population, network, "
    "facility inventory), not as one score. Only `indicative` sub-types get travel-time indicators. "
    "Status: PASS / WARN = a stated condition was tested and held / failed; info = reported without a "
    "threshold."
)


def _md_table(df: pd.DataFrame) -> list[str]:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)
    ]
    return out


def reliability_section(s: Settings) -> list[str]:
    path = s.processed_dir / "barangay_access.csv"
    if not path.exists():
        return []
    ind = pd.read_csv(path)
    if "rel_overall" not in ind:
        return []
    dims = ["rel_population", "rel_network", "rel_facility_inventory", "rel_overall"]
    counts = pd.DataFrame({d: ind[d].value_counts() for d in dims})
    counts = counts.reindex(["ok", "caution", "low", "unverified"]).fillna(0).astype(int)
    lines = [
        "## Barangay reliability (per dimension; not a combined score)",
        "",
        *_md_table(counts.reset_index(names="level")),
        "",
        (
            "Barangays eligible for rankings of population-based quantities: "
            f"{int(ind['pop_ranking_eligible'].sum())} of {len(ind)}."
        ),
        "",
    ]
    low = ind[ind["rel_overall"] == "low"].sort_values("pct_not_connected", ascending=False)
    if not low.empty:
        lines += ["Barangays with `rel_overall = low`:", ""]
        lines += _md_table(low[["adm4_name", "rel_population", "rel_network", "rel_overall_reasons"]])
        lines.append("")
    return lines


def sensitivity_section(s: Settings) -> list[str]:
    path = s.processed_dir / "drive_speed_sensitivity.csv"
    if not path.exists():
        return []
    lines = [
        "## Modelled uncongested car travel time: network-speed sensitivity",
        "",
        (
            "The drive-network leg is multiplied by each factor; the walk to and from the road is unchanged. "
            "The factors are illustrative, not calibrated congestion levels. Shares are of all residents."
        ),
        "",
    ]
    return lines + _md_table(pd.read_csv(path)) + [""]


def write_markdown(s: Settings) -> None:
    lines = [
        f"# ABOT — QA report ({date.today().isoformat()})",
        "",
        (
            f"City: {s['city']['name']} (`{s['city']['adm3_pcode']}`) · run `{s.run_name or 'baseline'}` · "
            f"population weight `{(s.get('population') or {}).get('primary_weight')}` · OSM buffer "
            f"{s['osm']['boundary_buffer_m']} m · CRS {s.projected_crs}"
        ),
        "",
        READ_ME,
        "",
        *reliability_section(s),
        *sensitivity_section(s),
    ]
    for stage, checks in qa.read_all(s).items():
        lines += [f"## {stage}", "", "| check | status | value | note |", "|---|---|---|---|"]
        lines += [
            f"| {k} | {_status(c['ok'])} | {c['value']} | {c.get('note', '')} |" for k, c in checks.items()
        ]
        lines.append("")
    prov = s.interim_dir / "osm_provenance.json"
    lines += [
        "## Data provenance",
        "",
        "Downloaded files and every cached Overpass response (`data/raw/manifest.json`):",
        "",
        "```json",
        json.dumps(load_manifest(s.raw_dir), indent=2),
        "```",
        "",
        "OpenStreetMap responses used by this run (`osm_provenance.json`):",
        "",
        "```json",
        prov.read_text(encoding="utf-8") if prov.exists() else "{}",
        "```",
        "",
        ATTRIBUTION,
        "",
    ]
    out = s.processed_dir / "qa_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote %s", out)


def _choropleth(ind: gpd.GeoDataFrame, column: str, name: str, caption: str, show: bool, reverse=False):
    vals = ind[column].dropna()
    colours = ["#1a9850", "#fee08b", "#d73027"]
    cmap = cm.LinearColormap(
        colours[::-1] if reverse else colours,
        vmin=float(vals.quantile(0.02)),
        vmax=float(vals.quantile(0.98)),
        caption=caption,
    )
    layer = folium.FeatureGroup(name=name, show=show)
    folium.GeoJson(
        ind[["adm4_name", column, "geometry"]],
        style_function=lambda f: {
            "fillColor": cmap(f["properties"][column]) if f["properties"][column] is not None else "#cccccc",
            "color": "#444",
            "weight": 0.5,
            "fillOpacity": 0.65,
        },
        tooltip=folium.GeoJsonTooltip(["adm4_name", column], aliases=["Barangay", caption]),
    ).add_to(layer)
    return layer, cmap


REL_COLOURS = {"ok": "#1a9850", "caution": "#fee08b", "low": "#d73027", "unverified": "#bdbdbd"}


def _categorical(ind: gpd.GeoDataFrame, column: str, name: str, reasons: str):
    layer = folium.FeatureGroup(name=name, show=False)
    folium.GeoJson(
        ind[["adm4_name", column, reasons, "geometry"]],
        style_function=lambda f: {
            "fillColor": REL_COLOURS.get(f["properties"][column], "#cccccc"),
            "color": "#444",
            "weight": 0.5,
            "fillOpacity": 0.6,
        },
        tooltip=folium.GeoJsonTooltip(["adm4_name", column, reasons], aliases=["Barangay", name, "Why"]),
    ).add_to(layer)
    return layer


def write_map(s: Settings) -> None:
    ind = gpd.read_file(s.gpkg, layer="barangay_access")
    fac = gpd.read_file(s.gpkg, layer="facilities").to_crs(4326)
    ind["geometry"] = ind.geometry.simplify(5)  # metres; keeps the HTML small
    ind = ind.to_crs(4326)

    centre = ind.union_all().centroid
    m = folium.Map(location=[centre.y, centre.x], zoom_start=13, tiles="OpenStreetMap")
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;bottom:4px;left:4px;z-index:9999;background:rgba(255,255,255,.85);'
            f'padding:2px 6px;font:11px sans-serif;max-width:70%">ABOT · {ATTRIBUTION}</div>'
        )
    )

    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;top:8px;left:50px;z-index:9999;background:rgba(255,255,255,.92);'
            f'padding:6px 8px;font:12px sans-serif;max-width:420px">{READ_ME.replace("**", "")}</div>'
        )
    )

    layers = [
        (
            "walk_health_primary_care_mean_min",
            "Walk to primary care (min)",
            "Mean walk to nearest mapped primary-care facility, min",
            True,
            False,
        ),
        (
            "walk_health_hospital_mean_min",
            "Walk to hospital (min)",
            "Mean walk to nearest mapped hospital, min",
            False,
            False,
        ),
        (
            "drive_health_hospital_mean_min",
            "Car to hospital (modelled uncongested, min)",
            "Mean modelled uncongested car travel time to nearest mapped hospital (lower bound), min",
            False,
            False,
        ),
        (
            "walk_market_public_mean_min",
            "Walk to public market (min)",
            "Mean walk to nearest mapped public market, min",
            False,
            False,
        ),
        (
            "walk_education_basic_mean_min",
            "Walk to school (min)",
            "Mean walk to nearest mapped school, min",
            False,
            False,
        ),
        (
            "pct_not_connected",
            "Residents not connected (%)",
            "% of residents with no valid walk-network connection",
            False,
            False,
        ),
        (
            "pop_census2020_adj",
            "Population (census-adjusted 2020)",
            "PSA 2020 census total, WorldPop 2020 pattern (adjusted)",
            False,
            True,
        ),
        (
            "pop_wp2026",
            "Population 2026 (original WorldPop)",
            "WorldPop 2026 projection (unadjusted)",
            False,
            True,
        ),
        (
            "wp2020_vs_census_pct",
            "WorldPop 2020 vs census (%)",
            "WorldPop 2020 − census, % (unit alignment, not validation)",
            False,
            False,
        ),
    ]
    for column, name, caption, show, reverse in layers:
        if column in ind and ind[column].notna().any():
            layer, cmap = _choropleth(ind, column, name, caption, show, reverse)
            layer.add_to(m)
            if show:
                cmap.add_to(m)
    for dim, label in [
        ("rel_overall", "Reliability: overall"),
        ("rel_population", "Reliability: population"),
        ("rel_network", "Reliability: network connection"),
    ]:
        if dim in ind:
            _categorical(ind, dim, label, f"{dim}_reasons").add_to(m)

    for cat, colour in CATEGORY_COLOURS.items():
        group = folium.FeatureGroup(name=f"Facilities: {cat}", show=cat == "health")
        for _, f in fac[fac["category"] == cat].iterrows():
            name = f["name"] if isinstance(f["name"], str) else "(unnamed)"
            excluded = f.get("tier") == "excluded"
            folium.CircleMarker(
                [f.geometry.y, f.geometry.x],
                radius=4,
                color="#000000" if excluded else colour,
                fill=True,
                fill_color=colour,
                fill_opacity=0.3 if f.get("tier") != "indicative" else 0.9,
                weight=2 if excluded else 1,
                tooltip=(
                    f"{cat}.{f.get('subtype')} [{f.get('tier')}]: {name} "
                    f"({f['osm_type']}/{f['osm_id']}; {f.get('class_status')})"
                ),
            ).add_to(group)
        group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    out = s.processed_dir / "abot_map.html"
    m.save(out)
    log.info("wrote %s", out)


def build(s: Settings) -> None:
    write_markdown(s)
    write_map(s)
    qa.record_stage(s, "report")
