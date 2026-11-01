"""Regression tests for Milestone 06.2A: the targeted gap snapshot is optional, declared evidence.

`abot components` writes review/m04/snapshot_status.json on every run and the corridor table only when
a targeted snapshot (`abot fetch-gaps --allow-download`) exists. The exporter must accept both states
as declared and refuse every inconsistent combination (V-S5). Offline; the end-to-end test reads the
real outputs read-only, writes only to a temporary directory, and is skipped without them."""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from abot import dashboard_data as D
from abot.config import DEFAULT_CONFIG, Settings, read_config

CFG = Settings(read_config(DEFAULT_CONFIG))
HAVE_DATA = (CFG.processed_dir / "component_aware" / "run_info.json").exists() and CFG.gpkg.exists()
SHA = "a" * 64


def _m04(tmp_path, status: dict | None, corridors: str | None = None):
    s = Settings(CFG.raw, root=tmp_path)
    m04 = s.processed_dir / "review" / "m04"
    m04.mkdir(parents=True)
    if status is not None:
        (m04 / D.SNAPSHOT_STATUS).write_text(json.dumps(status), encoding="utf-8")
    if corridors is not None:
        (m04 / D.CORRIDORS).write_text(corridors, encoding="utf-8")
    return s, m04


def _src(status: dict, corr: pd.DataFrame, gap_obtained: bool, manifest_sha: str | None):
    manifest = {"osm_cache/x.json": {"sha256": "b" * 64}}
    if manifest_sha:
        manifest["osm_targeted/m04_gaps_20261031T131445Z.json"] = {"sha256": manifest_sha}
    gapinv = pd.DataFrame({"fragment": ["F001", "F100", "F101"], "snapshot_obtained": [gap_obtained] * 3})
    return SimpleNamespace(snapshot_status=status, corr=corr, gapinv=gapinv, raw_manifest=manifest)


CORRIDOR_CSV = (
    "candidate,fragment,path_ways,path_gates,classification_reason,applied\n1,F001,way/1,none,r,False\n"
)
NOT_OBTAINED = {"obtained": False, "snapshot": None}
OBTAINED = {"obtained": True, "response_sha256": SHA, "link_candidates": 1}


def test_no_snapshot_declared_is_a_valid_state(tmp_path):
    s, m04 = _m04(tmp_path, NOT_OBTAINED)
    assert D.snapshot_declared(m04) is False
    corr = D.load_corridors(m04)
    assert corr.empty and list(corr.columns) == D.CORRIDOR_COLUMNS
    paths = [p for p, _ in D.source_paths(s, DEFAULT_CONFIG)]
    assert m04 / D.SNAPSHOT_STATUS in paths and m04 / D.CORRIDORS not in paths
    assert D.snapshot_checks(s, _src(NOT_OBTAINED, corr, False, None)) == []


def test_declared_snapshot_requires_and_reads_its_corridor_table(tmp_path):
    s, m04 = _m04(tmp_path, OBTAINED, CORRIDOR_CSV)
    assert D.snapshot_declared(m04) is True
    assert m04 / D.CORRIDORS in [p for p, _ in D.source_paths(s, DEFAULT_CONFIG)]  # V-S1 if absent
    corr = D.load_corridors(m04)
    assert corr["fragment"].tolist() == ["F001"]
    assert D.snapshot_checks(s, _src(OBTAINED, corr, True, SHA)) == []


def test_snapshot_without_link_candidates_gives_an_empty_table(tmp_path):
    status = {**OBTAINED, "link_candidates": 0}
    s, m04 = _m04(tmp_path, status)
    pd.DataFrame().to_csv(m04 / D.CORRIDORS, index=False)  # exactly what `abot components` writes then
    corr = D.load_corridors(m04)
    assert corr.empty and list(corr.columns) == D.CORRIDOR_COLUMNS
    assert D.snapshot_checks(s, _src(status, corr, True, SHA)) == []
    # the same empty table is refused when the declaration says candidates exist
    bad = D.snapshot_checks(s, _src(OBTAINED, corr, True, SHA))
    assert len(bad) == 1 and "1 link candidate" in bad[0]


