"""Fetch the three external datasets: COD-AB boundaries, PSA 2020 census, WorldPop rasters."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from abot.config import Settings
from abot.fetch.common import USER_AGENT, download, record

log = logging.getLogger(__name__)

HDX_API = "https://data.humdata.org/api/3/action/package_show"


def hdx_resources(dataset: str) -> tuple[dict, list[dict]]:
    r = requests.get(HDX_API, params={"id": dataset}, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    pkg = r.json()["result"]
    return pkg, pkg["resources"]


def fetch_boundaries(s: Settings, force: bool = False) -> Path:
    cfg = s["sources"]["cod_ab"]
    pkg, resources = hdx_resources(cfg["hdx_dataset"])
    res = next(r for r in resources if r["name"] == cfg["resource_name"])
    dest = s.raw_dir / "cod_ab" / res["name"]
    download(res["url"], dest, force=force)
    record(
        s.raw_dir,
        dest,
        res["url"],
        pkg.get("license_title", ""),
        hdx_dataset=cfg["hdx_dataset"],
        hdx_last_modified=res.get("last_modified"),
    )
    return dest


def fetch_census(s: Settings, force: bool = False) -> Path:
    cfg = s["sources"]["census_2020"]
    pkg, resources = hdx_resources(cfg["hdx_dataset"])
    res = next(r for r in resources if r.get("format", "").upper() in {"XLSX", "XLS"})
    dest = s.raw_dir / "census_2020" / Path(res["url"]).name
    download(res["url"], dest, force=force)
    record(
        s.raw_dir,
        dest,
        res["url"],
        pkg.get("license_title", ""),
        hdx_dataset=cfg["hdx_dataset"],
        hdx_last_modified=res.get("last_modified"),
    )
    return dest


def worldpop_path(s: Settings, year: int) -> Path:
    url = s["sources"]["worldpop"]["url_template"].format(year=year)
    return s.raw_dir / "worldpop" / Path(url).name


def fetch_worldpop(s: Settings, force: bool = False) -> list[Path]:
    cfg = s["sources"]["worldpop"]
    paths = []
    for year in cfg["years"]:
        url = cfg["url_template"].format(year=year)
        dest = worldpop_path(s, year)
        download(url, dest, force=force)
        record(s.raw_dir, dest, url, "CC BY 4.0", release="R2025A v1", year=year)
        paths.append(dest)
    return paths


def fetch_all(s: Settings, force: bool = False) -> None:
    log.info("COD-AB boundaries -> %s", fetch_boundaries(s, force))
    log.info("2020 census -> %s", fetch_census(s, force))
    for p in fetch_worldpop(s, force):
        log.info("WorldPop -> %s", p)
