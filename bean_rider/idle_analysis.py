"""Offline read-only idle stability analysis for timestamped generic OBD-II samples.

Samples must contain elapsed_s, rpm and speed_kph. No ECU writes or diagnosis.
"""
from __future__ import annotations

from math import isfinite, sqrt


def analyze_idle(samples: list[dict], *, max_speed_kph: float = 1.0,
                 min_rpm: float = 400.0, max_gap_s: float = 5.0) -> dict:
    """Summarize consecutive stationary running samples without bridging gaps.

    Duration is measured only across consecutive eligible samples. RPM
    statistics are sample-weighted, not time-weighted. All input is synthetic
    or externally acquired and cannot establish sensor accuracy.
    """
    if not isinstance(samples, list):
        raise ValueError("samples must be a list")
    for value in (max_speed_kph, min_rpm, max_gap_s):
        if type(value) not in (int, float) or not isfinite(value) or value <= 0:
            raise ValueError("thresholds must be positive finite numbers")
    previous_time = None
    previous_idle = False
    idle_rpm = []
    duration = 0.0
    intervals = 0
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("each sample must be a mapping")
        t, rpm, speed = (sample.get(key) for key in ("elapsed_s", "rpm", "speed_kph"))
        if any(type(v) not in (int, float) or not isfinite(v) for v in (t, rpm, speed)):
            raise ValueError("elapsed_s, rpm and speed_kph must be finite numbers")
        if t < 0 or rpm < 0 or speed < 0 or (previous_time is not None and t <= previous_time):
            raise ValueError("timestamps must increase and readings cannot be negative")
        eligible = rpm >= min_rpm and speed <= max_speed_kph
        if eligible:
            idle_rpm.append(float(rpm))
        if eligible and previous_idle and previous_time is not None and t - previous_time <= max_gap_s:
            duration += t - previous_time
            intervals += 1
        previous_time, previous_idle = t, eligible
    mean = sum(idle_rpm) / len(idle_rpm) if idle_rpm else None
    deviation = (sqrt(sum((x - mean) ** 2 for x in idle_rpm) / len(idle_rpm))
                 if idle_rpm else None)
    return {
        "schema": "bean.rider.idle_analysis.v1",
        "sample_count": len(samples),
        "eligible_samples": len(idle_rpm),
        "qualified_intervals": intervals,
        "observed_idle_seconds": round(duration, 3),
        "rpm_min": min(idle_rpm) if idle_rpm else None,
        "rpm_max": max(idle_rpm) if idle_rpm else None,
        "rpm_mean": round(mean, 3) if mean is not None else None,
        "rpm_population_stddev": round(deviation, 3) if deviation is not None else None,
        "source": "caller_supplied_observations_unverified",
        "diagnosis": "unknown",
        "ecu_writes": 0,
    }
