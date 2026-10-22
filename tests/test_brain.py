import gzip
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from bean_rider.obd import FakeOBDReader, scan, PIDS
from bean_rider.power import decide
from bean_rider.brain import RiderBrain
from bean_rider.injectors import CylinderTrial, review
from bean_rider.journal import EventJournal


class ScannerTests(unittest.TestCase):
    def test_read_only_with_missing_data(self):
        device = FakeOBDReader({"RPM": 1500, "SPEED": 40}, [("P0301", "Misfire cylinder one")])
        result = scan(device, timestamp="2026-10-21T12:00:00Z")
        self.assertEqual(result.values["rpm"], 1500)
        self.assertIn("coolant_c", result.missing_pids)
        self.assertEqual(result.dtcs[0][0], "P0301")
        self.assertEqual(set(result.values), set(PIDS))
        self.assertNotIn("vin", result.payload())

    def test_reject_nonfinite(self):
        device = FakeOBDReader({"RPM": float('nan')})
        self.assertIsNone(scan(device).values["rpm"])

    def test_power_does_not_guess_ignition(self):
        self.assertTrue(decide(ignition=None, supply_voltage=None, seconds_since_off=None).awake)
        self.assertFalse(decide(ignition=False, supply_voltage=12.5, seconds_since_off=300).awake)
        self.assertFalse(decide(ignition=False, supply_voltage=11.9, seconds_since_off=1).awake)
        self.assertTrue(decide(ignition=True, supply_voltage=11.2, seconds_since_off=300).awake)

    def test_brain_remembers_repeated_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder)/'brain.db'
            r = FakeOBDReader(faults=[("P0301", "Misfire")])
            with RiderBrain(filename) as brain:
                one = brain.observe(r)
                brain.observe(r)
                three = brain.observe(r)
                self.assertEqual(one.warnings[0]["repeat_observations"], 1)
                self.assertEqual(three.warnings[0]["priority"], "persistent")
                self.assertEqual(three.session_count, 3)
            with EventJournal(filename) as journal:
                self.assertEqual(journal.verify()["events"], 3)
                self.assertEqual(journal.export_gzip(Path(folder)/'events.json.gz')["rows"], 3)
                with gzip.open(Path(folder)/'events.json.gz','rb') as fp:
                    self.assertIn(b'P0301', fp.read())

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder)/'records.db'
            with EventJournal(filename) as ledger:
                ledger.append({'schema':'test','sample':17})
            with closing(sqlite3.connect(filename)) as db:
                with db:
                    db.execute("UPDATE events SET body='{}'")
            with self.assertRaises(ValueError):
                EventJournal(filename)


class InjectorTests(unittest.TestCase):
    def trial(self, **overrides):
        data = {"engine_id": "research-five-cylinder", "cylinder": 3,
                "condition_id": "cruise-2000rpm-80kpa", "source": "bench_cylinder_evidence",
                "baseline_error_pct": 8, "corrected_error_pct": 4,
                "latest_error_pct": 4, "evidence_count": 10,
                "compensation_pct": -3, "evidence_kind": "simulated"}
        data.update(overrides)
        return CylinderTrial(**data)

    def test_improved_is_only_attested(self):
        r = review(self.trial())
        self.assertEqual(r['status'],'improved_on_matched_input')
        self.assertFalse(r['ecu_write_performed'])
        self.assertEqual(r['verification'],'caller_supplied_not_authenticated')

    def test_failed_compensation_is_reported(self):
        r=review(self.trial(corrected_error_pct=8, latest_error_pct=8))
        self.assertEqual(r['status'],'compensation_failed')
        self.assertEqual(r['next_warning_after_s'],900)

    def test_degrading_warns_more_frequently(self):
        worse=review(self.trial(latest_error_pct=7))
        stable=review(self.trial())
        self.assertEqual(worse['status'],'degrading_after_compensation')
        self.assertLess(worse['next_warning_after_s'],stable['next_warning_after_s'])

    def test_physical_leak_is_not_tunable(self):
        r=review(self.trial(mechanical_leak_suspected=True))
        self.assertEqual(r['status'],'mechanical_fault_not_tunable')
        self.assertEqual(r['action'],'repair_and_verify_injector_mechanically')

    def test_insufficient_information_is_not_failure(self):
        self.assertEqual(review(self.trial(evidence_count=1))['status'],'insufficient_evidence')

if __name__ == '__main__':
    unittest.main()
