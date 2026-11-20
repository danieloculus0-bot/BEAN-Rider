import unittest

from bean_rider.idle_analysis import analyze_idle


class IdleAnalysisTests(unittest.TestCase):
    def test_stationary_sequence(self):
        result = analyze_idle([
            {"elapsed_s": 0, "rpm": 800, "speed_kph": 0},
            {"elapsed_s": 1, "rpm": 820, "speed_kph": 0},
            {"elapsed_s": 2, "rpm": 780, "speed_kph": 0},
        ])
        self.assertEqual(result["observed_idle_seconds"], 2)
        self.assertEqual(result["rpm_mean"], 800)
        self.assertEqual(result["eligible_samples"], 3)
        self.assertEqual(result["ecu_writes"], 0)

    def test_no_bridge_across_motion_or_gap(self):
        result = analyze_idle([
            {"elapsed_s": 0, "rpm": 800, "speed_kph": 0},
            {"elapsed_s": 1, "rpm": 900, "speed_kph": 5},
            {"elapsed_s": 2, "rpm": 800, "speed_kph": 0},
            {"elapsed_s": 12, "rpm": 800, "speed_kph": 0},
        ])
        self.assertEqual(result["observed_idle_seconds"], 0)
        self.assertEqual(result["eligible_samples"], 3)

    def test_empty(self):
        result = analyze_idle([])
        self.assertIsNone(result["rpm_mean"])
        self.assertEqual(result["diagnosis"], "unknown")

    def test_reject_invalid_observations(self):
        for observations in (
            [{"elapsed_s": 0, "rpm": float("nan"), "speed_kph": 0}],
            [{"elapsed_s": 0, "rpm": 800, "speed_kph": 0},
             {"elapsed_s": 0, "rpm": 800, "speed_kph": 0}],
            [{"elapsed_s": 0, "rpm": 800}],
            [{"elapsed_s": 0, "rpm": True, "speed_kph": 0}],
        ):
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                analyze_idle(observations)


if __name__ == "__main__":
    unittest.main()
