"""Engine-family roadmap and truthful OBD-II capability metadata.

A vehicle family is not an ECU protocol. Generic OBD-II availability varies by
vehicle, model year, emissions market, firmware and installed interface.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineFamily:
    key: str
    manufacturer: str
    family: str
    examples: tuple[str, ...]
    phase: int
    notes: str
    generic_obd: str = "vehicle_dependent"
    ecu_mapping: str = "not_implemented"

    def payload(self) -> dict:
        return {"key": self.key, "manufacturer": self.manufacturer,
                "family": self.family, "examples": list(self.examples),
                "phase": self.phase, "notes": self.notes,
                "generic_obd": self.generic_obd, "ecu_mapping": self.ecu_mapping}


# These are engine-family examples and a development queue, not ECU compatibility
# certificates. The stock ECU/ECM generation must be identified per vehicle.
FAMILIES = (
    EngineFamily("gm-ls", "GM", "LS Gen III/IV V8", ("LS1", "LS3", "LQ4", "L92"), 1,
                 "Port-injected applications vary by PCM generation and year."),
    EngineFamily("gm-lt", "GM", "LT Gen V V8", ("LT1", "LT4", "L83"), 1,
                 "Direct-injection engine controls and OEM security are application-specific."),
    EngineFamily("maserati-f136", "Maserati", "F136 V8", ("GranTurismo 4.2", "GranTurismo 4.7"), 2,
                 "Factory ECU calibration access not implemented."),
    EngineFamily("vw-ea888", "Volkswagen", "EA888", ("2.0 TSI", "2.0 TFSI"), 3,
                 "Engine generations and ECU variants require separate definitions."),
    EngineFamily("mercedes-v6-v8", "Mercedes-Benz", "M276 / M177", ("M276", "M177"), 3,
                 "OBD emission sensors are not equivalent to manufacturer diagnostic data."),
    EngineFamily("audi-v8", "Audi", "4.0 TFSI", ("Audi 4.0 TFSI" ,), 3,
                 "Do not assume Volkswagen calibration interchangeability."),
    EngineFamily("bmw-b58", "BMW", "B58", ("B58 straight-six",), 3,
                 "DME generation and security must be identified separately."),
    EngineFamily("ferrari-f154", "Ferrari", "F154 V8", ("F154 turbo V8",), 3,
                 "Research catalog only; no ECU flash or manufacturer diagnostic support."),
)
CATALOG = {x.key: x for x in FAMILIES}


def get_family(key: str) -> EngineFamily:
    if key not in CATALOG:
        raise ValueError("unknown engine family; use 'engine-families' for catalog")
    return CATALOG[key]


def catalog() -> dict:
    return {"schema": "bean.rider.engine.catalog.v1", "families": [p.payload() for p in FAMILIES],
            "instrument": "wired_generic_obd2_over_explicit_serial_port",
            "mapping": "offline_workbench_only", "ecu_write": False,
            "compatibility": "vehicle_year_firmware_and_adapter_specific"}
