"""Parking/sleep policy decisions; not an electrical battery disconnect.

The OBD-II connector may be continuously powered from pin 16. External hardware
must actually disconnect or sleep the computer/dongle when the host requests it.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ParkPolicy:
    low_supply_voltage: float = 12.1
    recover_supply_voltage: float = 12.7
    stop_delay_s: float = 120

    def __post_init__(self):
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in
               (self.low_supply_voltage, self.recover_supply_voltage, self.stop_delay_s)):
            raise ValueError("invalid park settings")
        if not 8 < self.low_supply_voltage < self.recover_supply_voltage < 17 or self.stop_delay_s < 0:
            raise ValueError("inconsistent park policy")


@dataclass(frozen=True)
class PowerDecision:
    mode: str
    advisory: str
    awake: bool


def decide(*, ignition: bool | None, supply_voltage: float | None,
           seconds_since_off: float | None, policy: ParkPolicy = ParkPolicy()) -> PowerDecision:
    if ignition is not None and type(ignition) is not bool:
        raise ValueError("ignition signal invalid")
    if supply_voltage is not None and (type(supply_voltage) not in (int, float) or
                                       not math.isfinite(supply_voltage)):
        raise ValueError("supply voltage invalid")
    if seconds_since_off is not None and (type(seconds_since_off) not in (int, float) or
                                          not math.isfinite(seconds_since_off) or seconds_since_off < 0):
        raise ValueError("invalid parked duration")
    if ignition is True:
        return PowerDecision("awake", "ignition present", True)
    if supply_voltage is not None and supply_voltage < policy.low_supply_voltage:
        return PowerDecision("sleep_requested", "low voltage: host must remove/suspend power", False)
    if ignition is False and seconds_since_off is not None and seconds_since_off >= policy.stop_delay_s:
        return PowerDecision("sleep_requested", "parked: host must suspend power", False)
    return PowerDecision("monitor", "ignition status not confirmed or park delay pending", True)
