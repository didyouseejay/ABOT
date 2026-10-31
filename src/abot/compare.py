"""Compare two runs (e.g. Milestone 01 vs current, or 1 km vs 3 km OSM buffer).

A run is a processed-output directory holding `abot_iloilo.gpkg` (layer `access_cells`, or
`access_cells_<year>` in Milestone 01/02 outputs) and `barangay_access.csv`. Travel-time columns `t_<mode>_<group>` present in both runs are
compared cell by cell and barangay by barangay; every group's city-wide summary is reported for
each run so that renamed or redefined groups can be read side by side.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from scipy.stats import spearmanr

from abot.config import Settings

log = logging.getLogger(__name__)

THRESHOLDS = {"walk": [5, 10, 15, 30, 60], "drive": [5, 10, 15, 30, 60]}
TIME_COL = re.compile(r"^t_(walk|drive)_(.+)$")


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Smallest value whose cumulative weight share reaches q (inverted cumulative weight)."""
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cum, q, side="left")])


def access_layer(gpkg: Path) -> str:
    """`access_cells` (Milestone 02B on) or the older `access_cells_<year>`."""
    names = [n for n, _ in pyogrio.list_layers(gpkg)]
    if "access_cells" in names:
        return "access_cells"
    old = sorted(n for n in names if n.startswith("access_cells_"))
    if not old:
        raise LookupError(f"no access_cells layer in {gpkg}")
    return old[-1]


def load_run(run_dir: Path) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    gpkg = run_dir / "abot_iloilo.gpkg"
    cells = gpd.read_file(gpkg, layer=access_layer(gpkg))
    ind = pd.read_csv(run_dir / "barangay_access.csv", dtype={"adm4_pcode": str})
    return cells, ind


def citywide(cells: pd.DataFrame) -> pd.DataFrame:
    """Population-weighted summary per travel-time column.

    Means and percentiles use cells with a time; shares `pct_le<N>` use ALL residents, so residents
    without a connection count neither as within nor as beyond (reported in pct_not_connected).
    """
    connected = (
        cells["conn_status"].eq("connected") if "conn_status" in cells else pd.Series(True, index=cells.index)
    )
    total = float(cells["pop"].sum())
    rows = []
    for col in cells.columns:
        m = TIME_COL.match(col)
        if not m:
            continue
        mode, group = m.groups()
        ok = connected & cells[col].notna()
        t, w = cells.loc[ok, col].to_numpy(), cells.loc[ok, "pop"].to_numpy()
        if len(t) == 0:
            continue
        row = {
            "mode": mode,
            "group": group,
            "pop_used_pct": round(100 * w.sum() / total, 2),
            "pct_not_connected": round(100 * float(cells.loc[~connected, "pop"].sum()) / total, 2),
            "mean_min": round(float(np.average(t, weights=w)), 2),
            "p50_min": round(weighted_quantile(t, w, 0.5), 2),
            "p90_min": round(weighted_quantile(t, w, 0.9), 2),
        }
        for th in THRESHOLDS[mode]:
            row[f"pct_le{th}"] = round(100 * float(w[t <= th].sum()) / total, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def barangay_changes(a: pd.DataFrame, b: pd.DataFrame, shared: list[tuple[str, str]]) -> pd.DataFrame:
    m = a.merge(b, on="adm4_pcode", suffixes=("_a", "_b"))
    rows = []
    for mode, group in shared:
        col = f"{mode}_{group}_mean_min"
        if f"{col}_a" not in m or f"{col}_b" not in m:
            continue
        x, y = m[f"{col}_a"], m[f"{col}_b"]
        ok = x.notna() & y.notna()
        d = (y - x)[ok]
        worst_a = set(m.loc[ok].nlargest(20, f"{col}_a")["adm4_pcode"])
        worst_b = set(m.loc[ok].nlargest(20, f"{col}_b")["adm4_pcode"])
        rows.append(
            {
                "mode": mode,
                "group": group,
                "barangays": int(ok.sum()),
                "spearman_rho_mean": round(float(spearmanr(x[ok], y[ok])[0]), 4) if ok.sum() > 2 else np.nan,
                "median_abs_change_min": round(float(d.abs().median()), 2),
                "max_abs_change_min": round(float(d.abs().max()), 2),
                "barangays_abs_change_gt1min": int((d.abs() > 1).sum()),
                "worst20_overlap": len(worst_a & worst_b),
            }
        )
    return pd.DataFrame(rows)


def cell_changes(ca: pd.DataFrame, cb: pd.DataFrame, shared: list[tuple[str, str]]) -> pd.DataFrame:
    if len(ca) != len(cb) or not np.allclose(ca["pop"].to_numpy(), cb["pop"].to_numpy()):
        log.warning("cell layers differ; skipping cell-level comparison")
        return pd.DataFrame()
    w = ca["pop"].to_numpy()
    rows = []
    for mode, group in shared:
        col = f"t_{mode}_{group}"
        d = cb[col].to_numpy() - ca[col].to_numpy()
        ok = ~np.isnan(d)
        rows.append(
            {
                "mode": mode,
                "group": group,
                "pop_faster_gt0.1min": round(float(w[ok & (d < -0.1)].sum())),
                "pop_slower_gt0.1min": round(float(w[ok & (d > 0.1)].sum())),
                "max_decrease_min": round(float(-d[ok].min()), 2) if ok.any() else np.nan,
                "max_increase_min": round(float(d[ok].max()), 2) if ok.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(none)_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)
    ]
    return "\n".join(lines)


def run(s: Settings, base: Path, variant: Path, name: str | None = None) -> Path:
    ca, ia = load_run(base)
    cb, ib = load_run(variant)
    name = name or f"{base.name}_vs_{variant.name}"
    out = s.data_dir / "processed" / "comparisons" / name
    out.mkdir(parents=True, exist_ok=True)

    sa, sb = citywide(ca), citywide(cb)
    shared = sorted(
        set(zip(sa["mode"], sa["group"], strict=True)) & set(zip(sb["mode"], sb["group"], strict=True))
    )
    side = sa.merge(sb, on=["mode", "group"], how="outer", suffixes=("_base", "_variant"))
    bc = barangay_changes(ia, ib, shared)
    cc = cell_changes(ca, cb, shared)
    side.to_csv(out / "citywide.csv", index=False)
    bc.to_csv(out / "barangay_changes.csv", index=False)
    cc.to_csv(out / "cell_changes.csv", index=False)

    keep = ["mode", "group", "pop_used_pct", "mean_min", "p50_min", "p90_min", "pct_le15", "pct_le30"]
    keep = [c for c in keep if c in sa and c in sb]
    text = [
        f"# Comparison: `{base}` (base) vs `{variant}` (variant)",
        "",
        (
            "Means and p50/p90 (population-weighted) cover residents with a valid connection; "
            "shares within N minutes use all residents as the denominator (not-connected residents are "
            "reported separately). Drive = modelled uncongested car travel time (lower bound)."
        ),
        "",
        "## City-wide summary, base",
        "",
        _md(sa[keep]),
        "",
        "## City-wide summary, variant",
        "",
        _md(sb[keep]),
        "",
        "## Groups present in both runs: barangay-level change (mean travel time)",
        "",
        _md(bc),
        "",
        "## Groups present in both runs: cell-level change",
        "",
        _md(cc),
        "",
    ]
    (out / "comparison.md").write_text("\n".join(text), encoding="utf-8")
    log.info("wrote %s", out / "comparison.md")
    return out
