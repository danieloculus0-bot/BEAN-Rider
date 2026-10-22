"""Always-present BEAN-Rider 10-inch head-unit apps and local receiver handoff.

Android Auto and CarPlay tiles are standard; their licensed phone-projection
receivers are NOT implemented here. For an installed compatible receiver, a
local operator may configure a direct, shell-free executable launch. This
module never emulates CarPlay/Android Auto or claims certification.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Callable

APPS = (
    ("bean", "BEAN Engine", "built_in"),
    ("carplay", "Apple CarPlay", "receiver_required"),
    ("android_auto", "Android Auto", "receiver_required"),
)
RECEIVERS = frozenset({"carplay", "android_auto"})


@dataclass(frozen=True)
class ReceiverCommand:
    executable: str
    args: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.executable, str) or not self.executable or
                not Path(self.executable).is_absolute() or '\x00' in self.executable):
            raise ValueError("receiver executable must be an absolute local path")
        if (not isinstance(self.args, tuple) or len(self.args) > 24 or
                not all(isinstance(x, str) and '\x00' not in x and len(x) <= 512
                        for x in self.args)):
            raise ValueError("receiver argument list invalid")


def load_receiver_config(path: str | Path | None) -> dict[str, ReceiverCommand]:
    """Optional local receiver install details, not a feature toggle."""
    if path is None:
        return {}
    config_path = Path(path)
    if config_path.stat().st_size > 16_384:
        raise ValueError("oversize receiver config")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "bean.rider.receiver.config.v1":
        raise ValueError("unknown receiver config")
    if set(data) != {"schema", "receivers"} or not isinstance(data["receivers"], dict):
        raise ValueError("receiver config shape invalid")
    result = {}
    for name, item in data["receivers"].items():
        if name not in RECEIVERS or not isinstance(item, dict) or set(item) != {"executable", "args"}:
            raise ValueError("unknown receiver or command fields")
        if not isinstance(item["args"], list):
            raise ValueError("receiver args must be a list")
        result[name] = ReceiverCommand(item["executable"], tuple(item["args"]))
    return result


class ProjectionManager:
    """Status and explicit local-process handoff to a separately installed receiver.

    The manager can know whether a process started, NOT whether a phone paired,
    whether USB/Wi-Fi transport is licensed, or whether video is working.
    """
    def __init__(self, commands: dict[str, ReceiverCommand] | None = None,
                 *, spawn: Callable[..., object] = subprocess.Popen):
        commands = {} if commands is None else dict(commands)
        if not set(commands).issubset(RECEIVERS) or not all(
                isinstance(command, ReceiverCommand) for command in commands.values()):
            raise ValueError("unsupported receiver")
        self.commands = commands
        self.spawn = spawn
        self.running: dict[str, object] = {}

    def status(self) -> dict:
        apps = []
        for key, title, kind in APPS:
            process = self.running.get(key)
            running = process is not None and process.poll() is None
            config = self.commands.get(key)
            executable_ready = bool(config and Path(config.executable).is_file() and
                                    os.access(config.executable, os.X_OK))
            apps.append({"id": key, "title": title, "standard": True,
                         "built_in": kind == "built_in", "receiver_configured": bool(config),
                         "receiver_executable_present": executable_ready,
                         "receiver_process_running": running,
                         "projection_operational_verified": False,
                         "status": "built_in" if key == "bean" else
                           "receiver_running_unverified" if running else
                           "receiver_ready_unverified" if executable_ready else
                           "receiver_not_installed"})
        return {"schema": "bean.rider.headunit.v1", "display": "10-inch touchscreen target",
                "apps": apps, "car_audio_integration": "future_adapter",
                "projection": "requires_compatible_external_receivers"}

    def launch(self, app: str) -> dict:
        if app not in RECEIVERS:
            raise ValueError("unsupported projection receiver")
        cfg = self.commands.get(app)
        if cfg is None:
            raise RuntimeError("receiver not installed: connect compatible CarPlay/Android Auto receiver hardware")
        if not Path(cfg.executable).is_file() or not os.access(cfg.executable, os.X_OK):
            raise RuntimeError("configured receiver executable is unavailable")
        running = self.running.get(app)
        if running is not None and running.poll() is None:
            return {"app": app, "launch": "already_running", "projection_verified": False}
        # Direct argv; no shell, URL scheme, ECU command or user-provided HTTP arguments.
        self.running[app] = self.spawn([cfg.executable, *cfg.args], shell=False,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        return {"app": app, "launch": "receiver_process_started", "projection_verified": False}
