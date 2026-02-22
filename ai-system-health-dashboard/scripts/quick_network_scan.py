#!/usr/bin/env python3
"""
Quick Network Scan for ASHD Network Monitoring
"""

import subprocess
import socket

def scan_specific_network():
    """Scan specific network ranges for active devices."""
    print("🔍 Scanning common network ranges...")
    
    # Common network ranges to scan
    networks = [
        "192.168.50",
        "192.168.1", 
        "192.168.0",
        "10.0.0",
        "172.16.0"
    ]
    
    all_active = {}
    
    for network in networks:
        print(f"\n📡 Scanning {network}.x network...")
        active_hosts = []
        
        # Scan key hosts in each network
        key_hosts = [1, 254, 1, 100, 200, 225]  # Common gateway/important IPs
        
        for i in key_hosts:
            host = f"{network}.{i}"
            try:
                # Quick ping test
                result = subprocess.run(['ping', '-c', '1', '-W', '1', host], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    active_hosts.append(host)
                    print(f"   ✅ {host} - Active")
            except:
                pass
        
        if active_hosts:
            all_active[network] = active_hosts
            print(f"   📊 Found {len(active_hosts)} active hosts")
    
    return all_active

def test_snmp_on_hosts(all_hosts):
    """Test SNMP on all active hosts."""
    print(f"\n🐌 Testing SNMP on active hosts...")
    
    snmp_devices = []
    
    for network, hosts in all_hosts.items():
        print(f"\n📡 Testing {network}.x network...")
        
        for host in hosts:
            try:
                # Test SNMP
                cmd = ['snmpwalk', '-v2c', '-c', 'public', '-t', '2', 
                       '-r', '1', f'{host}:161', '1.3.6.1.2.1.1.1.0']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                
                if result.returncode == 0:
                    system_info = result.stdout.split('=')[-1].strip()
                    print(f"   ✅ {host} - SNMP OK ({system_info[:40]}...)")
                    snmp_devices.append({
                        'host': host,
                        'network': network,
                        'info': system_info
                    })
                else:
                    print(f"   ❌ {host} - SNMP failed")
            except:
                print(f"   ❌ {host} - SNMP timeout")
    
    return snmp_devices

def configure_for_monitoring(snmp_devices):
    """Configure ASHD for the best SNMP device."""
    if not snmp_devices:
        print(f"\n❌ No SNMP devices found")
        return False
    
    print(f"\n🎯 Found {len(snmp_devices)} SNMP devices:")
    
    for i, device in enumerate(snmp_devices, 1):
        print(f"   {i}. {device['host']} ({device['network']}.x)")
        print(f"      {device['info'][:60]}...")
    
    # Select best device (first one for simplicity)
    best_device = snmp_devices[0]
    
    print(f"\n🚀 Configuring ASHD to monitor: {best_device['host']}")
    
    # Update .env file
    env_path = '.env'
    env_vars = {}
    
    # Read existing .env
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except:
        pass
    
    # Update SNMP settings
    env_vars['SNMP_HOST'] = best_device['host']
    env_vars['SNMP_PORT'] = '161'
    env_vars['SNMP_COMMUNITY'] = 'public'
    env_vars['SNMP_TIMEOUT_SECONDS'] = '3'
    
    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ ASHD configured for SNMP monitoring:")
    print(f"   Device: {best_device['host']}")
    print(f"   Network: {best_device['network']}.x")
    print(f"   Community: public")
    print(f"   Port: 161")
    
    return True

def main():
    print("🌐 ASHD Quick Network Setup")
    print("=" * 40)
    print("For: Network Performance Monitoring, Fault Detection, Device Inventory")
    
    # Scan networks
    all_active = scan_specific_network()
    
    if not all_active:
        print(f"\n❌ No active hosts found on any network")
        print(f"   Check network connectivity")
        return
    
    total_active = sum(len(hosts) for hosts in all_active.values())
    print(f"\n📊 Total active hosts found: {total_active}")
    
    # Test SNMP
    snmp_devices = test_snmp_on_hosts(all_active)
    
    if not snmp_devices:
        print(f"\n❌ No SNMP devices found")
        print(f"\n🔧 Options:")
        print(f"1. Enable SNMP on network devices")
        print(f"2. Use SNMP simulator for testing")
        
        use_simulator = input("\nUse SNMP simulator? (y/n) [y]: ").strip().lower()
        if use_simulator != 'n':
            print(f"\n🚀 Setup SNMP simulator:")
            print(f"   python scripts/snmp_simulator.py")
            print(f"   Then: python scripts/setup_snmp.py")
            print(f"   Enter: localhost")
        return
    
    # Configure ASHD
    if configure_for_monitoring(snmp_devices):
        print(f"\n✅ Setup complete!")
        print(f"\n🔄 Next Steps:")
        print(f"1. Restart ASHD server:")
        print(f"   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        print(f"2. Open dashboard: http://localhost:8001")
        print(f"3. Check SNMP status in Configuration")
        print(f"4. Monitor network performance!")
        
        print(f"\n🎯 Monitoring Features:")
        print(f"• Real-time device availability")
        print(f"• SNMP response time tracking")
        print(f"• Network fault detection")
        print(f"• Device inventory management")
        print(f"• Historical performance data")

if __name__ == "__main__":
    main()
