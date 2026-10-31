"""Load settings.yaml and resolve project paths.

An experiment config can start with `extends: <path>` (relative to itself) and override only the
keys it changes; mappings are merged recursively, everything else is replaced. Setting
`paths.run_name` sends interim and processed outputs to their own sub-folders so an experiment
never overwrites the baseline. Raw downloads (data/raw) are always shared.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "settings.yaml"


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge `override` into a copy of `base`. Non-mapping values are replaced."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def read_config(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    return deep_merge(read_config((path.parent / parent).resolve()), raw)


@dataclass
class Settings:
    raw: dict[str, Any]
    root: Path = PROJECT_ROOT

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @cached_property
    def data_dir(self) -> Path:
        return self.root / self.raw["paths"]["data_dir"]

    @property
    def run_name(self) -> str | None:
        return self.raw["paths"].get("run_name")

    def _run_dir(self, base: Path) -> Path:
        return base / self.run_name if self.run_name else base

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_dir(self) -> Path:
        return self._run_dir(self.data_dir / "interim")

    @property
    def processed_dir(self) -> Path:
        return self._run_dir(self.data_dir / "processed")

    @property
    def gpkg(self) -> Path:
        """Main output: one GeoPackage, many layers."""
        return self.processed_dir / "abot_iloilo.gpkg"

    @property
    def config_sha256(self) -> str:
        """Fingerprint of the resolved configuration, recorded with every build stage."""
        text = json.dumps(self.raw, sort_keys=True, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @property
    def projected_crs(self) -> str:
        return self.raw["crs"]["projected"]

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.interim_dir, self.processed_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings(path: Path | str = DEFAULT_CONFIG, create_dirs: bool = True) -> Settings:
    """`create_dirs=False` for read-only commands (`abot audit`) that must not touch the data tree."""
    settings = Settings(read_config(path))
    if create_dirs:
        settings.ensure_dirs()
    return settings
