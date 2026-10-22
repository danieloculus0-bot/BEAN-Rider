# BEAN-Rider engineering notes

BEAN-Rider is a separate **offline automotive research adapter**, not an ECU controller. For cross-repo BEAN work, read the BEAN Core AI activity gatekeeper at `danieloculus0-bot/BEAN/docs/AI_GATEKEEPER.md` and check present Core/Bridge branches before claiming features.

- Keep dimensional units and model assumptions explicit; never claim unmeasured Maserati data.
- Use deterministic matched baseline and holdout comparisons; keep negative outcomes.
- Preserve measured versus synthetic provenance in every export.
- Do not imply BEAN SpongeTD/DeepQ is running when only a deterministic grid search is used.
- Extend test coverage before adding live telemetry adapters. No automated real-vehicle ECU commands or road testing in this repository's prototype stage.
- Do not put credentials, personal driving traces, GPS coordinates, or identifying VINs into public GitHub reports.

- The v0.2 CLI is a workbench, not a universal ECU reflash tool. Interface boundaries to Speeduino and rusEFI need firmware-specific testing; do not claim support beyond MSQ inspection.
- Do not silently turn user-supplied injector/engine observations into a vehicle actuation command. Record match conditions, worsening trends, and failures as evidence; maintain original logs.
- Keep user driving and trip records local. For permanent OBD installation, actual parked-battery cutoff requires hardware, not a Python printout.
