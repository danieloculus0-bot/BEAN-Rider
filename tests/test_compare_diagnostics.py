"""End-to-end synthetic journal comparison and missing-data regression."""
from pathlib import Path
import json
import subprocess
import sys
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

    def test_cli_end_to_end_with_sealed_journals(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / "before.sqlite"
            followup = Path(folder) / "after.sqlite"
            with RiderBrain(baseline) as brain:
                brain.observe(FakeOBDReader({"RPM": 900}, [("P0300", "misfire")]),
                              timestamp="2026-11-01T00:00:00Z")
            with RiderBrain(followup) as brain:
                brain.observe(FakeOBDReader({"RPM": 1100}, []),
                              timestamp="2026-11-02T00:00:00Z")
            completed = subprocess.run(
                [sys.executable, "-m", "bean_rider", "compare-diagnostics",
                 str(baseline), str(followup)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["dtcs"][0]["code"], "P0300")
            self.assertEqual(report["dtcs"][0]["followup_resolution"],
                             "not_reported_in_queried_followup")
            self.assertTrue(report["dtcs"][0]["followup_absence_confirmed"])
            self.assertEqual(report["pids"]["rpm"]["average_delta"], 200)
            self.assertEqual(report["ecu_writes"], 0)

    def test_unavailable_followup_does_not_imply_repair(self):
        from bean_rider.compare_diagnostics import compare_reports
        from bean_rider.diagnostics import summarize_diagnostics
        from bean_rider.obd import scan
        first = scan(FakeOBDReader(faults=[("P0300", "misfire")])).payload()
        last = scan(FakeOBDReader()).payload()
        last["dtc_query_status"] = "unavailable"
        before = summarize_diagnostics([{"body": first}])
        after = summarize_diagnostics([{"body": last}])
        report = compare_reports(before, after)
        self.assertEqual(report["followup_dtc_evidence"], "unknown")
        self.assertFalse(report["dtcs"][0]["followup_absence_confirmed"])
        self.assertEqual(report["dtcs"][0]["followup_resolution"],
                         "unknown_followup_query_unavailable")

    def test_cli_rejects_missing_db_without_creating_it(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "missing1.sqlite", Path(folder) / "missing2.sqlite"
            completed = subprocess.run(
                [sys.executable, "-m", "bean_rider", "compare-diagnostics",
                 str(a), str(b)], capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("existing regular journal file required", completed.stderr)
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())

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
