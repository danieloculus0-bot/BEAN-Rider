"""Synthetic SAE J1979 Mode 02 vectors, no ECU or vehicle required."""
import unittest

from bean_rider.mode02 import decode_mode02


class Mode02Tests(unittest.TestCase):
    def test_rpm_freeze_frame(self):
        result = decode_mode02(bytes.fromhex("42 0C 00 1A F8"), 0x0C)
        self.assertEqual(result["value"], 1726.0)
        self.assertEqual(result["frame"], 0)
        self.assertEqual(result["mode"], "02")
        self.assertEqual(result["unit"], "revolutions_per_minute")
        self.assertEqual(result["ecu_writes"], 0)
        self.assertIn("unverified", result["source"])

    def test_other_frame_and_scaling(self):
        self.assertEqual(decode_mode02(bytes.fromhex("42 05 01 64"), 5, 1)["value"], 60)
        self.assertEqual(decode_mode02(bytes.fromhex("42 06 02 80"), 6, 2)["value"], 0)
        self.assertEqual(decode_mode02(bytes.fromhex("42 0D 03 3C"), 13, 3)["value"], 60)

    def test_malformed_and_negative_responses(self):
        for payload in (bytes.fromhex("7F 02 12"),
                        bytes.fromhex("42 0C 00 1A"),
                        bytes.fromhex("42 0C 00 1A F8 00"),
                        bytes.fromhex("42 0D 00 1A F8"),
                        bytes.fromhex("42 0C 01 1A F8")):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    decode_mode02(payload, 12)
        with self.assertRaises(TypeError):
            decode_mode02("42 0C 00 1A F8", 12)

    def test_invalid_pid_and_frame(self):
        for pid in (True, 0xFF):
            with self.assertRaises(ValueError):
                decode_mode02(bytes.fromhex("42 0C 00 1A F8"), pid)
        for frame in (-1, 256, True, 1.5):
            with self.assertRaises(ValueError):
                decode_mode02(bytes.fromhex("42 0C 00 1A F8"), 12, frame)


if __name__ == "__main__":
    unittest.main()
