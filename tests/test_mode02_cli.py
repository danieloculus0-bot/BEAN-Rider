"""End-to-end CLI acceptance tests for Mode 02 freeze-frame decoding."""
import json
import subprocess
import sys
import unittest


class FreezeFrameCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "bean_rider", "decode-freeze-frame", *args],
            text=True, capture_output=True, check=False,
        )

    def test_rpm_frame_zero(self):
        result = self.run_cli("420C001AF8", "--pid", "0x0C")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "02")
        self.assertEqual(payload["frame"], 0)
        self.assertEqual(payload["ecu_writes"], 0)
        self.assertEqual(payload["value"], 1726.0)

    def test_rejects_wrong_frame(self):
        result = self.run_cli("420C011AF8", "--pid", "0x0C")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid Mode 02", result.stderr)

    def test_rejects_truncated_response(self):
        result = self.run_cli("420C00", "--pid", "0x0C")
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_invalid_hex(self):
        result = self.run_cli("420C00ZZ", "--pid", "0x0C")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
