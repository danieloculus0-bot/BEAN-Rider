"""Compact, checksum-verified experiment transport for BEAN's evidence workflow.

This exports experiment data; it is not a replacement for BEAN Core's
hash-chained SQLite Journal. The archive bytes are reproducible for fixed input.
"""
from __future__ import annotations

import gzip
from hashlib import sha256
import json
from pathlib import Path


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def export_report(report: dict, folder: str | Path) -> dict:
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    raw = _canonical(report)
    digest = sha256(raw).hexdigest()
    target = path / "experiment.json.gz"
    # Reproducible gzip header to support content-level comparisons.
    with target.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as stream:
            stream.write(raw)
    manifest = {"schema": "bean.rider.evidence.v1", "archive": target.name,
                "sha256_uncompressed": digest, "bytes_uncompressed": len(raw),
                "evidence_kind": report.get("evidence_kind", "unknown")}
    (path / "manifest.json").write_bytes(_canonical(manifest))
    return manifest


def read_report(folder: str | Path) -> dict:
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "bean.rider.evidence.v1" or manifest.get("archive") != "experiment.json.gz":
        raise ValueError("unexpected manifest")
    with gzip.open(folder / "experiment.json.gz", "rb") as stream:
        raw = stream.read()
    if (len(raw) != manifest["bytes_uncompressed"] or
            sha256(raw).hexdigest() != manifest["sha256_uncompressed"]):
        raise ValueError("experiment evidence mismatch")
    return json.loads(raw)
