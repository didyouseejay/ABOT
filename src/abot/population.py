"""WorldPop 100 m population cells, fractional barangay allocation, and census-anchored weights.

Cells. Every WorldPop cell that touches the city is read (all configured years on the same grid).
Each cell polygon is split between the barangays it overlaps, in proportion to area ("pieces");
the part outside the city is not counted, so neighbouring municipalities are never double-counted.

Weights (validity assessment P1). Three weight sets are kept side by side, always named apart:
  pop_wp2020, pop_wp2026   ORIGINAL WorldPop R2025A modelled estimates (2026 is a projection)
  pop_census2020_adj       ADJUSTED: within each barangay, WorldPop 2020's cell pattern rescaled so
                           the barangay sums to its PSA 2020 census count
`pop` is a copy of the configured primary weight. For the Philippines WorldPop R2025A was itself
built from the 2020 barangay census, so agreement between WorldPop and the census is partly true by
construction and is never reported as independent validation.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import shapely

from abot import boundaries, qa
from abot.config import Settings
from abot.fetch.sources import worldpop_path

log = logging.getLogger(__name__)

# primary_weight option -> column holding it
WEIGHT_COLUMNS = {
    "census_2020_anchored": "pop_census2020_adj",
    "worldpop_2020": "pop_wp2020",
    "worldpop_2026": "pop_wp2026",
}
CELLS_LAYER, PIECES_LAYER = "pop_cells", "pop_pieces"


def old_psgc_to_cod(code: str) -> str:
    """Old 9-digit PSGC p-code -> COD-AB p-code: PH063022001 -> PH0603022001.

    COD-AB pads the 2-digit province to 3 digits; the 2023 10-digit PSGC
    (BgyCode_new, e.g. PH0631000001) uses a different scheme and cannot be mapped this way.
    """
    return f"{code[:4]}0{code[4:]}"


def primary_weight(s: Settings) -> tuple[str, str]:
    """(option name, column) of the configured primary population weight."""
    name = (s.get("population") or {}).get("primary_weight", "census_2020_anchored")
    if name not in WEIGHT_COLUMNS:
        raise ValueError(f"population.primary_weight must be one of {sorted(WEIGHT_COLUMNS)}, not {name!r}")
    return name, WEIGHT_COLUMNS[name]


def raster_cells(s: Settings, city: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Every cell touching the city with a value > 0 in any year: polygon + centre + original values."""
    geom = city.to_crs(4326).union_all()
    years = s["sources"]["worldpop"]["years"]
    values, grid = {}, None
    for year in years:
        with rasterio.open(worldpop_path(s, year)) as src:
            # mask() reads only the window around the city, never the national raster.
            arr, transform = rasterio.mask.mask(src, [geom], crop=True, all_touched=True, filled=False)
            row0, col0 = src.index(transform.c + transform.a / 2, transform.f + transform.e / 2)
        if grid is None:
            grid = (transform, arr.shape, row0, col0)
        elif (transform, arr.shape) != grid[:2]:
            raise ValueError(f"WorldPop {year} is not on the same grid as {years[0]}")
        values[year] = arr[0]
    if grid is None:
        raise ValueError("no WorldPop years configured (sources.worldpop.years is empty)")
    transform, _, row0, col0 = grid
    populated = np.zeros(values[years[0]].shape, dtype=bool)
    for band in values.values():
        populated |= ~np.ma.getmaskarray(band) & (band.filled(0) > 0)
    rows, cols = np.nonzero(populated)  # pyright: ignore[reportAssignmentType]  (numpy infers 1-D)
    x0, y0 = rasterio.transform.xy(transform, rows, cols, offset="ul")
    x1, y1 = rasterio.transform.xy(transform, rows, cols, offset="lr")
    cx, cy = rasterio.transform.xy(transform, rows, cols, offset="center")
    data: dict[str, object] = {
        "cell_id": [f"r{r + row0}c{c + col0}" for r, c in zip(rows, cols, strict=True)]
    }
    for year in years:
        data[f"wp{year}_cell"] = np.asarray(values[year].filled(0)[rows, cols], dtype="float64")
    cells = gpd.GeoDataFrame(data, geometry=shapely.box(x0, y1, x1, y0), crs=4326).to_crs(s.projected_crs)
    cells["centre"] = gpd.GeoSeries(gpd.points_from_xy(cx, cy), crs=4326).to_crs(s.projected_crs).values
    return cells


def fractional_pieces(cells: gpd.GeoDataFrame, brgy: gpd.GeoDataFrame, years: list[int]) -> pd.DataFrame:
    """Split each cell polygon between barangays by area: one row per (cell, barangay)."""
    polys = cells[["cell_id", "geometry"]].assign(cell_area=cells.area)
    pieces = gpd.overlay(polys, brgy[["adm4_pcode", "geometry"]], how="intersection", keep_geom_type=True)
    pieces["frac"] = pieces.area / pieces["cell_area"]
    pieces = pd.DataFrame(pieces.drop(columns=["geometry", "cell_area"]))
    pieces = pieces.groupby(["cell_id", "adm4_pcode"], as_index=False)["frac"].sum()
    original = cells.set_index("cell_id")
    for year in years:
        pieces[f"pop_wp{year}"] = pieces["frac"] * pieces["cell_id"].map(original[f"wp{year}_cell"])
    return pieces


