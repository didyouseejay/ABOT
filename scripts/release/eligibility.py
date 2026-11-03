"""Decide whether a tag may be deployed as ABOT's public release. Independent of GitHub Actions.

    python scripts/release/eligibility.py v1.0.0
    gh release list --json tagName,isDraft,isPrerelease --limit 1000 > releases.json
    python scripts/release/eligibility.py v1.0.0 --releases releases.json --require-latest
    python scripts/release/eligibility.py v0.9.0 --releases releases.json --require-latest --allow-rollback

Inputs (all explicit; no CI event payload is read):
- tag: the candidate, vMAJOR.MINOR.PATCH. The tag must exist in the local repository.
- --releases FILE: a JSON array of objects with the keys tagName (string), isDraft (bool) and
  isPrerelease (bool). That is the output of `gh release list --json tagName,isDraft,isPrerelease`;
  any other source must produce the same keys. "-" reads standard input.
- --draft / --prerelease true|false: the candidate's own status, if known from elsewhere. When the
  candidate also appears in --releases, both must agree.
- --require-latest: the candidate must be the highest published (non-draft, non-prerelease) version.
- --allow-rollback: with --require-latest, an older published version is also accepted (rollback).

Checks: valid tag; tag exists; release record committed at the tag; record tag matches; not a draft;
not a prerelease; latest (when requested). Status that no input provides is reported as
"not evaluated", never assumed. Exit 0 if eligible, 1 if not, 2 for unusable input.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import release_lib as R

PASS, FAIL, SKIP = "pass", "fail", "not evaluated"


@dataclass
class Decision:
    tag: str
    checks: list[tuple[str, str, str]] = field(default_factory=list)  # (check, status, detail)
    rollback: bool = False

    @property
    def eligible(self) -> bool:
        return bool(self.checks) and all(s != FAIL for _, s, _ in self.checks)

    def add(self, check: str, status: str, detail: str = "") -> None:
        self.checks.append((check, status, detail))

    def as_dict(self) -> dict:
        return {
            "tag": self.tag,
            "eligible": self.eligible,
            "rollback": self.rollback,
            "checks": [{"check": c, "status": s, "detail": d} for c, s, d in self.checks],
        }


class InputError(Exception):
    """The supplied inputs are malformed (exit 2)."""


def parse_releases(data: object) -> list[dict]:
    if not isinstance(data, list):
        raise InputError("releases input must be a JSON array")
    out = []
    for i, r in enumerate(data):
        if not (
            isinstance(r, dict)
            and isinstance(r.get("tagName"), str)
            and isinstance(r.get("isDraft"), bool)
            and isinstance(r.get("isPrerelease"), bool)
        ):
            raise InputError(f"releases[{i}] needs tagName (string), isDraft and isPrerelease (booleans)")
        out.append(r)
    tags = [r["tagName"] for r in out]
    if len(tags) != len(set(tags)):
        raise InputError("releases input lists a tag twice")
    return out


def _status(
    name: str, explicit: bool | None, listed: dict | None, key: str
) -> tuple[bool | None, str | None]:
    from_list = listed[key] if listed else None
    if explicit is not None and from_list is not None and explicit != from_list:
        return None, f"--{name} {str(explicit).lower()} contradicts the releases input ({key}: {from_list})"
    return (explicit if explicit is not None else from_list), None


def evaluate(
    repo: Path,
    tag: str,
    *,
    releases: list[dict] | None = None,
    draft: bool | None = None,
    prerelease: bool | None = None,
    require_latest: bool = False,
    allow_rollback: bool = False,
) -> Decision:
    d = Decision(tag)
    try:
        version = R.parse_tag(tag)
    except R.ReleaseError as e:
        d.add("valid_tag", FAIL, str(e))
        return d
    d.add("valid_tag", PASS)

    commit = R.tag_commit(Path(repo), tag)
    if commit is None:
        d.add("tag_exists", FAIL, f"tag {tag} not found in the local repository")
        return d
    d.add("tag_exists", PASS, commit)
    try:
        rec, _ = R.read_record_from_tag(Path(repo), tag)
        d.add("release_record", PASS, R.record_relpath(tag))
        d.add("record_consistent", PASS, f"record tag {rec['tag']}")
    except R.ReleaseError as e:
        missing = any("no release record" in p for p in e.problems)
        d.add("release_record", FAIL if missing else PASS, "; ".join(e.problems) if missing else "")
        if not missing:
            d.add("record_consistent", FAIL, "; ".join(e.problems))

    listed = next((r for r in releases or [] if r["tagName"] == tag), None)
    for name, explicit, key in (("draft", draft, "isDraft"), ("prerelease", prerelease, "isPrerelease")):
        value, conflict = _status(name, explicit, listed, key)
        if conflict:
            d.add(f"not_{name}", FAIL, conflict)
        elif value is None:
            d.add(f"not_{name}", SKIP, "no input provides this status")
        else:
            d.add(f"not_{name}", FAIL if value else PASS, f"{key}: {value}")

    if require_latest:
        if releases is None:
            d.add("latest", FAIL, "--require-latest needs --releases")
            return d
        published = [
            R.parse_tag(r["tagName"])
            for r in releases
            if not r["isDraft"] and not r["isPrerelease"] and R.TAG_RE.fullmatch(r["tagName"])
        ]
        latest = max(published, default=None)
        latest_tag = "v{}.{}.{}".format(*latest) if latest else None
        if latest is None or version >= latest:
            d.add(
                "latest",
                PASS,
                f"{tag} is the highest published version"
                + (f" (was {latest_tag})" if latest and version > latest else ""),
            )
        elif allow_rollback:
            d.rollback = True
            d.add(
                "latest", PASS, f"rollback: {tag} is older than the latest published {latest_tag} (allowed)"
            )
        else:
            d.add(
                "latest",
                FAIL,
                f"{tag} is older than the latest published {latest_tag}; pass --allow-rollback",
            )
    else:
        d.add("latest", SKIP, "not requested")
    return d


def _bool(v: str) -> bool:
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise argparse.ArgumentTypeError("expected true or false")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("tag")
    p.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    p.add_argument(
        "--releases", help="JSON file from `gh release list --json tagName,isDraft,isPrerelease`, or -"
    )
    p.add_argument("--draft", type=_bool, help="candidate is a draft (true|false)")
    p.add_argument("--prerelease", type=_bool, help="candidate is a prerelease (true|false)")
    p.add_argument("--require-latest", action="store_true")
    p.add_argument("--allow-rollback", action="store_true")
    p.add_argument("--json", action="store_true", help="print the decision as JSON")
    a = p.parse_args(argv)
    try:
        releases = None
        if a.releases:
            text = sys.stdin.read() if a.releases == "-" else Path(a.releases).read_text(encoding="utf-8")
            releases = parse_releases(json.loads(text))
        d = evaluate(
            a.repo,
            a.tag,
            releases=releases,
            draft=a.draft,
            prerelease=a.prerelease,
            require_latest=a.require_latest,
            allow_rollback=a.allow_rollback,
        )
    except (InputError, OSError, ValueError) as e:
        print(f"eligibility: unusable input: {e}", file=sys.stderr)
        return 2
    except R.ReleaseError as e:
        print(f"eligibility: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(d.as_dict(), indent=2))
    else:
        print(
            f"eligibility: {a.tag}: {'ELIGIBLE' if d.eligible else 'NOT ELIGIBLE'}"
            + (" (rollback)" if d.rollback else "")
        )
        for c, s, det in d.checks:
            print(f"  {s:<14} {c:<20} {det}")
    return 0 if d.eligible else 1


if __name__ == "__main__":
    sys.exit(main())
