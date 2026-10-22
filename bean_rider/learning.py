"""Reproducible, persistent experiment scoreboard; never autonomously writes ECU maps.

Uses BEAN's evidence-first philosophy without pretending experimental SpongeTD
is active or that caller-attested measurements are independently authenticated.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import re
from .journal import EventJournal

DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Comparison:
    engine_profile: str
    strategy: str
    condition_id: str
    metric: str
    direction: str
    baseline: float
    candidate: float
    cases_matched: int
    cases_expected: int
    baseline_run: str
    candidate_run: str
    evaluation_sha256: str
    evidence_kind: str = "synthetic"

    def __post_init__(self):
        for k in ("engine_profile","strategy","condition_id","metric","baseline_run","candidate_run"):
            if not isinstance(getattr(self,k),str) or not getattr(self,k).strip():
                raise ValueError("missing identifier: "+k)
        if self.direction not in ("lower", "higher"):
            raise ValueError("unknown metric direction")
        if self.evidence_kind not in ("synthetic", "measured", "caller_supplied"):
            raise ValueError("unknown evidence type")
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (self.baseline,self.candidate)):
            raise ValueError("nonfinite measured result")
        if (type(self.cases_matched) is not int or type(self.cases_expected) is not int or
            not 0 <= self.cases_matched <= self.cases_expected or self.cases_expected < 1):
            raise ValueError("invalid coverage")
        if not isinstance(self.evaluation_sha256,str) or not DIGEST.fullmatch(self.evaluation_sha256):
            raise ValueError("invalid evidence checksum")


def evaluate_comparison(comparison: Comparison, journal: EventJournal) -> dict:
    """Score one attested comparison once; record invalid/incomplete attempts too."""
    prior = journal.records()
    seen = any(e["body"].get("schema")=="bean.rider.score.v1" and
               e["body"].get("evaluation_sha256")==comparison.evaluation_sha256 and
               e["body"].get("engine_profile")==comparison.engine_profile and
               e["body"].get("metric")==comparison.metric for e in prior)
    if seen:
        status, reward = "duplicate_evidence_no_credit", None
    elif comparison.baseline_run == comparison.candidate_run:
        status, reward = "same_run_not_comparable", None
    elif comparison.cases_matched != comparison.cases_expected:
        status, reward = "incomplete_case_coverage", None
    else:
        improvement = (comparison.candidate-comparison.baseline) * (1 if comparison.direction=="higher" else -1)
        reward = round(max(-1.,min(1., improvement/max(abs(comparison.baseline),abs(comparison.candidate),1.))),8)
        status = "eligible_scored"
    event = {"schema":"bean.rider.score.v1", "engine_profile":comparison.engine_profile,
             "strategy":comparison.strategy, "condition_id":comparison.condition_id,
             "metric":comparison.metric, "direction":comparison.direction,
             "baseline":comparison.baseline,"candidate":comparison.candidate,
             "baseline_run":comparison.baseline_run,"candidate_run":comparison.candidate_run,
             "cases_matched":comparison.cases_matched,"cases_expected":comparison.cases_expected,
             "evaluation_sha256":comparison.evaluation_sha256,
             "evidence_kind":comparison.evidence_kind,
             "evidence_verified_independently":False,
             "status":status,"reward":reward,"ecu_change_performed":False}
    head=journal.append(event)
    return {**event,"journal_digest":head}


def scoreboard(journal: EventJournal) -> dict:
    """Replay journal events to rebuild a compact scoreboard after restart."""
    tallies = {}
    for record in journal.records():
        b=record["body"]
        if b.get("schema")!="bean.rider.score.v1" or b.get("status")!="eligible_scored":
            continue
        key=(b["engine_profile"],b["strategy"],b["metric"])
        entry=tallies.setdefault(key,{"experiment":list(key),"experiments":0,
                                       "improved":0,"regressed":0,"tied":0,
                                       "total_reward":0.0})
        entry["experiments"]+=1
        entry["total_reward"]+=b["reward"]
        entry["improved" if b["reward"]>0 else "regressed" if b["reward"]<0 else "tied"]+=1
    out=[]
    for k,e in sorted(tallies.items()):
        e["mean_reward"]=round(e.pop("total_reward")/e["experiments"],8)
        out.append(e)
    return {"schema":"bean.rider.scoreboard.v1","entries":out,
            "source":"replayed_local_event_ledger", "policy_learning":"not_automatically_connected"}