def test_missing_declaration_is_reported_not_guessed(tmp_path):
    s, m04 = _m04(tmp_path, None)
    assert D.snapshot_declared(m04) is None
    paths = [p for p, _ in D.source_paths(s, DEFAULT_CONFIG)]
    assert m04 / D.SNAPSHOT_STATUS in paths and m04 / D.CORRIDORS in paths  # both reported by V-S1
    for status in ({}, {"obtained": "yes"}):
        assert D.snapshot_checks(s, _src(status, pd.DataFrame(), False, None))[0].startswith("V-S5")


@pytest.mark.parametrize(
    ("status", "corridor_file", "gap_obtained", "manifest_sha", "expected"),
    [
        (NOT_OBTAINED, True, False, None, "exists from another run"),
        (NOT_OBTAINED, False, True, None, "gap_investigation.csv"),
        (OBTAINED, True, False, SHA, "gap_investigation.csv"),
        (NOT_OBTAINED, False, False, SHA, "not the one"),  # snapshot downloaded after `abot components`
        (OBTAINED, True, True, "c" * 64, "not the one"),  # a newer snapshot than the one used
    ],
)
def test_inconsistent_snapshot_states_are_refused(tmp_path, status, corridor_file, gap_obtained, manifest_sha,
                                                  expected):  # fmt: skip
    s, m04 = _m04(tmp_path, status, CORRIDOR_CSV if corridor_file else None)
    bad = D.snapshot_checks(s, _src(status, D.load_corridors(m04), gap_obtained, manifest_sha))
    assert len(bad) == 1 and bad[0].startswith("V-S5") and expected in bad[0]


@pytest.mark.skipif(not HAVE_DATA, reason="analytical outputs not present")
def test_export_without_a_snapshot_marks_the_evidence_as_not_examined(tmp_path, monkeypatch):
    """The real outputs as `abot components` would leave them without a snapshot: the bundle is valid,
    the gap evidence says what was not examined, and no indicator depends on the snapshot."""
    real_load = D.load

    def load_without_snapshot(s):
        src = real_load(s)
        src.snapshot_status = {**NOT_OBTAINED, "note": "no targeted snapshot"}
        src.corr = pd.DataFrame(columns=D.CORRIDOR_COLUMNS)
        g = src.gapinv.copy()
        g["snapshot_obtained"] = False
        g["snapshot_physical_connection"] = "not_examined"
        src.gapinv = g
        src.raw_manifest = {p: e for p, e in src.raw_manifest.items() if not p.startswith("osm_targeted/")}
        return src

    monkeypatch.setattr(D, "load", load_without_snapshot)
    # the on-disk view of the same state: no declaration of a snapshot and no corridor table
    monkeypatch.setattr(D, "snapshot_declared", lambda m04: False)
    monkeypatch.setattr(D, "CORRIDORS", "absent_in_this_test.csv")
    assert D.export(CFG, DEFAULT_CONFIG, skip_audit=True, root=tmp_path) == 0
    v1 = tmp_path / "v1"
    net = json.loads((v1 / "network.json").read_text(encoding="utf-8"))
    assert [g["fragment"] for g in net["gap_evidence"]] == ["F001", "F100", "F101"]
    assert all(g["snapshot_physical_connection"] == "not_examined" and g["path_ways"] is None
               and g["classification_reason"] is None and g["applied"] is False for g in net["gap_evidence"])  # fmt: skip
    prov = json.loads((v1 / "provenance.json").read_text(encoding="utf-8"))
    assert prov["targeted_snapshot"] is None
    # indicators are independent of the snapshot: identical to the installed bundle
    installed = CFG.processed_dir / "dashboard" / "v1"
    if (installed / "city.json").exists():
        for name, keys in (
            ("city.json", ("population", "walk", "drive")),
            ("barangay_indicators.json", ("barangays",)),
        ):
            new = json.loads((v1 / name).read_text(encoding="utf-8"))
            old = json.loads((installed / name).read_text(encoding="utf-8"))
            assert all(new[k] == old[k] for k in keys)
