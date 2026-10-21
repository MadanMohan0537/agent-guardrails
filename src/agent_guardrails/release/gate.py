"""Compare versioned, case-level evaluation runs. No network or third-party dependencies.

Origin: https://github.com/MadanMohan0537/releaseproof
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import statistics
import sys
from pathlib import Path

QUALITY_FIELDS = ("correct", "grounded", "safe", "refusal_correct")
NUMERIC_FIELDS = ("latency_ms", "cost_usd")
PROVENANCE_FIELDS = ("dataset_revision", "scorer_revision", "rubric_revision")


def number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{label} is outside its allowed range")
    return value


def validate_run(run):
    if not isinstance(run, dict) or not isinstance(run.get("version"), str) or not run["version"].strip():
        raise ValueError("run requires a nonempty version string")
    provenance = run.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, dict) or set(provenance) != set(PROVENANCE_FIELDS):
            raise ValueError("provenance requires exactly dataset_revision, scorer_revision and rubric_revision")
        if any(not isinstance(value, str) or not value.strip() for value in provenance.values()):
            raise ValueError("provenance revisions must be nonempty strings")
    cases = run.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("run requires a nonempty cases list")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("case IDs must be nonempty and unique")
        seen.add(case_id)
        if not isinstance(case.get("cohort"), str) or not case["cohort"].strip():
            raise ValueError(f"{case_id}: cohort must be nonempty")
        for field in QUALITY_FIELDS:
            if not isinstance(case.get(field), bool):
                raise ValueError(f"{case_id}: {field} must be boolean")
        for field in NUMERIC_FIELDS:
            number(case.get(field), f"{case_id}: {field}")
        if not isinstance(case.get("output", ""), str):
            raise ValueError(f"{case_id}: output must be text")
    return run


def validate_policy(policy):
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")
    allowed = {"minimum_quality", "maximum_quality_drop", "maximum_p95_latency_ms",
               "maximum_cost_per_1000_usd", "critical_cohorts", "bootstrap_samples", "seed",
               "require_provenance"}
    if set(policy) - allowed:
        raise ValueError(f"unknown policy fields: {sorted(set(policy) - allowed)}")
    if not isinstance(policy.get("require_provenance", False), bool):
        raise ValueError("require_provenance must be boolean")
    for field in ("minimum_quality", "maximum_quality_drop"):
        number(policy.get(field), field, maximum=1)
    for field in ("maximum_p95_latency_ms", "maximum_cost_per_1000_usd"):
        number(policy.get(field), field)
    critical = policy.get("critical_cohorts")
    if not isinstance(critical, dict) or not critical:
        raise ValueError("declare at least one critical cohort; do not infer coverage from observed cases")
    for cohort, count in critical.items():
        if not isinstance(cohort, str) or not cohort.strip() or isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("critical cohort minima must be positive integers")
    samples = policy.get("bootstrap_samples", 2000)
    if isinstance(samples, bool) or not isinstance(samples, int) or not 100 <= samples <= 10000:
        raise ValueError("bootstrap_samples must be an integer from 100 to 10000")
    seed = policy.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    return policy


def quantile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def quality(case):
    """Strict case success: every independently supplied quality check must pass."""
    return int(all(case[field] for field in QUALITY_FIELDS))


def metrics(cases):
    return {"quality": statistics.mean(quality(case) for case in cases),
            **{field: statistics.mean(int(case[field]) for case in cases) for field in QUALITY_FIELDS},
            "p95_latency_ms": quantile([case["latency_ms"] for case in cases], .95),
            "cost_per_1000_usd": statistics.mean(case["cost_usd"] for case in cases) * 1000}


def paired_interval(deltas, samples, seed):
    rng = random.Random(seed)
    means = [statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(samples)]
    return [quantile(means, .025), quantile(means, .975)]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def compare(baseline, candidate, policy):
    validate_run(baseline)
    validate_run(candidate)
    validate_policy(policy)
    old = {case["id"]: case for case in baseline["cases"]}
    new = {case["id"]: case for case in candidate["cases"]}
    if old.keys() != new.keys():
        raise ValueError("baseline and candidate must have identical case IDs; missing results are not successes")
    if any(old[key]["cohort"] != new[key]["cohort"] for key in old):
        raise ValueError("cohort tags must remain fixed between compared runs")
    ids = sorted(old)
    old_metrics, new_metrics = metrics(list(old.values())), metrics(list(new.values()))
    failures = []
    provenance = provenance_evidence(baseline, candidate, policy)
    failures.extend(provenance.pop("failures"))
    for label, value, threshold in [("quality", new_metrics["quality"], policy["minimum_quality"]),
                                   ("quality_delta", new_metrics["quality"] - old_metrics["quality"], -policy["maximum_quality_drop"])]:
        if value < threshold - 1e-12:
            failures.append({"rule": label, "observed": value, "required_minimum": threshold})
    for field, limit in [("p95_latency_ms", policy["maximum_p95_latency_ms"]),
                         ("cost_per_1000_usd", policy["maximum_cost_per_1000_usd"])]:
        if new_metrics[field] > limit + 1e-12:
            failures.append({"rule": field, "observed": new_metrics[field], "maximum": limit})
    unsafe_ids = [key for key in ids if not new[key]["safe"]]
    if unsafe_ids:
        failures.append({"rule": "unsafe_candidate_cases", "case_ids": unsafe_ids})
    cohorts = {}
    for cohort in sorted({case["cohort"] for case in new.values()} | set(policy["critical_cohorts"])):
        cohort_ids = [key for key in ids if new[key]["cohort"] == cohort]
        required = policy["critical_cohorts"].get(cohort, 0)
        cohort_delta = statistics.mean(quality(new[key]) - quality(old[key]) for key in cohort_ids) if cohort_ids else None
        cohort_quality = statistics.mean(quality(new[key]) for key in cohort_ids) if cohort_ids else None
        cohorts[cohort] = {"count": len(cohort_ids), "required_count": required,
                           "coverage_debt": max(0, required - len(cohort_ids)),
                           "quality": cohort_quality, "quality_delta": cohort_delta}
        if len(cohort_ids) < required:
            failures.append({"rule": "critical_cohort_coverage", "cohort": cohort,
                             "observed": len(cohort_ids), "required": required})
        if required and cohort_ids:
            if cohort_quality < policy["minimum_quality"] - 1e-12:
                failures.append({"rule": "critical_cohort_quality", "cohort": cohort, "observed": cohort_quality})
            if cohort_delta < -policy["maximum_quality_drop"] - 1e-12:
                failures.append({"rule": "critical_cohort_regression", "cohort": cohort, "observed": cohort_delta})
    deltas = [quality(new[key]) - quality(old[key]) for key in ids]
    interval = paired_interval(deltas, policy.get("bootstrap_samples", 2000), policy.get("seed", 0))
    differences = [{"id": key, "cohort": new[key]["cohort"], "baseline_success": bool(quality(old[key])),
                    "candidate_success": bool(quality(new[key])),
                    "changed_checks": [field for field in QUALITY_FIELDS if old[key][field] != new[key][field]],
                    "baseline_output": old[key].get("output", ""), "candidate_output": new[key].get("output", "")}
                   for key in ids if old[key] != new[key]]
    return {"schema_version": 1, "decision": "BLOCK" if failures else "PASS",
            "baseline_version": baseline["version"], "candidate_version": candidate["version"],
            "case_count": len(ids), "baseline": old_metrics, "candidate": new_metrics,
            "paired": {"improved": sum(delta > 0 for delta in deltas), "regressed": sum(delta < 0 for delta in deltas),
                       "unchanged": sum(delta == 0 for delta in deltas), "quality_delta": statistics.mean(deltas),
                       "bootstrap_95_interval": interval, "seed": policy.get("seed", 0),
                       "samples": policy.get("bootstrap_samples", 2000),
                       "interpretation": "Descriptive case-resampling interval; no repeated model-run uncertainty or production-safety guarantee."},
            "cohorts": cohorts, "failures": failures, "differences": differences,
            "provenance": provenance,
            "evidence_hashes": {"baseline": digest(baseline), "candidate": digest(candidate), "policy": digest(policy)}}


def provenance_evidence(baseline, candidate, policy):
    """Compare declared evaluation context, never candidate model/prompt identity."""
    old, new = baseline.get("provenance"), candidate.get("provenance")
    missing = [name for name, value in (("baseline", old), ("candidate", new)) if value is None]
    changes = [field for field in PROVENANCE_FIELDS if old and new and old[field] != new[field]]
    failures = []
    # Once either producer declares provenance, silently falling back is unsafe.
    if missing and (policy.get("require_provenance", False) or len(missing) != 2):
        failures.append({"rule": "missing_provenance", "runs": missing})
    if changes:
        failures.append({"rule": "incomparable_provenance", "fields": changes})
    return {"status": "blocked" if failures else "unverified" if missing else "matched",
            "baseline": old, "candidate": new, "changed_fields": changes,
            "interpretation": "Self-declared revisions; matching metadata is not authentication.",
            "failures": failures}


def render_html(report):
    def escape(value: object) -> str:
        return html.escape(str(value))
    rows = "".join(f"<tr><td>{escape(name)}</td><td>{data['count']}</td><td>{data['required_count']}</td>"
                   f"<td>{data['coverage_debt']}</td><td>{escape(data['quality'])}</td><td>{escape(data['quality_delta'])}</td></tr>"
                   for name, data in report["cohorts"].items())
    diffs = "".join(f"<article><h3>{escape(item['id'])} · {escape(item['cohort'])}</h3>"
                    f"<p>Changed checks: {escape(', '.join(item['changed_checks']) or 'timing, cost or output only')}</p>"
                    f"<h4>Baseline</h4><pre>{escape(item['baseline_output'])}</pre>"
                    f"<h4>Candidate</h4><pre>{escape(item['candidate_output'])}</pre></article>"
                    for item in report["differences"])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Release gate · {escape(report['decision'])}</title><style>
body{{font:16px system-ui,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px;color:#152b38;background:#f5f8fa}}
h1{{font-size:42px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:12px;border-bottom:1px solid #dce5eb;text-align:left}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#e8eff4;padding:16px;border-radius:8px}}article{{background:white;padding:18px;margin:18px 0;border-radius:12px}}
.decision{{display:inline-block;padding:8px 20px;border-radius:20px;background:{'#ffd3c7' if report['decision']=='BLOCK' else '#c8f0d9'}}}
</style><main><p>Agent Guardrails · Release evidence</p><h1>Release gate</h1>
<h2 class="decision">{escape(report['decision'])}</h2><p>{escape(report['baseline_version'])} → {escape(report['candidate_version'])} · {report['case_count']} matched cases</p>
<h2>Evaluation evidence</h2><pre>{escape(json.dumps({'baseline':report['baseline'],'candidate':report['candidate'],'paired':report['paired']},indent=2))}</pre>
<h2>Policy findings</h2><pre>{escape(json.dumps(report['failures'],indent=2))}</pre>
<h2>Evaluation provenance</h2><pre>{escape(json.dumps(report['provenance'],indent=2))}</pre>
<h2>Critical cohort coverage</h2><table><thead><tr><th>Cohort</th><th>Cases</th><th>Required</th><th>Debt</th><th>Quality</th><th>Delta</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Case differences</h2>{diffs or '<p>No case differences.</p>'}
<h2>Evidence hashes</h2><pre>{escape(json.dumps(report['evidence_hashes'],indent=2))}</pre>
<p>A pass means this recorded evaluation satisfied this policy. It does not certify production safety. Quality labels are supplied by your independent scorer.</p></main></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("report.json"))
    parser.add_argument("--html", type=Path)
    args = parser.parse_args(argv)
    try:
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"))
        report = compare(read(args.baseline), read(args.candidate), read(args.policy))
        for path in [args.report, args.html]:
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if args.html:
            args.html.write_text(render_html(report), encoding="utf-8")
        print(f"{report['decision']}: {report['case_count']} paired cases, {len(report['failures'])} policy findings")
        return 1 if report["decision"] == "BLOCK" else 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Invalid evaluation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

