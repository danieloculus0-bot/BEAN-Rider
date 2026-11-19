"""Compare two independently sealed local OBD-II journals, without ECU writes.

Run: python -m bean_rider.compare_diagnostics BASELINE.sqlite FOLLOWUP.sqlite
The result is a descriptive comparison, not proof of repair or causality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .diagnostics import summarize_diagnostics
from .journal import EventJournal
from .matched_diagnostics import compare_matched_scans

SCHEMA = "bean.rider.diagnostic_comparison.v1"


def compare_reports(before: dict, after: dict) -> dict:
    """Preserve missing values and do not confuse DTC absence with repair."""
    a = {row["code"]: row for row in before["faults"]}
    b = {row["code"]: row for row in after["faults"]}
    baseline_query = before.get("dtc_query_status_latest", "unknown")
    followup_query = after.get("dtc_query_status_latest", "unknown")
    # An absent code is only an observed negative if the corresponding
    # scanner actually completed a DTC query. Never infer repair from it.
    faults = []
    for code in sorted(a.keys() | b.keys()):
        old, new = a.get(code), b.get(code)
        faults.append({
            "code": code,
            "baseline_observations": old["observations"] if old else 0,
            "followup_observations": new["observations"] if new else 0,
            "baseline_latest_scan": old["seen_in_latest_scan"] if old else False,
            "followup_latest_scan": new["seen_in_latest_scan"] if new else False,
            "classification": "reported_in_both" if old and new else (
                "newly_reported" if new else "not_reported_in_followup"),
            "baseline_absence_confirmed": bool(not old and baseline_query == "queried"),
            "followup_absence_confirmed": bool(not new and followup_query == "queried"),
            "followup_resolution": (
                "still_reported" if new else
                "not_reported_in_queried_followup" if followup_query == "queried"
                else "unknown_followup_query_unavailable"
            ),
        })
    sensors = {}
    for key in sorted(before["pids"].keys() | after["pids"].keys()):
        old = before["pids"].get(key, {})
        new = after["pids"].get(key, {})
        x, y = old.get("average"), new.get("average")
        sensors[key] = {
            "unit": new.get("unit", old.get("unit")),
            "baseline_readings": old.get("readings", 0),
            "followup_readings": new.get("readings", 0),
            "baseline_average": x,
            "followup_average": y,
            "average_delta": round(y - x, 4) if x is not None and y is not None else None,
            "matched_operating_conditions": False,
        }
    return {
        "schema": SCHEMA,
        "baseline_scans": before["samples"],
        "followup_scans": after["samples"],
        "baseline_last_scan_utc": before["last_scan_utc"],
        "followup_last_scan_utc": after["last_scan_utc"],
        "dtcs": faults,
        "baseline_dtc_query_status_latest": baseline_query,
        "followup_dtc_query_status_latest": followup_query,
        "followup_dtc_evidence": (
            "queried" if followup_query == "queried" else "unknown"
        ),
        "pids": sensors,
        "assessment": "descriptive_only_not_repair_or_tuning_validation",
        "limits": [
            "Missing DTCs do not establish a repair or an ECU clearing event.",
            "Sensor averages are unmatched by load, RPM, environment and drive cycle.",
            "Journal integrity is verified; vehicle identity and sensor authenticity are not.",
        ],
        "ecu_writes": 0,
    }


def compare_journals(baseline: Path, followup: Path) -> dict:
    for path in (baseline, followup):
        if not path.is_file() or path.is_symlink():
            raise ValueError("existing regular journal file required")
    with EventJournal(baseline) as first, EventJournal(followup) as second:
        first.verify()
        second.verify()
        before_records, after_records = first.records(), second.records()
        result = compare_reports(summarize_diagnostics(before_records),
                                 summarize_diagnostics(after_records))
        result["condition_matched"] = compare_matched_scans(before_records, after_records)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two local verified diagnostic journals")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("followup", type=Path)
    args = parser.parse_args()
    try:
        result = compare_journals(args.baseline, args.followup)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
