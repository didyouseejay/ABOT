"""Per-stage QA records, written to data/interim/qa/<stage>.json and gathered by the report."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from abot.config import Settings

log = logging.getLogger(__name__)


def qa_dir(s: Settings) -> Path:
    d = s.interim_dir / "qa"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(s: Settings, stage: str, checks: dict) -> None:
    """`checks` maps a check name to {"ok": bool|None, "value": ..., "note": str}."""
    for name, c in checks.items():
        level = logging.INFO if c.get("ok") is not False else logging.WARNING
        log.log(level, "QA %s.%s = %s %s", stage, name, c.get("value"), c.get("note", ""))
    (qa_dir(s) / f"{stage}.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")


def read_all(s: Settings) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(qa_dir(s).glob("*.json"))}


def check(ok: bool | None, value, note: str = "") -> dict:
    return {"ok": None if ok is None else bool(ok), "value": value, "note": note}


def run_meta_path(s: Settings) -> Path:
    return s.interim_dir / "run_meta.json"


def read_run_meta(s: Settings) -> dict:
    p = run_meta_path(s)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record_stage(s: Settings, stage: str) -> None:
    """Record when a stage finished and with which configuration (used by `abot audit` for staleness)."""
    meta = read_run_meta(s)
    meta[stage] = {
        "completed_utc": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "config_sha256": s.config_sha256,
        "boundary_buffer_m": s["osm"]["boundary_buffer_m"],
        "primary_weight": (s.get("population") or {}).get("primary_weight"),
    }
    run_meta_path(s).write_text(json.dumps(meta, indent=2), encoding="utf-8")
