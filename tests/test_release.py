"""Tests for the M06.3 Phase 1 release tooling (scripts/release/; see releases/README.md).

Every test builds a synthetic Git repository and a synthetic dashboard bundle in a temporary
directory. None reads the real bundle or data/, and none uses the network.

"Forged" releases model an attacker who controls the release assets, and so can make the asset-level
hashes in a record match a tampered archive, but who cannot change the record the verifier reads
from the tag. Those tests show that each deeper layer catches the tampering on its own.
"""

import json
import shutil
import stat
import subprocess
import warnings
import zipfile
from collections.abc import Callable
from pathlib import Path

import eligibility as E
import fetch_bundle as F
import pack_release as P
import pytest
import release_lib as R
import verify_release as V

TAG = "v1.0.0"
GEN = "2026-11-02T01:39:00+00:00"
VERSION_TS = 'export const CONTRACT_ID = "abot-dashboard";\nexport const SUPPORTED_VERSION = "1.1.0";\n'


# --- synthetic repository and bundle ------------------------------------------------------------


def git(repo: Path, *args: str) -> str:
    cfg = ["-c", "user.name=ABOT Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]
    cfg += ["-c", "tag.gpgsign=false", "-c", "core.autocrlf=false"]
    r = subprocess.run(["git", "-C", str(repo), *cfg, *args], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def commit_all(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "dashboard/src/contract").mkdir(parents=True)
    (repo / ".gitignore").write_text("data/\ndist/\n", encoding="utf-8")
    (repo / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    (repo / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (repo / "LICENSE-DATA.md").write_text("# ABOT dataset licence\nODbL 1.0\n", encoding="utf-8")
    (repo / "docs/ATTRIBUTION.md").write_text(
        "# Attribution\n(c) OpenStreetMap contributors\n", encoding="utf-8"
    )
    (repo / R.VERSION_TS).write_text(VERSION_TS, encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    commit_all(repo, "initial")
    return repo


def jbytes(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode()


def make_bundle(
    repo: Path,
    commit: str,
    *,
    contract_version: str = "1.1.0",
    status: str = "obtained",
    outcome: str = "warn",
    fails: int = 0,
    clean: bool = True,
) -> Path:
    """A small bundle with the real bundle's structure: envelopes, manifest, provenance, OSM files."""
    raw = repo / R.RAW_REL
    osm = {"osm_cache/aaaa.json": b'{"elements":[1]}', "osm_targeted/gaps.json": b'{"elements":[2]}'}
    for rel, b in osm.items():
        (raw / rel).parent.mkdir(parents=True, exist_ok=True)
        (raw / rel).write_bytes(b)
    (raw / "osm_cache/unused.json").write_bytes(b"{}")  # cached but not used by the baseline

    def env(dataset: str, **body) -> bytes:
        return jbytes({"contract": "abot-dashboard", "contract_version": contract_version, "dataset": dataset,
                       "generated_utc": GEN, **body})  # fmt: skip

    files = {
        "city.json": env("city", population_total=1000),
        "cells-001.geojson": env("cells", type="FeatureCollection", features=[]),
        "provenance.json": env(
            "provenance",
            osm={
                "osmnx_version": "2.1.1",
                "overpass_endpoint": "https://overpass-api.de/api",
                "boundary_buffer_m": 3000,
                "responses": [
                    {
                        "label": "network_walk",
                        "cache_file": "osm_cache/aaaa.json",
                        "overpass_timestamp_osm_base": "2026-10-31T07:23:18Z",
                        "elements": 1,
                        "sha256": R.sha256_bytes(osm["osm_cache/aaaa.json"]),
                    },
                ],
            },  # fmt: skip
            targeted_snapshot={
                "file": "osm_targeted/gaps.json",
                "sha256": R.sha256_bytes(osm["osm_targeted/gaps.json"]),
                "timestamp_osm_base": "2026-10-31T13:14:07Z",
                "used_for": "evidence only",
            },  # fmt: skip
        ),
    }
    audit = {"status": status, "ran_utc": GEN, "outcome": outcome,
             "counts": {"pass": 5, "warn": 1, "fail": fails, "info": 0}, "findings": []}  # fmt: skip
    manifest = {
        "contract": "abot-dashboard",
        "contract_version": contract_version,
        "dataset": "manifest",
        "generated_utc": GEN,
        "data_quality": {"source_validation": {"audit": audit}},
        "files": [{"name": n, "sha256": R.sha256_bytes(b), "bytes": len(b)} for n, b in files.items()],
        "code": {
            "git_commit": commit,
            "git_working_tree_clean": clean,
            "git_dirty_count": 0 if clean else 2,
            "git_dirty_paths": [],
            "abot_version": "0.1.0",
        },  # fmt: skip
        "config_sha256": "c" * 64,
    }
    bundle = repo / R.BUNDLE_REL
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    for n, b in files.items():
        (bundle / n).write_bytes(b)
    (bundle / R.MANIFEST).write_bytes(jbytes(manifest))
    return bundle


def setup(tmp: Path, **bundle_kw) -> Path:
    repo = make_repo(tmp)
    make_bundle(repo, git(repo, "rev-parse", "HEAD"), **bundle_kw)
    (repo / "CHANGES.md").write_text("later code change\n", encoding="utf-8")
    commit_all(repo, "later code change")  # the release commit is a descendant of the source commit
    return repo


def pack(repo: Path, tag: str = TAG, **kw) -> P.Packed:
    kw.setdefault("check_bundle", lambda: 0)
    return P.pack(repo, tag, **kw)


def publish(repo: Path, tag: str = TAG) -> str:
    """What the maintainer does after packaging: commit the record, then tag that commit."""
    commit_all(repo, f"Release record {tag}")
    git(repo, "tag", "-a", tag, "-m", f"ABOT {tag}")
    return git(repo, "rev-parse", f"{tag}^{{commit}}")


@pytest.fixture
def released(tmp_path) -> tuple[Path, P.Packed]:
    repo = setup(tmp_path)
    packed = pack(repo, with_osm=True)
    publish(repo)
    return repo, packed


def dash(packed: P.Packed) -> Path:
    return packed.out_dir / R.dashboard_asset_name(TAG)


def problems(excinfo: pytest.ExceptionInfo) -> str:
    return " | ".join(excinfo.value.problems)


def raw_zip(path: Path, entries: list[tuple[str | zipfile.ZipInfo, bytes]]) -> None:
    """A ZIP written without any safety rule, for malicious archives."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # duplicate names
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in entries:
                if isinstance(name, str) and "\\" in name:
                    zi = zipfile.ZipInfo("placeholder")
                    zi.filename = name  # ZipInfo() turns os.sep into "/" on Windows; keep the backslash
                    name = zi
                zf.writestr(name, data)


def forge(
    repo: Path,
    *,
    mutate: Callable[[dict[str, bytes]], object] | None = None,
    mutate_record: Callable[[dict], None] | None = None,
    raw_entries: list[tuple[str | zipfile.ZipInfo, bytes]] | None = None,
    tag: str = TAG,
) -> Path:
    """Publish a release whose archive is tampered with but whose record matches it at asset level."""
    bundle = repo / R.BUNDLE_REL
    mbytes = (bundle / R.MANIFEST).read_bytes()
    manifest = json.loads(mbytes)
    head = git(repo, "rev-parse", "HEAD")
    entries = {n: (bundle / n).read_bytes() for n in R.manifest_files(manifest)}
    provenance = json.loads(entries[R.PROVENANCE])
    entries |= {R.MANIFEST: mbytes, **P.licence_entries(repo, head)}
    if mutate:
        mutate(entries)
    out = repo / "dist" / "forged"
    out.mkdir(parents=True, exist_ok=True)
    path = out / R.dashboard_asset_name(tag)
    path.unlink(missing_ok=True)
    pairs = [(n, entries[n]) for n in sorted(entries)] + (raw_entries or [])
    raw_zip(path, pairs)
    archive = path.read_bytes()
    asset = {
        "name": path.name,
        "kind": R.KIND_DASHBOARD,
        "bytes": len(archive),
        "sha256": R.sha256_bytes(archive),
        "contents": [
            {
                "name": (n.filename if isinstance(n, zipfile.ZipInfo) else n),
                "bytes": len(b),
                "sha256": R.sha256_bytes(b),
            }
            for n, b in pairs
        ],
    }
    record = P.build_record(tag, head, manifest, mbytes, provenance, [asset])
    if mutate_record:
        mutate_record(record)
    (repo / R.record_relpath(tag)).parent.mkdir(exist_ok=True)
    (repo / R.record_relpath(tag)).write_bytes(R.dumps_record(record))
    publish(repo, tag)
    return path


def tree_hashes(d: Path) -> dict[str, str]:
    return {p.relative_to(d).as_posix(): R.sha256_file(p) for p in sorted(d.rglob("*")) if p.is_file()}


# --- tags ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tag", ["1.0.0", "v1.0", "v01.0.0", "v1.0.0-rc.1", "v1.0.0/../x", "V1.0.0", "", "v1.0.0\n"]
)
def test_invalid_release_tag_is_rejected_everywhere(tmp_path, tag):
    with pytest.raises(R.ReleaseError, match="invalid release tag"):
        R.parse_tag(tag)
    repo = setup(tmp_path)
    with pytest.raises(R.ReleaseError, match="invalid release tag"):
        pack(repo, tag)
    with pytest.raises(R.ReleaseError, match="invalid release tag"):
        V.verify(repo, tag, tmp_path / "x.zip")
    d = E.evaluate(repo, tag)
    assert not d.eligible and d.checks[0][:2] == ("valid_tag", E.FAIL)


def test_valid_tags():
    assert R.parse_tag("v0.1.0") == (0, 1, 0)
    assert R.parse_tag("v10.20.30") == (10, 20, 30)


# --- packaging ----------------------------------------------------------------------------------


def test_pack_writes_assets_record_and_checksums(tmp_path):
    repo = setup(tmp_path)
    r = pack(repo, with_osm=True)
    rec = json.loads((repo / R.record_relpath(TAG)).read_bytes())
    assert rec["schema"] == R.RECORD_SCHEMA and rec["tag"] == TAG
    assert rec["packaged_from_commit"] == git(repo, "rev-parse", "HEAD")
    assert rec["source"]["git_commit"] == git(repo, "rev-parse", "HEAD~1")
    assert [a["kind"] for a in rec["assets"]] == [R.KIND_DASHBOARD, R.KIND_OSM]
    names = {c["name"] for c in rec["assets"][0]["contents"]}
    assert names == {
        "manifest.json",
        "city.json",
        "cells-001.geojson",
        "provenance.json",
        "LICENSE-DATA.md",
        "ATTRIBUTION.md",
    }
    osm_names = {c["name"] for c in rec["assets"][1]["contents"]}
    assert osm_names == {"osm_cache/aaaa.json", "osm_targeted/gaps.json", "LICENSE-DATA.md", "ATTRIBUTION.md"}
    sums = (r.out_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums == sorted(f"{a['sha256']}  {a['name']}" for a in rec["assets"])
    for a in rec["assets"]:
        assert R.sha256_file(r.out_dir / a["name"]) == a["sha256"]
    assert rec["licences"]["dataset"]["id"] == "ODbL-1.0"


def test_archive_is_deterministic_and_machine_independent(tmp_path):
    repo = setup(tmp_path)
    first = pack(repo, with_osm=True, out_dir=tmp_path / "out1")
    rec1 = (repo / R.record_relpath(TAG)).read_bytes()
    (repo / R.record_relpath(TAG)).unlink()
    pack(repo, with_osm=True, out_dir=tmp_path / "out2")
    rec2 = (repo / R.record_relpath(TAG)).read_bytes()
    # A clone at another path, packaged later, gives byte-identical output.
    clone = tmp_path / "elsewhere" / "clone"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True)
    shutil.copytree(repo / "data", clone / "data")
    third = pack(clone, with_osm=True)
    rec3 = (clone / R.record_relpath(TAG)).read_bytes()
    assert rec1 == rec2 == rec3
    for name in [*(a["name"] for a in first.record["assets"]), "SHA256SUMS"]:
        assert (tmp_path / "out1" / name).read_bytes() == (tmp_path / "out2" / name).read_bytes()
        assert (tmp_path / "out1" / name).read_bytes() == (third.out_dir / name).read_bytes()
    with zipfile.ZipFile(dash(first)) as zf:
        infos = zf.infolist()
    assert [i.filename for i in infos] == sorted(i.filename for i in infos)
    for i in infos:
        assert i.date_time == (1980, 1, 1, 0, 0, 0)
        assert i.external_attr >> 16 == stat.S_IFREG | 0o644 and i.create_system == 3
        assert i.compress_type == zipfile.ZIP_STORED and i.extra == b"" and i.comment == b""
    for blob in (rec1, dash(first).read_bytes()):
        assert str(tmp_path).encode() not in blob and b"\\Users" not in blob


def test_pack_reads_but_never_modifies_the_bundle(tmp_path):
    repo = setup(tmp_path)
    before = tree_hashes(repo / "data")
    pack(repo, with_osm=True)
    assert tree_hashes(repo / "data") == before


def test_licence_documents_come_from_git_not_the_working_tree(tmp_path):
    """A CRLF checkout (core.autocrlf on Windows) must not change the archive bytes."""
    repo = setup(tmp_path)
    (repo / "LICENSE-DATA.md").write_bytes(b"# ABOT dataset licence\r\nODbL 1.0\r\n")
    assert R.dirty_paths(repo) == []  # same content after normalisation
    r = pack(repo)
    with zipfile.ZipFile(dash(r)) as zf:
        assert zf.read("LICENSE-DATA.md") == b"# ABOT dataset licence\nODbL 1.0\n"


def refused(repo: Path, **kw) -> str:
    with pytest.raises(R.ReleaseError) as ei:
        pack(repo, **kw)
    assert not (repo / R.record_relpath(TAG)).exists(), "a refused pack must not write the record"
    assert not (repo / "dist" / "release" / TAG).exists(), "a refused pack must not write assets"
    return problems(ei)


def test_stale_bundle_is_refused(tmp_path):
    repo = setup(tmp_path)
    assert "export-dashboard --check failed (exit 1)" in refused(repo, check_bundle=lambda: 1)


def test_edited_bundle_file_is_refused(tmp_path):
    repo = setup(tmp_path)
    (repo / R.BUNDLE_REL / "city.json").write_bytes(b'{"edited":true}')
    assert "bundle file edited" in refused(repo)


def test_extra_file_in_bundle_is_refused(tmp_path):
    repo = setup(tmp_path)
    (repo / R.BUNDLE_REL / "notes.txt").write_text("x", encoding="utf-8")
    assert "unexpected file notes.txt" in refused(repo)


def test_missing_bundle_file_is_refused(tmp_path):
    repo = setup(tmp_path)
    (repo / R.BUNDLE_REL / "cells-001.geojson").unlink()
    assert "bundle file missing: cells-001.geojson" in refused(repo)


def test_missing_manifest_is_refused(tmp_path):
    repo = setup(tmp_path)
    (repo / R.BUNDLE_REL / R.MANIFEST).unlink()
    assert "no dashboard bundle" in refused(repo)


def test_dirty_working_tree_is_refused(tmp_path):
    repo = setup(tmp_path)
    (repo / "notes.txt").write_text("untracked", encoding="utf-8")
    assert "working tree is dirty" in refused(repo)
    (repo / "notes.txt").unlink()
    (repo / "LICENSE").write_text("changed\n", encoding="utf-8")
    assert "working tree is dirty" in refused(repo)


def test_manifest_reporting_unclean_export_tree_is_refused(tmp_path):
    repo = setup(tmp_path, clean=False)
    assert "unclean Git working tree" in refused(repo)


@pytest.mark.parametrize(
    "kw,msg",
    [
        ({"outcome": "fail", "fails": 2}, "audit outcome is 'fail'"),
        ({"status": "not_run", "outcome": "not_run"}, "audit status is 'not_run'"),
        ({"fails": 1}, "audit fail count is 1"),
    ],
)
def test_failed_or_missing_audit_is_refused(tmp_path, kw, msg):
    repo = setup(tmp_path, **kw)
    assert msg in refused(repo)


@pytest.mark.parametrize(
    "version,msg", [("2.0.0", "another major version"), ("1.2.0", "newer than the supported")]
)
def test_unsupported_contract_version_is_refused(tmp_path, version, msg):
    repo = setup(tmp_path, contract_version=version)
    assert msg in refused(repo)


def test_older_minor_and_other_patch_are_compatible():
    assert R.contract_problems("abot-dashboard", "1.0.0", "1.1.0") == []
    assert R.contract_problems("abot-dashboard", "1.1.7", "1.1.0") == []
    assert R.contract_problems("other", "1.1.0", "1.1.0")


def test_existing_tag_or_record_is_refused(tmp_path):
    repo = setup(tmp_path)
    git(repo, "tag", TAG)
    assert f"tag {TAG} already exists" in refused(repo)


def test_source_commit_not_an_ancestor_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    side = commit_all(repo, "side branch")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-q", "-D", "side")  # still reachable by id until gc
    make_bundle(repo, side)
    assert "is not an ancestor of HEAD" in refused(repo)


def test_unknown_source_commit_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    make_bundle(repo, "0123456789abcdef0123456789abcdef01234567")
    assert "is not in this repository" in refused(repo)


def test_osm_snapshot_must_match_provenance(tmp_path):
    repo = setup(tmp_path)
    (repo / R.RAW_REL / "osm_cache/aaaa.json").write_bytes(b'{"elements":["changed"]}')
    assert "differs from the bundle's provenance" in refused(repo, with_osm=True)
    (repo / R.RAW_REL / "osm_cache/aaaa.json").unlink()
    assert "OSM snapshot file missing" in refused(repo, with_osm=True)


def test_pack_cli_exit_codes(tmp_path, capsys):
    repo = setup(tmp_path)
    (repo / "notes.txt").write_text("x", encoding="utf-8")
    assert P.main([TAG, "--repo", str(repo)]) == 1
    assert "REFUSED" in capsys.readouterr().err


# --- verification -------------------------------------------------------------------------------


def test_verify_accepts_a_genuine_release(released):
    repo, packed = released
    v = V.verify(repo, TAG, dash(packed), packed.out_dir / R.osm_asset_name(TAG))
    assert v.manifest["contract_version"] == "1.1.0"
    assert V.main([TAG, str(dash(packed)), "--repo", str(repo)]) == 0


def verify_fails(repo: Path, archive: Path, **kw) -> str:
    with pytest.raises(R.ReleaseError) as ei:
        V.verify(repo, TAG, archive, **kw)
    return problems(ei)


def test_tampered_archive_is_rejected(released, tmp_path):
    repo, packed = released
    bad = tmp_path / "t" / dash(packed).name
    bad.parent.mkdir()
    b = bytearray(dash(packed).read_bytes())
    b[len(b) // 2] ^= 0xFF
    bad.write_bytes(bytes(b))
    assert "SHA-256 differs from the release record" in verify_fails(repo, bad)
    assert V.main([TAG, str(bad), "--repo", str(repo)]) == 1


def test_truncated_or_renamed_archive_is_rejected(released, tmp_path):
    repo, packed = released
    d = tmp_path / "t"
    d.mkdir()
    (d / dash(packed).name).write_bytes(dash(packed).read_bytes()[:-10])
    assert "bytes, release record says" in verify_fails(repo, d / dash(packed).name)
    shutil.copy(dash(packed), d / "renamed.zip")
    assert "is not the recorded asset name" in verify_fails(repo, d / "renamed.zip")


def test_record_is_read_from_the_tag_not_the_working_tree(released, tmp_path):
    """Rewriting the record in the working tree (or shipping one with the assets) changes nothing."""
    repo, packed = released
    forged = tmp_path / "f" / dash(packed).name
    forged.parent.mkdir()
    raw_zip(forged, [("manifest.json", b"{}")])
    rec = json.loads((repo / R.record_relpath(TAG)).read_bytes())
    rec["assets"][0].update(bytes=forged.stat().st_size, sha256=R.sha256_file(forged))
    (repo / R.record_relpath(TAG)).write_bytes(R.dumps_record(rec))
    assert "release record says" in verify_fails(repo, forged)


def test_tampered_osm_snapshot_is_rejected(released, tmp_path):
    repo, packed = released
    bad = tmp_path / "o" / R.osm_asset_name(TAG)
    bad.parent.mkdir()
    shutil.copy(packed.out_dir / R.osm_asset_name(TAG), bad)
    with bad.open("r+b") as f:
        f.seek(40)
        f.write(b"X")
    assert "differs from the release record" in verify_fails(repo, dash(packed), osm_archive=bad)


def test_tampered_manifest_is_rejected(tmp_path):
    repo = setup(tmp_path)

    def edit(e):
        m = json.loads(e[R.MANIFEST])
        m["generated_utc"] = "2027-01-01T00:00:00+00:00"
        e[R.MANIFEST] = jbytes(m)

    assert "manifest.json SHA-256 differs from the release record" in verify_fails(
        repo, forge(repo, mutate=edit)
    )


def test_tampered_data_file_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate=lambda e: e.update({"city.json": e["city.json"].replace(b"1000", b"9999")}))
    assert "city.json: SHA-256 differs from the manifest" in verify_fails(repo, archive)


def test_incorrect_byte_size_is_rejected(tmp_path):
    repo = setup(tmp_path)
    holder: dict[str, bytes] = {}

    def edit(e):
        m = json.loads(e[R.MANIFEST])
        m["files"][0]["bytes"] += 1  # city.json
        e[R.MANIFEST] = holder["m"] = jbytes(m)

    def consistent(rec):  # even a record that agrees with the edited manifest does not help
        rec["dashboard"].update(manifest_sha256=R.sha256_bytes(holder["m"]), manifest_bytes=len(holder["m"]))

    out = verify_fails(repo, forge(repo, mutate=edit, mutate_record=consistent))
    assert "city.json:" in out and "bytes, manifest says" in out


def test_missing_required_file_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate=lambda e: e.pop("cells-001.geojson"))
    assert "manifest-listed file cells-001.geojson missing" in verify_fails(repo, archive)


def test_missing_manifest_in_archive_is_rejected(tmp_path):
    repo = setup(tmp_path)
    assert "manifest.json missing from the archive" in verify_fails(
        repo, forge(repo, mutate=lambda e: e.pop(R.MANIFEST))
    )


def test_missing_licence_document_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate=lambda e: e.pop("LICENSE-DATA.md"))
    assert "licence document LICENSE-DATA.md missing" in verify_fails(repo, archive)


def test_unexpected_file_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate=lambda e: e.update({"extra.js": b"alert(1)"}))
    assert "unexpected file extra.js" in verify_fails(repo, archive)


def test_unexpected_nested_path_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate=lambda e: e.update({"sub/city.json": e["city.json"]}))
    assert "unexpected file sub/city.json" in verify_fails(repo, archive)


@pytest.mark.parametrize(
    "name,why",
    [
        ("../evil.json", "path traversal"),
        ("/etc/evil.json", "absolute path"),
        ("C:/evil.json", "absolute path"),
    ],
)
def test_malicious_names_are_rejected_even_if_the_record_lists_them(tmp_path, name, why):
    repo = setup(tmp_path)
    archive = forge(repo, raw_entries=[(name, b"x")])
    assert f"entry {name!r}: {why}" in verify_fails(repo, archive)


def test_symlink_entry_is_rejected_even_if_the_record_lists_it(tmp_path):
    repo = setup(tmp_path)
    link = zipfile.ZipInfo("link.json")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive = forge(repo, raw_entries=[(link, b"/etc/passwd")])
    assert "symbolic link" in verify_fails(repo, archive)


@pytest.mark.parametrize(
    "version,msg", [("2.0.0", "another major version"), ("1.2.0", "newer than the supported")]
)
def test_unsupported_contract_version_is_rejected(tmp_path, version, msg):
    repo = setup(tmp_path, contract_version=version)
    assert msg in verify_fails(repo, forge(repo))


def test_failed_audit_in_archive_is_rejected(tmp_path):
    repo = setup(tmp_path, outcome="fail", fails=1)
    out = verify_fails(repo, forge(repo))
    assert "audit outcome is 'fail'" in out and "audit fail count is 1" in out


@pytest.mark.parametrize(
    "mutate_record,block",
    [
        (lambda r: r["audit"].update(outcome="pass"), "audit"),
        (lambda r: r["source"].update(abot_version="9.9.9"), "source"),
        (lambda r: r["dashboard"].update(generated_utc="2030-01-01T00:00:00+00:00"), "dashboard"),
        (lambda r: r["osm"]["responses"][0].update(sha256="f" * 64), "osm"),
        (lambda r: r["licences"]["dataset"].update(id="CC0-1.0"), "licences"),
    ],
)
def test_record_metadata_inconsistent_with_manifest_is_rejected(tmp_path, mutate_record, block):
    repo = setup(tmp_path)
    archive = forge(repo, mutate_record=mutate_record)
    assert f"record {block} block disagrees" in verify_fails(repo, archive)


def test_envelope_metadata_tampering_is_rejected(tmp_path):
    """A data file whose envelope disagrees with the manifest is caught even if the manifest's hash
    for it was updated (a buggy or malicious exporter)."""
    repo = setup(tmp_path)
    bundle = repo / R.BUNDLE_REL
    city = json.loads((bundle / "city.json").read_bytes())
    city["contract_version"] = "1.0.0"
    new = jbytes(city)
    (bundle / "city.json").write_bytes(new)
    m = json.loads((bundle / R.MANIFEST).read_bytes())
    m["files"][0].update(sha256=R.sha256_bytes(new), bytes=len(new))
    (bundle / R.MANIFEST).write_bytes(jbytes(m))
    assert "city.json: contract_version '1.0.0' differs" in verify_fails(repo, forge(repo))


def test_missing_release_record_is_rejected(tmp_path):
    repo = setup(tmp_path)
    git(repo, "tag", TAG)
    assert "no release record" in verify_fails(repo, tmp_path / "x.zip")
    with pytest.raises(R.ReleaseError, match="does not exist"):
        V.verify(repo, "v9.9.9", tmp_path / "x.zip")


def test_record_for_another_tag_is_rejected(tmp_path):
    repo = setup(tmp_path)
    archive = forge(repo, mutate_record=lambda r: r.update(tag="v0.9.0"))
    assert "record tag 'v0.9.0' does not match" in verify_fails(repo, archive)


def test_source_commit_not_an_ancestor_of_the_tag_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    side = commit_all(repo, "side branch")
    git(repo, "checkout", "-q", "main")
    make_bundle(repo, side)
    assert f"source commit {side[:12]} is not an ancestor" in verify_fails(repo, forge(repo))


def test_packaged_commit_not_an_ancestor_of_the_tag_is_rejected(tmp_path):
    repo = setup(tmp_path)
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    side = commit_all(repo, "side branch")
    git(repo, "checkout", "-q", "main")
    archive = forge(repo, mutate_record=lambda r: r.update(packaged_from_commit=side))
    assert "packaged_from_commit" in verify_fails(repo, archive)


# --- safe archive reading (unit level) ----------------------------------------------------------


def expected_for(entries: dict[str, bytes]) -> dict[str, tuple[int, str]]:
    return {n: (len(b), R.sha256_bytes(b)) for n, b in entries.items()}


def read_fails(tmp_path: Path, entries, expected) -> str:
    p = tmp_path / "a.zip"
    raw_zip(p, entries)
    with pytest.raises(R.ReleaseError) as ei:
        R.read_archive(p, expected)
    return problems(ei)


@pytest.mark.parametrize(
    "name,why",
    [
        ("../x.json", "path traversal"),
        ("a/../../x.json", "path traversal"),
        ("./x.json", "path traversal"),
        ("/x.json", "absolute path"),
        ("D:/x.json", "absolute path"),
        ("a\\x.json", "backslash"),
        ("dir/", "directory entry"),
        ("a//x.json", "empty path segment"),
    ],
)
def test_unsafe_entry_names(tmp_path, name, why):
    assert why in read_fails(tmp_path, [(name, b"x")], {name: (1, R.sha256_bytes(b"x"))})


def test_duplicate_entries_are_rejected(tmp_path):
    out = read_fails(tmp_path, [("a.json", b"1"), ("a.json", b"1")], expected_for({"a.json": b"1"}))
    assert "duplicate archive entry" in out
    out = read_fails(
        tmp_path, [("a.json", b"1"), ("A.JSON", b"1")], expected_for({"a.json": b"1", "A.JSON": b"1"})
    )
    assert "duplicate archive entry" in out


def test_symlink_entry_is_rejected(tmp_path):
    link = zipfile.ZipInfo("a.json")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    assert "symbolic link" in read_fails(tmp_path, [(link, b"target")], expected_for({"a.json": b"target"}))


def test_oversized_entry_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "MAX_ENTRY_BYTES", 8)
    data = b"0123456789abcdef"
    assert "oversized" in read_fails(tmp_path, [("a.json", data)], expected_for({"a.json": data}))


def test_entry_size_and_content_mismatch(tmp_path):
    assert "4 bytes, expected 5" in read_fails(tmp_path, [("a.json", b"abcd")], {"a.json": (5, "0" * 64)})
    out = read_fails(tmp_path, [("a.json", b"abcd")], {"a.json": (4, R.sha256_bytes(b"abce"))})
    assert "SHA-256 differs" in out


def test_missing_and_unexpected_entries(tmp_path):
    out = read_fails(tmp_path, [("b.json", b"1"), ("n/b.json", b"1")], expected_for({"a.json": b"1"}))
    assert "missing entry 'a.json'" in out and "unexpected file" in out and "unexpected nested path" in out


def test_not_a_zip(tmp_path):
    p = tmp_path / "a.zip"
    p.write_bytes(b"not a zip")
    with pytest.raises(R.ReleaseError, match="not a readable ZIP"):
        R.read_archive(p, {})


def test_corrupt_entry_data_is_rejected(tmp_path):
    p = tmp_path / "a.zip"
    data = b"A" * 64
    R.write_zip(p, {"a.json": data})
    b = bytearray(p.read_bytes())
    i = b.index(data)
    b[i] = ord("B")  # same size, CRC no longer matches
    p.write_bytes(bytes(b))
    with pytest.raises(R.ReleaseError):
        R.read_archive(p, expected_for({"a.json": data}))


def test_write_zip_refuses_unsafe_names(tmp_path):
    with pytest.raises(R.ReleaseError, match="unsafe archive name"):
        R.write_zip(tmp_path / "a.zip", {"../x": b""})


# --- fetching and installing --------------------------------------------------------------------


def test_fetch_installs_only_the_bundle_files(released, tmp_path):
    repo, packed = released
    target = tmp_path / "site" / "v1"
    assert F.fetch(repo, TAG, archive=dash(packed), target=target, out=lambda _: None) == 0
    bundle = repo / R.BUNDLE_REL
    assert tree_hashes(target) == tree_hashes(bundle)  # nine files in the real case; no licence docs
    assert not list(target.parent.glob(".v1.*"))


def test_fetch_is_a_noop_when_the_release_is_installed(released, tmp_path):
    repo, packed = released
    msgs: list[str] = []
    assert F.fetch(repo, TAG, archive=dash(packed), out=msgs.append) == 0  # target: the repo's own bundle
    assert any("already installed" in m for m in msgs)


def test_invalid_archive_never_replaces_a_valid_bundle(released, tmp_path):
    repo, packed = released
    target = tmp_path / "site" / "v1"
    F.fetch(repo, TAG, archive=dash(packed), target=target, out=lambda _: None)
    before = tree_hashes(target)
    bad = tmp_path / "bad" / dash(packed).name
    bad.parent.mkdir()
    b = bytearray(dash(packed).read_bytes())
    b[-100] ^= 0xFF
    bad.write_bytes(bytes(b))
    with pytest.raises(R.ReleaseError):
        F.fetch(repo, TAG, archive=bad, target=target, replace=True, out=lambda _: None)
    assert tree_hashes(target) == before
    assert not list(target.parent.glob(".v1.*"))
    assert (
        F.main([TAG, "--repo", str(repo), "--archive", str(bad), "--target", str(target), "--replace"]) == 1
    )


def test_differing_bundle_needs_replace(released, tmp_path):
    repo, packed = released
    target = tmp_path / "site" / "v1"
    target.mkdir(parents=True)
    (target / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(R.ReleaseError, match="pass --replace"):
        F.fetch(repo, TAG, archive=dash(packed), target=target, out=lambda _: None)
    assert (target / "manifest.json").read_text(encoding="utf-8") == "{}"
    assert F.fetch(repo, TAG, archive=dash(packed), target=target, replace=True, out=lambda _: None) == 0
    assert tree_hashes(target) == tree_hashes(repo / R.BUNDLE_REL)


def test_verify_only_and_dry_run_write_nothing(released, tmp_path):
    repo, packed = released
    target = tmp_path / "site" / "v1"
    assert F.fetch(repo, TAG, archive=dash(packed), target=target, verify_only=True, out=lambda _: None) == 0

    def no_network(*_):
        raise AssertionError("dry run must not download")

    assert (
        F.fetch(repo, TAG, slug="o/r", target=target, dry_run=True, downloader=no_network, out=lambda _: None)
        == 0
    )
    assert not target.parent.exists()


def test_fetch_downloads_the_recorded_asset_name(released, tmp_path):
    repo, packed = released
    calls = []

    def fake(slug, tag, name, dest, max_bytes):
        calls.append((slug, tag, name, max_bytes))
        shutil.copy(dash(packed), dest)

    target = tmp_path / "site" / "v1"
    assert (
        F.fetch(repo, TAG, slug="didyouseejay/ABOT", target=target, downloader=fake, out=lambda _: None) == 0
    )
    assert calls == [("didyouseejay/ABOT", TAG, dash(packed).name, dash(packed).stat().st_size)]


def test_fetch_requires_the_tagged_record(tmp_path):
    repo = setup(tmp_path)
    with pytest.raises(R.ReleaseError, match="does not exist"):
        F.fetch(repo, TAG, slug="o/r", dry_run=True, out=lambda _: None)


# --- eligibility --------------------------------------------------------------------------------


def rel(tag: str, draft: bool = False, pre: bool = False) -> dict:
    return {"tagName": tag, "isDraft": draft, "isPrerelease": pre}


def status(d: E.Decision, check: str) -> str:
    return next(s for c, s, _ in d.checks if c == check)


def test_eligible_release_with_unknown_status_is_not_assumed(released):
    repo, _ = released
    d = E.evaluate(repo, TAG)
    assert d.eligible
    assert status(d, "not_draft") == E.SKIP and status(d, "not_prerelease") == E.SKIP
    assert status(d, "release_record") == E.PASS and status(d, "record_consistent") == E.PASS


def test_draft_and_prerelease_are_not_eligible(released):
    repo, _ = released
    assert not E.evaluate(repo, TAG, draft=True).eligible
    assert not E.evaluate(repo, TAG, prerelease=True).eligible
    assert not E.evaluate(repo, TAG, releases=[rel(TAG, draft=True)]).eligible
    assert not E.evaluate(repo, TAG, releases=[rel(TAG, pre=True)]).eligible
    assert E.evaluate(repo, TAG, draft=False, prerelease=False).eligible


def test_conflicting_status_inputs_fail(released):
    repo, _ = released
    d = E.evaluate(repo, TAG, releases=[rel(TAG, draft=True)], draft=False)
    assert not d.eligible and status(d, "not_draft") == E.FAIL


def test_latest_release_rule(released):
    repo, _ = released
    newer = [rel(TAG), rel("v1.1.0")]
    assert E.evaluate(repo, TAG, releases=[rel(TAG)], require_latest=True).eligible
    assert not E.evaluate(repo, TAG, releases=newer, require_latest=True).eligible
    assert E.evaluate(repo, TAG, releases=newer).eligible  # latest not requested
    # Drafts, prereleases and malformed tags do not count as published releases.
    others = [rel(TAG), rel("v2.0.0", pre=True), rel("v3.0.0", draft=True), rel("latest")]
    assert E.evaluate(repo, TAG, releases=others, require_latest=True).eligible
    # Not yet listed but higher than every published release.
    assert E.evaluate(repo, TAG, releases=[rel("v0.9.0")], require_latest=True).eligible


def test_rollback_must_be_explicit(released):
    repo, _ = released
    newer = [rel(TAG), rel("v1.1.0")]
    d = E.evaluate(repo, TAG, releases=newer, require_latest=True, allow_rollback=True)
    assert d.eligible and d.rollback
    assert not E.evaluate(repo, TAG, releases=newer, require_latest=True).rollback


def test_require_latest_needs_the_release_list(released):
    repo, _ = released
    d = E.evaluate(repo, TAG, require_latest=True)
    assert not d.eligible and status(d, "latest") == E.FAIL


def test_missing_tag_or_record_is_not_eligible(tmp_path):
    repo = setup(tmp_path)
    assert status(E.evaluate(repo, TAG), "tag_exists") == E.FAIL
    git(repo, "tag", TAG)
    d = E.evaluate(repo, TAG)
    assert not d.eligible and status(d, "release_record") == E.FAIL


def test_record_with_wrong_tag_is_not_eligible(tmp_path):
    repo = setup(tmp_path)
    forge(repo, mutate_record=lambda r: r.update(tag="v0.9.0"))
    d = E.evaluate(repo, TAG)
    assert not d.eligible and status(d, "record_consistent") == E.FAIL


def test_release_list_input_is_validated(tmp_path, released):
    repo, _ = released
    for bad in (
        {},
        [{"tagName": "v1.0.0"}],
        [rel(TAG), rel(TAG)],
        [{"tagName": 1, "isDraft": False, "isPrerelease": False}],
    ):
        with pytest.raises(E.InputError):
            E.parse_releases(bad)
    f = tmp_path / "releases.json"
    f.write_text(json.dumps([rel(TAG), rel("v1.1.0")]), encoding="utf-8")
    assert E.main([TAG, "--repo", str(repo), "--releases", str(f), "--require-latest"]) == 1
    assert (
        E.main([TAG, "--repo", str(repo), "--releases", str(f), "--require-latest", "--allow-rollback"]) == 0
    )
    f.write_text("{not json", encoding="utf-8")
    assert E.main([TAG, "--repo", str(repo), "--releases", str(f)]) == 2
