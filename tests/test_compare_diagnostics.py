"""End-to-end synthetic journal comparison and missing-data regression."""
from pathlib import Path
import tempfile
import unittest

from bean_rider.brain import RiderBrain
from bean_rider.obd import FakeOBDReader
from bean_rider.compare_diagnostics import compare_journals


class CompareDiagnosticTests(unittest.TestCase):
    def test_two_journals_preserve_dtc_and_pid_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "before.db", Path(folder) / "after.db"
            with RiderBrain(a) as brain:
                brain.observe(FakeOBDReader({"RPM": 1000}, [("P0301", "misfire")]),
                              timestamp="2026-11-01T00:00:00Z")
            with RiderBrain(b) as brain:
                brain.observe(FakeOBDReader({"RPM": 1200}, [("P0171", "lean")]),
                              timestamp="2026-11-02T00:00:00Z")
            result = compare_journals(a, b)
            self.assertEqual(result["baseline_scans"], 1)
            self.assertEqual(result["followup_scans"], 1)
            self.assertEqual({x["code"]: x["classification"] for x in result["dtcs"]},
                             {"P0301": "not_reported_in_followup", "P0171": "newly_reported"})
            self.assertEqual(result["pids"]["rpm"]["average_delta"], 200)
            self.assertFalse(result["pids"]["rpm"]["matched_operating_conditions"])
            self.assertEqual(result["ecu_writes"], 0)

    def test_missing_journal_rejected_without_creating_file(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "missing.db", Path(folder) / "other.db"
            with self.assertRaisesRegex(ValueError, "existing regular journal"):
                compare_journals(a, b)
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())

    def test_missing_sensor_average_remains_unknown(self):
        from bean_rider.compare_diagnostics import compare_reports
        from bean_rider.diagnostics import summarize_diagnostics
        empty = summarize_diagnostics([])
        result = compare_reports(empty, empty)
        self.assertIsNone(result["pids"]["rpm"]["average_delta"])
        self.assertEqual(result["dtcs"], [])


if __name__ == "__main__":
    unittest.main()
