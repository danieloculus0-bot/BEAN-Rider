"""Local append-only telemetry/diagnostics event ledger with hash-chain replay.

A standalone BEAN-Rider record, not a replacement for BEAN Core's Journal.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sqlite3

SCHEMA = "bean.rider.journal.v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(canonical(value)).hexdigest()


class EventJournal:
    def __init__(self, path):
        p = Path(path)
        if p.is_symlink():
            raise ValueError("journal symlink rejected")
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(p))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=4000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            previous_digest TEXT NOT NULL, digest TEXT NOT NULL,
            body TEXT NOT NULL, created_utc TEXT NOT NULL)""")
        self.db.commit()
        try:
            self.verify()
        except BaseException:
            self.db.close()
            raise

    def append(self, body: dict):
        if not isinstance(body, dict) or "schema" not in body:
            raise ValueError("event schema required")
        blob = canonical(body).decode("utf-8")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            last = self.db.execute("SELECT digest FROM events ORDER BY id DESC LIMIT 1").fetchone()
            prev = last[0] if last else "GENESIS"
            seal = digest({"previous": prev, "body": body})
            now = datetime.now(timezone.utc).isoformat()
            self.db.execute("INSERT INTO events (previous_digest,digest,body,created_utc) VALUES (?,?,?,?)",
                            (prev, seal, blob, now))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return seal

    def records(self):
        return [{"id": row["id"], "previous_digest": row["previous_digest"],
                 "digest": row["digest"], "body": json.loads(row["body"]),
                 "created_utc": row["created_utc"]} for row in
                self.db.execute("SELECT * FROM events ORDER BY id")]

    def verify(self):
        prev = "GENESIS"
        for row in self.records():
            expected = digest({"previous": prev, "body": row["body"]})
            if row["digest"] != expected or row["previous_digest"] != prev:
                raise ValueError("tampered or discontinuous RIDER journal")
            prev = expected
        return {"schema": SCHEMA, "events": self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "head": prev}

    def export_gzip(self, output):
        """Local export; potentially private records must not be committed to GitHub."""
        self.verify()
        rows = self.records()
        data = canonical({"schema": SCHEMA, "rows": rows})+b"\n"
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            with gzip.GzipFile(fileobj=f, mode="wb", filename="", mtime=0) as gz:
                gz.write(data)
        with gzip.open(path, "rb") as gz:
            if gz.read() != data:
                raise ValueError("gzip roundtrip mismatch")
        return {"compressed_bytes": path.stat().st_size, "rows": len(rows),
                "uncompressed_sha256": sha256(data).hexdigest(), "source": "local_private_export"}

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
