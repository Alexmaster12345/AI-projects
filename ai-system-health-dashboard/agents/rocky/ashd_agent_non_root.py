#!/usr/bin/env python3
"""
ASHD Monitoring Agent for Rocky (Non-Root Version)
"""

import json
import time
import subprocess
import socket
import psutil
import requests
import os
import pwd
from pathlib import Path

class NonRootASHDAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = self.get_hostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30
        self.user = pwd.getpwuid(os.getuid()).pw_name
    
    def get_hostname(self):
        """Get hostname with fallback methods for auto-discovery."""
        try:
            # Method 1: socket.gethostname() - most reliable
            hostname = socket.gethostname()
            if hostname and hostname != 'localhost' and hostname != 'localhost.localdomain':
                return hostname
        except:
            pass
        
        try:
            # Method 2: platform.node() - alternative method
            import platform
            hostname = platform.node()
            if hostname and hostname != 'localhost' and hostname != 'localhost.localdomain':
                return hostname
        except:
            pass
        
        try:
            # Method 3: Read from /etc/hostname (Linux specific)
            with open('/etc/hostname', 'r') as f:
                hostname = f.read().strip()
                if hostname and hostname != 'localhost' and hostname != 'localhost.localdomain':
                    return hostname
        except:
            pass
        
        try:
            # Method 4: Use hostname command
            result = subprocess.run(['hostname'], capture_output=True, text=True, timeout=5)
            hostname = result.stdout.strip()
            if hostname and hostname != 'localhost' and hostname != 'localhost.localdomain':
                return hostname
        except:
            pass
        
        # Fallback: generate a unique identifier
        try:
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
            return f"agent-{mac[:8]}"
        except:
            return f"agent-{int(time.time())}"
        
    def run_command_with_sudo(self, command):
        """Run command with sudo if needed."""
        try:
            # Try without sudo first
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Try with sudo
            result = subprocess.run(f"sudo {command}", shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return ""
        except Exception:
            return ""
    
    def get_system_metrics(self):
        """Collect system metrics."""
        try:
            # Basic metrics (no sudo required)
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            try:
                load_avg = os.getloadavg()
            except:
                load_avg = [0, 0, 0]
            
            try:
                uptime = time.time() - psutil.boot_time()
            except:
                uptime = 0
            
            try:
                process_count = len(psutil.pids())
            except:
                process_count = 0
            
            # Service status (requires sudo)
            service_status = {
                'snmpd': self._check_service('snmpd'),
                'chronyd': self._check_service('chronyd') if 'rocky' in ['rhel', 'centos', 'rocky'] else self._check_service('ntp'),
                'ashd-agent': self._check_service('ashd-agent')
            }
            
            # NTP status (requires sudo)
            ntp_status = self._get_ntp_status()
            
            metrics = {
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': 'rocky',
                'user': self.user,
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
                'processes': process_count,
                'services': service_status,
                'ntp': ntp_status
            }
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            return None
    
    def _check_service(self, service_name):
        """Check if a service is active."""
        try:
            status = self.run_command_with_sudo(f"systemctl is-active {service_name}")
            return status.strip() if status else "unknown"
        except:
            return "unknown"
    
    def _get_ntp_status(self):
        """Get NTP synchronization status."""
        try:
            if 'rocky' in ['rhel', 'centos', 'rocky']:
                # Use chronyc
                output = self.run_command_with_sudo("chronyc tracking")
                if output:
                    lines = output.split('\n')
                    status = {}
                    for line in lines:
                        if 'Stratum' in line:
                            status['stratum'] = line.split(':')[1].strip()
                        if 'Last offset' in line:
                            status['offset'] = line.split(':')[1].strip()
                    return status
            else:
                # Use ntpq for Ubuntu/Debian
                output = self.run_command_with_sudo("ntpq -c rv")
                if output:
                    lines = output.split('\n')
                    status = {}
                    for line in lines:
                        if 'stratum=' in line:
                            status['stratum'] = line.split('=')[1].strip()
                        if 'offset=' in line:
                            status['offset'] = line.split('=')[1].strip()
                    return status
        except:
            pass
        return {'status': 'unknown'}
    
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
        print(f"ASHD Agent starting for {self.hostname} (user: {self.user})")
        print(f"Reporting to: {self.server_url}")
        
        while True:
            try:
                metrics = self.get_system_metrics()
                if metrics:
                    success = self.send_metrics(metrics)
                    if success:
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Metrics sent")
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
    agent = NonRootASHDAgent()
    agent.run()
