"""Read-only Mode 02 acquisition over an injected ELM327-compatible serial link.

Only unsegmented application responses are supported. Ambiguous ECU replies,
ISO-TP multi-frame traffic and adapter errors fail closed rather than fabricate data.
"""
from __future__ import annotations

import re
from .mode02 import decode_mode02
from .mode01 import SUPPORTED


def parse_elm_response(raw: bytes, pid: int, frame: int = 0) -> bytes:
    """Extract one exact 42 PID FRAME response from an ELM text transaction."""
    if not isinstance(raw, bytes) or b">" not in raw:
        raise ValueError("Incomplete ELM327 response")
    text = raw.split(b">", 1)[0].decode("ascii", errors="strict").upper()
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    candidates = []
    for line in lines:
        compact = re.sub(r"\\s+", "", line)
        if not compact or compact in ("SEARCHING...", "OK") or compact.startswith("020"):
            continue
        if any(word in compact for word in ("NODATA", "ERROR", "STOPPED", "UNABLETOCONNECT", "BUSINIT")):
            raise ValueError("Adapter reported no usable freeze-frame response")
        if not re.fullmatch(r"[0-9A-F]+", compact) or len(compact) % 2:
            raise ValueError("Unsupported ELM response format")
        payload = bytes.fromhex(compact)
        if payload and payload[0] == len(payload) - 1:
            payload = payload[1:]  # single-frame CAN PCI byte
        candidates.append(payload)
    if len(candidates) != 1:
        raise ValueError("Expected exactly one unambiguous ECU response")
    payload = candidates[0]
    decode_mode02(payload, pid, frame)
    return payload


def acquire_freeze_frame(serial_link, pid: int, frame: int = 0) -> dict:
    """Request one Mode 02 PID; serial_link must be an initialized ELM327 link."""
    if type(pid) is not int or pid not in SUPPORTED:
        raise ValueError("Unsupported Mode 02 PID")
    if type(frame) is not int or not 0 <= frame <= 255:
        raise ValueError("Invalid frame number")
    command = f"02{pid:02X}{frame:02X}\r".encode("ascii")
    serial_link.write(command)
    response = serial_link.read_until(b">")
    result = decode_mode02(parse_elm_response(response, pid, frame), pid, frame)
    result["source"] = "elm327_mode02_readonly_unverified_vehicle"
    return result
