import glob
import json
import os
import unittest

import numpy as np

from recrate.core import crate as cr
from recrate.core.classify import classify_change, classify_patch, needs_approval
from recrate.orchestrator import gate_approvals, withhold_expected_values
from recrate.plugins.image import count_objects, f1_at_thresholds, iou_matrix
from recrate.plugins.tabular import TabularPlugin


def _load_json(path):
    with open(path) as f:
        return json.load(f)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRATE = os.path.join(ROOT, "examples", "peikert2021", "paper-crate")


class TestClassify(unittest.TestCase):
    def test_patches(self):
        self.assertEqual(classify_patch("Dockerfile"), "environment")
        self.assertEqual(classify_patch("env/requirements.txt"), "environment")
        self.assertEqual(classify_patch("renv.lock"), "environment")
        self.assertEqual(classify_patch("R/bootstrap.R"), "analysis")
        self.assertEqual(classify_patch("Makefile"), "analysis")                 # unknown -> safer class
        self.assertEqual(classify_patch("requirements.txt", analysis_files=["requirements.txt"]), "analysis")

    def test_changes(self):
        self.assertEqual(classify_change("unit-conversion"), "routine")
        self.assertEqual(classify_change("out-of-range"), "warning")
        self.assertTrue(needs_approval("threshold-change"))
        self.assertTrue(needs_approval("something-new"))                         # unknown -> needs approval

    def test_approval_gate_records_decision(self):
        changes = [{"kind": "unit-conversion", "target": "x", "description": "mm to m"},
                   {"kind": "threshold-change", "target": "cutoff", "description": "0.42 to 0.38"}]
        answers = iter(["approve", "A. Reviewer", "cohort is older"])
        out = gate_approvals(changes, ask=lambda _: next(answers))
        self.assertNotIn("approval", out[0])
        self.assertEqual(out[1]["approval"], {"decision": "approve", "by": "A. Reviewer", "reason": "cohort is older"})

    def test_execution_agent_never_sees_expected_values(self):
        hidden = withhold_expected_values(cr.claims(cr.load(CRATE)))
        for c in hidden:
            self.assertNotIn("rc:expectedValue", c)
            self.assertNotIn("rc:condition", c)
            self.assertNotIn("rc:decimalPlaces", c)


class TestImageMetric(unittest.TestCase):
    def setUp(self):
        self.truth = np.zeros((10, 10), int)
        self.truth[0:4, 0:4] = 1          # 16 px
        self.truth[6:10, 6:10] = 2        # 16 px
        self.pred = np.zeros((10, 10), int)
        self.pred[0:4, 0:3] = 7           # IoU 12/16 = 0.75 with object 1
        self.pred[6:8, 0:2] = 9           # false positive

    def test_iou(self):
        iou = iou_matrix(self.truth, self.pred)
        self.assertAlmostEqual(iou[0, 0], 0.75)
        self.assertEqual(iou[1].max(), 0)

    def test_f1(self):
        r = f1_at_thresholds(self.truth, self.pred)
        self.assertAlmostEqual(r["per_threshold"][0.5], 0.5)    # 1 TP, 1 FP, 1 FN
        self.assertEqual(r["per_threshold"][0.8], 0.0)
        self.assertEqual((r["n_true"], r["n_pred"]), (2, 2))
        self.assertEqual(count_objects(self.truth), 2)

    def test_perfect(self):
        self.assertEqual(f1_at_thresholds(self.truth, self.truth)["mean_f1"], 1.0)


class TestTabularTransfer(unittest.TestCase):
    def test_compatibility(self):
        p = TabularPlugin()
        rows = [{"pred": "1.0", "y": "2"}, {"pred": "3.5", "y": ""}]
        contract = {"rc:requiredColumns": ["x", "y"], "rc:columnTypes": {"y": "numeric"}}
        kinds = {c.kind for c in p.check_compatibility(p.profile(rows), contract)}
        self.assertEqual(kinds, {"missing-column", "missing-values"})


class TestSchemas(unittest.TestCase):
    def test_example_claims_match_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = _load_json(os.path.join(ROOT, "schemas", "claim.schema.json"))
        for c in cr.claims(cr.load(CRATE)):
            jsonschema.validate(c, schema)

    def test_example_observed_files_match_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = _load_json(os.path.join(ROOT, "schemas", "observed.schema.json"))
        for path in glob.glob(os.path.join(ROOT, "examples", "*", "work", "observed-*.json")):
            jsonschema.validate(_load_json(path), schema)

    def test_schemas_are_valid(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        for path in glob.glob(os.path.join(ROOT, "schemas", "*.json")):
            jsonschema.Draft202012Validator.check_schema(_load_json(path))


if __name__ == "__main__":
    unittest.main()
