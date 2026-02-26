from flask import Flask, jsonify, request, render_template
from datetime import datetime
import copy, re, time

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Switch State
# ---------------------------------------------------------------------------

SWITCH_STATE = {
    "hostname": "SW1",
    "model": "VM-Switch 24G",
    "uptime_start": time.time(),
    "ports": {
        f"Gi0/{i}": {
            "id": f"Gi0/{i}",
            "label": f"Gi0/{i}",
            "status": "up" if i in [1,2,3,4,7,8] else "down",
            "admin": "up",
            "speed": "1000",
            "duplex": "full",
            "vlan": 1 if i not in [5,6] else 10,
            "mode": "access",
            "description": "",
            "mac_count": 1 if i in [1,2,3,4,7,8] else 0,
            "rx_bytes": 1024*1024*(i*3) if i in [1,2,3,4,7,8] else 0,
            "tx_bytes": 1024*512*(i*2) if i in [1,2,3,4,7,8] else 0,
            "errors": 0,
        }
        for i in range(1, 25)
    },
    "vlans": {
        1:  {"id": 1,  "name": "default",    "active": True,  "ports": []},
        10: {"id": 10, "name": "MGMT",       "active": True,  "ports": ["Gi0/5","Gi0/6"]},
        20: {"id": 20, "name": "SERVERS",    "active": True,  "ports": []},
        30: {"id": 30, "name": "GUEST",      "active": False, "ports": []},
        99: {"id": 99, "name": "NATIVE",     "active": True,  "ports": []},
    },
    "interfaces": {
        "Vlan1":  {"id": "Vlan1",  "ip": "192.168.1.1",   "mask": "255.255.255.0", "status": "up"},
        "Vlan10": {"id": "Vlan10", "ip": "10.0.10.1",     "mask": "255.255.255.0", "status": "up"},
        "Vlan20": {"id": "Vlan20", "ip": "10.0.20.1",     "mask": "255.255.255.0", "status": "up"},
    },
    "spanning_tree": {
        "mode": "rapid-pvst",
        "enabled": True,
        "root": "SW1",
        "priority": 32768,
    },
    "mac_table": [
        {"mac": "aa:bb:cc:11:22:01", "vlan": 1,  "port": "Gi0/1", "type": "dynamic"},
        {"mac": "aa:bb:cc:11:22:02", "vlan": 1,  "port": "Gi0/2", "type": "dynamic"},
        {"mac": "aa:bb:cc:11:22:03", "vlan": 1,  "port": "Gi0/3", "type": "dynamic"},
        {"mac": "aa:bb:cc:11:22:04", "vlan": 1,  "port": "Gi0/4", "type": "dynamic"},
        {"mac": "aa:bb:cc:11:22:07", "vlan": 1,  "port": "Gi0/7", "type": "dynamic"},
        {"mac": "aa:bb:cc:11:22:08", "vlan": 1,  "port": "Gi0/8", "type": "dynamic"},
        {"mac": "de:ad:be:ef:10:05", "vlan": 10, "port": "Gi0/5", "type": "static"},
        {"mac": "de:ad:be:ef:10:06", "vlan": 10, "port": "Gi0/6", "type": "static"},
    ],
    "acl": [],
    "ntp": {"server": "pool.ntp.org", "status": "synced"},
    "snmp": {"community": "public", "enabled": True},
    "logging": {"host": "", "level": "informational"},
    "cli_history": [],
}

# ---------------------------------------------------------------------------
# CLI Engine
# ---------------------------------------------------------------------------

CLI_MODE = {"mode": "exec", "context": None}   # exec / priv / config / if / vlan


def uptime_str():
    secs = int(time.time() - SWITCH_STATE["uptime_start"])
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    return f"{d}d {h}h {m}m {s}s"


def prompt():
    hn = SWITCH_STATE["hostname"]
    m = CLI_MODE["mode"]
    ctx = CLI_MODE.get("context", "")
    if m == "exec":    return f"{hn}>"
    if m == "priv":    return f"{hn}#"
    if m == "config":  return f"{hn}(config)#"
    if m == "if":      return f"{hn}(config-if)#"
    if m == "vlan":    return f"{hn}(config-vlan)#"
    return f"{hn}#"


