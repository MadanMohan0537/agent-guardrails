# Contributing

Thanks for helping improve Agent Guardrails. The toolkit has three modules:

- `evaluate` scores a versioned case suite
- `enforce` decides whether an agent may call a tool
- `release` compares a baseline run with a candidate and returns PASS or BLOCK

## Setup

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Checks

Run these from the repository root before opening a pull request:

```bash
ruff check src tests examples worker
pytest
sentinel-eval run datasets/product_support.jsonl --mutations --min-pass-rate 0.80
agent-guardrails demo
```

`pytest` collects both pytest-style tests and `unittest.TestCase` suites. The evaluation command exits `2` when the gate fails. The release command exits `1` when policy findings block a candidate.

## Pull requests

- Explain which decision the change improves: a score, a denial, an approval, or a release finding.
- Add a regression test when behavior changes. Prefer a small synthetic fixture over a live model.
- Keep new dependencies justified. The enforce and release modules stay on the Python standard library.
- Do not put secrets, customer content, or credentials in fixtures, reports, or revision strings.
- Do not add metrics to the README unless you produced them by running a command in this repository, and label demo data as demo data.

## Scope of this repository

This is a local reference toolkit. A passing gate means the supplied cases met the supplied policy. It is not a certification of model safety. See [docs/threat-model.md](docs/threat-model.md) for what the gateway does and does not defend against.

## License

By contributing, you agree that your contributions are licensed under the MIT license in [LICENSE](LICENSE).
