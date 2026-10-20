"""Reproduce a scorer-change comparison with no services or credentials."""
import copy
import json
from pathlib import Path

from agent_guardrails.release.gate import compare

root = Path(__file__).resolve().parent
baseline = json.loads((root / "baseline.json").read_text())
candidate = copy.deepcopy(baseline)
policy = json.loads((root / "policy.json").read_text())
policy["require_provenance"] = True
context = {"dataset_revision": "synthetic-eight-v1", "scorer_revision": "checks-v1",
           "rubric_revision": "rubric-v1"}
baseline["provenance"] = dict(context)
candidate["provenance"] = dict(context)
control = compare(baseline, candidate, policy)
candidate["provenance"]["scorer_revision"] = "checks-v2"
changed = compare(baseline, candidate, policy)
assert control["decision"] == "PASS"
assert changed["decision"] == "BLOCK"
print(json.dumps({"matched_control": control["decision"],
                  "changed_scorer": changed["decision"],
                  "candidate_quality": changed["candidate"]["quality"],
                  "findings": changed["failures"]}, indent=2))
