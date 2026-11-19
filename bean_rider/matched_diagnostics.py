"""Condition-matched, read-only comparison of sealed OBD scan journals.

Greedy one-to-one nearest-neighbor matching in RPM/load space. Results describe
sensor changes only; matches are not independent experiments or repair proof.
"""
from __future__ import annotations

from math import isfinite
from .obd import PIDS

SCHEMA = "bean.rider.condition_matched_comparison.v1"


def _valid(value):
    return type(value) in (int, float) and isfinite(value)


def _scans(records):
    for record in records:
        body = record.get("body") if isinstance(record, dict) else None
        if isinstance(body, dict) and body.get("schema") == "bean.rider.obd.scan.v1":
            yield body


def compare_matched_scans(before_records, after_records, *, rpm_tolerance=150,
                          load_tolerance=8):
    """Match each followup scan to at most one baseline scan.

    RPM tolerance is revolutions/minute; load tolerance is percentage points.
    Only readings with both matching conditions present are eligible.
    """
    if not (_valid(rpm_tolerance) and rpm_tolerance > 0 and
            _valid(load_tolerance) and load_tolerance > 0):
        raise ValueError("positive finite RPM and load tolerances required")
    before = list(_scans(before_records))
    after = list(_scans(after_records))
    available = []
    for i, scan in enumerate(before):
        values = scan.get("values")
        if isinstance(values, dict) and all(_valid(values.get(k)) for k in
                                            ("rpm", "engine_load_pct")):
            available.append(i)
    pairs = []
    for j, scan in enumerate(after):
        values = scan.get("values")
        if not isinstance(values, dict) or not all(_valid(values.get(k)) for k in
                                                    ("rpm", "engine_load_pct")):
            continue
        candidates = []
        for i in available:
            baseline = before[i]["values"]
            rpm_delta = abs(values["rpm"] - baseline["rpm"])
            load_delta = abs(values["engine_load_pct"] - baseline["engine_load_pct"])
            if rpm_delta <= rpm_tolerance and load_delta <= load_tolerance:
                distance = (rpm_delta / rpm_tolerance) ** 2 + (load_delta / load_tolerance) ** 2
                candidates.append((distance, i))
        if candidates:
            _, i = min(candidates)
            available.remove(i)
            pairs.append((i, j))
    sensors = {}
    for key, (_, unit) in PIDS.items():
        deltas = []
        for i, j in pairs:
            a, b = before[i]["values"].get(key), after[j]["values"].get(key)
            if _valid(a) and _valid(b):
                deltas.append(b - a)
        sensors[key] = {
            "unit": unit,
            "paired_readings": len(deltas),
            "mean_followup_minus_baseline": round(sum(deltas) / len(deltas), 4)
            if deltas else None,
        }
    return {
        "schema": SCHEMA,
        "baseline_scans": len(before),
        "followup_scans": len(after),
        "matched_pairs": len(pairs),
        "rpm_tolerance": rpm_tolerance,
        "load_tolerance_percentage_points": load_tolerance,
        "pids": sensors,
        "provenance": "local_journal_unverified_vehicle_identity",
        "assessment": "condition_matched_descriptive_only_not_repair_validation",
        "limits": [
            "Greedy nearest-neighbor matches are not causal or independent validation.",
            "Temperature, ambient conditions, vehicle identity and drive cycle are unmatched.",
            "No missing sensor is converted to zero; DTC absence is not repair evidence.",
        ],
        "ecu_writes": 0,
    }
