#!/bin/bash
# ASHD Agent Deployment Script for Rocky (Non-Root Version)

set -e

AGENT_USER="ashd-agent"
AGENT_DIR="/home/$AGENT_USER/ashd-agent"
SERVICE_NAME="ashd-agent"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root for initial setup"
    echo "Please run: sudo $0"
    exit 1
fi

echo "🚀 Deploying ASHD Agent for Rocky (Non-Root)"
echo "=================================================="

echo "📋 Step 1: Creating agent user..."
if ! id "$AGENT_USER" &>/dev/null; then
    useradd -m -s /bin/bash $AGENT_USER
    print_status "Created user: $AGENT_USER"
else
    print_status "User $AGENT_USER already exists"
fi

echo "📦 Step 2: Installing system packages..."

dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony


echo "🐍 Step 3: Installing Python dependencies..."
python3 -m pip install --user psutil requests

echo "📁 Step 4: Creating agent directory..."
mkdir -p "$AGENT_DIR"
chown $AGENT_USER:$AGENT_USER "$AGENT_DIR"

echo "📝 Step 5: Copying agent files..."
cp ashd_agent_non_root.py "$AGENT_DIR/ashd_agent.py"
chown $AGENT_USER:$AGENT_USER "$AGENT_DIR/ashd_agent.py"
chmod +x "$AGENT_DIR/ashd_agent.py"

echo "⚙️  Step 6: Configuring SNMP..."
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'EOF'
# ASHD SNMP Configuration
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

echo "⏰ Step 7: Configuring NTP..."
if [ "rocky" = "ubuntu" ] || [ "rocky" = "debian" ]; then
    # Ubuntu/Debian NTP
    [ -f /etc/ntp.conf ] && cp /etc/ntp.conf /etc/ntp.conf.backup
    echo "server pool.ntp.org iburst" >> /etc/ntp.conf
else
    # RHEL/CentOS/Rocky chrony
    [ -f /etc/chrony.conf ] && cp /etc/chrony.conf /etc/chrony.conf.backup
    cat > /etc/chrony.conf << 'EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
EOF
fi

echo "🔥 Step 8: Configuring firewall..."

firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload


echo "🔐 Step 9: Setting up sudo permissions..."
cat > /etc/sudoers.d/ashd-agent << 'EOF'
# ASHD Agent sudo permissions
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/chronyc
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/ntpq
ashd-agent ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF

echo "🔄 Step 10: Creating systemd service..."
cat > /etc/systemd/system/ashd-agent.service << EOF
[Unit]
Description=ASHD Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User=ashd-agent
Group=ashd-agent
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 $AGENT_DIR/ashd_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "🚀 Step 11: Starting services..."
systemctl daemon-reload
systemctl enable snmpd
systemctl restart snmpd
systemctl enable chronyd
systemctl restart chronyd
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "✅ Step 12: Setting up log rotation..."
mkdir -p /var/log/ashd-agent
chown $AGENT_USER:$AGENT_USER /var/log/ashd-agent

cat > /etc/logrotate.d/ashd-agent << EOF
/var/log/ashd-agent/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ashd-agent ashd-agent
}
EOF

echo "🔍 Step 13: Verifying deployment..."
echo ""
print_status "Service Status:"
systemctl status snmpd --no-pager -l | head -5
systemctl status chronyd --no-pager -l | head -5
systemctl status $SERVICE_NAME --no-pager -l | head -5

echo ""
print_status "SNMP Test:"
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0 2>/dev/null || print_warning "SNMP test failed"

echo ""
print_status "NTP Test:"
if command -v chronyc &>/dev/null; then
    chronyc sources | head -5
else
    ntpq -p | head -5
fi

echo ""
print_status "Agent Test:"
sudo -u $AGENT_USER python3 $AGENT_DIR/ashd_agent.py &
AGENT_PID=$!
sleep 3
kill $AGENT_PID 2>/dev/null || true
print_status "Agent test completed"

echo ""
echo "🎯 Deployment completed successfully!"
echo ""
echo "📋 Agent Information:"
echo "- User: $AGENT_USER"
echo "- Home: /home/$AGENT_USER"
echo "- Agent: $AGENT_DIR/ashd_agent.py"
echo "- Logs: journalctl -u ashd-agent -f"
echo ""
echo "🔧 Management Commands:"
echo "- Restart: systemctl restart ashd-agent"
echo "- Status: systemctl status ashd-agent"
echo "- Logs: journalctl -u ashd-agent -f"
echo "- Test: sudo -u $AGENT_USER python3 $AGENT_DIR/ashd_agent.py"
echo ""
echo "🌐 Check ASHD dashboard: http://localhost:8001"
