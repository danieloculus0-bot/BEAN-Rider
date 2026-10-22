"""Integrated, observable driving brain with reproducible memory and alarms.

Read-only observation and analysis only; do not infer vehicle health from an
absent PID or automatically assume a cylinder fault from generic OBD trims.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from .obd import Reader, scan
from .journal import EventJournal
from .injectors import CylinderTrial, review


@dataclass(frozen=True)
class BrainReport:
    observation: dict
    warnings: tuple[dict, ...]
    journal_digest: str
    session_count: int

    def as_dict(self):
        return {"schema": "bean.rider.brain.v1", "observation": self.observation,
                "warnings": list(self.warnings), "journal_digest": self.journal_digest,
                "session_count": self.session_count,
                "ecu_writes": 0}


class RiderBrain:
    def __init__(self, db_path: str | Path):
        self.journal = EventJournal(db_path)
        # Rebuild on restart, then count incrementally. Re-reading the entire
        # driving history at each scan creates quadratic latency for a logger.
        self._seen_dtcs: dict[str, int] = {}
        self._observations = 0
        for row in self.journal.records():
            body = row["body"]
            if body.get("schema") == "bean.rider.obd.scan.v1":
                self._observations += 1
                for code in {pair[0] for pair in body.get("dtcs", [])}:
                    self._seen_dtcs[code] = self._seen_dtcs.get(code, 0) + 1

    def observe(self, reader: Reader, *, timestamp: str | None = None):
        result = scan(reader, timestamp=timestamp).payload()
        dtcs = {code for code, _ in result["dtcs"]}
        warnings = []
        for code in sorted(dtcs):
            count = self._seen_dtcs.get(code, 0)
            warnings.append({"code": code, "repeat_observations": count+1,
                             "priority": "persistent" if count >= 2 else "new_or_recurrent",
                             "recommendation": "read_service_diagnostics_before_tuning"})
        seal = self.journal.append(result)
        self._observations += 1
        for code in dtcs:
            self._seen_dtcs[code] = self._seen_dtcs.get(code, 0) + 1
        return BrainReport(result, tuple(warnings), seal, self._observations)

    def review_injector(self, trial: CylinderTrial):
        result = review(trial)
        seal = self.journal.append(result)
        return {**result, "journal_digest": seal}

    def close(self):
        self.journal.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
