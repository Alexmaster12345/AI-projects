# VM-Switch Manager

A browser-based managed switch simulator with a full in-browser CLI emulator.

**URL:** `http://localhost:5050`

## Features

- **Dashboard** — port panel (24 ports), live stats, MAC table preview, switch info
- **Ports** — view all 24 GigabitEthernet ports, edit description/VLAN/mode/speed/duplex, shutdown/no-shutdown
- **VLANs** — create, view, and delete VLANs (ID 1–4094)
- **Routing** — Layer 3 SVI interfaces (ip address per VLAN)
- **MAC Table** — dynamic/static MAC entries, clear dynamic entries
- **Spanning Tree** — STP mode, root bridge, priority
- **CLI** — full in-browser Cisco IOS-like CLI with:
  - `enable` / `configure terminal` / `exit` / `end`
  - `show version`, `show interfaces`, `show vlan`, `show mac-address-table`
  - `show running-config`, `show spanning-tree`, `show ip interface`
  - `hostname`, `interface Gi0/X`, `switchport`, `shutdown`, `description`
  - `vlan <id>`, `name`, `no vlan`
  - `spanning-tree mode`, `spanning-tree priority`
  - `ntp server`, `snmp-server community`
  - `ping`, `traceroute`, `write memory`, `reload`
  - Arrow key history, Tab completion, Ctrl+C / Ctrl+Z / Ctrl+L

## Quick Start

```bash
cd VM-Switch
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5050`

## Project Structure

```
VM-Switch/
├── app.py              # Flask backend + CLI engine + switch state
├── requirements.txt
├── templates/
│   └── index.html      # Single-page web UI
└── static/
    ├── css/style.css   # Dark theme UI styles
    └── js/app.js       # Tab routing, API calls, CLI handler
```

## Default Switch State

| Item | Value |
|------|-------|
| Hostname | SW1 |
| Model | VM-Switch 24G |
| Ports | Gi0/1 – Gi0/24 |
| Ports Up | Gi0/1–4, Gi0/7–8 |
| VLAN 1 | default |
| VLAN 10 | MGMT (Gi0/5, Gi0/6) |
| VLAN 20 | SERVERS |
| STP Mode | rapid-pvst |
| SVI Vlan1 | 192.168.1.1/24 |
| SVI Vlan10 | 10.0.10.1/24 |
| SVI Vlan20 | 10.0.20.1/24 |

## CLI Examples

```
SW1> enable
SW1# show version
SW1# show interfaces
SW1# show vlan
SW1# configure terminal
SW1(config)# hostname CORE-SW
CORE-SW(config)# interface Gi0/1
CORE-SW(config-if)# description Uplink to Router
CORE-SW(config-if)# switchport access vlan 20
CORE-SW(config-if)# exit
CORE-SW(config)# vlan 40
CORE-SW(config-vlan)# name DMZ
CORE-SW(config-vlan)# exit
CORE-SW(config)# end
CORE-SW# write memory
```
