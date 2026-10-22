"""Command line entrypoint: python -m bean_rider demo --output evidence/rider."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bridge import bean_event
from .evidence import export_report, read_report
from .experiment import tune
from .telemetry import read_csv, describe


def main() -> int:
    parser = argparse.ArgumentParser(description="BEAN-Rider offline thermal bench")
    sub = parser.add_subparsers(dest="operation", required=True)
    demo = sub.add_parser("demo", help="run matched synthetic train/holdout sweeps")
    demo.add_argument("--output", type=Path, default=Path("evidence/rider"))
    demo.add_argument("--steps", type=int, default=300)
    verify = sub.add_parser("verify", help="validate compressed trial archive")
    verify.add_argument("folder", type=Path)
    imp = sub.add_parser("inspect-csv", help="read-only report of normalized recorded telemetry")
    imp.add_argument("csv", type=Path)
    args = parser.parse_args()
    if args.operation == "demo":
        report = tune(steps=args.steps)
        manifest = export_report(report, args.output)
        print(json.dumps({"report": report, "manifest": manifest,
                          "bean_bridge_event": bean_event(report)}, indent=2))
    elif args.operation == "verify":
        print(json.dumps({"verified_report": read_report(args.folder)}, indent=2))
    else:
        print(json.dumps({"telemetry": describe(read_csv(args.csv))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
