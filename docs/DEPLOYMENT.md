# Deploying the ABOT dashboard

Milestone 06.3 Phase 2. The public dashboard is a static site on Vercel. It is deployed by
[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml), and only from a published GitHub
Release whose bundle passes verification against the release record committed at its tag. The
release record, asset formats and verification rules are described in
[releases/README.md](../releases/README.md).

**Status:** the workflow and tooling are in the repository. Nothing has been deployed. The Vercel
project, its secrets and the first release are manual steps for the maintainer (§2, §3).

## 1. What happens on a deployment

| Step | Tool | Fails if |
|---|---|---|
| 1. Validate the tag | shell (same pattern as `release_lib.TAG_RE`) | the tag is not `vMAJOR.MINOR.PATCH` |
| 2. Check out the tag, full history | `actions/checkout` (`fetch-depth: 0`, no persisted credentials) | the tag does not exist |
| 3. Eligibility | `eligibility.py --require-published --require-latest [--allow-rollback]` | there is no record at the tag, or the release is a draft, a prerelease, unpublished, or older than the latest published release (unless a rollback is allowed) |
| 4. Download, verify, install | `fetch_bundle.py <tag>` (uses `gh` and the job's read-only token) | any check in releases/README.md §5 fails; nothing is installed |
| 5. Type-check, test, build | `npm ci`, `npm run typecheck`, `npm test`, `npm run build` | any check fails |
| 6. Prepare the prebuilt output | `prepare_deploy.py <tag>` | `dist/data/v1/` is not exactly the release's verified bundle, or `index.html` is missing |
| 7. Deploy | `vercel deploy --prebuilt --prod` (Vercel CLI pinned to 65.10.0) | a secret is missing or the upload fails |
| 8. Live check (optional) | `check_live.py <tag> $ABOT_SITE_URL` | the site does not serve the release's `manifest.json` with the expected security headers within about a minute |

Points to note:
- **Vercel builds nothing.** The workflow uploads a Build Output API v3 directory
  (`.vercel/output/static/` plus `config.json`), so the deployed bytes are the ones the workflow
  verified. The root [`vercel.json`](../vercel.json) also sets `git.deploymentEnabled: false`. If
  the project is ever connected to Git, a push still cannot trigger a build that would have no data.
- **The bundle is checked three times.** `fetch_bundle.py` checks it against the tagged record. The
  Vite plugin checks each file against the manifest as it copies it into the build.
  `prepare_deploy.py` checks the build against the tagged record again.
- **Credentials:**
  - The job token is read-only (`contents: read`).
  - Vercel secrets reach only the deploy step, through `env`.
  - Every `${{ }}` value used by a script is passed through `env`, never written into the script
    text. This guards against script injection through a tag name.
  - All actions are pinned to commit SHAs, the same pins as `ci.yml`.
  - `tests/test_deploy.py` checks these properties.
- **One deployment at a time.** Concurrency group `deploy-production`. A queued run waits and never
  cancels an upload in progress.

### Headers

`prepare_deploy.py` writes these response headers into `config.json`:

| Path | Headers |
|---|---|
| all | `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'` |
| all | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()`, `Cross-Origin-Opener-Policy: same-origin` |
| `/assets/*` (file names contain content hashes) | `Cache-Control: public, max-age=31536000, immutable` |
| `/data/v1/*` | `Cache-Control: public, max-age=0, must-revalidate` |

The CSP was tested on the production build of the real bundle in Chrome, served locally with
exactly these headers. Every page (Home, Map, Barangays, Facilities, Network, Data quality,
Methodology, About) rendered, all 24 visible street-map tiles loaded, and there were no
`securitypolicyviolation` events and no console errors. Inline styles are allowed because Leaflet
and React set element styles. Inline scripts are not allowed.

## 2. One-time setup (maintainer)

These steps are done in the Vercel and GitHub web interfaces. They cannot be scripted from this
repository.

1. **Vercel project.** Create a project (framework preset "Other") **without connecting a Git
   repository**. Note the project ID and the team or user ID (Project → Settings → General).
2. **Vercel token.** Create a token scoped to that team (Account → Settings → Tokens). Give it an
   expiry date.
3. **GitHub environment.** Repository → Settings → Environments → New environment named
   `production`.
   - Optional but recommended: add yourself as a required reviewer, so every deployment waits for
     your approval.
   - Restrict "Deployment branches and tags" to tags matching `v*`.
4. **Secrets** in the `production` environment: `VERCEL_TOKEN`, `VERCEL_ORG_ID` (team or user ID),
   `VERCEL_PROJECT_ID`.
5. **Optional variable:** `ABOT_SITE_URL` (Repository → Settings → Variables), for example
   `https://<project>.vercel.app` or your own domain. When it is set, the workflow checks the live
   site after each deployment. When it is not set, that step is skipped with a notice.
6. **Deployment Protection.** Vercel's default protection may require a login for deployment URLs.
   The production domain stays public, but check this after the first deployment. If you set
   `ABOT_SITE_URL`, use the public production domain.

## 3. Publishing a release (which deploys it)

From a clean `main` that contains the current bundle:

```bash
uv run python scripts/release/pack_release.py v0.1.0 --with-osm-snapshot
git add releases/v0.1.0.json
git commit -m "Release record v0.1.0"
git tag -a v0.1.0 -m "ABOT v0.1.0"
uv run python scripts/release/verify_release.py v0.1.0 dist/release/v0.1.0/abot-dashboard-v1-v0.1.0.zip \
    --osm-archive dist/release/v0.1.0/abot-osm-snapshot-v0.1.0.zip
git push origin main v0.1.0
gh release create v0.1.0 --verify-tag --title "ABOT v0.1.0" --notes-file <notes.md> \
    dist/release/v0.1.0/abot-dashboard-v1-v0.1.0.zip \
    dist/release/v0.1.0/abot-osm-snapshot-v0.1.0.zip \
    dist/release/v0.1.0/SHA256SUMS
```

`gh release create` publishes the release, and publishing triggers the deployment. The release
needs its assets **when it is published**, because the workflow downloads them at once. If you
prefer to draft first: create the release with `--draft`, upload the assets, check them, then
publish (`gh release edit v0.1.0 --draft=false`). A prerelease (`--prerelease`) is never deployed.
The release notes should carry the ODbL notice (see [LICENSE-DATA.md](../LICENSE-DATA.md)).

## 4. Rollback and redeploy

Actions → Deploy → Run workflow:
- **Redeploy** the latest release: enter its tag and leave `allow_rollback` unticked.
- **Roll back:** enter an older published tag and tick `allow_rollback`. Without the tick,
  eligibility refuses any release older than the latest published one.

The equivalent command is `gh workflow run deploy.yml -f tag=v0.1.0 -f allow_rollback=true`.

Rolling back deploys the older release's own verified bundle and the dashboard code at its tag.
It does not change which release GitHub marks as latest, so a later run without `allow_rollback`
returns to the latest release.

## 5. Checking a deployment by hand

```bash
python scripts/release/check_live.py v0.1.0 https://<your-site>
curl -sI https://<your-site>/ | grep -i -E "content-security-policy|x-content-type"
```

`check_live.py` compares the SHA-256 of `/data/v1/manifest.json` with `releases/v0.1.0.json` at the
tag. The dashboard's own Data quality page also shows the bundle's contract version and audit
status.

## 6. Known limitations

- **The workflow has not run yet.** Its first real run needs the Vercel project, the secrets and a
  published release. Its safety properties are checked statically (`tests/test_deploy.py`), and
  every script it calls is tested, but GitHub Actions and Vercel behaviour are not covered by tests.
- **Vercel CLI behaviour is assumed from Vercel's documentation.** `vercel pull`, then
  `vercel deploy --prebuilt --prod` with `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`, and the Build
  Output API v3 `routes` with `continue` and `handle: filesystem`. Version 65.10.0 is pinned.
  Upgrade it deliberately.
- **Source maps are deployed** (`build.sourcemap: true`; audit finding L6). The code is public under
  MIT, so this exposes nothing new, but it does make the deployment larger.
- **Deployment approval** depends on the environment protection rules you configure (§2.3). Without
  a required reviewer, publishing a release deploys it immediately.
- The limitations of the release tooling also apply: unsigned tags, and the bundle's source commit
  is an ancestor of the release, not the release commit itself (releases/README.md §9).
