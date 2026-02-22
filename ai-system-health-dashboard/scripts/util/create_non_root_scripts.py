#!/usr/bin/env python3
"""
Create Non-Root Deployment Scripts

Creates deployment scripts for all OS types that install agents as non-root users.
"""

import os
from pathlib import Path

def create_non_root_scripts():
    """Create non-root deployment scripts for all OS types."""
    print("📝 Creating Non-Root Deployment Scripts")
    print("=" * 40)
    
    os_types = ['ubuntu', 'debian', 'rhel', 'centos', 'rocky']
    agent_user = 'ashd-agent'
    
    for os_type in os_types:
        print(f"   📝 Creating {os_type.title()} scripts...")
        
        # Create agent directory
        agent_dir = Path(f'agents/{os_type}')
        agent_dir.mkdir(exist_ok=True)
        
        # Create non-root agent
        create_non_root_agent(agent_dir, os_type)
        
        # Create deployment script
        create_deployment_script(agent_dir, os_type, agent_user)
        
        # Create user setup script
        create_user_setup_script(agent_dir, os_type, agent_user)
    
    print(f"✅ Created non-root scripts for {len(os_types)} OS types")

def create_non_root_agent(agent_dir, os_type):
    """Create non-root version of the agent."""
    agent_content = f'''#!/usr/bin/env python3
"""
ASHD Monitoring Agent for {os_type.title()} (Non-Root Version)
"""

import json
import time
import subprocess
import socket
import psutil
import requests
import os
import pwd
from pathlib import Path

class NonRootASHDAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"
        self.hostname = socket.gethostname()
        self.agent_id = f"{{self.hostname}}-{{int(time.time())}}"
        self.metrics_interval = 30
        self.user = pwd.getpwuid(os.getuid()).pw_name
        
    def run_command_with_sudo(self, command):
        """Run command with sudo if needed."""
        try:
            # Try without sudo first
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Try with sudo
            result = subprocess.run(f"sudo {{command}}", shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return ""
        except Exception:
            return ""
    
    def get_system_metrics(self):
        """Collect system metrics."""
        try:
            # Basic metrics (no sudo required)
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            try:
                load_avg = os.getloadavg()
            except:
                load_avg = [0, 0, 0]
            
            try:
                uptime = time.time() - psutil.boot_time()
            except:
                uptime = 0
            
            try:
                process_count = len(psutil.pids())
            except:
                process_count = 0
            
            # Service status (requires sudo)
            service_status = {{
                'snmpd': self._check_service('snmpd'),
                'chronyd': self._check_service('chronyd') if '{os_type}' in ['rhel', 'centos', 'rocky'] else self._check_service('ntp'),
                'ashd-agent': self._check_service('ashd-agent')
            }}
            
            # NTP status (requires sudo)
            ntp_status = self._get_ntp_status()
            
            metrics = {{
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': '{os_type}',
                'user': self.user,
                'cpu': {{
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg': list(load_avg)
                }},
                'memory': {{
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                }},
                'disk': {{
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                }},
                'network': {{
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }},
                'uptime': uptime,
                'processes': process_count,
                'services': service_status,
                'ntp': ntp_status
            }}
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting metrics: {{e}}")
            return None
    
    def _check_service(self, service_name):
        """Check if a service is active."""
        try:
            status = self.run_command_with_sudo(f"systemctl is-active {{service_name}}")
            return status.strip() if status else "unknown"
        except:
            return "unknown"
    
    def _get_ntp_status(self):
        """Get NTP synchronization status."""
        try:
            if '{os_type}' in ['rhel', 'centos', 'rocky']:
                # Use chronyc
                output = self.run_command_with_sudo("chronyc tracking")
                if output:
                    lines = output.split('\\n')
                    status = {{}}
                    for line in lines:
                        if 'Stratum' in line:
                            status['stratum'] = line.split(':')[1].strip()
                        if 'Last offset' in line:
                            status['offset'] = line.split(':')[1].strip()
                    return status
            else:
                # Use ntpq for Ubuntu/Debian
                output = self.run_command_with_sudo("ntpq -c rv")
                if output:
                    lines = output.split('\\n')
                    status = {{}}
                    for line in lines:
                        if 'stratum=' in line:
                            status['stratum'] = line.split('=')[1].strip()
                        if 'offset=' in line:
                            status['offset'] = line.split('=')[1].strip()
                    return status
        except:
            pass
        return {{'status': 'unknown'}}
    
    def send_metrics(self, metrics):
        """Send metrics to ASHD server."""
        try:
            response = requests.post(
                f"{{self.server_url}}/api/agent/metrics",
                json=metrics,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending metrics: {{e}}")
            return False
    
    def run(self):
        """Main agent loop."""
        print(f"ASHD Agent starting for {{self.hostname}} (user: {{self.user}})")
        print(f"Reporting to: {{self.server_url}}")
        
        while True:
            try:
                metrics = self.get_system_metrics()
                if metrics:
                    success = self.send_metrics(metrics)
                    if success:
                        print(f"{{time.strftime('%Y-%m-%d %H:%M:%S')}} - Metrics sent")
                    else:
                        print(f"{{time.strftime('%Y-%m-%d %H:%M:%S')}} - Failed to send metrics")
                
                time.sleep(self.metrics_interval)
                
            except KeyboardInterrupt:
                print("Agent stopped by user")
                break
            except Exception as e:
                print(f"Agent error: {{e}}")
                time.sleep(10)

if __name__ == "__main__":
    agent = NonRootASHDAgent()
    agent.run()
'''
    
    agent_file = agent_dir / 'ashd_agent_non_root.py'
    with open(agent_file, 'w') as f:
        f.write(agent_content)
    
    agent_file.chmod(0o755)

