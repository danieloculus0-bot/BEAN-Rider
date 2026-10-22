import tempfile
from pathlib import Path
import unittest
from bean_rider.telemetry import describe, read_csv

HEADER = 'time_s,rpm,speed_kph,coolant_c,oil_c,intake_c,manifold_kpa,lambda_measured,knock_retard_deg\n'


class TestTelemetry(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'sample.csv'
            p.write_text(content, encoding='utf8')
            return read_csv(p)

    def test_csv_import_and_summary(self):
        rows = self.parse(HEADER + '0,900,0,91,92,30,30,1,0\n1,1500,22,92,95,31,75,.98,1\n')
        self.assertEqual(describe(rows)['readings'], 2)
        self.assertEqual(describe(rows)['max_rpm'], 1500)
        self.assertEqual(describe(rows)['diagnostic_conclusion'][:4], 'none')

    def test_out_of_order_timestamps_fail(self):
        with self.assertRaises(ValueError):
            self.parse(HEADER + '2,1000,10,90,90,30,40,1,0\n1,1100,10,90,90,30,40,1,0\n')

    def test_invalid_and_missing_units_fail(self):
        with self.assertRaises(ValueError):
            self.parse('time_s,rpm\n1,100\n')
        with self.assertRaises(ValueError):
            self.parse(HEADER + '1,nan,10,90,90,30,40,1,0\n')
        with self.assertRaises(ValueError):
            self.parse(HEADER)
