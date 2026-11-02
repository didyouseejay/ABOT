"""Regression tests for Milestone 05.1: the dashboard data exporter (contract abot-dashboard 1.0.0).
Offline. Unit tests use synthetic data; the two end-to-end tests read the real outputs read-only,
write only to a temporary directory, and are skipped when the outputs are absent."""

import copy
import json
import math

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Polygon, shape

from abot import audit
from abot import dashboard_data as D
from abot.config import DEFAULT_CONFIG, Settings, read_config

CFG = Settings(read_config(DEFAULT_CONFIG))
HAVE_DATA = (CFG.processed_dir / "component_aware" / "run_info.json").exists() and CFG.gpkg.exists()


# --- serialisation and nulls (§5) -----------------------------------------------------------------


def test_dumps_is_compact_deterministic_and_rejects_nan():
    obj = {"b": 1.5, "a": [None, "é"]}
    assert D.dumps(obj) == '{"b":1.5,"a":[null,"é"]}\n'.encode()
    assert D.dumps(obj) == D.dumps(dict(obj))
    with pytest.raises(ValueError):
        D.dumps({"x": float("nan")})


def test_nn_keeps_null_null_and_zero_zero():
    assert D.nn(np.nan) is None and D.nn(pd.NA) is None and D.nn(None) is None
    assert D.nn(0.0) == 0.0 and D.nn(np.float64(0.0)) is not None
    assert D.nn(np.int64(3)) == 3 and isinstance(D.nn(np.int64(3)), int)
    assert D.nn(np.bool_(True)) is True
    assert D.as_int(4.0) == 4 and D.as_int(np.nan) is None
    with pytest.raises(D.ExportError):
        D.as_int(4.5)


# --- walk_distribution (§7.2, Q5) -----------------------------------------------------------------


def test_distribution_bins_are_right_closed_and_keep_the_open_bin():
    t = np.array([0.0, 0.5, 1.0, 1.01, 10.0, 59.99, 60.0, 60.01, 91.9, np.nan])
    w = np.array([1.0, 1, 1, 1, 1, 1, 1, 1, 5, 7])  # the NaN cell has no citywide time
    d = D.walk_distribution(t, w, float(w.sum()))
    bins = {b["upper_min"]: b["pop"] for b in d["bins"]}
    assert len(d["bins"]) == 61 and d["bins"][-1] == {"lower_min": 60, "upper_min": None, "pop": 6.0}
    assert bins[1] == 3.0  # 0, 0.5 and exactly 1.0 are in (0, 1]
    assert bins[2] == 1.0 and bins[10] == 1.0 and bins[60] == 2.0  # 59.99 and 60.0
    assert d["pop_open_bin"] == 6.0 and d["pop_with_time"] == 13.0 and d["pop_total"] == 20.0
    cum = {c["minutes"]: c["pct_all_residents"] for c in d["cumulative"]}
    assert cum[10] == round(100 * w[t <= 10].sum() / 20, 2)  # identical to a direct share
    assert cum[60] == round(100 * 7 / 20, 2)  # seven cells at or below 60 min
    # the final point includes the > 60 min population, still below 100 % (no-time residents)
    assert cum[None] == round(100 * 13 / 20, 2) and d["cumulative"][-1]["minutes"] is None
    assert cum[None] < 100


def test_distribution_reproduces_direct_shares_at_thresholds():
    rng = np.random.default_rng(1)
    t = np.round(rng.uniform(0.05, 95, 5000), 2)
    t[rng.random(5000) < 0.03] = np.nan
    w = rng.uniform(0, 120, 5000)
    d = D.walk_distribution(t, w, float(w.sum()))
    cum = {c["minutes"]: c["pct_all_residents"] for c in d["cumulative"]}
    for n in (10, 15, 30):
        assert cum[n] == round(100 * float(w[t <= n].sum()) / float(w.sum()), 2)


def _dist(t, w):
    t, w = np.asarray(t, float), np.asarray(w, float)
    return {"group": "g", **D.walk_distribution(t, w, float(w.sum()))}, t, w


