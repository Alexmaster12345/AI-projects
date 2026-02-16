#!/usr/bin/env python3
"""
Update CentOS-Docker IP Address

Updates configuration to use the correct IP: 192.168.50.198
"""

import subprocess
from pathlib import Path

def update_configuration():
    """Update .env file with correct IP address."""
    print("🔧 Updating centos-docker IP address...")
    
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
    
    # Update to correct IP address
    old_ip = env_vars.get('ICMP_HOST', '')
    env_vars['ICMP_HOST'] = '192.168.50.198'
    env_vars['SNMP_HOST'] = '192.168.50.198'
    
    # Keep other settings
    env_vars['ICMP_TIMEOUT_SECONDS'] = '3'
    env_vars['SNMP_TIMEOUT_SECONDS'] = '5'
    env_vars['SNMP_COMMUNITY'] = 'public'
    env_vars['NTP_SERVER'] = 'pool.ntp.org'
    env_vars['PROTOCOL_CHECK_INTERVAL_SECONDS'] = '30'
    
    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print("✅ Updated IP address:")
    print(f"   ICMP_HOST: {old_ip} → 192.168.50.198")
    print(f"   SNMP_HOST: {old_ip} → 192.168.50.198")
    
    return env_vars

def update_hosts_file():
    """Update hosts file with correct IP address."""
    print("\n📝 Updating hosts file...")
    
    # Remove old entry and add new one
    try:
        # Read current hosts file
        with open('/etc/hosts', 'r') as f:
            hosts_content = f.read()
        
        # Remove old centos-docker entry
        lines = hosts_content.split('\n')
        new_lines = []
        for line in lines:
            if 'centos-docker' not in line:
                new_lines.append(line)
        
        # Add new entry
        new_lines.append('192.168.50.198 centos-docker')
        
        # Write back
        with open('/etc/hosts.tmp', 'w') as f:
            f.write('\n'.join(new_lines))
        
        # Apply with sudo
        subprocess.run(['sudo', 'mv', '/etc/hosts.tmp', '/etc/hosts'], check=True)
        
        print("✅ Updated hosts file:")
        print("   192.168.50.198 centos-docker")
        
    except Exception as e:
        print(f"   ⚠️  Could not update hosts file: {e}")
        print("   Manual update required:")
        print("   echo '192.168.50.198 centos-docker' | sudo tee -a /etc/hosts")

def test_connectivity():
    """Test connectivity to the correct IP address."""
    print("\n🧪 Testing connectivity to 192.168.50.198...")
    
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', '192.168.50.198'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ Connectivity successful")
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
            print("   ❌ Connectivity failed")
            return False
    except Exception as e:
        print(f"   ❌ Connectivity test error: {e}")
        return False

def test_hostname_resolution():
    """Test hostname resolution."""
    print("\n🧪 Testing hostname resolution...")
    
    try:
        result = subprocess.run(['ping', '-c', '2', '-W', '2', 'centos-docker'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ Hostname resolution successful")
            # Check if it resolves to correct IP
            if '192.168.50.198' in result.stdout:
                print("   ✅ Resolves to correct IP: 192.168.50.198")
            else:
                print("   ⚠️  Resolves to different IP")
            return True
        else:
            print("   ❌ Hostname resolution failed")
            return False
    except Exception as e:
        print(f"   ❌ Hostname test error: {e}")
        return False

def update_deployment_scripts():
    """Update deployment scripts with correct IP."""
    print("\n📝 Updating deployment scripts...")
    
    # Update deployment helper script
    try:
        with open('deploy_agent_manual.sh', 'r') as f:
            content = f.read()
        
        # Replace old IP with new IP
        content = content.replace('192.168.50.225', '192.168.50.198')
        
        with open('deploy_agent_manual.sh', 'w') as f:
            f.write(content)
        
        print("   ✅ Updated deploy_agent_manual.sh")
    except Exception as e:
        print(f"   ⚠️  Could not update deployment script: {e}")

def update_status_report():
    """Update status report with correct IP."""
    print("\n📊 Updating status report...")
    
    import json
    import time
    
    try:
        with open('agent_status_report.json', 'r') as f:
            status = json.load(f)
        
        status['ip_update'] = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'old_ip': '192.168.50.225',
            'new_ip': '192.168.50.198',
            'hostname': 'centos-docker',
            'reason': 'Correct IP address provided by user',
            'status': 'Updated'
        }
        status['target_ip'] = '192.168.50.198'
        
        with open('agent_status_report.json', 'w') as f:
            json.dump(status, f, indent=2)
        
        print("   ✅ Status report updated")
    except Exception as e:
        print(f"   ⚠️  Could not update status report: {e}")

def main():
    print("🔧 CentOS-Docker IP Address Update")
    print("=" * 50)
    print("Name: centos-docker")
    print("Address: 192.168.50.198")
    print("Updating from: 192.168.50.225")
    
    # Update configuration
    config = update_configuration()
    
    # Update hosts file
    update_hosts_file()
    
    # Test connectivity
    connectivity_ok = test_connectivity()
    
    # Test hostname resolution
    hostname_ok = test_hostname_resolution()
    
    # Update deployment scripts
    update_deployment_scripts()
    
    # Update status report
    update_status_report()
    
    print("\n📋 Summary:")
    print("   ✅ Configuration updated to 192.168.50.198")
    print("   ✅ Hosts file updated")
    print("   ✅ Connectivity test: " + ("PASSED" if connectivity_ok else "FAILED"))
    print("   ✅ Hostname resolution: " + ("PASSED" if hostname_ok else "FAILED"))
    print("   ✅ Deployment scripts updated")
    print("   ✅ Status report updated")
    
    print("\n🔄 Next Steps:")
    print("   1. ASHD server will auto-reload with new configuration")
    print("   2. ICMP checks will use 192.168.50.198")
    print("   3. Deploy SNMP agent to correct IP address")
    print("   4. Verify monitoring on dashboard")
    
    print("\n🎯 Expected Result:")
    print("   ICMP: OK · 192.168.50.198 responding")
    print("   SNMP: Ready for agent deployment")
    
    if connectivity_ok:
        print("\n🚀 Ready for agent deployment:")
        print("   scp deploy_centos_docker_agent.sh root@192.168.50.198:/root/")
        print("   ssh root@192.168.50.198")
        print("   sudo ./deploy_centos_docker_agent.sh")

if __name__ == "__main__":
    main()
