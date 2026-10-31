"""ABOT — geospatial accessibility and public infrastructure intelligence for Iloilo City."""

__version__ = "0.1.0"


def main() -> None:
    from abot.cli import main as cli_main

    cli_main()
