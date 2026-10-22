"""Read-only generic OBD-II scanning, designed for a permanently installed logger.

Generic OBD-II supports only a vehicle-dependent subset of sensors and DTCs.
It does NOT expose universal injector/cylinder trim or engine calibration maps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Protocol

PIDS = {
    "rpm": ("RPM", "revolutions_per_minute"),
    "speed_kph": ("SPEED", "kilometer_per_hour"),
    "coolant_c": ("COOLANT_TEMP", "degC"),
    "intake_c": ("INTAKE_TEMP", "degC"),
    "manifold_kpa": ("INTAKE_PRESSURE", "kilopascal"),
    "engine_load_pct": ("ENGINE_LOAD", "percent"),
    "throttle_pct": ("THROTTLE_POS", "percent"),
    "short_fuel_trim_bank1_pct": ("SHORT_FUEL_TRIM_1", "percent"),
    "long_fuel_trim_bank1_pct": ("LONG_FUEL_TRIM_1", "percent"),
}


class Reader(Protocol):
    def read(self, name: str, unit: str): ...
    def dtcs(self) -> list[tuple[str, str]]: ...
    def close(self) -> None: ...


def _numeric(value):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("OBD adapter returned nonfinite reading")
    return round(float(value), 4)


@dataclass(frozen=True)
class Scan:
    timestamp_utc: str
    values: dict[str, float | None]
    dtcs: tuple[tuple[str, str], ...]
    missing_pids: tuple[str, ...]
    source: str

    def payload(self):
        return {"schema": "bean.rider.obd.scan.v1", "timestamp_utc": self.timestamp_utc,
                "values": self.values, "dtcs": [list(x) for x in self.dtcs],
                "missing_pids": list(self.missing_pids), "source": self.source,
                "conclusion": "read_only_observations_not_ecu_calibration"}


def scan(reader: Reader, *, dtc: bool = True, timestamp: str | None = None) -> Scan:
    values = {}
    for label, (command, unit) in PIDS.items():
        try:
            values[label] = _numeric(reader.read(command, unit))
        except (ValueError, AttributeError, LookupError, RuntimeError, TypeError):
            values[label] = None
    faults = reader.dtcs() if dtc else []
    cleaned = []
    for code, description in faults:
        if not isinstance(code, str) or len(code)>12 or not isinstance(description, str):
            raise ValueError("invalid DTC response")
        cleaned.append((code, description[:250]))
    return Scan(timestamp or datetime.now(timezone.utc).isoformat(), values,
                tuple(cleaned), tuple(k for k,v in values.items() if v is None),
                "obd2_adapter_unverified_sensor_origin")


class PythonOBDReader:
    """Optional python-OBD package interface. No clear-DTC or arbitrary commands."""

    def __init__(self, port: str, *, timeout: float = 1.0):
        if not port or not 0 < timeout <= 10:
            raise ValueError("explicit serial port and reasonable timeout required")
        try:
            import obd
        except ImportError as exc:
            raise RuntimeError("Install optional dependency: pip install python-OBD") from exc
        self._obd = obd
        self.connection = obd.OBD(portstr=port, fast=False, timeout=timeout)
        if not self.connection.is_connected():
            self.connection.close()
            raise RuntimeError("ELM327 OBD adapter did not connect")

    def read(self, name: str, unit: str):
        if name not in {item[0] for item in PIDS.values()}:
            raise ValueError("non-allowlisted PID")
        command = getattr(self._obd.commands, name)
        if not self.connection.supports(command):
            return None
        answer = self.connection.query(command)
        if answer.is_null() or answer.value is None:
            return None
        quantity = answer.value
        if not hasattr(quantity, "to"):
            return None
        try:
            return float(quantity.to(unit).magnitude)
        except (ValueError, TypeError, AttributeError):
            return None

    def dtcs(self):
        cmd = self._obd.commands.GET_DTC
        if not self.connection.supports(cmd):
            return []
        answer = self.connection.query(cmd)
        return list(answer.value or []) if not answer.is_null() else []

    def close(self):
        self.connection.close()


class FakeOBDReader:
    """Deterministic offline adapter for testing and demo only."""

    def __init__(self, data=None, faults=()):
        self.data = dict(data or {"RPM": 900, "SPEED": 0, "COOLANT_TEMP": 84,
                                  "INTAKE_TEMP": 26, "INTAKE_PRESSURE": 38})
        self.faults = list(faults)
        self.closed = False

    def read(self, name, unit):
        return self.data.get(name)

    def dtcs(self):
        return list(self.faults)

    def close(self):
        self.closed = True
