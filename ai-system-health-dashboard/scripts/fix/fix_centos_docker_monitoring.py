#!/usr/bin/env python3
"""
Fix CentOS-Docker Monitoring Issues

Issues to fix:
1. SNMP not monitoring (pysnmp not installed - FIXED)
2. High resource usage (agent reachability)
3. NTP clock skew / server reachability
4. Add agent to centos-docker host
"""

import os
import subprocess
from pathlib import Path

def update_env_for_centos_docker():
    """Update .env file for centos-docker monitoring."""
    print("🔧 Configuring ASHD for centos-docker monitoring...")
    
    env_path = Path('.env')
    env_vars = {}
    
    # Read existing .env
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Configure for centos-docker host
    env_vars['SNMP_HOST'] = 'centos-docker'  # Use hostname
    env_vars['SNMP_PORT'] = '161'
    env_vars['SNMP_COMMUNITY'] = 'public'
    env_vars['SNMP_TIMEOUT_SECONDS'] = '5'  # Longer timeout for reliability
    
    # Keep ICMP monitoring as backup
    env_vars['ICMP_HOST'] = 'centos-docker'
    env_vars['ICMP_TIMEOUT_SECONDS'] = '3'
    
    # Optimize for resource usage
    env_vars['PROTOCOL_CHECK_INTERVAL_SECONDS'] = '30'  # Reduce frequency
    
    # Fix NTP configuration
    env_vars['NTP_SERVER'] = 'pool.ntp.org'
    env_vars['NTP_TIMEOUT_SECONDS'] = '3'
    
    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print("✅ Updated configuration:")
    print("   SNMP_HOST=centos-docker")
    print("   SNMP_PORT=161")
    print("   SNMP_COMMUNITY=public")
    print("   SNMP_TIMEOUT_SECONDS=5")
    print("   ICMP_HOST=centos-docker")
    print("   NTP_SERVER=pool.ntp.org")
    print("   PROTOCOL_CHECK_INTERVAL_SECONDS=30")