def process_command(raw):
    global CLI_MODE
    cmd = raw.strip()
    if not cmd:
        return "", prompt()

    lo = cmd.lower()
    parts = cmd.split()
    lparts = [p.lower() for p in parts]
    out = []
    m = CLI_MODE["mode"]

    # ---- universal ----
    if lo in ("exit", "end", "quit"):
        if m in ("if", "vlan"):
            CLI_MODE = {"mode": "config", "context": None}
        elif m == "config":
            CLI_MODE = {"mode": "priv",   "context": None}
        elif m == "priv":
            CLI_MODE = {"mode": "exec",   "context": None}
        return "", prompt()

    if lo == "enable":
        CLI_MODE["mode"] = "priv"
        return "", prompt()

    if lo in ("disable",):
        CLI_MODE["mode"] = "exec"
        return "", prompt()

    if lo == "configure terminal" or lo == "conf t":
        if m != "priv":
            return "%  Not in privileged mode", prompt()
        CLI_MODE["mode"] = "config"
        return "Enter configuration commands, one per line. End with CNTL/Z.", prompt()

    # ---- show commands ----
    if lparts[0] == "show":
        return handle_show(lparts[1:])

    # ---- config-level commands ----
    if m == "config":
        return handle_config(lparts, parts)

    if m == "if":
        return handle_if_config(lparts, parts)

    if m == "vlan":
        return handle_vlan_config(lparts, parts)

    # ---- exec-level ----
    if lparts[0] == "ping":
        ip = parts[1] if len(parts) > 1 else ""
        if not ip:
            return "% Incomplete command", prompt()
        lines = [f"Sending 5 ICMP echos to {ip}:", "!!!!!",
                 f"Success rate is 100% (5/5), round-trip min/avg/max = 1/2/3 ms"]
        return "\n".join(lines), prompt()

    if lparts[0] == "traceroute":
        ip = parts[1] if len(parts) > 1 else ""
        return f"  1  gateway  1 ms\n  2  {ip}  2 ms", prompt()

    if lo in ("reload", "reload force"):
        SWITCH_STATE["uptime_start"] = time.time()
        return "Reloading... (simulated — uptime reset)", prompt()

    if lo == "write memory" or lo == "wr" or lo == "copy running-config startup-config":
        return "Building configuration...\n[OK]", prompt()

    if lo in ("clear mac address-table dynamic", "clear mac-address-table dynamic"):
        SWITCH_STATE["mac_table"] = [e for e in SWITCH_STATE["mac_table"] if e["type"] == "static"]
        return "MAC address table cleared.", prompt()

    return f"% Unrecognized command: '{cmd}'", prompt()


