"""Pure, offline SAE J1979 Mode 01 response decoder (no ECU writes).

Input is the OBD application payload starting with 0x41, not a CAN frame.
CAN/ISO-TP framing, multi-frame reassembly and transport validation belong to
the adapter layer. Values are engineering units; no vehicle-specific inference.
"""
from __future__ import annotations

import math

# PID: (number of data bytes, output name, unit)
SUPPORTED = {
    0x04: (1, "engine_load_pct", "percent"),
    0x05: (1, "coolant_c", "degC"),
    0x06: (1, "short_fuel_trim_bank1_pct", "percent"),
    0x07: (1, "long_fuel_trim_bank1_pct", "percent"),
    0x0B: (1, "manifold_kpa", "kilopascal"),
    0x0C: (2, "rpm", "revolutions_per_minute"),
    0x0D: (1, "speed_kph", "kilometer_per_hour"),
    0x0F: (1, "intake_c", "degC"),
    0x11: (1, "throttle_pct", "percent"),
}


def decode_mode01(payload: bytes, pid: int) -> dict:
    """Decode a positive Mode 01 reply; reject malformed/negative responses.

    Example: decode_mode01(bytes.fromhex("41 0C 1A F8"), 0x0C)
    returns 1726 rpm. This does not establish sensor accuracy.
    """
    if type(pid) is not int or pid not in SUPPORTED:
        raise ValueError("Unsupported Mode 01 PID")
    if not isinstance(payload, bytes):
        raise TypeError("payload must be raw application bytes")
    length, name, unit = SUPPORTED[pid]
    if len(payload) != length + 2 or payload[:2] != bytes((0x41, pid)):
        raise ValueError("Invalid Mode 01 positive response or payload length")
    a = payload[2]
    if pid == 0x0C:
        value = (256 * a + payload[3]) / 4
    elif pid in (0x05, 0x0F):
        value = a - 40
    elif pid in (0x06, 0x07):
        value = (a - 128) * 100 / 128
    elif pid in (0x04, 0x11):
        value = a * 100 / 255
    else:
        value = float(a)
    if not math.isfinite(value):
        raise ValueError("Nonfinite decoded value")
    return {"pid": f"01{pid:02X}", "name": name, "value": round(value, 4),
            "unit": unit, "source": "raw_obd_mode01_unverified",
            "ecu_writes": 0}
