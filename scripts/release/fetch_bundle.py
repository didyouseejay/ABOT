"""Download an ABOT release's dashboard bundle, verify it, and install it.

    python scripts/release/fetch_bundle.py v1.0.0                 # download, verify, install
    python scripts/release/fetch_bundle.py v1.0.0 --verify-only   # download and verify; install nothing
    python scripts/release/fetch_bundle.py v1.0.0 --dry-run       # show the plan; no network, no writes
    python scripts/release/fetch_bundle.py v1.0.0 --archive <zip> # verify and install a local copy

Prerequisites: git, and the tag in the local repository (`git fetch --tags`; a shallow clone also needs
the history back to the bundle's source commit). Downloads use the GitHub CLI (`gh`) when it is
installed and fall back to a plain HTTPS download of the public release asset otherwise.

The asset name, size and SHA-256 come from `releases/<tag>.json` in the tag's Git object. The archive
is fully verified (scripts/release/verify_release.py) before anything is written. The install goes to
a temporary sibling directory and is swapped in with two renames, so an existing bundle is never
replaced by an invalid one. An existing bundle that differs from the release is only replaced with
--replace. See releases/README.md.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path

import release_lib as R
import verify_release as V

Downloader = Callable[[str, str, str, Path, int], None]  # slug, tag, asset name, destination, max bytes


def download_https(slug: str, tag: str, name: str, dest: Path, max_bytes: int) -> None:
    url = f"https://github.com/{slug}/releases/download/{tag}/{name}"
    req = urllib.request.Request(url, headers={"User-Agent": "abot-fetch-bundle"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, dest.open("xb") as f:  # noqa: S310 (fixed https URL)
            total = 0
            while chunk := resp.read(1 << 20):
                total += len(chunk)
                if total > max_bytes:
                    raise R.ReleaseError(f"download of {name} exceeds the recorded size ({max_bytes} bytes)")
                f.write(chunk)
    except OSError as e:
        raise R.ReleaseError(f"download failed: {url}: {e}") from e


def download_gh(slug: str, tag: str, name: str, dest: Path, max_bytes: int) -> None:
    cmd = ["gh", "release", "download", tag, "--repo", slug, "--pattern", name, "--dir", str(dest.parent)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise R.ReleaseError(f"gh release download failed: {r.stderr.strip()}")
    if not dest.is_file():
        raise R.ReleaseError(f"gh release download did not produce {name}")
    if dest.stat().st_size > max_bytes:
        raise R.ReleaseError(f"downloaded {name} exceeds the recorded size ({max_bytes} bytes)")


def default_downloader() -> Downloader:
    return download_gh if shutil.which("gh") else download_https


def installed_manifest_sha(target: Path) -> str | None:
    """SHA-256 of the installed manifest if the installed bundle is complete and unedited."""
    mp = target / R.MANIFEST
    try:
        mbytes = mp.read_bytes()
        files = R.manifest_files(R.loads_json(mbytes, R.MANIFEST))
        ok = all(
            (target / n).is_file()
            and (target / n).stat().st_size == size
            and R.sha256_file(target / n) == sha
            for n, (size, sha) in files.items()
        )
    except (OSError, R.ReleaseError, KeyError, TypeError):
        return None
    return R.sha256_bytes(mbytes) if ok else None


def install(files: dict[str, bytes], target: Path) -> None:
    """Write the verified files next to `target`, re-check them on disk, then swap directories.

    Uses the exporter's temporary names (.v1.tmp-<hex>, .v1.old-<hex>), so `abot export-dashboard`
    recovers a crashed install the same way it recovers a crashed export."""
    root = target.parent
    root.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex[:12]
    tmp, old = root / f".{target.name}.tmp-{suffix}", root / f".{target.name}.old-{suffix}"
    tmp.mkdir()
    try:
        for name, data in sorted(files.items()):
            if not R.safe_flat_name(name):
                raise R.ReleaseError(f"refusing to install unsafe name {name!r}")
            with (tmp / name).open("xb") as f:
                f.write(data)
        for name, data in files.items():
            if R.sha256_file(tmp / name) != R.sha256_bytes(data):
                raise R.ReleaseError(f"{name}: written file differs from the verified content")
        if target.exists():
            target.rename(old)
        try:
            tmp.rename(target)
        except OSError:
            if old.exists():
                old.rename(target)
            raise
    except BaseException:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise
    if old.exists():
        shutil.rmtree(old)


def fetch(
    repo: Path,
    tag: str,
    *,
    slug: str | None = None,
    archive: Path | None = None,
    verify_only: bool = False,
    dry_run: bool = False,
    replace: bool = False,
    target: Path | None = None,
    downloader: Downloader | None = None,
    out: Callable[[str], None] = print,
) -> int:
    repo = Path(repo).resolve()
    target = Path(target) if target else repo / R.BUNDLE_REL
    rec, commit = R.read_record_from_tag(repo, tag)
    asset = R.record_asset(rec, R.KIND_DASHBOARD)
    assert asset is not None
    slug = slug or R.github_slug(repo)
    if archive is None and slug is None:
        raise R.ReleaseError(
            "cannot tell the GitHub repository from the origin remote; pass --repo-slug owner/name"
        )
    out(f"release {tag}: record {R.record_relpath(tag)} at {commit[:12]}")
    out(f"  asset   {asset['name']}  {asset['bytes']:,} bytes  sha256 {asset['sha256']}")
    out(f"  source  {'local file ' + str(archive) if archive else f'github.com/{slug} release {tag}'}")
    out(f"  target  {target}" + ("  (not written: --verify-only)" if verify_only else ""))
    if dry_run:
        out("dry run: nothing downloaded, verified or written")
        return 0

    with tempfile.TemporaryDirectory(prefix="abot-fetch-") as td:
        dest = Path(td) / asset["name"]
        if archive is not None:
            shutil.copyfile(archive, dest)
        else:
            (downloader or default_downloader())(slug or "", tag, asset["name"], dest, asset["bytes"])
        v = V.verify(repo, tag, dest)
    out(f"verified: {len(v.files)} entries match the release record and the manifest")
    if verify_only:
        return 0

    bundle = {n: v.files[n] for n in [*R.manifest_files(v.manifest), R.MANIFEST]}
    current = installed_manifest_sha(target) if target.exists() else None
    if current == rec["dashboard"]["manifest_sha256"]:
        out(f"already installed: {target} is this release's bundle; nothing changed")
        return 0
    if target.exists() and not replace:
        state = "a different complete bundle" if current else "an incomplete or edited bundle"
        raise R.ReleaseError(f"{target} holds {state}; pass --replace to install {tag} over it")
    install(bundle, target)
    out(f"installed {len(bundle)} files into {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag", help="release tag, e.g. v1.0.0 (must exist in the local repository)")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    p.add_argument("--repo-slug", help="GitHub owner/name (default: from the origin remote)")
    p.add_argument("--archive", type=Path, help="use this local ZIP instead of downloading")
    p.add_argument("--target", type=Path, help=f"install directory (default: <repo>/{R.BUNDLE_REL})")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true", help="download and verify; install nothing")
    mode.add_argument("--dry-run", action="store_true", help="print the plan; no network, no writes")
    p.add_argument("--replace", action="store_true", help="replace an existing bundle that differs")
    a = p.parse_args(argv)
    try:
        return fetch(
            a.repo,
            a.tag,
            slug=a.repo_slug,
            archive=a.archive,
            verify_only=a.verify_only,
            dry_run=a.dry_run,
            replace=a.replace,
            target=a.target,
        )
    except R.ReleaseError as e:
        print(
            f"fetch_bundle: {a.tag}: FAILED, nothing installed; {len(e.problems)} problem(s):",
            file=sys.stderr,
        )
        for m in e.problems:
            print(f"  X {m}", file=sys.stderr)
        return 1
    except Exception as e:  # fail closed
        print(f"fetch_bundle: {a.tag}: FAILED, nothing installed ({e!r})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
