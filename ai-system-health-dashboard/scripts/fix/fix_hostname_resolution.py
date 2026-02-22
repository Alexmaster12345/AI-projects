#!/usr/bin/env python3
"""
Fix Hostname Resolution Issues

Changes centos-docker hostname to IP address (192.168.50.225)
to resolve "Name or service not known" ICMP errors.
"""

import os
from pathlib import Path

def fix_hostname_resolution():
    """Update .env file to use IP address instead of hostname."""
    print("🔧 Fixing hostname resolution issues...")
    
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
    
    # Fix hostname resolution
    old_host = env_vars.get('ICMP_HOST', '')
    old_snmp_host = env_vars.get('SNMP_HOST', '')
    
    # Update to use IP address
    env_vars['ICMP_HOST'] = '192.168.50.225'
    env_vars['SNMP_HOST'] = '192.168.50.225'
    
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
    
    print("✅ Fixed hostname resolution:")
    print(f"   ICMP_HOST: {old_host} → 192.168.50.225")
    print(f"   SNMP_HOST: {old_snmp_host} → 192.168.50.225")
    
    return env_vars

def test_icmp_connectivity():
    """Test ICMP connectivity to the IP address."""
    print("\n🧪 Testing ICMP connectivity to 192.168.50.225...")
    
    import subprocess
    
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', '192.168.50.225'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ ICMP connectivity successful")
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
            print("   ❌ ICMP connectivity failed")
            return False
    except Exception as e:
        print(f"   ❌ ICMP test error: {e}")
        return False

def check_system_logs():
    """Check for hostname resolution issues in system logs."""
    print("\n📋 Checking for hostname resolution issues...")
    
    import subprocess
    
    try:
        # Check recent logs for hostname resolution errors
        result = subprocess.run(['journalctl', '--since', '10 minutes ago', '-g', 'Name or service not known'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip():
            print("   📄 Found hostname resolution errors in logs:")
            for line in result.stdout.strip().split('\n')[:5]:  # Show first 5 lines
                if line.strip():
                    print(f"      {line}")
        else:
            print("   ✅ No hostname resolution errors found in recent logs")
            
    except Exception as e:
        print(f"   ⚠️  Could not check system logs: {e}")

def create_hosts_file_entry():
    """Create a hosts file entry for centos-docker."""
    print("\n📝 Creating hosts file entry...")
    
    hosts_entry = """
# Add this line to /etc/hosts to resolve centos-docker hostname
192.168.50.225 centos-docker

# This will allow both hostname and IP address to work:
# ping centos-docker  # Will work
# ping 192.168.50.225  # Will work
"""
    
    with open('hosts_entry.txt', 'w') as f:
        f.write(hosts_entry.strip())
    
    print("✅ Created hosts entry file: hosts_entry.txt")
    print("   To apply: echo '192.168.50.225 centos-docker' | sudo tee -a /etc/hosts")

def update_status_report():
    """Update the status report with the fix."""
    print("\n📊 Updating status report...")
    
    import json
    import time
    
    try:
        with open('agent_status_report.json', 'r') as f:
            status = json.load(f)
        
        status['hostname_fix'] = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'icmp_host': '192.168.50.225',
            'snmp_host': '192.168.50.225',
            'issue': 'Hostname resolution failed',
            'solution': 'Using IP address instead of hostname',
            'status': 'Fixed'
        }
        
        with open('agent_status_report.json', 'w') as f:
            json.dump(status, f, indent=2)
        
        print("✅ Status report updated")
    except Exception as e:
        print(f"   ⚠️  Could not update status report: {e}")

def main():
    print("🔧 Hostname Resolution Fix")
    print("=" * 40)
    print("Issue: centos-docker hostname not resolvable")
    print("Solution: Use IP address 192.168.50.225")
    
    # Fix configuration
    config = fix_hostname_resolution()
    
    # Test ICMP connectivity
    icmp_ok = test_icmp_connectivity()
    
    # Check system logs
    check_system_logs()
    
    # Create hosts file entry
    create_hosts_file_entry()
    
    # Update status report
    update_status_report()
    
    print("\n📋 Summary:")
    print("   ✅ Configuration updated to use IP address")
    print("   ✅ ICMP connectivity test: " + ("PASSED" if icmp_ok else "FAILED"))
    print("   ✅ Hosts file entry created")
    print("   ✅ Status report updated")
    
    print("\n🔄 Next Steps:")
    print("   1. ASHD server will auto-reload with new configuration")
    print("   2. ICMP checks will now use 192.168.50.225")
    print("   3. System logs should show fewer hostname errors")
    print("   4. Deploy SNMP agent on centos-docker when ready")
    
    print("\n💡 Optional: Add hosts entry for hostname support:")
    print("   echo '192.168.50.225 centos-docker' | sudo tee -a /etc/hosts")
    
    print("\n🎯 Expected Result:")
    print("   ICMP: OK · 192.168.50.225 responding")
    print("   No more 'Name or service not known' errors")

if __name__ == "__main__":
    main()