def handle_show(args):
    if not args:
        return "% Incomplete command", prompt()
    sub = args[0]

    if sub == "version":
        lines = [
            f"VM-Switch IOS Emulator v1.0",
            f"Hostname: {SWITCH_STATE['hostname']}",
            f"Model:    {SWITCH_STATE['model']}",
            f"Uptime:   {uptime_str()}",
            f"Ports:    24x GigabitEthernet",
        ]
        return "\n".join(lines), prompt()

    if sub == "running-config" or (len(args) > 1 and args[1] == "running-config"):
        return build_running_config(), prompt()

    if sub == "startup-config":
        return build_running_config(), prompt()

    if sub in ("interfaces", "interface"):
        if len(args) > 1:
            iface = args[1].capitalize() if len(args[1]) < 6 else args[1]
            # normalize e.g. gi0/1 -> Gi0/1
            iface = normalize_port(args[1])
            p = SWITCH_STATE["ports"].get(iface)
            if not p:
                return f"% Interface {iface} not found", prompt()
            lines = [
                f"{p['id']} is {p['status']}, line protocol is {p['status']}",
                f"  Description: {p['description'] or '(none)'}",
                f"  Speed: {p['speed']} Mbps, Duplex: {p['duplex']}",
                f"  Switchport mode: {p['mode']}, Access VLAN: {p['vlan']}",
                f"  Input:  {p['rx_bytes']} bytes",
                f"  Output: {p['tx_bytes']} bytes",
                f"  Errors: {p['errors']}",
            ]
            return "\n".join(lines), prompt()
        lines = []
        for pid, p in SWITCH_STATE["ports"].items():
            lines.append(f"{p['id']:<12} {p['status']:<6} {p['mode']:<8} VLAN {p['vlan']}")
        return "\n".join(lines), prompt()

    if sub == "interfaces" and len(args) >= 2 and args[1] == "status":
        return handle_show(["interfaces", "status"])

    if sub == "vlan" or (len(args) > 1 and args[0] == "vlan"):
        lines = ["VLAN  Name                Status    Ports", "-" * 60]
        for vid, v in sorted(SWITCH_STATE["vlans"].items()):
            ports = ",".join(v["ports"]) if v["ports"] else ""
            status = "active" if v["active"] else "act/lshut"
            lines.append(f"{vid:<5} {v['name']:<20} {status:<10} {ports}")
        return "\n".join(lines), prompt()

    if sub in ("ip", ) and len(args) > 1 and args[1] == "interface":
        lines = ["Interface      IP Address        Status", "-" * 50]
        for iid, iv in SWITCH_STATE["interfaces"].items():
            lines.append(f"{iid:<14} {iv['ip']}/{iv['mask']:<18} {iv['status']}")
        return "\n".join(lines), prompt()

    if sub in ("mac", "mac-address-table"):
        lines = ["Mac Address Table", "-" * 55,
                 f"{'Vlan':<6} {'Mac Address':<20} {'Type':<10} {'Ports'}", "-" * 55]
        for e in SWITCH_STATE["mac_table"]:
            lines.append(f"{e['vlan']:<6} {e['mac']:<20} {e['type']:<10} {e['port']}")
        return "\n".join(lines), prompt()

    if sub == "spanning-tree":
        stp = SWITCH_STATE["spanning_tree"]
        lines = [
            f"Spanning Tree Mode: {stp['mode']}",
            f"Root Bridge: {stp['root']}",
            f"Bridge Priority: {stp['priority']}",
            f"Status: {'enabled' if stp['enabled'] else 'disabled'}",
        ]
        return "\n".join(lines), prompt()

    if sub == "hostname":
        return SWITCH_STATE["hostname"], prompt()

    if sub in ("ntp", "ntp status"):
        n = SWITCH_STATE["ntp"]
        return f"NTP Server: {n['server']}\nStatus: {n['status']}", prompt()

    if sub == "snmp":
        s = SWITCH_STATE["snmp"]
        return f"SNMP Community: {s['community']}\nEnabled: {s['enabled']}", prompt()

    if sub == "uptime":
        return f"Uptime: {uptime_str()}", prompt()

    if sub == "clock":
        return f"Current time: {datetime.utcnow().strftime('%H:%M:%S UTC %b %d %Y')}", prompt()

    if sub == "users":
        return "    Line       User       Host(s)       Idle\n*  0 con 0    admin      idle          00:00:00", prompt()

    return f"% Unknown show subcommand: '{' '.join(args)}'", prompt()


def handle_config(lparts, parts):
    # hostname
    if lparts[0] == "hostname" and len(parts) > 1:
        SWITCH_STATE["hostname"] = parts[1]
        return "", prompt()

    # interface
    if lparts[0] in ("interface", "int") and len(parts) > 1:
        iface = normalize_port(" ".join(parts[1:]))
        if iface not in SWITCH_STATE["ports"]:
            return f"% Interface {iface} not found", prompt()
        CLI_MODE["mode"] = "if"
        CLI_MODE["context"] = iface
        return "", prompt()

    # vlan
    if lparts[0] == "vlan" and len(parts) > 1:
        vid = int(parts[1])
        if vid not in SWITCH_STATE["vlans"]:
            SWITCH_STATE["vlans"][vid] = {"id": vid, "name": f"VLAN{vid:04d}", "active": True, "ports": []}
        CLI_MODE["mode"] = "vlan"
        CLI_MODE["context"] = vid
        return "", prompt()

    # no vlan
    if lparts[0] == "no" and len(lparts) > 1 and lparts[1] == "vlan" and len(parts) > 2:
        vid = int(parts[2])
        if vid in SWITCH_STATE["vlans"]:
            del SWITCH_STATE["vlans"][vid]
            return f"VLAN {vid} deleted.", prompt()
        return f"% VLAN {vid} not found", prompt()

    # spanning-tree mode
    if lparts[0] == "spanning-tree" and len(lparts) > 1 and lparts[1] == "mode":
        SWITCH_STATE["spanning_tree"]["mode"] = parts[2] if len(parts) > 2 else "pvst"
        return "", prompt()

    if lparts[0] == "spanning-tree" and len(lparts) > 1 and lparts[1] == "priority":
        SWITCH_STATE["spanning_tree"]["priority"] = int(parts[2]) if len(parts) > 2 else 32768
        return "", prompt()

    if lparts[0] == "no" and len(lparts) > 1 and lparts[1] == "spanning-tree":
        SWITCH_STATE["spanning_tree"]["enabled"] = False
        return "Spanning tree disabled.", prompt()

    # ntp server
    if lparts[0] == "ntp" and len(lparts) > 1 and lparts[1] == "server":
        SWITCH_STATE["ntp"]["server"] = parts[2] if len(parts) > 2 else ""
        return "", prompt()

    # snmp
    if lparts[0] == "snmp-server" and len(lparts) > 2 and lparts[1] == "community":
        SWITCH_STATE["snmp"]["community"] = parts[2]
        return "", prompt()

    # ip interface vlan
    if lparts[0] == "interface" and len(lparts) > 1 and lparts[1].startswith("vlan"):
        vid = lparts[1].replace("vlan", "")
        CLI_MODE["mode"] = "if"
        CLI_MODE["context"] = f"Vlan{vid}"
        return "", prompt()

    return f"% Unknown config command: '{' '.join(parts)}'", prompt()


