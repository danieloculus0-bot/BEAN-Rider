"""Local, evidence-first OBD-II diagnostic case summary.

Summarizes stored scanner observations without guessing root causes, asserting
vehicle compatibility, treating missing PIDs as zero, or writing to the ECU.
"""
from __future__ import annotations

from math import isfinite
from .obd import PIDS

SCHEMA = "bean.rider.diagnostics.v1"
CONTEXT_FIELDS = (
    "rpm", "speed_kph", "coolant_c", "intake_c", "manifold_kpa",
    "engine_load_pct", "throttle_pct",
    "short_fuel_trim_bank1_pct", "long_fuel_trim_bank1_pct",
)


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def _context(values):
    if not isinstance(values, dict):
        return {}
    return {key: round(float(values[key]), 4) for key in CONTEXT_FIELDS
            if _number(values.get(key))}


def summarize_diagnostics(records: list[dict]) -> dict:
    """Turn verified EventJournal records into an auditable diagnostic summary.

    DTC absent from the last scan is NOT interpreted as repaired or cleared:
    generic readers can return an empty list when the command is unsupported.
    Sampling cadence and independent confirmation are not established here.
    """
    scans = [row["body"] for row in records if isinstance(row, dict)
             and isinstance(row.get("body"), dict)
             and row["body"].get("schema") == "bean.rider.obd.scan.v1"]
    total = len(scans)
    stats = {}
    for label, (command, unit) in PIDS.items():
        values = [s.get("values", {}).get(label) for s in scans
                  if isinstance(s.get("values"), dict)]
        nums = [float(x) for x in values if _number(x)]
        stats[label] = {
            "unit": unit,
            "readings": len(nums),
            "available_pct": round(100 * len(nums) / total, 1) if total else 0.0,
            "minimum": min(nums) if nums else None,
            "maximum": max(nums) if nums else None,
            "average": round(sum(nums) / len(nums), 4) if nums else None,
        }

    faults = {}
    for index, scan in enumerate(scans):
        stamp = scan.get("timestamp_utc")
        seen = set()
        for pair in scan.get("dtcs", []):
            if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                    or not isinstance(pair[0], str) or not pair[0]
                    or not isinstance(pair[1], str)):
                continue
            code, desc = pair
            if code in seen:
                continue
            seen.add(code)
            entry = faults.get(code)
            if entry is None:
                entry = {
                    "code": code, "description": desc[:250],
                    "observations": 0,
                    "first_seen_utc": stamp,
                    "last_seen_utc": stamp,
                    "first_context": _context(scan.get("values")),
                    "last_context": {},
                    "seen_in_latest_scan": False,
                }
                faults[code] = entry
            entry["observations"] += 1
            entry["last_seen_utc"] = stamp
            entry["last_context"] = _context(scan.get("values"))
            entry["seen_in_latest_scan"] = index == total - 1
            if desc:
                entry["description"] = desc[:250]
    ordered = sorted(faults.values(),
                     key=lambda x: (-int(x["seen_in_latest_scan"]),
                                    -x["observations"], x["code"]))

    return {
        "schema": SCHEMA,
        "purpose": "diagnostic_evidence_review_not_root_cause_determination",
        "samples": total,
        "first_scan_utc": scans[0].get("timestamp_utc") if total else None,
        "last_scan_utc": scans[-1].get("timestamp_utc") if total else None,
        "distinct_reported_dtcs": len(faults),
        "faults": ordered,
        "pids": stats,
        "data_provenance": "local_journal_records_not_sensor_authenticated",
        "limits": [
            "Only generic PIDs queried by BEAN-Rider are included.",
            "An absent DTC or PID does not prove a repaired component or healthy system.",
            "Occurrences count scans, not separate drive cycles or confirmed failures.",
            "Readings are not automatically matched for load, speed or temperature.",
            "No vehicle-specific tests, freeze frames or OEM service data are implied.",
        ],
        "ecu_writes": 0,
    }
