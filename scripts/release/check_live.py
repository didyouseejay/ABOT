"""Check that the live site serves a release's bundle, after a deployment.

    python scripts/release/check_live.py v1.0.0 https://abot.example.org

Fetches <site>/data/v1/manifest.json and compares its SHA-256 with `releases/<tag>.json` at the tag,
then checks that <site>/ answers with the security headers from prepare_deploy.py. Retries for a
short while, because a new production deployment can take a few seconds to be served everywhere.
Exit 0 if the site serves the release, 1 otherwise. See docs/DEPLOYMENT.md.
"""

import argparse
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path

import prepare_deploy as D
import release_lib as R

Fetch = Callable[[str], tuple[bytes, Message]]
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
REQUIRED_HEADERS = ("Content-Security-Policy", "X-Content-Type-Options")


def fetch_https(url: str) -> tuple[bytes, Message]:
    req = urllib.request.Request(url, headers={"User-Agent": "abot-check-live", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (URL validated in check)
        return resp.read(MAX_MANIFEST_BYTES + 1), resp.headers


def site_problems(site: str, want_sha: str, fetch: Fetch) -> list[str]:
    try:
        body, _ = fetch(f"{site}/{D.DATA_PREFIX}/{R.MANIFEST}")
        _, headers = fetch(f"{site}/")
    except OSError as e:
        return [f"request failed: {e}"]
    bad = []
    if len(body) > MAX_MANIFEST_BYTES:
        bad.append("manifest.json is larger than expected")
    elif R.sha256_bytes(body) != want_sha:
        bad.append(f"{site}/{D.DATA_PREFIX}/{R.MANIFEST} is not this release's manifest")
    for h in REQUIRED_HEADERS:
        if headers.get(h) != D.SECURITY_HEADERS[h]:
            bad.append(f"{site}/ header {h} is {headers.get(h)!r}, expected {D.SECURITY_HEADERS[h]!r}")
    return bad


def check(
    repo: Path, tag: str, site: str, *, fetch: Fetch = fetch_https, attempts: int = 6, wait: float = 10.0
) -> None:
    parsed = urllib.parse.urlsplit(site)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.query or parsed.fragment:
        raise R.ReleaseError(f"site URL {site!r} must be an http(s) origin, e.g. https://abot.example.org")
    site = site.rstrip("/")
    record, _ = R.read_record_from_tag(repo, tag)
    bad: list[str] = []
    for i in range(attempts):
        bad = site_problems(site, record["dashboard"]["manifest_sha256"], fetch)
        if not bad:
            return
        if i + 1 < attempts:
            time.sleep(wait)
    raise R.ReleaseError(bad)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag")
    p.add_argument("site", help="the production origin, e.g. https://abot.example.org")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    p.add_argument("--attempts", type=int, default=6)
    a = p.parse_args(argv)
    try:
        check(a.repo, a.tag, a.site, attempts=a.attempts)
    except R.ReleaseError as e:
        print(f"check_live: {a.tag} at {a.site}: FAILED", file=sys.stderr)
        for m in e.problems:
            print(f"  X {m}", file=sys.stderr)
        return 1
    print(f"check_live: {a.site} serves release {a.tag} (manifest SHA-256 and security headers match)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
