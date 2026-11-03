"""Verify an ABOT release asset against the release record committed at its Git tag.

    python scripts/release/verify_release.py v1.0.0 dist/release/v1.0.0/abot-dashboard-v1-v1.0.0.zip
    python scripts/release/verify_release.py v1.0.0 <dashboard zip> --osm-archive <osm snapshot zip>

The expected values come from `releases/<tag>.json` in the Git object of the tag, never from a file
downloaded with the assets. Nothing is extracted to disk: the archive is checked in memory. Exit 0
only if every check passes; any problem, or any error while checking, exits 1 (fail closed).
See releases/README.md.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import release_lib as R


@dataclass
class Verified:
    record: dict
    tag_commit: str
    manifest: dict
    files: dict[str, bytes]  # every archive entry, by name, already checked


def _git_problems(repo: Path, rec: dict, tag: str, tag_commit: str) -> list[str]:
    bad = []
    src, packed = rec["source"].get("git_commit"), rec["packaged_from_commit"]
    if not isinstance(src, str) or R.resolve_commit(repo, src) != src:
        return [f"source commit {src!r} is not in this repository (a shallow clone needs the full history)"]
    if R.resolve_commit(repo, packed) != packed:
        return [f"packaged_from_commit {packed} is not in this repository"]
    if not R.is_ancestor(repo, src, packed):
        bad.append(f"source commit {src[:12]} is not an ancestor of packaged_from_commit {packed[:12]}")
    if not R.is_ancestor(repo, packed, tag_commit):
        bad.append(f"packaged_from_commit {packed[:12]} is not an ancestor of tag {tag}")
    if not R.is_ancestor(repo, src, tag_commit):
        bad.append(f"source commit {src[:12]} is not an ancestor of tag {tag}")
    return bad


def check_dashboard_contents(rec: dict, files: dict[str, bytes], supported: str) -> dict:
    """Checks that need the archive's content; returns the parsed manifest."""
    asset = R.record_asset(rec, R.KIND_DASHBOARD)
    assert asset is not None
    if R.MANIFEST not in files:
        raise R.ReleaseError(f"{R.MANIFEST} missing from the archive")
    mbytes = files[R.MANIFEST]
    bad = []
    if R.sha256_bytes(mbytes) != rec["dashboard"]["manifest_sha256"]:
        bad.append("manifest.json SHA-256 differs from the release record")
    if len(mbytes) != rec["dashboard"]["manifest_bytes"]:
        bad.append("manifest.json size differs from the release record")
    manifest = R.loads_json(mbytes, R.MANIFEST)
    bad += R.contract_problems(manifest.get("contract"), manifest.get("contract_version"), supported)
    bad += R.manifest_problems(manifest)
    if bad:
        raise R.ReleaseError(bad)

    listed = R.manifest_files(manifest)
    licence_names = {name for _, name in R.LICENCE_DOCS}
    expected_names = set(listed) | {R.MANIFEST} | licence_names
    got_names = set(files)
    bad += [f"manifest-listed file {n} missing from the archive" for n in sorted(set(listed) - got_names)]
    bad += [f"licence document {n} missing from the archive" for n in sorted(licence_names - got_names)]
    bad += [f"unexpected file {n} in the archive" for n in sorted(got_names - expected_names)]
    for name, (size, sha) in sorted(listed.items()):
        data = files.get(name)
        if data is None:
            continue
        if len(data) != size:
            bad.append(f"{name}: {len(data)} bytes, manifest says {size}")
        elif R.sha256_bytes(data) != sha:
            bad.append(f"{name}: SHA-256 differs from the manifest")
        if name.endswith((".json", ".geojson")):
            bad += R.envelope_problems(name, data, manifest)
    if bad:
        raise R.ReleaseError(bad)

    # Every metadata block the record copies must equal its source in the verified archive.
    provenance = R.loads_json(files[R.PROVENANCE], R.PROVENANCE)
    derived = {
        "dashboard": R.dashboard_block(manifest, mbytes),
        "source": R.source_block(manifest),
        "audit": R.audit_block(manifest),
        "osm": R.osm_block(provenance),
        "licences": R.LICENCES,
    }
    for key, want in derived.items():
        if rec[key] != want:
            diff = sorted(k for k in set(want) | set(rec[key]) if rec[key].get(k) != want.get(k))
            bad.append(f"record {key} block disagrees with the archive's metadata: {diff}")
    if bad:
        raise R.ReleaseError(bad)
    return manifest


