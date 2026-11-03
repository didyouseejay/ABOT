"""Package the current dashboard bundle as a release and write its release record.

    python scripts/release/pack_release.py v1.0.0
    python scripts/release/pack_release.py v1.0.0 --with-osm-snapshot

Run from a clean checkout of the commit to be released, before the tag exists. It writes:
- dist/release/<tag>/abot-dashboard-v1-<tag>.zip   (the nine bundle files and the licence documents)
- dist/release/<tag>/abot-osm-snapshot-<tag>.zip   (with --with-osm-snapshot)
- dist/release/<tag>/SHA256SUMS
- releases/<tag>.json                              (the release record: commit it, then tag that commit)

It only reads data/: nothing is exported, regenerated or modified. It refuses (exit 1, nothing
written) if the bundle is stale or edited, the audit failed or was not obtained, the bundle was
exported from an unclean tree, the working tree is dirty, the tag is invalid or already exists, or the
bundle's source commit is not an ancestor of HEAD. See releases/README.md.
"""

import argparse
import copy
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import release_lib as R
import verify_release as V


@dataclass
class Packed:
    record_path: Path
    out_dir: Path
    assets: list[Path]
    record: dict


def run_export_check(repo: Path, config: str | None = None) -> int:
    """`abot export-dashboard --check` in a subprocess (read-only; exit 0 means current)."""
    cmd = [sys.executable, "-c", "from abot.cli import main; main()"]
    cmd += ["--config", config] if config else []
    cmd += ["export-dashboard", "--check"]
    try:
        return subprocess.run(cmd, cwd=repo, check=False).returncode
    except OSError as e:
        print(f"could not run abot export-dashboard --check: {e}", file=sys.stderr)
        return 1


def bundle_problems(bundle: Path, manifest: dict) -> list[str]:
    """The installed bundle is exactly the manifest's files plus manifest.json, unedited."""
    listed = R.manifest_files(manifest)
    bad = []
    present = {}
    for p in sorted(bundle.iterdir()):
        if p.is_symlink() or not p.is_file():
            bad.append(f"bundle contains a non-regular entry {p.name}")
        elif p.name != R.MANIFEST and p.name not in listed:
            bad.append(f"bundle contains an unexpected file {p.name}")
        else:
            present[p.name] = p
    for name, (size, sha) in sorted(listed.items()):
        p = present.get(name)
        if p is None:
            bad.append(f"bundle file missing: {name}")
        elif p.stat().st_size != size or R.sha256_file(p) != sha:
            bad.append(f"bundle file edited (size or SHA-256 differs from the manifest): {name}")
    return bad


def licence_entries(repo: Path, commit: str) -> dict[str, bytes]:
    out, bad = {}, []
    for path, name in R.LICENCE_DOCS:
        b = R.show_file(repo, commit, path)
        if b is None:
            bad.append(f"{path} is not committed at {commit[:12]}")
        else:
            out[name] = b
    if bad:
        raise R.ReleaseError(bad)
    return out


def osm_entries(raw: Path, osm: dict) -> dict[str, bytes]:
    out, bad = {}, []
    files = R.osm_files(osm)
    if not osm["responses"]:
        bad.append("provenance.json lists no OSM responses")
    for rel, sha in sorted(files.items()):
        if R.entry_name_problem(rel):
            bad.append(f"provenance OSM path {rel!r} is unsafe")
            continue
        p = raw / rel
        if not p.is_file():
            bad.append(f"OSM snapshot file missing: {R.RAW_REL}/{rel}")
            continue
        b = p.read_bytes()
        if R.sha256_bytes(b) != sha:
            bad.append(f"OSM snapshot file differs from the bundle's provenance: {R.RAW_REL}/{rel}")
        out[rel] = b
    if bad:
        raise R.ReleaseError(bad)
    return out


def asset_entry(name: str, kind: str, archive: bytes, entries: dict[str, bytes]) -> dict:
    return {
        "name": name,
        "kind": kind,
        "bytes": len(archive),
        "sha256": R.sha256_bytes(archive),
        "contents": [
            {"name": n, "bytes": len(entries[n]), "sha256": R.sha256_bytes(entries[n])}
            for n in sorted(entries)
        ],
    }


