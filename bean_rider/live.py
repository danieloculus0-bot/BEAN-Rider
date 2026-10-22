"""USB/serial OBD-II live dashboard and persistent observation runner.

Read-only generic SAE data via the existing PythonOBDReader. No ECU tuning,
actuator commands, trip locations or public network service. Server defaults
strictly to loopback and only exposes the current in-process observations.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import threading
import time
from typing import Callable

from .brain import RiderBrain
from .engine_catalog import get_family
from .headunit import ProjectionManager
from .obd import Reader


@dataclass(frozen=True)
class LiveConfig:
    profile: str = "gm-ls"
    interval_s: float = 3.0
    history_points: int = 90
    host: str = "127.0.0.1"
    http_port: int = 8765

    def __post_init__(self):
        get_family(self.profile)
        if (not isinstance(self.interval_s, (int, float)) or
                not math.isfinite(self.interval_s) or not 0.5 <= self.interval_s <= 60):
            raise ValueError("invalid sampling interval")
        if type(self.history_points) is not int or not 5 <= self.history_points <= 1000:
            raise ValueError("invalid history length")
        if self.host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("dashboard requires loopback interface")
        if type(self.http_port) is not int or not 0 <= self.http_port <= 65535:
            raise ValueError("invalid HTTP port")


class LiveState:
    """Thread-safe bounded session observations and dashboard snapshot."""
    def __init__(self, config: LiveConfig):
        self.config = config
        self._lock = threading.Lock()
        self._history = deque(maxlen=config.history_points)
        self._latest = None
        self._warnings = []
        self._error = None
        self._samples = 0
        self._created_at = time.time()

    def record(self, report: dict):
        if report.get("schema") != "bean.rider.brain.v1":
            raise ValueError("unexpected brain observation")
        item = report["observation"]
        if item.get("schema") != "bean.rider.obd.scan.v1":
            raise ValueError("unknown scan schema")
        with self._lock:
            self._samples += 1
            self._latest = item
            self._warnings = report["warnings"]
            self._error = None
            self._history.append({"time": item["timestamp_utc"],
                                  "rpm": item["values"].get("rpm"),
                                  "coolant_c": item["values"].get("coolant_c"),
                                  "speed_kph": item["values"].get("speed_kph")})

    def error(self, message: str):
        with self._lock:
            self._error = message[:200]

    def snapshot(self) -> dict:
        with self._lock:
            return {"schema": "bean.rider.live.v1", "engine": get_family(self.config.profile).payload(),
                    "status": "error" if self._error else "receiving" if self._latest else "waiting",
                    "samples": self._samples, "sample_interval_target_s": self.config.interval_s,
                    "uptime_s": round(time.time() - self._created_at, 2),
                    "latest": self._latest, "warnings": list(self._warnings),
                    "history": list(self._history), "error": self._error,
                    "connection": "user_supplied_wired_serial_obd2_or_simulated",
                    "ecu_writes": 0, "source_claim": "reader_origin_not_hardware_authenticated"}


def collect_one(state: LiveState, brain: RiderBrain, reader: Reader) -> dict:
    result = brain.observe(reader).as_dict()
    state.record(result)
    return state.snapshot()


# This UI consumes the JSON API but does not connect to the vehicle itself.
DASHBOARD_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BEAN Rider | Engine Brain</title>
<style>
:root{color-scheme:dark;font:16px system-ui;background:#101712;color:#eff8ec}
*{box-sizing:border-box}body{margin:0 auto;padding:26px;max-width:1120px}
header{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}
h1{font-size:2rem;letter-spacing:-.05em;margin:0}h1 b{color:#a9f65c}
small,.muted{color:#a8b4ac}.pill{border:1px solid #4d6c48;border-radius:30px;padding:7px 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(172px,1fr));gap:12px;margin:24px 0}
.card,.panel{border:1px solid #334235;background:#19221a;border-radius:15px;padding:17px}
.card .name{font-size:.8rem;color:#a8b4ac}.card .value{font-size:2.1rem;font-weight:700;margin:5px 0}
.card .unit{font-size:.8rem;color:#b6c9b5}.panel{margin-top:12px}h2{margin:0 0 10px;font-size:1rem}
canvas{width:100%;height:210px;display:block}.warning{padding:9px 0;border-top:1px solid #344638}
.apps{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0}
.app{min-height:68px;flex:1 1 155px;text-align:left;touch-action:manipulation;cursor:pointer;color:#eff8ec;
 background:#223026;border:2px solid #4a5a43;border-radius:14px;font-weight:750;font-size:1.04rem;padding:13px}
.app:focus-visible{outline:3px solid #b7ff61;outline-offset:2px}
.app[disabled]{opacity:.7;cursor:default}.app strong{color:#b7ff61}
#projection-panel{padding:12px 16px;background:#1b2c1d;border:1px solid #456544;border-radius:12px;min-height:55px}
#projection-panel[hidden]{display:none}
@media(max-width:760px){body{padding:13px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.card .value{font-size:1.7rem}}
@media(orientation:landscape) and (max-height:650px){body{padding:8px 16px}.apps{margin:8px 0}.app{min-height:60px} .grid{margin:10px 0}}

</style></head><body>
<header><div><h1>BEAN <b>RIDER</b></h1><small id="family">Wired OBD-II engine brain</small></div><span id="state" class="pill">Connecting…</span></header>
<nav class="apps" aria-label="Standard BEAN-Rider cockpit applications">
<button type="button" class="app" id="app-bean" aria-current="page" onclick="showBean()">🧠 <strong>BEAN</strong> Engine</button>
<button type="button" class="app" id="app-carplay" onclick="openProjection('carplay')">Apple CarPlay</button>
<button type="button" class="app" id="app-android_auto" onclick="openProjection('android_auto')">Android Auto</button>
</nav>
<div id="projection-panel" role="status" aria-live="polite" hidden></div>
<main id="engine-main"><div id="readings" class="grid"></div>
<section class="panel"><h2>Live engine speed</h2><canvas id="trend"></canvas><small>Recent RPM observations · readings depend on ECU and adapter availability</small></section>
<section class="panel"><h2>Diagnostics and memory</h2><div id="warnings" class="muted">Waiting for the scanner.</div></section></main>
<footer><p class="muted" id="footer">Generic diagnostics only · No ECU writes</p></footer>
<script>
async function openProjection(kind){
  const panel=document.getElementById('projection-panel');panel.hidden=false;
  const app=projectionApps.find(item=>item.id===kind);
  document.getElementById('engine-main').hidden=false;
  if(!app||!app.receiver_executable_present){panel.textContent=(kind==='carplay'?'Apple CarPlay':'Android Auto')+' is standard in BEAN-Rider. Projection requires a separately installed compatible receiver; no stream is running.';return;}
  panel.textContent='Starting compatible receiver process…';
  try{const r=await fetch('/api/projection/'+kind+'/launch',{method:'POST',headers:{'X-BEAN-Cockpit':'receiver-launch','Content-Type':'application/json'}});
  const j=await r.json();panel.textContent=r.ok?'Receiver process started; confirm pairing and actual projection on the receiver.':j.error;
  }catch(e){panel.textContent='Receiver launch unavailable';}
}
function showBean(){document.getElementById('engine-main').hidden=false;document.getElementById('projection-panel').hidden=true;}
let projectionApps=[];
async function refreshProjection(){try{let r=await fetch('/api/projection',{cache:'no-store'});let d=await r.json();projectionApps=d.apps||[];
  for(const a of projectionApps){const btn=document.getElementById('app-'+a.id);if(btn&&a.id!=='bean')btn.title=a.status.replaceAll('_',' ');}}
  catch(e){} }
refreshProjection();setInterval(refreshProjection,5000);
const fields=[['rpm','RPM','rev/min'],['speed_kph','Speed','km/h'],['coolant_c','Coolant','°C'],['intake_c','Intake','°C'],['manifold_kpa','MAP','kPa'],['engine_load_pct','Load','%'],['short_fuel_trim_bank1_pct','STFT B1','%'],['long_fuel_trim_bank1_pct','LTFT B1','%']];
const root=document.getElementById('readings');for(const [id,label,unit] of fields){const el=document.createElement('div');el.className='card';el.innerHTML='<div class="name"></div><div class="value">--</div><div class="unit"></div>';el.querySelector('.name').textContent=label;el.querySelector('.unit').textContent=unit;el.id='reading-'+id;root.appendChild(el);}
function draw(data){const c=document.getElementById('trend');const w=c.clientWidth,h=210,dpr=devicePixelRatio||1;c.width=w*dpr;c.height=h*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,w,h);x.strokeStyle='#35503c';for(let j=0;j<4;j++){x.beginPath();x.moveTo(0,j*h/3);x.lineTo(w,j*h/3);x.stroke()}const vals=data.history.map(z=>z.rpm);const max=Math.max(1000,...vals.filter(v=>typeof v==='number'));x.strokeStyle='#b7ff61';x.lineWidth=2;x.beginPath();let started=false;vals.forEach((v,i)=>{if(typeof v!=='number'){started=false;return}const xx=(i/Math.max(1,vals.length-1))*w,yy=h-8-(v/max)*(h-20);if(!started)x.moveTo(xx,yy);else x.lineTo(xx,yy);started=true});x.stroke();}
async function update(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();document.getElementById('family').textContent=d.engine.manufacturer+' · '+d.engine.family;document.getElementById('state').textContent=d.status+' · '+d.samples+' samples';const p=d.latest?.values||{};fields.forEach(([id])=>document.querySelector('#reading-'+id+' .value').textContent=p[id]==null?'--':p[id]);const box=document.getElementById('warnings');box.textContent='';if(d.error)box.textContent='Connection: '+d.error;else if(!d.warnings.length)box.textContent='No reported DTCs in latest scan';else d.warnings.forEach(w=>{const div=document.createElement('div');div.className='warning';div.textContent=w.code+' · '+w.priority+' · seen '+w.repeat_observations+' times';box.appendChild(div)});document.getElementById('footer').textContent='Last scan: '+(d.latest?.timestamp_utc||'none')+' · ECU writes: 0 · Sample interval target: '+d.sample_interval_target_s+' s';draw(d);}catch(e){document.getElementById('state').textContent='Dashboard disconnected';}}
update();setInterval(update,1000);
</script></body></html>'''


def make_handler(state: LiveState, projections: ProjectionManager | None = None):
    projections = projections if projections is not None else ProjectionManager()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                content = json.dumps(state.snapshot(), sort_keys=True, allow_nan=False).encode('utf-8')
                content_type = 'application/json; charset=utf-8'
            elif self.path == "/api/projection":
                content = json.dumps(projections.status(), sort_keys=True).encode('utf-8')
                content_type = 'application/json; charset=utf-8'
            elif self.path in ("/", "/index.html"):
                content = DASHBOARD_HTML.encode('utf-8')
                content_type = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            prefix = "/api/projection/"
            if not self.path.startswith(prefix) or not self.path.endswith("/launch"):
                self.send_error(404)
                return
            kind = self.path[len(prefix):-len("/launch")]
            # A malicious external webpage must not be able to POST a launch to
            # the loopback cockpit. Cross-origin JS cannot set this custom header.
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            valid_hosts = {f"127.0.0.1:{self.server.server_port}",
                           f"localhost:{self.server.server_port}"}
            if (host not in valid_hosts or
                (origin is not None and origin not in {"http://"+x for x in valid_hosts}) or
                self.headers.get("X-BEAN-Cockpit") != "receiver-launch"):
                self.send_error(403)
                return
            try:
                result = projections.launch(kind)
                code = 200
            except (RuntimeError, ValueError, OSError) as exc:
                result = {"error": str(exc), "projection_verified": False}
                code = 409
            content = json.dumps(result).encode('utf-8')
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args):
            return
    return Handler


def run_dashboard(reader: Reader, db_path, config: LiveConfig,
                  *, reporter: Callable[[dict], None] | None = None,
                  projections: ProjectionManager | None = None):
    """Run until Ctrl+C. Serial device stays open; all observations stay local."""
    state = LiveState(config)
    server = ThreadingHTTPServer((config.host, config.http_port), make_handler(state, projections))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"BEAN-Rider dashboard: http://{config.host}:{server.server_port}", flush=True)
    try:
        with RiderBrain(db_path) as brain:
            while True:
                started = time.monotonic()
                try:
                    report = collect_one(state, brain, reader)
                    if reporter is not None:
                        reporter(report)
                except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                    state.error(type(exc).__name__ + ': ' + str(exc))
                # Serial poll latency can exceed the target cadence.
                delay = max(0.0, config.interval_s-(time.monotonic()-started))
                if delay:
                    time.sleep(delay)
    except KeyboardInterrupt:
        return state.snapshot()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        reader.close()
