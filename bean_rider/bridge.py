"""Explicit BEAN integration contract, independent of BEAN runtime.

BEAN Core may ingest a report via its existing Journal, and experimental
SpongeTD can be trained by a separate adapter using verified matched reward
receipts. Neither is silently imported or claimed to be active here.
"""
from __future__ import annotations

from hashlib import sha256
import json


def bean_event(report: dict) -> dict:
    """Build a portable evidence record consumable by a host-owned bridge."""
    if report.get("schema") != "bean.rider.experiment.v1":
        raise ValueError("unrecognized report")
    blob = json.dumps(report, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")
    return {"schema": "bean.rider.bridge.v1",
            "objective": "bean.rider.thermal.simulated",
            "report_sha256": sha256(blob).hexdigest(),
            "evidence_kind": report["evidence_kind"],
            "optimizer": report["optimizer"],
            "holdout_metric": "score",
            "lower_is_better": True,
            "matched_holdout_scenario": (
                report["baseline_holdout"]["scenario_hash"] ==
                report["selected_holdout"]["scenario_hash"]),
            "baseline_score": report["baseline_holdout"]["score"],
            "candidate_score": report["selected_holdout"]["score"],
            "learning_claim": "none: deterministic parameter search only"}