def build_record(
    tag: str, packaged_from: str, manifest: dict, mbytes: bytes, provenance: dict, assets: list
) -> dict:
    return {
        "schema": R.RECORD_SCHEMA,
        "schema_version": R.RECORD_SCHEMA_VERSION,
        "tag": tag,
        "packaged_from_commit": packaged_from,
        "dashboard": R.dashboard_block(manifest, mbytes),
        "source": R.source_block(manifest),
        "audit": R.audit_block(manifest),
        "osm": R.osm_block(provenance),
        "licences": copy.deepcopy(R.LICENCES),
        "assets": assets,
    }


def sha256sums(assets: list[dict]) -> bytes:
    """`sha256sum -c` format: '<hash>  <name>' per line, sorted, LF."""
    return "".join(f"{a['sha256']}  {a['name']}\n" for a in sorted(assets, key=lambda a: a["name"])).encode()


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.zip"
        R.write_zip(p, entries)
        return p.read_bytes()


def pack(
    repo: Path,
    tag: str,
    *,
    bundle_dir: Path | None = None,
    raw_dir: Path | None = None,
    out_dir: Path | None = None,
    with_osm: bool = False,
    check_bundle: Callable[[], int] | None = None,
) -> Packed:
    repo = Path(repo).resolve()
    R.parse_tag(tag)
    bundle = Path(bundle_dir) if bundle_dir else repo / R.BUNDLE_REL
    raw = Path(raw_dir) if raw_dir else repo / R.RAW_REL
    out = Path(out_dir) if out_dir else repo / "dist" / "release" / tag
    record_path = repo / R.record_relpath(tag)

    bad: list[str] = []
    dirty = R.dirty_paths(repo)
    if dirty:
        bad.append(f"working tree is dirty ({len(dirty)} path(s), e.g. {dirty[:3]}); commit or remove them")
    if R.tag_commit(repo, tag):
        bad.append(f"tag {tag} already exists: the record must be committed before the tag is created")
    head = R.head_commit(repo)
    if record_path.exists() or R.show_file(repo, head, R.record_relpath(tag)) is not None:
        bad.append(f"{R.record_relpath(tag)} already exists")
    if out.exists() and any(out.iterdir()):
        bad.append(f"output directory {out} is not empty")
    mpath = bundle / R.MANIFEST
    if not mpath.is_file():
        raise R.ReleaseError([*bad, f"no dashboard bundle: {mpath} missing (run abot export-dashboard)"])
    mbytes = mpath.read_bytes()
    manifest = R.loads_json(mbytes, R.MANIFEST)

    rc = (check_bundle or (lambda: run_export_check(repo)))()
    if rc != 0:
        bad.append(f"abot export-dashboard --check failed (exit {rc}): the bundle is stale or missing")
    supported = R.supported_version(R.show_file(repo, head, R.VERSION_TS))
    bad += R.contract_problems(manifest.get("contract"), manifest.get("contract_version"), supported)
    mbad = R.manifest_problems(manifest)
    bad += mbad
    if mbad:
        raise R.ReleaseError(bad)
    bad += bundle_problems(bundle, manifest)
    src = manifest["code"]["git_commit"]
    if R.resolve_commit(repo, src) != src:
        bad.append(f"the bundle's source commit {src[:12]} is not in this repository")
    elif not R.is_ancestor(repo, src, head):
        bad.append(f"the bundle's source commit {src[:12]} is not an ancestor of HEAD ({head[:12]})")
    if bad:
        raise R.ReleaseError(bad)

    files = {n: (bundle / n).read_bytes() for n in R.manifest_files(manifest)}
    if R.sha256_bytes((bundle / R.MANIFEST).read_bytes()) != R.sha256_bytes(mbytes):
        raise R.ReleaseError("manifest.json changed while packaging")
    provenance = R.loads_json(files[R.PROVENANCE], R.PROVENANCE)
    licences = licence_entries(repo, head)
    dash_entries = {**files, R.MANIFEST: mbytes, **licences}
    dash_zip = zip_bytes(dash_entries)
    archives = {R.dashboard_asset_name(tag): dash_zip}
    assets = [asset_entry(R.dashboard_asset_name(tag), R.KIND_DASHBOARD, dash_zip, dash_entries)]
    if with_osm:
        osm_e = {**osm_entries(raw, R.osm_block(provenance)), **licences}
        osm_zip = zip_bytes(osm_e)
        archives[R.osm_asset_name(tag)] = osm_zip
        assets.append(asset_entry(R.osm_asset_name(tag), R.KIND_OSM, osm_zip, osm_e))
    record = build_record(tag, head, manifest, mbytes, provenance, assets)
    shape = R.record_shape_problems(record)
    if shape:
        raise R.ReleaseError(shape)

    # Self-check with the verifier's own content checks before anything is written.
    with tempfile.TemporaryDirectory() as td:
        for name, b in archives.items():
            (Path(td) / name).write_bytes(b)
        dasset = R.record_asset(record, R.KIND_DASHBOARD)
        assert dasset is not None
        dpath = Path(td) / dasset["name"]
        R.check_asset_file(dpath, dasset)
        V.check_dashboard_contents(record, R.read_archive(dpath, R.contents_map(dasset)), supported)
        oasset = R.record_asset(record, R.KIND_OSM)
        if oasset is not None:
            opath = Path(td) / oasset["name"]
            R.check_asset_file(opath, oasset)
            V.check_osm_contents(record, R.read_archive(opath, R.contents_map(oasset)))

    out.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for name, b in archives.items():
            (out / name).write_bytes(b)
            written.append(out / name)
        (out / "SHA256SUMS").write_bytes(sha256sums(assets))
        written.append(out / "SHA256SUMS")
        record_path.parent.mkdir(exist_ok=True)
        with record_path.open("xb") as f:
            f.write(R.dumps_record(record))
    except BaseException:
        for p in written:
            p.unlink(missing_ok=True)
        raise
    return Packed(record_path, out, written, record)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag", help="release tag to create, vMAJOR.MINOR.PATCH (must not exist yet)")
    p.add_argument("--with-osm-snapshot", action="store_true", help="also package the baseline OSM responses")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    p.add_argument("--bundle-dir", type=Path, help=f"bundle directory (default: <repo>/{R.BUNDLE_REL})")
    p.add_argument("--raw-dir", type=Path, help=f"raw data directory (default: <repo>/{R.RAW_REL})")
    p.add_argument("--out-dir", type=Path, help="output directory (default: <repo>/dist/release/<tag>)")
    p.add_argument("--config", help="settings.yaml passed to abot export-dashboard --check")
    a = p.parse_args(argv)
    repo = a.repo.resolve()
    try:
        r = pack(
            repo,
            a.tag,
            bundle_dir=a.bundle_dir,
            raw_dir=a.raw_dir,
            out_dir=a.out_dir,
            with_osm=a.with_osm_snapshot,
            check_bundle=lambda: run_export_check(repo, a.config),
        )
    except R.ReleaseError as e:
        print(
            f"pack_release: {a.tag}: REFUSED, nothing written; {len(e.problems)} problem(s):", file=sys.stderr
        )
        for m in e.problems:
            print(f"  X {m}", file=sys.stderr)
        return 1
    print(f"pack_release: {a.tag}: packaged")
    for asset in r.record["assets"]:
        print(f"  {asset['sha256']}  {asset['name']}  ({asset['bytes']:,} bytes)")
    print(f"  checksums  {r.out_dir / 'SHA256SUMS'}")
    print(f"  record     {R.record_relpath(a.tag)}")
    print("next: review and commit the record, tag that commit, then verify:")
    print(f"  git add {R.record_relpath(a.tag)} && git commit -m 'Release record {a.tag}'")
    print(f"  git tag -a {a.tag} -m 'ABOT {a.tag}'")
    print(f"  python scripts/release/verify_release.py {a.tag} {r.assets[0].as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
