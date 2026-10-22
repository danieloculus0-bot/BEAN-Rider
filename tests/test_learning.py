import hashlib
from pathlib import Path
import tempfile
import unittest
from bean_rider.journal import EventJournal
from bean_rider.learning import Comparison, evaluate_comparison, scoreboard


class TestLearning(unittest.TestCase):
    def comparison(self, **changes):
        values={"engine_profile":"test","strategy":"low_power_fans", "condition_id":"same_dynocycle",
                "metric":"thermal_score","direction":"lower", "baseline":90,"candidate":80,
                "cases_matched":10,"cases_expected":10,"baseline_run":"cold","candidate_run":"test",
                "evaluation_sha256":hashlib.sha256(b'first complete evidence').hexdigest(),
                "evidence_kind":"synthetic"}
        values.update(changes)
        return Comparison(**values)

    def test_scoreboard_persists_without_duplicate_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/'journal.db'
            with EventJournal(f) as ledger:
                earned=evaluate_comparison(self.comparison(),ledger)
                self.assertGreater(earned['reward'],0)
                duplicate=evaluate_comparison(self.comparison(candidate=20,candidate_run='renamed'),ledger)
                self.assertIsNone(duplicate['reward'])
                self.assertEqual(scoreboard(ledger)['entries'][0]['experiments'],1)
            with EventJournal(f) as ledger:
                state=scoreboard(ledger)
                self.assertEqual(state['entries'][0]['improved'],1)
                result=evaluate_comparison(self.comparison(
                    candidate=120,evaluation_sha256=hashlib.sha256(b'different receipt').hexdigest()),ledger)
                self.assertLess(result['reward'],0)
                self.assertEqual(scoreboard(ledger)['entries'][0]['regressed'],1)

    def test_missing_coverage_is_not_zero_or_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with EventJournal(Path(directory)/'store.db') as ledger:
                result=evaluate_comparison(self.comparison(cases_matched=7),ledger)
                self.assertEqual(result['status'],'incomplete_case_coverage')
                self.assertIsNone(result['reward'])
                self.assertEqual(scoreboard(ledger)['entries'],[])

    def test_same_run_cannot_earn(self):
        with tempfile.TemporaryDirectory() as directory:
            with EventJournal(Path(directory)/'store.db') as ledger:
                result=evaluate_comparison(self.comparison(candidate_run='cold'),ledger)
                self.assertIsNone(result['reward'])

if __name__=='__main__':unittest.main()
