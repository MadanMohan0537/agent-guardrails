"""Command-line entry point for the release gate."""

from __future__ import annotations

from .gate import main as gate_main


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(gate_main(argv))


if __name__ == "__main__":
    main()
