"""Offline SAE J1979 Mode 02 freeze-frame PID decoder.

Accepts one fully reassembled application response: 42 PID frame data...
CAN/ISO-TP framing and ECU selection are the transport's responsibility.
No OBD commands are transmitted and no freeze-frame availability is inferred.
"""
from __future__ import annotations

from .mode01 import SUPPORTED, decode_mode01


def decode_mode02(payload: bytes, pid: int, frame: int = 0) -> dict:
    """Decode a supported Mode 02 freeze-frame PID using Mode 01 scaling.

    The third byte of a positive Mode 02 response is the requested frame
    number. This routine does not claim that an ECU supports that frame.
    """
    if type(pid) is not int or pid not in SUPPORTED:
        raise ValueError("Unsupported Mode 02 PID")
    if type(frame) is not int or not 0 <= frame <= 255:
        raise ValueError("Freeze-frame number must be an unsigned byte")
    if not isinstance(payload, bytes):
        raise TypeError("payload must be raw application bytes")
    expected_length = SUPPORTED[pid][0] + 3
    if (len(payload) != expected_length
            or payload[:3] != bytes((0x42, pid, frame))):
        raise ValueError("Invalid Mode 02 positive response, frame or length")
    # Mode 02 uses the same PID data scaling as Mode 01 for these PIDs.
    decoded = decode_mode01(bytes((0x41, pid)) + payload[3:], pid)
    return {
        **decoded,
        "mode": "02",
        "frame": frame,
        "source": "raw_obd_mode02_freeze_frame_unverified",
        "ecu_writes": 0,
    }
