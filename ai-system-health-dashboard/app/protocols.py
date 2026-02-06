from __future__ import annotations

import asyncio
import errno
import re
import socket
import subprocess
import threading
import time
from typing import Dict, Optional

from .config import settings
from .models import ProtocolStatus


# Optional dependencies
try:
    import ntplib  # type: ignore
except Exception:  # pragma: no cover
    ntplib = None


try:
    from pysnmp.hlapi import (  # type: ignore
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )
except Exception:  # pragma: no cover
    CommunityData = None  # type: ignore
    ContextData = None  # type: ignore
    ObjectIdentity = None  # type: ignore
    ObjectType = None  # type: ignore
    SnmpEngine = None  # type: ignore
    UdpTransportTarget = None  # type: ignore
    getCmd = None  # type: ignore


_lock = threading.Lock()
_cache: Dict[str, ProtocolStatus] = {}
_task: Optional[asyncio.Task] = None


def get_protocols_snapshot() -> dict[str, ProtocolStatus]:
    """Return a snapshot of cached protocol health.

    This must be fast and safe to call from the sampler loop.
    """
    with _lock:
        return dict(_cache)


def _set(name: str, st: ProtocolStatus) -> None:
    with _lock:
        _cache[name] = st


def _now() -> float:
    return time.time()


def _check_ntp() -> ProtocolStatus:
    ts = _now()
    server = (settings.ntp_server or "").strip()
    if not server:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="not configured")

    if ntplib is None:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="ntplib not installed")

    try:
        c = ntplib.NTPClient()
        t0 = time.perf_counter()
        r = c.request(server, version=3, timeout=float(settings.ntp_timeout_seconds))
        t1 = time.perf_counter()
        delay_s = float(getattr(r, "delay", 0.0) or 0.0)
        latency_ms = (delay_s * 1000.0) if delay_s > 0 else ((t1 - t0) * 1000.0)
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"NTP failed: {e}")

    if latency_ms <= 150.0:
        status = "ok"
    elif latency_ms <= 300.0:
        status = "warn"
    else:
        status = "crit"

    return ProtocolStatus(status=status, checked_ts=ts, latency_ms=float(latency_ms), message=server)


_PING_RE = re.compile(r"time[=<]?\s*([0-9.]+)\s*ms", re.IGNORECASE)


def _check_icmp() -> ProtocolStatus:
    ts = _now()
    host = (settings.icmp_host or "").strip()
    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="not configured")

    timeout_s = max(1, int(float(settings.icmp_timeout_seconds) or 1))
    try:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_s), "-n", host],
            capture_output=True,
            text=True,
            timeout=float(timeout_s) + 0.5,
            check=False,
        )
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"ping failed: {e}")

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        msg = msg[:140] if msg else "no reply"
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"{host}: {msg}")

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = _PING_RE.search(out)
    latency_ms = float(m.group(1)) if m else None

    if latency_ms is None:
        return ProtocolStatus(status="ok", checked_ts=ts, message=host)
    if latency_ms <= 100.0:
        status = "ok"
    elif latency_ms <= 250.0:
        status = "warn"
    else:
        status = "crit"

    return ProtocolStatus(status=status, checked_ts=ts, latency_ms=float(latency_ms), message=host)


def _check_snmp() -> ProtocolStatus:
    ts = _now()
    host = (settings.snmp_host or "").strip()
    community = (settings.snmp_community or "").strip()
    port = int(settings.snmp_port)

    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="not configured")
    if not community:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="SNMP_COMMUNITY not set")
    if getCmd is None:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="pysnmp not installed")

    timeout = float(settings.snmp_timeout_seconds)
    try:
        t0 = time.perf_counter()
        # sysUpTime.0
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # v2c
            UdpTransportTarget((host, port), timeout=timeout, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),
        )
        error_indication, error_status, error_index, _var_binds = next(iterator)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        if error_indication:
            return ProtocolStatus(status="crit", checked_ts=ts, latency_ms=latency_ms, message=str(error_indication))
        if error_status:
            return ProtocolStatus(
                status="crit",
                checked_ts=ts,
                latency_ms=latency_ms,
                message=f"{error_status.prettyPrint()} at {error_index}",
            )

        return ProtocolStatus(status="ok", checked_ts=ts, latency_ms=latency_ms, message=f"{host}:{port}")
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"SNMP failed: {e}")


def _check_netflow_port() -> ProtocolStatus:
    ts = _now()
    port = int(settings.netflow_port)
    if port <= 0 or port > 65535:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="invalid port")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", port))
        # If we can bind, nobody else is bound => collector likely not running.
        return ProtocolStatus(status="warn", checked_ts=ts, message=f"UDP {port} is free")
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return ProtocolStatus(status="ok", checked_ts=ts, message=f"UDP {port} in use")
        if e.errno == errno.EACCES:
            return ProtocolStatus(status="unknown", checked_ts=ts, message="permission denied")
        return ProtocolStatus(status="unknown", checked_ts=ts, message=str(e))
    finally:
        try:
            s.close()
        except Exception:
            pass


def start_protocol_checker() -> None:
    """Start the background checker task (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="protocol-checker")


async def _loop() -> None:
    await asyncio.sleep(0.5)

    while True:
        try:
            # Run checks off-thread so we don't block the event loop.
            ntp = await asyncio.to_thread(_check_ntp)
            icmp = await asyncio.to_thread(_check_icmp)
            snmp = await asyncio.to_thread(_check_snmp)
            netflow = await asyncio.to_thread(_check_netflow_port)

            _set("ntp", ntp)
            _set("icmp", icmp)
            _set("snmp", snmp)
            _set("netflow", netflow)
        except Exception as e:
            ts = _now()
            _set("ntp", ProtocolStatus(status="unknown", checked_ts=ts, message=f"checker error: {e}"))

        await asyncio.sleep(max(5.0, float(settings.protocol_check_interval_seconds)))
