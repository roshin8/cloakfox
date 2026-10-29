import unittest

from probe_sab_privacy import classify


class ClassificationTests(unittest.TestCase):
    def test_recoverable_signal(self):
        result = classify([{"label": i % 2, "delta": 10 if i % 2 else 1} for i in range(40)])
        self.assertEqual(result["held_out_accuracy"], 1)
        self.assertEqual(result["nonzero_fraction"], 1)
        self.assertGreater(result["descriptive_wilson_95"][0], .5)

    def test_zero_clock_is_chance_not_privacy_pass(self):
        result = classify([{"label": i % 2, "delta": 0} for i in range(40)])
        self.assertEqual(result["held_out_accuracy"], .5)
        self.assertEqual(result["nonzero_fraction"], 0)
        self.assertNotIn("pass", result)
        self.assertLess(result["descriptive_wilson_95"][0], .5)
        self.assertGreater(result["descriptive_wilson_95"][1], .5)

    def test_test_labels_do_not_train_threshold(self):
        train = [{"label": i % 2, "delta": 10 if i % 2 else 1} for i in range(20)]
        test = [{"label": i % 2, "delta": 1 if i % 2 else 10} for i in range(20)]
        result = classify(train + test)
        self.assertEqual(result["threshold"], 5.5)
        self.assertEqual(result["held_out_accuracy"], 0)

    def test_unbalanced_partitions_rejected(self):
        with self.assertRaises(ValueError):
            classify([{"label": 0, "delta": 1}] * 8)


if __name__ == "__main__":
    unittest.main()
