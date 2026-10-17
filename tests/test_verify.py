"""Golden results and planted errors on the Peikert & Brandmaier example.

The verifier must catch every planted error. If one of these tests starts passing an error
through, the verifier is no longer trustworthy.
"""
import copy
import json
import os
import shutil
import tempfile
import unittest

from recrate.core import crate as cr
from recrate.core import verify as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples", "peikert2021")
CRATE = os.path.join(EX, "paper-crate")
OBS35 = os.path.join(EX, "work", "observed-shipped-3.5.0.json")
OBS36 = os.path.join(EX, "work", "observed-shipped-3.6.1.json")
INDEP = os.path.join(EX, "work", "independent-I1.json")


def load(p):
    with open(p) as f:
        return json.load(f)


def as_execution(obs, **outputs):
    o = copy.deepcopy(obs)
    o["source"] = "execution"
    o["outputs"].update(outputs)
    return o


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.doc = cr.load(CRATE)
        self.o35, self.o36 = load(OBS35), load(OBS36)

    def judge(self, observations, independent=(), patches=()):
        return v.judge_all(self.doc, [(f"obs{i}.json", o) for i, o in enumerate(observations)],
                           [("i.json", x) for x in independent], [dict(p) for p in patches])

    def test_golden_shipped_outputs(self):
        res = self.judge([self.o35, self.o36], [load(INDEP)])
        self.assertEqual({k: r["verdict"] for k, r in res.items()},
                         {c: v.MATCHES_RECORDED for c in ["C1", "C2", "C3", "C4", "C5"]})
        self.assertEqual(res["C5"]["checks"][0]["outcome"], "fragile")

    def test_reexecution_upgrades_to_reproduced(self):
        res = self.judge([as_execution(self.o35), as_execution(self.o36)])
        self.assertTrue(all(r["verdict"] == v.REPRODUCED for r in res.values()))

    def test_execution_preferred_over_recorded_outputs(self):
        res = self.judge([self.o35, as_execution(self.o35)])
        self.assertEqual(res["C1"]["verdict"], v.REPRODUCED)

    def test_planted_output_error_is_caught(self):
        bad = as_execution(self.o36, boot_ci_lower=0.0021)        # CI no longer includes zero
        res = self.judge([as_execution(self.o35), bad])
        self.assertEqual(res["C4"]["verdict"], v.MISMATCH)
        self.assertEqual(res["C5"]["verdict"], v.MISMATCH)
        self.assertEqual(res["C2"]["verdict"], v.REPRODUCED)       # untouched claims stay intact

    def test_planted_expected_value_error_is_caught(self):
        for c in self.doc["@graph"]:
            if c.get("identifier") == "C3":
                c["rc:expectedValue"] = [0.0120, 0.3842]
        res = self.judge([as_execution(self.o35), as_execution(self.o36)])
        self.assertEqual(res["C3"]["verdict"], v.MISMATCH)

    def test_wrong_environment_is_not_run(self):
        o = as_execution(self.o35)
        o["environment"]["r_version"] = "4.4.1"
        res = self.judge([o])
        self.assertTrue(all(r["verdict"] == v.NOT_RUN for r in res.values()))

    def test_could_not_run_is_recorded(self):
        o = {"source": "execution", "status": "could-not-run", "reason": "image build failed: MRAN retired",
             "environment": {"r_version": "3.5.0"}}
        res = self.judge([o])
        self.assertEqual(res["C1"]["verdict"], v.COULD_NOT_RUN)
        self.assertIn("MRAN", res["C1"]["detail"])
        self.assertEqual(res["C5"]["verdict"], v.COULD_NOT_RUN)

    def test_analysis_patch_downgrades_reproduced(self):
        patches = [{"file": "R/bootstrap.R", "reason": "changed a parameter"},
                   {"file": "Dockerfile", "reason": "MRAN to Posit Package Manager"}]
        res = self.judge([as_execution(self.o35), as_execution(self.o36)], patches=patches)
        self.assertEqual(res["C3"]["verdict"], v.REPRODUCED_PATCHED)
        self.assertEqual(res["C5"]["verdict"], v.REPRODUCED_PATCHED)
        self.assertEqual(res["C1"]["verdict"], v.REPRODUCED)      # random.R untouched; Dockerfile is environment

    def test_robust_independent_check_upgrades(self):
        chk = {"check": "I9", "about": "C1", "outcome": "robust", "summary": "re-derived", "method": "test"}
        res = self.judge([as_execution(self.o35)], [chk])
        self.assertEqual(res["C1"]["verdict"], v.INDEPENDENTLY_CHECKED)

    def test_fragile_check_does_not_upgrade(self):
        chk = {"check": "I9", "about": "C1", "outcome": "fragile", "summary": "seed-dependent", "method": "test"}
        res = self.judge([as_execution(self.o35)], [chk])
        self.assertEqual(res["C1"]["verdict"], v.REPRODUCED)


class TestGatesAndIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.crate = os.path.join(self.tmp, "paper-crate")
        shutil.copytree(CRATE, self.crate)
        lock_file = os.path.join(self.crate, v.LOCK_FILE)
        if os.path.exists(lock_file):
            os.remove(lock_file)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_verify(self, **kw):
        return v.verify(self.crate, os.path.join(self.tmp, "run"), [OBS35, OBS36], [INDEP], **kw)

    def test_unlocked_claims_are_refused(self):
        with self.assertRaises(v.VerifyError):
            self.run_verify()

    def test_lock_then_verify_records_lock(self):
        v.lock(self.crate, "Test Person")
        self.run_verify()
        root = cr.entities(cr.load(os.path.join(self.tmp, "run")))["./"]
        self.assertTrue(root["rc:claimsLocked"])
        self.assertEqual(root["rc:claimsLockedBy"], "Test Person")

    def test_editing_claims_after_lock_breaks_the_lock(self):
        v.lock(self.crate, "Test Person")
        doc = cr.load(self.crate)
        for c in doc["@graph"]:
            if c.get("identifier") == "C4":
                c["rc:decimalPlaces"] = 2                          # loosen a tolerance after locking
        with open(os.path.join(self.crate, cr.METADATA), "w") as f:
            json.dump(doc, f)
        with self.assertRaises(v.VerifyError):
            self.run_verify()

    def test_tampered_data_file_is_refused(self):
        with open(os.path.join(self.crate, "data", "pathological-example2.csv"), "a") as f:
            f.write("9.99,9.99\n")
        with self.assertRaises(v.VerifyError):
            self.run_verify(allow_unlocked=True)

    def test_missing_file_is_refused(self):
        os.remove(os.path.join(self.crate, "R", "bootstrap.R"))
        self.assertTrue(any("missing" in p for p in cr.check(self.crate)))

    def test_run_crate_is_structurally_valid(self):
        self.run_verify(allow_unlocked=True)
        self.assertEqual(cr.check(os.path.join(self.tmp, "run")), [])


if __name__ == "__main__":
    unittest.main()
