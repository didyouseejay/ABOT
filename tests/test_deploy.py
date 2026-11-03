"""Tests for the M06.3 Phase 2 deployment pieces (docs/DEPLOYMENT.md).

prepare_deploy.py and check_live.py run on synthetic releases built with the Phase 1 helpers in
tests/test_release.py, with no real data and no network. The workflow tests read
.github/workflows/deploy.yml and check its safety properties. They cannot run it: the deployment
itself needs GitHub, a published release and Vercel credentials.
"""

import json
import re
import shutil
from email.message import Message
from pathlib import Path

import check_live as L
import eligibility as E
import prepare_deploy as D
import pytest
import release_lib as R
import yaml

from test_release import TAG, pack, publish, rel, status
from test_release import setup as release_repo

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"


@pytest.fixture
def released(tmp_path) -> Path:
    repo = release_repo(tmp_path)
    pack(repo)
    publish(repo)
    return repo


def make_dist(repo: Path, tmp: Path) -> Path:
    """What `npm run build` produces after fetch_bundle.py installed the release bundle."""
    dist = tmp / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><script type=module src=./assets/a.js></script>", encoding="utf-8"
    )
    (dist / "assets" / "a.js").write_text("console.log(1)", encoding="utf-8")
    bundle = repo / R.BUNDLE_REL
    shutil.copytree(bundle, dist / D.DATA_PREFIX)
    return dist


def refused(repo: Path, dist: Path, out: Path) -> str:
    with pytest.raises(R.ReleaseError) as ei:
        D.prepare(repo, TAG, dist, out)
    assert not (out / "config.json").exists()
    return " | ".join(ei.value.problems)


# --- prepare_deploy -----------------------------------------------------------------------------


def test_prepare_writes_build_output(released, tmp_path):
    dist = make_dist(released, tmp_path)
    out = tmp_path / "site" / ".vercel" / "output"
    D.prepare(released, TAG, dist, out)
    copied = {p.relative_to(out / "static").as_posix() for p in (out / "static").rglob("*") if p.is_file()}
    assert copied == {p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file()}
    cfg = json.loads((out / "config.json").read_bytes())
    assert cfg["version"] == 3 and cfg["routes"][-1] == {"handle": "filesystem"}
    assert all(r.get("continue") for r in cfg["routes"][:-1])
    headers = cfg["routes"][-2]["headers"]
    assert headers["Content-Security-Policy"] == D.CSP and headers["X-Frame-Options"] == "DENY"
    assert D.main([TAG, "--repo", str(released), "--dist", str(dist), "--out", str(tmp_path / "o2")]) == 0


def test_csp_allows_no_inline_or_third_party_scripts():
    directives = {name: value for name, value in (d.split(" ", 1) for d in D.CSP.split("; "))}
    assert directives["script-src"] == "'self'"
    assert directives["connect-src"] == "'self'" and directives["frame-ancestors"] == "'none'"
    assert directives["img-src"] == "'self' data: https://tile.openstreetmap.org"


def test_build_without_data_is_refused(released, tmp_path):
    dist = make_dist(released, tmp_path)
    shutil.rmtree(dist / D.DATA_PREFIX)
    assert "the build has no data" in refused(released, dist, tmp_path / "out")


def test_build_with_another_bundle_is_refused(released, tmp_path):
    dist = make_dist(released, tmp_path)
    m = json.loads((dist / D.DATA_PREFIX / R.MANIFEST).read_bytes())
    m["generated_utc"] = "2030-01-01T00:00:00+00:00"
    (dist / D.DATA_PREFIX / R.MANIFEST).write_text(json.dumps(m), encoding="utf-8")
    assert f"is not the manifest of release {TAG}" in refused(released, dist, tmp_path / "out")


def test_build_with_edited_extra_or_missing_data_is_refused(released, tmp_path):
    dist = make_dist(released, tmp_path)
    data = dist / D.DATA_PREFIX
    (data / "city.json").write_bytes(b"{}")
    (data / "extra.json").write_bytes(b"{}")
    (data / "cells-001.geojson").unlink()
    out = refused(released, dist, tmp_path / "out")
    assert (
        "city.json differs" in out
        and "unexpected entry extra.json" in out
        and "cells-001.geojson missing" in out
    )


def test_build_without_index_or_into_a_used_output_is_refused(released, tmp_path):
    dist = make_dist(released, tmp_path)
    (dist / "index.html").unlink()
    assert "index.html missing" in refused(released, dist, tmp_path / "out")
    dist = make_dist(released, tmp_path / "b")
    out = tmp_path / "used"
    out.mkdir()
    (out / "old.txt").write_text("x", encoding="utf-8")
    assert "is not empty" in refused(released, dist, out)


def test_unknown_release_is_refused(released, tmp_path):
    dist = make_dist(released, tmp_path)
    with pytest.raises(R.ReleaseError, match="does not exist"):
        D.prepare(released, "v9.9.9", dist, tmp_path / "out")


# --- check_live ---------------------------------------------------------------------------------


