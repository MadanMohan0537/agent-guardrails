"""Unified command line for evaluate, enforce, release, and the end-to-end demo."""

from __future__ import annotations

import sys

HELP = """Agent Guardrails

  agent-guardrails demo                 run the enforce → evaluate → release demo
  agent-guardrails eval run <dataset>   score a versioned JSONL suite
  agent-guardrails enforce              run the local tool-gateway demo
  agent-guardrails release BASE CAND --policy POLICY

Module commands are also installed as sentinel-eval, scopelock, and releaseproof.
"""


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(HELP)
        raise SystemExit(0)
    command, rest = args[0], args[1:]
    if command == "demo":
        from agent_guardrails.demo import main as demo_main

        raise SystemExit(demo_main(rest))
    if command == "eval":
        from agent_guardrails.evaluate.cli import main as eval_main

        eval_main(rest)
        return
    if command == "enforce":
        from agent_guardrails.enforce.cli import main as enforce_main

        enforce_main(rest)
        return
    if command == "release":
        from agent_guardrails.release.gate import main as release_main

        raise SystemExit(release_main(rest))
    print(HELP, file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