def test_independent_check_accepts_a_correct_distribution_including_boundaries():
    rec, t, w = _dist([0.0, 1.0, 1.01, 15.0, 30.0, 60.0, 60.01, 120.0, np.nan], [1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert D.distribution_failures(rec, t, w) == []
    assert rec["bins"][0]["pop"] == 3.0 and rec["bins"][59]["pop"] == 6.0 and rec["pop_open_bin"] == 15.0


def test_independent_check_rejects_a_wrong_final_cumulative_point():
    rec, t, w = _dist([5.0, 61.0, 90.0, np.nan], [10, 20, 30, 40])
    for wrong in (
        100.0,
        rec["cumulative"][-2]["pct_all_residents"],
        rec["cumulative"][-1]["pct_all_residents"] + 0.01,
    ):
        bad = copy.deepcopy(rec)
        bad["cumulative"][-1]["pct_all_residents"] = wrong
        assert any("final cumulative point" in m for m in D.distribution_failures(bad, t, w)), wrong
    dropped = copy.deepcopy(rec)
    dropped["cumulative"].pop()  # final point missing
    assert D.distribution_failures(dropped, t, w)


def test_independent_check_rejects_a_dropped_or_moved_open_bin_population():
    rec, t, w = _dist([5.0, 61.0, 90.0], [10, 20, 30])
    zero = copy.deepcopy(rec)
    zero["bins"][-1]["pop"] = 0.0  # > 60 min residents suppressed
    assert any("open bin" in m for m in D.distribution_failures(zero, t, w))
    moved = copy.deepcopy(rec)
    moved["bins"][59]["pop"] += moved["bins"][-1]["pop"]  # folded into the 60-minute bin
    moved["bins"][-1]["pop"] = moved["pop_open_bin"] = 0.0
    assert len(D.distribution_failures(moved, t, w)) >= 2
    edges = copy.deepcopy(rec)
    edges["bins"][-1]["upper_min"] = 61
    assert any("bin edges" in m for m in D.distribution_failures(edges, t, w))


def test_independent_check_compares_with_citywide_reference_values():
    rec, t, w = _dist([5.0, 12.0, 25.0, 61.0], [10, 20, 30, 40])
    ref = {"pct_le10": rec["cumulative"][9]["pct_all_residents"], "mean_min": round(float(np.average(t, weights=w)), 2),
           "pop_network_connected": 100.0}  # fmt: skip
    assert D.distribution_failures(rec, t, w, ref) == []
    assert any("citywide_a3" in m for m in D.distribution_failures(rec, t, w, {**ref, "pct_le10": 0.0}))
    assert any("citywide_a3" in m for m in D.distribution_failures(rec, t, w, {**ref, "mean_min": 1.0}))


def test_distribution_without_any_citywide_time():
    rec, t, w = _dist([np.nan, np.nan], [3, 4])
    assert D.distribution_failures(rec, t, w) == []
    assert (
        rec["cumulative"][-1] == {"minutes": None, "pct_all_residents": 0.0} and rec["pop_with_time"] == 0.0
    )


# --- cell chunking (§7.5.1, Q9) -------------------------------------------------------------------


def _ctx():
    sv = {"audit": {"status": "not_run"}}
    # No Sources: the chunking code under test never reads them.
    return D.Ctx(CFG, None, "2026-11-01T00:00:00+00:00", sv, [], {})  # pyright: ignore[reportArgumentType]


def _feats(n):
    return [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [122.5, 10.7]},
             "properties": {"cell_id": f"r{i:05d}c1", "pop": 1.0}} for i in range(n)]  # fmt: skip


def test_single_file_when_under_the_limit():
    files, layout = D.chunk_cells(_ctx(), _feats(10), max_bytes=10**6)
    assert list(files) == ["cells-001.geojson"] and layout["count"] == 1
    assert layout["single_file_bytes"] == len(files["cells-001.geojson"])