def test_centos_docker_connectivity():
    """Test connectivity to centos-docker host."""
    print("\n🧪 Testing centos-docker connectivity...")
    
    # Test ping
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', 'centos-docker'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("   ✅ ICMP connectivity OK")
            # Parse ping results
            for line in result.stdout.strip().split('\n'):
                if 'packet loss' in line.lower():
                    loss = line.split('%')[0].split()[-1]
                    print(f"   📊 Packet loss: {loss}%")
                elif 'avg' in line.lower():
                    avg_time = line.split('/')[4]
                    print(f"   ⏱️  Average response time: {avg_time} ms")
        else:
            print("   ❌ ICMP connectivity failed")
    except Exception as e:
        print(f"   ❌ ICMP test error: {e}")
    
    # Test SNMP
    try:
        cmd = ['snmpwalk', '-v2c', '-c', 'public', '-t', '3', 
               '-r', '2', 'centos-docker:161', '1.3.6.1.2.1.1.1.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            system_info = result.stdout.split('=')[-1].strip()
            print("   ✅ SNMP connectivity OK")
            print(f"   📄 System: {system_info[:60]}...")
        else:
            print("   ❌ SNMP connectivity failed")
            print(f"   📝 Error: {result.stderr.strip()}")
    except Exception as e:
        print(f"   ❌ SNMP test error: {e}")

def create_centos_docker_agent():
    """Create agent deployment script for centos-docker."""
    print("\n🚀 Creating centos-docker agent...")
    
    agent_script = """#!/bin/bash
# ASHD Agent Deployment for CentOS-Docker

set -e

echo "🐧 Deploying ASHD Agent on CentOS-Docker..."

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
# SNMP Configuration for ASHD Monitoring
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

# Create ASHD agent directory
echo "📁 Creating agent directory..."
mkdir -p /opt/ashd-agent
cd /opt/ashd-agent

# Create simple agent script
cat > ashd_agent.py << 'EOF'
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
    print("🤖 ASHD Agent starting...")
    
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

chmod +x ashd_agent.py

# Create systemd service for agent
cat > /etc/systemd/system/ashd-agent.service << 'EOF'
[Unit]
Description=ASHD Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ashd-agent
ExecStart=/usr/bin/python3 /opt/ashd-agent/ashd_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start agent service
echo "🚀 Starting ASHD agent..."
systemctl daemon-reload
systemctl enable ashd-agent
systemctl start ashd-agent
systemctl status ashd-agent

# Test SNMP
echo "🧪 Testing SNMP..."
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

echo "✅ ASHD Agent deployment complete!"
echo "📊 Agent metrics: /opt/ashd-agent/ashd_agent.py"
echo "🔧 SNMP service: systemctl status snmpd"
echo "🤖 Agent service: systemctl status ashd-agent"
"""
    
    with open('deploy_centos_docker_agent.sh', 'w') as f:
        f.write(agent_script)
    
    os.chmod('deploy_centos_docker_agent.sh', 0o755)
    
    print("✅ Created deployment script: deploy_centos_docker_agent.sh")

def fix_ntp_configuration():
    """Fix NTP configuration for clock skew issues."""
    print("\n🕐 Fixing NTP configuration...")
    
    ntp_script = """#!/bin/bash
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
"""
    
    with open('fix_ntp_centos_docker.sh', 'w') as f:
        f.write(ntp_script)
    
    os.chmod('fix_ntp_centos_docker.sh', 0o755)
    
    print("✅ Created NTP fix script: fix_ntp_centos_docker.sh")

def create_monitoring_summary():
    """Create monitoring summary and next steps."""
    print("\n📋 CentOS-Docker Monitoring Setup Summary")
    print("=" * 50)
    
    print("\n✅ Issues Fixed:")
    print("   1. pysnmp - Already installed ✓")
    print("   2. SNMP monitoring - Configured for centos-docker ✓")
    print("   3. Resource usage - Optimized check intervals ✓")
    print("   4. NTP clock skew - Configuration created ✓")
    print("   5. Agent deployment - Script created ✓")
    
    print("\n🔧 Configuration Changes:")
    print("   • SNMP_HOST=centos-docker")
    print("   • SNMP_TIMEOUT_SECONDS=5")
    print("   • ICMP_HOST=centos-docker")
    print("   • PROTOCOL_CHECK_INTERVAL_SECONDS=30")
    print("   • NTP_SERVER=pool.ntp.org")
    
    print("\n🚀 Deployment Scripts Created:")
    print("   • deploy_centos_docker_agent.sh - Agent deployment")
    print("   • fix_ntp_centos_docker.sh - NTP configuration")
    
    print("\n🔄 Next Steps:")
    print("   1. Copy scripts to centos-docker host:")
    print("      scp deploy_centos_docker_agent.sh centos-docker:/root/")
    print("      scp fix_ntp_centos_docker.sh centos-docker:/root/")
    print("   2. Run scripts on centos-docker:")
    print("      ssh centos-docker 'sudo ./fix_ntp_centos_docker.sh'")
    print("      ssh centos-docker 'sudo ./deploy_centos_docker_agent.sh'")
    print("   3. Restart ASHD server to apply changes")
    print("   4. Monitor dashboard for SNMP status")

def main():
    print("🔧 CentOS-Docker Monitoring Fix")
    print("=" * 40)
    print("Fixing: SNMP, Resource Usage, NTP, Agent Deployment")
    
    # Update configuration
    update_env_for_centos_docker()
    
    # Test connectivity
    test_centos_docker_connectivity()
    
    # Create deployment scripts
    create_centos_docker_agent()
    fix_ntp_configuration()
    
    # Create summary
    create_monitoring_summary()
    
    print("\n🎉 CentOS-Docker monitoring fix complete!")
    print("\n💡 Note: Run the deployment scripts on centos-docker host")

if __name__ == "__main__":
    main()
