import json
import os
import shutil
import tempfile
import unittest

from recrate.site import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def read_data(site_dir):
    with open(os.path.join(site_dir, "data.js")) as f:
        text = f.read()
    prefix = "window.RECRATE_DATA = "
    assert text.startswith(prefix)
    return json.loads(text[len(prefix):].rstrip().rstrip(";").replace("<\\/", "</"))


class TestSite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_builds_from_examples(self):
        info = build(os.path.join(self.tmp, "site"), [EXAMPLES])
        self.assertGreaterEqual(info["papers"], 1)
        data = read_data(os.path.join(self.tmp, "site"))
        paper = next(p for p in data["papers"] if p["id"] == "peikert2021")
        self.assertTrue(paper["runs"])
        verdicts = [e for e in paper["runs"][0]["crate"]["@graph"] if e["@id"].startswith("#verdict-")]
        self.assertEqual(len(verdicts), 5)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "site", "index.html")))

    def test_refuses_a_tampered_crate(self):
        ex = os.path.join(self.tmp, "ex")
        shutil.copytree(os.path.join(EXAMPLES, "peikert2021"), os.path.join(ex, "peikert2021"))
        with open(os.path.join(ex, "peikert2021", "paper-crate", "data", "pathological-example2.csv"), "a") as f:
            f.write("1,1\n")
        with self.assertRaises(ValueError):
            build(os.path.join(self.tmp, "site"), [ex])

    def test_script_end_tags_are_escaped(self):
        build(os.path.join(self.tmp, "site"), [EXAMPLES])
        with open(os.path.join(self.tmp, "site", "data.js")) as f:
            self.assertNotIn("</script", f.read().lower())


if __name__ == "__main__":
    unittest.main()
