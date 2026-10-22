"""Read-only normalized telemetry import; no OBD/CAN/ECU command support."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .thermal import _range

REQUIRED_COLUMNS = ("time_s", "rpm", "speed_kph", "coolant_c", "oil_c",
                    "intake_c", "manifold_kpa", "lambda_measured", "knock_retard_deg")


@dataclass(frozen=True)
class Telemetry:
    time_s: float
    rpm: float
    speed_kph: float
    coolant_c: float
    oil_c: float
    intake_c: float
    manifold_kpa: float
    lambda_measured: float
    knock_retard_deg: float

    def __post_init__(self) -> None:
        bounds = {"time_s": (0, 1e10), "rpm": (0, 12000), "speed_kph": (0, 450),
                  "coolant_c": (-40, 220), "oil_c": (-40, 240),
                  "intake_c": (-40, 180), "manifold_kpa": (5, 400),
                  "lambda_measured": (0.4, 2.0), "knock_retard_deg": (0, 40)}
        for field, (low, high) in bounds.items():
            _range(field, getattr(self, field), low, high)


def read_csv(path: str | Path) -> tuple[Telemetry, ...]:
    """Load bounded numeric columns in explicit SI/automotive units."""
    with Path(path).open("r", newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise ValueError("missing required telemetry columns or units")
        rows = []
        previous = -1.0
        for row in reader:
            try:
                item = Telemetry(**{key: float(row[key]) for key in REQUIRED_COLUMNS})
            except (TypeError, KeyError) as exc:
                raise ValueError("unusable telemetry value") from exc
            if item.time_s <= previous:
                raise ValueError("timestamps must increase strictly")
            previous = item.time_s
            rows.append(item)
            if len(rows) > 100000:
                raise ValueError("too many rows; split into trips")
        if not rows:
            raise ValueError("empty telemetry")
        return tuple(rows)


def describe(rows: tuple[Telemetry, ...]) -> dict:
    if not rows:
        raise ValueError("no readings")
    return {"schema": "bean.rider.telemetry.summary.v1",
            "readings": len(rows),
            "seconds_observed": round(rows[-1].time_s - rows[0].time_s, 3),
            "max_rpm": max(r.rpm for r in rows),
            "max_coolant_c": max(r.coolant_c for r in rows),
            "max_oil_c": max(r.oil_c for r in rows),
            "max_knock_retard_deg": max(r.knock_retard_deg for r in rows),
            "max_manifold_kpa": max(r.manifold_kpa for r in rows),
            "minimum_lambda": min(r.lambda_measured for r in rows),
            "source_kind": "caller_provided_csv_not_authenticated",
            "diagnostic_conclusion": "none; thresholds depend on engine and operating state"}
