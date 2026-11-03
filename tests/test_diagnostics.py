"""Evidence-driven diagnostic summaries are reproducible, offline, read-only."""
from pathlib import Path
import tempfile
import unittest

from bean_rider.brain import RiderBrain
from bean_rider.diagnostics import SCHEMA, summarize_diagnostics
from bean_rider.journal import EventJournal
from bean_rider.obd import FakeOBDReader, scan


class DiagnosticReportTests(unittest.TestCase):
    def test_empty_journal_is_not_reported_as_a_clean_vehicle(self):
        result = summarize_diagnostics([])
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["samples"], 0)
        self.assertEqual(result["faults"], [])
        self.assertIsNone(result["last_scan_utc"])
        self.assertIsNone(result["pids"]["rpm"]["minimum"])
        self.assertEqual(result["ecu_writes"], 0)

    def test_fault_frequency_timeline_and_sensor_context(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "observations.db"
            with RiderBrain(db) as brain:
                brain.observe(FakeOBDReader({"RPM": 1100, "COOLANT_TEMP": 78},
                                            [("P0301", "Cylinder 1 misfire")]),
                              timestamp="2026-11-03T12:00:00Z")
                brain.observe(FakeOBDReader({"RPM": 2200, "COOLANT_TEMP": 82},
                                            [("P0301", "Cylinder 1 misfire"),
                                             ("P0171", "System too lean")]),
                              timestamp="2026-11-03T12:01:00Z")
                brain.observe(FakeOBDReader({"RPM": 3000, "COOLANT_TEMP": 84},
                                            [("P0171", "System too lean")]),
                              timestamp="2026-11-03T12:02:00Z")
            with EventJournal(db) as journal:
                self.assertEqual(journal.verify()["events"], 3)
                result = summarize_diagnostics(journal.records())
            self.assertEqual(result["samples"], 3)
            self.assertEqual(result["distinct_reported_dtcs"], 2)
            self.assertEqual(result["faults"][0]["code"], "P0171")
            self.assertTrue(result["faults"][0]["seen_in_latest_scan"])
            self.assertEqual(result["faults"][0]["observations"], 2)
            self.assertEqual(result["faults"][0]["first_context"]["rpm"], 2200)
            self.assertEqual(result["faults"][0]["last_context"]["rpm"], 3000)
            self.assertEqual(result["faults"][1]["code"], "P0301")
            self.assertFalse(result["faults"][1]["seen_in_latest_scan"])
            self.assertEqual(result["faults"][1]["first_seen_utc"],
                             "2026-11-03T12:00:00Z")
            self.assertEqual(result["pids"]["rpm"]["minimum"], 1100)
            self.assertEqual(result["pids"]["rpm"]["maximum"], 3000)
            self.assertEqual(result["pids"]["rpm"]["readings"], 3)
            self.assertEqual(result["pids"]["rpm"]["available_pct"], 100.0)
            self.assertIsNone(result["pids"]["throttle_pct"]["average"])

    def test_missing_pid_is_not_zero_and_zero_is_valid(self):
        events = []
        for data in ({}, {"RPM": 0}, {"RPM": 1600}):
            events.append({"body": scan(FakeOBDReader(data),
                                        timestamp="2026-11-03T13:00:00Z").payload()})
        # FakeOBDReader defaults for an empty dictionary; explicitly remove the
        # default by creating the scan and replacing its RPM value with None.
        events[0]["body"]["values"]["rpm"] = None
        result = summarize_diagnostics(events)
        self.assertEqual(result["pids"]["rpm"]["readings"], 2)
        self.assertEqual(result["pids"]["rpm"]["minimum"], 0)
        self.assertEqual(result["pids"]["rpm"]["maximum"], 1600)
        self.assertEqual(result["pids"]["rpm"]["average"], 800)
        self.assertEqual(result["pids"]["rpm"]["available_pct"], 66.7)

    def test_duplicate_code_in_one_scan_counts_once(self):
        item = scan(FakeOBDReader({"RPM": 1200},
                                  [("P0420", "Catalyst efficiency"),
                                   ("P0420", "Catalyst efficiency")])).payload()
        result = summarize_diagnostics([{"body": item}])
        self.assertEqual(result["distinct_reported_dtcs"], 1)
        self.assertEqual(result["faults"][0]["observations"], 1)

    def test_ignores_other_journal_events_and_non_numeric_telemetry(self):
        item = scan(FakeOBDReader({"RPM": 1200})).payload()
        item["values"]["rpm"] = float("nan")
        item["values"]["speed_kph"] = True
        records = [{"body": {"schema": "bean.rider.score.v1"}},
                   {"body": item}, {"body": {"schema": "anything_else"}}]
        result = summarize_diagnostics(records)
        self.assertEqual(result["samples"], 1)
        self.assertIsNone(result["pids"]["rpm"]["average"])
        self.assertIsNone(result["pids"]["speed_kph"]["average"])


if __name__ == "__main__":
    unittest.main()
