"""Shared helpers for ABOT's release tooling (M06.3 Phase 1; see releases/README.md).

Standard library only, so the tools run without the analytical dependencies. Everything here reads;
the only writer is `write_zip`, which builds a deterministic archive at a path the caller chooses.

Trust anchor: the release record `releases/<tag>.json` is read from the Git object of the tag
(`git show <tag>:releases/<tag>.json`), never from the working tree or from a release asset.
"""

import hashlib
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

RECORD_SCHEMA = "abot-release-record"
RECORD_SCHEMA_VERSION = 1
CONTRACT_ID = "abot-dashboard"
BUNDLE_REL = "data/processed/dashboard/v1"
RAW_REL = "data/raw"
VERSION_TS = "dashboard/src/contract/version.ts"
RECORDS_DIR = "releases"
MANIFEST = "manifest.json"
PROVENANCE = "provenance.json"

# Licence and attribution documents shipped in every archive: (path in the repository, archive name).
# They are read from the Git object of the packaged commit, so the bytes do not depend on the
# checkout's line endings.
LICENCE_DOCS = (("LICENSE-DATA.md", "LICENSE-DATA.md"), ("docs/ATTRIBUTION.md", "ATTRIBUTION.md"))
LICENCES = {
    "dataset": {
        "id": "ODbL-1.0",
        "url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "file": "LICENSE-DATA.md",
    },
    "attribution": {"file": "docs/ATTRIBUTION.md"},
    "code": {"id": "MIT", "file": "LICENSE", "covers_dataset": False},
}

KIND_DASHBOARD = "dashboard-bundle"
KIND_OSM = "osm-snapshot"

TAG_RE = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# All patterns are used with fullmatch (`$` would also accept a trailing newline).

# Fixed archive metadata: the earliest timestamp ZIP can store, Unix "regular file, rw-r--r--", and
# no compression. Stored entries make the archive bytes independent of the zlib build.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = stat.S_IFREG | 0o644
ZIP_UNIX = 3
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 64


class ReleaseError(Exception):
    """A release check failed. `problems` lists every reason found (fail closed)."""

    def __init__(self, problems: list[str] | str):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("; ".join(self.problems))


# --- names ------------------------------------------------------------------------------------


def parse_tag(tag: str) -> tuple[int, int, int]:
    """`vMAJOR.MINOR.PATCH`, no leading zeros, no suffix."""
    m = TAG_RE.fullmatch(tag) if isinstance(tag, str) else None
    if not m:
        raise ReleaseError(f"invalid release tag {tag!r}: expected vMAJOR.MINOR.PATCH, e.g. v1.0.0")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def dashboard_asset_name(tag: str) -> str:
    return f"abot-dashboard-v1-{tag}.zip"


def osm_asset_name(tag: str) -> str:
    return f"abot-osm-snapshot-{tag}.zip"


def record_relpath(tag: str) -> str:
    return f"{RECORDS_DIR}/{tag}.json"


