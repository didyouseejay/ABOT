"""Streaming downloads with a provenance manifest (URL, date, size, SHA-256)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)

USER_AGENT = "ABOT/0.1 (Iloilo City accessibility research)"
CHUNK = 1 << 20  # 1 MiB keeps memory flat regardless of file size


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_path(raw_dir: Path) -> Path:
    return raw_dir / "manifest.json"


def load_manifest(raw_dir: Path) -> dict:
    p = _manifest_path(raw_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record(raw_dir: Path, dest: Path, url: str, licence: str, **extra) -> None:
    manifest = load_manifest(raw_dir)
    manifest[dest.relative_to(raw_dir).as_posix()] = {
        "url": url,
        "licence": licence,
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "bytes": dest.stat().st_size,
        "sha256": sha256(dest),
        **extra,
    }
    _manifest_path(raw_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def download(url: str, dest: Path, *, force: bool = False, timeout: int = 60) -> Path:
    """Download `url` to `dest` unless it already exists with the expected size."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if dest.exists() and not force:
        head = session.head(url, allow_redirects=True, timeout=timeout)
        expected = int(head.headers.get("Content-Length", -1))
        if expected in (-1, dest.stat().st_size):
            log.info("cached: %s", dest.name)
            return dest
        log.info("size mismatch for %s, re-downloading", dest.name)

    tmp = dest.with_suffix(dest.suffix + ".part")
    with session.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        next_report = 0.0
        with open(tmp, "wb") as f:
            for block in r.iter_content(CHUNK):
                f.write(block)
                done += len(block)
                if total and done / total >= next_report:
                    log.info("%s: %3.0f%% of %.1f MB", dest.name, 100 * done / total, total / 1e6)
                    next_report += 0.25
    tmp.replace(dest)
    return dest