def test_chunks_are_contiguous_equal_count_and_under_the_limit():
    feats = _feats(101)
    single = len(D.dumps(D.cells_file(_ctx(), feats, 1, 1)))
    files, layout = D.chunk_cells(_ctx(), feats, max_bytes=single // 2)
    n = layout["count"]
    assert n >= 3 and list(files) == [f"cells-{i:03d}.geojson" for i in range(1, n + 1)]
    assert all(len(b) <= single // 2 for b in files.values())
    got = [f["properties"]["cell_id"] for b in files.values() for f in json.loads(b)["features"]]
    assert got == [f["properties"]["cell_id"] for f in feats]  # nothing dropped, order kept
    m = math.ceil(101 / n)
    assert [c["features"] for c in layout["chunks"]] == [len(feats[i * m : (i + 1) * m]) for i in range(n)]
    # the smallest count that fits: one chunk fewer does not
    fewer = [D.dumps(D.cells_file(_ctx(), p, i + 1, n - 1)) for i, p in enumerate(D.split(feats, n - 1))]
    assert any(len(b) > single // 2 for b in fewer)
    for c, b in zip(layout["chunks"], files.values(), strict=True):
        o = json.loads(b)
        assert o["chunk"]["index"] == c["index"] and o["chunk"]["count"] == n and o["dataset"] == "cells"
        assert c["sha256"] == D.sha256_bytes(b) and c["bytes"] == len(b)


# --- audit gate (§6.1.1, Q3) ----------------------------------------------------------------------


def _f(status):
    return audit.Finding("sec", f"check_{status}", status, "detail", "")


def test_audit_outcomes_and_gate():
    passed, blocking = D.audit_from_findings([_f("PASS"), _f("INFO")], "t")
    warned, _ = D.audit_from_findings([_f("PASS"), _f("WARN")], "t")
    failed, why = D.audit_from_findings([_f("WARN"), _f("FAIL")], "t")
    assert passed["outcome"] == "pass" and passed["counts"] == {"pass": 1, "warn": 0, "fail": 0, "info": 1}
    assert warned["outcome"] == "warn" and [f["status"] for f in warned["findings"]] == ["WARN"]
    assert failed["outcome"] == "fail" and why and blocking == []
    assert D.audit_allows_export(passed, skip=False)
    assert D.audit_allows_export(warned, skip=False)
    assert not D.audit_allows_export(failed, skip=False)
    assert not D.audit_allows_export(failed, skip=True)


def test_skipped_audit_is_not_a_pass_and_only_allowed_on_request():
    block, _ = D.run_audit(CFG, DEFAULT_CONFIG, skip=True)
    assert block["status"] == "not_run" and block["outcome"] is None and block["counts"] is None
    assert D.audit_allows_export(block, skip=True)
    assert not D.audit_allows_export(block, skip=False)


def test_audit_exception_is_error_and_blocks(monkeypatch):
    def boom(self):
        raise RuntimeError("broken")

    monkeypatch.setattr(audit.Audit, "run", boom)
    block, why = D.run_audit(CFG, DEFAULT_CONFIG, skip=False)
    assert block["status"] == "error" and block["counts"] is None and "RuntimeError" in block["reason"]
    assert why and not D.audit_allows_export(block, skip=False)


# --- geometry (§8.2, Q1) --------------------------------------------------------------------------


def test_display_polygon_wraps_rounds_and_keeps_validity():
    sq = Polygon([(122.5, 10.7), (122.50001, 10.70000001), (122.51, 10.7), (122.51, 10.71), (122.5, 10.71)])
    out = D.display_polygon(MultiPolygon([sq]))
    assert out.geom_type == "MultiPolygon" and len(out.geoms) == 1 and out.is_valid
    assert all(round(x, 6) == x and round(y, 6) == y for x, y in out.geoms[0].exterior.coords)
    assert shapely_coords(out) < shapely_coords(sq)


def shapely_coords(g):
    import shapely

    return int(shapely.get_num_coordinates(g))


def test_invalid_display_geometry_fails_instead_of_being_repaired():
    bowtie = Polygon([(122.5, 10.7), (122.51, 10.71), (122.51, 10.7), (122.5, 10.71)])
    with pytest.raises(D.ExportError):
        D.display_polygon(MultiPolygon([bowtie]))


# --- catalogue (§4.1, Q2) -------------------------------------------------------------------------


def test_catalogue_ids_are_unique_complete_and_typed():
    cat, bsrc = D.catalog(CFG)
    ids = [e["id"] for e in cat]
    assert len(ids) == len(set(ids))
    assert {i for e in cat if "barangay" in e["levels"] for i in [e["id"]]} == set(bsrc)
    assert all(e["unit"] in ("%", "minutes", "residents") and e["role"] for e in cat)
    assert all(e["denominator"] or e["population_described"] for e in cat)
    assert all(set(e["statements"]) <= set(D.STATEMENTS) for e in cat)
    # A1 driving and A3 walking never share an id; sensitivity is evidence only; p90 is barangay only
    assert not any(i.startswith("A3.drive") for i in ids)
    assert all(e["role"] == "evidence_only" for e in cat if e["id"].startswith("A1.drive_sensitivity"))
    assert all(e["levels"] == ["barangay"] for e in cat if e["statistic"] == "p90_min")
    # local / uncertain internal counts are evidence only and never shares
    assert all(
        e["unit"] == "residents" and e["role"] == "evidence_only" for e in cat if "internal" in e["id"]
    )


# --- install / recover (§10.1) --------------------------------------------------------------------


ID1, ID2 = "0123456789ab", "ba9876543210"  # exporter-owned names use 12 lowercase hex characters


def _bundle(d, tag="x", complete=True):
    """A minimal bundle directory: one data file listed with its size and hash in manifest.json."""
    d.mkdir(parents=True)
    (d / "city.json").write_text(f'{{"tag": "{tag}"}}')
    files = [
        {"name": "city.json", "bytes": (d / "city.json").stat().st_size, "sha256": D.sha256(d / "city.json")}
    ]
    (d / "manifest.json").write_text(json.dumps({"generated_utc": tag, "files": files}))
    if not complete:
        (d / "city.json").write_text("edited after export")
    return d


def _names(root):
    return sorted(p.name for p in root.iterdir())


def test_install_replaces_and_recover_restores_after_a_crash(tmp_path):
    _bundle(tmp_path / "v1", "old")
    new = _bundle(tmp_path / f".v1.tmp-{ID1}", "new")
    D.install(new, tmp_path)
    assert json.loads((tmp_path / "v1" / "manifest.json").read_text())["generated_utc"] == "new"
    assert _names(tmp_path) == ["v1"]
    # crash between the two renames: v1 missing, one complete backup left -> restored
    (tmp_path / "v1").rename(tmp_path / f".v1.old-{ID1}")
    (tmp_path / f".v1.tmp-{ID2}").mkdir()
    D.recover(tmp_path)
    assert json.loads((tmp_path / "v1" / "manifest.json").read_text())["generated_utc"] == "new"
    assert _names(tmp_path) == ["v1"]


def test_install_failure_restores_the_previous_bundle(tmp_path):
    _bundle(tmp_path / "v1", "old")
    with pytest.raises(OSError):
        D.install(tmp_path / f".v1.tmp-{ID1}", tmp_path)  # missing temporary: second rename fails
    assert json.loads((tmp_path / "v1" / "manifest.json").read_text())["generated_utc"] == "old"
    assert _names(tmp_path) == ["v1"]


def test_recover_touches_only_exporter_owned_directories(tmp_path):
    _bundle(tmp_path / "v1")
    for name in (".v1.tmp-abc", ".v1.old-XYZ", f".v1.tmp-{ID1}x", "v1.old-0123456789ab", "notes"):
        (tmp_path / name).mkdir()
    (tmp_path / "README.txt").write_text("user file")
    (tmp_path / f".v1.tmp-{ID1}").mkdir()
    (tmp_path / f".v1.old-{ID2}").mkdir()
    D.recover(tmp_path)
    assert _names(tmp_path) == sorted([".v1.old-XYZ", ".v1.tmp-abc", f".v1.tmp-{ID1}x", "README.txt", "notes",
                                       "v1", "v1.old-0123456789ab"])  # fmt: skip


def test_backup_is_removed_only_when_v1_is_safely_present(tmp_path):
    _bundle(tmp_path / "v1", complete=False)  # v1 edited after export: not safely present
    _bundle(tmp_path / f".v1.old-{ID1}")
    notes = D.recover(tmp_path)
    assert f".v1.old-{ID1}" in _names(tmp_path) and any("kept" in n for n in notes)
    (tmp_path / "v1" / "manifest.json").unlink()  # no manifest: still not safely present
    D.recover(tmp_path)
    assert f".v1.old-{ID1}" in _names(tmp_path)


def test_incomplete_or_several_backups_stop_recovery_without_changes(tmp_path):
    _bundle(tmp_path / f".v1.old-{ID1}", complete=False)
    with pytest.raises(D.RecoveryError):
        D.recover(tmp_path)
    assert _names(tmp_path) == [f".v1.old-{ID1}"]
    _bundle(tmp_path / f".v1.old-{ID2}")
    with pytest.raises(D.RecoveryError):
        D.recover(tmp_path)
    assert _names(tmp_path) == [f".v1.old-{ID1}", f".v1.old-{ID2}"]
    # the export stops on this state before reading anything, and says so
    assert D.export(CFG, DEFAULT_CONFIG, root=tmp_path) == 1
    assert _names(tmp_path) == [f".v1.old-{ID1}", f".v1.old-{ID2}"]


def test_every_failed_check_is_reported(capsys):
    assert D._fail([f"check {i}" for i in range(250)]) == 1
    out = capsys.readouterr().out
    assert "250 problem(s)" in out and "check 0" in out and "check 249" in out and "more" not in out


def test_check_reports_a_recoverable_backup_without_changing_anything(tmp_path, capsys):
    s = Settings(CFG.raw, root=tmp_path)
    _bundle(tmp_path / f".v1.old-{ID1}", "2026-11-01T00:00:00+00:00")
    assert D.check(s, root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "no bundle" in out and "complete" in out and "recoverable" in out and "2026-11-01" in out
    assert _names(tmp_path) == [f".v1.old-{ID1}"]
    _bundle(tmp_path / f".v1.old-{ID2}", complete=False)
    assert D.check(s, root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "incomplete" in out and "not recoverable automatically" in out
    assert _names(tmp_path) == [f".v1.old-{ID1}", f".v1.old-{ID2}"]


# --- git metadata (D6) ----------------------------------------------------------------------------


def test_porcelain_z_keeps_spaces_and_unusual_characters_literally():
    out = '?? rc tests docs Documentation.md\0 M src/abot/cli.py\0R  new name.md\0old name.md\0?? .vscode/\0?? café "q".txt\0'
    assert D.parse_porcelain_z(out) == ["rc tests docs Documentation.md", "src/abot/cli.py", "new name.md",
                                        ".vscode/", 'café "q".txt']  # fmt: skip
    assert D.parse_porcelain_z("") == []


def test_git_info_on_a_scratch_repository(tmp_path):
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git not available")
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "init")
    assert D.git_info(tmp_path)["git_working_tree_clean"] is True
    (tmp_path / "a b.txt").write_text("x")
    info = D.git_info(tmp_path)
    assert info["git_working_tree_clean"] is False and info["git_dirty_count"] == 1
    assert info["git_dirty_paths"] == ["a b.txt"]  # not '"a b.txt"'
    assert D.git_info(tmp_path / "no-repo-here")["git_commit"] is None


# --- --check (§9.2) -------------------------------------------------------------------------------


def test_check_reports_current_then_stale(tmp_path, capsys):
    s = Settings(CFG.raw, root=tmp_path)
    src = tmp_path / "data" / "processed" / "x.csv"
    src.parent.mkdir(parents=True)
    src.write_text("a\n1\n")
    v1 = tmp_path / "bundle" / "v1"
    v1.mkdir(parents=True)
    (v1 / "city.json").write_text("{}")
    man = {"generated_utc": "2026-11-01T00:00:00+00:00", "contract_version": "1.0.0",
           "config_sha256": s.config_sha256, "code": {"git_commit": None, "git_working_tree_clean": None},
           "source_files": [{"path": "data/processed/x.csv", "sha256": D.sha256(src)}],
           "files": [{"name": "city.json", "sha256": D.sha256(v1 / "city.json")}]}  # fmt: skip
    (v1 / "manifest.json").write_text(json.dumps(man))
    before = sorted(p.name for p in v1.iterdir())
    assert D.check(s, root=tmp_path / "bundle") == 0
    src.write_text("a\n2\n")
    (v1 / "city.json").write_text('{"edited": true}')
    assert D.check(s, root=tmp_path / "bundle") == 1
    out = capsys.readouterr().out
    assert "source changed" in out and "edited" in out
    assert sorted(p.name for p in v1.iterdir()) == before  # read-only
    assert D.check(s, root=tmp_path / "nothing") == 1


def test_experiment_configuration_is_refused():
    exp = Settings({**CFG.raw, "paths": {**CFG.raw["paths"], "run_name": "hist_buffer_1km"}})
    with pytest.raises(SystemExit):
        D.export(exp, DEFAULT_CONFIG)


# --- end to end on the real outputs (read-only; writes only to tmp_path) --------------------------


@pytest.mark.skipif(not HAVE_DATA, reason="analytical outputs not present")
def test_failed_audit_blocks_the_export_and_keeps_the_previous_bundle(tmp_path, monkeypatch):
    (tmp_path / "v1").mkdir()
    (tmp_path / "v1" / "manifest.json").write_text("previous")
    failed, why = D.audit_from_findings([_f("FAIL")], "t")
    monkeypatch.setattr(D, "run_audit", lambda s, c, skip: (failed, why))
    assert D.export(CFG, DEFAULT_CONFIG, root=tmp_path) == 1
    assert (tmp_path / "v1" / "manifest.json").read_text() == "previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v1"]


@pytest.mark.skipif(not HAVE_DATA, reason="analytical outputs not present")
def test_export_end_to_end_then_failed_validation_keeps_it(tmp_path, monkeypatch):
    srcs = [p for p, _ in D.source_paths(CFG, DEFAULT_CONFIG)]
    before = {p: D.sha256(p) for p in srcs}
    assert D.export(CFG, DEFAULT_CONFIG, skip_audit=True, root=tmp_path) == 0
    v1 = tmp_path / "v1"
    man = json.loads((v1 / "manifest.json").read_text(encoding="utf-8"))
    assert man["data_quality"]["source_validation"]["audit"]["status"] == "not_run"
    assert "AUDIT-NOT-RUN" in [k["code"] for k in man["known_issues"]]
    assert man["cells_layout"]["features"] == 8035 and all(
        c["bytes"] <= D.MAX_FILE_BYTES for c in man["cells_layout"]["chunks"]
    )
    city = json.loads((v1 / "city.json").read_text(encoding="utf-8"))
    hosp = next(r for r in city["walk_distribution"] if r["group"] == "health_hospital")
    assert hosp["pop_open_bin"] > 0 and hosp["bins"][-1]["pop"] == hosp["pop_open_bin"]
    b = json.loads((v1 / "barangays.geojson").read_text(encoding="utf-8"))
    assert len(b["features"]) == 180 and all(shape(f["geometry"]).is_valid for f in b["features"])
    assert {p: D.sha256(p) for p in srcs} == before  # sources byte-identical
    # a failing validation writes nothing and keeps the bundle just written
    kept = {p.name: D.sha256(p) for p in v1.iterdir()}
    monkeypatch.setattr(D, "validate", lambda *a, **k: ["forced failure"])
    assert D.export(CFG, DEFAULT_CONFIG, skip_audit=True, root=tmp_path) == 1
    assert {p.name: D.sha256(p) for p in v1.iterdir()} == kept
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v1"]
