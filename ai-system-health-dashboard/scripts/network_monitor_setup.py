#!/usr/bin/env python3
"""
ASHD Network Monitoring Setup for Network Operations

Configures ASHD for:
- Network Performance Monitoring
- Fault Detection  
- Device Inventory Management
"""

import os
import subprocess
import socket
from pathlib import Path

def scan_network(network_range="192.168.1"):
    """Scan network for active devices."""
    print(f"🔍 Scanning network {network_range}.x for active devices...")
    
    active_hosts = []
    for i in range(1, 255):
        host = f"{network_range}.{i}"
        try:
            # Quick ping test
            result = subprocess.run(['ping', '-c', '1', '-W', '1', host], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                active_hosts.append(host)
                print(f"   ✅ {host} - Active")
        except:
            pass
    
    return active_hosts

def test_snmp_on_hosts(hosts, community='public'):
    """Test SNMP on multiple hosts."""
    print(f"\n🐌 Testing SNMP on {len(hosts)} active hosts...")
    
    snmp_hosts = []
    for host in hosts:
        try:
            # Test SNMP with timeout
            cmd = ['snmpwalk', '-v2c', '-c', community, '-t', '2', 
                   '-r', '1', f'{host}:161', '1.3.6.1.2.1.1.1.0']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            
            if result.returncode == 0:
                system_info = result.stdout.split('=')[-1].strip()
                print(f"   ✅ {host} - SNMP OK ({system_info[:50]}...)")
                snmp_hosts.append(host)
            else:
                print(f"   ❌ {host} - SNMP failed")
        except:
            print(f"   ❌ {host} - SNMP timeout")
    
    return snmp_hosts

def get_device_info(host, community='public'):
    """Get detailed device information via SNMP."""
    device_info = {
        'host': host,
        'ip': host,
        'system_description': '',
        'system_name': '',
        'system_uptime': '',
        'system_location': '',
        'interfaces': []
    }
    
    try:
        # System Description
        cmd = ['snmpwalk', '-v2c', '-c', community, '-t', '2', 
               f'{host}:161', '1.3.6.1.2.1.1.1.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            device_info['system_description'] = result.stdout.split('=')[-1].strip()
        
        # System Name
        cmd = ['snmpwalk', '-v2c', '-c', community, '-t', '2', 
               f'{host}:161', '1.3.6.1.2.1.1.5.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            device_info['system_name'] = result.stdout.split('=')[-1].strip()
        
        # System Location
        cmd = ['snmpwalk', '-v2c', '-c', community, '-t', '2', 
               f'{host}:161', '1.3.6.1.2.1.1.6.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            device_info['system_location'] = result.stdout.split('=')[-1].strip()
        
        # Interface Count
        cmd = ['snmpwalk', '-v2c', '-c', community, '-t', '2', 
               f'{host}:161', '1.3.6.1.2.1.2.1.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            device_info['interface_count'] = len(result.stdout.strip().split('\n'))
        
    except Exception as e:
        print(f"   ⚠️  Error getting info for {host}: {e}")
    
    return device_info

def configure_ashd_snmp(primary_host, community='public', port=161):
    """Configure ASHD for SNMP monitoring."""
    env_path = Path('.env')
    
    # Read existing .env
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update SNMP configuration
    env_vars['SNMP_HOST'] = primary_host
    env_vars['SNMP_PORT'] = str(port)
    env_vars['SNMP_COMMUNITY'] = community
    env_vars['SNMP_TIMEOUT_SECONDS'] = '3'  # Slightly longer for network monitoring
    
    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Configured ASHD for SNMP monitoring:")
    print(f"   Primary device: {primary_host}")
    print(f"   Community: {community}")
    print(f"   Port: {port}")
    print(f"   Timeout: 3 seconds")

def generate_inventory_report(devices):
    """Generate device inventory report."""
    report_path = Path('network_inventory.md')
    
    with open(report_path, 'w') as f:
        f.write("# Network Device Inventory\n\n")
        f.write(f"Generated: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}\n\n")
        f.write(f"Total Devices: {len(devices)}\n\n")
        
        f.write("## Device Details\n\n")
        f.write("| IP Address | Device Name | Type | Location | Status |\n")
        f.write("|------------|-------------|------|----------|--------|\n")
        
        for device in devices:
            name = device.get('system_name', 'Unknown')
            desc = device.get('system_description', '')
            location = device.get('system_location', 'Unknown')
            
            # Determine device type from description
            device_type = 'Unknown'
            if 'cisco' in desc.lower():
                device_type = 'Cisco Switch/Router'
            elif 'linux' in desc.lower():
                device_type = 'Linux Server'
            elif 'windows' in desc.lower():
                device_type = 'Windows Server'
            elif 'printer' in desc.lower():
                device_type = 'Printer'
            elif 'ups' in desc.lower():
                device_type = 'UPS'
            
            f.write(f"| {device['host']} | {name} | {device_type} | {location} | ✅ Active |\n")
        
        f.write(f"\n## Monitoring Configuration\n\n")
        f.write(f"- **Primary SNMP Device**: {devices[0]['host'] if devices else 'None'}\n")
        f.write(f"- **SNMP Community**: public\n")
        f.write(f"- **Monitoring Tool**: ASHD Dashboard\n")
        f.write(f"- **Dashboard URL**: http://localhost:8001\n")
        
        f.write(f"\n## Network Performance Metrics\n\n")
        f.write(f"ASHD will monitor:\n")
        f.write(f"- Device availability and uptime\n")
        f.write(f"- SNMP response times\n")
        f.write(f"- Network connectivity status\n")
        f.write(f"- Protocol health checks (NTP, ICMP, SNMP)\n")
        
        f.write(f"\n## Fault Detection\n\n")
        f.write(f"ASHD will detect:\n")
        f.write(f"- Device failures and timeouts\n")
        f.write(f"- Network connectivity issues\n")
        f.write(f"- SNMP service problems\n")
        f.write(f"- Protocol check failures\n")
        
        f.write(f"\n## Recommendations\n\n")
        f.write(f"1. **Primary Monitoring**: Configure ASHD to monitor the most critical device\n")
        f.write(f"2. **Backup Monitoring**: Consider additional monitoring for redundancy\n")
        f.write(f"3. **Alerting**: Set up notifications for device failures\n")
        f.write(f"4. **Documentation**: Keep this inventory updated\n")
        f.write(f"5. **Security**: Change default SNMP community strings\n")
    
    print(f"📄 Inventory report saved to: {report_path}")

def main():
    print("🌐 ASHD Network Monitoring Setup")
    print("=" * 50)
    print("Use Cases:")
    print("• Network Performance Monitoring")
    print("• Fault Detection")
    print("• Device Inventory Management")
    print("=" * 50)
    
    # Get network range
    network_range = input("Enter network range (e.g., 192.168.1) [192.168.1]: ").strip()
    if not network_range:
        network_range = "192.168.1"
    
    # Scan network
    active_hosts = scan_network(network_range)
    
    if not active_hosts:
        print(f"❌ No active hosts found on {network_range}.x network")
        print("   Check network connectivity and try again")
        return
    
    print(f"\n📊 Found {len(active_hosts)} active hosts")
    
    # Test SNMP on active hosts
    snmp_hosts = test_snmp_on_hosts(active_hosts)
    
    if not snmp_hosts:
        print(f"\n❌ No SNMP devices found")
        print(f"\n🔧 Options:")
        print(f"1. Enable SNMP on network devices")
        print(f"2. Use SNMP simulator for testing")
        print(f"3. Try different community strings")
        
        use_simulator = input("\nUse SNMP simulator for testing? (y/n) [y]: ").strip().lower()
        if use_simulator != 'n':
            print(f"\n🚀 Starting SNMP simulator...")
            print(f"   Run: python scripts/snmp_simulator.py")
            print(f"   Then configure ASHD with: localhost")
            return
        else:
            return
    
    print(f"\n🎯 Found {len(snmp_hosts)} SNMP-enabled devices")
    
    # Get device information
    print(f"\n📋 Gathering device information...")
    devices = []
    for host in snmp_hosts[:5]:  # Limit to first 5 for demo
        device_info = get_device_info(host)
        devices.append(device_info)
    
    # Display devices
    print(f"\n📊 Device Inventory:")
    for i, device in enumerate(devices, 1):
        print(f"   {i}. {device['host']}")
        print(f"      Name: {device.get('system_name', 'Unknown')}")
        print(f"      Type: {device.get('system_description', 'Unknown')[:60]}...")
        print(f"      Location: {device.get('system_location', 'Unknown')}")
        print()
    
    # Select primary monitoring device
    if len(devices) > 1:
        print(f"Select primary device for ASHD monitoring:")
        for i, device in enumerate(devices, 1):
            print(f"   {i}. {device['host']} ({device.get('system_name', 'Unknown')})")
        
        try:
            choice = int(input(f"Enter choice (1-{len(devices)}) [1]: ").strip() or "1")
            if 1 <= choice <= len(devices):
                primary_device = devices[choice-1]['host']
            else:
                primary_device = devices[0]['host']
        except:
            primary_device = devices[0]['host']
    else:
        primary_device = devices[0]['host']
    
    # Configure ASHD
    configure_ashd_snmp(primary_device)
    
    # Generate inventory report
    generate_inventory_report(devices)
    
    print(f"\n✅ Network monitoring setup complete!")
    print(f"\n🔄 Next Steps:")
    print(f"1. Restart ASHD server:")
    print(f"   - Stop current server (Ctrl+C)")
    print(f"   - Start: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
    print(f"2. Check dashboard: http://localhost:8001")
    print(f"3. Verify SNMP status in Configuration page")
    print(f"4. Review inventory report: network_inventory.md")
    
    print(f"\n🎯 Monitoring Capabilities:")
    print(f"• Real-time device availability")
    print(f"• SNMP response time monitoring")
    print(f"• Network fault detection")
    print(f"• Device inventory tracking")
    print(f"• Historical performance data")

if __name__ == "__main__":
    main()
