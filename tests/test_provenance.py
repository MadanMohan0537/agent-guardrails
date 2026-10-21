import copy
import json
import unittest
from pathlib import Path

from agent_guardrails.release.gate import compare, render_html

ROOT = Path(__file__).resolve().parents[1]


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.baseline = json.loads((ROOT / "examples/baseline.json").read_text())
        self.candidate = copy.deepcopy(self.baseline)
        self.policy = json.loads((ROOT / "examples/policy.json").read_text())
        self.context = {"dataset_revision": "faq-v1", "scorer_revision": "checks-v1",
                        "rubric_revision": "rubric-v1"}

    def run_gate(self):
        return compare(self.baseline, self.candidate, self.policy)

    def declare(self):
        self.baseline["provenance"] = dict(self.context)
        self.candidate["provenance"] = dict(self.context)

    def test_legacy_is_explicitly_unverified(self):
        self.assertEqual(self.run_gate()["provenance"]["status"], "unverified")

    def test_required_missing_blocks(self):
        self.policy["require_provenance"] = True
        self.assertEqual(self.run_gate()["decision"], "BLOCK")

    def test_one_sided_metadata_blocks(self):
        self.baseline["provenance"] = self.context
        self.assertEqual(self.run_gate()["failures"][0]["rule"], "missing_provenance")

    def test_matching_context_allows_candidate_version_change(self):
        self.declare()
        self.candidate["version"] = "new-model-prompt"
        self.assertEqual(self.run_gate()["decision"], "PASS")
        self.assertEqual(self.run_gate()["provenance"]["status"], "matched")

    def test_each_context_change_blocks_perfect_scores(self):
        for field in self.context:
            with self.subTest(field=field):
                self.declare()
                self.candidate["provenance"][field] = "changed"
                report = self.run_gate()
                self.assertEqual(report["decision"], "BLOCK")
                self.assertEqual(report["provenance"]["changed_fields"], [field])

    def test_malformed_context_rejected(self):
        for value in ([], {}, {**self.context, "extra": "x"},
                      {**self.context, "scorer_revision": ""}, None):
            with self.subTest(value=value):
                self.baseline["provenance"] = value
                if value is None:
                    continue  # Null means undeclared, and is governed by policy.
                with self.assertRaises(ValueError):
                    self.run_gate()

    def test_policy_requires_boolean(self):
        self.policy["require_provenance"] = "true"
        with self.assertRaises(ValueError):
            self.run_gate()

    def test_context_is_hashed_and_html_escaped(self):
        self.declare()
        before = self.run_gate()["evidence_hashes"]["candidate"]
        self.candidate["provenance"]["rubric_revision"] = "<script>changed</script>"
        report = self.run_gate()
        self.assertNotEqual(before, report["evidence_hashes"]["candidate"])
        self.assertNotIn("<script>", render_html(report))
        self.assertIn("&lt;script&gt;", render_html(report))


if __name__ == "__main__":
    unittest.main()
