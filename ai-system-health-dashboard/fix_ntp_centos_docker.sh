#!/bin/bash
# NTP Configuration Fix for CentOS-Docker

set -e

echo "🕐 Configuring NTP for CentOS-Docker..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Install NTP
echo "📦 Installing NTP..."
dnf install -y ntp

# Configure NTP servers
echo "🔧 Configuring NTP servers..."
cat > /etc/ntp.conf << 'EOF'
# NTP Configuration for ASHD
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server 2.pool.ntp.org iburst
server 3.pool.ntp.org iburst

# Local clock as fallback
server 127.127.1.0
fudge  127.127.1.0 stratum 10

# Security
restrict default nomodify notrap nopeer noquery
restrict 127.0.0.1
restrict ::1

# Logging
driftfile /var/lib/ntp/drift
logfile /var/log/ntp.log
EOF

# Enable and start NTP service
echo "🚀 Starting NTP service..."
systemctl enable ntpd
systemctl start ntpd

# Open firewall for NTP
echo "🔥 Configuring firewall for NTP..."
firewall-cmd --permanent --add-service=ntp
firewall-cmd --reload

# Force NTP sync
echo "🔄 Forcing NTP synchronization..."
ntpdate -u pool.ntp.org
systemctl restart ntpd

# Check NTP status
echo "📊 NTP Status:"
ntpq -p

echo "✅ NTP configuration complete!"
