from __future__ import annotations

import socket
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

import psutil

from .config import settings
from .protocols import get_protocols_snapshot
from .models import DiskUsage, GpuDevice, NetIO, SystemSample


@dataclass
class MetricsStore:
    history: Deque[SystemSample]

    def maxlen(self) -> int:
        return max(1, int(settings.history_seconds / max(settings.sample_interval_seconds, 0.1)))


_store: Optional[MetricsStore] = None


def get_store() -> MetricsStore:
    global _store
    if _store is None:
        _store = MetricsStore(history=deque(maxlen=1))
        _store.history = deque(maxlen=_store.maxlen())
    return _store


def _safe_getloadavg() -> tuple[Optional[float], Optional[float], Optional[float]]:
    try:
        l1, l5, l15 = psutil.getloadavg()  # type: ignore[attr-defined]
        return float(l1), float(l5), float(l15)
    except Exception:
        try:
            l1, l5, l15 = socket.getloadavg()
            return float(l1), float(l5), float(l15)
        except Exception:
            return None, None, None


def _disk_usages() -> list[DiskUsage]:
    disks: list[DiskUsage] = []
    for part in psutil.disk_partitions(all=False):
        # Skip pseudo/permission denied mounts
        if part.fstype == "":
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        disks.append(
            DiskUsage(
                mount=part.mountpoint,
                total_bytes=int(usage.total),
                used_bytes=int(usage.used),
                free_bytes=int(usage.free),
                percent=float(usage.percent),
            )
        )
    # Prefer stable ordering
    disks.sort(key=lambda d: d.mount)
    return disks


def _disk_health(disks: list[DiskUsage]) -> str:
    if not disks:
        return "unknown"
    worst = max((d.percent for d in disks), default=0.0)
    # Keep thresholds aligned with UI badges
    if worst >= 95.0:
        return "crit"
    if worst >= 85.0:
        return "warn"
    return "ok"


def _gpu_devices() -> list[GpuDevice]:
    """Best-effort NVIDIA GPU probe using nvidia-smi.

    Returns [] if not available.
    """
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=0.8,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout:
        return []

    out: list[GpuDevice] = []
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not parts:
            continue
        name = parts[0] if len(parts) > 0 else "GPU"

        def _to_float(s: str) -> Optional[float]:
            try:
                return float(s)
            except Exception:
                return None

        def _to_int(s: str) -> Optional[int]:
            try:
                return int(float(s))
            except Exception:
                return None

        util = _to_float(parts[1]) if len(parts) > 1 else None
        mem_used = _to_int(parts[2]) if len(parts) > 2 else None
        mem_total = _to_int(parts[3]) if len(parts) > 3 else None
        temp = _to_float(parts[4]) if len(parts) > 4 else None

        out.append(
            GpuDevice(
                name=name,
                util_percent=util,
                mem_used_mb=mem_used,
                mem_total_mb=mem_total,
                temp_c=temp,
            )
        )
    return out


def _gpu_health(gpus: list[GpuDevice]) -> str:
    """Derived GPU health status.

    Heuristic thresholds (worst across devices):
    - temp >= 90C or VRAM >= 99% => crit
    - temp >= 83C or VRAM >= 95% or util >= 99% => warn
    - no GPU telemetry => unknown
    """
    if not gpus:
        return "unknown"

    def rank(status: str) -> int:
        if status == "crit":
            return 3
        if status == "warn":
            return 2
        if status == "ok":
            return 1
        return 0

    worst = "ok"
    for g in gpus:
        dev = "ok"
        if g.temp_c is not None:
            if float(g.temp_c) >= 90.0:
                dev = "crit"
            elif float(g.temp_c) >= 83.0:
                dev = "warn"

        if g.mem_used_mb is not None and g.mem_total_mb:
            try:
                mem_pct = (float(g.mem_used_mb) / float(g.mem_total_mb)) * 100.0
                if mem_pct >= 99.0:
                    dev = "crit"
                elif mem_pct >= 95.0:
                    dev = "warn" if dev != "crit" else dev
            except Exception:
                pass

        if g.util_percent is not None:
            try:
                if float(g.util_percent) >= 99.0 and dev == "ok":
                    dev = "warn"
            except Exception:
                pass

        if rank(dev) > rank(worst):
            worst = dev
    return worst


