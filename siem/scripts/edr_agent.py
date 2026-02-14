#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import socket
import subprocess
import time
import uuid
import ipaddress
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx


AGENT_VERSION = "0.1.0"


def _auth_headers(*, api_key: Optional[str]) -> Dict[str, str]:
    key = (api_key or os.environ.get("SIEM_API_KEY") or "").strip()
    if not key:
        return {}
    return {"x-api-key": key}


def _auth_basic(*, user: Optional[str], password: Optional[str]) -> Optional[Tuple[str, str]]:
    u = (user or os.environ.get("SIEM_BASIC_USER") or "").strip()
    p = (password or os.environ.get("SIEM_BASIC_PASS") or "").strip()
    if not u or not p:
        return None
    return u, p


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path, *, limit: int = 128_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > limit:
            data = data[:limit]
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _os_release() -> str:
    p = Path("/etc/os-release")
    if not p.exists():
        return platform.platform()
    txt = read_text(p)
    pretty = ""
    for line in txt.splitlines():
        if line.startswith("PRETTY_NAME="):
            pretty = line.split("=", 1)[1].strip().strip('"')
            break
    return pretty or platform.platform()


def _get_ip_addrs() -> List[str]:
    addrs: List[str] = []
    try:
        hostname = socket.gethostname()
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            ip = info[4][0]
            if ":" in ip:
                continue
            if ip.startswith("127."):
                continue
            if ip not in addrs:
                addrs.append(ip)
    except Exception:
        pass
    return addrs


def _uptime_seconds() -> Optional[int]:
    p = Path("/proc/uptime")
    if not p.exists():
        return None
    try:
        first = p.read_text(encoding="utf-8").split()[0]
        return int(float(first))
    except Exception:
        return None


def _list_pids() -> Iterable[int]:
    proc = Path("/proc")
    for p in proc.iterdir():
        if p.is_dir() and p.name.isdigit():
            try:
                yield int(p.name)
            except Exception:
                continue


def _read_cmdline(pid: int) -> str:
    p = Path(f"/proc/{pid}/cmdline")
    try:
        raw = p.read_bytes()
        if not raw:
            return ""
        parts = [x.decode("utf-8", errors="replace") for x in raw.split(b"\x00") if x]
        return " ".join(parts).strip()
    except Exception:
        return ""


def _read_exe(pid: int) -> str:
    p = Path(f"/proc/{pid}/exe")
    try:
        return os.readlink(p)
    except Exception:
        return ""


def _read_uid(pid: int) -> Optional[int]:
    p = Path(f"/proc/{pid}/status")
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
    except Exception:
        return None
    return None


def _uid_to_user(uid: Optional[int]) -> Optional[str]:
    if uid is None:
        return None
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name
    except Exception:
        return str(uid)


def snapshot_processes(*, limit: int = 2000) -> Dict[str, Dict[str, Any]]:
    """Returns a dict keyed by a stable-ish process key.

    Key format: "<pid>:<exe>:<cmdline_hash>". This avoids false positives
    when PIDs are recycled.
    """
    out: Dict[str, Dict[str, Any]] = {}
    n = 0
    for pid in _list_pids():
        if n >= limit:
            break
        cmd = _read_cmdline(pid)
        exe = _read_exe(pid)
        uid = _read_uid(pid)
        user = _uid_to_user(uid)
        h = hashlib.sha1(cmd.encode("utf-8", errors="replace")).hexdigest()[:12]
        key = f"{pid}:{exe}:{h}"
        out[key] = {
            "pid": pid,
            "exe": exe,
            "cmdline": cmd,
            "uid": uid,
            "user": user,
        }
        n += 1
    return out


