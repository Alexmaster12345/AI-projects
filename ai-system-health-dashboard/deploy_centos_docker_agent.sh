#!/bin/bash
# System Trace Agent Deployment for CentOS-Docker

set -e

echo "🐧 Deploying System Trace Agent on CentOS-Docker..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils

# Configure SNMP service
echo "🔧 Configuring SNMP service..."
cat > /etc/snmp/snmpd.conf << 'EOF'
# SNMP Configuration for System Trace Monitoring
rocommunity public
syslocation "Data Center"
syscontact "admin@example.com"
dontLogTCPwrappersConnects
EOF

# Enable and start SNMP service
echo "🚀 Starting SNMP service..."
systemctl enable snmpd
systemctl start snmpd
systemctl status snmpd

# Open firewall for SNMP
echo "🔥 Configuring firewall..."
firewall-cmd --permanent --add-service=snmp
firewall-cmd --reload

# Create System Trace agent directory
echo "📁 Creating agent directory..."
mkdir -p /opt/system-trace-agent
cd /opt/system-trace-agent

# Create simple agent script
cat > system-trace_agent.py << 'EOF'
#!/usr/bin/env python3
import subprocess
import json
import time
import psutil

def get_system_metrics():
    metrics = {
        'timestamp': time.time(),
        'hostname': subprocess.check_output(['hostname'], text=True).strip(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
        'network_interfaces': len(psutil.net_if_addrs()),
        'processes': len(psutil.pids())
    }
    return metrics

def main():
    print("🤖 System Trace Agent starting...")
    
    while True:
        try:
            metrics = get_system_metrics()
            print(json.dumps(metrics))
            time.sleep(30)
        except KeyboardInterrupt:
            print("🛑 Agent stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
EOF

chmod +x system-trace_agent.py

# Create systemd service for agent
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

[Install]
WantedBy=multi-user.target
EOF

# Enable and start agent service
echo "🚀 Starting System Trace agent..."
systemctl daemon-reload
systemctl enable system-trace-agent
systemctl start system-trace-agent
systemctl status system-trace-agent

# Test SNMP
echo "🧪 Testing SNMP..."
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

echo "✅ System Trace Agent deployment complete!"
echo "📊 Agent metrics: /opt/system-trace-agent/system-trace_agent.py"
echo "🔧 SNMP service: systemctl status snmpd"
echo "🤖 Agent service: systemctl status system-trace-agent"
