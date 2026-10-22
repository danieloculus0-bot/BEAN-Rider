# BEAN-Rider

**Automotive intelligence laboratory | Phase 0: offline, instrument-first research**

BEAN-Rider is a standalone experimental companion to [BEAN Core](https://github.com/danieloculus0-bot/BEAN), initially motivated by a custom 2012 Maserati GranTurismo 4.7L twin-turbo concept. It is not an ECU firmware project, a validated vehicle tune, or a live automotive controller.

The hardware concept is unusual on purpose: **two top-mounted intake fans, complementary trailing exhaust fans, tapered ducts with low-side hot-air discharge, independent liquid circuits, and twin Peltier modules**. The goal is to characterize pressure, heat rejection, coolant loads and control strategies before fabricating the hardware.

## Built in v0.1.0

- A deterministic **three-node lumped thermal model** (turbine, turbo coolant, illuminated display coolant) with explicit heat conservation, pressure-based push-pull fan airflow, radiator heat transfer, Peltier cooling plus electrical waste heat, and exhaust-air rise estimates.
- Four independently commanded *virtual* actuator outputs: leading fans, trailing fans, circulation pump and Peltier duty.
- An offline **81-candidate parameter search** using a training scenario and a different, untouched synthetic holdout drive cycle. Baseline metrics, selected metrics, energy penalty, and regressions are all retained.
- A **compressed, checksum-verified evidence bundle**, with deterministic gzip formatting and round-trip verification. The bundle is a transport artifact, **not** a replacement for BEAN Core's SQLite Journal.
- A structured **BEAN bridge event** with exact report digest and matched-scenario identification. Integration hooks are a data contract; BEAN Core does **not** ingest them automatically yet.
- **Read-only CSV telemetry ingestion** with explicit units, numeric validation and summary statistics. No ECU writes, CAN actuation or diagnostic assertions.
- Offline unit tests and Windows/Linux CI checks.

### Run it

Requires Python 3.10+ and **only the standard library** at runtime. From repository root:

```bash
python -m unittest discover -s tests -v
python -m bean_rider demo --output evidence/rider --steps 300
python -m bean_rider verify evidence/rider
python -m bean_rider inspect-csv examples/example_telemetry.csv
```

The demo emits a JSON report and `bean_bridge_event`. The compressed report and manifest are created at the specified output path, which is gitignored by default. `inspect-csv` only parses caller-provided records. The bundled example is **fabricated sample data**.

## Model boundaries and engineering notes

These are **illustrative lumped parameters**, not measured values or validated thresholds from Maserati, Ferrari, LOJ, Garrett or Peltier manufacturers. The thermal model does not include turbo oil coking, exhaust gas turbine efficiency, vehicle-underhood pressure maps, radiator fan curves, actual pump curves, cavitation, control latency, thermal cycling damage, injector behavior, fuel maps, boost actuation or knock consequences. The exhaust-temperature estimate is a simplified bulk energy calculation, not a prediction of component skin temperatures.

A push-pull arrangement increases **available pressure**, but pressure/flow gains depend on actual fan curves and system resistance. The fans do not remove resistance. Peltier hot-side rejection equals extracted cold-side heat **plus electrical input**; active cooling cannot avoid paying that heat and electricity bill. Conventional radiators will generally dominate bulk heat rejection. Ordinary PC cooling hardline is **not** assumed suitable for turbo coolant temperatures; isolating an aesthetic loop doesn't make high-temp components safe.

The current optimizer is **deterministic grid search**, not BEAN's experimental Q-learning. It changes virtual duty response parameters only. A training improvement may fail to transfer to holdout; the separate holdout result is reported even when negative. Neither result establishes real-vehicle efficiency gains.

## Telemetry input schema

A CSV must have the following columns with these exact units:

| Field | Units | Meaning |
|---|---|---|
| `time_s` | s | Monotonic sample time |
| `rpm` | rev/min | Engine speed |
| `speed_kph` | km/h | Vehicle speed |
| `coolant_c` | °C | Reported engine coolant temperature |
| `oil_c` | °C | Reported oil temperature |
| `intake_c` | °C | Reported intake air temperature |
| `manifold_kpa` | kPa absolute | Manifold absolute pressure |
| `lambda_measured` | lambda | Reported equivalence relative to stoichiometric |
| `knock_retard_deg` | degrees | Reported ignition retard associated with knock |

Column meaning must be verified against the source logger; merely naming a column doesn't authenticate a sensor. This phase intentionally omits VIN, GPS, and personal location.

## BEAN integration path

BEAN Core currently has a [hash-chained SQLite Journal](https://github.com/danieloculus0-bot/BEAN/blob/main/bean/optimization/autodev.py) and separate experimental [SpongeTD](https://github.com/danieloculus0-bot/BEAN/blob/experiment/bean-sponge-core-20261011/bean/optimization/sponge_td.py) and [scoreboard/reward](https://github.com/danieloculus0-bot/BEAN/blob/experiment/bean-visible-scoreboard-reward-20261020/bean/optimization/scoreboard_context.py) work. Do not conflate the branches.

1. Use `bean_rider.bridge.bean_event(report)` to produce a versioned observation with report hash, evidence type and matched baseline/holdout comparison.
2. A future host-owned BEAN Bridge worker can verify the compressed artifact and append its reference to Core's **existing Journal**. This adapter is not yet live.
3. A separately tested worker may expose these matched simulation observations to SpongeTD for offline policy experiments, with explicit verified reward receipts and frozen holdout data. It must not call the current grid search "Q-learning".
4. Later, introduce measured radiator/fan/pump curves, an instrumented dyno, real thermal sensor data and a read-only OBD/CAN collector with documented controller interface. Keep any safety-critical ECU actuation outside learned closed-loop recommendations unless separately engineered and validated.

**Known status:** no BEAN agent is controlling vehicle hardware. No Maserati calibration, installation or live tune has been performed. Read the CI run for the exact commit before stating verification status.

## Development

This repository currently has no general redistribution license. Source visibility alone does not confer rights to reuse. Contributions should preserve evidence and label the scope of claims.
