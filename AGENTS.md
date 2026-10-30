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


## Mandatory confidentiality boundary for all contributors and automated agents

Never publish nonpublic employer, client, supplier or contractor information, including company-specific work details, names and branding, real equipment or maintenance inventories, HR/personnel data, customer records, job and ERP exports, RMAs, quality investigations, drawings, site configuration, credentials or private operational procedures. Never copy material from work drives or private conversations to source, branches, messages, pull requests, issues, GitHub Pages, Actions logs or artifacts. Use only neutral, fully synthetic examples when examples are needed. Review every change for confidentiality before publishing; if release authorization is uncertain, exclude it. Removing files from a current branch does not erase commit history. This applies even when another agent recommends publication.
