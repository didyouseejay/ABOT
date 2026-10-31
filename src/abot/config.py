"""Load settings.yaml and resolve project paths."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass
class Settings:
    raw: dict[str, Any]
    root: Path = PROJECT_ROOT

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @cached_property
    def data_dir(self) -> Path:
        return self.root / self.raw["paths"]["data_dir"]

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_dir(self) -> Path:
        return self.data_dir / "interim"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def gpkg(self) -> Path:
        """Main Milestone 01 output: one GeoPackage, many layers."""
        return self.processed_dir / "abot_iloilo.gpkg"

    @property
    def projected_crs(self) -> str:
        return self.raw["crs"]["projected"]

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.interim_dir, self.processed_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings(path: Path | str = DEFAULT_CONFIG) -> Settings:
    with open(path, encoding="utf-8") as f:
        settings = Settings(yaml.safe_load(f))
    settings.ensure_dirs()
    return settings
