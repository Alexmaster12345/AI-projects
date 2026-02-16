#!/usr/bin/env python3
"""
ASHD Monitoring Agent for Rhel

Collects system metrics and reports to ASHD server.
"""

import json
import time
import subprocess
import socket
import psutil
import platform
import requests
from pathlib import Path

class ASHDAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"  # Update with your ASHD server
        self.hostname = socket.gethostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30  # seconds
        
    def get_system_metrics(self):
        """Collect system metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Load average (Linux)
            try:
                load_avg = os.getloadavg()
            except:
                load_avg = [0, 0, 0]
            
            # System uptime
            try:
                uptime = time.time() - psutil.boot_time()
            except:
                uptime = 0
            
            metrics = {
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': 'rhel',
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg': list(load_avg)
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'uptime': uptime,
                'processes': len(psutil.pids())
            }
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            return None
    
    def send_metrics(self, metrics):
        """Send metrics to ASHD server."""
        try:
            response = requests.post(
                f"{self.server_url}/api/agent/metrics",
                json=metrics,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending metrics: {e}")
            return False
    
    def run(self):
        """Main agent loop."""
        print(f"ASHD Agent starting for {self.hostname} ({self.agent_id})")
        print(f"Reporting to: {self.server_url}")
        print(f"Metrics interval: {self.metrics_interval} seconds")
        
        while True:
            try:
                metrics = self.get_system_metrics()
                if metrics:
                    success = self.send_metrics(metrics)
                    if success:
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Metrics sent successfully")
                    else:
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Failed to send metrics")
                
                time.sleep(self.metrics_interval)
                
            except KeyboardInterrupt:
                print("Agent stopped by user")
                break
            except Exception as e:
                print(f"Agent error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    agent = ASHDAgent()
    agent.run()
