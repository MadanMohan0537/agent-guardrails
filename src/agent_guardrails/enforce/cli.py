from __future__ import annotations

import argparse
import json
from pathlib import Path

from .demo import run_demo


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scopelock", description="Run the local ScopeLock policy gateway demo")
    parser.add_argument("--db", default=".agent-guardrails/audit.db", help="SQLite audit log path")
    parser.add_argument("--json", help="optional report output path")
    args = parser.parse_args(argv)
    if args.db != ":memory:":
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    report = run_demo(args.db)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
