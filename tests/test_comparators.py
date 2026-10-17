import unittest

from recrate.plugins.tabular import compare_values


class TestComparators(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(compare_values([2, 6, 5], [2, 6, 5], "exact").passed)
        self.assertFalse(compare_values([2, 6, 5], [2, 6, 4], "exact").passed)
        self.assertTrue(compare_values(412, 412.0, "exact").passed)

    def test_rounded_inside_and_at_edges(self):
        self.assertTrue(compare_values(0.00965348, 0.0097, "rounded", decimal_places=4).passed)
        self.assertTrue(compare_values(0.00965, 0.0097, "rounded", decimal_places=4).passed)   # tie accepted
        self.assertFalse(compare_values(0.00964, 0.0097, "rounded", decimal_places=4).passed)
        self.assertTrue(compare_values(0.00964, 0.0097, "rounded", decimal_places=4).near)

    def test_rounded_needs_decimals(self):
        with self.assertRaises(ValueError):
            compare_values(1.0, 1.0, "rounded")

    def test_abs_and_rel(self):
        self.assertTrue(compare_values(0.815, 0.812, "abs", tolerance=0.01).passed)
        r = compare_values(0.83, 0.812, "abs", tolerance=0.01)
        self.assertFalse(r.passed)
        self.assertTrue(r.near)
        self.assertTrue(compare_values(2.43, 2.41, "rel", tolerance=0.05).passed)
        self.assertFalse(compare_values(2.80, 2.41, "rel", tolerance=0.05).near)

    def test_length_mismatch_fails(self):
        self.assertFalse(compare_values([1, 2], [1, 2, 3], "abs", tolerance=1).passed)

    def test_distribution(self):
        samples = [0.85 + 0.001 * i for i in range(100)]          # 0.850 .. 0.949
        self.assertTrue(compare_values(samples, 0.8864, "distribution").passed)
        r = compare_values(samples, 0.851, "distribution")         # inside range, outside central 95%
        self.assertFalse(r.passed)
        self.assertTrue(r.near)
        self.assertFalse(compare_values(samples, 0.99, "distribution").near)

    def test_unknown_comparison(self):
        with self.assertRaises(ValueError):
            compare_values(1, 1, "pixels")


if __name__ == "__main__":
    unittest.main()
