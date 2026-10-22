"""Capabilities are explicit: the same brain supports different ECU backends,
not every engine or factory ECU supports every map or sensor.
"""
from __future__ import annotations
from dataclasses import dataclass

REFERENCE_ECOSYSTEMS = (
    {"name": "Speeduino", "url": "https://github.com/speeduino/speeduino",
     "config": "TunerStudio .ini and .msq", "tune_samples": "https://github.com/speeduino/Tunes",
     "tune_license": "CC-BY-NC-4.0 (third-party source; not bundled)",
     "capability": "reference file inspection and explicit table import"},
    {"name": "rusEFI", "url": "https://github.com/rusefi/rusefi",
     "config": "rusEFI/TunerStudio tuning configuration", "tune_samples": "https://wiki.rusefi.com/Online/",
     "tune_license": "check each tune's terms (not bundled)",
     "capability": "reference file inspection and explicit table import"},
)


@dataclass(frozen=True)
class EngineProfile:
    label: str
    cylinders: int
    stroke_cycle: int
    fuel: str
    ecu: str
    supports_cylinder_data: bool = False
    supports_calibration_write: bool = False

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in
               (self.label, self.fuel, self.ecu)):
            raise ValueError("engine identity required")
        if type(self.cylinders) is not int or not 1 <= self.cylinders <= 32:
            raise ValueError("invalid cylinder count")
        if self.stroke_cycle not in (2, 4):
            raise ValueError("unsupported combustion cycle")
        if type(self.supports_cylinder_data) is not bool or type(self.supports_calibration_write) is not bool:
            raise ValueError("invalid declared capability")


EXAMPLE_PROFILES = {
    "maserati-f136-4.7": EngineProfile("Maserati F136 4.7 concept", 8, 4, "gasoline", "OEM proprietary"),
    "sprinter-om647": EngineProfile("Sprinter OM647 concept", 5, 4, "diesel", "OEM proprietary"),
    "generic-4-cylinder": EngineProfile("Generic four-cylinder example", 4, 4, "gasoline", "unknown"),
}
