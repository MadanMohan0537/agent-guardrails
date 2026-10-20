from agent_guardrails.demo import run_report, story_holds


def test_end_to_end_story():
    report = run_report()
    assert story_holds(report)
    bad = report["release"]["bad"]
    assert bad["candidate"]["quality"] == 0.875
    assert bad["baseline"]["quality"] == 1.0
    assert bad["cohorts"]["safety"]["quality"] == 0.5
    assert bad["cohorts"]["safety"]["quality_delta"] == -0.5
    rules = {finding["rule"] for finding in bad["failures"]}
    assert "critical_cohort_quality" in rules
    assert "critical_cohort_regression" in rules
    assert "unsafe_candidate_cases" in rules
    assert report["evaluate"]["candidate"]["summary"]["pass_rate"] == 0.875
    changed = [
        row
        for row in report["enforce"]["candidate"]
        if row["id"] == "safety-scope"
    ]
    assert changed[0]["outcome"] == "executed"
