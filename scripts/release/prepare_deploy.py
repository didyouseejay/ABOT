"""Turn a verified dashboard build into a Vercel prebuilt deployment (Build Output API v3).

    python scripts/release/prepare_deploy.py v1.0.0 --dist dashboard/dist --out <dir>/.vercel/output

Run after `fetch_bundle.py <tag>` (which verified and installed the release bundle) and
`npm run build` (which copied it to dist/data/v1/). This script checks that the build carries exactly
the release's bundle: dist/data/v1/ holds manifest.json and the files it lists, nothing else, and the
manifest's SHA-256 is the one in `releases/<tag>.json` at the tag. It then copies dist/ to
<out>/static/ and writes <out>/config.json with the security and caching headers. The output is
deployed with `vercel deploy --prebuilt`, so Vercel serves these bytes and builds nothing itself.
See docs/DEPLOYMENT.md.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import release_lib as R

DATA_PREFIX = "data/v1"

# Content Security Policy for the static dashboard. Scripts, styles, fonts and data are same-origin.
# The only third-party request is the OpenStreetMap street-map tiles. Inline styles are allowed
# because Leaflet and React set element styles; inline scripts are not.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https://tile.openstreetmap.org",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def vercel_config() -> dict:
    """Build Output API v3 config. Header routes `continue` to the filesystem, which serves the files."""
    return {
        "version": 3,
        "routes": [
            {"src": "/assets/(.*)", "headers": {"Cache-Control": "public, max-age=31536000, immutable"}, "continue": True},
            {"src": f"/{DATA_PREFIX}/(.*)", "headers": {"Cache-Control": "public, max-age=0, must-revalidate"}, "continue": True},
            {"src": "/(.*)", "headers": SECURITY_HEADERS, "continue": True},
            {"handle": "filesystem"},
        ],
    }  # fmt: skip


def dist_problems(dist: Path, record: dict) -> list[str]:
    """The build is complete and its data is exactly the release's verified bundle."""
    bad: list[str] = []
    if not (dist / "index.html").is_file():
        bad.append(f"{dist}/index.html missing: run npm run build")
    for p in sorted(dist.rglob("*")):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            bad.append(f"non-regular entry in the build: {p.relative_to(dist).as_posix()}")
    data = dist / DATA_PREFIX
    mpath = data / R.MANIFEST
    if not mpath.is_file():
        return [
            *bad,
            f"{DATA_PREFIX}/{R.MANIFEST} missing: the build has no data (was the bundle installed?)",
        ]
    mbytes = mpath.read_bytes()
    if R.sha256_bytes(mbytes) != record["dashboard"]["manifest_sha256"]:
        return [*bad, f"{DATA_PREFIX}/{R.MANIFEST} is not the manifest of release {record['tag']}"]
    manifest = R.loads_json(mbytes, R.MANIFEST)
    listed = R.manifest_files(manifest)
    present = {p.name for p in data.iterdir()}
    bad += [
        f"{DATA_PREFIX}/ has an unexpected entry {n}" for n in sorted(present - set(listed) - {R.MANIFEST})
    ]
    for name, (size, sha) in sorted(listed.items()):
        p = data / name
        if not p.is_file():
            bad.append(f"{DATA_PREFIX}/{name} missing")
        elif p.stat().st_size != size or R.sha256_file(p) != sha:
            bad.append(f"{DATA_PREFIX}/{name} differs from the manifest")
    return bad


def prepare(repo: Path, tag: str, dist: Path, out: Path) -> dict:
    record, _ = R.read_record_from_tag(Path(repo), tag)
    bad = dist_problems(Path(dist), record)
    if out.exists() and any(out.iterdir()):
        bad.append(f"output directory {out} is not empty")
    if bad:
        raise R.ReleaseError(bad)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dist, out / "static")
    (out / "config.json").write_bytes(R.dumps_record(vercel_config()))
    return record


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag", help="release tag being deployed (must exist in the local repository)")
    p.add_argument(
        "--dist", type=Path, default=Path("dashboard/dist"), help="the Vite build (default: dashboard/dist)"
    )
    p.add_argument("--out", type=Path, required=True, help="the .vercel/output directory to create")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    a = p.parse_args(argv)
    try:
        rec = prepare(a.repo, a.tag, a.dist, a.out)
    except R.ReleaseError as e:
        print(f"prepare_deploy: {a.tag}: REFUSED; {len(e.problems)} problem(s):", file=sys.stderr)
        for m in e.problems:
            print(f"  X {m}", file=sys.stderr)
        return 1
    files = sum(1 for f in (a.out / "static").rglob("*") if f.is_file())
    print(f"prepare_deploy: {a.tag}: {files} files in {a.out / 'static'}; config.json written")
    print(
        f"  manifest sha256 {rec['dashboard']['manifest_sha256']} (matches releases/{a.tag}.json at the tag)"
    )
    print(json.dumps(vercel_config()["routes"][-2]["headers"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
