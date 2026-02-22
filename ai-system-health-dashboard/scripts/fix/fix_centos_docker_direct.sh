#!/bin/bash
# Direct Fix for centos-docker SNMP and NTP Issues

set -e

echo "🔧 Fixing SNMP and NTP Issues on centos-docker"
echo "=============================================="

# Variables
HOST="192.168.50.198"
AGENT_DIR="/opt/system-trace-agent"

echo "📁 Step 1: Creating agent directory on host..."
ssh root@$HOST 'mkdir -p $AGENT_DIR'

echo "📦 Step 2: Installing required packages..."
ssh root@$HOST 'dnf update -y'
ssh root@$HOST 'dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony'

echo "🐍 Step 3: Installing Python dependencies..."
ssh root@$HOST 'python3 -m pip install psutil requests'

echo "📝 Step 4: Creating System Trace agent..."
cat << 'EOF' | ssh root@$HOST 'cat > $AGENT_DIR/system-trace_agent.py'
#!/usr/bin/env python3
"""
System Trace Monitoring Agent for Rocky Linux
"""

import json
import time
import subprocess
import socket
import psutil
import platform
import requests
from pathlib import Path
import os

class System TraceAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = socket.gethostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30
        
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
            
            # Load average
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
                'os_type': 'rocky',
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
        """Send metrics to System Trace server."""
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
        print(f"System Trace Agent starting for {self.hostname}")
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
    agent = System TraceAgent()
    agent.run()
EOF

echo "⚙️  Step 5: Configuring SNMP..."
cat << 'EOF' | ssh root@$HOST 'cat > /etc/snmp/snmpd.conf'
# System Trace SNMP Configuration
# Basic SNMP v2c configuration

# Listen on all interfaces
agentAddress udp:161

# SNMP community strings
com2sec readonly  public
com2sec readwrite  private

# Group definitions
group MyROGroup v2c        readonly
group MyRWGroup v2c        readwrite

# Access control
view all    included  .1                               80
view system included  .iso.org.dod.internet.mgmt.mib-2.system

# Access permissions
access MyROGroup ""      any       noauth    exact  all    none   none
access MyRWGroup ""      any       noauth    exact  all    all    none

# System information
sysLocation    "Data Center"
sysContact     "admin@example.com"
sysServices    72

# Process monitoring
proc httpd
proc sendmail

# Disk monitoring
includeAllDisks 10%

# Load average monitoring
load 12 10 5
EOF

echo "⏰ Step 6: Configuring NTP..."
cat << 'EOF' | ssh root@$HOST 'cat > /etc/chrony.conf'
# Use public servers from the pool.ntp.org project.
pool pool.ntp.org iburst

# Record the rate at which the system clock gains/loses time.
driftfile /var/lib/chrony/drift

# Allow NTP client access from local network.
allow 192.168.0.0/16

# Serve time even if not synchronized to a time source.
local stratum 10
EOF

echo "🔥 Step 7: Configuring firewall..."
ssh root@$HOST 'firewall-cmd --permanent --add-port=161/udp'
ssh root@$HOST 'firewall-cmd --permanent --add-port=123/udp'
ssh root@$HOST 'firewall-cmd --reload'

echo "🔄 Step 8: Creating systemd service..."
cat << 'EOF' | ssh root@$HOST 'cat > /etc/systemd/system/system-trace-agent.service'
[Unit]
Description=System Trace Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/system-trace-agent
ExecStart=/usr/bin/python3 /opt/system-trace-agent/system-trace_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "🚀 Step 9: Starting services..."
ssh root@$HOST 'systemctl daemon-reload'
ssh root@$HOST 'systemctl enable snmpd'
ssh root@$HOST 'systemctl restart snmpd'
ssh root@$HOST 'systemctl enable chronyd'
ssh root@$HOST 'systemctl restart chronyd'
ssh root@$HOST 'systemctl enable system-trace-agent'
ssh root@$HOST 'systemctl restart system-trace-agent'

echo "✅ Step 10: Verifying deployment..."
echo ""
echo "📊 Service Status:"
ssh root@$HOST 'systemctl status snmpd --no-pager -l'
echo ""
ssh root@$HOST 'systemctl status chronyd --no-pager -l'
echo ""
ssh root@$HOST 'systemctl status system-trace-agent --no-pager -l'

echo ""
echo "🧪 Testing SNMP:"
ssh root@$HOST 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'

echo ""
echo "🕐 Checking NTP:"
ssh root@$HOST 'chronyc sources'

echo ""
echo "🌐 Testing SNMP from System Trace server:"
snmpwalk -v2c -c public $HOST 1.3.6.1.2.1.1.1.0

echo ""
echo "🎯 Deployment completed!"
echo "📋 Check System Trace dashboard: http://localhost:8001"
echo "   SNMP should show: OK · $HOST:161 responding"
echo "   NTP should show: OK · Time synchronized"
echo "   Agent should show: OK · Metrics reporting"