# --- hashing and JSON -------------------------------------------------------------------------


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dumps_record(obj: dict) -> bytes:
    """Deterministic JSON: fixed key order (as built), two-space indent, ASCII, LF, final newline."""
    return (json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def loads_json(b: bytes, what: str) -> dict:
    try:
        obj = json.loads(b.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ReleaseError(f"{what}: not valid UTF-8 JSON ({e})") from e
    if not isinstance(obj, dict):
        raise ReleaseError(f"{what}: expected a JSON object")
    return obj


# --- git --------------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    except FileNotFoundError as e:
        raise ReleaseError("git is not installed or not on PATH") from e


def git_text(repo: Path, *args: str) -> str:
    r = _git(repo, *args)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()
        raise ReleaseError(f"git {' '.join(args)} failed: {err}")
    return r.stdout.decode("utf-8", "replace").strip()


def head_commit(repo: Path) -> str:
    return git_text(repo, "rev-parse", "--verify", "HEAD^{commit}")


def resolve_commit(repo: Path, rev: str) -> str | None:
    """The full commit id of `rev`, or None if it does not name a commit in this repository."""
    r = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}")
    out = r.stdout.decode("ascii", "replace").strip()
    return out if r.returncode == 0 and COMMIT_RE.fullmatch(out) else None


def tag_commit(repo: Path, tag: str) -> str | None:
    parse_tag(tag)
    return resolve_commit(repo, f"refs/tags/{tag}")


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """True if `ancestor` is `descendant` or one of its ancestors."""
    r = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if r.returncode in (0, 1):
        return r.returncode == 0
    raise ReleaseError(f"git merge-base failed: {r.stderr.decode('utf-8', 'replace').strip()}")


def dirty_paths(repo: Path) -> list[str]:
    """Modified, staged or untracked (not ignored) paths; empty for a clean working tree."""
    r = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if r.returncode != 0:
        raise ReleaseError(f"git status failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    return [e[3:] for e in r.stdout.decode("utf-8", "replace").split("\0") if len(e) > 3]


def show_file(repo: Path, commit: str, path: str) -> bytes | None:
    """The bytes of `path` in the Git object of `commit`, or None if it is not there."""
    r = _git(repo, "show", f"{commit}:{path}")
    return r.stdout if r.returncode == 0 else None


def github_slug(repo: Path) -> str | None:
    """owner/name of the `origin` remote if it is a github.com URL."""
    r = _git(repo, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", r.stdout.decode().strip())
    return f"{m.group(1)}/{m.group(2)}" if r.returncode == 0 and m else None


# --- contract ---------------------------------------------------------------------------------


def parse_version(v: object) -> tuple[int, int, int] | None:
    m = VERSION_RE.fullmatch(v) if isinstance(v, str) else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def supported_version(version_ts: bytes | None) -> str:
    """SUPPORTED_VERSION from dashboard/src/contract/version.ts (the frontend's authority)."""
    if version_ts is None:
        raise ReleaseError(f"{VERSION_TS} not found")
    text = version_ts.decode("utf-8", "replace")
    cid = re.search(r'export const CONTRACT_ID = "([^"]+)";', text)
    ver = re.search(r'export const SUPPORTED_VERSION = "(\d+\.\d+\.\d+)";', text)
    if not cid or not ver or cid.group(1) != CONTRACT_ID:
        raise ReleaseError(f"{VERSION_TS}: CONTRACT_ID {CONTRACT_ID!r} / SUPPORTED_VERSION not found")
    return ver.group(1)


def contract_problems(contract: object, version: object, supported: str) -> list[str]:
    """The dashboard's rule (version.ts), made strict for a release: the major must match and the
    minor must not be newer than the frontend supports (a newer minor would load with fields hidden)."""
    if contract != CONTRACT_ID:
        return [f"contract is {contract!r}, expected {CONTRACT_ID!r}"]
    got, want = parse_version(version), parse_version(supported)
    if got is None or want is None:
        return [f"unreadable contract_version {version!r}"]
    if got[0] != want[0]:
        return [f"contract_version {version} has another major version than the supported {supported}"]
    if got[1] > want[1]:
        return [f"contract_version {version} is newer than the supported {supported}"]
    return []


# --- manifest ---------------------------------------------------------------------------------


def _obj(d: dict, key: str) -> dict:
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def _audit(manifest: dict) -> dict:
    try:
        a = manifest["data_quality"]["source_validation"]["audit"]
    except (KeyError, TypeError):
        return {}
    return a if isinstance(a, dict) else {}


def safe_flat_name(name: object) -> bool:
    return isinstance(name, str) and entry_name_problem(name) is None and "/" not in name


def manifest_problems(manifest: dict) -> list[str]:
    """Release eligibility of the manifest itself (audit, provenance cleanliness, file list)."""
    bad = []
    a = _audit(manifest)
    if a.get("status") != "obtained":
        bad.append(f"audit status is {a.get('status')!r}, not 'obtained'")
    if a.get("outcome") not in ("pass", "warn"):
        bad.append(f"audit outcome is {a.get('outcome')!r}")
    counts = a.get("counts")
    if not isinstance(counts, dict) or counts.get("fail") != 0:
        bad.append(f"audit fail count is {counts.get('fail') if isinstance(counts, dict) else None!r}, not 0")
    code = _obj(manifest, "code")
    if code.get("git_working_tree_clean") is not True or code.get("git_dirty_count") != 0:
        bad.append(
            "manifest reports an unclean Git working tree at export time "
            f"(clean: {code.get('git_working_tree_clean')!r}, dirty: {code.get('git_dirty_count')!r})"
        )
    if not (isinstance(code.get("git_commit"), str) and COMMIT_RE.fullmatch(code["git_commit"])):
        bad.append(f"manifest code.git_commit {code.get('git_commit')!r} is not a full commit id")
    if not isinstance(manifest.get("generated_utc"), str):
        bad.append("manifest generated_utc missing")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return [*bad, "manifest files list missing or empty"]
    seen = set()
    for f in files:
        if not isinstance(f, dict):
            bad.append("manifest files entry is not an object")
            continue
        n = f.get("name")
        if not safe_flat_name(n) or n == MANIFEST:
            bad.append(f"manifest files entry has an unsafe or reserved name {n!r}")
        elif n in seen:
            bad.append(f"manifest lists {n} twice")
        seen.add(n)
        if not (isinstance(f.get("sha256"), str) and SHA_RE.fullmatch(f["sha256"])):
            bad.append(f"manifest entry {n!r}: bad sha256")
        b = f.get("bytes")
        if not isinstance(b, int) or isinstance(b, bool) or b < 0 or b > MAX_ENTRY_BYTES:
            bad.append(f"manifest entry {n!r}: bad or oversized byte count {b!r}")
    if PROVENANCE not in seen:
        bad.append(f"manifest does not list {PROVENANCE}")
    return bad


def manifest_files(manifest: dict) -> dict[str, tuple[int, str]]:
    return {f["name"]: (f["bytes"], f["sha256"]) for f in manifest["files"]}


def envelope_problems(name: str, data: bytes, manifest: dict) -> list[str]:
    """Every JSON/GeoJSON file repeats contract, contract_version and generated_utc (contract §5.3)."""
    try:
        env = loads_json(data, name)
    except ReleaseError as e:
        return e.problems
    return [
        f"{name}: {k} {env.get(k)!r} differs from the manifest's {manifest.get(k)!r}"
        for k in ("contract", "contract_version", "generated_utc")
        if env.get(k) != manifest.get(k)
    ]


# --- record blocks derived from the manifest and provenance -----------------------------------
# The record copies these fields for readability; the verifier recomputes every block from the
# verified archive and requires equality, so a copied field can never disagree with its source.


def dashboard_block(manifest: dict, manifest_bytes: bytes) -> dict:
    return {
        "contract": manifest.get("contract"),
        "contract_version": manifest.get("contract_version"),
        "generated_utc": manifest.get("generated_utc"),
        "config_sha256": manifest.get("config_sha256"),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "manifest_bytes": len(manifest_bytes),
    }


def source_block(manifest: dict) -> dict:
    code = _obj(manifest, "code")
    return {
        k: code.get(k) for k in ("git_commit", "git_working_tree_clean", "git_dirty_count", "abot_version")
    }


def audit_block(manifest: dict) -> dict:
    a = _audit(manifest)
    return {k: a.get(k) for k in ("status", "outcome", "counts", "ran_utc")}


def osm_block(provenance: dict) -> dict:
    osm = _obj(provenance, "osm")
    responses = osm.get("responses")
    responses = responses if isinstance(responses, list) else []
    keys = ("label", "cache_file", "sha256", "overpass_timestamp_osm_base", "elements")
    ts = provenance.get("targeted_snapshot")
    return {
        "osmnx_version": osm.get("osmnx_version"),
        "overpass_endpoint": osm.get("overpass_endpoint"),
        "boundary_buffer_m": osm.get("boundary_buffer_m"),
        "responses": [{k: r.get(k) for k in keys} for r in responses if isinstance(r, dict)],
        "targeted_snapshot": (
            {k: ts.get(k) for k in ("file", "sha256", "timestamp_osm_base", "used_for")}
            if isinstance(ts, dict)
            else None
        ),
    }


def osm_files(osm: dict) -> dict[str, str]:
    """Paths (relative to data/raw) and SHA-256 of the OSM responses the baseline was built from."""
    out = {r["cache_file"]: r["sha256"] for r in osm["responses"]}
    if osm.get("targeted_snapshot"):
        out[osm["targeted_snapshot"]["file"]] = osm["targeted_snapshot"]["sha256"]
    return out


# --- record shape -----------------------------------------------------------------------------


def _is_sha(v: object) -> bool:
    return isinstance(v, str) and bool(SHA_RE.fullmatch(v))


def _is_size(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v


def record_shape_problems(rec: dict) -> list[str]:
    bad = []
    if rec.get("schema") != RECORD_SCHEMA:
        bad.append(f"record schema is {rec.get('schema')!r}, expected {RECORD_SCHEMA!r}")
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        bad.append(f"record schema_version {rec.get('schema_version')!r} is not supported")
    if not (
        isinstance(rec.get("packaged_from_commit"), str) and COMMIT_RE.fullmatch(rec["packaged_from_commit"])
    ):
        bad.append("record packaged_from_commit is not a full commit id")
    for k in ("dashboard", "source", "audit", "osm", "licences"):
        if not isinstance(rec.get(k), dict):
            bad.append(f"record {k} block missing")
    if isinstance(rec.get("dashboard"), dict):
        d = rec["dashboard"]
        if not _is_sha(d.get("manifest_sha256")) or not _is_size(d.get("manifest_bytes")):
            bad.append("record dashboard.manifest_sha256 / manifest_bytes invalid")
    assets = rec.get("assets")
    if not isinstance(assets, list) or not assets:
        return [*bad, "record assets missing"]
    names, kinds = set(), []
    for a in assets:
        if not isinstance(a, dict):
            bad.append("record asset is not an object")
            continue
        n = a.get("name")
        if not safe_flat_name(n) or n in names:
            bad.append(f"record asset name {n!r} unsafe or repeated")
        names.add(n)
        kinds.append(a.get("kind"))
        if not _is_sha(a.get("sha256")) or not _is_size(a.get("bytes")):
            bad.append(f"record asset {n!r}: sha256 / bytes invalid")
        contents = a.get("contents")
        if not isinstance(contents, list) or not contents:
            bad.append(f"record asset {n!r}: contents missing")
            continue
        for c in contents:
            if not (
                isinstance(c, dict)
                and isinstance(c.get("name"), str)
                and _is_sha(c.get("sha256"))
                and _is_size(c.get("bytes"))
            ):
                bad.append(f"record asset {n!r}: invalid contents entry {c!r}")
    if kinds.count(KIND_DASHBOARD) != 1 or any(k not in (KIND_DASHBOARD, KIND_OSM) for k in kinds):
        bad.append(f"record assets must be one {KIND_DASHBOARD} and at most one {KIND_OSM}: {kinds}")
    if kinds.count(KIND_OSM) > 1:
        bad.append(f"record lists more than one {KIND_OSM}")
    return bad


def record_asset(rec: dict, kind: str) -> dict | None:
    return next((a for a in rec["assets"] if a.get("kind") == kind), None)


def read_record_from_tag(repo: Path, tag: str) -> tuple[dict, str]:
    """The release record committed at `tag`, and the tag's commit. The working tree is never read."""
    parse_tag(tag)
    commit = tag_commit(repo, tag)
    if commit is None:
        raise ReleaseError(f"tag {tag} does not exist in {repo} (git fetch --tags?)")
    raw = show_file(repo, commit, record_relpath(tag))
    if raw is None:
        raise ReleaseError(f"no release record {record_relpath(tag)} in the commit of tag {tag}")
    rec = loads_json(raw, record_relpath(tag))
    bad = record_shape_problems(rec)
    if rec.get("tag") != tag:
        bad.append(f"record tag {rec.get('tag')!r} does not match {tag}")
    if bad:
        raise ReleaseError(bad)
    return rec, commit


# --- archives ---------------------------------------------------------------------------------


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    """Deterministic ZIP: sorted names, fixed timestamp and mode, stored, no comment or extras."""
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(entries):
            if entry_name_problem(name):
                raise ReleaseError(f"refusing to write unsafe archive name {name!r}")
            zi = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            zi.compress_type = zipfile.ZIP_STORED
            zi.create_system = ZIP_UNIX
            zi.external_attr = ZIP_MODE << 16
            zf.writestr(zi, entries[name])


def entry_name_problem(name: str) -> str | None:
    if not name or "\0" in name:
        return "empty or NUL in name"
    if "\\" in name:
        return "backslash in name"
    if name.startswith("/") or re.match(r"[A-Za-z]:", name):
        return "absolute path"
    if name.endswith("/"):
        return "directory entry"
    parts = PurePosixPath(name).parts
    if any(p in ("..", ".") for p in name.split("/")):
        return "path traversal"
    if len(parts) != len(name.split("/")):
        return "empty path segment"
    return None


def read_archive(path: Path, expected: dict[str, tuple[int, str]]) -> dict[str, bytes]:
    """Read and check every entry of the ZIP at `path` in memory, without extracting anything.

    `expected` maps each allowed name to (bytes, sha256). Rejects unsafe names, symlinks and other
    non-regular entries, encrypted or unknown-compression entries, duplicates (also by case), entries
    that are unexpected, missing, oversized or of another size, and content with another SHA-256.
    Structural problems are all reported before any content is read.
    """
    bad: list[str] = []
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise ReleaseError(f"{path.name}: not a readable ZIP archive ({e})") from e
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ReleaseError(f"{path.name}: {len(infos)} entries, more than {MAX_ENTRIES}")
        seen: set[str] = set()
        folded: set[str] = set()
        total = 0
        for info in infos:
            name = info.orig_filename
            why = entry_name_problem(name)
            if why:
                bad.append(f"entry {name!r}: {why}")
                continue
            if name in seen or name.casefold() in folded:
                bad.append(f"entry {name!r}: duplicate archive entry")
                continue
            seen.add(name)
            folded.add(name.casefold())
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                bad.append(f"entry {name!r}: symbolic link")
                continue
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG) or info.is_dir():
                bad.append(f"entry {name!r}: not a regular file")
                continue
            if info.flag_bits & 0x1:
                bad.append(f"entry {name!r}: encrypted")
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                bad.append(f"entry {name!r}: unsupported compression {info.compress_type}")
            if info.file_size > MAX_ENTRY_BYTES:
                bad.append(f"entry {name!r}: oversized ({info.file_size} bytes > {MAX_ENTRY_BYTES})")
            total += info.file_size
            if name not in expected:
                kind = "unexpected nested path" if "/" in name else "unexpected file"
                bad.append(f"entry {name!r}: {kind}")
            elif info.file_size != expected[name][0]:
                bad.append(f"entry {name!r}: {info.file_size} bytes, expected {expected[name][0]}")
        if total > MAX_ARCHIVE_BYTES:
            bad.append(f"archive expands to {total} bytes, more than {MAX_ARCHIVE_BYTES}")
        bad += [f"missing entry {n!r}" for n in sorted(set(expected) - seen)]
        if bad:
            raise ReleaseError(bad)
        out: dict[str, bytes] = {}
        for info in infos:
            size, sha = expected[info.orig_filename]
            try:
                with zf.open(info) as f:
                    data = f.read(size + 1)
            except (OSError, zipfile.BadZipFile, ValueError) as e:  # CRC errors, truncated data
                bad.append(f"entry {info.orig_filename!r}: unreadable ({e})")
                continue
            if len(data) != size:
                bad.append(f"entry {info.orig_filename!r}: read {len(data)} bytes, expected {size}")
            elif sha256_bytes(data) != sha:
                bad.append(f"entry {info.orig_filename!r}: SHA-256 differs from the release record")
            else:
                out[info.orig_filename] = data
        if bad:
            raise ReleaseError(bad)
        return out


def contents_map(asset: dict) -> dict[str, tuple[int, str]]:
    return {c["name"]: (c["bytes"], c["sha256"]) for c in asset["contents"]}


def check_asset_file(path: Path, asset: dict) -> None:
    """The downloaded file is the recorded asset: name, size and SHA-256, before it is opened."""
    bad = []
    if path.name != asset["name"]:
        bad.append(f"file name {path.name!r} is not the recorded asset name {asset['name']!r}")
    if not path.is_file():
        raise ReleaseError([*bad, f"{path} is not a file"])
    size = path.stat().st_size
    if size != asset["bytes"]:
        bad.append(f"{path.name}: {size} bytes, release record says {asset['bytes']}")
    elif sha256_file(path) != asset["sha256"]:
        bad.append(f"{path.name}: SHA-256 differs from the release record")
    if bad:
        raise ReleaseError(bad)
