"""Copy superseded run outputs into data/archive/<name>/ with a SHA-256 record, then verify the copy.

The record (`data/archive/<name>.sha256.json`) has the same shape as the earlier archives, so
`abot audit` checks it automatically. Files are COPIED: the originals are never moved or deleted
here (removing them is a separate, manual decision). An existing archive is never overwritten.

Layout: every source is copied under a prefix (`interim/`, `processed/`, `comparison_<name>/`,
`config/`), mirroring data/archive/stale_sens_maxspeed_override_m02_1km.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from abot.config import PROJECT_ROOT, Settings
from abot.fetch.common import sha256

log = logging.getLogger(__name__)


def _files(src: Path) -> list[Path]:
    return sorted(p for p in src.rglob("*") if p.is_file()) if src.is_dir() else [src]


def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def copy_and_record(
    s: Settings, name: str, sources: dict[str, Path], note: str, context: dict | None = None
) -> dict:
    """Copy each source (file or directory) to archive/<name>/<prefix>/..., hash both sides, record.

    Raises if the archive or its record already exists, if a source is missing, or if any copied file
    does not match its source byte for byte. The originals are left in place.
    """
    arch = s.data_dir / "archive"
    dest_root, record_path = arch / name, arch / f"{name}.sha256.json"
    if dest_root.exists() or record_path.exists():
        raise FileExistsError(f"archive {name} already exists: never overwritten")
    missing = [str(p) for p in sources.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"archive sources missing: {missing}")

    files: dict[str, str] = {}
    origin: dict[str, dict] = {}
    for prefix, src in sorted(sources.items()):
        base = src if src.is_dir() else src.parent
        for f in _files(src):
            rel = f"{prefix}/{f.relative_to(base).as_posix()}"
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)  # keeps the modification time: it records when the run was built
            h_src, h_dst = sha256(f), sha256(target)
            if h_src != h_dst:
                raise OSError(f"copy of {f} does not match its source")
            files[rel] = h_dst
            origin[rel] = {
                "source": f.relative_to(s.root).as_posix() if f.is_relative_to(s.root) else str(f),
                "bytes": f.stat().st_size,
                "source_mtime_local": datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(
                    timespec="seconds"
                ),
            }
    rec = {
        "archive": name,
        "recorded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": note,
        "originals_kept": True,
        "git_head_at_archive": _git_head(s.root),
        "context": context or {},
        "files": dict(sorted(files.items())),
        "origin": dict(sorted(origin.items())),
    }
    record_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    log.info("archived %d files to %s", len(files), dest_root)
    return rec


def verify(s: Settings, name: str, against_sources: bool = True) -> dict:
    """Re-hash the archive independently of the copy step.

    Returns {"files", "archive_mismatch", "source_mismatch", "extra_in_archive"}. With
    `against_sources`, every original that still exists is hashed again too.
    """
    arch = s.data_dir / "archive"
    rec = json.loads((arch / f"{name}.sha256.json").read_text(encoding="utf-8"))
    root = arch / name
    bad_arch = [f for f, h in rec["files"].items() if not (root / f).exists() or sha256(root / f) != h]
    bad_src = []
    if against_sources:
        for f, h in rec["files"].items():
            src = s.root / rec["origin"][f]["source"]
            if src.exists() and sha256(src) != h:
                bad_src.append(f)
    listed = set(rec["files"])
    extra = sorted(p.relative_to(root).as_posix() for p in _files(root) if p.relative_to(root).as_posix() not in listed)
    return {"files": len(rec["files"]), "archive_mismatch": bad_arch, "source_mismatch": bad_src, "extra_in_archive": extra}


def remove_verified_originals(s: Settings, name: str, prefixes: tuple[str, ...]) -> list[str]:
    """Delete the originals of an archive, but only those under `prefixes`, and only after both the
    archive and every original still match the recorded SHA-256. Returns the deleted source paths.

    The archive record is updated (`originals_kept: false`, `originals_removed`); its file hashes are
    not touched. Empty source directories are removed afterwards. Anything outside the recorded files
    (e.g. a file added to the folder since archiving) blocks the removal.
    """
    arch = s.data_dir / "archive"
    record_path = arch / f"{name}.sha256.json"
    rec = json.loads(record_path.read_text(encoding="utf-8"))
    chk = verify(s, name, against_sources=True)
    targets = {f: s.root / rec["origin"][f]["source"] for f in rec["files"] if f.split("/")[0] in prefixes}
    missing = [f for f, p in targets.items() if not p.exists()]
    if chk["archive_mismatch"] or chk["source_mismatch"] or chk["extra_in_archive"] or missing or not targets:
        raise RuntimeError(f"archive {name} not verified, nothing removed: {chk}, missing originals {missing}")
    dirs = {p.parent for p in targets.values()}
    # Each archived source folder (parent of its top-level files) must hold exactly the recorded files.
    recorded = {p.resolve() for p in targets.values()}
    for d in {targets[f].parent for f in targets if f.count("/") == 1}:
        unexpected = [p for p in d.rglob("*") if p.is_file() and p.resolve() not in recorded]
        if unexpected:
            raise RuntimeError(f"unrecorded files in {d}, nothing removed: {unexpected[:5]}")
    removed = []
    for f, p in sorted(targets.items()):
        p.unlink()
        removed.append(rec["origin"][f]["source"])
    for d in sorted(dirs, key=lambda x: len(x.parts), reverse=True):  # deepest first
        while d != s.data_dir and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    rec["originals_kept"] = False
    rec["originals_removed"] = {
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "prefixes": list(prefixes),
        "files": removed,
        "verified_before_removal": chk,
    }
    record_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    log.info("removed %d verified originals of %s", len(removed), name)
    return removed


def archive_e7_buffer_3km(s: Settings) -> dict:
    """Phase E of Milestone 04: the original Experiment E7 outputs (Milestone 02 code, 3 km buffer)."""
    d = s.data_dir
    cfg = PROJECT_ROOT / "config" / "experiments" / "e7_buffer_3km.yaml"
    sources = {
        "interim": d / "interim" / "e7_buffer_3km",
        "processed": d / "processed" / "e7_buffer_3km",
        "comparison_e7_buffer_1km_vs_3km": d / "processed" / "comparisons" / "e7_buffer_1km_vs_3km",
        "config": cfg,
    }
    note = (
        "Original Experiment E7 outputs (3 km OSM extraction buffer), built 2026-10-31 15:23-15:52 local "
        "with the Milestone 02 working-tree code, before stage recording (no run_meta.json). Since "
        "Milestone 02B the 3 km buffer IS the baseline, so these outputs are superseded: they use the "
        "Milestone 02 definitions (unadjusted WorldPop 2026 weights, connected-only denominators, no "
        "census anchoring, pre-fix mixed-class drive speeds). comparison_e7_buffer_1km_vs_3km compares "
        "the then-baseline (1 km, M02) with this run. The current buffer comparison is "
        "comparisons/e7_buffer_1km_vs_3km_m02b (hist_buffer_1km vs the active baseline), not archived. "
        "Copied in Milestone 04; originals kept in place pending a separate decision."
    )
    context = {
        "experiment_config": "config/experiments/e7_buffer_3km.yaml (copy under config/)",
        "experiment_overrides": {"paths.run_name": "e7_buffer_3km", "osm.boundary_buffer_m": 3000},
        "built_with_code": "Milestone 02 working tree, after commit 3edc0dd (Milestone 01) and before "
        "commit 3e85764 (Milestone 02B, 2026-10-31 18:36 +0800)",
        "osm_cache_used": "walk 547bf6791e75, drive 5b51ed1ede82, barriers 5eb220f49c1c, facilities "
        "662e760ef580 (see interim/osm_provenance.json); the same responses the active baseline uses",
        "active_baseline": "data/processed (3 km, Milestone 02B definitions); unchanged by this archive",
        "why_historical": "built before census anchoring, the fractional barangay allocation, the "
        "all-residents denominators and the drive-speed fix; flagged by `abot audit` (experiment: "
        "e7_buffer_3km, no run_meta.json)",
    }
    return copy_and_record(s, "hist_e7_buffer_3km_m02", sources, note, context)


def archive_m04_pre_access_taxonomy(s: Settings, crosswalk: Path) -> dict:
    """M04 methodology review: the review/m04 evidence and the A3 layer as built with the pre-review
    access labels, before `abot components` regenerates them, plus the old-to-new label crosswalk."""
    d = s.processed_dir
    sources = {"review_m04": d / "review" / "m04", "component_aware": d / "component_aware", "crosswalk": crosswalk}
    note = (
        "review/m04 and component_aware as built before the M04 access-taxonomy revision. Old labels "
        "(ineligible, resident_restricted, private_uncertain, uncertain) inferred residents from highway=service "
        "and called an explicit access=private outside residential context 'uncertain'. New labels (no, private, "
        "residents, customers, unknown, destination, pedestrian_override, untagged, public; abot.access) describe "
        "the mapped tags only. crosswalk/access_taxonomy_crosswalk.csv maps every cached walk way and gate node "
        "from the old class to the new status. Routing, components and A3 are not changed by the revision; "
        "review_m04/component_inventory.csv is the reference for the exact component-class check in "
        "`abot components`. Originals are regenerated in place, not deleted."
    )
    context = {
        "reason": "access taxonomy revision (separate physical connectivity, mapped restriction, public "
        "pedestrian access and authorised-user access)",
        "regenerated_by": "abot components (offline: Overpass cache and the existing targeted snapshot only)",
        "unchanged_by_revision": "walk graph, component membership and classes, A1/A2/A3 categories, "
        "population, facility travel times, targeted snapshot data/raw/osm_targeted/",
    }
    return copy_and_record(s, "review_m04_pre_access_taxonomy", sources, note, context)
