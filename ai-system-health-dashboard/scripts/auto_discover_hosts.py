#!/usr/bin/env python3
"""
Auto-Discovery and Multi-Platform Agent Deployment System

Scans network for hosts, identifies OS types, and deploys appropriate agents.
Supports: Ubuntu, RHEL, Debian, CentOS, Rocky Linux
"""

import subprocess
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import ipaddress

class HostDiscovery:
    def __init__(self):
        self.discovered_hosts = []
        self.agent_configs = {
            'ubuntu': {
                'package_manager': 'apt',
                'snmp_package': 'snmpd',
                'ntp_package': 'ntp',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'ufw'
            },
            'debian': {
                'package_manager': 'apt',
                'snmp_package': 'snmpd',
                'ntp_package': 'ntp',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'ufw'
            },
            'rhel': {
                'package_manager': 'dnf',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld'
            },
            'centos': {
                'package_manager': 'yum',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld'
            },
            'rocky': {
                'package_manager': 'dnf',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld'
            }
        }
    
    def scan_network_range(self, network_range: str) -> List[str]:
        """Scan network range for active hosts."""
        print(f"🔍 Scanning network range: {network_range}")
        
        active_hosts = []
        
        try:
            # Use nmap for network scanning if available
            result = subprocess.run(['nmap', '-sn', network_range], 
                                  capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Nmap scan report for' in line:
                        ip = line.split()[-1].strip('()')
                        if ip and not ip.startswith('192.168.50.225'):  # Skip self
                            active_hosts.append(ip)
            else:
                # Fallback to ping sweep
                network = ipaddress.ip_network(network_range, strict=False)
                for ip in network.hosts():
                    ip_str = str(ip)
                    if ip_str.endswith('.1') or ip_str.endswith('.254'):  # Skip gateway/broadcast
                        continue
                    
                    try:
                        result = subprocess.run(['ping', '-c', '1', '-W', '1', ip_str], 
                                              capture_output=True, timeout=2)
                        if result.returncode == 0:
                            active_hosts.append(ip_str)
                    except:
                        continue
                        
        except Exception as e:
            print(f"   ⚠️  Scan error: {e}")
        
        print(f"   📊 Found {len(active_hosts)} active hosts")
        return active_hosts
    
    def identify_os(self, ip: str) -> Tuple[str, Dict]:
        """Identify operating system of host."""
        print(f"   🔍 Identifying OS for {ip}")
        
        os_info = {
            'ip': ip,
            'hostname': None,
            'os_type': 'unknown',
            'os_version': None,
            'package_manager': None,
            'snmp_available': False,
            'ssh_accessible': False,
            'agent_deployable': False
        }
        
        # Try SSH connection and OS identification
        try:
            # Test SSH connectivity
            result = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes', 
                                   f'root@{ip}', 'echo "SSH_OK"'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and 'SSH_OK' in result.stdout:
                os_info['ssh_accessible'] = True
                
                # Get hostname
                try:
                    result = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes', 
                                           f'root@{ip}', 'hostname'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        os_info['hostname'] = result.stdout.strip()
                except:
                    pass
                
                # Identify OS distribution
                try:
                    result = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes', 
                                           f'root@{ip}', 'cat /etc/os-release'], 
                                          capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        os_release = result.stdout
                        
                        # Parse OS information
                        for line in os_release.split('\n'):
                            if line.startswith('ID='):
                                os_id = line.split('=')[1].strip('"').lower()
                                if 'ubuntu' in os_id:
                                    os_info['os_type'] = 'ubuntu'
                                elif 'debian' in os_id:
                                    os_info['os_type'] = 'debian'
                                elif 'rhel' in os_id:
                                    os_info['os_type'] = 'rhel'
                                elif 'centos' in os_id:
                                    os_info['os_type'] = 'centos'
                                elif 'rocky' in os_id:
                                    os_info['os_type'] = 'rocky'
                            
                            elif line.startswith('VERSION_ID='):
                                os_info['os_version'] = line.split('=')[1].strip('"')
                        
                        # Set package manager based on OS type
                        if os_info['os_type'] in self.agent_configs:
                            config = self.agent_configs[os_info['os_type']]
                            os_info['package_manager'] = config['package_manager']
                            os_info['agent_deployable'] = True
                
                except:
                    pass
                
                # Check SNMP availability
                try:
                    result = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'BatchMode=yes', 
                                           f'root@{ip}', 'which snmpd'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        os_info['snmp_available'] = True
                except:
                    pass
                    
        except Exception as e:
            print(f"     ⚠️  OS identification failed: {e}")
        
        return os_info['os_type'], os_info
    
    def discover_hosts(self, network_ranges: List[str]) -> Dict:
        """Main discovery function."""
        print("🚀 Starting Auto-Discovery of Network Hosts")
        print("=" * 50)
        
        discovery_results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'network_ranges': network_ranges,
            'total_hosts_found': 0,
            'hosts_by_os': {},
            'deployable_hosts': [],
            'all_hosts': []
        }
        
        all_active_ips = []
        
        # Scan each network range
        for network_range in network_ranges:
            active_hosts = self.scan_network_range(network_range)
            all_active_ips.extend(active_hosts)
        
        # Remove duplicates
        all_active_ips = list(set(all_active_ips))
        discovery_results['total_hosts_found'] = len(all_active_ips)
        
        print(f"\n🔍 Identifying OS for {len(all_active_ips)} hosts...")
        
        # Identify OS for each host
        for ip in all_active_ips:
            os_type, os_info = self.identify_os(ip)
            
            discovery_results['all_hosts'].append(os_info)
            
            if os_type != 'unknown':
                if os_type not in discovery_results['hosts_by_os']:
                    discovery_results['hosts_by_os'][os_type] = []
                discovery_results['hosts_by_os'][os_type].append(os_info)
                
                if os_info['agent_deployable']:
                    discovery_results['deployable_hosts'].append(os_info)
        
        return discovery_results

