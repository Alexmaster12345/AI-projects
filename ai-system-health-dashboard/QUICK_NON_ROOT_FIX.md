# 🚀 Quick Non-Root Fix for SNMP & NTP Issues

## 🎯 Current Issues
- **SNMP**: CRIT · 5000 ms · SNMP timeout
- **NTP**: UNKNOWN · no NTP response

## 🔧 Quick Fix Commands

### **SSH to centos-docker**
```bash
ssh root@192.168.50.198
```

### **One-Command Setup (Copy & Paste)**
```bash
# Create agent user and install packages
useradd -m -s /bin/bash system-trace-agent && \
dnf update -y && \
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony && \
sudo -u system-trace-agent python3 -m pip install --user psutil requests && \
mkdir -p /home/system-trace-agent/system-trace-agent && \
chown system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent

# Create agent script
cat > /home/system-trace-agent/system-trace-agent/system-trace_agent.py << 'AGENT_EOF'
#!/usr/bin/env python3
import json, time, subprocess, socket, psutil, requests, os, pwd

class NonRootSystem TraceAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = socket.gethostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30
        self.user = pwd.getpwuid(os.getuid()).pw_name
        
    def run_command_with_sudo(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            result = subprocess.run(f"sudo {command}", shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        except:
            return ""
    
    def get_system_metrics(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0,0,0]
            uptime = time.time() - psutil.boot_time() if hasattr(psutil, 'boot_time') else 0
            
            service_status = {
                'snmpd': self._check_service('snmpd'),
                'chronyd': self._check_service('chronyd'),
                'system-trace-agent': self._check_service('system-trace-agent')
            }
            
            ntp_status = self._get_ntp_status()
            
            return {
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': 'rocky',
                'user': self.user,
                'cpu': {'percent': cpu_percent, 'count': psutil.cpu_count(), 'load_avg': list(load_avg)},
                'memory': {'total': memory.total, 'available': memory.available, 'percent': memory.percent, 'used': memory.used, 'free': memory.free},
                'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free, 'percent': (disk.used/disk.total)*100},
                'network': {'bytes_sent': network.bytes_sent, 'bytes_recv': network.bytes_recv, 'packets_sent': network.packets_sent, 'packets_recv': network.packets_recv},
                'uptime': uptime,
                'processes': len(psutil.pids()),
                'services': service_status,
                'ntp': ntp_status
            }
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def _check_service(self, service_name):
        try:
            status = self.run_command_with_sudo(f"systemctl is-active {service_name}")
            return status.strip() if status else "unknown"
        except:
            return "unknown"
    
    def _get_ntp_status(self):
        try:
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
        try:
            return requests.post(f"{self.server_url}/api/agent/metrics", json=metrics, timeout=10).status_code == 200
        except:
            return False
    
    def run(self):
        print(f"System Trace Agent starting for {self.hostname} (user: {self.user})")
        while True:
            try:
                metrics = self.get_system_metrics()
                if metrics and self.send_metrics(metrics):
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Metrics sent")
                time.sleep(30)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    NonRootSystem TraceAgent().run()
AGENT_EOF

# Configure SNMP
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
agentAddress udp:161
com2sec readonly public
group MyROGroup v2c readonly
view all included .1 80
access MyROGroup "" any noauth exact all none none
sysLocation "Data Center"
sysContact "admin@example.com"
sysServices 72
load 12 10 5
SNMP_EOF

# Configure NTP
cat > /etc/chrony.conf << 'NTP_EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
NTP_EOF

# Setup sudo permissions
cat > /etc/sudoers.d/system-trace-agent << 'SUDO_EOF'
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/chronyc
system-trace-agent ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
SUDO_EOF

# Create systemd service
cat > /etc/systemd/system/system-trace-agent.service << 'SERVICE_EOF'
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

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Set permissions
chown -R system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent/
chmod +x /home/system-trace-agent/system-trace-agent/system-trace_agent.py

# Configure firewall
firewall-cmd --permanent --add-port=161/udp && \
firewall-cmd --permanent --add-port=123/udp && \
firewall-cmd --reload

# Start all services
systemctl daemon-reload && \
systemctl enable snmpd && systemctl restart snmpd && \
systemctl enable chronyd && systemctl restart chronyd && \
systemctl enable system-trace-agent && systemctl restart system-trace-agent && \
echo "✅ Non-root deployment completed!" && \
echo "" && \
echo "=== Service Status ===" && \
systemctl status snmpd --no-pager -l | head -5 && \
systemctl status chronyd --no-pager -l | head -5 && \
systemctl status system-trace-agent --no-pager -l | head -5 && \
echo "" && \
echo "=== SNMP Test ===" && \
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0 && \
echo "" && \
echo "=== NTP Test ===" && \
chronyc sources && \
echo "" && \
echo "=== Agent User ===" && \
id system-trace-agent && \
echo "" && \
echo "🎯 Check dashboard: http://localhost:8001"
```

### **Exit SSH and Test**
```bash
exit

# Test from System Trace server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0
ping -c 3 192.168.50.198
```

## 🌐 Expected Results

### **Before Fix**
```
SNMP: CRIT · 5000 ms · SNMP timeout
NTP: UNKNOWN · no NTP response
```

### **After Fix**
```
SNMP: OK · 192.168.50.198:161 responding
NTP: OK · Time synchronized
Agent: OK · Metrics reporting normally (user: system-trace-agent)
```

## 📊 Dashboard Verification

Open: http://localhost:8001

Look for:
- ✅ SNMP status green
- ✅ NTP status green  
- ✅ Agent metrics appearing
- ✅ User shown as "system-trace-agent"

## ⏱️ Expected Timeline

- **Setup**: 5-8 minutes
- **Verification**: 1-2 minutes
- **Total**: 7-10 minutes

---

**Copy and paste the one-command setup above to fix all SNMP and NTP issues!** 🚀
