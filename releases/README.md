# ABOT releases

This folder holds one **release record** per published release, `releases/vX.Y.Z.json`. The record
is committed to Git at the release tag. The tools in [`scripts/release/`](../scripts/release/)
verify every downloaded release asset against the record read from the tag, never against a file
that came with the assets.

The tooling was added in Milestone 06.3 Phase 1. No release has been published yet. Phase 2 added
the deployment workflow, which deploys a published release only after these checks pass. See
[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## 1. Assets

| Asset | Contents |
|---|---|
| `abot-dashboard-v1-vX.Y.Z.zip` | The dashboard bundle (`manifest.json` plus every file it lists: nine files for the current bundle), `LICENSE-DATA.md` and `ATTRIBUTION.md` |
| `abot-osm-snapshot-vX.Y.Z.zip` | Optional (`--with-osm-snapshot`). The OpenStreetMap responses the baseline was built from: every `osm.responses[].cache_file` and the `targeted_snapshot.file` in the bundle's `provenance.json`, under their `data/raw/` paths, plus the same two licence documents |
| `SHA256SUMS` | `<sha256>  <asset name>` per line, sorted, LF. Readable by `sha256sum -c` |

The dashboard archive is flat, with no folders. The OSM archive has exactly the `osm_cache/` and
`osm_targeted/` paths that `provenance.json` names. Both archives are released under the ODbL 1.0
([LICENSE-DATA.md](../LICENSE-DATA.md)). The MIT licence covers the code only.

Archives are deterministic. Entries are sorted, use the fixed timestamp 1980-01-01 00:00:00 and Unix
mode `-rw-r--r--`, and are stored uncompressed, so the bytes do not depend on the zlib build. There is
no comment and there are no extra fields. The licence documents are read from the Git object of the
packaged commit, not the working tree, so a CRLF checkout gives the same bytes. Packaging the same
commit and bundle twice, or in a clone at another path, gives byte-identical archives, record and
`SHA256SUMS`. This is tested in `tests/test_release.py` and was also checked on the real bundle. The
dashboard archive is about 10 MB and the OSM snapshot about 12 MB.

## 2. Release record schema (`abot-release-record`, schema version 1)

```jsonc
{
  "schema": "abot-release-record",
  "schema_version": 1,
  "tag": "v0.1.0",
  "packaged_from_commit": "<40-hex>",   // HEAD when packaged; the record commit is its child
  "dashboard": {                         // copied from manifest.json
    "contract": "abot-dashboard",
    "contract_version": "1.1.0",
    "generated_utc": "2026-11-02T01:39:00+00:00",
    "config_sha256": "<64-hex>",
    "manifest_sha256": "<64-hex>",      // SHA-256 of manifest.json as shipped
    "manifest_bytes": 177379
  },
  "source": {                            // copied from manifest.code
    "git_commit": "<40-hex>",           // the commit the bundle was exported from
    "git_working_tree_clean": true,
    "git_dirty_count": 0,
    "abot_version": "0.1.0"
  },
  "audit": {                             // copied from manifest data_quality.source_validation.audit
    "status": "obtained", "outcome": "warn",
    "counts": {"pass": 58, "warn": 3, "fail": 0, "info": 11},
    "ran_utc": "2026-11-02T01:38:58+00:00"
  },
  "osm": {                               // copied from provenance.json (osm, targeted_snapshot)
    "osmnx_version": "2.1.1",
    "overpass_endpoint": "https://overpass-api.de/api",
    "boundary_buffer_m": 3000,
    "responses": [{"label": "network_walk", "cache_file": "osm_cache/<id>.json",
                   "sha256": "<64-hex>", "overpass_timestamp_osm_base": "2026-10-31T07:23:18Z",
                   "elements": 62049}],
    "targeted_snapshot": {"file": "osm_targeted/<name>.json", "sha256": "<64-hex>",
                          "timestamp_osm_base": "2026-10-31T13:14:07Z", "used_for": "evidence only"}
  },
  "licences": {
    "dataset": {"id": "ODbL-1.0", "url": "https://opendatacommons.org/licenses/odbl/1-0/", "file": "LICENSE-DATA.md"},
    "attribution": {"file": "docs/ATTRIBUTION.md"},
    "code": {"id": "MIT", "file": "LICENSE", "covers_dataset": false}
  },
  "assets": [
    {"name": "abot-dashboard-v1-v0.1.0.zip", "kind": "dashboard-bundle", "bytes": 10196335,
     "sha256": "<64-hex>", "contents": [{"name": "city.json", "bytes": 107233, "sha256": "<64-hex>"}]},
    {"name": "abot-osm-snapshot-v0.1.0.zip", "kind": "osm-snapshot", "...": "..."}
  ]
}
```

- `assets[].contents` lists every archive entry, sorted by name. Nothing else may be in the archive.
- There is exactly one `dashboard-bundle` asset and at most one `osm-snapshot` asset.
- The record contains no timestamps of its own and no machine paths. It is written as two-space,
  ASCII, LF JSON, so it is deterministic too.
- The `dashboard`, `source`, `audit`, `osm` and `licences` blocks repeat values for readability only.
  The verifier recomputes each block from the verified archive and fails on any difference, so a
  copied field can never silently disagree with the manifest.

## 3. Trust anchor

The trust anchor is the Git tag. `verify_release.py`, `fetch_bundle.py` and `eligibility.py` read
`releases/<tag>.json` with `git show <tag>:releases/<tag>.json`:

- They never read a record from the working tree. Editing `releases/vX.Y.Z.json` locally changes
  nothing.
- They never read a record from the release assets. No record is uploaded.
- An attacker who can replace release assets cannot change the expected hashes without also
  changing the tagged commit.
- The supported contract version is read the same way, from `dashboard/src/contract/version.ts` at
  the tag.

The verifier checks the commit chain: the bundle's source commit must be an ancestor of
`packaged_from_commit`, which must be an ancestor of the tag. All three commits must exist locally.

What the anchor does **not** cover: it is only as trustworthy as the tag itself. Tags are not
signed, and anyone with push access to the repository can move or recreate a tag. See
[Known limitations](#9-known-limitations).

## 4. Packaging

Prerequisites:
- A clean checkout of the commit to release.
- The tag must not exist yet.
- The current bundle in `data/processed/dashboard/v1/`, with its source data present, so that
  `abot export-dashboard --check` can pass.
- For `--with-osm-snapshot`, the OSM responses in `data/raw/`.

```bash
uv run python scripts/release/pack_release.py v0.1.0 --with-osm-snapshot
git add releases/v0.1.0.json && git commit -m "Release record v0.1.0"
git tag -a v0.1.0 -m "ABOT v0.1.0"
uv run python scripts/release/verify_release.py v0.1.0 dist/release/v0.1.0/abot-dashboard-v1-v0.1.0.zip \
    --osm-archive dist/release/v0.1.0/abot-osm-snapshot-v0.1.0.zip
```

The commands are the same in PowerShell. `pack_release.py` writes the assets and `SHA256SUMS` to
`dist/release/<tag>/` (git-ignored) and the record to `releases/<tag>.json`. It never creates a tag,
commit or GitHub Release. Uploading the assets is a separate, manual step.

It refuses, writes nothing and exits 1 if any of these is true:

| Condition | Check |
|---|---|
| Invalid tag | Not `vMAJOR.MINOR.PATCH`: no leading zeros, no suffix, no trailing characters |
| Tag or record already exists | The record must be committed before the tag is created |
| Dirty working tree | `git status --porcelain --untracked-files=all` is not empty |
| Missing bundle | `manifest.json` is not in the bundle directory |
| Stale bundle | `abot export-dashboard --check` exits non-zero |
| Edited or incomplete bundle | A file's size or SHA-256 differs from the manifest, a listed file is missing, or there is an extra or non-regular file |
| Audit | `status` is not `obtained`, `outcome` is not `pass` or `warn`, or `counts.fail` is not 0 |
| Unclean export | The manifest's `code.git_working_tree_clean` is not true or `git_dirty_count` is not 0 |
| Contract | The contract is not `abot-dashboard`, the major version differs from `SUPPORTED_VERSION`, or the minor version is newer |
| Source commit | `code.git_commit` is not in the repository, or is not an ancestor of HEAD |
| OSM snapshot | A file named in `provenance.json` is missing from `data/raw/`, or its SHA-256 differs |

Packaging reads `data/` and writes nothing there. It does not export, regenerate or change any
analytical output. Before writing, it runs the verifier's content checks on the archives it built.

## 5. Verification

`verify_release.py <tag> <dashboard zip> [--osm-archive <osm zip>]` exits 0 only if every check
passes. Any problem, or any unexpected error, exits 1 (fail closed). It checks, in order:

1. The tag is valid and exists. `releases/<tag>.json` is in the tag's commit, has the right schema,
   and its `tag` field matches.
2. Commit chain: source commit → `packaged_from_commit` → tag.
3. The asset name is `abot-dashboard-v1-<tag>.zip`. The file's name, size and SHA-256 match the
   record **before the archive is opened**.
4. Every entry, by safe reading (§6). Each entry's size and SHA-256 must match `assets[].contents`.
5. The SHA-256 and size of `manifest.json` match `dashboard.manifest_sha256` and `manifest_bytes`.
6. Contract compatibility with `SUPPORTED_VERSION` at the tag. The major version must be equal and the
   minor version must not be newer. A newer minor version, which the dashboard would load with a
   warning, is rejected for a release.
7. Audit (`obtained`, `pass` or `warn`, 0 failures) and the manifest's clean-tree flags.
8. The archive holds exactly the manifest-listed files, `manifest.json` and the two licence
   documents. Each listed file's size and SHA-256 must match the manifest. Each JSON/GeoJSON file's
   `contract`, `contract_version` and `generated_utc` must equal the manifest's.
9. The record's `dashboard`, `source`, `audit`, `osm` and `licences` blocks equal the values
   recomputed from the archive.
10. With `--osm-archive`: name, size and SHA-256 against the record. The entries must be exactly the
    files named in the bundle's provenance, with the SHA-256 recorded there, plus licence texts
    identical to the dashboard archive's.

## 6. Safe extraction

Archives are read in memory with Python's `zipfile`. Nothing is extracted until every check has
passed. All structural problems are reported before any content is read. An entry is rejected if:
- its path is absolute (`/x`, `C:/x`), contains `..` or `.`, has an empty segment, uses a backslash,
  contains NUL, or is a directory entry;
- it is a symbolic link or any other non-regular file (Unix mode bits);
- it duplicates another entry, including a duplicate that differs only by case;
- it is encrypted or uses a compression method other than stored or deflated;
- it is larger than 64 MiB, the archive expands to more than 256 MiB, or there are more than 64
  entries;
- it is unexpected (including an unexpected nested path), missing, of another size than recorded,
  unreadable (CRC error or truncation), or has another SHA-256.

Content is read with a byte limit of the recorded size plus one.

Installing (`fetch_bundle.py`) writes only the manifest and its listed files, with exclusive-create.
It writes them to a temporary sibling directory (`.v1.tmp-<hex>`) and re-hashes them on disk. It
then swaps that directory in with two renames (`v1` → `.v1.old-<hex>`, temporary → `v1`) and
restores the old directory if the second rename fails. These are the exporter's names, so
`abot export-dashboard` recovers an interrupted install the same way it recovers an interrupted
export. The licence documents are verified but not installed, because the repository already
contains them.

## 7. Getting the approved bundle in a fresh clone

Prerequisites:
- Git, and the tag in the local repository. A shallow clone also needs the history back to the
  bundle's source commit. In CI that means `fetch-depth: 0`.
- Python 3.13. The release scripts use only the standard library.
- Optional: the GitHub CLI (`gh`). Without it, the asset is downloaded over HTTPS from the public
  release URL.

```bash
git clone https://github.com/didyouseejay/ABOT.git && cd ABOT
git fetch --tags
python scripts/release/fetch_bundle.py v0.1.0 --dry-run      # show the plan: no network, no writes
python scripts/release/fetch_bundle.py v0.1.0 --verify-only  # download and verify only
python scripts/release/fetch_bundle.py v0.1.0                # download, verify, install into data/processed/dashboard/v1/
```

- `--archive <zip>` verifies and installs a local copy instead of downloading.
- If `data/processed/dashboard/v1/` already holds this release's bundle, nothing changes.
- If it holds a different bundle, or an incomplete or edited one, the script stops unless you pass
  `--replace`.
- An invalid archive never replaces anything.

The dashboard then runs on the installed bundle (`cd dashboard && npm ci && npm run dev`). In a
fresh clone without source data, `abot export-dashboard --check` reports the bundle as stale,
because the sources it describes are absent. That is expected.

## 8. Inspecting checksums by hand

```bash
cd dist/release/v0.1.0            # or the folder you downloaded the assets to
sha256sum -c SHA256SUMS           # Linux; macOS: shasum -a 256 -c SHA256SUMS
git show v0.1.0:releases/v0.1.0.json | python -m json.tool | less   # the expected values
```

In PowerShell: `Get-FileHash abot-dashboard-v1-v0.1.0.zip -Algorithm SHA256`. Compare the result
with `assets[].sha256` in the record **from the tag**. `SHA256SUMS` travels with the assets, so it
only detects corruption, not tampering. The tagged record detects both.

## 9. Known limitations

- **Tags are not signed.** The anchor relies on the integrity of the GitHub repository and its tags.
  Anyone with push access could publish a new tag, record and assets together. Signed tags
  (`git tag -s`) and checking them would close this gap. Not done in Phase 1.
- **The source commit is an ancestor, not the release commit.** A release can contain a bundle
  exported at an earlier commit. The current bundle was exported at `86d9797`, and later commits
  changed `src/abot/` (formatting and type annotations in M06.2C). The verifier proves only that the
  bundle's recorded commit is in the tag's history and that the bundle is byte-identical to what was
  approved. It does **not** prove that the code at the tag would regenerate the bundle.
- **Analytical reproducibility is not verified by this tooling.** No end-to-end rebuild from the
  released OSM snapshot has been run. The snapshot holds only the baseline's OSM responses. The other
  inputs (COD-AB, PSA census, WorldPop) are still downloaded by `abot fetch` and checked by
  `data/raw/manifest.json`. Cached responses used only by experiments or Milestone 01 are not
  included.
- **Draft and prerelease status** come from explicit inputs (§10). The tools do not query GitHub.
- `--with-osm-snapshot` and `fetch_bundle.py` handle one dashboard bundle (`v1`). Installing the OSM
  snapshot into `data/raw/` is a manual step after `verify_release.py --osm-archive` has passed.
- The checks need the `git` executable, and the full history between the source commit and the tag.

## 10. Release eligibility (`eligibility.py`)

`eligibility.py` decides whether a tag may be deployed. It does not depend on GitHub Actions and reads
no CI event payload. All inputs are explicit:

| Input | Meaning |
|---|---|
| `tag` | The candidate, `vMAJOR.MINOR.PATCH`. It must exist locally |
| `--releases FILE` or `-` | A JSON array with the keys `tagName` (string), `isDraft` and `isPrerelease` (booleans). This is the output of `gh release list --json tagName,isDraft,isPrerelease --limit 1000` |
| `--draft`, `--prerelease true\|false` | The candidate's own status, if known. Must agree with `--releases` if the tag is listed there |
| `--require-latest` | The candidate must be the highest published (non-draft, non-prerelease) version |
| `--allow-rollback` | With `--require-latest`, also accept an older published version. The output marks it as a rollback |
| `--require-published` | The candidate must appear in `--releases` as a published release (not a draft, not a prerelease). Added in Phase 2. The deployment workflow always passes it |

Checks:
1. Valid tag.
2. The tag exists.
3. The release record is in the tag's commit.
4. The record is valid and its `tag` matches.
5. Not a draft.
6. Not a prerelease.
7. Published, when requested.
8. Latest, when requested.

A status that no input provides is reported as `not evaluated` and is never assumed. Drafts,
prereleases and malformed tags in the list do not count as published versions. A candidate higher
than every published version counts as the latest. Exit codes: 0 eligible, 1 not eligible, 2
unusable input. `--json` prints the decision as JSON.
