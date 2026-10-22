# BEAN-Rider

**Automotive intelligence laboratory | v0.4: Jetson cockpit and wired OBD-II**

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


## v0.4 Jetson 10-inch standard cockpit and phone projection contract

**Apple CarPlay and Android Auto are standard built-in cockpit applications** (always visible, not optional feature unlocks) alongside the engine dashboard. BEAN-Rider supplies the fullscreen touchscreen navigation, receiver readiness API, and local executable handoff for either service. **The actual phone projection video, audio transport, pairing protocol, licensing, and touch input forwarding require a separate compatible receiver/software-hardware stack that is NOT supplied or emulated by this repository.** An unconfigured receiver is prominently shown as unavailable, not falsely as working. Stereo integration is a later adapter; the Jetson itself is the cockpit computer.

An NVIDIA Jetson Orin Nano dev kit can use its USB Type-A host port for a **wired ELM327-compatible 16-pin OBD-II-to-USB interface**. The factory screen connection on that dev kit is **DisplayPort** (use DisplayPort-to-HDMI for an HDMI display); a typical touch monitor requires a second USB connection for touchscreen input. Select a Linux-compatible serial interface and confirm the actual `/dev/ttyUSB*` or `/dev/ttyACM*` port. The app never assumes hardware is installed merely because a menu item exists.

```bash
python -m bean_rider projection-status
python -m bean_rider live --simulate --engine gm-ls
# On an installed Jetson with a compatible OBD cable:
python -m bean_rider live --port /dev/ttyUSB0 --engine gm-ls
# Open http://127.0.0.1:8765 in kiosk/fullscreen browser on the 10-inch screen.
```

To connect **already-installed compatible receiver executables**, a local administrator may write an untracked configuration file (e.g. `evidence/receiver.json`):

```json
{
  "schema": "bean.rider.receiver.config.v1",
  "receivers": {
    "carplay": {"executable": "/absolute/path/to/compatible/carplay-receiver", "args": []},
    "android_auto": {"executable": "/absolute/path/to/compatible/android-auto-receiver", "args": []}
  }
}
```

Then start `python -m bean_rider live --simulate --projection-config evidence/receiver.json`. Pressing the standard app tile directly launches its configured receiver as a separate local process without a shell. Startup does **not** establish actual phone pairing, projection compatibility, MFi approval, or verified operation. No cloud/screen broadcasting endpoints are added. The local app-launch HTTP route checks the cockpit request origin and a custom header. Keep private receiver configuration and vehicle logs out of GitHub.

