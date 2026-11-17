"""Offline protocol vectors, never connected to a vehicle."""
import unittest
from bean_rider.mode01 import decode_mode01, decode_mode03, decode_mode07, decode_mode0a


class Mode01Tests(unittest.TestCase):
    def test_rpm(self):
        self.assertEqual(decode_mode01(bytes.fromhex("41 0C 1A F8"), 12)["value"], 1726.0)

    def test_mass_air_flow_and_module_voltage(self):
        maf = decode_mode01(bytes.fromhex("41 10 01 F4"), 0x10)
        self.assertEqual(maf["value"], 5.0)
        self.assertEqual(maf["unit"], "gram_per_second")
        voltage = decode_mode01(bytes.fromhex("41 42 30 39"), 0x42)
        self.assertEqual(voltage["value"], 12.345)
        self.assertEqual(voltage["unit"], "volt")
        for pid, payload in ((0x10, bytes.fromhex("41 10 01")),
                             (0x42, bytes.fromhex("41 42 30 39 00"))):
            with self.assertRaises(ValueError):
                decode_mode01(payload, pid)

    def test_additional_standard_sensor_pids(self):
        vectors = (
            (0x1F, "41 1F 01 2C", "engine_runtime_s", 300, "second"),
            (0x2F, "41 2F FF", "fuel_level_pct", 100, "percent"),
            (0x33, "41 33 65", "barometric_kpa", 101, "kilopascal"),
            (0x46, "41 46 28", "ambient_c", 0, "degC"),
            (0x5C, "41 5C 50", "engine_oil_c", 40, "degC"),
        )
        for pid, raw, name, expected, unit in vectors:
            with self.subTest(pid=pid):
                result = decode_mode01(bytes.fromhex(raw), pid)
                self.assertEqual(result["name"], name)
                self.assertEqual(result["value"], expected)
                self.assertEqual(result["unit"], unit)
                self.assertEqual(result["ecu_writes"], 0)
                self.assertEqual(result["source"], "raw_obd_mode01_unverified")
                for malformed in (bytes.fromhex(raw)[:-1], bytes.fromhex(raw) + b"\\x00"):
                    with self.assertRaises(ValueError):
                        decode_mode01(malformed, pid)

    def test_temperature_and_trim(self):
        self.assertEqual(decode_mode01(bytes.fromhex("41 05 00"), 5)["value"], -40)
        self.assertEqual(decode_mode01(bytes.fromhex("41 0F 64"), 15)["value"], 60)
        self.assertEqual(decode_mode01(bytes.fromhex("41 06 80"), 6)["value"], 0)
        self.assertEqual(decode_mode01(bytes.fromhex("41 07 00"), 7)["value"], -100)

    def test_percent_and_pressure(self):
        self.assertEqual(decode_mode01(bytes.fromhex("41 04 FF"), 4)["value"], 100)
        self.assertEqual(decode_mode01(bytes.fromhex("41 11 00"), 17)["value"], 0)
        self.assertEqual(decode_mode01(bytes.fromhex("41 0B 64"), 11)["value"], 100)
        self.assertEqual(decode_mode01(bytes.fromhex("41 0D 3C"), 13)["value"], 60)

    def test_reject_negative_wrong_pid_and_truncated(self):
        for payload, pid in [(bytes.fromhex("7F 01 12"), 12),
                             (bytes.fromhex("41 0D 1A F8"), 12),
                             (bytes.fromhex("41 0C 1A"), 12),
                             (bytes.fromhex("41 0C 1A F8 00"), 12)]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    decode_mode01(payload, pid)

    def test_reject_unknown_pid_and_wrong_type(self):
        with self.assertRaises(ValueError):
            decode_mode01(bytes.fromhex("41 FF 00"), 255)
        with self.assertRaises(TypeError):
            decode_mode01("41 0C 1A F8", 12)


class Mode03Tests(unittest.TestCase):
    def test_stored_codes_and_padding(self):
        decoded = decode_mode03(bytes.fromhex("43 01 33 C1 23 00 00"))
        self.assertEqual(decoded["dtcs"], ["P0133", "U0123"])
        self.assertEqual(decoded["ecu_writes"], 0)
        self.assertEqual(decode_mode03(bytes.fromhex("43 00 00"))["dtcs"], [])

    def test_all_code_families(self):
        self.assertEqual(decode_mode03(bytes.fromhex("43 40 01 80 02"))["dtcs"],
                         ["C0001", "B0002"])

    def test_reject_malformed_and_negative(self):
        for payload in (b"", bytes.fromhex("7F 03 11"),
                        bytes.fromhex("43 01"), bytes.fromhex("43 00 00 01 33")):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    decode_mode03(payload)
        with self.assertRaises(TypeError):
            decode_mode03("43 01 33")


    def test_pending_and_permanent_dtc_classes(self):
        pending = decode_mode07(bytes.fromhex("47 01 33 C1 23 00 00"))
        permanent = decode_mode0a(bytes.fromhex("4A 40 01 80 02"))
        self.assertEqual(pending["mode"], "07")
        self.assertEqual(pending["dtcs"], ["P0133", "U0123"])
        self.assertEqual(permanent["mode"], "0A")
        self.assertEqual(permanent["dtcs"], ["C0001", "B0002"])
        self.assertEqual(pending["ecu_writes"], 0)
        self.assertEqual(permanent["ecu_writes"], 0)

    def test_pending_permanent_reject_malformed(self):
        for decoder, positive in ((decode_mode07, "47"), (decode_mode0a, "4A")):
            for payload in (b"", bytes.fromhex("7F 07 11"),
                            bytes.fromhex(positive + " 01"),
                            bytes.fromhex(positive + " 00 00 01 33")):
                with self.subTest(decoder=decoder.__name__, payload=payload):
                    with self.assertRaises(ValueError):
                        decoder(payload)
            with self.assertRaises(TypeError):
                decoder(positive)


if __name__ == "__main__":
    unittest.main()
