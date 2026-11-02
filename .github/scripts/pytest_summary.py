"""Markdown summary of a pytest JUnit XML report, for the GitHub Actions job summary.

Usage: python pytest_summary.py pytest-results.xml
Writes to $GITHUB_STEP_SUMMARY when set, otherwise to stdout. Standard library only. The summary only
reports; whether the job passes is decided by the pytest step itself.
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def first_line(text: str | None) -> str:
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


def summarise(xml_path: Path) -> str:
    if not xml_path.exists():
        return f"## Python tests\n\n:x: No test report found at `{xml_path}`: pytest did not complete.\n"
    root = ET.parse(xml_path).getroot()
    cases = list(root.iter("testcase"))
    failed, errored, skipped = [], [], defaultdict(list)
    for case in cases:
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        if (el := case.find("failure")) is not None:
            failed.append((name, first_line(el.get("message")) or first_line(el.text)))
        elif (el := case.find("error")) is not None:
            errored.append((name, first_line(el.get("message")) or first_line(el.text)))
        elif (el := case.find("skipped")) is not None:
            skipped[first_line(el.get("message")) or "no reason given"].append(name)
    n_skipped = sum(len(v) for v in skipped.values())
    passed = len(cases) - len(failed) - len(errored) - n_skipped
    ok = not failed and not errored
    lines = [
        "## Python tests",
        "",
        f"{':white_check_mark:' if ok else ':x:'} **{'All tests passed' if ok else 'Tests failed'}**",
        "",
        "| Total | Passed | Failed | Errors | Skipped |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(cases)} | {passed} | {len(failed)} | {len(errored)} | {n_skipped} |",
    ]
    for title, items in (("Failed", failed), ("Errors", errored)):
        if items:
            lines += ["", f"### {title}", ""] + [f"- `{n}`: {m}" for n, m in items]
    if skipped:
        lines += [
            "",
            "### Skipped tests",
            "",
            (
                "CI has no `data/` directory (analytical outputs, archives and the dashboard bundle are local "
                "and git-ignored), so tests that read them skip by design."
            ),
            "",
            "| Reason | Tests |",
            "|---|---|",
        ]
        lines += [
            f"| {reason} | {', '.join(f'`{n}`' for n in names)} |"
            for reason, names in sorted(skipped.items())
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = summarise(Path(argv[1] if len(argv) > 1 else "pytest-results.xml"))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