def _top_processes(limit: int = 5) -> list[dict]:
    procs: list[dict] = []
    for p in psutil.process_iter(attrs=["pid", "name", "memory_percent"]):
        try:
            cpu = p.cpu_percent(interval=None)
            info = p.info
            procs.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "cpu_percent": float(cpu),
                    "mem_percent": float(info.get("memory_percent") or 0.0),
                }
            )
        except Exception:
            continue
    procs.sort(key=lambda x: (x.get("cpu_percent", 0.0), x.get("mem_percent", 0.0)), reverse=True)
    return procs[:limit]


def _cpu_freq_mhz() -> Optional[float]:
    try:
        f = psutil.cpu_freq()
        if not f:
            return None
        return float(f.current)
    except Exception:
        return None


def _cpu_temp_c() -> Optional[float]:
    """Best-effort CPU temperature.

    On many Linux systems psutil exposes sensors; otherwise returns None.
    """
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False)  # type: ignore[attr-defined]
    except Exception:
        return None
    if not temps:
        return None

    candidates = []
    for name, entries in temps.items():
        for e in entries or []:
            # prefer labeled CPU package/core temps
            label = (getattr(e, "label", "") or "").lower()
            cur = getattr(e, "current", None)
            if cur is None:
                continue
            score = 0
            if "package" in label or "tctl" in label:
                score += 3
            if "cpu" in label or "core" in label:
                score += 2
            if name.lower() in ("coretemp", "k10temp", "cpu_thermal"):
                score += 2
            candidates.append((score, float(cur)))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def collect_sample() -> SystemSample:
    ts = time.time()
    hostname = socket.gethostname()

    cpu_percent = float(psutil.cpu_percent(interval=None))
    cpu_freq_mhz = _cpu_freq_mhz()
    cpu_temp_c = _cpu_temp_c()
    l1, l5, l15 = _safe_getloadavg()

    try:
        boot = float(psutil.boot_time())
        uptime = float(ts - boot)
    except Exception:
        boot = None
        uptime = None

    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()

    net = psutil.net_io_counters()
    disks = _disk_usages()

    gpus = _gpu_devices()
    return SystemSample(
        ts=ts,
        hostname=hostname,
        cpu_percent=cpu_percent,
        cpu_freq_mhz=cpu_freq_mhz,
        cpu_temp_c=cpu_temp_c,
        load1=l1,
        load5=l5,
        load15=l15,

        boot_time_ts=boot,
        uptime_seconds=uptime,
        mem_total_bytes=int(vm.total),
        mem_used_bytes=int(vm.used),
        mem_available_bytes=int(vm.available),
        mem_percent=float(vm.percent),
        swap_total_bytes=int(sm.total),
        swap_used_bytes=int(sm.used),
        swap_percent=float(sm.percent),
        disk=disks,
        disk_health=_disk_health(disks),
        net=NetIO(bytes_sent=int(net.bytes_sent), bytes_recv=int(net.bytes_recv)),
        protocols=get_protocols_snapshot(),
        gpu=gpus,
        gpu_health=_gpu_health(gpus),
        top_processes=_top_processes(),
    )


def add_sample(sample: SystemSample) -> None:
    store = get_store()
    # Ensure deque maxlen reflects current settings
    if store.history.maxlen != store.maxlen():
        store.history = deque(store.history, maxlen=store.maxlen())
    store.history.append(sample)


def latest() -> Optional[SystemSample]:
    store = get_store()
    if not store.history:
        return None
    return store.history[-1]


def history(seconds: int) -> list[SystemSample]:
    store = get_store()
    if not store.history:
        return []
    cutoff = time.time() - max(1, seconds)
    return [s for s in store.history if s.ts >= cutoff]
