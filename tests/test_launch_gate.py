import copy
import json
import tempfile
import unittest
from pathlib import Path

from agent_guardrails.release.gate import compare, main, render_html

ROOT = Path(__file__).resolve().parents[1]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.baseline = json.loads((ROOT / "examples/baseline.json").read_text())
        self.candidate = copy.deepcopy(self.baseline)
        self.candidate["version"] = "test-candidate"
        self.policy = json.loads((ROOT / "examples/policy.json").read_text())

    def run_gate(self):
        return compare(self.baseline, self.candidate, self.policy)

    def test_identical_passes(self):
        report = self.run_gate()
        self.assertEqual(report["decision"], "PASS")
        self.assertEqual(report["paired"]["bootstrap_95_interval"], [0, 0])

    def test_quality_regression_blocks(self):
        self.policy["maximum_quality_drop"] = .1
        self.candidate["cases"][0]["correct"] = False
        self.assertEqual(self.run_gate()["decision"], "BLOCK")

    def test_small_noncritical_drop_within_policy_passes(self):
        self.candidate["cases"][0]["correct"] = False
        self.assertEqual(self.run_gate()["decision"], "PASS")

    def test_removing_cases_from_both_runs_leaves_debt(self):
        self.candidate["cases"].pop()
        self.baseline["cases"].pop()
        report = self.run_gate()
        self.assertEqual(report["cohorts"]["safety"]["coverage_debt"], 1)
        self.assertEqual(report["decision"], "BLOCK")

    def test_safety_failure_cannot_be_averaged_away(self):
        self.policy["minimum_quality"] = 0
        self.policy["maximum_quality_drop"] = 1
        self.candidate["cases"][0]["safe"] = False
        self.assertIn("unsafe_candidate_cases", [f["rule"] for f in self.run_gate()["failures"]])

    def test_critical_cohort_failure_despite_good_aggregate(self):
        self.policy["minimum_quality"] = .7
        self.policy["maximum_quality_drop"] = .2
        self.candidate["cases"][-1]["correct"] = False
        report = self.run_gate()
        self.assertGreaterEqual(report["candidate"]["quality"], .7)
        self.assertIn("critical_cohort_regression", [f["rule"] for f in report["failures"]])

    def test_coverage_debt_blocks_even_with_perfect_quality(self):
        self.policy["critical_cohorts"]["unobserved-critical"] = 2
        report = self.run_gate()
        self.assertEqual(report["cohorts"]["unobserved-critical"]["coverage_debt"], 2)
        self.assertEqual(report["decision"], "BLOCK")

    def test_missing_case_is_invalid(self):
        self.candidate["cases"].pop()
        with self.assertRaisesRegex(ValueError, "identical case IDs"):
            self.run_gate()

    def test_duplicate_case_is_invalid(self):
        self.candidate["cases"].append(self.candidate["cases"][0])
        with self.assertRaisesRegex(ValueError, "unique"):
            self.run_gate()

    def test_cohort_changes_are_invalid(self):
        self.candidate["cases"][0]["cohort"] = "other"
        with self.assertRaisesRegex(ValueError, "tags must remain fixed"):
            self.run_gate()

    def test_boolean_labels_are_required(self):
        self.candidate["cases"][0]["correct"] = "true"
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.run_gate()

    def test_nonfinite_numbers_rejected(self):
        for invalid in [float("nan"), float("inf"), -1, True]:
            with self.subTest(invalid=invalid):
                self.candidate["cases"][0]["cost_usd"] = invalid
                with self.assertRaises(ValueError):
                    self.run_gate()

    def test_latency_and_cost_limits(self):
        for field in ["latency_ms", "cost_usd"]:
            with self.subTest(field=field):
                self.setUp()
                for case in self.candidate["cases"]:
                    case[field] = 100000
                self.assertEqual(self.run_gate()["decision"], "BLOCK")

    def test_policy_typo_rejected(self):
        self.policy["minimun_quality"] = 1
        with self.assertRaisesRegex(ValueError, "unknown policy"):
            self.run_gate()

    def test_pairing_is_order_invariant(self):
        expected = self.run_gate()
        self.candidate["cases"].reverse()
        actual = self.run_gate()
        self.assertEqual(expected["paired"], actual["paired"])

    def test_refusal_quality_is_required(self):
        self.candidate["cases"][0]["refusal_correct"] = False
        self.assertEqual(self.run_gate()["paired"]["regressed"], 1)

    def test_output_is_html_escaped(self):
        self.candidate["cases"][0]["output"] = '<script>alert("x")</script>'
        rendered = render_html(self.run_gate())
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_reproducibility_and_hash_changes(self):
        self.candidate["cases"][0]["correct"] = False
        a = self.run_gate()
        self.assertEqual(a, self.run_gate())
        self.policy["seed"] += 1
        self.assertNotEqual(a["evidence_hashes"]["policy"], self.run_gate()["evidence_hashes"]["policy"])

    def test_cli_exit_codes_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "nested/report.json"
            page = Path(tmp) / "report.html"
            args = [str(ROOT / "examples/baseline.json"), str(ROOT / "examples/candidate-good.json"),
                    "--policy", str(ROOT / "examples/policy.json"), "--report", str(report), "--html", str(page)]
            self.assertEqual(main(args), 0)
            self.assertTrue(page.exists())
            args[1] = str(ROOT / "examples/candidate-bad.json")
            self.assertEqual(main(args), 1)
            self.assertEqual(json.loads(report.read_text())["decision"], "BLOCK")
            args[1] = str(Path(tmp) / "missing.json")
            self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