def handle_if_config(lparts, parts):
    iface = CLI_MODE.get("context", "")
    p = SWITCH_STATE["ports"].get(iface)

    # Vlan interface
    if iface.startswith("Vlan"):
        vi = SWITCH_STATE["interfaces"].get(iface)
        if lparts[0] == "ip" and len(lparts) > 2 and lparts[1] == "address":
            if not vi:
                SWITCH_STATE["interfaces"][iface] = {"id": iface, "ip": parts[2], "mask": parts[3] if len(parts) > 3 else "255.255.255.0", "status": "up"}
            else:
                vi["ip"] = parts[2]
                if len(parts) > 3:
                    vi["mask"] = parts[3]
            return "", prompt()
        if lparts[0] == "no" and len(lparts) > 2 and lparts[1] == "ip" and lparts[2] == "address":
            if vi:
                vi["ip"] = "unassigned"
            return "", prompt()
        return f"% Unknown interface command", prompt()

    if not p:
        return f"% Interface {iface} not found", prompt()

    if lparts[0] == "shutdown":
        p["admin"] = "down"
        p["status"] = "down"
        return "", prompt()

    if lparts[0] == "no" and len(lparts) > 1 and lparts[1] == "shutdown":
        p["admin"] = "up"
        p["status"] = "up"
        return "", prompt()

    if lparts[0] == "description" and len(parts) > 1:
        p["description"] = " ".join(parts[1:])
        return "", prompt()

    if lparts[0] == "switchport" and len(lparts) > 2 and lparts[1] == "mode":
        p["mode"] = lparts[2]
        return "", prompt()

    if lparts[0] == "switchport" and len(lparts) > 3 and lparts[1] == "access" and lparts[2] == "vlan":
        vid = int(parts[3])
        p["vlan"] = vid
        v = SWITCH_STATE["vlans"].get(vid)
        if v and iface not in v["ports"]:
            v["ports"].append(iface)
        return "", prompt()

    if lparts[0] == "speed" and len(parts) > 1:
        p["speed"] = parts[1]
        return "", prompt()

    if lparts[0] == "duplex" and len(parts) > 1:
        p["duplex"] = lparts[1]
        return "", prompt()

    if lparts[0] == "no" and len(lparts) > 1 and lparts[1] == "description":
        p["description"] = ""
        return "", prompt()

    return f"% Unknown interface command: '{' '.join(parts)}'", prompt()


def handle_vlan_config(lparts, parts):
    vid = CLI_MODE.get("context")
    v = SWITCH_STATE["vlans"].get(vid)
    if not v:
        return f"% VLAN {vid} not found", prompt()

    if lparts[0] == "name" and len(parts) > 1:
        v["name"] = parts[1]
        return "", prompt()

    if lparts[0] == "state" and len(lparts) > 1:
        v["active"] = lparts[1] == "active"
        return "", prompt()

    return f"% Unknown vlan command: '{' '.join(parts)}'", prompt()


