#!/usr/bin/env python3
"""WAF Management Dashboard — Flask backend"""

import os
import re
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict, deque
from flask import Flask, render_template, jsonify, request, Response
import threading
import time

app = Flask(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
AUDIT_LOG    = "/var/log/waf/modsec_audit.log"
ACCESS_LOG   = "/var/log/waf/access.log"
CUSTOM_RULES = "/etc/nginx/modsec/custom-rules.conf"
MODSEC_CONF  = "/etc/nginx/modsec/modsecurity.conf"

# In-memory ring buffer for live feed (last 200 events)
_events: deque = deque(maxlen=200)
_stats = {
    "total_blocked": 0,
    "total_allowed": 0,
    "attack_types": defaultdict(int),
    "top_ips": defaultdict(int),
    "hourly": defaultdict(int),   # key = "YYYY-MM-DD HH"
}
_lock = threading.Lock()

# ── Log parsing ──────────────────────────────────────────────────────────────
ATTACK_TAG_RE = re.compile(r'tag "([^"]+)"')
MSG_RE        = re.compile(r'msg "([^"]+)"')
IP_RE         = re.compile(r'^\[.*?\] \S+ (\d+\.\d+\.\d+\.\d+)')
STATUS_RE     = re.compile(r'HTTP/[\d.]+" (\d{3})')
URI_RE        = re.compile(r'"(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS) ([^ ]+)')

def _classify_tag(tags: list[str]) -> str:
    for t in tags:
        t = t.lower()
        if "sqli" in t or "sql" in t:          return "SQLi"
        if "xss" in t:                          return "XSS"
        if "rfi" in t:                          return "RFI"
        if "lfi" in t or "traversal" in t:      return "LFI"
        if "rce" in t or "exec" in t:           return "RCE"
        if "scanner" in t or "bot" in t:        return "Scanner"
        if "webshell" in t or "shell" in t:     return "WebShell"
        if "admin" in t:                        return "Admin"
        if "sensitive" in t:                    return "SensitiveFile"
        if "protocol" in t:                     return "Protocol"
    return "Other"

def _parse_nginx_access_line(line: str):
    """Parse combined-log-format access log line."""
    m = re.match(
        r'(\S+) - \S+ \[([^\]]+)\] "([^"]*)" (\d+) (\d+)',
        line.strip()
    )
    if not m:
        return None
    ip, ts_raw, req, status, _ = m.groups()
    try:
        ts = datetime.strptime(ts_raw.split()[0], "%d/%b/%Y:%H:%M:%S")
    except Exception:
        ts = datetime.now()
    status = int(status)
    uri = req.split(" ")[1] if " " in req else req
    return {
        "ts": ts.isoformat(),
        "ip": ip,
        "uri": uri,
        "status": status,
        "blocked": status in (400, 403, 414, 429),
        "type": "Access",
    }

def _tail_access_log():
    """Background thread: tail access log and update in-memory stats."""
    while True:
        try:
            proc = subprocess.Popen(
                ["sudo", "tail", "-F", "-n", "0", ACCESS_LOG],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True
            )
            for line in proc.stdout:
                ev = _parse_nginx_access_line(line)
                if not ev:
                    continue
                with _lock:
                    _events.appendleft(ev)
                    hour_key = ev["ts"][:13]
                    if ev["blocked"]:
                        _stats["total_blocked"] += 1
                        _stats["hourly"][hour_key] += 1
                        _stats["top_ips"][ev["ip"]] += 1
                    else:
                        _stats["total_allowed"] += 1
        except Exception:
            pass
        time.sleep(5)

def _load_historical():
    """Load last 1000 lines of access log into memory at startup."""
    try:
        result = subprocess.run(
            ["sudo", "tail", "-n", "1000", ACCESS_LOG],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            ev = _parse_nginx_access_line(line)
            if not ev:
                continue
            with _lock:
                _events.append(ev)
                hour_key = ev["ts"][:13]
                if ev["blocked"]:
                    _stats["total_blocked"] += 1
                    _stats["hourly"][hour_key] += 1
                    _stats["top_ips"][ev["ip"]] += 1
                else:
                    _stats["total_allowed"] += 1
    except Exception:
        pass

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "nginx"],
            capture_output=True, text=True
        )
        nginx_status = result.stdout.strip()
    except Exception:
        nginx_status = "unknown"

    try:
        v = subprocess.run(
            ["sudo", "nginx", "-V"],
            capture_output=True, text=True
        )
        modsec = "enabled" if "modsecurity" in v.stderr.lower() else "unknown"
        # count loaded rules from error log
        rules_match = re.search(r"rules loaded.*?(\d+)/(\d+)/(\d+)", v.stderr)
    except Exception:
        modsec = "unknown"

    # Get rule count from nginx error log
    rules_loaded = 0
    try:
        r = subprocess.run(
            ["sudo", "grep", "-oP", r"rules loaded.*?local/\K\d+", "/var/log/nginx/error.log"],
            capture_output=True, text=True
        )
        nums = r.stdout.strip().splitlines()
        if nums:
            rules_loaded = int(nums[-1])
    except Exception:
        pass

    with _lock:
        blocked = _stats["total_blocked"]
        allowed = _stats["total_allowed"]

    return jsonify({
        "nginx": nginx_status,
        "modsecurity": modsec,
        "rules_loaded": rules_loaded,
        "blocked": blocked,
        "allowed": allowed,
        "uptime": _get_nginx_uptime(),
    })

