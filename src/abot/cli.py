"""Command-line entry point: `abot fetch | build | report | all | compare | review | validate | components |
fetch-gaps | audit | export-dashboard`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from abot.config import DEFAULT_CONFIG, load_settings

STAGES = ["boundaries", "population", "osm", "accessibility"]


def _build(s, stages: list[str]) -> None:
    # Imported lazily so `abot fetch` stays fast and light.
    if "boundaries" in stages:
        from abot import boundaries

        boundaries.build(s)
    if "population" in stages:
        from abot import population

        population.build(s)
    if "osm" in stages:
        from abot import osm

        osm.build(s)
    if "accessibility" in stages:
        from abot import accessibility

        accessibility.build(s)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="abot", description="ABOT accessibility pipeline")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to settings.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download boundaries, census and WorldPop into data/raw")
    p_fetch.add_argument("--force", action="store_true", help="re-download even if cached")

    p_build = sub.add_parser("build", help="run processing stages")
    p_build.add_argument("--only", nargs="+", choices=STAGES, default=STAGES)

    sub.add_parser("report", help="write the QA report and HTML map")
    sub.add_parser("all", help="fetch + build + report")

    p_cmp = sub.add_parser("compare", help="compare two processed-output directories")
    p_cmp.add_argument("base", type=Path, help="e.g. data/archive/m01_3edc0dd")
    p_cmp.add_argument("variant", type=Path, help="e.g. data/processed")
    p_cmp.add_argument("--name", help="output folder under data/processed/comparisons/")

    sub.add_parser(
        "review",
        help="write manual-review files (duplicates, unconnected cells) to <processed>/review; changes no data",
    )
    sub.add_parser(
        "validate",
        help="write desk-validation evidence for the review items to <processed>/review/m03; "
        "reads the Overpass cache only and changes no data",
    )
    sub.add_parser(
        "components",
        help="write walk-network component, approach-comparison and access-tag evidence to "
        "<processed>/review/m04; reads the Overpass cache only and changes no data",
    )
    p_gap = sub.add_parser(
        "fetch-gaps",
        help="build and validate the Milestone 04 targeted Overpass query (dry run unless --allow-download)",
    )
    p_gap.add_argument(
        "--allow-download", action="store_true", help="send the query once; snapshot to data/raw/osm_targeted/"
    )
    p_aud = sub.add_parser(
        "audit", help="read-only check of inputs, outputs, staleness and consistency (PASS/WARN/FAIL)"
    )
    p_aud.add_argument("--output", type=Path, help="also write the findings as Markdown (outside data/)")
    p_aud.add_argument(
        "--skip-hashes", action="store_true", help="skip SHA-256 checks of raw and archived files"
    )
    p_exp = sub.add_parser(
        "export-dashboard",
        help="write the dashboard data bundle to <processed>/dashboard/v1 (contract abot-dashboard 1.0.1); "
        "read-only over the analytical outputs",
    )
    p_exp.add_argument(
        "--skip-audit", action="store_true", help="export without running `abot audit` (recorded as not_run)"
    )
    p_exp.add_argument(
        "--check",
        action="store_true",
        help="only report whether the existing bundle is stale; writes nothing",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.command == "audit":
        from abot import audit

        # Read-only: no directory is created, nothing under data/ is written.
        s = load_settings(args.config, create_dirs=False)
        sys.exit(audit.run(s, Path(args.config), args.output, hashes=not args.skip_hashes))
    if args.command == "export-dashboard":
        from abot import dashboard_data

        # Read-only over data/: only <processed>/dashboard/ is written, and nothing at all with --check.
        s = load_settings(args.config, create_dirs=False)
        if args.check:
            sys.exit(dashboard_data.check(s))
        sys.exit(dashboard_data.export(s, Path(args.config), skip_audit=args.skip_audit))
    s = load_settings(args.config)

    if args.command in ("fetch", "all"):
        from abot.fetch.sources import fetch_all

        fetch_all(s, force=getattr(args, "force", False))
    if args.command in ("build", "all"):
        _build(s, getattr(args, "only", STAGES))
    if args.command in ("report", "all"):
        from abot import report

        report.build(s)
    if args.command == "compare":
        from abot import compare

        compare.run(s, args.base, args.variant, args.name)
    if args.command == "review":
        from abot import review

        review.build(s)
    if args.command == "validate":
        from abot import validation

        validation.build(s)
    if args.command == "components":
        from abot import components

        components.build(s)
    if args.command == "fetch-gaps":
        from abot.fetch import targeted

        result = targeted.fetch(s, allow_download=args.allow_download)
        print(result["query"])
        print(f"snapshot: {result.get('snapshot', 'none (dry run)')}")
