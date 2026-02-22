#!/bin/bash
# ASHD Agent Deployment Script for Debian

set -e

echo "🚀 Deploying ASHD Agent for Debian"
echo "=========================================="

# Variables
AGENT_DIR="/opt/ashd-agent"
SERVICE_NAME="ashd-agent"
SERVER_URL="http://192.168.50.225:8001"

echo "📦 Installing dependencies..."

# Update package manager
if command -v apt >/dev/null 2>&1; then
    apt update -y
fi

# Install required packages
apt install -y \
    python3 \
    python3-pip \
    snmpd \
    ntp \
    curl \
    wget

# Install Python dependencies
python3 -m pip install psutil requests

echo "📁 Creating agent directory..."
mkdir -p $AGENT_DIR

echo "📝 Copying agent files..."
# These files will be copied during deployment
cp ashd_agent.py $AGENT_DIR/
cp ashd-agent.service /etc/systemd/system/

echo "🔧 Configuring SNMP..."
# Backup original SNMP config
if [ -f /etc/snmp/snmpd.conf ]; then
    cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup
fi

# Install new SNMP config
cp snmpd.conf /etc/snmp/

echo "⏰ Configuring NTP..."
# Configure NTP service
if [ "debian" = "ubuntu" ] || [ "debian" = "debian" ]; then
    # Ubuntu/Debian NTP configuration
    if ! grep -q "pool.ntp.org" /etc/ntp.conf 2>/dev/null; then
        echo "server pool.ntp.org iburst" >> /etc/ntp.conf
    fi
else
    # RHEL/CentOS/Rocky chrony configuration
    if ! grep -q "pool.ntp.org" /etc/chrony.conf 2>/dev/null; then
        echo "pool pool.ntp.org iburst" >> /etc/chrony.conf
    fi
fi

echo "🔥 Configuring firewall..."
# Open SNMP port
if command -v ufw >/dev/null 2>&1; then
    if [ "ufw" = "ufw" ]; then
        ufw allow 161/udp comment "SNMP"
        ufw allow 123/udp comment "NTP"
    else
        firewall-cmd --permanent --add-port=161/udp
        firewall-cmd --permanent --add-port=123/udp
        firewall-cmd --reload
    fi
fi

echo "🔄 Starting services..."
# Enable and start services
systemctl enable snmpd
systemctl restart snmpd

systemctl enable ntp
systemctl restart ntp

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "✅ Deployment completed!"
echo ""
echo "📊 Service Status:"
systemctl status snmpd
systemctl status ntp
systemctl status $SERVICE_NAME

echo ""
echo "🧪 Testing SNMP:"
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

echo ""
echo "🕐 Checking NTP:"
if command -v ntpq >/dev/null 2>&1; then
    ntpq -p
else
    chronyc sources
fi

echo ""
echo "📋 Agent logs:"
journalctl -u $SERVICE_NAME -f
