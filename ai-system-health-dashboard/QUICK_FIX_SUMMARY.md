# 🔧 Quick Fix Summary for SNMP & NTP Issues

## 🎯 Current Issues
- **SNMP**: High resource usage (agent reachability) - CRIT · 5000 ms · SNMP timeout
- **NTP**: Clock skew / NTP server reachability (udp/123)

## 🚀 One-Command Solution

Execute this script to fix all issues:

```bash
# SSH to centos-docker and run the fix
ssh root@192.168.50.198
```

Then run these commands on centos-docker:

```bash
# Quick fix commands (run all at once)
dnf update -y && \
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony && \
python3 -m pip install psutil requests && \
mkdir -p /opt/ashd-agent && \
cat > /opt/ashd-agent/ashd_agent.py << 'AGENT_EOF'
#!/usr/bin/env python3
import json, time, socket, psutil, requests, os

class ASHDAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = socket.gethostname()
        self.agent_id = f"{self.hostname}-{int(time.time())}"
        self.metrics_interval = 30
        
    def get_system_metrics(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0,0,0]
            uptime = time.time() - psutil.boot_time() if hasattr(psutil, 'boot_time') else 0
            
            return {
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': 'rocky',
                'cpu': {'percent': cpu_percent, 'count': psutil.cpu_count(), 'load_avg': list(load_avg)},
                'memory': {'total': memory.total, 'available': memory.available, 'percent': memory.percent, 'used': memory.used, 'free': memory.free},
                'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free, 'percent': (disk.used/disk.total)*100},
                'network': {'bytes_sent': network.bytes_sent, 'bytes_recv': network.bytes_recv, 'packets_sent': network.packets_sent, 'packets_recv': network.packets_recv},
                'uptime': uptime,
                'processes': len(psutil.pids())
            }
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def send_metrics(self, metrics):
        try:
            return requests.post(f"{self.server_url}/api/agent/metrics", json=metrics, timeout=10).status_code == 200
        except:
            return False
    
    def run(self):
        print(f"ASHD Agent starting for {self.hostname}")
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
    ASHDAgent().run()
AGENT_EOF

chmod +x /opt/ashd-agent/ashd_agent.py && \
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
agentAddress udp:161
com2sec readonly  public
group MyROGroup v2c readonly
view all included .1 80
access MyROGroup "" any noauth exact all none none
sysLocation "Data Center"
sysContact "admin@example.com"
sysServices 72
load 12 10 5
SNMP_EOF

cat > /etc/chrony.conf << 'NTP_EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
NTP_EOF

cat > /etc/systemd/system/ashd-agent.service << 'SERVICE_EOF'
[Unit]
Description=ASHD Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ashd-agent
ExecStart=/usr/bin/python3 /opt/ashd-agent/ashd_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

firewall-cmd --permanent --add-port=161/udp && \
firewall-cmd --permanent --add-port=123/udp && \
firewall-cmd --reload && \
systemctl daemon-reload && \
systemctl enable snmpd && systemctl restart snmpd && \
systemctl enable chronyd && systemctl restart chronyd && \
systemctl enable ashd-agent && systemctl restart ashd-agent && \
echo "✅ Deployment completed!" && \
systemctl status snmpd --no-pager -l && \
systemctl status chronyd --no-pager -l && \
systemctl status ashd-agent --no-pager -l && \
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0 && \
chronyc sources
```

## 🌐 Verify Fix

After running the commands, exit SSH and test:

```bash
# Test SNMP from ASHD server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0

# Check dashboard
http://localhost:8001
```

## 📊 Expected Results

**Before Fix:**
```
SNMP: CRIT · 5000 ms · SNMP timeout
NTP: Clock skew / NTP server reachability (udp/123)
```

**After Fix:**
```
SNMP: OK · 192.168.50.198:161 responding
NTP: OK · Time synchronized
Agent: OK · Metrics reporting normally
```

## 🎯 Success Indicators

✅ SNMP responds to queries  
✅ NTP shows synchronized time sources  
✅ Agent service is active  
✅ Dashboard shows green status for all protocols  
✅ System metrics appear in dashboard  

---

**Execute the SSH command above to fix all SNMP and NTP issues! 🚀**
