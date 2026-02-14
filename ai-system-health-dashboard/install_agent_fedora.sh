#!/bin/bash
# Install ASHD agent on Fedora (or other Linux with systemd)

set -euo pipefail

DASHBOARD_SERVER="${1:-http://localhost:8000}"
INTERVAL="${2:-30}"

echo "Installing ASHD agent..."
echo "Dashboard server: $DASHBOARD_SERVER"
echo "Reporting interval: ${INTERVAL}s"

# Install dependencies
echo "Installing dependencies..."
sudo dnf install -y python3 python3-psutil python3-requests

# Create user and directories
echo "Creating user and directories..."
sudo useradd -r -s /sbin/nologin -d /opt/ashd-agent ashd-agent || true
sudo mkdir -p /opt/ashd-agent /etc/ashd-agent /var/lib/ashd-agent /var/log/ashd-agent
sudo cp agent_fedora.py /opt/ashd-agent/
sudo chmod +x /opt/ashd-agent/agent_fedora.py

# Create config file
echo "Creating config..."
sudo tee /etc/ashd-agent/config.json > /dev/null <<EOF
{
  "server": "$DASHBOARD_SERVER",
  "interval": $INTERVAL
}
EOF

# Install systemd service
echo "Installing systemd service..."
sed "s|http://your-dashboard:8000|$DASHBOARD_SERVER|g; s|--interval 30|--interval $INTERVAL|g" ashd-agent.service | sudo tee /etc/systemd/system/ashd-agent.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now ashd-agent

echo "Installation complete."
echo "Check status with: sudo systemctl status ashd-agent"
echo "View logs with: sudo journalctl -u ashd-agent -f"
echo "To uninstall: sudo systemctl disable --now ashd-agent && sudo userdel ashd-agent && sudo rm -rf /opt/ashd-agent /etc/ashd-agent /var/lib/ashd-agent /var/log/ashd-agent /etc/systemd/system/ashd-agent.service && sudo systemctl daemon-reload"
