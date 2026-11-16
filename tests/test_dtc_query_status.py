"""DTC query status must not confuse an unavailable ECU response with no faults."""
import unittest
from bean_rider.obd import FakeOBDReader, scan


class DTCQueryStatusTests(unittest.TestCase):
    def test_successful_empty_query_is_not_missing(self):
        result = scan(FakeOBDReader(faults=[]), timestamp="2026-01-01T00:00:00Z")
        self.assertEqual(result.payload()["dtc_query_status"], "queried")
        self.assertEqual(result.dtcs, ())

    def test_query_exception_preserves_sensor_readings(self):
        class BrokenDTC(FakeOBDReader):
            def dtcs(self):
                raise OSError("adapter timeout")

        result = scan(BrokenDTC(), timestamp="2026-01-01T00:00:00Z")
        self.assertEqual(result.payload()["dtc_query_status"], "unavailable")
        self.assertEqual(result.values["rpm"], 900)
        self.assertEqual(result.dtcs, ())

    def test_unsupported_dtc_query_is_not_no_faults(self):
        class Unsupported(FakeOBDReader):
            def dtcs(self):
                return None

        result = scan(Unsupported())
        self.assertEqual(result.payload()["dtc_query_status"], "unavailable")

    def test_opt_out_is_distinct(self):
        result = scan(FakeOBDReader(), dtc=False)
        self.assertEqual(result.payload()["dtc_query_status"], "not_requested")

    def test_actual_fault_is_preserved(self):
        result = scan(FakeOBDReader(faults=[("P0300", "Random misfire")]))
        self.assertEqual(result.payload()["dtc_query_status"], "queried")
        self.assertEqual(result.dtcs, (("P0300", "Random misfire"),))


if __name__ == "__main__":
    unittest.main()
