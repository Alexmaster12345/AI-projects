# 🔧 Manual Non-Root Agent Deployment - SNMP & NTP Fix

## 🎯 Issues to Resolve
- **SNMP**: High resource usage (agent reachability) - CRIT · 5000 ms · SNMP timeout
- **NTP**: Clock skew / NTP server reachability (udp/123) - UNKNOWN · no NTP response

## 🚀 Step-by-Step Manual Deployment

### **Step 1: SSH to centos-docker**
```bash
ssh root@192.168.50.198
```

### **Step 2: Create Non-Root Agent User**
```bash
# Create dedicated agent user
useradd -m -s /bin/bash system-trace-agent

# Verify user creation
id system-trace-agent
ls -la /home/system-trace-agent/
```

### **Step 3: Install Required Packages**
```bash
# Update system packages
dnf update -y

# Install monitoring packages
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony

# Install Python dependencies for agent user
sudo -u system-trace-agent python3 -m pip install --user psutil requests
```

### **Step 4: Create Agent Directory**
```bash
# Create agent home directory
mkdir -p /home/system-trace-agent/system-trace-agent
chown system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent
```

### **Step 5: Deploy Non-Root Agent**
```bash
# Create the non-root agent script
cat > /home/system-trace-agent/system-trace-agent/system-trace_agent.py << 'EOF'
#!/usr/bin/env python3
"""
System Trace Monitoring Agent (Non-Root Version)
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

class NonRootSystem TraceAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = socket.gethostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30
        self.user = pwd.getpwuid(os.getuid()).pw_name
        
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
                'chronyd': self._check_service('chronyd'),
                'system-trace-agent': self._check_service('system-trace-agent')
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
        except:
            pass
        return {'status': 'unknown'}
    
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
        print(f"System Trace Agent starting for {self.hostname} (user: {self.user})")
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
    agent = NonRootSystem TraceAgent()
    agent.run()
EOF

# Set permissions
chown system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent/system-trace_agent.py
chmod +x /home/system-trace-agent/system-trace-agent/system-trace_agent.py
```

### **Step 6: Configure SNMP**
```bash
# Backup original SNMP config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP configuration
cat > /etc/snmp/snmpd.conf << 'EOF'
# System Trace SNMP Configuration
agentAddress udp:161
com2sec readonly public
group MyROGroup v2c readonly
view all included .1 80
access MyROGroup "" any noauth exact all none none
sysLocation "Data Center"
sysContact "admin@example.com"
sysServices 72
load 12 10 5
EOF
```

### **Step 7: Configure NTP**
```bash
# Backup original chrony config
[ -f /etc/chrony.conf ] && cp /etc/chrony.conf /etc/chrony.conf.backup

# Create new chrony configuration
cat > /etc/chrony.conf << 'EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
EOF
```

### **Step 8: Configure Firewall**
```bash
# Open SNMP and NTP ports
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
```

### **Step 9: Setup Sudo Permissions**
```bash
# Create sudoers file for agent user
cat > /etc/sudoers.d/system-trace-agent << 'EOF'
# System Trace Agent sudo permissions
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/chronyc
system-trace-agent ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF
```

### **Step 10: Create Systemd Service**
```bash
# Create systemd service for non-root agent
cat > /etc/systemd/system/system-trace-agent.service << 'EOF'
[Unit]
Description=System Trace Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User=system-trace-agent
Group=system-trace-agent
WorkingDirectory=/home/system-trace-agent/system-trace-agent
ExecStart=/usr/bin/python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### **Step 11: Start All Services**
```bash
# Reload systemd and start services
systemctl daemon-reload
systemctl enable snmpd
systemctl restart snmpd
systemctl enable chronyd
systemctl restart chronyd
systemctl enable system-trace-agent
systemctl restart system-trace-agent
```

### **Step 12: Verify Deployment**
```bash
# Check service status
echo "=== Service Status ==="
systemctl status snmpd --no-pager -l | head -5
systemctl status chronyd --no-pager -l | head -5
systemctl status system-trace-agent --no-pager -l | head -5

echo ""
echo "=== SNMP Test ==="
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

echo ""
echo "=== NTP Test ==="
chronyc sources

echo ""
echo "=== Agent User Test ==="
id system-trace-agent
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py &
AGENT_PID=$!
sleep 3
kill $AGENT_PID 2>/dev/null || true
echo "Agent test completed"
```

### **Step 13: Exit SSH and Test from System Trace Server**
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

**Expected Results After Non-Root Deployment:**
```
SNMP: OK · 192.168.50.198:161 responding
NTP: OK · Time synchronized
Agent: OK · Metrics reporting normally (user: system-trace-agent)
ICMP: OK · 192.168.50.198 responding
```

## 🔍 Troubleshooting

### **If SNMP Still Fails**
```bash
# On centos-docker
ssh root@192.168.50.198

# Check SNMP service
systemctl status snmpd

# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check firewall
firewall-cmd --list-all | grep 161
```

### **If NTP Still Fails**
```bash
# On centos-docker
ssh root@192.168.50.198

# Check NTP service
systemctl status chronyd

# Check NTP sources
chronyc sources

# Force NTP sync
chronyc -a makestep
```

### **If Agent Fails**
```bash
# On centos-docker
ssh root@192.168.50.198

# Check agent service
systemctl status system-trace-agent

# Check agent logs
journalctl -u system-trace-agent -f

# Test agent manually
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py
```

## 📊 Expected Timeline

- **Steps 1-3**: 3-4 minutes (user creation and package installation)
- **Steps 4-11**: 3-4 minutes (configuration and setup)
- **Step 12**: 1-2 minutes (verification)
- **Total Time**: 7-10 minutes

## 🎯 Success Indicators

✅ **SNMP Test**: `snmpwalk` returns system information  
✅ **NTP Test**: `chronyc sources` shows time servers  
✅ **Agent Test**: `systemctl status system-trace-agent` shows active  
✅ **Dashboard**: All protocols show green status  
✅ **User Context**: Metrics show "user": "system-trace-agent"  
✅ **Security**: Agent runs as non-root user  

---

**Execute these manual steps to resolve SNMP timeout and NTP issues with non-root agent deployment!** 🚀