def check_osm_contents(rec: dict, files: dict[str, bytes]) -> None:
    want = R.osm_files(rec["osm"])
    licence_names = {name for _, name in R.LICENCE_DOCS}
    bad = [f"OSM snapshot: {n} missing" for n in sorted(set(want) - set(files))]
    bad += [f"OSM snapshot: unexpected file {n}" for n in sorted(set(files) - set(want) - licence_names)]
    bad += [f"OSM snapshot: licence document {n} missing" for n in sorted(licence_names - set(files))]
    bad += [
        f"OSM snapshot: {n} SHA-256 differs from the provenance recorded in the bundle"
        for n, sha in sorted(want.items())
        if n in files and R.sha256_bytes(files[n]) != sha
    ]
    if bad:
        raise R.ReleaseError(bad)


def verify(repo: Path, tag: str, archive: Path, osm_archive: Path | None = None) -> Verified:
    """Every check from releases/README.md "Verification"; raises ReleaseError listing the problems."""
    repo = Path(repo)
    rec, commit = R.read_record_from_tag(repo, tag)
    supported = R.supported_version(R.show_file(repo, commit, R.VERSION_TS))
    bad = _git_problems(repo, rec, tag, commit)
    if bad:
        raise R.ReleaseError(bad)

    asset = R.record_asset(rec, R.KIND_DASHBOARD)
    assert asset is not None
    if asset["name"] != R.dashboard_asset_name(tag):
        raise R.ReleaseError(f"record asset name {asset['name']!r} is not {R.dashboard_asset_name(tag)!r}")
    R.check_asset_file(Path(archive), asset)
    files = R.read_archive(Path(archive), R.contents_map(asset))
    manifest = check_dashboard_contents(rec, files, supported)

    if osm_archive is not None:
        osm_asset = R.record_asset(rec, R.KIND_OSM)
        if osm_asset is None:
            raise R.ReleaseError(f"release {tag} has no {R.KIND_OSM} asset in its record")
        R.check_asset_file(Path(osm_archive), osm_asset)
        osm = R.read_archive(Path(osm_archive), R.contents_map(osm_asset))
        check_osm_contents(rec, osm)
        for _, name in R.LICENCE_DOCS:  # one set of licence texts per release
            if osm[name] != files[name]:
                raise R.ReleaseError(f"OSM snapshot {name} differs from the dashboard archive's")
    return Verified(rec, commit, manifest, files)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag", help="release tag, e.g. v1.0.0 (must exist in the local repository)")
    p.add_argument("archive", type=Path, help="the downloaded dashboard bundle ZIP")
    p.add_argument("--osm-archive", type=Path, help="also verify the OSM snapshot ZIP")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    a = p.parse_args(argv)
    try:
        v = verify(a.repo, a.tag, a.archive, a.osm_archive)
    except R.ReleaseError as e:
        print(f"verify_release: {a.tag}: FAILED, {len(e.problems)} problem(s):", file=sys.stderr)
        for m in e.problems:
            print(f"  X {m}", file=sys.stderr)
        return 1
    except Exception as e:  # fail closed on anything unforeseen
        print(f"verify_release: {a.tag}: FAILED (error while verifying: {e!r})", file=sys.stderr)
        return 1
    d, s, au = v.record["dashboard"], v.record["source"], v.record["audit"]
    print(f"verify_release: {a.tag}: OK")
    print(f"  record    {R.record_relpath(a.tag)} at tag commit {v.tag_commit[:12]}")
    print(f"  archive   {a.archive.name}  sha256 {R.sha256_file(a.archive)}")
    print(f"  contract  {d['contract']} {d['contract_version']}, generated {d['generated_utc']}")
    print(f"  source    {s['git_commit'][:12]} (clean), ancestor of {a.tag}")
    print(f"  audit     {au['status']} / {au['outcome']} {au['counts']}")
    print(f"  files     {len(v.files)} entries, every SHA-256 and size matches")
    if a.osm_archive:
        print(f"  osm       {a.osm_archive.name} matches the record and the bundle's provenance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
