"""Matched train/holdout evaluation of BEAN-Rider thermal configurations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json

from .controller import ControllerConfig, command
from .thermal import Conditions, PlantState, advance


@dataclass(frozen=True)
class Result:
    score: float
    peak_turbine_c: float
    peak_coolant_c: float
    peak_display_c: float
    electricity_wh: float
    peak_exhaust_air_c: float
    scenario_hash: str
    steps: int

    def as_dict(self) -> dict:
        return asdict(self)


def scenario(name: str, *, steps: int = 300) -> tuple[Conditions, ...]:
    if not 1 <= steps <= 10000:
        raise ValueError("invalid steps")
    if name not in ("train", "holdout"):
        raise ValueError("unknown scenario")
    seq = []
    for i in range(steps):
        part = i / steps
        if name == "train":
            ambient = 28.0
            speed = 0.0 if part < .28 else (18.0 if part < .80 else 0.0)
            heat = 1500 if part < .28 else (7700 if part < .80 else 600)
            display_heat = 75 if part < .8 else 40
        else:
            ambient = 34.0
            speed = 11.0 if part < .2 else (4.0 if part < .75 else 0)
            heat = 3900 if part < .2 else (9000 if part < .75 else 1100)
            display_heat = 100 if part < .75 else 55
        seq.append(Conditions(ambient, speed, heat, display_heat))
    return tuple(seq)


def evaluate(config: ControllerConfig, trace: tuple[Conditions, ...]) -> Result:
    if not trace:
        raise ValueError("trace cannot be empty")
    state = PlantState()
    peak_turbine = state.turbine_c
    peak_coolant = state.turbo_coolant_c
    peak_display = state.display_coolant_c
    peak_exhaust_air = 0.0
    electric_wh = 0.0
    thermal_penalty = 0.0
    for env in trace:
        out = advance(state, command(state, env, config), env)
        state = out.state
        peak_turbine = max(peak_turbine, state.turbine_c)
        peak_coolant = max(peak_coolant, state.turbo_coolant_c)
        peak_display = max(peak_display, state.display_coolant_c)
        peak_exhaust_air = max(peak_exhaust_air, out.exhaust_air_c)
        electric_wh += out.total_electric_w / 3600
        # Scoring coefficients are illustrative, not validated temperature limits.
        thermal_penalty += (max(0, state.turbine_c - 195) ** 2 * .004
                            + max(0, state.turbo_coolant_c - 105) ** 2 * .035
                            + max(0, state.display_coolant_c - 39) ** 2 * .15)
    # Minimize. Electricity is charged, never treated as free cooling.
    loss = thermal_penalty / len(trace) + electric_wh * .15
    digest = sha256(json.dumps([asdict(x) for x in trace], sort_keys=True,
                               separators=(",", ":")).encode()).hexdigest()
    return Result(round(loss, 8), round(peak_turbine, 4),
                  round(peak_coolant, 4), round(peak_display, 4),
                  round(electric_wh, 6), round(peak_exhaust_air, 4),
                  digest, len(trace))


def tune(*, steps: int = 300) -> dict:
    """Grid-search the training trace; score the *untouched* holdout only after selection.

    This is deterministic parameter search, NOT BEAN's experimental Q-learning
    and not a claim of improved real-vehicle cooling or ECU tuning.
    """
    train = scenario("train", steps=steps)
    holdout = scenario("holdout", steps=steps)
    baseline_cfg = ControllerConfig()
    baseline_train = evaluate(baseline_cfg, train)
    baseline_holdout = evaluate(baseline_cfg, holdout)
    best_cfg, best_train = baseline_cfg, baseline_train
    candidates = 0
    for vals in product((.4, .8, 1.2), (.7, 1.0, 1.25),
                        (.5, 1.0, 1.5), (0.0, .8, 1.6)):
        cfg = ControllerConfig(*vals)
        result = evaluate(cfg, train)
        candidates += 1
        if result.score < best_train.score:
            best_cfg, best_train = cfg, result
    candidate_holdout = evaluate(best_cfg, holdout)
    return {
        "schema": "bean.rider.experiment.v1",
        "evidence_kind": "synthetic_lumped_parameter_model",
        "optimizer": "grid_search_not_q_learning",
        "steps_per_scenario": steps,
        "candidates_compared": candidates,
        "baseline_config": asdict(baseline_cfg),
        "selected_config": asdict(best_cfg),
        "baseline_train": baseline_train.as_dict(),
        "selected_train": best_train.as_dict(),
        "baseline_holdout": baseline_holdout.as_dict(),
        "selected_holdout": candidate_holdout.as_dict(),
        "holdout_delta_lower_is_better": round(candidate_holdout.score - baseline_holdout.score, 8),
        "limitations": ["synthetic calibrated-to-no-vehicle measurements",
                        "no ECU writes or physical actuators",
                        "holdout is a second synthetic drive cycle, not independent physics"],
    }
