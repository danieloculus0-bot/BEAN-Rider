"""End-to-end CLI acceptance for offline generic DTC response decoding."""
import json
import subprocess
import sys
import unittest


class DTCDecodeCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "bean_rider", "decode-dtcs", *args],
            text=True, capture_output=True, check=False,
        )

    def test_stored_pending_and_permanent_are_distinct(self):
        for mode, response, expected in (
            ("03", "4301330000", "P0133"),
            ("07", "4703010000", "P0301"),
            ("0A", "4A42000000", "C0200"),
        ):
            with self.subTest(mode=mode):
                result = self.run_cli(response, "--mode", mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["mode"], mode)
                self.assertEqual(payload["dtcs"], [expected])
                self.assertEqual(payload["ecu_writes"], 0)

    def test_no_codes_is_explicit_empty_response(self):
        result = self.run_cli("43", "--mode", "03")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["dtcs"], [])

    def test_rejects_wrong_mode_and_malformed_data(self):
        for response, mode in (
            ("430133", "07"),
            ("4301", "03"),
            ("4300000133", "03"),
            ("GG", "03"),
        ):
            with self.subTest(response=response, mode=mode):
                result = self.run_cli(response, "--mode", mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("error:", result.stderr)
                self.assertFalse(result.stdout)


if __name__ == "__main__":
    unittest.main()
