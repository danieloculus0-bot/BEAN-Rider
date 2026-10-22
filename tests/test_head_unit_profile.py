"""Check Jetson head-unit profile without requiring OpenSCAD in CI."""
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1] / "hardware" / "jetson_head_unit"

class HeadUnitProfileTests(unittest.TestCase):
    def test_profile_is_specific_and_does_not_falsely_claim_fit(self):
        p = json.loads((HERE/"head_unit_profile.json").read_text(encoding="utf-8"))
        self.assertEqual(p["schema"], "bean.rider.hardware.jetson-head-unit.v1")
        self.assertEqual(p["hardware"]["screen_diagonal_in"], 10.1)
        self.assertIsNone(p["hardware"]["screen_external_dimensions_mm"])
        self.assertFalse(p["hardware"]["carrier_hole_locations_verified"])
        self.assertFalse(p["print_reference"]["chassis_attachment_verified"])
        self.assertIn("NOT powered", p["hardware"]["power"])
        self.assertEqual(p["phone_projection"]["required_in_finished_cockpit"],
                         ["Android Auto", "Apple CarPlay"])

    def test_print_parts_are_declared_in_scad(self):
        p = json.loads((HERE/"head_unit_profile.json").read_text(encoding="utf-8"))
        scad = (HERE/"head_unit.scad").read_text(encoding="utf-8")
        self.assertEqual([(x["part"],x["quantity"]) for x in p["printed_parts"]],
                         [("jetson_tray",1),("screen_tab",4),("cable_anchor",2)])
        for part in ["jetson_tray","screen_tab","cable_anchor"]:
            self.assertIn("module "+part+"()", scad)

if __name__ == "__main__":
    unittest.main()
