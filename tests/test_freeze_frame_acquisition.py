"""Deterministic serial transport tests; no hardware or ECU required."""
import unittest
from bean_rider.freeze_frame import acquire_freeze_frame, parse_elm_response


class SerialFake:
    def __init__(self, reply):
        self.reply = reply
        self.commands = []

    def write(self, command):
        self.commands.append(command)

    def read_until(self, terminator):
        assert terminator == b">"
        return self.reply


class FreezeFrameAcquisitionTests(unittest.TestCase):
    def test_readonly_rpm_query(self):
        link = SerialFake(b"020C00\r420C001AF8\r>")
        result = acquire_freeze_frame(link, 0x0C)
        self.assertEqual(link.commands, [b"020C00\r"])
        self.assertEqual(result["value"], 1726.0)
        self.assertEqual(result["ecu_writes"], 0)

    def test_single_frame_pci(self):
        self.assertEqual(parse_elm_response(b"05420C001AF8\r>", 12),
                         bytes.fromhex("420C001AF8"))

    def test_reject_ambiguous_or_invalid(self):
        for reply in (b"NO DATA\r>", b"420C001AF8\r420C001AF8\r>",
                      b"420C001AF8", b"7F0212\r>", b"420C011AF8\r>",
                      b"1010420C001AF8\r>"):
            with self.subTest(reply=reply):
                with self.assertRaises(ValueError):
                    acquire_freeze_frame(SerialFake(reply), 12)

    def test_no_command_for_invalid_pid(self):
        link = SerialFake(b">")
        with self.assertRaises(ValueError):
            acquire_freeze_frame(link, 255)
        self.assertEqual(link.commands, [])


if __name__ == "__main__":
    unittest.main()
