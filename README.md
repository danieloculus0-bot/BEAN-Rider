# BEAN-Rider

**Onboard automotive tuner, OBD-II scanner, and engine-monitoring cockpit**

BEAN-Rider is an automotive diagnostics and tuning platform designed to live **inside a vehicle**, not a project for modifying one particular car. Its goal is to bring fault-code scanning, live engine telemetry, drive logging, calibration-map work, and evidence-based tuning analysis into one persistent onboard computer with a touchscreen.

The intended installation uses an **NVIDIA Jetson** as the onboard computer, a **10-inch touchscreen**, and a **wired OBD-II diagnostic interface**. The software is designed around multiple engine/ECU profiles, with GM LS/LT families first in the development queue. Vehicle-specific access depends on the actual ECU, protocol, adapter, model year, and available sensors.

**Current implementation:** live read-only OBD-II scanning and dashboard, local diagnostic history, offline calibration tools, tuning experiments, and a head-unit application shell are in the repository. Vehicle-specific ECU calibration reading/writing, real-world tuning validation, and finished in-car installation are **still development work**, not delivered capabilities.

## What BEAN-Rider is for

1. **Scan and diagnose:** Read supported OBD-II parameters and diagnostic trouble codes (DTCs), identify unavailable PIDs, and retain recurring fault observations.
2. **Monitor while driving:** Present RPM, speed, coolant and intake temperature, manifold pressure, load, throttle, and available fuel trims on a local touchscreen dashboard.
3. **Log and compare:** Keep local SQLite observation history and hash-chained evidence. Import externally logged CSV telemetry and compare matched baseline/candidate tuning experiments.
4. **Work with tunes and calibration maps:** Inspect compatible TunerStudio `.msq` files, extract explicitly identified 2D tables, edit versioned JSON grids offline, and compare revisions without overwriting source maps.
5. **Build a permanent cockpit:** Integrate the Jetson, display, diagnostic cable, ignition-aware power hardware, and later compatible phone-projection receivers in a self-contained head unit.
6. **Evolve toward ECU-specific tuning:** Add validated ECU/profile interfaces, measured feedback, controlled changes, and verification procedures as those components are implemented and tested.

This is an **engine-management diagnostic and tuning workbench**, with a path toward an integrated onboard tuner. Its thermal simulation code is one optional research tool, not the purpose of the product.

## Implemented software, at a glance

| Area | What exists in this repository | Current boundary |
| --- | --- | --- |
| Diagnostic scanner | Wired serial/USB ELM327-compatible OBD-II reader through optional `python-OBD`; supported live PIDs and DTC scans | Read-only generic OBD-II; actual PID availability varies by vehicle |
| Onboard dashboard | Local browser cockpit with live values, RPM history, error/warning states and persistent sessions | HTTP bound to loopback; not a completed automotive hardware installation |
| Logging and fault history | SQLite event journal, repeated-DTC tracking, checksum/hash-chain verification | Vehicle and sensor provenance are not automatically authenticated |
| Calibration workbench | JSON calibration grids, interpolation, single-cell edits, map diff, `.msq` inspection/extraction | Offline editing; no ECU flashing or live map writes |
| Tuning evaluation | Matched baseline/candidate scoring, injector-trial review, evidence receipts and scoreboard | Uses supplied/simulated evidence; not a closed-loop auto-tuner |
| Engine profiles | LS/LT-first catalog and extensible engine-family metadata | Entries are a development queue, not confirmed OEM ECU compatibility |
| Touchscreen/head unit | 10-inch Jetson layout target, CarPlay/Android Auto tiles, optional launch handoff | Real phone projection requires separate compatible receivers |
| Supporting engineering | Power/sleep recommendations, thermal/airflow simulator and telemetry importer | Power shutdown needs hardware; simulation is not a measured tune |

**No factory ECU write, flash, boost actuation, or autonomous fuel/ignition control is implemented in the current source.** That limitation describes development status, not the intended purpose of BEAN-Rider.

## Diagnostic evidence report (first intelligence milestone)

BEAN-Rider now has a **diagnostic case summary** command over its existing, checksum-verified SQLite journal. It reports each recorded trouble code's first/last observation, repeat count, latest-scan presence, and associated RPM/load/temperature/fuel-trim observations. It also summarizes supported PID availability and minimum/maximum/average values, retaining missing-data gaps instead of converting them to zero.

```bash
# First create observations by scanning or using the simulated reader.
python -m bean_rider scan-obd --simulate --samples 3 --db evidence/test-diagnostics.sqlite

# Analyze the recorded evidence, entirely offline.
python -m bean_rider diagnose --db evidence/test-diagnostics.sqlite
```

The resulting JSON is **evidence for investigation**, not a guessed root cause or repair verification. A DTC disappearing from one scan does not prove it was repaired; some adapters simply cannot query that DTC. No DTC clearing, flashing, actuator test, VIN harvesting, or ECU write is performed. This is the first building block for condition-matched before/after repair analysis and guided diagnostic workflows.

## Quick start

Requires **Python 3.10+**. Core offline commands use the standard library; connecting to an ELM327-compatible serial adapter uses the optional `python-OBD` dependency.

From the repository root:

```bash
python -m unittest discover -s tests -v

# Inspect configured engine-family priorities
python -m bean_rider engine-families

# Start the onboard dashboard with simulated data, no vehicle needed
python -m bean_rider live --simulate --engine gm-ls --http-port 8765
```

Open **http://127.0.0.1:8765** on the computer running BEAN-Rider. Simulation produces fabricated values and is intended for interface testing.

### Connect the OBD-II scanner