class AgentGenerator:
    def __init__(self):
        self.agent_dir = Path('agents')
        self.agent_dir.mkdir(exist_ok=True)
    
    def create_agent_files(self, os_type: str) -> Dict[str, str]:
        """Create agent files for specific OS type."""
        print(f"   📝 Creating agent files for {os_type}")
        
        agent_files = {}
        os_dir = self.agent_dir / os_type
        os_dir.mkdir(exist_ok=True)
        
        # Agent configuration
        config = self.get_agent_config(os_type)
        
        # Create agent script
        agent_script = self.create_agent_script(os_type, config)
        agent_file = os_dir / 'ashd_agent.py'
        with open(agent_file, 'w') as f:
            f.write(agent_script)
        agent_files['agent_script'] = str(agent_file)
        
        # Create deployment script
        deploy_script = self.create_deployment_script(os_type, config)
        deploy_file = os_dir / f'deploy_{os_type}_agent.sh'
        with open(deploy_file, 'w') as f:
            f.write(deploy_script)
        agent_files['deploy_script'] = str(deploy_file)
        
        # Create systemd service file
        service_file = self.create_service_file(os_type, config)
        service_path = os_dir / 'ashd-agent.service'
        with open(service_path, 'w') as f:
            f.write(service_file)
        agent_files['service_file'] = str(service_path)
        
        # Create SNMP configuration
        snmp_config = self.create_snmp_config(os_type, config)
        snmp_file = os_dir / 'snmpd.conf'
        with open(snmp_file, 'w') as f:
            f.write(snmp_config)
        agent_files['snmp_config'] = str(snmp_file)
        
        # Make scripts executable
        os.chmod(deploy_file, 0o755)
        
        return agent_files
    
    def get_agent_config(self, os_type: str) -> Dict:
        """Get OS-specific configuration."""
        configs = {
            'ubuntu': {
                'package_manager': 'apt',
                'snmp_package': 'snmpd',
                'ntp_package': 'ntp',
                'python_package': 'python3',
                'pip_package': 'python3-pip',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'ufw',
                'snmp_service': 'snmpd',
                'ntp_service': 'ntp'
            },
            'debian': {
                'package_manager': 'apt',
                'snmp_package': 'snmpd',
                'ntp_package': 'ntp',
                'python_package': 'python3',
                'pip_package': 'python3-pip',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'ufw',
                'snmp_service': 'snmpd',
                'ntp_service': 'ntp'
            },
            'rhel': {
                'package_manager': 'dnf',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'python_package': 'python3',
                'pip_package': 'python3-pip',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            },
            'centos': {
                'package_manager': 'yum',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'python_package': 'python3',
                'pip_package': 'python3-pip',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            },
            'rocky': {
                'package_manager': 'dnf',
                'snmp_package': 'net-snmp',
                'ntp_package': 'chrony',
                'python_package': 'python3',
                'pip_package': 'python3-pip',
                'service_cmd': 'systemctl',
                'firewall_cmd': 'firewalld',
                'snmp_service': 'snmpd',
                'ntp_service': 'chronyd'
            }
        }
        
        return configs.get(os_type, configs['ubuntu'])
    
    def create_agent_script(self, os_type: str, config: Dict) -> str:
        """Create the main agent script."""
        return f'''#!/usr/bin/env {config['python_package']}
"""
ASHD Monitoring Agent for {os_type.title()}

Collects system metrics and reports to ASHD server.
"""

import json
import time
import subprocess
import socket
import psutil
import platform
import requests
from pathlib import Path

class ASHDAgent:
    def __init__(self):
        self.server_url = "http://192.168.50.225:8001"  # Update with your ASHD server
        self.hostname = socket.gethostname()
        self.agent_id = f"{{self.hostname}}-{{int(time.time())}}"
        self.metrics_interval = 30  # seconds
        
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
            
            metrics = {{
                'timestamp': time.time(),
                'hostname': self.hostname,
                'agent_id': self.agent_id,
                'os_type': '{os_type}',
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
                'processes': len(psutil.pids())
            }}
            
            return metrics
            
        except Exception as e:
            print(f"Error collecting metrics: {{e}}")
            return None
    
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
        print(f"ASHD Agent starting for {{self.hostname}} ({{self.agent_id}})")
        print(f"Reporting to: {{self.server_url}}")
        print(f"Metrics interval: {{self.metrics_interval}} seconds")
        
        while True:
            try:
                metrics = self.get_system_metrics()
                if metrics:
                    success = self.send_metrics(metrics)
                    if success:
                        print(f"{{time.strftime('%Y-%m-%d %H:%M:%S')}} - Metrics sent successfully")
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
    agent = ASHDAgent()
    agent.run()
'''
    
    def create_deployment_script(self, os_type: str, config: Dict) -> str:
        """Create deployment script for the OS."""
        return f'''#!/bin/bash
# ASHD Agent Deployment Script for {os_type.title()}

set -e

echo "🚀 Deploying ASHD Agent for {os_type.title()}"
echo "=========================================="

# Variables
AGENT_DIR="/opt/ashd-agent"
SERVICE_NAME="ashd-agent"
SERVER_URL="http://192.168.50.225:8001"

echo "📦 Installing dependencies..."

# Update package manager
if command -v {config['package_manager']} >/dev/null 2>&1; then
    {config['package_manager']} update -y
fi

# Install required packages
{config['package_manager']} install -y \\
    {config['python_package']} \\
    {config['pip_package']} \\
    {config['snmp_package']} \\
    {config['ntp_package']} \\
    curl \\
    wget

# Install Python dependencies
{config['python_package']} -m pip install psutil requests

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
if [ "{os_type}" = "ubuntu" ] || [ "{os_type}" = "debian" ]; then
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
if command -v {config['firewall_cmd']} >/dev/null 2>&1; then
    if [ "{config['firewall_cmd']}" = "ufw" ]; then
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
{config['service_cmd']} enable {config['snmp_service']}
{config['service_cmd']} restart {config['snmp_service']}

{config['service_cmd']} enable {config['ntp_service']}
{config['service_cmd']} restart {config['ntp_service']}

{config['service_cmd']} daemon-reload
{config['service_cmd']} enable $SERVICE_NAME
{config['service_cmd']} restart $SERVICE_NAME

echo "✅ Deployment completed!"
echo ""
echo "📊 Service Status:"
{config['service_cmd']} status {config['snmp_service']}
{config['service_cmd']} status {config['ntp_service']}
{config['service_cmd']} status $SERVICE_NAME

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
'''
    
    def create_service_file(self, os_type: str, config: Dict) -> str:
        """Create systemd service file."""
        return '''[Unit]
Description=ASHD Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ashd-agent
ExecStart=/usr/bin/python3 /opt/ashd-agent/ashd_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''
    
    def create_snmp_config(self, os_type: str, config: Dict) -> str:
        """Create SNMP configuration."""
        return '''# ASHD SNMP Configuration
