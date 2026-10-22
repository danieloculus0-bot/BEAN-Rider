"""Deterministic lumped-parameter *research* simulator, not a vehicle calibration.

Every heat term is in watts. Node capacitances are in joules per kelvin.
Numbers are deliberately declared assumptions, not Maserati measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt


def _finite(value: float) -> bool:
    return type(value) in (int, float) and isfinite(value)


def _range(name: str, value: float, low: float, high: float) -> None:
    if not _finite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite in [{low}, {high}]")


@dataclass(frozen=True)
class Conditions:
    ambient_c: float
    road_speed_mps: float
    turbine_heating_w: float
    display_heating_w: float = 55.0

    def __post_init__(self) -> None:
        _range("ambient_c", self.ambient_c, -40, 70)
        _range("road_speed_mps", self.road_speed_mps, 0, 90)
        _range("turbine_heating_w", self.turbine_heating_w, 0, 30000)
        _range("display_heating_w", self.display_heating_w, 0, 2000)


@dataclass(frozen=True)
class PlantState:
    turbine_c: float = 155.0
    turbo_coolant_c: float = 82.0
    display_coolant_c: float = 35.0

    def __post_init__(self) -> None:
        for field in ("turbine_c", "turbo_coolant_c", "display_coolant_c"):
            _range(field, getattr(self, field), -100, 3000)


@dataclass(frozen=True)
class Controls:
    inlet_fan: float
    outlet_fan: float
    coolant_pump: float
    peltier: float

    def __post_init__(self) -> None:
        for field in ("inlet_fan", "outlet_fan", "coolant_pump", "peltier"):
            _range(field, getattr(self, field), 0, 1)


@dataclass(frozen=True)
class ThermalResult:
    state: PlantState
    flow_m3_s: float
    heat_to_coolant_w: float
    radiator_rejection_w: float
    peltier_cold_w: float
    peltier_hot_w: float
    peltier_electric_w: float
    total_electric_w: float
    exhaust_air_c: float


def duct_flow_m3_s(inlet_fan: float, outlet_fan: float, speed_mps: float) -> float:
    """Illustrative push-pull series pressure model with optional ram-air contribution.

    Pressure adds; volume flow does *not* add for fans in series. Real fan curves,
    ducts, placement and vehicle surface pressure still require measurement.
    """
    _range("inlet_fan", inlet_fan, 0, 1)
    _range("outlet_fan", outlet_fan, 0, 1)
    _range("speed_mps", speed_mps, 0, 90)
    fan_pa = 85.0 * (inlet_fan ** 2 + outlet_fan ** 2)
    ram_pa = 0.07 * 0.5 * 1.2 * speed_mps ** 2
    return min(0.12, sqrt((fan_pa + ram_pa) / 21000.0))


def advance(state: PlantState, controls: Controls, conditions: Conditions,
            *, seconds: float = 1.0) -> ThermalResult:
    """Advance a simple three-node thermal circuit via explicit Euler integration."""
    _range("seconds", seconds, 0.001, 2.0)
    flow = duct_flow_m3_s(controls.inlet_fan, controls.outlet_fan,
                          conditions.road_speed_mps)
    transfer_w = (65.0 + 135.0 * controls.coolant_pump) * (
        state.turbine_c - state.turbo_coolant_c)
    radiator_ua = 8.0 + 1050.0 * flow
    radiator_w = radiator_ua * (state.turbo_coolant_c - conditions.ambient_c)

    # Model the Peltier hot-side exhaust heat exchanger explicitly. Cold-side
    # capacity declines with increasing temperature lift; COP is not constant.
    peltier_electrical = 220.0 * controls.peltier
    hot_sink_c = conditions.ambient_c + 5.0 + peltier_electrical / (12.0 + 550 * flow)
    lift_c = max(0.0, hot_sink_c - state.display_coolant_c)
    cold_capacity_w = 140.0 * controls.peltier * max(0.0, 1.0 - lift_c / 55.0)
    peltier_hot_w = cold_capacity_w + peltier_electrical

    display_passive_w = 2.5 * (conditions.ambient_c - state.display_coolant_c)
    turbine_c = state.turbine_c + seconds * (
        conditions.turbine_heating_w - transfer_w) / 14500.0
    coolant_c = state.turbo_coolant_c + seconds * (transfer_w - radiator_w) / 16000.0
    display_c = state.display_coolant_c + seconds * (
        conditions.display_heating_w + display_passive_w - cold_capacity_w) / 5500.0
    next_state = PlantState(turbine_c, coolant_c, display_c)
    # Assumes independent hot-side ducts exhaust to outside the bay.
    # Estimate outlet rise from air mass flow; very low flow means hot ducting.
    total_reject = max(0.0, radiator_w) + peltier_hot_w
    outlet_air = conditions.ambient_c + total_reject / max(1.0, 1200.0 * flow)
    fan_w = 42 * ((controls.inlet_fan**3 + controls.outlet_fan**3) / 2)
    pump_w = 75 * controls.coolant_pump ** 3
    return ThermalResult(next_state, flow, transfer_w, radiator_w,
                         cold_capacity_w, peltier_hot_w, peltier_electrical,
                         fan_w + pump_w + peltier_electrical, outlet_air)
