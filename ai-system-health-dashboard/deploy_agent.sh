#!/bin/bash

# ASHD Agent Deployment Script for centos-docker host
# This script will deploy and configure the ASHD agent to monitor system metrics

set -e

HOST="192.168.50.198"
DASHBOARD_SERVER="http://192.168.50.1:8000"  # Update this to your dashboard IP
AGENT_USER="ashd-agent"
AGENT_DIR="/opt/ashd-agent"

echo "=== ASHD Agent Deployment for centos-docker ($HOST) ==="

# Create deployment package
echo "Creating agent deployment package..."
mkdir -p /tmp/ashd-deploy
cp agent_fedora.py /tmp/ashd-deploy/
cp ashd-agent.service /tmp/ashd-deploy/
cat > /tmp/ashd-deploy/install.sh << 'EOF'
#!/bin/bash

# Install ASHD agent on CentOS/RHEL
set -e

echo "Installing ASHD agent dependencies..."
yum update -y
yum install -y python3 python3-pip python3-psutil python3-requests

# Create agent user
echo "Creating ashd-agent user..."
useradd -r -s /bin/false -d /opt/ashd-agent ashd-agent 2>/dev/null || true

# Create agent directory
echo "Creating agent directory..."
mkdir -p /opt/ashd-agent
mkdir -p /var/lib/ashd-agent
mkdir -p /var/log/ashd-agent

# Install agent files
echo "Installing agent files..."
cp agent_fedora.py /opt/ashd-agent/
chmod +x /opt/ashd-agent/agent_fedora.py

# Install systemd service
echo "Installing systemd service..."
cp ashd-agent.service /etc/systemd/system/
systemctl daemon-reload

# Configure agent
echo "Configuring agent..."
mkdir -p /etc/ashd-agent
cat > /etc/ashd-agent/config.json << CONFIG
{
    "server": "DASHBOARD_SERVER_PLACEHOLDER",
    "interval": 30,
    "hostname": "$(hostname)",
    "tags": ["centos", "docker", "monitored", "new-tag"]
}
CONFIG

# Replace placeholder with actual server
sed -i "s|DASHBOARD_SERVER_PLACEHOLDER|$DASHBOARD_SERVER|g" /etc/ashd-agent/config.json

# Set permissions
echo "Setting permissions..."
chown -R ashd-agent:ashd-agent /opt/ashd-agent
chown -R ashd-agent:ashd-agent /var/lib/ashd-agent
chown -R ashd-agent:ashd-agent /var/log/ashd-agent
chown -R ashd-agent:ashd-agent /etc/ashd-agent

# Enable and start service
echo "Enabling and starting ASHD agent..."
systemctl enable ashd-agent
systemctl start ashd-agent

# Check status
echo "Checking agent status..."
systemctl status ashd-agent --no-pager

echo "=== Agent installation complete! ==="
echo "Check dashboard for incoming metrics from $(hostname)"
EOF

# Update the install script with the correct server URL
sed -i "s|DASHBOARD_SERVER_PLACEHOLDER|$DASHBOARD_SERVER|g" /tmp/ashd-deploy/install.sh

# Create a script to enable SNMP, Syslog, and NetFlow monitoring
cat > /tmp/ashd-deploy/enable_services.sh << 'EOF'
#!/bin/bash

# Enable monitoring services on CentOS/RHEL
set -e

echo "=== Enabling SNMP, Syslog, and NetFlow monitoring ==="

# Install required packages
echo "Installing monitoring packages..."
yum update -y
yum install -y net-snmp net-snmp-utils rsyslog

# Configure SNMP
echo "Configuring SNMP..."
cat > /etc/snmp/snmpd.conf << SNMP_CONFIG
com2sec local     localhost       public
group   MyROGroup v2c        local
view    all      included  .1
access  MyROGroup ""      any       noauth    exact  all  none none
syslocation "Data Center"
syscontact admin@example.com
SNMP_CONFIG

# Configure firewall for SNMP
echo "Configuring firewall for SNMP..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=161/udp
    firewall-cmd --reload
else
    iptables -A INPUT -p udp --dport 161 -j ACCEPT
    iptables-save > /etc/sysconfig/iptables 2>/dev/null || true
fi

# Start and enable SNMP
systemctl enable snmpd
systemctl start snmpd

# Configure Syslog to receive remote logs
echo "Configuring Syslog..."
sed -i 's/#\$ModLoad imudp/\$ModLoad imudp/' /etc/rsyslog.conf
sed -i 's/#\$UDPServerRun 514/\$UDPServerRun 514/' /etc/rsyslog.conf

# Configure firewall for Syslog
echo "Configuring firewall for Syslog..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=514/udp
    firewall-cmd --reload
else
    iptables -A INPUT -p udp --dport 514 -j ACCEPT
    iptables-save > /etc/sysconfig/iptables 2>/dev/null || true
fi

# Restart Syslog
systemctl restart rsyslog

# Install and configure NetFlow (using fprobe)
echo "Installing NetFlow collector..."
yum install -y epel-release
yum install -y fprobe || echo "fprobe not available, skipping NetFlow"

if command -v fprobe &> /dev/null; then
    # Configure fprobe for NetFlow
    cat > /etc/fprobe.conf << FPROBE_CONFIG
# fprobe configuration
# Replace with your NetFlow collector IP
COLLECTOR_IP="127.0.0.1"
COLLECTOR_PORT="2055"

# Interface to monitor
INTERFACE="eth0"

# NetFlow version
VERSION="5"
FPROBE_CONFIG

    # Configure firewall for NetFlow
    echo "Configuring firewall for NetFlow..."
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=2055/udp
        firewall-cmd --reload
    else
        iptables -A INPUT -p udp --dport 2055 -j ACCEPT
        iptables-save > /etc/sysconfig/iptables 2>/dev/null || true
    fi

    # Create systemd service for fprobe
    cat > /etc/systemd/system/fprobe.service << FPROBE_SERVICE
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
else
    echo "NetFlow collector (fprobe) not available. You may need to install it manually."
fi

echo "=== Service configuration complete! ==="
echo "Testing SNMP..."
snmpwalk -v2c -c public localhost sysName.0 2>/dev/null || echo "SNMP test failed"

echo "Testing Syslog listener..."
netstat -uln | grep :514 || echo "Syslog port 514 not listening"

echo "Testing NetFlow..."
netstat -uln | grep :2055 || echo "NetFlow port 2055 not listening"

echo "=== Services enabled! ==="
EOF

chmod +x /tmp/ashd-deploy/install.sh
chmod +x /tmp/ashd-deploy/enable_services.sh

echo "Deployment package created in /tmp/ashd-deploy/"
echo ""
echo "To deploy to centos-docker host, you need to:"
echo "1. Copy the package to the host:"
echo "   scp -r /tmp/ashd-deploy/ root@$HOST:/tmp/"
echo ""
echo "2. SSH to the host and run:"
echo "   ssh root@$HOST"
echo "   cd /tmp/ashd-deploy"
echo "   ./install.sh"
echo "   ./enable_services.sh"
echo ""
echo "3. Check the dashboard for incoming metrics"
echo ""
echo "Note: You'll need SSH access to the centos-docker host with root privileges."
