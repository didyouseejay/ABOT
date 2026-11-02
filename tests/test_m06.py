"""Regression tests for Milestone 06.2A: the targeted gap snapshot is optional, declared evidence.

`abot components` writes review/m04/snapshot_status.json on every run and the corridor table only when
a targeted snapshot (`abot fetch-gaps --allow-download`) exists. The exporter must accept both states
as declared and refuse every inconsistent combination (V-S5).

Follow-up: archive-aware validation. Without any data/archive/ (a fresh clone) the archive-dependent
checks are NOT PERFORMED (audit WARN, V-S4 `not_performed`), never passed; whenever data/archive/
exists they stay strict. Offline; the end-to-end tests read the real outputs read-only, write only to
a temporary directory, and are skipped without them."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest

from abot import audit
from abot import dashboard_data as D
from abot.config import DEFAULT_CONFIG, Settings, read_config
from abot.fetch.common import sha256

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


def _src(status: dict, corr: pd.DataFrame, gap_obtained: bool, manifest_sha: str | None) -> D.Sources:
    """A stand-in for D.Sources with only the fields snapshot_checks reads."""
    manifest = {"osm_cache/x.json": {"sha256": "b" * 64}}
    if manifest_sha:
        manifest["osm_targeted/m04_gaps_20261031T131445Z.json"] = {"sha256": manifest_sha}
    gapinv = pd.DataFrame({"fragment": ["F001", "F100", "F101"], "snapshot_obtained": [gap_obtained] * 3})
    ns = SimpleNamespace(snapshot_status=status, corr=corr, gapinv=gapinv, raw_manifest=manifest)
    return cast(D.Sources, ns)


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


# --- archive-aware validation (M06.2A follow-up) ---------------------------------------------------

REF = Path("archive") / "review_m04_pre_access_taxonomy" / "review_m04" / "component_inventory.csv"
COMPARED = {"reference": "data/" + REF.as_posix(), "components_compared": 112, "identical": True}
NOT_COMPARED = {"reference": None, "note": "pre-taxonomy reference archive absent: not compared"}


def _project(tmp_path, archive: bool = False, m01: bool = False, reference: bool = False) -> Settings:
    s = Settings(CFG.raw, root=tmp_path)
    arch = s.data_dir / "archive"
    if archive:
        arch.mkdir(parents=True)
    if m01:
        f = arch / "m01_3edc0dd" / "barangay_access.csv"
        f.parent.mkdir(parents=True)
        f.write_text("a\n1\n", encoding="utf-8")
        rec = {"archive": "m01_3edc0dd", "recorded_utc": "x", "files": {"barangay_access.csv": sha256(f)}}
        (arch / "m01_3edc0dd.sha256.json").write_text(json.dumps(rec), encoding="utf-8")
    if reference:
        (s.data_dir / REF).parent.mkdir(parents=True)
        (s.data_dir / REF).write_text("fragment\nmain\n", encoding="utf-8")
    return s


def _archive_findings(s):
    a = audit.Audit(s, DEFAULT_CONFIG)
    a.check_archive()
    return {f.check: f for f in a.findings}


def test_absent_archive_tree_is_not_performed_never_passed(tmp_path):
    s = _project(tmp_path)
    f = _archive_findings(s)
    assert list(f) == ["m01_archive_present"]
    m01 = f["m01_archive_present"]
    assert (
        m01.status == audit.WARN
        and m01.detail.startswith(audit.NOT_PERFORMED)
        and "data/archive/ absent" in m01.detail
    )
    block, bad = D.classes_check(s, NOT_COMPARED)
    assert bad == [] and block["status"] == "not_performed"
    assert block["identical"] is None and block["components_compared"] is None and "absent" in block["reason"]
    assert not (tmp_path / "data").exists()  # nothing created


def test_complete_archive_with_valid_references_passes_strictly(tmp_path):
    s = _project(tmp_path, archive=True, m01=True, reference=True)
    f = _archive_findings(s)
    assert f["m01_archive_present"].status == audit.PASS and f["m01_3edc0dd"].status == audit.PASS
    block, bad = D.classes_check(s, COMPARED)
    assert bad == [] and block == {**COMPARED, "status": "performed", "reason": None}


def test_archive_present_but_missing_references_fails(tmp_path):
    # the M01 archive missing from an existing archive tree stays a FAIL
    s = _project(tmp_path, archive=True, reference=True)
    assert _archive_findings(s)["m01_archive_present"].status == audit.FAIL
    # the taxonomy reference missing from an existing archive tree: no comparison possible -> V-S4
    s = _project(tmp_path / "b", archive=True, m01=True)
    _, bad = D.classes_check(s, NOT_COMPARED)
    assert len(bad) == 1 and bad[0].startswith("V-S4") and "incomplete archive" in bad[0]
    # a comparison recorded earlier whose reference has since disappeared from the archive
    _, bad = D.classes_check(s, COMPARED)
    assert len(bad) == 1 and "no longer in data/archive/" in bad[0]
    # an archived file listed in its SHA-256 record but missing
    (s.data_dir / "archive" / "m01_3edc0dd" / "barangay_access.csv").unlink()
    assert _archive_findings(s)["m01_3edc0dd"].status == audit.FAIL


@pytest.mark.parametrize(
    ("taxonomy", "expected"),
    [
        ({**COMPARED, "identical": False}, "taxonomy_check False"),
        ({**COMPARED, "components_compared": 111}, "111 components"),
        (
            {**COMPARED, "reference": "data/archive/other/component_inventory.csv"},
            "not the pre-taxonomy reference",
        ),
        (NOT_COMPARED, "the comparison was not made"),  # reference present, `components` ran without it
    ],
)
def test_invalid_or_inconsistent_references_fail(tmp_path, taxonomy, expected):
    s = _project(tmp_path, archive=True, m01=True, reference=True)
    _, bad = D.classes_check(s, taxonomy)
    assert len(bad) == 1 and bad[0].startswith("V-S4") and expected in bad[0]


def test_modified_archived_file_fails(tmp_path):
    s = _project(tmp_path, archive=True, m01=True, reference=True)
    (s.data_dir / "archive" / "m01_3edc0dd" / "barangay_access.csv").write_text("a\n2\n", encoding="utf-8")
    assert _archive_findings(s)["m01_3edc0dd"].status == audit.FAIL


def _export_with_archive_dir(tmp_path, monkeypatch, arch: Path, taxonomy: dict) -> int:
    """Export the real outputs to tmp_path/bundle as if data/archive/ were `arch` and taxonomy_check.json
    were `taxonomy`. The audit block is the one the real audit gives without archives."""
    real_load = D.load

    def load(s):
        src = real_load(s)
        src.taxonomy = taxonomy
        return src

    monkeypatch.setattr(D, "load", load)
    monkeypatch.setattr(D, "archive_dir", lambda s: arch)
    finding = audit.Finding(
        "archive", "m01_archive_present", audit.WARN, f"{audit.NOT_PERFORMED}: data/archive/ absent"
    )
    monkeypatch.setattr(D, "run_audit", lambda s, c, skip: D.audit_from_findings([finding], "t"))
    return D.export(CFG, DEFAULT_CONFIG, root=tmp_path / "bundle")


@pytest.mark.skipif(not HAVE_DATA, reason="analytical outputs not present")
def test_export_without_archives_records_not_performed(tmp_path, monkeypatch):
    assert _export_with_archive_dir(tmp_path, monkeypatch, tmp_path / "no_archive", NOT_COMPARED) == 0
    v1 = tmp_path / "bundle" / "v1"
    man = json.loads((v1 / "manifest.json").read_text(encoding="utf-8"))
    sv = man["data_quality"]["source_validation"]
    cc = sv["component_classes_check"]
    assert cc["status"] == "not_performed" and cc["identical"] is None and cc["components_compared"] is None
    assert sv["audit"]["outcome"] == "warn" and sv["audit"]["findings"][0]["detail"].startswith(
        audit.NOT_PERFORMED
    )
    codes = [k["code"] for k in man["known_issues"]]
    assert D.ARCHIVE_ISSUE in codes and "AUDIT-WARN" in codes
    assert man["contract_version"] == "1.1.0"
    # the indicators do not depend on the archives: identical to the installed bundle
    installed = CFG.processed_dir / "dashboard" / "v1"
    if (installed / "city.json").exists():
        for name, keys in (
            ("city.json", ("population", "walk", "walk_internal", "walk_distribution", "drive")),
            ("barangay_indicators.json", ("barangays",)),
            ("facilities.geojson", ("features",)),
            ("cells-001.geojson", ("features",)),
            ("cells-002.geojson", ("features",)),
        ):
            new = json.loads((v1 / name).read_text(encoding="utf-8"))
            old = json.loads((installed / name).read_text(encoding="utf-8"))
            assert all(new[k] == old[k] for k in keys), name


@pytest.mark.skipif(not HAVE_DATA, reason="analytical outputs not present")
def test_export_with_incomplete_archives_is_blocked(tmp_path, monkeypatch, capsys):
    arch = tmp_path / "incomplete_archive"
    (arch / "m01_3edc0dd").mkdir(parents=True)  # the tree exists; the taxonomy reference does not
    assert _export_with_archive_dir(tmp_path, monkeypatch, arch, NOT_COMPARED) == 1
    out = capsys.readouterr().out
    assert "V-S4" in out and "incomplete archive" in out
    assert not (tmp_path / "bundle").exists()  # nothing written
