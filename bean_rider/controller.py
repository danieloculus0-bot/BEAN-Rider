"""Testable, configurable 4-actuator research controller. No hardware interface."""
from __future__ import annotations

from dataclasses import dataclass
from .thermal import Conditions, Controls, PlantState, _range


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class ControllerConfig:
    fan_gain: float = 0.8
    exhaust_ratio: float = 1.0
    pump_gain: float = 1.0
    peltier_gain: float = 0.8

    def __post_init__(self) -> None:
        for name, upper in (("fan_gain", 3), ("exhaust_ratio", 2),
                            ("pump_gain", 3), ("peltier_gain", 3)):
            _range(name, getattr(self, name), 0, upper)


def command(state: PlantState, conditions: Conditions,
            config: ControllerConfig = ControllerConfig()) -> Controls:
    """Closed-loop heuristic; configuration can be optimized on simulated traces."""
    coolant_error = max(0.0, (state.turbo_coolant_c - 65) / 35)
    hot_error = max(0.0, (state.turbine_c - 125) / 140)
    inlet = _clamp(0.12 + config.fan_gain * coolant_error)
    outlet = _clamp(0.12 + inlet * config.exhaust_ratio)
    pump = _clamp(0.22 + config.pump_gain * hot_error)
    peltier = _clamp(config.peltier_gain * max(0.0, (state.display_coolant_c - 31) / 17))
    return Controls(inlet, outlet, pump, peltier)
