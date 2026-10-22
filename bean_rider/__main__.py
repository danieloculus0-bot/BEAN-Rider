"""BEAN-Rider terminal workbench: offline mapping, OBD observations and evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

from .bridge import bean_event
from .evidence import export_report, read_report
from .experiment import tune
from .telemetry import read_csv, describe
from .calibration import inspect_msq, load_msq_map, load_map_json, save_map_json, compare_maps
from .obd import PythonOBDReader, FakeOBDReader
from .brain import RiderBrain
from .injectors import CylinderTrial
from .journal import EventJournal
from .profiles import REFERENCE_ECOSYSTEMS
from .power import decide
from .learning import Comparison, evaluate_comparison, scoreboard
from .engine_catalog import catalog
from .live import LiveConfig, run_dashboard
from .headunit import ProjectionManager, load_receiver_config


def _output(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="BEAN-Rider automotive intelligence workbench")
    sub = parser.add_subparsers(dest="operation", required=True)
    demo = sub.add_parser("demo", help="matched synthetic thermal optimization")
    demo.add_argument("--output", type=Path, default=Path("evidence/rider"))
    demo.add_argument("--steps", type=int, default=300)
    verify = sub.add_parser("verify", help="validate compressed thermal experiment archive")
    verify.add_argument("folder", type=Path)
    imp = sub.add_parser("inspect-csv", help="summarize imported structured telemetry")
    imp.add_argument("csv", type=Path)
    sub.add_parser("ecosystems", help="show supported third-party reference formats")
    sub.add_parser("engine-families", help="LS/LT-first engine family compatibility roadmap")
    live = sub.add_parser("live", help="local real-time dashboard using a wired OBD-II serial adapter")
    live.add_argument("--port", help="USB/serial ELM327 adapter (COM4 or /dev/ttyUSB0)")
    live.add_argument("--simulate", action="store_true", help="fabricated data without a car")
    live.add_argument("--engine", default="gm-ls", help="engine family from engine-families")
    live.add_argument("--db", type=Path, default=Path("evidence/rider-live.sqlite"))
    live.add_argument("--http-port", type=int, default=8765)
    live.add_argument("--interval", type=float, default=3.0, help="target seconds per full scanner pass")
    live.add_argument("--projection-config", type=Path,
                      help="local commands for separately installed, compatible CarPlay/Android Auto receivers")
    p = sub.add_parser("projection-status", help="standard head-unit apps and receiver readiness")
    p.add_argument("--projection-config", type=Path)
    p = sub.add_parser("inspect-msq", help="inspect local TunerStudio/Speeduino/rusEFI MSQ")
    p.add_argument("path", type=Path)
    p = sub.add_parser("extract-msq", help="extract one explicitly identified MSQ table")
    p.add_argument("path", type=Path)
    for k in ("table", "x-variable", "y-variable", "profile", "ecu-family", "x-unit", "y-unit", "value-unit"):
        p.add_argument("--"+k,required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("edit-map", help="edit one grid cell offline; keep the original")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--x", type=int, required=True, help="zero-based column index")
    p.add_argument("--y", type=int, required=True, help="zero-based row index")
    p.add_argument("--value", type=float, required=True)
    p = sub.add_parser("compare-maps", help="compare two local map JSON files")
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p = sub.add_parser("review-injector", help="evaluate evidence of injector calibration response")
    p.add_argument("trial", type=Path)
    p.add_argument("--db", type=Path, default=Path("evidence/rider-brain.sqlite"))
    p = sub.add_parser("scan-obd", help="one read-only scan, or continuous logged observations")
    p.add_argument("--port", help="ELM327 serial port, e.g. COM4, /dev/ttyUSB0")
    p.add_argument("--simulate", action="store_true", help="fabricated scan; no OBD connection")
    p.add_argument("--db", type=Path, default=Path("evidence/rider-brain.sqlite"))
    p.add_argument("--samples", type=int, default=1, help="0 continuously until interrupted")
    p.add_argument("--interval", type=float, default=5, help="seconds between scans")
    p = sub.add_parser("score-trial", help="score one independent baseline/candidate receipt")
    p.add_argument("trial", type=Path)
    p.add_argument("--db", type=Path, default=Path("evidence/rider-brain.sqlite"))
    p = sub.add_parser("scoreboard", help="replay persistent learning scoreboards")
    p.add_argument("db", type=Path)
    p = sub.add_parser("verify-journal", help="check hash chain of local evidence")
    p.add_argument("db", type=Path)
    p = sub.add_parser("power-plan", help="park/sleep advisory, no actual electrical switching")
    p.add_argument("--ignition", choices=("on","off","unknown"), default="unknown")
    p.add_argument("--voltage", type=float)
    p.add_argument("--off-seconds", type=float)
    args = parser.parse_args()
    if args.operation == "demo":
        report=tune(steps=args.steps)
        _output({"report":report, "manifest":export_report(report,args.output),
                 "bean_bridge_event":bean_event(report)})
    elif args.operation == "verify":
        _output({"verified_report":read_report(args.folder)})
    elif args.operation == "inspect-csv":
        _output({"telemetry":describe(read_csv(args.csv))})
    elif args.operation == "ecosystems":
        _output({"references":REFERENCE_ECOSYSTEMS, "execution":"offline_only"})
    elif args.operation == "engine-families":
        _output(catalog())
    elif args.operation == "projection-status":
        _output(ProjectionManager(load_receiver_config(args.projection_config)).status())
    elif args.operation == "live":
        if bool(args.port)==bool(args.simulate):
            parser.error("choose exactly one of --port or --simulate")
        config = LiveConfig(profile=args.engine, interval_s=args.interval,
                            http_port=args.http_port)
        reader = FakeOBDReader() if args.simulate else PythonOBDReader(args.port)
        run_dashboard(reader,args.db,config, projections=ProjectionManager(load_receiver_config(args.projection_config)))
    elif args.operation == "inspect-msq":
        _output(inspect_msq(args.path))
    elif args.operation == "extract-msq":
        obj = load_msq_map(args.path,table=args.table,x_variable=args.x_variable,
                           y_variable=args.y_variable,profile=args.profile,
                           ecu_family=args.ecu_family,x_unit=args.x_unit,
                           y_unit=args.y_unit,value_unit=args.value_unit)
        save_map_json(obj,args.output)
        _output({"sha256":obj.fingerprint(),"path":str(args.output),"ecu_write":False})
    elif args.operation == "edit-map":
        if args.input.resolve()==args.output.resolve():
            parser.error("do not overwrite your source calibration; use a distinct file")
        original=load_map_json(args.input)
        changed=original.edit(args.x,args.y,args.value)
        save_map_json(changed,args.output)
        _output({"output":str(args.output),"diff":compare_maps(original,changed)})
    elif args.operation == "compare-maps":
        _output(compare_maps(load_map_json(args.before),load_map_json(args.after)))
    elif args.operation == "review-injector":
        data=json.loads(args.trial.read_text(encoding="utf-8"))
        with RiderBrain(args.db) as brain:
            _output(brain.review_injector(CylinderTrial(**data)))
    elif args.operation == "score-trial":
        trial=Comparison(**json.loads(args.trial.read_text(encoding="utf-8")))
        with EventJournal(args.db) as journal:
            _output(evaluate_comparison(trial,journal))
    elif args.operation == "scoreboard":
        with EventJournal(args.db) as journal:
            _output(scoreboard(journal))
    elif args.operation == "verify-journal":
        with EventJournal(args.db) as journal:
            _output(journal.verify())
    elif args.operation == "power-plan":
        ign={"on":True,"off":False,"unknown":None}[args.ignition]
        obj=decide(ignition=ign,supply_voltage=args.voltage,seconds_since_off=args.off_seconds)
        _output({"mode":obj.mode,"awake":obj.awake,"advisory":obj.advisory,
                 "physical_power_cutoff_present":False})
    elif args.operation == "scan-obd":
        if bool(args.port)==bool(args.simulate):
            parser.error("choose exactly one of --port or --simulate")
        if args.samples<0 or args.interval<0.2:
            parser.error("nonnegative samples and interval >= 0.2 required")
        reader=FakeOBDReader() if args.simulate else PythonOBDReader(args.port)
        try:
            with RiderBrain(args.db) as brain:
                count=0
                while args.samples==0 or count<args.samples:
                    _output(brain.observe(reader).as_dict())
                    count+=1
                    if args.samples==0 or count<args.samples:
                        time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
        finally:
            reader.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
