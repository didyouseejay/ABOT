"""Command-line entry point: `abot fetch | build | report | all`."""

from __future__ import annotations

import argparse
import logging

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
    parser = argparse.ArgumentParser(prog="abot", description="ABOT Milestone 01 pipeline")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to settings.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download boundaries, census and WorldPop into data/raw")
    p_fetch.add_argument("--force", action="store_true", help="re-download even if cached")

    p_build = sub.add_parser("build", help="run processing stages")
    p_build.add_argument("--only", nargs="+", choices=STAGES, default=STAGES)

    sub.add_parser("report", help="write the QA report and HTML map")
    sub.add_parser("all", help="fetch + build + report")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    s = load_settings(args.config)

    if args.command in ("fetch", "all"):
        from abot.fetch.sources import fetch_all

        fetch_all(s, force=getattr(args, "force", False))
    if args.command in ("build", "all"):
        _build(s, getattr(args, "only", STAGES))
    if args.command in ("report", "all"):
        from abot import report

        report.build(s)
