#!/usr/bin/env python3
"""
Simple agent example to report host metrics to the dashboard.
Run this on a host you want to monitor.

Usage:
  python3 agent_example.py --server http://dashboard:8000 --interval 30
"""

import argparse
import json
import time
import socket
import psutil
import requests

def collect_metrics():
    """Collect basic system metrics."""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    load1, load5, load15 = psutil.getloadavg()
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
    parser = argparse.ArgumentParser(description="Simple metrics agent for ASHD")
    parser.add_argument("--server", required=True, help="Dashboard server URL, e.g., http://192.168.50.10:8000")
    parser.add_argument("--interval", type=int, default=30, help="Reporting interval in seconds")
    args = parser.parse_args()

    report_url = f"{args.server.rstrip('/')}/api/agent/report"
    print(f"Reporting to: {report_url}")
    print(f"Interval: {args.interval}s")

    while True:
        try:
            metrics = collect_metrics()
            resp = requests.post(report_url, json=metrics, timeout=10)
            if resp.status_code == 200:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Reported OK")
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception: {e}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