def _run_cmd(args: List[str], *, timeout: float = 2.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return int(p.returncode), (p.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:
        return 1, f"error: {e}"


def _which(name: str) -> Optional[str]:
    from shutil import which

    return which(name)


def _server_allow_list(base_url: str) -> Tuple[List[str], Optional[int]]:
    """Return (server_ips, port) for allowing SIEM connectivity during isolation."""
    try:
        u = urlparse(base_url)
        host = u.hostname
        port = u.port or (443 if u.scheme == "https" else 80)
        if not host:
            return [], None
        ips: List[str] = []
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        for info in infos:
            ip = info[4][0]
            # Prefer IPv4 for now
            if ":" in ip:
                continue
            if ip not in ips:
                ips.append(ip)
        return ips, int(port)
    except Exception:
        return [], None


def _run_root_cmd(args: List[str], *, timeout: float = 6.0) -> Tuple[int, str]:
    """Run a command that typically requires root; return (rc, output)."""
    try:
        p = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return int(p.returncode), (p.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception as e:
        return 1, f"error: {e}"


def _is_valid_ipv4(ip: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
    except Exception:
        return False


def _nft_table_exists() -> bool:
    if not _which("nft"):
        return False
    rc, _ = _run_root_cmd(["nft", "list", "table", "inet", "siem_edr"], timeout=2.0)
    return rc == 0


def _ensure_nft_base_chains(*, policy_drop: bool) -> Tuple[bool, str]:
    nft = _which("nft")
    if not nft:
        return False, "nft not found"

    cmds: List[List[str]] = []
    if not _nft_table_exists():
        cmds.append([nft, "add", "table", "inet", "siem_edr"])

    # Create chains if missing. If they exist, add will fail; ignore failures.
    policy = "drop" if policy_drop else "accept"
    cmds.extend(
        [
            [nft, "add", "chain", "inet", "siem_edr", "input", "{", "type", "filter", "hook", "input", "priority", "0", ";", "policy", policy, ";", "}"] ,
            [nft, "add", "chain", "inet", "siem_edr", "output", "{", "type", "filter", "hook", "output", "priority", "0", ";", "policy", policy, ";", "}"] ,
        ]
    )

    out_parts: List[str] = []
    for c in cmds:
        rc, out = _run_root_cmd(c, timeout=4.0)
        if rc not in (0, 1):
            # 1 is common for "already exists"; still ok.
            return False, out or "nft command failed"
        if out.strip():
            out_parts.append(out.strip())

    return True, "\n".join(out_parts)


def isolate_endpoint(*, base_url: str) -> Tuple[bool, Dict[str, Any]]:
    """Isolate host by dropping most traffic, allowing only loopback, established, and SIEM server."""
    server_ips, port = _server_allow_list(base_url)
    if not server_ips or port is None:
        return False, {"error": "could not resolve SIEM server IP/port for allowlist"}

    nft = _which("nft")
    iptables = _which("iptables")

    if nft:
        ok, msg = _ensure_nft_base_chains(policy_drop=True)
        if not ok:
            return False, {"error": msg}

        # Base allow rules (best-effort). Order matters.
        allow_cmds: List[List[str]] = [
            [nft, "add", "rule", "inet", "siem_edr", "input", "iif", "lo", "accept"],
            [nft, "add", "rule", "inet", "siem_edr", "output", "oif", "lo", "accept"],
            [nft, "add", "rule", "inet", "siem_edr", "input", "ct", "state", "established,related", "accept"],
            [nft, "add", "rule", "inet", "siem_edr", "output", "ct", "state", "established,related", "accept"],
        ]

        for ip in server_ips:
            allow_cmds.append([nft, "add", "rule", "inet", "siem_edr", "output", "ip", "daddr", ip, "tcp", "dport", str(port), "accept"])
            allow_cmds.append([nft, "add", "rule", "inet", "siem_edr", "input", "ip", "saddr", ip, "tcp", "sport", str(port), "accept"])

        for c in allow_cmds:
            _run_root_cmd(c, timeout=4.0)

        return True, {"backend": "nft", "allowed_server_ips": server_ips, "allowed_port": port}

    if iptables:
        # Create chains and jump rules. Default policy is in our chains via final DROP.
        cmds = [
            [iptables, "-N", "SIEM_EDR_IN"],
            [iptables, "-N", "SIEM_EDR_OUT"],
            [iptables, "-C", "INPUT", "-j", "SIEM_EDR_IN"],
            [iptables, "-I", "INPUT", "1", "-j", "SIEM_EDR_IN"],
            [iptables, "-C", "OUTPUT", "-j", "SIEM_EDR_OUT"],
            [iptables, "-I", "OUTPUT", "1", "-j", "SIEM_EDR_OUT"],
        ]
        for c in cmds:
            rc, _ = _run_root_cmd(c, timeout=4.0)
            # ignore errors (exists / already inserted)
            _ = rc

        # Flush and re-add rules
        _run_root_cmd([iptables, "-F", "SIEM_EDR_IN"], timeout=4.0)
        _run_root_cmd([iptables, "-F", "SIEM_EDR_OUT"], timeout=4.0)

        # Allow loopback and established
        _run_root_cmd([iptables, "-A", "SIEM_EDR_IN", "-i", "lo", "-j", "ACCEPT"], timeout=4.0)
        _run_root_cmd([iptables, "-A", "SIEM_EDR_OUT", "-o", "lo", "-j", "ACCEPT"], timeout=4.0)
        _run_root_cmd([iptables, "-A", "SIEM_EDR_IN", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"], timeout=4.0)
        _run_root_cmd([iptables, "-A", "SIEM_EDR_OUT", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"], timeout=4.0)

        for ip in server_ips:
            _run_root_cmd([iptables, "-A", "SIEM_EDR_OUT", "-p", "tcp", "-d", ip, "--dport", str(port), "-j", "ACCEPT"], timeout=4.0)
            _run_root_cmd([iptables, "-A", "SIEM_EDR_IN", "-p", "tcp", "-s", ip, "--sport", str(port), "-j", "ACCEPT"], timeout=4.0)

        # Drop everything else
        _run_root_cmd([iptables, "-A", "SIEM_EDR_IN", "-j", "DROP"], timeout=4.0)
        _run_root_cmd([iptables, "-A", "SIEM_EDR_OUT", "-j", "DROP"], timeout=4.0)

        return True, {"backend": "iptables", "allowed_server_ips": server_ips, "allowed_port": port}

    return False, {"error": "neither nft nor iptables found"}


def unisolate_endpoint() -> Tuple[bool, Dict[str, Any]]:
    nft = _which("nft")
    iptables = _which("iptables")

    if nft and _nft_table_exists():
        rc, out = _run_root_cmd([nft, "delete", "table", "inet", "siem_edr"], timeout=6.0)
        if rc == 0:
            return True, {"backend": "nft"}
        return False, {"backend": "nft", "error": out.strip() or "delete table failed"}

    if iptables:
        # Remove jump rules and delete chains if present.
        for c in ([iptables, "-D", "INPUT", "-j", "SIEM_EDR_IN"], [iptables, "-D", "OUTPUT", "-j", "SIEM_EDR_OUT"]):
            _run_root_cmd(c, timeout=4.0)
        for c in (
            [iptables, "-F", "SIEM_EDR_IN"],
            [iptables, "-F", "SIEM_EDR_OUT"],
            [iptables, "-X", "SIEM_EDR_IN"],
            [iptables, "-X", "SIEM_EDR_OUT"],
        ):
            _run_root_cmd(c, timeout=4.0)
        return True, {"backend": "iptables"}

    return False, {"error": "no firewall backend found"}


def block_ip(*, ip: str) -> Tuple[bool, Dict[str, Any]]:
    if not _is_valid_ipv4(ip):
        return False, {"error": "invalid IPv4 address"}

    nft = _which("nft")
    iptables = _which("iptables")

    if nft:
        ok, msg = _ensure_nft_base_chains(policy_drop=False)
        if not ok:
            return False, {"error": msg}
        # Drop inbound from and outbound to IP.
        _run_root_cmd([nft, "add", "rule", "inet", "siem_edr", "input", "ip", "saddr", ip, "drop"], timeout=4.0)
        _run_root_cmd([nft, "add", "rule", "inet", "siem_edr", "output", "ip", "daddr", ip, "drop"], timeout=4.0)
        return True, {"backend": "nft", "ip": ip}

    if iptables:
        # Use explicit rules (best-effort idempotency not guaranteed).
        _run_root_cmd([iptables, "-I", "INPUT", "1", "-s", ip, "-j", "DROP"], timeout=4.0)
        _run_root_cmd([iptables, "-I", "OUTPUT", "1", "-d", ip, "-j", "DROP"], timeout=4.0)
        return True, {"backend": "iptables", "ip": ip}

    return False, {"error": "neither nft nor iptables found"}


def unblock_ip(*, ip: str) -> Tuple[bool, Dict[str, Any]]:
    if not _is_valid_ipv4(ip):
        return False, {"error": "invalid IPv4 address"}

    nft = _which("nft")
    iptables = _which("iptables")

    # Best-effort removal; rules may remain if multiple duplicates were inserted.
    if nft and _nft_table_exists():
        # Find and delete matching rules by handle.
        rc_in, out_in = _run_root_cmd([nft, "-a", "list", "chain", "inet", "siem_edr", "input"], timeout=4.0)
        rc_out, out_out = _run_root_cmd([nft, "-a", "list", "chain", "inet", "siem_edr", "output"], timeout=4.0)
        handles: List[str] = []
        if rc_in == 0:
            for line in out_in.splitlines():
                if f"ip saddr {ip}" in line and " drop" in line and "handle" in line:
                    handles.append(line.rsplit("handle", 1)[-1].strip())
        if rc_out == 0:
            for line in out_out.splitlines():
                if f"ip daddr {ip}" in line and " drop" in line and "handle" in line:
                    handles.append(line.rsplit("handle", 1)[-1].strip())

        deleted = 0
        # input/output handles are per-chain, so delete with chain context.
        if rc_in == 0:
            for line in out_in.splitlines():
                if f"ip saddr {ip}" in line and " drop" in line and "handle" in line:
                    h = line.rsplit("handle", 1)[-1].strip()
                    r, _ = _run_root_cmd([nft, "delete", "rule", "inet", "siem_edr", "input", "handle", h], timeout=4.0)
                    if r == 0:
                        deleted += 1
        if rc_out == 0:
            for line in out_out.splitlines():
                if f"ip daddr {ip}" in line and " drop" in line and "handle" in line:
                    h = line.rsplit("handle", 1)[-1].strip()
                    r, _ = _run_root_cmd([nft, "delete", "rule", "inet", "siem_edr", "output", "handle", h], timeout=4.0)
                    if r == 0:
                        deleted += 1

        return True, {"backend": "nft", "ip": ip, "deleted": deleted}

    if iptables:
        # Attempt to delete one instance of each rule.
        _run_root_cmd([iptables, "-D", "INPUT", "-s", ip, "-j", "DROP"], timeout=4.0)
        _run_root_cmd([iptables, "-D", "OUTPUT", "-d", ip, "-j", "DROP"], timeout=4.0)
        return True, {"backend": "iptables", "ip": ip}

    return False, {"error": "no firewall backend found"}


def snapshot_listening_ports() -> Dict[str, Dict[str, Any]]:
    """Best-effort listening sockets snapshot using `ss` if available."""
    rc, out = _run_cmd(["ss", "-lntuap"], timeout=2.5)
    if rc != 0 or not out.strip():
        return {}

    ports: Dict[str, Dict[str, Any]] = {}
    for line in out.splitlines():
        if not line or line.lower().startswith("netid"):
            continue
        # Example:
        # tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=123,fd=3))
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[4]
        procinfo = " ".join(parts[6:]) if len(parts) >= 7 else ""
        key = f"{proto}:{local}:{procinfo}"[:240]
        ports[key] = {"proto": proto, "local": local, "proc": procinfo}
    return ports


def snapshot_logged_in_users() -> List[str]:
    rc, out = _run_cmd(["who"], timeout=1.5)
    if rc != 0:
        return []
    users: List[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        users.append(line)
    return users[:50]


def load_state(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def post_telemetry(
    client: httpx.Client,
    *,
    base_url: str,
    agent_id: str,
    host: str,
    events: List[Dict[str, Any]],
) -> None:
    if not events:
        return
    resp = client.post(
        f"{base_url.rstrip('/')}/edr/telemetry",
        json={"agent_id": agent_id, "host": host, "events": events},
    )
    resp.raise_for_status()


def register_agent(client: httpx.Client, *, base_url: str, agent_id: Optional[str], host: str) -> str:
    payload = {
        "agent_id": agent_id,
        "host": host,
        "os": _os_release(),
        "ip": ",".join(_get_ip_addrs()),
        "version": AGENT_VERSION,
        "tags": {
            "kernel": platform.release(),
            "machine": platform.machine(),
        },
    }
    resp = client.post(f"{base_url.rstrip('/')}/edr/register", json=payload)
    resp.raise_for_status()
    data = resp.json()
    return str(data["agent_id"])


def poll_actions(client: httpx.Client, *, base_url: str, agent_id: str) -> List[Dict[str, Any]]:
    resp = client.get(f"{base_url.rstrip('/')}/edr/actions/poll", params={"agent_id": agent_id, "limit": 20})
    resp.raise_for_status()
    data = resp.json()
    return list(data.get("actions") or [])


def ack_action(client: httpx.Client, *, base_url: str, action_id: int, agent_id: str) -> bool:
    resp = client.post(
        f"{base_url.rstrip('/')}/edr/actions/{action_id}/ack",
        json={"agent_id": agent_id},
    )
    resp.raise_for_status()
    return bool(resp.json().get("ok"))


def post_action_result(
    client: httpx.Client,
    *,
    base_url: str,
    action_id: int,
    agent_id: str,
    ok: bool,
    result: Dict[str, Any],
) -> None:
    resp = client.post(
        f"{base_url.rstrip('/')}/edr/actions/{action_id}/result",
        json={"agent_id": agent_id, "ok": ok, "result": result},
    )
    resp.raise_for_status()


def _sha256_file(path: Path, *, max_bytes: int = 50_000_000) -> Tuple[bool, Dict[str, Any]]:
    if not path.exists():
        return False, {"error": "path not found"}
    if not path.is_file():
        return False, {"error": "path is not a file"}

    try:
        size = int(path.stat().st_size)
    except Exception:
        size = -1

    if size > max_bytes:
        return False, {"error": f"file too large ({size} bytes)", "max_bytes": max_bytes}

    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return True, {"sha256": h.hexdigest(), "bytes": size}
    except Exception as e:
        return False, {"error": str(e)}


def _kill_process(pid: int) -> Tuple[bool, Dict[str, Any]]:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, {"note": "process not found"}
    except PermissionError:
        return False, {"error": "permission denied"}
    except Exception as e:
        return False, {"error": str(e)}

    # Grace period
    time.sleep(0.8)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True, {"note": "terminated"}
    except Exception:
        pass

    try:
        os.kill(pid, signal.SIGKILL)
        return True, {"note": "killed"}
    except PermissionError:
        return False, {"error": "permission denied"}
    except Exception as e:
        return False, {"error": str(e)}


def handle_action(
    action: Dict[str, Any], *, allow_response: bool, server_url: str
) -> Tuple[bool, Dict[str, Any]]:
    action_type = str(action.get("action_type") or "").strip()
    params = action.get("params") or {}
    if not isinstance(params, dict):
        params = {"params_raw": params}

    if not allow_response:
        return False, {"error": "response disabled (start agent with --allow-response)"}

    if action_type == "collect_file_hash":
        path = Path(str(params.get("path") or "").strip())
        ok, res = _sha256_file(path)
        res["path"] = str(path)
        return ok, res

    if action_type == "kill_process":
        try:
            pid = int(params.get("pid"))
        except Exception:
            return False, {"error": "pid must be an integer"}
        ok, res = _kill_process(pid)
        res["pid"] = pid
        return ok, res

    if action_type == "list_processes":
        procs = snapshot_processes(limit=200)
        # Return a small view
        return True, {"count": len(procs), "sample": list(procs.values())[:50]}

    if action_type == "isolate_endpoint":
        return isolate_endpoint(base_url=server_url)

    if action_type == "unisolate_endpoint":
        return unisolate_endpoint()

    if action_type == "block_ip":
        target = str(params.get("ip") or "").strip()
        return block_ip(ip=target)

    if action_type == "unblock_ip":
        target = str(params.get("ip") or "").strip()
        return unblock_ip(ip=target)

    return False, {"error": f"unknown action_type: {action_type}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Minimal Linux EDR agent for the SIEM MVP.")
    ap.add_argument("--server", default="http://VOLVIX.local:8000", help="SIEM base URL")
    ap.add_argument("--state", default=str(Path.home() / ".siem_edr" / "state.json"), help="State file path")
    ap.add_argument("--agent-id", default=None, help="Optional fixed agent id (otherwise saved in state)")
    ap.add_argument("--interval", type=float, default=5.0, help="Seconds between loops")
    ap.add_argument(
        "--allow-response",
        action="store_true",
        help=(
            "Allow executing response actions (kill_process, collect_file_hash, list_processes, "
            "isolate_endpoint, unisolate_endpoint, block_ip, unblock_ip)"
        ),
    )
    ap.add_argument("--api-key", default="", help="SIEM API key (or set SIEM_API_KEY)")
    ap.add_argument("--basic-user", default="", help="SIEM Basic auth user (or set SIEM_BASIC_USER)")
    ap.add_argument("--basic-pass", default="", help="SIEM Basic auth password (or set SIEM_BASIC_PASS)")
    args = ap.parse_args()

    state_path = Path(args.state)
    state = load_state(state_path)

    host = socket.gethostname()
    agent_id = args.agent_id or state.get("agent_id")

    if not agent_id:
        # pre-generate so it's stable even if register fails once
        agent_id = uuid.uuid4().hex

    headers = _auth_headers(api_key=args.api_key)
    basic = _auth_basic(user=args.basic_user, password=args.basic_pass)

    with httpx.Client(timeout=6.0, headers=headers, auth=basic) as client:
        try:
            agent_id = register_agent(client, base_url=args.server, agent_id=agent_id, host=host)
        except Exception as e:
            raise SystemExit(f"register failed: {e}")

        state["agent_id"] = agent_id
        save_state(state_path, state)

        prev_procs = state.get("procs") if isinstance(state.get("procs"), dict) else {}
        prev_ports = state.get("ports") if isinstance(state.get("ports"), dict) else {}

        while True:
            events: List[Dict[str, Any]] = []

            # Heartbeat
            events.append(
                {
                    "ts": now_utc_iso(),
                    "facility": "edr",
                    "severity": "info",
                    "message": "edr_heartbeat",
                    "fields": {
                        "agent_version": AGENT_VERSION,
                        "os": _os_release(),
                        "kernel": platform.release(),
                        "ip_addrs": _get_ip_addrs(),
                        "uptime_sec": _uptime_seconds(),
                    },
                }
            )

            # Process deltas
            procs = snapshot_processes(limit=2500)
            new_keys = [k for k in procs.keys() if k not in prev_procs]
            for k in new_keys[:60]:
                p = procs[k]
                events.append(
                    {
                        "ts": now_utc_iso(),
                        "facility": "edr",
                        "severity": "info",
                        "message": "edr_process_start",
                        "fields": p,
                    }
                )

            # Listening ports deltas
            ports = snapshot_listening_ports()
            new_ports = [k for k in ports.keys() if k not in prev_ports]
            for k in new_ports[:60]:
                s = ports[k]
                events.append(
                    {
                        "ts": now_utc_iso(),
                        "facility": "edr",
                        "severity": "info",
                        "message": "edr_listen_socket",
                        "fields": s,
                    }
                )

            # Logged-in users snapshot (small)
            users = snapshot_logged_in_users()
            if users:
                events.append(
                    {
                        "ts": now_utc_iso(),
                        "facility": "edr",
                        "severity": "info",
                        "message": "edr_logged_in_users",
                        "fields": {"who": users},
                    }
                )

            try:
                post_telemetry(client, base_url=args.server, agent_id=agent_id, host=host, events=events)
            except Exception as e:
                print(f"telemetry send failed: {e}")

            # Poll + handle actions
            try:
                actions = poll_actions(client, base_url=args.server, agent_id=agent_id)
                for a in actions:
                    action_id = int(a.get("id"))
                    if not ack_action(client, base_url=args.server, action_id=action_id, agent_id=agent_id):
                        continue
                    ok, res = handle_action(
                        a,
                        allow_response=bool(args.allow_response),
                        server_url=str(args.server),
                    )
                    post_action_result(client, base_url=args.server, action_id=action_id, agent_id=agent_id, ok=ok, result=res)
            except Exception as e:
                print(f"action poll/handle failed: {e}")

            # Persist state
            state["procs"] = procs
            state["ports"] = ports
            save_state(state_path, state)

            time.sleep(max(0.5, float(args.interval)))


if __name__ == "__main__":
    raise SystemExit(main())
