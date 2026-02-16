#!/bin/bash
# User Setup Script for ASHD Agent (Rhel)

AGENT_USER="ashd-agent"
AGENT_DIR="/home/$AGENT_USER/ashd-agent"

echo "🔧 Setting up ASHD agent user environment..."

# Create log directory
sudo mkdir -p /var/log/ashd-agent
sudo chown $AGENT_USER:$AGENT_USER /var/log/ashd-agent

# Create config directory
mkdir -p "$AGENT_DIR/config"
mkdir -p "$AGENT_DIR/logs"

# Create agent config
cat > "$AGENT_DIR/config/agent.conf" << EOF
[agent]
server_url = http://192.168.50.225:8001
metrics_interval = 30
log_level = INFO

[monitoring]
enable_cpu = true
enable_memory = true
enable_disk = true
enable_network = true
enable_services = true
enable_ntp = true
EOF

echo "✅ User environment setup completed"
echo "Agent directory: $AGENT_DIR"
echo "Config file: $AGENT_DIR/config/agent.conf"
echo "Log directory: /var/log/ashd-agent"