def create_deployment_script(agent_dir, os_type, agent_user):
    """Create deployment script for non-root user."""
    
    # OS-specific commands
    if os_type in ['ubuntu', 'debian']:
        package_cmd = f'''
apt update -y
apt install -y python3 python3-pip net-snmp snmpd ntp
'''
        python_cmd = 'python3 -m pip install --user psutil requests'
        snmp_service = 'snmpd'
        ntp_service = 'ntp'
        firewall_cmd = '''
ufw allow 161/udp comment "SNMP"
ufw allow 123/udp comment "NTP"
ufw --force enable
'''
    else:  # rhel, centos, rocky
        package_cmd = f'''
dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony
'''
        python_cmd = 'python3 -m pip install --user psutil requests'
        snmp_service = 'snmpd'
        ntp_service = 'chronyd'
        firewall_cmd = '''
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
'''
    
    script_content = f'''#!/bin/bash
# ASHD Agent Deployment Script for {os_type.title()} (Non-Root Version)

set -e

AGENT_USER="{agent_user}"
AGENT_DIR="/home/$AGENT_USER/ashd-agent"
SERVICE_NAME="ashd-agent"

# Colors
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
NC='\\033[0m'

print_status() {{ echo -e "${{GREEN}}✅ $1${{NC}}"; }}
print_warning() {{ echo -e "${{YELLOW}}⚠️  $1${{NC}}"; }}
print_error() {{ echo -e "${{RED}}❌ $1${{NC}}"; }}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root for initial setup"
    echo "Please run: sudo $0"
    exit 1
fi

echo "🚀 Deploying ASHD Agent for {os_type.title()} (Non-Root)"
echo "=================================================="

echo "📋 Step 1: Creating agent user..."
if ! id "$AGENT_USER" &>/dev/null; then
    useradd -m -s /bin/bash $AGENT_USER
    print_status "Created user: $AGENT_USER"
else
    print_status "User $AGENT_USER already exists"
fi

echo "📦 Step 2: Installing system packages..."
{package_cmd}

echo "🐍 Step 3: Installing Python dependencies..."
{python_cmd}

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
if [ "{os_type}" = "ubuntu" ] || [ "{os_type}" = "debian" ]; then
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
{firewall_cmd}

echo "🔐 Step 9: Setting up sudo permissions..."
cat > /etc/sudoers.d/ashd-agent << 'EOF'
# ASHD Agent sudo permissions
{agent_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
{agent_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status {ntp_service}
{agent_user} ALL=(ALL) NOPASSWD: /usr/bin/chronyc
{agent_user} ALL=(ALL) NOPASSWD: /usr/bin/ntpq
{agent_user} ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF

echo "🔄 Step 10: Creating systemd service..."
cat > /etc/systemd/system/ashd-agent.service << EOF
[Unit]
Description=ASHD Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User={agent_user}
Group={agent_user}
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
systemctl enable {snmp_service}
systemctl restart {snmp_service}
systemctl enable {ntp_service}
systemctl restart {ntp_service}
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "✅ Step 12: Setting up log rotation..."
mkdir -p /var/log/ashd-agent
chown $AGENT_USER:$AGENT_USER /var/log/ashd-agent

cat > /etc/logrotate.d/ashd-agent << EOF
/var/log/ashd-agent/*.log {{
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 {agent_user} {agent_user}
}}
EOF

echo "🔍 Step 13: Verifying deployment..."
echo ""
print_status "Service Status:"
systemctl status {snmp_service} --no-pager -l | head -5
systemctl status {ntp_service} --no-pager -l | head -5
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
'''
    
    script_file = agent_dir / f'deploy_{os_type}_agent_non_root.sh'
    with open(script_file, 'w') as f:
        f.write(script_content)
    
    script_file.chmod(0o755)

def create_user_setup_script(agent_dir, os_type, agent_user):
    """Create user setup script."""
    setup_content = f'''#!/bin/bash
# User Setup Script for ASHD Agent ({os_type.title()})

AGENT_USER="{agent_user}"
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
'''
    
    setup_file = agent_dir / f'setup_{os_type}_user.sh'
    with open(setup_file, 'w') as f:
        f.write(setup_content)
    
    setup_file.chmod(0o755)

def main():
    """Main function."""
    create_non_root_scripts()
    
    print(f"\n📁 Non-Root Scripts Created:")
    print(f"   agents/ubuntu/deploy_ubuntu_agent_non_root.sh")
    print(f"   agents/debian/deploy_debian_agent_non_root.sh")
    print(f"   agents/rhel/deploy_rhel_agent_non_root.sh")
    print(f"   agents/centos/deploy_centos_agent_non_root.sh")
    print(f"   agents/rocky/deploy_rocky_agent_non_root.sh")
    print(f"")
    print(f"🎯 Usage:")
    print(f"   1. Copy script to target host")
    print(f"   2. Run with sudo: sudo ./deploy_*_agent_non_root.sh")
    print(f"   3. Agent runs as non-root user: ashd-agent")
    print(f"   4. Monitor via dashboard: http://localhost:8001")

if __name__ == "__main__":
    main()
