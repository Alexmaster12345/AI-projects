#!/usr/bin/env python3
"""
Non-Root Agent Deployment System

Deploys ASHD agents to discovered hosts using regular user accounts
with sudo privileges for system operations.
"""

import json
import subprocess
import time
import os
from pathlib import Path
from typing import Dict, List, Optional

class NonRootAgentDeployer:
    def __init__(self):
        self.deployment_results = []
        self.agents_dir = Path('agents')
        self.default_user = 'ashd-agent'  # Default non-root user
        
    def load_discovery_results(self) -> Dict:
        """Load discovery results from file."""
        try:
            with open('discovery_results.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ Discovery results not found. Run auto_discover_hosts.py first.")
            return {}
    
    def create_user_deployment_scripts(self):
        """Create deployment scripts for non-root users."""
        print("📝 Creating non-root deployment scripts...")
        
        os_types = ['ubuntu', 'debian', 'rhel', 'centos', 'rocky']
        
        for os_type in os_types:
            self._create_non_root_agent(os_type)
            self._create_non_root_deployment_script(os_type)
            self._create_user_setup_script(os_type)
        
        print(f"✅ Created non-root deployment scripts for {len(os_types)} OS types")
    
    def _create_non_root_agent(self, os_type: str):
        """Create a non-root version of the agent."""
        agent_dir = self.agents_dir / os_type
        agent_dir.mkdir(exist_ok=True)
        
        agent_content = f'''#!/usr/bin/env python3
"""
ASHD Monitoring Agent for {os_type.title()} (Non-Root Version)

Runs as non-root user with sudo for privileged operations.
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
        
    def run_command_with_sudo(self, command: str) -> str:
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
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Load average (Linux)
            try:
                load_avg = os.getloadavg()
            except:
                load_avg = [0, 0, 0]
            
            # System uptime
            try:
                uptime = time.time() - psutil.boot_time()
            except:
                uptime = 0
            
            # Process count
            try:
                process_count = len(psutil.pids())
            except:
                process_count = 0
            
            # Additional metrics that might need sudo
            service_status = self._get_service_status()
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
    
    def _get_service_status(self) -> Dict:
        """Get status of key services."""
        services = {{
            'snmpd': self._check_service('snmpd'),
            'chronyd': self._check_service('chronyd') if '{os_type}' in ['rhel', 'centos', 'rocky'] else self._check_service('ntp'),
            'ashd-agent': self._check_service('ashd-agent')
        }}
        return services
    
    def _check_service(self, service_name: str) -> str:
        """Check if a service is active."""
        try:
            status = self.run_command_with_sudo(f"systemctl is-active {{service_name}}")
            return status.strip() if status else "unknown"
        except:
            return "unknown"
    
    def _get_ntp_status(self) -> Dict:
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
                        if 'RMS offset' in line:
                            status['rms_offset'] = line.split(':')[1].strip()
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
        
        # Make executable
        agent_file.chmod(0o755)
    
    def _create_non_root_deployment_script(self, os_type: str):
        """Create deployment script for non-root user."""
        agent_dir = self.agents_dir / os_type
        
        # Get OS-specific configuration
        config = self._get_os_config(os_type)
        
        script_content = f'''#!/bin/bash
# ASHD Agent Deployment Script for {os_type.title()} (Non-Root Version)

set -e

echo "🚀 Deploying ASHD Agent for {os_type.title()} (Non-Root)"
echo "=================================================="

# Configuration
AGENT_USER="{self.default_user}"
AGENT_DIR="/home/$AGENT_USER/ashd-agent"
SERVICE_NAME="ashd-agent"

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

print_status() {{
    echo -e "${{GREEN}}✅ $1${{NC}}"
}}

print_warning() {{
    echo -e "${{YELLOW}}⚠️  $1${{NC}}"
}}

print_error() {{
    echo -e "${{RED}}❌ $1${{NC}}"
}}

# Check if running as root (needed for setup)
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root for initial setup"
    echo "Please run: sudo $0"
    exit 1
fi

echo "📋 Step 1: Creating agent user..."
if ! id "$AGENT_USER" &>/dev/null; then
    {config['user_create_cmd']}
    print_status "Created user: $AGENT_USER"
else
    print_status "User $AGENT_USER already exists"
fi

echo "📦 Step 2: Installing system packages..."
{config['package_install_cmd']}

echo "🐍 Step 3: Installing Python dependencies..."
{config['python_install_cmd']}

echo "📁 Step 4: Creating agent directory..."
mkdir -p "$AGENT_DIR"
chown $AGENT_USER:$AGENT_USER "$AGENT_DIR"

echo "📝 Step 5: Copying agent files..."
cp ashd_agent_non_root.py "$AGENT_DIR/ashd_agent.py"
chown $AGENT_USER:$AGENT_USER "$AGENT_DIR/ashd_agent.py"
chmod +x "$AGENT_DIR/ashd_agent.py"

echo "⚙️  Step 6: Configuring SNMP..."
{config['snmp_config_cmd']}

echo "⏰ Step 7: Configuring NTP..."
{config['ntp_config_cmd']}

echo "🔥 Step 8: Configuring firewall..."
{config['firewall_config_cmd']}

echo "🔐 Step 9: Setting up sudo permissions..."
cat > /etc/sudoers.d/ashd-agent << 'EOF'
# ASHD Agent sudo permissions
{self.default_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
{self.default_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
{self.default_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status ntp
{self.default_user} ALL=(ALL) NOPASSWD: /usr/bin/chronyc
{self.default_user} ALL=(ALL) NOPASSWD: /usr/bin/ntpq
{self.default_user} ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF

echo "🔄 Step 10: Creating systemd service..."
cat > /etc/systemd/system/ashd-agent.service << 'EOF'
[Unit]
Description=ASHD Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User={self.default_user}
Group={self.default_user}
WorkingDirectory={agent_dir}/
ExecStart=/usr/bin/python3 {agent_dir}/ashd_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "🚀 Step 11: Starting services..."
systemctl daemon-reload
systemctl enable {config['snmp_service']}
systemctl restart {config['snmp_service']}
systemctl enable {config['ntp_service']}
systemctl restart {config['ntp_service']}
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "✅ Step 12: Setting up log rotation..."
cat > /etc/logrotate.d/ashd-agent << 'EOF'
/var/log/ashd-agent/*.log {{
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 {self.default_user} {self.default_user}
}}
EOF

echo "🔍 Step 13: Verifying deployment..."
echo ""
print_status "Service Status:"
systemctl status {config['snmp_service']} --no-pager -l | head -5
systemctl status {config['ntp_service']} --no-pager -l | head -5
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
echo "📋 Next Steps:"
echo "1. Check ASHD dashboard: http://localhost:8001"
echo "2. Monitor agent logs: journalctl -u ashd-agent -f"
echo "3. Test SNMP from external: snmpwalk -v2c -c public $(hostname -I | cut -d' ' -f1) 1.3.6.1.2.1.1.1.0"
echo ""
echo "🔧 Agent Management:"
echo "- Restart: systemctl restart ashd-agent"
echo "- Status: systemctl status ashd-agent"
echo "- Logs: journalctl -u ashd-agent -f"
echo "- Config: $AGENT_DIR/ashd_agent.py"
'''
        
        script_file = agent_dir / f'deploy_{os_type}_agent_non_root.sh'
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        # Make executable
        script_file.chmod(0o755)
    
    def _create_user_setup_script(self, os_type: str):
        """Create user setup script for initial configuration."""
        agent_dir = self.agents_dir / os_type
        
        setup_content = f'''#!/bin/bash
# User Setup Script for ASHD Agent ({os_type.title()})

set -e

AGENT_USER="{self.default_user}"
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
        
        # Make executable
        setup_file.chmod(0o755)
    
    def _get_os_config(self, os_type: str) -> Dict:
        """Get OS-specific configuration."""
        configs = {{
            'ubuntu': {{
                'user_create_cmd': 'useradd -m -s /bin/bash $AGENT_USER',
                'package_install_cmd': '''
apt update -y
apt install -y python3 python3-pip net-snmp snmpd ntp
''',
                'python_install_cmd': 'python3 -m pip install --user psutil requests',
                'snmp_config_cmd': '''
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
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
SNMP_EOF

# Enable SNMP
sed -i 's/.*SNMPDOPTS=.*/SNMPDOPTS="-Lsd -Lf /dev/null -u snmp -I smux -p /var/run/snmpd.pid"/' /etc/default/snmpd
''',
                'ntp_config_cmd': '''
# Configure NTP
[ -f /etc/ntp.conf ] && cp /etc/ntp.conf /etc/ntp.conf.backup
echo "server pool.ntp.org iburst" >> /etc/ntp.conf
''',
                'firewall_config_cmd': '''
ufw allow 161/udp comment "SNMP"
ufw allow 123/udp comment "NTP"
ufw --force enable
''',
                'snmp_service': 'snmpd',
                'ntp_service': 'ntp'
            }},
            'debian': {{
                'user_create_cmd': 'useradd -m -s /bin/bash $AGENT_USER',
                'package_install_cmd': '''
apt update -y
apt install -y python3 python3-pip net-snmp snmpd ntp
''',
                'python_install_cmd': 'python3 -m pip install --user psutil requests',
                'snmp_config_cmd': '''
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
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
SNMP_EOF
''',
                'ntp_config_cmd': '''
# Configure NTP
[ -f /etc/ntp.conf ] && cp /etc/ntp.conf /etc/ntp.conf.backup
echo "server pool.ntp.org iburst" >> /etc/ntp.conf
''',
                'firewall_config_cmd': '''
ufw allow 161/udp comment "SNMP"
ufw allow 123/udp comment "NTP"
ufw --force enable
''',
                'snmp_service': 'snmpd',
                'ntp_service': 'ntp'
            }},
            'rhel': {{
                'user_create_cmd': 'useradd -m -s /bin/bash $AGENT_USER',
                'package_install_cmd': '''
dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony
''',
                'python_install_cmd': 'python3 -m pip install --user psutil requests',
                'snmp_config_cmd': '''
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
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
SNMP_EOF
''',
                'ntp_config_cmd': '''
# Configure chrony
[ -f /etc/chrony.conf ] && cp /etc/chrony.conf /etc/chrony.conf.backup
cat > /etc/chrony.conf << 'NTP_EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
NTP_EOF
''',
                'firewall_config_cmd': '''
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
''',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            }},
            'centos': {{
                'user_create_cmd': 'useradd -m -s /bin/bash $AGENT_USER',
                'package_install_cmd': '''
yum update -y
yum install -y python3 python3-pip net-snmp net-snmp-utils chrony
''',
                'python_install_cmd': 'python3 -m pip install --user psutil requests',
                'snmp_config_cmd': '''
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
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
SNMP_EOF
''',
                'ntp_config_cmd': '''
# Configure chrony
[ -f /etc/chrony.conf ] && cp /etc/chrony.conf /etc/chrony.conf.backup
cat > /etc/chrony.conf << 'NTP_EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
NTP_EOF
''',
                'firewall_config_cmd': '''
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
''',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            }},
            'rocky': {{
                'user_create_cmd': 'useradd -m -s /bin/bash $AGENT_USER',
                'package_install_cmd': '''
dnf update -y
dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony
''',
                'python_install_cmd': 'python3 -m pip install --user psutil requests',
                'snmp_config_cmd': '''
# Backup original config
[ -f /etc/snmp/snmpd.conf ] && cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.backup

# Create new SNMP config
cat > /etc/snmp/snmpd.conf << 'SNMP_EOF'
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
SNMP_EOF
''',
                'ntp_config_cmd': '''
# Configure chrony
[ -f /etc/chrony.conf ] && cp /etc/chrony.conf /etc/chrony.conf.backup
cat > /etc/chrony.conf << 'NTP_EOF'
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
NTP_EOF
''',
                'firewall_config_cmd': '''
firewall-cmd --permanent --add-port=161/udp
firewall-cmd --permanent --add-port=123/udp
firewall-cmd --reload
''',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            }}
        }}
        
        return configs.get(os_type, configs['ubuntu'])
    
    def deploy_to_all_hosts(self, username: str = None):
        """Deploy agents to all discovered hosts using non-root user."""
        print("🚀 Starting Non-Root Agent Deployment")
        print("=" * 50)
        
        if username:
            self.default_user = username
        
        # Load discovery results
        discovery = self.load_discovery_results()
        if not discovery:
            return
        
        hosts = discovery['all_hosts']
        print(f"📊 Found {len(hosts)} hosts to process")
        
        # Create deployment scripts
        self.create_user_deployment_scripts()
        
        for i, host in enumerate(hosts, 1):
            ip = host['ip']
            print(f"\n[{i}/{len(hosts)}] Processing {ip}")
            
            # Try to detect OS or use default
            os_type = host.get('os_type', 'rocky')  # Default to rocky for centos-docker
            if ip == '192.168.50.198':
                os_type = 'rocky'  # centos-docker is Rocky Linux
            
            # Deploy to host
            result = self._deploy_to_host_non_root(ip, os_type)
            self.deployment_results.append(result)
            
            # Print result
            if result['success']:
                print(f"   ✅ Deployment successful for {ip}")
            else:
                print(f"   ❌ Deployment failed for {ip}: {result['error']}")
        
        # Save results
        self._save_deployment_results()
        self._print_deployment_summary()
    
    def _deploy_to_host_non_root(self, ip: str, os_type: str) -> Dict:
        """Deploy agent to specific host using non-root user."""
        result = {{
            'ip': ip,
            'os_type': os_type,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'success': False,
            'steps': [],
            'error': None,
            'user': self.default_user
        }}
        
        try:
            # Step 1: Test SSH connectivity
            print(f"   1️⃣ Testing SSH connectivity...")
            ssh_result = subprocess.run([
                'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                f'root@{ip}', 'echo "SSH_OK"'
            ], capture_output=True, text=True, timeout=10)
            
            if ssh_result.returncode != 0 or 'SSH_OK' not in ssh_result.stdout:
                result['error'] = 'SSH connectivity failed'
                result['steps'].append('❌ SSH connectivity failed')
                return result
            
            result['steps'].append('✅ SSH connectivity verified')
            
            # Step 2: Copy deployment script
            print(f"   2️⃣ Copying deployment script...")
            script_path = f'agents/{os_type}/deploy_{os_type}_agent_non_root.sh'
            agent_path = f'agents/{os_type}/ashd_agent_non_root.py'
            
            if not Path(script_path).exists():
                result['error'] = f'Deployment script not found: {script_path}'
                result['steps'].append('❌ Deployment script not found')
                return result
            
            # Copy files
            scp_result = subprocess.run([
                'scp', script_path, f'root@{ip}:/tmp/'
            ], capture_output=True, text=True, timeout=30)
            
            if scp_result.returncode != 0:
                result['error'] = f'Failed to copy deployment script'
                result['steps'].append('❌ Failed to copy deployment script')
                return result
            
            scp_result = subprocess.run([
                'scp', agent_path, f'root@{ip}:/tmp/'
            ], capture_output=True, text=True, timeout=30)
            
            if scp_result.returncode != 0:
                result['error'] = f'Failed to copy agent script'
                result['steps'].append('❌ Failed to copy agent script')
                return result
            
            result['steps'].append('✅ Files copied to host')
            
            # Step 3: Execute deployment script
            print(f"   3️⃣ Executing deployment script...")
            deploy_result = subprocess.run([
                'ssh', f'root@{ip}', 
                f'chmod +x /tmp/deploy_{os_type}_agent_non_root.sh && /tmp/deploy_{os_type}_agent_non_root.sh'
            ], capture_output=True, text=True, timeout=180)
            
            if deploy_result.returncode != 0:
                result['error'] = f'Deployment script failed: {deploy_result.stderr}'
                result['steps'].append('❌ Deployment script failed')
                return result
            
            result['steps'].append('✅ Deployment script executed')
            
            # Step 4: Verify deployment
            print(f"   4️⃣ Verifying deployment...")
            services = ['ashd-agent', 'snmpd', 'chronyd' if os_type in ['rhel', 'centos', 'rocky'] else 'ntp']
            
            for service in services:
                service_result = subprocess.run([
                    'ssh', f'root@{ip}', f'systemctl is-active {service}'
                ], capture_output=True, text=True, timeout=10)
                
                if service_result.returncode == 0 and 'active' in service_result.stdout:
                    result['steps'].append(f'✅ {service} service active')
                else:
                    result['steps'].append(f'⚠️  {service} service not active')
            
            # Step 5: Test SNMP
            print(f"   5️⃣ Testing SNMP...")
            snmp_result = subprocess.run([
                'snmpwalk', '-v2c', '-c', 'public', '-t', '3', 
                f'{ip}:161', '1.3.6.1.2.1.1.1.0'
            ], capture_output=True, text=True, timeout=10)
            
            if snmp_result.returncode == 0:
                result['steps'].append('✅ SNMP responding')
            else:
                result['steps'].append('⚠️  SNMP not responding')
            
            result['success'] = True
            result['steps'].append('🎉 Non-root agent deployment completed')
            
        except Exception as e:
            result['error'] = str(e)
            result['steps'].append(f'❌ Deployment failed: {e}')
        
        return result
    
    def _save_deployment_results(self):
        """Save deployment results to file."""
        results_data = {{
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'deployment_type': 'non-root',
            'agent_user': self.default_user,
            'total_deployments': len(self.deployment_results),
            'successful_deployments': len([r for r in self.deployment_results if r['success']]),
            'failed_deployments': len([r for r in self.deployment_results if not r['success']]),
            'results': self.deployment_results
        }}
        
        with open('non_root_deployment_results.json', 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📄 Deployment results saved to non_root_deployment_results.json")
    
    def _print_deployment_summary(self):
        """Print deployment summary."""
        total = len(self.deployment_results)
        successful = len([r for r in self.deployment_results if r['success']])
        failed = total - successful
        
        print(f"\n📊 Non-Root Deployment Summary")
        print("=" * 40)
        print(f"Agent User: {self.default_user}")
        print(f"Total deployments: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/total*100):.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print(f"\n❌ Failed Deployments:")
            for result in self.deployment_results:
                if not result['success']:
                    print(f"   {result['ip']}: {result['error']}")
        
        print(f"\n🎯 Next Steps:")
        print(f"   1. Check ASHD dashboard: http://localhost:8001")
        print(f"   2. Verify agent status on hosts")
        print(f"   3. Monitor SNMP and system metrics")
        print(f"   4. Check user permissions: sudo -u {self.default_user} -l")

def main():
    """Main non-root deployment function."""
    import sys
    
    deployer = NonRootAgentDeployer()
    
    # Check for custom username
    username = None
    if len(sys.argv) > 1:
        username = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == '--create-scripts-only':
        # Only create scripts, don't deploy
        deployer.create_user_deployment_scripts()
        print(f"\n✅ Non-root deployment scripts created")
        print(f"   Agent user: {deployer.default_user}")
        print(f"   Scripts location: agents/*/")
        return
    
    # Deploy to all hosts
    deployer.deploy_to_all_hosts(username)

if __name__ == "__main__":
    main()