def anchor_to_census(pieces: pd.DataFrame, census: pd.Series, pattern: str = "pop_wp2020"):
    """Rescale `pattern` within each barangay so it sums to the census count.

    Returns (pieces with pop_census2020_adj, per-barangay table). A barangay whose census population
    cannot be placed (no WorldPop 2020 population in it) is reported in `census_unallocated`; it is
    never spread to other barangays.
    """
    totals = pieces.groupby("adm4_pcode")[pattern].sum()
    table = pd.DataFrame({"census_2020": census}).join(totals.rename("pattern_total"), how="left")
    table["pattern_total"] = table["pattern_total"].fillna(0.0)
    allocatable = (table["pattern_total"] > 0) & table["census_2020"].notna()
    table["census_adj_factor"] = np.where(allocatable, table["census_2020"] / table["pattern_total"], np.nan)
    table["census_unallocated"] = np.where(allocatable, 0.0, table["census_2020"].fillna(0.0))
    factor = pieces["adm4_pcode"].map(table["census_adj_factor"]).fillna(0.0)
    pieces = pieces.assign(pop_census2020_adj=pieces[pattern] * factor)
    return pieces, table


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


def load_cells(s: Settings) -> gpd.GeoDataFrame:
    return gpd.read_file(s.gpkg, layer=CELLS_LAYER)


def load_pieces(s: Settings) -> pd.DataFrame:
    return pd.DataFrame(gpd.read_file(s.gpkg, layer=PIECES_LAYER, ignore_geometry=True))


def load_barangay_population(s: Settings) -> pd.DataFrame:
    return pd.read_csv(s.processed_dir / "barangay_population.csv", dtype={"adm4_pcode": str})


def build(s: Settings) -> None:
    city, brgy = boundaries.load(s)
    years = s["sources"]["worldpop"]["years"]
    if 2020 not in years:
        raise ValueError("sources.worldpop.years must include 2020 (the census-anchoring pattern)")
    weight_name, weight_col = primary_weight(s)

    cells = raster_cells(s, city)
    pieces = fractional_pieces(cells, brgy, years)
    census = census_2020(s)
    pieces, anchor = anchor_to_census(pieces, census.set_index("adm4_pcode")["census_2020"])
    pieces["pop"] = pieces[weight_col]

    # Cell layer: centre points; population columns are the in-city part of each cell.
    weight_cols = [*(f"pop_wp{y}" for y in years), "pop_census2020_adj", "pop"]
    in_city = pieces.groupby("cell_id")[[*weight_cols, "frac"]].sum()
    home = pieces.sort_values("frac", ascending=False).drop_duplicates("cell_id").set_index("cell_id")
    centre_brgy = (
        gpd.sjoin(
            gpd.GeoDataFrame(cells[["cell_id"]], geometry=cells["centre"], crs=cells.crs),
            brgy[["adm4_pcode", "geometry"]],
            predicate="within",
            how="left",
        )
        .drop_duplicates("cell_id")
        .set_index("cell_id")["adm4_pcode"]
    )
    out = cells[["cell_id", *(f"wp{y}_cell" for y in years)]].copy()
    out = out.join(in_city, on="cell_id").rename(columns={"frac": "frac_in_city"})
    out = out[out["frac_in_city"].notna()]  # touches the city polygon but no barangay (seam only)
    out["adm4_pcode"] = out["cell_id"].map(home["adm4_pcode"])  # barangay holding most of the cell
    out["centre_adm4_pcode"] = out["cell_id"].map(centre_brgy)
    out = gpd.GeoDataFrame(out, geometry=cells.loc[out.index, "centre"].values, crs=cells.crs)
    out.to_file(s.gpkg, layer=CELLS_LAYER, driver="GPKG")
    gpd.GeoDataFrame(pieces, geometry=[None] * len(pieces)).to_file(s.gpkg, layer=PIECES_LAYER, driver="GPKG")

    table = brgy[["adm4_pcode", "adm4_name"]].merge(census, on="adm4_pcode", how="left")
    sums = pieces.groupby("adm4_pcode")[weight_cols].sum()
    table = table.join(sums, on="adm4_pcode")
    table = table.join(anchor[["census_adj_factor", "census_unallocated"]], on="adm4_pcode")
    centre_counts = out.groupby("centre_adm4_pcode").size()
    table["pop_cells_centre"] = table["adm4_pcode"].map(centre_counts).fillna(0).astype(int)
    table["pop_cells_touching"] = table["adm4_pcode"].map(pieces.groupby("adm4_pcode").size()).astype(int)
    straddle = pieces.assign(straddling=pieces["frac"] < 0.999)
    sp = straddle[straddle["straddling"]].groupby("adm4_pcode")["pop"].sum()
    table["pct_pop_from_straddling_cells"] = (
        100 * table["adm4_pcode"].map(sp).fillna(0) / table["pop"].replace(0, np.nan)
    ).round(1)
    # Centre-rule WorldPop 2020 total (Milestone 01 rule), kept to show the allocation effect.
    centre_wp = out.groupby("centre_adm4_pcode")["wp2020_cell"].sum()
    table["pop_wp2020_centre_rule"] = table["adm4_pcode"].map(centre_wp).fillna(0.0)
    # Diagnostic of unit alignment, NOT validation: WorldPop 2020 was built from this census.
    table["wp2020_vs_census_pct"] = (
        100 * (table["pop_wp2020"] - table["census_2020"]) / table["census_2020"]
    ).round(1)
    table["primary_weight"] = weight_name
    for c in [*weight_cols, "pop_wp2020_centre_rule", "census_unallocated"]:
        table[c] = table[c].fillna(0.0).round(1)
    table["census_adj_factor"] = table["census_adj_factor"].round(4)
    table.to_csv(s.processed_dir / "barangay_population.csv", index=False)

    qa.write(s, "population", population_checks(s, cells, out, pieces, table, weight_name))
    qa.record_stage(s, "population")