def normalize_port(s):
    s = s.strip()
    m = re.match(r'^(?:gi(?:gabit(?:ethernet)?)?|ge)[\s]?(\d+/\d+)$', s, re.I)
    if m:
        return f"Gi0/{m.group(1).split('/')[-1]}"
    m2 = re.match(r'^gi0/(\d+)$', s, re.I)
    if m2:
        return f"Gi0/{m2.group(1)}"
    return s


def build_running_config():
    hn = SWITCH_STATE["hostname"]
    stp = SWITCH_STATE["spanning_tree"]
    lines = [
        "!",
        f"hostname {hn}",
        "!",
        f"spanning-tree mode {stp['mode']}",
    ]
    for vid, v in sorted(SWITCH_STATE["vlans"].items()):
        lines += [f"vlan {vid}", f" name {v['name']}", "!"]
    for pid, p in SWITCH_STATE["ports"].items():
        lines.append(f"interface {pid}")
        if p["description"]:
            lines.append(f" description {p['description']}")
        lines.append(f" switchport mode {p['mode']}")
        lines.append(f" switchport access vlan {p['vlan']}")
        if p["admin"] == "down":
            lines.append(" shutdown")
        lines.append("!")
    for iid, iv in SWITCH_STATE["interfaces"].items():
        lines.append(f"interface {iid}")
        lines.append(f" ip address {iv['ip']} {iv['mask']}")
        lines.append("!")
    lines.append("end")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    ports = SWITCH_STATE["ports"]
    up = sum(1 for p in ports.values() if p["status"] == "up")
    down = len(ports) - up
    return jsonify({
        "hostname": SWITCH_STATE["hostname"],
        "model": SWITCH_STATE["model"],
        "uptime": uptime_str(),
        "ports_up": up,
        "ports_down": down,
        "total_ports": len(ports),
        "vlan_count": len(SWITCH_STATE["vlans"]),
        "stp_mode": SWITCH_STATE["spanning_tree"]["mode"],
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    })


@app.route("/api/ports")
def api_ports():
    return jsonify(list(SWITCH_STATE["ports"].values()))


@app.route("/api/ports/<port_id>", methods=["GET", "PATCH"])
def api_port(port_id):
    p = SWITCH_STATE["ports"].get(port_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    if request.method == "PATCH":
        data = request.json or {}
        for k in ("status", "admin", "description", "vlan", "mode", "speed", "duplex"):
            if k in data:
                p[k] = data[k]
    return jsonify(p)


@app.route("/api/vlans")
def api_vlans():
    return jsonify(list(SWITCH_STATE["vlans"].values()))


@app.route("/api/vlans", methods=["POST"])
def api_vlan_create():
    data = request.json or {}
    vid = data.get("id")
    if not vid:
        return jsonify({"error": "id required"}), 400
    vid = int(vid)
    SWITCH_STATE["vlans"][vid] = {
        "id": vid,
        "name": data.get("name", f"VLAN{vid:04d}"),
        "active": True,
        "ports": [],
    }
    return jsonify(SWITCH_STATE["vlans"][vid]), 201


@app.route("/api/vlans/<int:vid>", methods=["DELETE"])
def api_vlan_delete(vid):
    if vid not in SWITCH_STATE["vlans"]:
        return jsonify({"error": "not found"}), 404
    del SWITCH_STATE["vlans"][vid]
    return jsonify({"ok": True})


@app.route("/api/mac-table")
def api_mac():
    return jsonify(SWITCH_STATE["mac_table"])


@app.route("/api/interfaces")
def api_interfaces():
    return jsonify(list(SWITCH_STATE["interfaces"].values()))


@app.route("/api/spanning-tree")
def api_stp():
    return jsonify(SWITCH_STATE["spanning_tree"])


@app.route("/api/cli", methods=["POST"])
def api_cli():
    data = request.json or {}
    cmd = data.get("command", "")
    SWITCH_STATE["cli_history"].append({"ts": datetime.utcnow().isoformat(), "cmd": cmd})
    output, new_prompt = process_command(cmd)
    return jsonify({"output": output, "prompt": new_prompt})


@app.route("/api/cli/prompt")
def api_cli_prompt():
    return jsonify({"prompt": prompt()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
