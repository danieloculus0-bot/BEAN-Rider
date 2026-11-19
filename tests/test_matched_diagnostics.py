"""Condition-matched diagnostic comparison regression tests using synthetic data."""
import unittest

from bean_rider.matched_diagnostics import compare_matched_scans
from bean_rider.obd import scan, FakeOBDReader


def observation(rpm=None, load=None, coolant=None):
    data = {"RPM": rpm, "ENGINE_LOAD": load, "COOLANT_TEMP": coolant}
    return {"body": scan(FakeOBDReader(data)).payload()}


class MatchedDiagnosticTests(unittest.TestCase):
    def test_matched_pid_delta_and_one_to_one_pairing(self):
        baseline = [observation(1000, 30, 80), observation(1500, 50, 85)]
        followup = [observation(1050, 32, 84), observation(1520, 52, 89),
                    observation(1040, 31, 100)]
        result = compare_matched_scans(baseline, followup)
        self.assertEqual(result["matched_pairs"], 2)
        self.assertEqual(result["pids"]["coolant_c"]["paired_readings"], 2)
        self.assertEqual(result["pids"]["coolant_c"]["mean_followup_minus_baseline"], 4)
        self.assertEqual(result["ecu_writes"], 0)

    def test_unmatched_conditions_are_not_compared(self):
        result = compare_matched_scans([observation(1000, 20, 80)],
                                       [observation(3000, 80, 95)])
        self.assertEqual(result["matched_pairs"], 0)
        self.assertIsNone(result["pids"]["coolant_c"]["mean_followup_minus_baseline"])

    def test_missing_values_never_become_zero(self):
        result = compare_matched_scans([observation(1000, 20, None)],
                                       [observation(1010, 21, 90)])
        self.assertEqual(result["matched_pairs"], 1)
        self.assertEqual(result["pids"]["coolant_c"]["paired_readings"], 0)
        self.assertIsNone(result["pids"]["coolant_c"]["mean_followup_minus_baseline"])

    def test_nonfinite_and_invalid_conditions_rejected(self):
        for invalid in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    compare_matched_scans([], [], rpm_tolerance=invalid)

    def test_unknown_condition_excluded(self):
        result = compare_matched_scans([observation(None, 20, 80)],
                                       [observation(1000, 20, 90)])
        self.assertEqual(result["matched_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
