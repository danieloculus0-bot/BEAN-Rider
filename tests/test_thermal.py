from dataclasses import replace
import math
import unittest

from bean_rider.controller import ControllerConfig, command
from bean_rider.thermal import Conditions, Controls, PlantState, advance, duct_flow_m3_s


class TestThermal(unittest.TestCase):
    def setUp(self):
        self.env = Conditions(28, 0, 4500, 65)
        self.state = PlantState()

    def test_push_pull_adds_pressure_and_increases_flow(self):
        leading_only = duct_flow_m3_s(0.8, 0, 0)
        push_pull = duct_flow_m3_s(0.8, 0.8, 0)
        self.assertGreater(push_pull, leading_only)
        self.assertLess(push_pull, 2 * leading_only)

    def test_speed_adds_flow_to_identical_fans(self):
        self.assertGreater(duct_flow_m3_s(0.3, 0.3, 28), duct_flow_m3_s(0.3, 0.3, 0))

    def test_peltier_hot_side_includes_electrical_input(self):
        o = advance(self.state, Controls(1, 1, 1, 1), self.env)
        self.assertAlmostEqual(o.peltier_hot_w, o.peltier_cold_w + o.peltier_electric_w)
        self.assertGreater(o.peltier_electric_w, o.peltier_cold_w)

    def test_zero_peltier_never_fakes_cooling(self):
        out = advance(self.state, Controls(.6, .6, .8, 0), self.env)
        self.assertEqual(out.peltier_cold_w, 0)
        self.assertEqual(out.peltier_hot_w, 0)

    def test_thermal_conservation_turbine_and_coolant(self):
        controls = Controls(.65, .8, .7, .5)
        out = advance(self.state, controls, self.env)
        stored_change = (out.state.turbine_c - self.state.turbine_c) * 14500
        stored_change += (out.state.turbo_coolant_c - self.state.turbo_coolant_c) * 16000
        self.assertAlmostEqual(stored_change, self.env.turbine_heating_w - out.radiator_rejection_w, places=7)

    def test_active_pump_cools_hot_turbine_more(self):
        off = advance(self.state, Controls(.8, .8, 0, 0), self.env)
        on = advance(self.state, Controls(.8, .8, 1, 0), self.env)
        self.assertLess(on.state.turbine_c, off.state.turbine_c)

    def test_fan_and_peltier_command_bounded(self):
        extreme = PlantState(750, 350, 110)
        cmd = command(extreme, self.env, ControllerConfig(3, 2, 3, 3))
        self.assertTrue(all(0 <= value <= 1 for value in vars(cmd).values()))

    def test_invalid_nonfinite_and_negative_actuators(self):
        for controls in ((math.nan, .5, .4, .3), (-.1, .3, .3, .3)):
            with self.assertRaises(ValueError):
                Controls(*controls)
        with self.assertRaises(ValueError):
            Conditions(25, -4, 100)

    def test_model_does_not_write_hardware(self):
        result = advance(self.state, Controls(.7, .7, .7, .3), self.env)
        self.assertIsInstance(result.state, PlantState)