def fake_site(manifest: bytes, headers: dict[str, str]):
    calls: list[str] = []

    def fetch(url: str) -> tuple[bytes, Message]:
        calls.append(url)
        msg = Message()
        for k, v in headers.items():
            msg[k] = v
        return (manifest if url.endswith("/manifest.json") else b"<html>"), msg

    return fetch, calls


def test_live_site_serving_the_release_passes(released):
    manifest = (released / R.BUNDLE_REL / R.MANIFEST).read_bytes()
    fetch, calls = fake_site(manifest, D.SECURITY_HEADERS)
    L.check(released, TAG, "https://abot.example.org/", fetch=fetch, attempts=1)
    assert calls == ["https://abot.example.org/data/v1/manifest.json", "https://abot.example.org/"]


def test_live_site_with_another_bundle_or_headers_fails(released):
    fetch, _ = fake_site(b"{}", D.SECURITY_HEADERS)
    with pytest.raises(R.ReleaseError, match="not this release's manifest"):
        L.check(released, TAG, "https://abot.example.org", fetch=fetch, attempts=2, wait=0)
    manifest = (released / R.BUNDLE_REL / R.MANIFEST).read_bytes()
    fetch, _ = fake_site(manifest, {"X-Content-Type-Options": "nosniff"})
    with pytest.raises(R.ReleaseError, match="Content-Security-Policy"):
        L.check(released, TAG, "https://abot.example.org", fetch=fetch, attempts=1)


def test_live_check_rejects_bad_urls_and_network_errors(released):
    for url in ("abot.example.org", "ftp://abot.example.org", "https://abot.example.org/?x=1", "https://"):
        with pytest.raises(R.ReleaseError, match="must be an http"):
            L.check(released, TAG, url, attempts=1)

    def down(url: str) -> tuple[bytes, Message]:
        raise OSError("connection refused")

    with pytest.raises(R.ReleaseError, match="request failed"):
        L.check(released, TAG, "https://abot.example.org", fetch=down, attempts=1)


# --- eligibility: published ---------------------------------------------------------------------


def test_require_published(released):
    assert E.evaluate(released, TAG, releases=[rel(TAG)], require_published=True).eligible
    for releases in ([], [rel("v0.9.0")], [rel(TAG, draft=True)], [rel(TAG, pre=True)], None):
        d = E.evaluate(released, TAG, releases=releases, require_published=True)
        assert not d.eligible and status(d, "published") == E.FAIL
    assert status(E.evaluate(released, TAG), "published") == E.SKIP


# --- the workflow -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps(wf: dict) -> list[dict]:
    return wf["jobs"]["deploy"]["steps"]


def step(wf: dict, name_part: str) -> dict:
    return next(s for s in steps(wf) if name_part in s.get("name", ""))


def test_workflow_triggers_and_permissions(wf):
    on = wf.get("on", wf.get(True))  # PyYAML reads the key `on` as True
    assert on["release"] == {"types": ["published"]}
    assert set(on["workflow_dispatch"]["inputs"]) == {"tag", "allow_rollback"}
    assert on["workflow_dispatch"]["inputs"]["allow_rollback"]["default"] is False
    assert wf["permissions"] == {"contents": "read"}
    assert "permissions" not in wf["jobs"]["deploy"]
    assert wf["concurrency"]["cancel-in-progress"] is False
    assert wf["jobs"]["deploy"]["environment"] == "production"


def test_workflow_actions_are_pinned_and_scripts_take_no_expressions(wf):
    for s in steps(wf):
        if "uses" in s:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", s["uses"]), s["uses"]
        if "run" in s:
            assert "${{" not in s["run"], f"expression interpolated into a script: {s['name']}"


def test_workflow_tag_rule_matches_the_release_tools(wf):
    run = step(wf, "Validate the release tag")["run"]
    pattern = re.search(r"re='([^']+)'", run)
    assert pattern and pattern.group(1) == f"^{R.TAG_RE.pattern}$"


def test_workflow_order_and_gates(wf):
    names = [s["name"] for s in steps(wf)]
    order = [
        "Validate",
        "Check out",
        "eligibility",
        "verify and install",
        "build the dashboard",
        "Prepare",
        "Deploy to Vercel",
        "live site",
    ]
    idx = [next(i for i, n in enumerate(names) if part in n) for part in order]
    assert idx == sorted(idx)
    checkout = step(wf, "Check out")["with"]
    assert checkout["fetch-depth"] == 0 and checkout["persist-credentials"] is False
    elig = step(wf, "eligibility")["run"]
    assert "--require-published --require-latest" in elig
    assert 'if [ "$ALLOW_ROLLBACK" = "true" ]; then args+=(--allow-rollback); fi' in elig
    deploy = step(wf, "Deploy to Vercel")
    assert "vercel deploy --prebuilt --prod" in deploy["run"]
    assert re.search(r"vercel@\d+\.\d+\.\d+\s", deploy["run"])


def test_workflow_secrets_only_reach_the_deploy_step(wf):
    for s in steps(wf):
        text = json.dumps(s)
        if "secrets." in text:
            assert s["name"] == "Deploy to Vercel (production)"
            assert set(s["env"]) >= {"VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"}


def test_vercel_git_deployments_are_disabled():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["git"]["deploymentEnabled"] is False