def population_checks(s, cells, out, pieces, table, weight_name: str) -> dict:
    years = s["sources"]["worldpop"]["years"]
    checks = {
        "primary_weight": qa.check(
            None, weight_name, "weights used by every indicator; original WorldPop values kept beside them"
        ),
        "cells_touching_city": qa.check(None, len(out), "populated 100 m cells overlapping a barangay"),
    }
    for y in years:
        full = float(cells[f"wp{y}_cell"].sum())
        inside = float(pieces[f"pop_wp{y}"].sum())
        checks[f"wp{y}_total_in_city"] = qa.check(
            None,
            round(inside),
            f"original WorldPop {y} estimate, fractional allocation ({'projection' if y > 2020 else 'modelled'})",
        )
        checks[f"wp{y}_outside_city_part_pct"] = qa.check(
            None,
            round(100 * (full - inside) / full, 2),
            "part of touching cells outside the city: not counted",
        )
    census_total = float(table["census_2020"].sum())
    checks["census_matched_barangays"] = qa.check(
        bool(table["census_2020"].notna().all()),
        int(table["census_2020"].notna().sum()),
        "joined via old PSGC code",
    )
    checks["census_2020_total"] = qa.check(None, int(census_total), "PSA 2020 census (observed count)")
    adj = float(pieces["pop_census2020_adj"].sum())
    unalloc = float(table["census_unallocated"].sum())
    checks["census_adjusted_total"] = qa.check(
        abs(adj + unalloc - census_total) < 1, round(adj), "census-anchored weights sum to the census"
    )
    checks["census_unallocated_pop"] = qa.check(
        unalloc == 0, round(unalloc), "census residents in barangays with no WorldPop 2020 population"
    )
    t = table.dropna(subset=["census_2020"])
    city_err = 100 * (t["pop_wp2020"].sum() - t["census_2020"].sum()) / t["census_2020"].sum()
    ape = (t["pop_wp2020"] - t["census_2020"]).abs() / t["census_2020"].clip(lower=1)
    checks["wp2020_vs_census_city_pct"] = qa.check(
        None,
        round(city_err, 2),
        "NOT validation: WorldPop R2025A used the PSA 2020 barangay census as input and scales to UN WPP; "
        "agreement is by construction",
    )
    checks["wp2020_vs_census_barangay_median_ape_pct"] = qa.check(
        None,
        round(100 * float(ape.median()), 1),
        "measures mismatch between WorldPop input units and COD-AB barangays plus within-unit allocation; "
        "not an accuracy test",
    )
    checks["wp2020_vs_census_barangays_abs_err_gt50pct"] = qa.check(
        None,
        int((ape > 0.5).sum()),
        "these barangays' original WorldPop totals are not used as primary weights",
    )
    f = t["census_adj_factor"].dropna()
    checks["census_adj_factor_range"] = qa.check(
        None,
        f"min {f.min():.2f} / median {f.median():.2f} / max {f.max():.2f}",
        "census 2020 / WorldPop 2020 per barangay",
    )
    small = t["pop_cells_centre"] <= 5
    change = (t["pop_wp2020"] - t["pop_wp2020_centre_rule"]).abs() / t["pop_wp2020"].replace(0, np.nan)
    checks["small_barangays_allocation_change_pct"] = qa.check(
        None,
        round(100 * float(change[small].median()), 1) if small.any() else 0,
        f"{int(small.sum())} barangays with <= 5 cell centres: median |fractional - centre rule| / fractional",
    )
    cons = pieces.groupby("cell_id")["frac"].sum()
    checks["pieces_fraction_le_1"] = qa.check(bool((cons <= 1 + 1e-6).all()), round(float(cons.max()), 6))
    return checks
