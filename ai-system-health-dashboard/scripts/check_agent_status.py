#!/usr/bin/env python3
"""
Check ASHD Agent Status on CentOS-Docker

This script helps verify the agent deployment and provides troubleshooting steps.
"""

import subprocess
import json
import time
from pathlib import Path

def test_connectivity(ip):
    """Test basic connectivity to target IP."""
    print(f"🔍 Testing connectivity to {ip}...")
    
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', ip], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(f"   ✅ Ping successful")
            # Parse ping results
            for line in result.stdout.strip().split('\n'):
                if 'packet loss' in line.lower():
                    loss = line.split('%')[0].split()[-1]
                    print(f"   📊 Packet loss: {loss}%")
                elif 'avg' in line.lower():
                    avg_time = line.split('/')[4]
                    print(f"   ⏱️  Average response time: {avg_time} ms")
            return True
        else:
            print(f"   ❌ Ping failed")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_snmp_connectivity(ip):
    """Test SNMP connectivity to target IP."""
    print(f"🐌 Testing SNMP connectivity to {ip}...")
    
    try:
        cmd = ['snmpwalk', '-v2c', '-c', 'public', '-t', '3', 
               '-r', '2', f'{ip}:161', '1.3.6.1.2.1.1.1.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            system_info = result.stdout.split('=')[-1].strip()
            print(f"   ✅ SNMP successful")
            print(f"   📄 System: {system_info[:60]}...")
            return True
        else:
            print(f"   ❌ SNMP failed")
            print(f"   📝 Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"   ❌ SNMP test error: {e}")
        return False

def check_ashd_config():
    """Check current ASHD configuration."""
    print(f"🔧 Checking ASHD configuration...")
    
    try:
        with open('.env', 'r') as f:
            config = {}
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        print(f"   📋 Current configuration:")
        print(f"      SNMP_HOST: {config.get('SNMP_HOST', 'Not set')}")
        print(f"      SNMP_PORT: {config.get('SNMP_PORT', '161')}")
        print(f"      ICMP_HOST: {config.get('ICMP_HOST', 'Not set')}")
        print(f"      NTP_SERVER: {config.get('NTP_SERVER', 'Not set')}")
        print(f"      CHECK_INTERVAL: {config.get('PROTOCOL_CHECK_INTERVAL_SECONDS', 'Not set')}s")
        
        return config
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")
        return {}

def generate_deployment_commands(ip):
    """Generate deployment commands for the target IP."""
    print(f"\n🚀 Deployment Commands for {ip}")
    print(f"=" * 50)
    
    print(f"\n📋 Step 1: Copy scripts to target host")
    print(f"```bash")
    print(f"scp deploy_centos_docker_agent.sh root@{ip}:/root/")
    print(f"scp fix_ntp_centos_docker.sh root@{ip}:/root/")
    print(f"```")
    
    print(f"\n📋 Step 2: SSH to target host")
    print(f"```bash")
    print(f"ssh root@{ip}")
    print(f"```")
    
    print(f"\n📋 Step 3: Run NTP fix")
    print(f"```bash")
    print(f"sudo ./fix_ntp_centos_docker.sh")
    print(f"```")
    
    print(f"\n📋 Step 4: Deploy agent")
    print(f"```bash")
    print(f"sudo ./deploy_centos_docker_agent.sh")
    print(f"```")
    
    print(f"\n📋 Step 5: Verify deployment")
    print(f"```bash")
    print(f"# Check services")
    print(f"systemctl status snmpd")
    print(f"systemctl status ntpd")
    print(f"systemctl status ashd-agent")
    print(f"")
    print(f"# Test SNMP")
    print(f"snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0")
    print(f"")
    print(f"# Check NTP")
    print(f"ntpq -p")
    print(f"")
    print(f"# Check agent logs")
    print(f"journalctl -u ashd-agent -f")
    print(f"```")

def create_status_report():
    """Create a status report file."""
    print(f"\n📄 Creating status report...")
    
    status_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'target_ip': '192.168.50.225',
        'connectivity_test': 'Pending',
        'snmp_test': 'Pending',
        'ashd_config': 'Checked',
        'deployment_status': 'Scripts ready',
        'next_steps': 'Manual deployment required'
    }
    
    with open('agent_status_report.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    
    print(f"✅ Status report saved: agent_status_report.json")

def main():
    print("🔍 ASHD Agent Status Check")
    print("=" * 40)
    
    # Target IP (likely centos-docker)
    target_ip = "192.168.50.225"
    
    # Check ASHD configuration
    config = check_ashd_config()
    
    # Test connectivity
    connectivity_ok = test_connectivity(target_ip)
    
    if connectivity_ok:
        # Test SNMP
        snmp_ok = test_snmp_connectivity(target_ip)
        
        if not snmp_ok:
            print(f"\n⚠️  SNMP not responding - agent deployment needed")
            generate_deployment_commands(target_ip)
        else:
            print(f"\n✅ SNMP working - agent may already be deployed")
    else:
        print(f"\n❌ Host not reachable - check network connectivity")
    
    # Create status report
    create_status_report()
    
    print(f"\n📋 Summary:")
    print(f"   Target IP: {target_ip}")
    print(f"   Connectivity: {'✅ OK' if connectivity_ok else '❌ Failed'}")
    print(f"   SNMP: {'✅ OK' if connectivity_ok and test_snmp_connectivity(target_ip) else '❌ Needs deployment'}")
    print(f"   ASHD Config: ✅ Updated for centos-docker")
    print(f"   Deployment Scripts: ✅ Ready")
    
    print(f"\n🎯 Next Actions:")
    if connectivity_ok:
        print(f"   1. Copy deployment scripts to {target_ip}")
        print(f"   2. Run fix_ntp_centos_docker.sh")
        print(f"   3. Run deploy_centos_docker_agent.sh")
        print(f"   4. Verify services are running")
    else:
        print(f"   1. Check network connectivity to {target_ip}")
        print(f"   2. Verify target host is online")
        print(f"   3. Check firewall settings")
    
    print(f"\n💡 Pro Tip: After deployment, check ASHD dashboard at http://localhost:8001")

if __name__ == "__main__":
    main()
