import copy
import json
from pathlib import Path
import tempfile
import unittest

from bean_rider.bridge import bean_event
from bean_rider.controller import ControllerConfig
from bean_rider.evidence import export_report, read_report
from bean_rider.experiment import evaluate, scenario, tune


class TestExperiments(unittest.TestCase):
    def test_scenario_repeatable_and_disjoint(self):
        self.assertEqual(scenario("train"), scenario("train"))
        a, b = evaluate(ControllerConfig(), scenario("train")), evaluate(ControllerConfig(), scenario("holdout"))
        self.assertNotEqual(a.scenario_hash, b.scenario_hash)

    def test_optimizer_reproducible_and_matched_holdout(self):
        x, y = tune(steps=50), tune(steps=50)
        self.assertEqual(x, y)
        self.assertEqual(x["candidates_compared"], 81)
        self.assertEqual(x["optimizer"], "grid_search_not_q_learning")
        bridge = bean_event(x)
        self.assertTrue(bridge["matched_holdout_scenario"])
        self.assertEqual(bridge["learning_claim"], "none: deterministic parameter search only")

    def test_compressed_archive_restores_and_detects_corruption(self):
        report = tune(steps=25)
        with tempfile.TemporaryDirectory() as t:
            manifest = export_report(report, t)
            self.assertEqual(manifest["evidence_kind"], "synthetic_lumped_parameter_model")
            self.assertEqual(read_report(t), report)
            archived = Path(t) / "experiment.json.gz"
            data = archived.read_bytes()
            archived.write_bytes(data[:-1] + bytes([data[-1] ^ 0xff]))
            with self.assertRaises((ValueError, EOFError, OSError)):
                read_report(t)

    def test_bridge_rejects_unknown_report(self):
        with self.assertRaises(ValueError):
            bean_event({"schema": "impossible"})

    def test_evidence_sha_matches_payload(self):
        x = tune(steps=20)
        receipt = bean_event(x)
        import hashlib
        expected = hashlib.sha256(json.dumps(x, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertEqual(receipt["report_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