```bash
python -m pip install '.[obd]'

# Linux / Jetson example: select the actual serial device for your adapter
python -m bean_rider live --port /dev/ttyUSB0 --engine gm-ls --db evidence/rider-live.sqlite

# Windows example: one diagnostic scan with local fault/reading history
python -m bean_rider scan-obd --port COM4 --samples 1 --db evidence/rider-brain.sqlite

# Repeated scanning until interrupted
python -m bean_rider scan-obd --port COM4 --samples 0 --interval 5
```

Replace `/dev/ttyUSB0` or `COM4` with the detected port. The adapter must be an **active, compatible OBD-II interface**, not a passive connector cable. The program does not auto-detect a vehicle's ECU calibration protocol. OBD-II polling speed depends on the vehicle and interface.

### Work with tuning maps and evidence

```bash
# Inspect a compatible, locally supplied TunerStudio project
python -m bean_rider inspect-msq path/to/tune.msq

# Edit a copy of a sample map offline, retaining the source
python -m bean_rider edit-map examples/example_map.json evidence/edited_map.json --x 1 --y 0 --value 51
python -m bean_rider compare-maps examples/example_map.json evidence/edited_map.json

# Review an example injector response and local evidence history
python -m bean_rider review-injector examples/example_injector_trial.json
python -m bean_rider scoreboard evidence/rider-brain.sqlite
python -m bean_rider verify-journal evidence/rider-brain.sqlite

# Summarize externally collected telemetry
python -m bean_rider inspect-csv examples/example_telemetry.csv
```

For 2D map extraction, use `python -m bean_rider extract-msq --help`. Specify the actual table, axis variable names, units, profile and ECU family from the corresponding firmware definition; BEAN-Rider will not guess those properties. An `.msq` file is not automatically compatible with a different ECU.

### Other available commands

- `python -m bean_rider projection-status`: check cockpit app and receiver readiness.
- `python -m bean_rider ecosystems`: list external configuration-format references.
- `python -m bean_rider power-plan --ignition off --voltage 12.4 --off-seconds 150`: preview parked-power recommendations.
- `python -m bean_rider demo --output evidence/rider --steps 300`: run an **optional synthetic thermal-control experiment**.
- `python -m bean_rider verify evidence/rider`: validate the resulting evidence bundle.

All bundled examples are synthetic. No real vehicle dataset or tune is shipped.

## Onboard hardware architecture

```text
Vehicle ECU + supported sensors
        |
  OBD-II diagnostic port
        |
 Active USB/serial adapter
        |
  Jetson onboard computer
        |-- Local BEAN-Rider scanner and telemetry journal
        |-- Calibration-map / tuning analysis workbench
        |-- Local browser cockpit on 10-inch touchscreen
        |-- Optional external CarPlay / Android Auto receiver software
        |
 Automotive-rated fused power supply + ignition-aware shutdown
```

A printable prototype mount is in [`hardware/jetson_head_unit/`](hardware/jetson_head_unit/README.md), with OpenSCAD parts for a Jetson tray, screen-housing tabs and cable anchors. This is a test-fit design, not a vehicle-certified mount.

For the Jetson Orin Nano developer kit, plan for **DisplayPort video** (or a suitable converter), USB touchscreen input, USB diagnostic adapter, and correctly regulated onboard power. **Do not power the Jetson from OBD port pin 16.** A permanently installed unit needs fused automotive power conditioning, proper shutdown, and a real independent battery undervoltage disconnect. The `power-plan` function is advisory and cannot cut power itself.

Apple CarPlay and Android Auto are intended standard cockpit applications. The current code provides visible tiles and handoff to **separately installed receiver executables** via an optional local configuration, but does not implement licensed phone projection, pairing, or touch/video transport. See `bean_rider/headunit.py` for the configuration contract.

## Project organization

| Path | Responsibility |
| --- | --- |
| `bean_rider/obd.py`, `live.py` | Diagnostic queries, local telemetry dashboard |
| `bean_rider/brain.py`, `journal.py` | Observations, persistent fault history, evidence integrity |
| `bean_rider/calibration.py`, `profiles.py` | Offline calibration files and ECU-profile references |
| `bean_rider/learning.py`, `injectors.py` | Tuning comparison evidence and injector-trial review |
| `bean_rider/engine_catalog.py` | Engine-family development queue |
| `bean_rider/headunit.py`, `power.py` | Cockpit receiver handoff and parked-power policy |
| `bean_rider/telemetry.py`, `experiment.py`, `thermal.py` | CSV analysis and optional simulation |
| `hardware/jetson_head_unit/` | Parametric prototype mounting kit |
| `tests/` | Offline automated unit tests |

## Development priorities

1. Test the wired diagnostic path on identified real vehicles and adapters, recording supported/unsupported PIDs and reliable sampling performance.
2. Make the touch-first cockpit practical for an always-installed device: readable gauges, startup/reconnect behavior, fault-history review, and robust storage.
3. Add ECU-specific diagnostic and calibration adapters backed by explicit protocol definitions, verification, and real instrumentation.
4. Connect logged operating conditions to versioned calibration decisions, matched comparisons, and reversible review procedures.
5. Validate power, thermal conditions, physical mounting, and end-to-end behavior before treating the head unit as ready for vehicle deployment.

**Scope:** This repository is the BEAN-Rider automotive platform. It is not tied to a specific car, forced-induction conversion, or one-off fabrication exercise. Future tuning capabilities must be implemented and validated rather than assumed from generic OBD-II access.

Keep VINs, identifying trip logs, and private vehicle records local. The project is public but currently grants no general redistribution license.
