"""QA report (Markdown) and a quick-look interactive map (folium HTML)."""

from __future__ import annotations

import json
import logging
from datetime import date

import branca.colormap as cm
import folium
import geopandas as gpd

from abot import qa
from abot.config import Settings
from abot.fetch.common import load_manifest

log = logging.getLogger(__name__)

ATTRIBUTION = (
    "Boundaries: OCHA COD-AB (NAMRIA/PSA), CC BY-IGO · Population: WorldPop R2025A, CC BY 4.0 · "
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


def write_markdown(s: Settings) -> None:
    lines = [
        f"# ABOT Milestone 01 — QA report ({date.today().isoformat()})",
        "",
        (
            f"City: {s['city']['name']} (`{s['city']['adm3_pcode']}`) · analysis year "
            f"{s['sources']['worldpop']['analysis_year']} · CRS {s.projected_crs}"
        ),
        "",
    ]
    for stage, checks in qa.read_all(s).items():
        lines += [f"## {stage}", "", "| check | status | value | note |", "|---|---|---|---|"]
        lines += [
            f"| {k} | {_status(c['ok'])} | {c['value']} | {c.get('note', '')} |" for k, c in checks.items()
        ]
        lines.append("")
    lines += [
        "## Data provenance",
        "",
        "```json",
        json.dumps(load_manifest(s.raw_dir), indent=2),
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
            f'padding:2px 6px;font:11px sans-serif;max-width:70%">ABOT M01 · {ATTRIBUTION}</div>'
        )
    )

    year = s["sources"]["worldpop"]["analysis_year"]
    layers = [
        (
            "walk_health_mean_min",
            "Walk to health (min)",
            "Mean walk to nearest health facility, min",
            True,
            False,
        ),
        (
            "drive_health_mean_min",
            "Drive to health (min)",
            "Mean drive to nearest health facility, min",
            False,
            False,
        ),
        ("walk_market_mean_min", "Walk to market (min)", "Mean walk to nearest market, min", False, False),
        ("walk_education_mean_min", "Walk to school (min)", "Mean walk to nearest school, min", False, False),
        (f"wp_{year}", f"Population {year}", f"WorldPop {year} population", False, True),
        ("wp2020_vs_census_pct", "WorldPop vs census 2020 (%)", "WorldPop 2020 − census, %", False, False),
    ]
    for column, name, caption, show, reverse in layers:
        if column in ind:
            layer, cmap = _choropleth(ind, column, name, caption, show, reverse)
            layer.add_to(m)
            if show:
                cmap.add_to(m)

    for cat, colour in CATEGORY_COLOURS.items():
        group = folium.FeatureGroup(name=f"Facilities: {cat}", show=cat == "health")
        for _, f in fac[fac["category"] == cat].iterrows():
            folium.CircleMarker(
                [f.geometry.y, f.geometry.x],
                radius=4,
                color=colour,
                fill=True,
                fill_opacity=0.9,
                weight=1,
                tooltip=f"{cat}: {f['name'] if isinstance(f['name'], str) else '(unnamed)'}",
            ).add_to(group)
        group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    out = s.processed_dir / "abot_map.html"
    m.save(out)
    log.info("wrote %s", out)


def build(s: Settings) -> None:
    write_markdown(s)
    write_map(s)
