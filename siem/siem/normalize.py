from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


_SSHD_FAILED_RE = re.compile(
    r"Failed password for(?: invalid user)?\s+(?P<user>\S+)\s+from\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)
_SSHD_ACCEPTED_RE = re.compile(
    r"Accepted password for\s+(?P<user>\S+)\s+from\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)

_SUDO_CMD_RE = re.compile(
    r"sudo:\s+(?P<user>\S+)\s*:\s+.*\bCOMMAND=(?P<cmd>.+)$",
    re.IGNORECASE,
)
_SUDO_AUTH_FAIL_RE = re.compile(
    r"sudo:.*authentication failure",
    re.IGNORECASE,
)

_UFW_RE = re.compile(
    r"\bUFW\s+(?P<action>ALLOW|BLOCK)\b.*\bSRC=(?P<src>\d{1,3}(?:\.\d{1,3}){3})\b.*\bDST=(?P<dst>\d{1,3}(?:\.\d{1,3}){3})\b.*\bPROTO=(?P<proto>\w+)\b.*\bSPT=(?P<spt>\d+)\b.*\bDPT=(?P<dpt>\d+)\b",
    re.IGNORECASE,
)
_FIREWALL_KV_RE = re.compile(
    r"\bSRC=(?P<src>\d{1,3}(?:\.\d{1,3}){3})\b.*\bDST=(?P<dst>\d{1,3}(?:\.\d{1,3}){3})\b.*\bPROTO=(?P<proto>\w+)\b(?:.*\bSPT=(?P<spt>\d+)\b)?(?:.*\bDPT=(?P<dpt>\d+)\b)?",
    re.IGNORECASE,
)

_HTTP_ACCESS_RE = re.compile(
    r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>[^\s]+)\s+(?P<proto>[^"]+)"\s+(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)"',
    re.IGNORECASE,
)

_DNS_QUERY_RE = re.compile(
    r"\bquery:\s+(?P<qname>\S+)\s+IN\s+(?P<qtype>\S+)",
    re.IGNORECASE,
)
_DNS_CLIENT_RE = re.compile(
    r"\bclient\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})#\d+",
    re.IGNORECASE,
)

_DHCPACK_RE = re.compile(
    r"\bDHCPACK\b.*\bon\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\b.*\bto\s+(?P<mac>(?:[0-9a-f]{2}:){5}[0-9a-f]{2})\b",
    re.IGNORECASE,
)
_DHCPDISCOVER_RE = re.compile(
    r"\bDHCPDISCOVER\b.*\bfrom\s+(?P<mac>(?:[0-9a-f]{2}:){5}[0-9a-f]{2})\b",
    re.IGNORECASE,
)


def _get_any(fields: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if not k:
            continue
        if k in fields:
            return fields.get(k)
    return None


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    try:
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _as_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        s = str(v)
    except Exception:
        return None
    s = s.strip()
    return s if s else None


def _win_event_id(fields: Dict[str, Any]) -> Optional[int]:
    v = _get_any(fields, "EventID", "event_id", "winlog.event_id", "win.event_id")
    return _as_int(v)


def _merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for k, v in (extra or {}).items():
        if v is None:
            continue
        # Don't overwrite explicit values already provided.
        if k in out and out[k] not in (None, ""):
            continue
        out[k] = v
    return out


def normalize_event(
    *,
    source: str,
    message: str,
    fields: Dict[str, Any],
    host: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Normalize raw events into a lightweight, consistent field schema.

    This is intentionally simple (MVP): it enriches `fields` with common keys like:
    - auth.* for authentication events
    - src_ip, user
    - event_category, event_action, event_outcome

    It does not remove or rewrite original fields.
    """

    f: Dict[str, Any] = dict(fields or {})
    msg = str(message or "")
    src = str(source or "")

    # Common: ensure host is reflected into fields for correlation pivots.
    if host and "host" not in f:
        f["host"] = host

    # If upstream shippers provide a log type, preserve it.
    log_type = _as_str(_get_any(f, "log_type", "event.dataset", "dataset"))
    if log_type and "log_type" not in f:
        f["log_type"] = log_type

    # Try to recognize sshd auth events from syslog-style messages.
    m = _SSHD_FAILED_RE.search(msg)
    if m:
        user = m.group("user")
        ip = m.group("ip")
        enrich = {
            "event_category": "authentication",
            "event_action": "logon",
            "event_outcome": "failure",
            "auth.service": "sshd",
            "user": user,
            "src_ip": ip,
        }
        return msg, _merge(f, enrich)

    m = _SSHD_ACCEPTED_RE.search(msg)
    if m:
        user = m.group("user")
        ip = m.group("ip")
        enrich = {
            "event_category": "authentication",
            "event_action": "logon",
            "event_outcome": "success",
            "auth.service": "sshd",
            "user": user,
            "src_ip": ip,
        }
        return msg, _merge(f, enrich)

    # sudo command execution / auth failure (Linux auth.log)
    m = _SUDO_CMD_RE.search(msg)
    if m:
        user = m.group("user")
        cmd = m.group("cmd").strip()
        enrich = {
            "log_type": log_type or "sudo",
            "event_category": "privilege",
            "event_action": "sudo",
            "event_outcome": "success",
            "user": user,
            "command": cmd,
        }
        return msg, _merge(f, enrich)

    if _SUDO_AUTH_FAIL_RE.search(msg):
        enrich = {
            "log_type": log_type or "sudo",
            "event_category": "privilege",
            "event_action": "sudo",
            "event_outcome": "failure",
        }
        return msg, _merge(f, enrich)

    # Firewall logs (UFW / iptables-style key=value)
    m = _UFW_RE.search(msg)
    if m:
        action = (m.group("action") or "").upper()
        enrich = {
            "log_type": log_type or "firewall",
            "event_category": "network",
            "event_action": "connection",
            "event_outcome": "blocked" if action == "BLOCK" else "allowed",
            "src_ip": m.group("src"),
            "dst_ip": m.group("dst"),
            "network.protocol": (m.group("proto") or "").lower(),
            "src_port": _as_int(m.group("spt")),
            "dst_port": _as_int(m.group("dpt")),
        }
        return msg, _merge(f, enrich)

    if "SRC=" in msg and "DST=" in msg and "PROTO=" in msg:
        m = _FIREWALL_KV_RE.search(msg)
        if m:
            enrich = {
                "log_type": log_type or "firewall",
                "event_category": "network",
                "event_action": "connection",
                "src_ip": m.group("src"),
                "dst_ip": m.group("dst"),
                "network.protocol": (m.group("proto") or "").lower(),
                "src_port": _as_int(m.group("spt")),
                "dst_port": _as_int(m.group("dpt")),
            }
            return msg, _merge(f, enrich)

    # Web access logs (Apache/Nginx combined)
    m = _HTTP_ACCESS_RE.match(msg)
    if m:
        status = _as_int(m.group("status"))
        enrich = {
            "log_type": log_type or "web",
            "event_category": "web",
            "event_action": "http_request",
            "src_ip": m.group("ip"),
            "http_method": (m.group("method") or "").upper(),
            "http_path": m.group("path"),
            "http_status": status,
            "user_agent": m.group("ua"),
        }
        return msg, _merge(f, enrich)

    # DNS query logs (BIND/unbound style)
    m = _DNS_QUERY_RE.search(msg)
    if m:
        client = _DNS_CLIENT_RE.search(msg)
        enrich = {
            "log_type": log_type or "dns",
            "event_category": "network",
            "event_action": "dns_query",
            "dns_qname": m.group("qname"),
            "dns_qtype": m.group("qtype"),
            "src_ip": client.group("ip") if client else None,
        }
        return msg, _merge(f, enrich)

    # DHCP lease logs
    m = _DHCPACK_RE.search(msg)
    if m:
        enrich = {
            "log_type": log_type or "dhcp",
            "event_category": "network",
            "event_action": "dhcp_lease",
            "event_outcome": "success",
            "dhcp_ip": m.group("ip"),
            "dhcp_mac": m.group("mac"),
        }
        return msg, _merge(f, enrich)

    m = _DHCPDISCOVER_RE.search(msg)
    if m:
        enrich = {
            "log_type": log_type or "dhcp",
            "event_category": "network",
            "event_action": "dhcp_discover",
            "dhcp_mac": m.group("mac"),
        }
        return msg, _merge(f, enrich)

    # Windows Event Logs (expect JSON shippers to provide EventID + common fields)
    wid = _win_event_id(f)
    if wid is not None:
        # Common lookups used by several event IDs
        ip = _as_str(_get_any(f, "IpAddress", "ip", "src_ip", "winlog.event_data.IpAddress"))
        user = _as_str(_get_any(f, "TargetUserName", "user", "winlog.event_data.TargetUserName"))

        if wid in {4624, 4625}:
            enrich = {
                "log_type": log_type or "windows_security",
                "event_category": "authentication",
                "event_action": "logon",
                "event_outcome": "success" if wid == 4624 else "failure",
                "auth.service": "windows",
                "user": user,
                "src_ip": ip,
            }
            return msg, _merge(f, enrich)

        if wid == 1102:
            enrich = {
                "log_type": log_type or "windows_security",
                "event_category": "audit",
                "event_action": "log_cleared",
                "event_outcome": "success",
                "user": user,
                "src_ip": ip,
            }
            return msg, _merge(f, enrich)

        if wid in {4720, 4726}:
            enrich = {
                "log_type": log_type or "windows_security",
                "event_category": "identity",
                "event_action": "account_created" if wid == 4720 else "account_deleted",
                "event_outcome": "success",
                "user": user,
            }
            return msg, _merge(f, enrich)

        if wid in {4728, 4732, 4729, 4733}:
            group = _as_str(_get_any(f, "GroupName", "group", "winlog.event_data.GroupName"))
            enrich = {
                "log_type": log_type or "windows_security",
                "event_category": "identity",
                "event_action": "group_membership_added" if wid in {4728, 4732} else "group_membership_removed",
                "event_outcome": "success",
                "user": user,
                "group": group,
            }
            return msg, _merge(f, enrich)

        if wid == 4688:
            exe = _as_str(_get_any(f, "NewProcessName", "Image", "process.exe", "exe"))
            cmdline = _as_str(_get_any(f, "CommandLine", "process.command_line", "cmdline"))
            enrich = {
                "log_type": log_type or "windows_security",
                "event_category": "process",
                "event_action": "process_start",
                "event_outcome": "success",
                "user": user,
                "exe": exe,
                "cmdline": cmdline,
                "src_ip": ip,
            }
            return msg, _merge(f, enrich)

        if wid == 4104:
            script = _as_str(_get_any(f, "ScriptBlockText", "script", "powershell.script_block"))
            enrich = {
                "log_type": log_type or "powershell",
                "event_category": "process",
                "event_action": "powershell_script",
                "event_outcome": "success",
                "user": user,
                "script": script,
                "src_ip": ip,
            }
            return msg, _merge(f, enrich)

    # Generic structured flow records (NetFlow/IPFIX-like) sent as JSON into fields
    if _as_str(_get_any(f, "src_ip")) and (_as_int(_get_any(f, "dst_port")) is not None or _as_str(_get_any(f, "dst_ip"))):
        enrich = {
            "event_category": _as_str(_get_any(f, "event_category")) or "network",
            "event_action": _as_str(_get_any(f, "event_action")) or "flow",
            "src_ip": _as_str(_get_any(f, "src_ip")),
            "dst_ip": _as_str(_get_any(f, "dst_ip")),
            "src_port": _as_int(_get_any(f, "src_port")),
            "dst_port": _as_int(_get_any(f, "dst_port")),
            "network.protocol": _as_str(_get_any(f, "proto", "network.protocol")),
            "log_type": log_type or _as_str(_get_any(f, "log_type")) or "netflow",
        }
        return msg, _merge(f, enrich)

    # Fallback: preserve message/fields.
    return msg, f