Official references: [NVIDIA Orin Nano developer-kit port layout](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/hardware_layout.html), [Python-OBD and ELM327](https://python-obd.readthedocs.io/en/latest/), and [Apple MFi/CarPlay](https://mfi.apple.com/en/how-it-works).

## v0.3 Wired OBD-II live dashboard and engine priority catalog

This version adds an **actual local HTTP dashboard** fed by the existing Python-OBD **USB/serial** reader. Live values, DTCs, bounded RPM history and durable local SQLite observation history are displayed in a mobile-friendly page. It does not require Bluetooth, cloud services, a phone app or external network access.

```bash
python -m unittest discover -s tests -v
python -m bean_rider engine-families
python -m bean_rider live --simulate --engine gm-ls --http-port 8765
# Open http://127.0.0.1:8765 in a browser (synthetic values)

python -m pip install '.[obd]'
python -m bean_rider live --port COM4 --engine gm-ls --db evidence/ls-logger.sqlite
# Linux: replace COM4 with /dev/ttyUSB0 or the actual adapter path
```

The engine catalog prioritizes GM LS and LT, followed by Maserati F136, VW, Mercedes, Audi, BMW and Ferrari, with **explicitly unimplemented factory ECU mapping** for each. Engine identification is selected by the user, not inferred from an unverified OBD response. Generic OBD-II provides a **vehicle-specific subset** of emission diagnostics, RPM, speed, temperature, pressure, throttle and fuel trims. It does **not** provide unrestricted ECU fuel/ignition table access, accurate knock data, injector flow, or all manufacturer sensors. Physical engine optimization/auto-tuning remains unimplemented; the earlier thermal simulator and offline map editor are separate building blocks. The existing scanner may take longer than the requested interval because a slow adapter requires serial command round-trips.

The dashboard listens on loopback (`127.0.0.1`) rather than exposing vehicle telemetry to the LAN. Running the program and an OBD-II cable on an onboard computer is not itself a validated vehicle installation. A truly permanent plugged-in unit needs ignition-aware power control and an independent electrical low-voltage cutoff, because diagnostic port pin 16 may remain powered when the car is parked. Do not leave a permanently awake laptop or USB adapter draining the battery. The live logger cannot flash, tune, or actuate the ECU.

## v0.2 Engine brain, scanners, maps and learning (October 2026)

The **platform is engine-agnostic by explicit engine and ECU profiles**, not universal ECU access. This release adds actual software modules and independent tests:

- `bean_rider.obd`: **read-only** ELM327/OBD-II polling (optional `python-OBD` package), supported generic live PIDs, fault-code scanning, optional persistent observations. The standard OBD-II interface cannot read or write arbitrary ignition/injection ECU maps or single-cylinder trims. Missing PIDs remain explicitly unknown.
- `bean_rider.brain` + `bean_rider.journal`: continuous operation with SQLite-backed, hash-chained append-only observations, repeat-fault memory, restart/replay verification and gzip export. The ledger is private/local by default.
- `bean_rider.calibration`: original versioned JSON calibration grid, dimensional checks, interpolation, explicit offline cell edits, diff, and read-only XML `.msq` inspection/extraction for compatible TunerStudio projects. ECU-specific axis names, units and orientation must be supplied rather than guessed. **No flashing.**
- `bean_rider.profiles`: basic engine-agnostic profiles and versioned references to Speeduino and rusEFI configuration ecosystems. Compatibility does **not** imply copying community tunes or using them on unrelated engines.
- `bean_rider.injectors`: evidence-based cylinder-specific **simulated compensation review** with failure/worsening detection and more frequent warnings. Physical injector leakage is not assumed fixable by tuning, and generic OBD cannot identify individual injector flow. No live injector compensation or control is installed.
- `bean_rider.learning`: baseline/candidate matched comparison, signed outcome rewards, durable ledger scoreboard, duplicate receipt detection, and negative outcome retention. It is *not* a connected BEAN SpongeTD learner or actual vehicle auto-tuning yet.
- `bean_rider.power`: park/sleep **advisory policy**; a compatible power controller must implement real low-voltage cutoff and sleep behavior. A permanently attached OBD dongle may have continuous battery power, even when the ignition is off.

### CLI workbench

```bash
python -m unittest discover -s tests -v
python -m bean_rider scan-obd --simulate --db evidence/rider-brain.sqlite
# Optional serial ELM327 OBD-II hardware (pip install python-OBD):
python -m bean_rider scan-obd --port COM4 --db evidence/rider-brain.sqlite --samples 0 --interval 5
python -m bean_rider verify-journal evidence/rider-brain.sqlite
python -m bean_rider inspect-msq path/to/your_tune.msq
python -m bean_rider edit-map examples/example_map.json evidence/edited_map.json --x 1 --y 0 --value 51
python -m bean_rider compare-maps examples/example_map.json evidence/edited_map.json
python -m bean_rider review-injector examples/example_injector_trial.json --db evidence/rider-brain.sqlite
python -m bean_rider scoreboard evidence/rider-brain.sqlite
python -m bean_rider power-plan --ignition off --voltage 12.4 --off-seconds 150
python -m bean_rider ecosystems
```

For a complete MSQ 2D map extraction use `extract-msq` with explicit `--table`,
`--x-variable`, `--y-variable`, `--profile`, `--ecu-family`, `--x-unit`,
`--y-unit`, `--value-unit`, and `--output`. Check the official firmware-specific
`.ini` to identify table names, units and row ordering.

### Open-source configuration references

- [Speeduino reference .ini](https://github.com/speeduino/speeduino/blob/master/reference/speeduino.ini) and [Speeduino Tunes](https://github.com/speeduino/Tunes). Speeduino's tune library identifies a **CC BY-NC 4.0** license; no sample tune is vendored here. Firmware signatures and engine/hardware compatibility matter.
- [rusEFI firmware and console](https://github.com/rusefi/rusefi), [public tune/log catalog](https://wiki.rusefi.com/Online/). Its core has GPLv3 and additional conditions; no code is copied or linked into this repository.
- Users must verify individual third-party permissions, compatibility, emissions requirements and licensing before using or modifying ECU firmware or tunes.

### Permanent installation concept

Connect a certified/appropriate OBD-II adapter, local computing unit, and **independent switched/low-voltage-disconnect power management**. Use ignition sensing, onboard storage, reconnect-after-start, sensible polling frequencies and a known wake/sleep strategy. The software's `power-plan` command does not physically switch power. Bluetooth dongles and pin-16-powered accessories can drain the parked battery.

Do not upload private VINs, complete GPS/location traces, owner details or unredacted trip logs to the public repo. No automatic public telemetry exports exist.

### Implementation boundaries

This version **does not** reflash factory ECUs, set boost/fuel/ignition tables in a running engine, remotely command actuators, confirm injector mechanical conditions, or claim universal support for every OEM ECU. Live test data, real injector-trim sensors, hardware clocks, an installer, GUI, and BEAN Core reward-loop ingestion remain future work. The first on-vehicle stage is a read-only logger; calibration changes require a separately validated ECU-specific adapter and proper instrumentation.

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
