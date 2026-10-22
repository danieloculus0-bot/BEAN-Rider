"""Engine-agnostic calibration map workbench. Offline only; no ECU flashing.

TunerStudio .msq parsing is read-only and requires callers to identify exact
axis/table names. Vendor-specific axis layout and scaling are not inferred.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _axis(name, axis):
    if not isinstance(axis, (tuple, list)) or len(axis) < 2:
        raise ValueError(f"{name} axis needs at least two values")
    if not all(_finite(v) for v in axis) or any(a >= b for a, b in zip(axis, axis[1:])):
        raise ValueError(f"{name} axis must be finite, strictly increasing")


@dataclass(frozen=True)
class CalibrationMap:
    name: str
    engine_profile: str
    ecu_family: str
    x_unit: str
    y_unit: str
    value_unit: str
    x_axis: tuple[float, ...]
    y_axis: tuple[float, ...]
    values: tuple[tuple[float, ...], ...]
    source: str = "local_user_supplied"

    def __post_init__(self):
        if any(not isinstance(s, str) or not s.strip() for s in
               (self.name, self.engine_profile, self.ecu_family,
                self.x_unit, self.y_unit, self.value_unit, self.source)):
            raise ValueError("named source/profile/units required")
        _axis("x", self.x_axis)
        _axis("y", self.y_axis)
        if len(self.values) != len(self.y_axis) or any(len(row) != len(self.x_axis) for row in self.values):
            raise ValueError("map dimensions do not match axes")
        if not all(_finite(v) for row in self.values for v in row):
            raise ValueError("map contains nonfinite values")
        if len(self.x_axis) * len(self.y_axis) > 20000:
            raise ValueError("map too large")

    def payload(self):
        return {k: getattr(self, k) for k in
                ("name", "engine_profile", "ecu_family", "x_unit", "y_unit",
                 "value_unit", "x_axis", "y_axis", "values", "source")}

    def fingerprint(self):
        return sha256(json.dumps(self.payload(), sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def edit(self, x_index: int, y_index: int, value: float) -> "CalibrationMap":
        if type(x_index) is not int or type(y_index) is not int or not _finite(value):
            raise ValueError("invalid edit")
        if not (0 <= x_index < len(self.x_axis) and 0 <= y_index < len(self.y_axis)):
            raise IndexError("out of map bounds")
        rows = [list(row) for row in self.values]
        rows[y_index][x_index] = float(value)
        return replace(self, values=tuple(tuple(row) for row in rows), source="edited_from:"+self.fingerprint())

    def sample(self, x: float, y: float) -> float:
        """Bilinear interpolation, explicitly refusing uncalibrated extrapolation."""
        if not _finite(x) or not _finite(y):
            raise ValueError("invalid coordinates")
        if not (self.x_axis[0] <= x <= self.x_axis[-1] and self.y_axis[0] <= y <= self.y_axis[-1]):
            raise ValueError("outside calibration axes")
        def bracket(a, value):
            for i in range(len(a) - 1):
                if a[i] <= value <= a[i+1]:
                    return i, (value-a[i])/(a[i+1]-a[i])
            raise AssertionError("validated in range")
        i, tx = bracket(self.x_axis, x)
        j, ty = bracket(self.y_axis, y)
        v = self.values
        return ((1-tx)*(1-ty)*v[j][i] + tx*(1-ty)*v[j][i+1] +
                (1-tx)*ty*v[j+1][i] + tx*ty*v[j+1][i+1])


def compare_maps(before: CalibrationMap, after: CalibrationMap) -> dict:
    labels = ("name", "engine_profile", "ecu_family", "x_unit", "y_unit", "value_unit", "x_axis", "y_axis")
    if any(getattr(before, label) != getattr(after, label) for label in labels):
        raise ValueError("maps differ in identity, units, or grid; not comparable")
    changes = []
    for y, (r0, r1) in enumerate(zip(before.values, after.values)):
        for x, (a, b) in enumerate(zip(r0, r1)):
            if a != b:
                changes.append({"x": x, "y": y, "before": a, "after": b, "delta": b-a})
    return {"schema": "bean.rider.map.diff.v1", "before_sha256": before.fingerprint(),
            "after_sha256": after.fingerprint(), "changed_cells": len(changes), "changes": changes,
            "execution": "offline_not_applied_to_ecu"}


def load_map_json(path: str | Path) -> CalibrationMap:
    file = Path(path)
    if file.stat().st_size > 1_000_000:
        raise ValueError("oversized map")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "bean.rider.map.v1":
        raise ValueError("unknown map schema")
    allowed = {"schema", *CalibrationMap.__dataclass_fields__.keys()}
    if set(data) - allowed:
        raise ValueError("unknown fields")
    for key in ("x_axis", "y_axis"):
        data[key] = tuple(data[key])
    data["values"] = tuple(tuple(row) for row in data["values"])
    data.pop("schema")
    return CalibrationMap(**data)


def save_map_json(calibration: CalibrationMap, path: str | Path):
    payload = {"schema": "bean.rider.map.v1", **calibration.payload()}
    Path(path).write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def _msq_variables(path: str | Path):
    """Read standard TunerStudio XML pcVariables without resolving entities."""
    file = Path(path)
    if file.stat().st_size > 5_000_000:
        raise ValueError("oversized msq")
    raw = file.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("external entities and DTD not supported")
    root = ET.fromstring(raw)
    if root.tag.split("}")[-1] != "msq":
        raise ValueError("not an MSQ document")
    variables = {}
    for item in root.iter():
        if item.tag.split("}")[-1] == "pcVariable":
            name = item.get("name")
            if name in variables:
                raise ValueError("duplicate MSQ variable")
            if name:
                variables[name] = item
    return root, variables


def inspect_msq(path: str | Path) -> dict:
    """Inspect known open TunerStudio/Speeduino/rusEFI metadata, without copying tune values."""
    root, variables = _msq_variables(path)
    version = next((x.attrib for x in root.iter() if x.tag.split("}")[-1] == "versionInfo"), {})
    tables = []
    for name, el in sorted(variables.items()):
        if el.get("rows") and el.get("cols"):
            tables.append({"name": name, "rows": int(el.get("rows")),
                           "cols": int(el.get("cols")), "unit": el.get("units", "")})
    return {"schema": "bean.rider.msq.inspect.v1", "firmware": version.get("firmwareInfo", "unknown"),
            "signature": version.get("signature", "unknown"), "tables": tables,
            "variables": len(variables), "values_exported": False,
            "compatibility": "requires matching firmware/ECU; reference only"}


def _read_msq_numbers(item):
    raw = (item.text or "").replace(",", " ").split()
    if not raw:
        raise ValueError("empty numeric variable")
    try:
        numbers = [float(x) for x in raw]
    except ValueError as exc:
        raise ValueError("variable is not plain numeric data") from exc
    if not all(_finite(v) for v in numbers):
        raise ValueError("invalid numeric table")
    return numbers


def load_msq_map(path: str | Path, *, table: str, x_variable: str, y_variable: str,
                 profile: str, ecu_family: str, x_unit: str, y_unit: str,
                 value_unit: str) -> CalibrationMap:
    """Explicit 2D MSQ extraction. Caller must verify axes/units/row order against the ECU INI."""
    _root, vars = _msq_variables(path)
    if len({table, x_variable, y_variable}) != 3:
        raise ValueError("separate table and axes required")
    try:
        matrix, xvar, yvar = [vars[k] for k in (table, x_variable, y_variable)]
    except KeyError as exc:
        raise ValueError("missing named MSQ constant") from exc
    rows = int(matrix.get("rows", "0"))
    cols = int(matrix.get("cols", "0"))
    if rows < 2 or cols < 2 or rows*cols > 20000:
        raise ValueError("expected a 2D table")
    xs, ys = _read_msq_numbers(xvar), _read_msq_numbers(yvar)
    vals = _read_msq_numbers(matrix)
    if len(xs) != cols or len(ys) != rows or len(vals) != rows*cols:
        raise ValueError("MSQ dimensions mismatch: check firmware axis names")
    return CalibrationMap(table, profile, ecu_family, x_unit, y_unit,
                          value_unit, tuple(xs), tuple(ys),
                          tuple(tuple(vals[y*cols:(y+1)*cols]) for y in range(rows)),
                          "imported_msq_sha256:"+sha256(Path(path).read_bytes()).hexdigest())