# Basic SNMP v2c configuration for monitoring

# Listen on all interfaces
agentAddress udp:161

# SNMP community strings
com2sec readonly  public
com2sec readwrite  private

# Group definitions
group MyROGroup v2c        readonly
group MyRWGroup v2c        readwrite

# Access control
view all    included  .1                               80
view system included  .iso.org.dod.internet.mgmt.mib-2.system

# Access permissions
access MyROGroup ""      any       noauth    exact  all    none   none
access MyRWGroup ""      any       noauth    exact  all    all    none

# System information
sysLocation    "Data Center"
sysContact     "admin@example.com"
sysServices    72

# Process monitoring
proc httpd
proc sendmail

# Disk monitoring
includeAllDisks 10%

# Load average monitoring
load 12 10 5

'''
    
    def create_all_agents(self) -> Dict[str, Dict[str, str]]:
        """Create agent files for all supported OS types."""
        print("📝 Creating agent files for all supported OS types...")
        
        all_agents = {}
        
        for os_type in ['ubuntu', 'debian', 'rhel', 'centos', 'rocky']:
            agent_files = self.create_agent_files(os_type)
            all_agents[os_type] = agent_files
            print(f"   ✅ {os_type.title()}: {len(agent_files)} files created")
        
        return all_agents

def main():
    """Main auto-discovery and agent generation function."""
    
    # Network range to scan (dashboard network)
    network_ranges = [
        '192.168.50.0/24'
    ]
    
    # Discover hosts
    discovery = HostDiscovery()
    results = discovery.discover_hosts(network_ranges)
    
    # Save discovery results
    with open('discovery_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Discovery Summary:")
    print(f"   Total hosts found: {results['total_hosts_found']}")
    print(f"   Deployable hosts: {len(results['deployable_hosts'])}")
    
    for os_type, hosts in results['hosts_by_os'].items():
        print(f"   {os_type.title()}: {len(hosts)} hosts")
    
    # Generate agent files
    generator = AgentGenerator()
    all_agents = generator.create_all_agents()
    
    print(f"\n📁 Agent files created in 'agents/' directory:")
    for os_type, files in all_agents.items():
        print(f"   {os_type.title()}/:")
        for file_type, file_path in files.items():
            print(f"     - {file_type}: {file_path}")
    
    # Create deployment plan
    deployment_plan = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discovery_results': results,
        'agent_files': all_agents,
        'deployment_commands': {}
    }
    
    # Generate deployment commands for each host
    for host in results['deployable_hosts']:
        os_type = host['os_type']
        ip = host['ip']
        
        if os_type in all_agents:
            agent_files = all_agents[os_type]
            commands = [
                f"# Deploy to {host['hostname']} ({ip}) - {os_type.title()}",
                f"scp {agent_files['agent_script']} root@{ip}:/opt/ashd-agent/",
                f"scp {agent_files['deploy_script']} root@{ip}:/tmp/",
                f"scp {agent_files['service_file']} root@{ip}:/tmp/",
                f"scp {agent_files['snmp_config']} root@{ip}:/tmp/",
                f"ssh root@{ip} 'chmod +x /tmp/deploy_{os_type}_agent.sh'",
                f"ssh root@{ip} '/tmp/deploy_{os_type}_agent.sh'"
            ]
            deployment_plan['deployment_commands'][ip] = commands
    
    # Save deployment plan
    with open('deployment_plan.json', 'w') as f:
        json.dump(deployment_plan, f, indent=2)
    
    print(f"\n🚀 Deployment Plan Created:")
    print(f"   discovery_results.json - Host discovery results")
    print(f"   deployment_plan.json - Deployment commands")
    print(f"   agents/ directory - All agent files")
    
    print(f"\n🎯 Ready for deployment!")
    print(f"   Review deployment_plan.json for commands")
    print(f"   Execute commands to deploy agents to discovered hosts")

if __name__ == "__main__":
    main()
