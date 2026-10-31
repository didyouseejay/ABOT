"""Barangay reliability flags (validity assessment P2, P3) and the facility-inventory table.

Four dimensions are reported separately, each with a level (ok | caution | low), the measured values
behind it, and a plain-language reason:

  rel_population          barangay population totals and population-based quantities (counts,
                          persons beyond a threshold, densities). Rests on how many 100 m cells
                          the barangay has and on how well WorldPop matched its census count.
  rel_network             share of residents with no valid walk-network connection.
  rel_facility_inventory  completeness of the mapped facility inventory. No official registry is
                          integrated yet, so this is "unverified" everywhere; the measurable parts
                          (duplicates pending review, missing attributes, unconnected destinations)
                          are in facility_inventory.csv and the reason text.
  rel_overall             the most restrictive of rel_population and rel_network, with all reasons.
                          A categorical rule, not a score: read the dimensions, not just this.

`pop_ranking_eligible` is False when population or network reliability is low: such barangays keep
their travel-time indicators (which are stable, see the validity assessment section 4) but are left
out of rankings of population-based quantities.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from abot.config import Settings

LEVELS = ("ok", "caution", "low")
NOT_TAG_RULE = {"ambiguous", "attribute_missing", "reclassified_by_name", "osm_name_only", "level_not_tagged"}


def worst(*levels: str) -> str:
    return max(levels, key=LEVELS.index)


def population_level(row, cfg: dict, census_anchored: bool) -> tuple[str, list[str]]:
    level, reasons = "ok", []
    n = int(row["pop_cells_centre"])
    if row.get("census_unallocated", 0) > 0:
        level = "low"
        reasons.append(
            f"{row['census_unallocated']:.0f} census residents could not be placed (no WorldPop 2020 cells)"
        )
    if n <= cfg["low_max_centre_cells"]:
        level = "low"
        reasons.append(
            f"{n} cell centres (<= {cfg['low_max_centre_cells']}): totals depend on the allocation rule"
        )
    elif n <= cfg["caution_max_centre_cells"]:
        level = worst(level, "caution")
        reasons.append(f"{n} cell centres (<= {cfg['caution_max_centre_cells']})")
    f = row.get("census_adj_factor")
    lo, hi = cfg["caution_anchor_factor_outside"]
    if census_anchored and pd.notna(f) and not lo <= f <= hi:
        level = worst(level, "caution")
        reasons.append(
            f"census/WorldPop 2020 factor {f:.2f} (outside {lo}-{hi}): WorldPop's units do not match this "
            "barangay, so the within-barangay pattern is uncertain"
        )
    err = row.get("wp2020_vs_census_pct")
    if not census_anchored and pd.notna(err) and abs(err) > 50:
        level = "low"
        reasons.append(f"WorldPop total differs from the census by {err:+.0f}%")
    return level, reasons


def network_level(row, cfg: dict) -> tuple[str, list[str]]:
    pct = float(row.get("pct_not_connected") or 0.0)
    pop = float(row.get("pop_not_connected") or 0.0)
    if pct > cfg["low_pct_not_connected"]:
        return "low", [
            f"{pct:.1f}% of residents ({pop:.0f}) not connected (> {cfg['low_pct_not_connected']}%)"
        ]
    if pct > cfg["caution_pct_not_connected"]:
        return "caution", [f"{pct:.1f}% of residents ({pop:.0f}) not connected"]
    return "ok", []


def _pending_duplicate_keys(excl: pd.DataFrame) -> set[str]:
    dup = excl[excl["reason"].astype(str).str.startswith("possible duplicate")]
    keys = set(dup["osm_type"].astype(str) + "/" + dup["osm_id"].astype(str))
    if "related_osm_id" in dup:
        rel = dup.dropna(subset=["related_osm_id"])
        keys |= set(
            rel["related_osm_type"].astype(str) + "/" + rel["related_osm_id"].astype("int64").astype(str)
        )
    return keys


def add_flags(
    s: Settings, ind: gpd.GeoDataFrame, fac: gpd.GeoDataFrame, excl: pd.DataFrame
) -> gpd.GeoDataFrame:
    rel = s["reliability"]
    census_anchored = (s.get("population") or {}).get("primary_weight") == "census_2020_anchored"
    ind = ind.copy()

    dup_keys = _pending_duplicate_keys(excl)
    pending = fac[fac["fid_key"].isin(dup_keys) & fac["inside_city"]]
    j = gpd.sjoin(pending[["fid_key", "geometry"]], ind[["adm4_pcode", "geometry"]], predicate="within")
    ind["n_facilities_duplicate_review"] = (
        ind["adm4_pcode"].map(j.groupby("adm4_pcode").size()).fillna(0).astype(int)
    )

    out = {k: [] for k in ("pop", "pop_r", "net", "net_r", "fac", "fac_r", "all", "all_r")}
    for _, row in ind.iterrows():
        pl, pr = population_level(row, rel["population"], census_anchored)
        nl, nr = network_level(row, rel["network"])
        fr = ["no official facility registry matched yet (OSM completeness unknown)"]
        if row["n_facilities_duplicate_review"]:
            fr.append(f"{row['n_facilities_duplicate_review']} mapped facilities pending duplicate review")
        overall = worst(pl, nl)
        reasons = [f"population: {r}" for r in pr] + [f"network: {r}" for r in nr]
        out["pop"].append(pl)
        out["pop_r"].append("; ".join(pr))
        out["net"].append(nl)
        out["net_r"].append("; ".join(nr))
        out["fac"].append("unverified")
        out["fac_r"].append("; ".join(fr))
        out["all"].append(overall)
        out["all_r"].append(
            "; ".join(reasons) or "population and network checks passed; facility inventory unverified"
        )
    ind["rel_population"], ind["rel_population_reasons"] = out["pop"], out["pop_r"]
    ind["rel_network"], ind["rel_network_reasons"] = out["net"], out["net_r"]
    ind["rel_facility_inventory"], ind["rel_facility_inventory_reasons"] = out["fac"], out["fac_r"]
    ind["rel_overall"], ind["rel_overall_reasons"] = out["all"], out["all_r"]
    ind["pop_ranking_eligible"] = (ind["rel_population"] != "low") & (ind["rel_network"] != "low")
    return ind


def facility_inventory(
    s: Settings, roles: gpd.GeoDataFrame, fac: pd.DataFrame, excl: pd.DataFrame
) -> pd.DataFrame:
    """Measurable inventory-completeness signals per indicator group (no completeness score exists)."""
    dup_keys = _pending_duplicate_keys(excl)
    conn = fac.set_index("fid_key")["conn_status"]
    rows = []
    for gname, g in s["indicator_groups"].items():
        sel = roles[(roles["category"] == g["category"]) & roles["subtype"].isin(g["subtypes"])]
        sel = sel.drop_duplicates("fid_key")
        status = sel["fid_key"].map(conn)
        named = sel["name"].astype(str).str.strip().replace({"nan": "", "None": ""}) != ""
        rows.append(
            {
                "group": gname,
                "n_in_city": int(sel["inside_city"].sum()),
                "n_in_buffer_outside_city": int((~sel["inside_city"].astype(bool)).sum()),
                "n_destinations_connected": int((status == "connected").sum()),
                "n_not_connected_not_used": int((status != "connected").sum()),
                "n_unnamed": int((~named).sum()),
                "n_not_decided_by_tag_rule": int(sel["status"].isin(NOT_TAG_RULE).sum()),
                "n_duplicate_review_pending": int(sel["fid_key"].isin(dup_keys).sum()),
                "registry_reference": "none",
                "inventory_status": "unverified",
                "note": "counts of mapped OSM features only; completeness unknown until matched to an official registry",
            }
        )
    return pd.DataFrame(rows).replace({np.nan: None})
