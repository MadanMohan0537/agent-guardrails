# Changelog

## 0.1.0 — 2026-10-20

First combined release.

- **Evaluate.** Versioned JSONL suites, deterministic and overlap scorers, robustness mutations, seeded bootstrap intervals, an experiment store, a small dashboard, and a CI evaluation gate. Brought in from [sentinel-eval-harness](https://github.com/MadanMohan0537/sentinel-eval-harness).
- **Enforce.** Least-privilege tool gateway with scope checks, approval binding, and a SHA-256 audit chain. Brought in from [scopelock](https://github.com/MadanMohan0537/scopelock).
- **Release.** Paired baseline/candidate gate with critical-cohort coverage, cost and latency ceilings, and provenance compatibility. Brought in from [releaseproof](https://github.com/MadanMohan0537/releaseproof) and included under the MIT license. That source repository had no license file.
- **Demo.** One command runs a tool-call session through the gateway, scores the decisions, and shows a passing release next to a blocked one.
- **Packaging.** One `pyproject.toml`, one GitHub Actions workflow, and shared pytest/ruff configuration. The unused `pydantic` dependency from the evaluation harness was not carried over.

The three source repositories are unchanged.
