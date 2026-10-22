# BEAN-Rider engineering notes

BEAN-Rider is a separate **offline automotive research adapter**, not an ECU controller. For cross-repo BEAN work, read the BEAN Core AI activity gatekeeper at `danieloculus0-bot/BEAN/docs/AI_GATEKEEPER.md` and check present Core/Bridge branches before claiming features.

- Keep dimensional units and model assumptions explicit; never claim unmeasured Maserati data.
- Use deterministic matched baseline and holdout comparisons; keep negative outcomes.
- Preserve measured versus synthetic provenance in every export.
- Do not imply BEAN SpongeTD/DeepQ is running when only a deterministic grid search is used.
- Extend test coverage before adding live telemetry adapters. No automated real-vehicle ECU commands or road testing in this repository's prototype stage.
- Do not put credentials, personal driving traces, GPS coordinates, or identifying VINs into public GitHub reports.
