"""WorldPop 100 m population cells, barangay totals, and the 2020 census cross-check.

A cell belongs to a barangay when its centre falls inside it (rasterio's default
masking rule), so cells straddling the city limit are not double-counted with
neighbouring municipalities. The QA record reports how much population that excludes.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask

from abot import boundaries, qa
from abot.config import Settings
from abot.fetch.sources import worldpop_path

log = logging.getLogger(__name__)


def old_psgc_to_cod(code: str) -> str:
    """Old 9-digit PSGC p-code -> COD-AB p-code: PH063022001 -> PH0603022001.

    COD-AB pads the 2-digit province to 3 digits; the 2023 10-digit PSGC
    (BgyCode_new, e.g. PH0631000001) uses a different scheme and cannot be mapped this way.
    """
    return f"{code[:4]}0{code[4:]}"


def _masked_sum(src, geom_4326, all_touched: bool) -> float:
    arr, _ = rasterio.mask.mask(src, [geom_4326], crop=True, all_touched=all_touched, filled=False)
    return float(arr.sum())


def raster_cells(s: Settings, year: int, city: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    geom = city.to_crs(4326).union_all()
    with rasterio.open(worldpop_path(s, year)) as src:
        # mask() reads only the window around the city, never the national raster.
        arr, transform = rasterio.mask.mask(src, [geom], crop=True, filled=False)
        upper_bound = _masked_sum(src, geom, all_touched=True)
    band = arr[0]
    rows, cols = np.nonzero(~np.ma.getmaskarray(band) & (band.filled(0) > 0))
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    cells = gpd.GeoDataFrame(
        {"pop": band[rows, cols].astype("float64")},
        geometry=gpd.points_from_xy(xs, ys),
        crs=4326,
    ).to_crs(s.projected_crs)
    stats = {
        "cells": len(cells),
        "sum_centre_rule": float(cells["pop"].sum()),
        "sum_all_touched": upper_bound,
    }
    return cells, stats


def assign_barangays(cells: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    b = brgy[["adm4_pcode", "geometry"]]
    joined = gpd.sjoin(cells, b, predicate="within", how="left").drop(columns="index_right")
    missing = joined["adm4_pcode"].isna()
    if missing.any():  # centre inside the city but on a barangay seam/sliver
        near = gpd.sjoin_nearest(joined.loc[missing, ["pop", "geometry"]], b, max_distance=100)
        joined.loc[near.index, "adm4_pcode"] = near["adm4_pcode"]
    return joined[~joined.index.duplicated()]


def census_2020(s: Settings) -> pd.DataFrame:
    """Barangay totals from the PSA 2020 census, keyed by COD-AB p-code (cached as CSV)."""
    cache = s.interim_dir / "census_2020_city.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"adm4_pcode": str})
    src = next((s.raw_dir / "census_2020").glob("*.xlsx"))
    df = pd.read_excel(src, usecols="A:G", engine="openpyxl")
    df["adm4_pcode"] = df["BgyCode_old"].astype(str).map(old_psgc_to_cod, na_action="ignore")
    city = df[df["adm4_pcode"].str.startswith(s["city"]["adm3_pcode"], na=False)]
    city = city.rename(columns={"Bgy": "census_name", "Total_MF": "census_2020", "BgyCode_new": "psgc_2023"})
    city = city[["adm4_pcode", "psgc_2023", "census_name", "census_2020"]]
    city.to_csv(cache, index=False)
    return city


def cells_layer(year: int) -> str:
    return f"pop_cells_{year}"


def load_cells(s: Settings, year: int) -> gpd.GeoDataFrame:
    return gpd.read_file(s.gpkg, layer=cells_layer(year))


def load_barangay_population(s: Settings) -> pd.DataFrame:
    return pd.read_csv(s.processed_dir / "barangay_population.csv", dtype={"adm4_pcode": str})


def build(s: Settings) -> None:
    city, brgy = boundaries.load(s)
    table = brgy[["adm4_pcode", "adm4_name"]].copy()
    checks = {}

    for year in s["sources"]["worldpop"]["years"]:
        cells, stats = raster_cells(s, year, city)
        cells = assign_barangays(cells, brgy)
        cells.to_file(s.gpkg, layer=cells_layer(year), driver="GPKG")
        table = table.merge(
            cells.groupby("adm4_pcode")["pop"].sum().rename(f"wp_{year}").reset_index(),
            on="adm4_pcode",
            how="left",
        )
        edge_pct = 100 * (stats["sum_all_touched"] - stats["sum_centre_rule"]) / stats["sum_all_touched"]
        checks[f"wp{year}_total"] = qa.check(
            None, round(stats["sum_centre_rule"]), f"{stats['cells']} populated cells"
        )
        checks[f"wp{year}_edge_excluded_pct"] = qa.check(
            edge_pct < 5, round(edge_pct, 2), "population in boundary-straddling cells not counted"
        )
        checks[f"wp{year}_unassigned_cells"] = qa.check(
            int(cells["adm4_pcode"].isna().sum()) == 0, int(cells["adm4_pcode"].isna().sum())
        )
        empty = table[f"wp_{year}"].isna() | (table[f"wp_{year}"] == 0)
        checks[f"wp{year}_barangays_without_population"] = qa.check(
            None, int(empty.sum()), "tiny barangays can fall between 100 m cell centres"
        )

    census = census_2020(s)
    table = table.merge(census, on="adm4_pcode", how="left")
    checks["census_matched_barangays"] = qa.check(
        table["census_2020"].notna().all(),
        int(table["census_2020"].notna().sum()),
        "joined via old PSGC code",
    )
    checks["census_2020_total"] = qa.check(None, int(table["census_2020"].sum()))

    if 2020 in s["sources"]["worldpop"]["years"]:
        t = table.dropna(subset=["census_2020"]).fillna({"wp_2020": 0})
        city_err = 100 * (t["wp_2020"].sum() - t["census_2020"].sum()) / t["census_2020"].sum()
        r = float(np.corrcoef(t["wp_2020"], t["census_2020"])[0, 1])
        ape = (t["wp_2020"] - t["census_2020"]).abs() / t["census_2020"].clip(lower=1)
        table["wp2020_vs_census_pct"] = (
            100 * (table["wp_2020"].fillna(0) - table["census_2020"]) / table["census_2020"]
        ).round(1)
        checks["wp2020_vs_census_city_pct"] = qa.check(abs(city_err) < 10, round(city_err, 2))
        checks["wp2020_vs_census_barangay_r"] = qa.check(r > 0.7, round(r, 3), "Pearson r across barangays")
        checks["wp2020_vs_census_barangay_median_ape_pct"] = qa.check(
            None, round(100 * float(ape.median()), 1), "median absolute % error per barangay"
        )

    table.to_csv(s.processed_dir / "barangay_population.csv", index=False)
    qa.write(s, "population", checks)
