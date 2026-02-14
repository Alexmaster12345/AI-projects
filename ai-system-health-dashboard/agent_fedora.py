#!/usr/bin/env python3
"""
Lightweight agent for Fedora (and other Linux hosts) to report metrics to ASHD dashboard.
Features:
- Minimal dependencies (python3-psutil)
- Systemd service file included
- Graceful shutdown on SIGTERM/SIGINT
- Configurable server URL and interval via CLI or config file
"""

import argparse
import json
import os
import signal
import sys
import time
import socket
import logging
from pathlib import Path

try:
    import psutil
    import requests
except ImportError as e:
    sys.stderr.write(f"Missing required dependency: {e}\n")
    sys.stderr.write("Install with: sudo dnf install python3-psutil python3-requests\n")
    sys.exit(1)

# Defaults
DEFAULT_SERVER = "http://localhost:8000"
DEFAULT_INTERVAL = 30
CONFIG_PATH = Path("/etc/ashd-agent/config.json")

def load_config():
    """Load config from file if present."""
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load config from {CONFIG_PATH}: {e}")
    return {}

def collect_metrics():
    """Collect system metrics."""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    try:
        load1, load5, load15 = psutil.getloadavg()
    except AttributeError:
        # getloadavg not available on some platforms
        load1 = load5 = load15 = None
    uptime = time.time() - psutil.boot_time()
    return {
        "hostname": socket.gethostname(),
        "cpu_percent": cpu,
        "mem_percent": mem.percent,
        "disk_percent": (disk.used / disk.total) * 100,
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
        "uptime_seconds": uptime,
        "load1": load1,
        "load5": load5,
        "load15": load15,
        "timestamp": time.time(),
    }

def main():
    parser = argparse.ArgumentParser(description="ASHD agent for Fedora/Linux hosts")
    parser.add_argument("--server", help=f"Dashboard server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--interval", type=int, help=f"Reporting interval in seconds (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    # Load config file and override with CLI args
    cfg = load_config()
    server = args.server or cfg.get("server") or DEFAULT_SERVER
    interval = args.interval or cfg.get("interval") or DEFAULT_INTERVAL

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    report_url = f"{server.rstrip('/')}/api/agent/report"
    logging.info(f"Reporting to: {report_url}")
    logging.info(f"Interval: {interval}s")

    shutdown = False

    def handle_signal(signum, frame):
        nonlocal shutdown
        logging.info(f"Received signal {signum}, shutting down...")
        shutdown = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not shutdown:
        try:
            metrics = collect_metrics()
            resp = requests.post(report_url, json=metrics, timeout=10)
            if resp.status_code == 200:
                logging.debug("Reported OK")
            else:
                logging.warning(f"Error: {resp.status_code} {resp.text}")
        except Exception as e:
            logging.warning(f"Exception: {e}")
        # Sleep in chunks to allow quick shutdown
        for _ in range(interval):
            if shutdown:
                break
            time.sleep(1)

    logging.info("Agent stopped")

if __name__ == "__main__":
    main()
