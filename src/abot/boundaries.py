"""Extract Iloilo City and its barangays from the national COD-AB GeoDatabase.

Only rows matching the city's adm3 p-code are read, so the national file is never
loaded into memory.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import pyogrio

from abot import qa
from abot.config import Settings

log = logging.getLogger(__name__)


def cod_ab_path(s: Settings):
    return s.raw_dir / "cod_ab" / s["sources"]["cod_ab"]["resource_name"]


def _layer(path, level: int) -> str:
    """Find the polygon layer for an admin level (names differ between COD-AB releases)."""
    layers = [name for name, _geom in pyogrio.list_layers(path)]
    matches = [n for n in layers if n.lower().endswith(f"admin{level}") or n.lower().endswith(f"adm{level}")]
    if not matches:
        raise LookupError(f"no admin{level} layer in {path.name}; layers: {layers}")
    return matches[0]


def read_admin(s: Settings, level: int) -> gpd.GeoDataFrame:
    path = cod_ab_path(s)
    pcode = s["city"]["adm3_pcode"]
    gdf = pyogrio.read_dataframe(path, layer=_layer(path, level), where=f"adm3_pcode = '{pcode}'")
    gdf = gdf.to_crs(s.projected_crs)
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def load(s: Settings) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Read the processed city and barangay layers."""
    city = gpd.read_file(s.gpkg, layer="city")
    brgy = gpd.read_file(s.gpkg, layer="barangays")
    return city, brgy


def build(s: Settings) -> None:
    city = read_admin(s, 3)
    brgy = read_admin(s, 4)
    keep = [
        "adm4_pcode",
        "adm4_name",
        "adm3_pcode",
        "adm3_name",
        "area_sqkm",
        "valid_on",
        "version",
        "geometry",
    ]
    brgy = brgy[[c for c in keep if c in brgy.columns]].sort_values("adm4_pcode").reset_index(drop=True)
    brgy["area_km2"] = brgy.area / 1e6

    city_area = float(city.area.sum() / 1e6)
    union_area = float(brgy.union_all().area / 1e6)
    overlap_km2 = float(brgy.area.sum() / 1e6 - union_area)
    expected = s["city"]["expected_barangays"]
    checks = {
        "city_found": qa.check(len(city) == 1, len(city)),
        "barangay_count": qa.check(len(brgy) == expected, len(brgy), f"expected {expected}"),
        "pcodes_unique": qa.check(brgy["adm4_pcode"].is_unique, int(brgy["adm4_pcode"].nunique())),
        "geometries_valid": qa.check(bool(brgy.is_valid.all()), int((~brgy.is_valid).sum()), "invalid count"),
        "city_area_km2": qa.check(
            None,
            round(city_area, 2),
            "official figure is ~78 km2 (unverified); coastline differences expected",
        ),
        "barangay_union_vs_city_pct": qa.check(
            abs(union_area - city_area) / city_area < 0.01,
            round(100 * (union_area - city_area) / city_area, 3),
            "barangays should tile the city",
        ),
        "barangay_overlap_km2": qa.check(overlap_km2 < 0.01, round(overlap_km2, 4)),
        "smallest_barangay_km2": qa.check(None, round(float(brgy.area_km2.min()), 4)),
        "largest_barangay_km2": qa.check(None, round(float(brgy.area_km2.max()), 2)),
    }
    qa.write(s, "boundaries", checks)

    city.to_file(s.gpkg, layer="city", driver="GPKG")
    brgy.to_file(s.gpkg, layer="barangays", driver="GPKG")
    log.info("wrote city + %d barangays to %s", len(brgy), s.gpkg.name)
