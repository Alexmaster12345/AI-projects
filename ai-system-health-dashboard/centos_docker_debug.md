# CentOS-Docker Host Debug and Setup Guide

## Current Status
- **Host**: centos-docker (192.168.50.198)
- **Issues**: SNMP (161/udp), Syslog (514/udp), NetFlow (2055/udp) - all CRITICAL
- **Host Type**: Auto-discovered VM (VMware MAC: 00:0c:29:c4:f0:c7)

## Manual Setup Instructions

### Step 1: Access the Host
Since SSH requires password authentication, you'll need to:
1. Access the host console directly (VMware console, etc.)
2. Or configure SSH key authentication
3. Or use the root password if you know it

### Step 2: Install ASHD Agent
Once you have root access on the centos-docker host:

```bash
# Create deployment directory
mkdir -p /tmp/ashd-deploy

# Install dependencies
yum update -y
yum install -y python3 python3-pip python3-psutil python3-requests

# Create agent user
useradd -r -s /bin/false -d /opt/ashd-agent ashd-agent

# Create directories
mkdir -p /opt/ashd-agent
mkdir -p /var/lib/ashd-agent
mkdir -p /var/log/ashd-agent

# Create agent script
cat > /opt/ashd-agent/agent.py << 'AGENT_SCRIPT'
#!/usr/bin/env python3
import json
import time
import socket
import psutil
import requests

SERVER_URL = "http://192.168.50.1:8000"  # Update to your dashboard IP
HOSTNAME = socket.gethostname()
INTERVAL = 30

def collect_metrics():
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

def main():
    print(f"ASHD Agent starting for {HOSTNAME}")
    print(f"Server: {SERVER_URL}")
    
    while True:
        try:
            metrics = collect_metrics()
            response = requests.post(f"{SERVER_URL}/api/agent/report", json=metrics, timeout=10)
            if response.status_code == 200:
                print(f"Metrics sent successfully: {response.status_code}")
            else:
                print(f"Failed to send metrics: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
AGENT_SCRIPT

chmod +x /opt/ashd-agent/agent.py

# Create systemd service
cat > /etc/systemd/system/ashd-agent.service << 'SERVICE'
[Unit]
Description=ASHD Metrics Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/ashd-agent/agent.py
Restart=on-failure
RestartSec=10
User=ashd-agent
Group=ashd-agent
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

# Set permissions
chown -R ashd-agent:ashd-agent /opt/ashd-agent
chown -R ashd-agent:ashd-agent /var/lib/ashd-agent
chown -R ashd-agent:ashd-agent /var/log/ashd-agent

# Enable and start service
systemctl daemon-reload
systemctl enable ashd-agent
systemctl start ashd-agent

# Check status
systemctl status ashd-agent
```

### Step 3: Enable SNMP Service

```bash
# Install SNMP
yum install -y net-snmp net-snmp-utils

# Configure SNMP
cat > /etc/snmp/snmpd.conf << 'SNMP_CONF'
com2sec local     localhost       public
group   MyROGroup v2c        local
view    all      included  .1
access  MyROGroup ""      any       noauth    exact  all  none none
syslocation "Data Center"
syscontact admin@example.com
SNMP_CONF

# Configure firewall
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=161/udp
    firewall-cmd --reload
else
    iptables -A INPUT -p udp --dport 161 -j ACCEPT
fi

# Enable and start SNMP
systemctl enable snmpd
systemctl start snmpd

# Test SNMP
snmpwalk -v2c -c public localhost sysName.0
```

### Step 4: Enable Syslog Service

```bash
# Configure rsyslog to receive remote logs
sed -i 's/#\$ModLoad imudp/\$ModLoad imudp/' /etc/rsyslog.conf
sed -i 's/#\$UDPServerRun 514/\$UDPServerRun 514/' /etc/rsyslog.conf

# Configure firewall
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=514/udp
    firewall-cmd --reload
else
    iptables -A INPUT -p udp --dport 514 -j ACCEPT
fi

# Restart rsyslog
systemctl restart rsyslog

# Test syslog listener
netstat -uln | grep :514
```

### Step 5: Enable NetFlow (Optional)

```bash
# Install EPEL and fprobe
yum install -y epel-release
yum install -y fprobe

# Configure fprobe
cat > /etc/fprobe.conf << 'FPROBE_CONF'
COLLECTOR_IP="127.0.0.1"
COLLECTOR_PORT="2055"
INTERFACE="eth0"
VERSION="5"
FPROBE_CONF

# Configure firewall
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=2055/udp
    firewall-cmd --reload
else
    iptables -A INPUT -p udp --dport 2055 -j ACCEPT
fi

# Create systemd service
cat > /etc/systemd/system/fprobe.service << 'FPROBE_SERVICE'
[Unit]
Description=NetFlow Probe
After=network.target

[Service]
ExecStart=/usr/sbin/fprobe -ieth0 -fudp:$COLLECTOR_IP:$COLLECTOR_PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
FPROBE_SERVICE

systemctl daemon-reload
systemctl enable fprobe
systemctl start fprobe
```

### Step 6: Verify Services

```bash
# Check all services
systemctl status ashd-agent snmpd rsyslog fprobe

# Check ports
netstat -uln | grep -E ":(161|514|2055)"

# Test SNMP
snmpwalk -v2c -c public localhost sysName.0

# Check agent logs
tail -f /var/log/ashd-agent/agent.log
```

## Troubleshooting

### If Services Still Show CRITICAL:

1. **Check Firewall**: Ensure ports are open on both the host and any network firewalls
2. **Check SELinux**: May need to allow services through SELinux
   ```bash
   setsebool -P snmpd_connect_anon on
   ```
3. **Check Network**: Verify connectivity between host and dashboard
4. **Check Agent Logs**: Look for errors in `/var/log/ashd-agent/`

### Alternative: Manual Port Check

If automated checks fail, you can manually verify:
```bash
# From the centos-docker host
nc -u -l 161 &  # SNMP
nc -u -l 514 &  # Syslog  
nc -u -l 2055 & # NetFlow

# From the dashboard host
nc -u 192.168.50.198 161
nc -u 192.168.50.198 514
nc -u 192.168.50.198 2055
```

## Expected Results

After setup:
- **ASHD Agent**: Should report CPU, memory, disk, network metrics to dashboard
- **SNMP**: Should show "OK" status in dashboard
- **Syslog**: Should show "OK" status in dashboard  
- **NetFlow**: Should show "OK" status in dashboard (if fprobe is installed)

The dashboard should start receiving detailed metrics from the centos-docker host within 30-60 seconds of agent startup.
