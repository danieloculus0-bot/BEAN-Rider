"""Cylinder-specific compensation evidence and failure detection.

No injector writes. Generic emissions OBD cannot measure single-cylinder drift.
A physical leaking injector can flow when commanded closed: not software-fixable.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


def _finite(x):
    return type(x) in (int, float) and math.isfinite(x)


@dataclass(frozen=True)
class CylinderTrial:
    engine_id: str
    cylinder: int
    condition_id: str
    source: str
    baseline_error_pct: float
    corrected_error_pct: float
    latest_error_pct: float
    evidence_count: int
    compensation_pct: float
    mechanical_leak_suspected: bool = False
    evidence_kind: str = "simulated"

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in
                   (self.engine_id, self.condition_id, self.source)):
            raise ValueError("engine, condition and source required")
        if type(self.cylinder) is not int or not 1 <= self.cylinder <= 32:
            raise ValueError("invalid cylinder")
        if type(self.evidence_count) is not int or self.evidence_count < 0:
            raise ValueError("invalid count")
        if self.evidence_kind not in ("simulated", "measured", "caller_supplied"):
            raise ValueError("invalid evidence kind")
        for key in ("baseline_error_pct", "corrected_error_pct",
                    "latest_error_pct", "compensation_pct"):
            if not _finite(getattr(self, key)) or abs(getattr(self, key)) > 200:
                raise ValueError("invalid observation " + key)
        if type(self.mechanical_leak_suspected) is not bool:
            raise ValueError("invalid leak report")


def review(trial: CylinderTrial) -> dict:
    """Score matched evidence supplied by a caller; no automatic ECU actuation.

    Positive errors indicate deviation magnitude; comparisons use absolute
    values. Caller must ensure load, ambient and fuel conditions are matched.
    """
    baseline = abs(trial.baseline_error_pct)
    corrected = abs(trial.corrected_error_pct)
    latest = abs(trial.latest_error_pct)
    if trial.evidence_count < 3:
        status, interval = "insufficient_evidence", None
    elif trial.mechanical_leak_suspected:
        status, interval = "mechanical_fault_not_tunable", 0
    elif latest > corrected * 1.20 and latest - corrected >= 0.5:
        status, interval = "degrading_after_compensation", 300
    elif corrected >= baseline - 0.25:
        status, interval = "compensation_failed", 900
    elif latest >= baseline:
        status, interval = "compensation_regressed", 900
    else:
        status, interval = "improved_on_matched_input", 86400
    return {"schema": "bean.rider.injector.review.v1", "engine_id": trial.engine_id,
            "cylinder": trial.cylinder, "condition_id": trial.condition_id,
            "status": status, "baseline_abs_error_pct": baseline,
            "corrected_abs_error_pct": corrected, "latest_abs_error_pct": latest,
            "compensation_pct": trial.compensation_pct,
            "next_warning_after_s": interval, "evidence_kind": trial.evidence_kind,
            "evidence_count": trial.evidence_count, "source": trial.source,
            "verification": "caller_supplied_not_authenticated",
            "action": ("repair_and_verify_injector_mechanically" if trial.mechanical_leak_suspected else
                       "inspect_degradation_and_reassess_calibration" if status in
                       ("degrading_after_compensation", "compensation_failed", "compensation_regressed") else
                       "collect_matched_cylinder_evidence" if interval is None else
                       "continue_trending_with_original_evidence"),
            "ecu_write_performed": False}