def _get_nginx_uptime() -> str:
    try:
        r = subprocess.run(
            ["sudo", "systemctl", "show", "nginx", "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True
        )
        ts_str = r.stdout.strip().split("=", 1)[-1]
        ts = datetime.strptime(ts_str, "%a %Y-%m-%d %H:%M:%S %Z")
        delta = datetime.now() - ts
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m = rem // 60
        return f"{h}h {m}m"
    except Exception:
        return "N/A"

@app.route("/api/events")
def api_events():
    limit = min(int(request.args.get("limit", 50)), 200)
    filter_blocked = request.args.get("blocked", "")
    with _lock:
        events = list(_events)
    if filter_blocked == "1":
        events = [e for e in events if e.get("blocked")]
    elif filter_blocked == "0":
        events = [e for e in events if not e.get("blocked")]
    return jsonify(events[:limit])

@app.route("/api/stats")
def api_stats():
    with _lock:
        blocked = _stats["total_blocked"]
        allowed = _stats["total_allowed"]
        top_ips = sorted(_stats["top_ips"].items(), key=lambda x: -x[1])[:10]
        attack_types = dict(_stats["attack_types"])
        # last 24 hours hourly
        now = datetime.now()
        hourly = []
        for i in range(23, -1, -1):
            h = (now - timedelta(hours=i))
            key = h.strftime("%Y-%m-%d %H")
            hourly.append({"hour": h.strftime("%H:00"), "blocked": _stats["hourly"].get(key, 0)})

    return jsonify({
        "blocked": blocked,
        "allowed": allowed,
        "top_ips": [{"ip": ip, "count": c} for ip, c in top_ips],
        "attack_types": attack_types,
        "hourly": hourly,
    })

@app.route("/api/rules")
def api_rules():
    """Parse custom-rules.conf and return rules list."""
    rules = []
    try:
        result = subprocess.run(
            ["sudo", "cat", CUSTOM_RULES],
            capture_output=True, text=True
        )
        content = result.stdout
        # Find each SecRule / SecAction block
        for m in re.finditer(
            r'(?:^|\n)(#[^\n]*)?\n?SecRule\s+(\S+)\s+"([^"]+)"\s*\\\s*\n\s+"id:(\d+),([^"]+)"',
            content, re.MULTILINE
        ):
            comment, variables, operator, rule_id, actions = m.groups()
            msg_m = re.search(r"msg:'([^']+)'", actions)
            msg = msg_m.group(1) if msg_m else ""
            tag_m = re.search(r"tag:'([^']+)'", actions)
            tag = tag_m.group(1) if tag_m else ""
            disabled = bool(re.search(rf'#\s*SecRule.*id:{rule_id}', content))
            rules.append({
                "id": int(rule_id),
                "msg": msg,
                "tag": tag,
                "variables": variables,
                "operator": operator[:60] + ("…" if len(operator) > 60 else ""),
                "disabled": disabled,
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    rules.sort(key=lambda r: r["id"])
    return jsonify(rules)

@app.route("/api/logs/raw")
def api_logs_raw():
    """Return last N lines of the access log."""
    n = min(int(request.args.get("n", 100)), 500)
    try:
        result = subprocess.run(
            ["sudo", "tail", f"-n{n}", ACCESS_LOG],
            capture_output=True, text=True
        )
        return jsonify({"lines": result.stdout.splitlines()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs/audit")
def api_logs_audit():
    """Return last N lines of the ModSecurity audit log."""
    n = min(int(request.args.get("n", 100)), 500)
    try:
        result = subprocess.run(
            ["sudo", "tail", f"-n{n}", AUDIT_LOG],
            capture_output=True, text=True
        )
        return jsonify({"lines": result.stdout.splitlines()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/engine", methods=["POST"])
def api_engine():
    """Toggle SecRuleEngine On/Off/DetectionOnly."""
    mode = request.json.get("mode", "On")
    if mode not in ("On", "Off", "DetectionOnly"):
        return jsonify({"error": "Invalid mode"}), 400
    try:
        subprocess.run(
            ["sudo", "sed", "-i",
             f"s/^SecRuleEngine .*/SecRuleEngine {mode}/",
             MODSEC_CONF],
            check=True
        )
        subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
        return jsonify({"ok": True, "mode": mode})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/test", methods=["POST"])
def api_test():
    """Run test-waf.sh and stream results."""
    script = "/home/alexk/AI-projects/WAF/test-waf.sh"
    try:
        result = subprocess.run(
            ["bash", script, "http://localhost"],
            capture_output=True, text=True, timeout=120
        )
        # Strip ANSI colour codes
        clean = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout)
        return jsonify({"output": clean})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Test timed out"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Startup ───────────────────────────────────────────────────────────────────
_load_historical()
t = threading.Thread(target=_tail_access_log, daemon=True)
t.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=False)
