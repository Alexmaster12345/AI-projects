#!/usr/bin/env python3
"""
Simple ASHD Agent for CentOS-Docker Host
Copy this file to /opt/ashd-agent/agent.py on the target host
"""

import json
import time
import socket
import sys

try:
    import psutil
    import requests
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Install with: yum install python3-psutil python3-requests")
    sys.exit(1)

# Configuration
SERVER_URL = "http://192.168.50.1:8000"  # Update to your dashboard IP
HOSTNAME = socket.gethostname()
INTERVAL = 30

def collect_metrics():
    """Collect system metrics."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        uptime = time.time() - psutil.boot_time()
        
        load = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
        
        return {
            "hostname": HOSTNAME,
            "cpu_percent": cpu,
            "mem_percent": mem.percent,
            "disk_percent": disk.percent,
            "net_bytes_sent": net.bytes_sent,
            "net_bytes_recv": net.bytes_recv,
            "uptime_seconds": uptime,
            "load1": load[0],
            "load5": load[1],
            "load15": load[2],
            "timestamp": int(time.time())
        }
    except Exception as e:
        print(f"Error collecting metrics: {e}")
        return None

def main():
    """Main agent loop."""
    print(f"ASHD Agent starting for {HOSTNAME}")
    print(f"Server: {SERVER_URL}")
    print(f"Interval: {INTERVAL} seconds")
    
    while True:
        try:
            metrics = collect_metrics()
            if metrics:
                print(f"Sending metrics: CPU={metrics['cpu_percent']:.1f}%, MEM={metrics['mem_percent']:.1f}%")
                response = requests.post(f"{SERVER_URL}/api/agent/report", json=metrics, timeout=10)
                if response.status_code == 200:
                    print(f"✓ Metrics sent successfully: {response.status_code}")
                else:
                    print(f"✗ Failed to send metrics: {response.status_code} - {response.text}")
            else:
                print("✗ Failed to collect metrics")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
