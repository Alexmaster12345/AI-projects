from __future__ import annotations

import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class NetSession:
    session_id: str
    interface: str
    bpf_filter: str
    mode: str  # 'summary' | 'pcap'
    started_at: float
    finished_at: Optional[float]
    return_code: Optional[int]
    log_path: Path
    pcap_path: Optional[Path]
    error: Optional[str]
    _proc: Optional[subprocess.Popen[str]]


_sessions: Dict[str, NetSession] = {}
_sessions_lock = threading.Lock()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_line(log_path: Path, line: str) -> None:
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _infer_error_from_log_tail(log_text: str) -> Optional[str]:
    t = (log_text or "").lower()

    # Common tcpdump permission/capabilities errors.
    if "you don't have permission" in t or "operation not permitted" in t:
        return (
            "permission denied for packet capture. "
            "On Linux you typically need root or capabilities (CAP_NET_RAW/CAP_NET_ADMIN) for tcpdump."
        )

    if "cannot open" in t and "permission" in t:
        return "permission denied for packet capture"

    return None


def list_interfaces() -> List[str]:
    # Try `ip` first (Linux). Fall back to /sys/class/net.
    interfaces: List[str] = []
    ip_path = shutil.which("ip")

    if ip_path:
        try:
            out = subprocess.check_output([ip_path, "-o", "link", "show"], text=True, stderr=subprocess.STDOUT)
            for line in out.splitlines():
                # Format: "1: lo: <...>" or "2: eth0@if3: <...>"
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    name = parts[1].strip()
                    name = name.split("@")[0]
                    if name and name not in interfaces:
                        interfaces.append(name)
        except Exception:
            interfaces = []

    if interfaces:
        return interfaces

    sys_net = Path("/sys/class/net")
    if sys_net.exists():
        for p in sys_net.iterdir():
            if p.is_dir():
                interfaces.append(p.name)

    return sorted(set(interfaces))


def _run_tcpdump(session: NetSession) -> None:
    tcpdump = shutil.which("tcpdump")
    if not tcpdump:
        with _sessions_lock:
            session.error = "tcpdump not found. Install tcpdump (e.g., 'sudo dnf install tcpdump' or 'sudo apt install tcpdump')."
            session.return_code = 127
            session.finished_at = time.time()
        _write_line(session.log_path, f"[siem] ERROR: {session.error}")
        return

    args: List[str] = [tcpdump, "-i", session.interface, "-n", "-tt", "-q"]

    if session.mode == "pcap":
        # Capture full packets (headers + payload) into a Wireshark-compatible file.
        # NOTE: this can create large files quickly.
        if session.pcap_path is None:
            with _sessions_lock:
                session.error = "internal error: missing pcap_path"
                session.return_code = 1
                session.finished_at = time.time()
            _write_line(session.log_path, f"[siem] ERROR: {session.error}")
            return

        args.extend(["-s", "0", "-U", "-w", str(session.pcap_path)])
    else:
        # Summary mode: line-buffered stdout for live display.
        args.extend(["-l", "-s", "96"])

    if session.bpf_filter.strip():
        # tcpdump expects filter as separate tokens; split on whitespace.
        # This is not a shell, so no injection.
        args.extend(session.bpf_filter.strip().split())

    _write_line(session.log_path, f"[siem] starting tcpdump ({session.mode}): {' '.join(args)}")
    if session.mode == "pcap" and session.pcap_path is not None:
        _write_line(session.log_path, f"[siem] writing pcap to: {session.pcap_path}")

    try:
        # In pcap mode tcpdump writes to file; stdout is mostly unused.
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        session._proc = proc

        captured_lines: List[str] = []

        if proc.stdout is not None:
            for line in proc.stdout:
                _write_line(session.log_path, line)
                if len(captured_lines) < 2000:
                    captured_lines.append(line)

        rc = proc.wait()
        _write_line(session.log_path, f"[siem] tcpdump finished with code {rc}")
        with _sessions_lock:
            session.return_code = rc
            session.finished_at = time.time()
            session._proc = None

            # If tcpdump exited with an error and we didn't already set a structured error,
            # infer a human-friendly error from its output.
            if rc != 0 and not session.error:
                tail = "".join(captured_lines[-40:])
                inferred = _infer_error_from_log_tail(tail)
                if inferred:
                    session.error = inferred
    except Exception as e:
        with _sessions_lock:
            session.error = f"monitor failed: {e}"
            session.return_code = 1
            session.finished_at = time.time()
            session._proc = None
        _write_line(session.log_path, f"[siem] ERROR: {session.error}")


def start_monitor(*, logs_dir: Path, interface: str, bpf_filter: str) -> NetSession:
    _ensure_dir(logs_dir)

    session_id = uuid.uuid4().hex
    log_path = logs_dir / f"net-{session_id}.log"
    pcap_path = logs_dir / f"net-{session_id}.pcap"

    session = NetSession(
        session_id=session_id,
        interface=interface,
        bpf_filter=bpf_filter,
        mode="summary",
        started_at=time.time(),
        finished_at=None,
        return_code=None,
        log_path=log_path,
        pcap_path=None,
        error=None,
        _proc=None,
    )

    _write_line(log_path, f"[siem] session_id={session_id}")

    with _sessions_lock:
        _sessions[session_id] = session

    t = threading.Thread(target=_run_tcpdump, args=(session,), daemon=True)
    t.start()

    return session


def start_capture(*, logs_dir: Path, interface: str, bpf_filter: str) -> NetSession:
    _ensure_dir(logs_dir)

    session_id = uuid.uuid4().hex
    log_path = logs_dir / f"net-{session_id}.log"
    pcap_path = logs_dir / f"net-{session_id}.pcap"

    session = NetSession(
        session_id=session_id,
        interface=interface,
        bpf_filter=bpf_filter,
        mode="pcap",
        started_at=time.time(),
        finished_at=None,
        return_code=None,
        log_path=log_path,
        pcap_path=pcap_path,
        error=None,
        _proc=None,
    )

    _write_line(log_path, f"[siem] session_id={session_id}")

    with _sessions_lock:
        _sessions[session_id] = session

    t = threading.Thread(target=_run_tcpdump, args=(session,), daemon=True)
    t.start()

    return session


def pcap_info(session: NetSession) -> Dict[str, int]:
    if session.pcap_path is None:
        return {"pcap_bytes": 0}
    try:
        return {"pcap_bytes": int(session.pcap_path.stat().st_size)}
    except Exception:
        return {"pcap_bytes": 0}


def stop_monitor(session_id: str) -> bool:
    with _sessions_lock:
        session = _sessions.get(session_id)
        if not session:
            return False
        proc = session._proc

    if proc is None:
        return True

    try:
        proc.terminate()
        return True
    except Exception:
        return False


def get_session(session_id: str) -> Optional[NetSession]:
    with _sessions_lock:
        return _sessions.get(session_id)


def read_log_tail(session: NetSession, *, max_bytes: int = 32_000) -> str:
    if not session.log_path.exists():
        return ""

    data = session.log_path.read_bytes()
    if len(data) <= max_bytes:
        return data.decode("utf-8", errors="replace")

    return data[-max_bytes:].decode("utf-8", errors="replace")
