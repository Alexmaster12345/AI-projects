# 🔧 Manual Fix Guide for SNMP and NTP Issues

## 🎯 Issues to Resolve

- **SNMP**: High resource usage (agent reachability) - CRIT · 5000 ms · SNMP timeout
- **NTP**: Clock skew / NTP server reachability (udp/123)

## 🚀 Quick Manual Deployment

Execute these commands step by step to fix the issues:

### **Step 1: SSH to centos-docker**
```bash
ssh root@192.168.50.198
```

### **Step 2: Install Required Packages**
```bash
dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony
```

### **Step 3: Install Python Dependencies**
```bash
python3 -m pip install psutil requests
```

### **Step 4: Create Agent Directory**
```bash
mkdir -p /opt/system-trace-agent
```

### **Step 5: Create System Trace Agent**
```bash
cat > /opt/system-trace-agent/system-trace_agent.py << 'EOF'
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

chmod +x /opt/system-trace-agent/system-trace_agent.py
```

### **Step 6: Configure SNMP**
```bash
cat > /etc/snmp/snmpd.conf << 'EOF'
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
```

### **Step 7: Configure NTP**
```bash
cat > /etc/chrony.conf << 'EOF'
# Use public servers from the pool.ntp.org project.
pool pool.ntp.org iburst

# Record the rate at which the system clock gains/loses time.
driftfile /var/lib/chrony/drift

# Allow NTP client access from local network.
allow 192.168.0.0/16

# Serve time even if not synchronized to a time source.
local stratum 10
EOF
```

### **Step 8: Configure Firewall**
```bash
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
```

### **Step 9: Create Systemd Service**
```bash
cat > /etc/systemd/system/system-trace-agent.service << 'EOF'
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
```

### **Step 10: Start All Services**
```bash
systemctl daemon-reload
systemctl enable snmpd
systemctl restart snmpd
systemctl enable chronyd
systemctl restart chronyd
systemctl enable system-trace-agent
systemctl restart system-trace-agent
```

### **Step 11: Verify Deployment**
```bash
# Check service status
systemctl status snmpd
systemctl status chronyd
systemctl status system-trace-agent

# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check NTP
chronyc sources
```

### **Step 12: Exit and Test from System Trace Server**
```bash
exit
```

Now test from the System Trace server:
```bash
# Test SNMP from System Trace server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0

# Test ICMP
ping -c 3 192.168.50.198
```

## 🌐 Verify on Dashboard

Open the System Trace dashboard:
```
http://localhost:8001
```

**Expected Results:**
- **SNMP**: OK · 192.168.50.198:161 responding
- **NTP**: OK · Time synchronized  
- **Agent**: OK · Metrics reporting normally
- **ICMP**: OK · 192.168.50.198 responding

## 🔍 Troubleshooting

### **If SNMP Still Fails**
```bash
# Check SNMP service
systemctl status snmpd

# Check SNMP configuration
cat /etc/snmp/snmpd.conf

# Check firewall
firewall-cmd --list-all | grep 161

# Test SNMP manually
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0
```

### **If NTP Still Fails**
```bash
# Check NTP service
systemctl status chronyd

# Check NTP configuration
cat /etc/chrony.conf

# Force NTP sync
chronyc -a makestep

# Check NTP sources
chronyc sources
```

### **If Agent Fails**
```bash
# Check agent service
systemctl status system-trace-agent

# Check agent logs
journalctl -u system-trace-agent -f

# Test agent manually
python3 /opt/system-trace-agent/system-trace_agent.py
```

## 🎯 Expected Timeline

- **Steps 1-3**: 2-3 minutes (package installation)
- **Steps 4-10**: 2-3 minutes (configuration)
- **Steps 11-12**: 1-2 minutes (verification)
- **Total Time**: 5-8 minutes

## 📊 Success Indicators

✅ **SNMP Test**: `snmpwalk` returns system information  
✅ **NTP Test**: `chronyc sources` shows time servers  
✅ **Agent Test**: `systemctl status system-trace-agent` shows active  
✅ **Dashboard**: All protocols show green status  
✅ **Metrics**: System data appearing in dashboard  

---

**Execute these steps manually to resolve the SNMP timeout and NTP reachability issues!** 🚀
