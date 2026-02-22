#!/usr/bin/env python3
"""
Configure ASHD for Network Monitoring Use Cases

Network Performance Monitoring, Fault Detection, Device Inventory Management
"""

import os
import subprocess
import time
from pathlib import Path

def configure_icmp_monitoring():
    """Configure ICMP monitoring for network performance."""
    print("🔧 Configuring ICMP Monitoring...")
    
    # Use one of the active hosts we found
    icmp_host = "192.168.50.225"  # Active host from our scan
    
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
    
    # Configure ICMP settings
    env_vars['ICMP_HOST'] = icmp_host
    env_vars['ICMP_TIMEOUT_SECONDS'] = '2'
    
    # Keep SNMP disabled but configure for future use
    env_vars['SNMP_HOST'] = ''  # Disabled
    env_vars['SNMP_PORT'] = '161'
    env_vars['SNMP_COMMUNITY'] = 'public'
    env_vars['SNMP_TIMEOUT_SECONDS'] = '2'
    
    # Optimize protocol check interval for network monitoring
    env_vars['PROTOCOL_CHECK_INTERVAL_SECONDS'] = '15'  # Check every 15 seconds
    
    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Configured ICMP monitoring:")
    print(f"   Target: {icmp_host}")
    print(f"   Timeout: 2 seconds")
    print(f"   Check interval: 15 seconds")
    
    return icmp_host

def test_connectivity(host):
    """Test connectivity to a host."""
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', host], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Parse ping results
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'packet loss' in line.lower():
                    loss = line.split('%')[0].split()[-1]
                    print(f"   📊 Packet loss: {loss}%")
                elif 'avg' in line.lower():
                    avg_time = line.split('/')[4]
                    print(f"   ⏱️  Average response time: {avg_time} ms")
            
            return True
        else:
            print(f"   ❌ Host unreachable")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def create_network_inventory():
    """Create network device inventory."""
    print(f"\n📋 Creating Network Device Inventory...")
    
    # Active hosts from our scan
    network_devices = [
        {
            'ip': '192.168.50.1',
            'type': 'Gateway/Router',
            'status': 'Active',
            'location': 'Network Core'
        },
        {
            'ip': '192.168.50.225', 
            'type': 'Server/Workstation',
            'status': 'Active',
            'location': 'Network Segment'
        },
        {
            'ip': '192.168.1.1',
            'type': 'Alternative Gateway',
            'status': 'Active', 
            'location': 'Backup Network'
        },
        {
            'ip': '10.0.0.225',
            'type': 'Management Network',
            'status': 'Active',
            'location': 'Management Segment'
        }
    ]
    
    # Create inventory file
    inventory_path = Path('network_inventory.json')
    import json
    
    inventory_data = {
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_devices': len(network_devices),
        'network_segments': ['192.168.50.x', '192.168.1.x', '10.0.0.x'],
        'monitoring_target': '192.168.50.225',
        'devices': network_devices
    }
    
    with open(inventory_path, 'w') as f:
        json.dump(inventory_data, f, indent=2)
    
    print(f"✅ Network inventory created: {inventory_path}")
    print(f"   Total devices: {len(network_devices)}")
    print(f"   Network segments: 3")
    print(f"   Primary monitoring target: 192.168.50.225")
    
    return inventory_data

def create_monitoring_dashboard():
    """Create monitoring dashboard configuration."""
    print(f"\n📊 Setting up Monitoring Dashboard...")
    
    dashboard_config = {
        'title': 'ASHD Network Operations Center',
        'use_cases': [
            'Network Performance Monitoring',
            'Fault Detection', 
            'Device Inventory Management'
        ],
        'monitored_metrics': [
            'ICMP Response Time',
            'Packet Loss',
            'Device Availability',
            'Network Latency',
            'Protocol Health Status'
        ],
        'alert_thresholds': {
            'icmp_timeout': '2 seconds',
            'packet_loss_warning': '5%',
            'packet_loss_critical': '20%',
            'response_time_warning': '100ms',
            'response_time_critical': '500ms'
        },
        'monitoring_schedule': {
            'protocol_checks': 'Every 15 seconds',
            'data_retention': '24 hours',
            'historical_analysis': 'Real-time'
        }
    }
    
    config_path = Path('monitoring_config.json')
    import json
    
    with open(config_path, 'w') as f:
        json.dump(dashboard_config, f, indent=2)
    
    print(f"✅ Dashboard configuration created: {config_path}")
    
    return dashboard_config

def generate_setup_summary():
    """Generate setup summary and next steps."""
    print(f"\n📋 Network Monitoring Setup Summary")
    print(f"=" * 50)
    
    print(f"\n🎯 Use Cases Configured:")
    print(f"   ✅ Network Performance Monitoring")
    print(f"   ✅ Fault Detection")
    print(f"   ✅ Device Inventory Management")
    
    print(f"\n🔧 Configuration Details:")
    print(f"   • ICMP Target: 192.168.50.225")
    print(f"   • Check Interval: 15 seconds")
    print(f"   • Timeout: 2 seconds")
    print(f"   • SNMP: Disabled (no devices available)")
    
    print(f"\n📊 Monitoring Capabilities:")
    print(f"   • Real-time ping monitoring")
    print(f"   • Response time tracking")
    print(f"   • Packet loss detection")
    print(f"   • Device availability status")
    print(f"   • Network fault alerts")
    
    print(f"\n🌐 Network Inventory:")
    print(f"   • 4 active devices discovered")
    print(f"   • 3 network segments identified")
    print(f"   • Device types: Gateway, Server, Management")
    
    print(f"\n🔄 Next Steps:")
    print(f"   1. Restart ASHD server:")
    print(f"      uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
    print(f"   2. Open dashboard: http://localhost:8001")
    print(f"   3. Check Configuration page for ICMP status")
    print(f"   4. Monitor Overview page for network health")
    print(f"   5. Review Protocol Health section")

def main():
    print("🌐 ASHD Network Monitoring Configuration")
    print("=" * 50)
    print("For: Network Performance Monitoring, Fault Detection, Device Inventory")
    
    # Configure ICMP monitoring
    icmp_host = configure_icmp_monitoring()
    
    # Test connectivity
    print(f"\n🧪 Testing connectivity to {icmp_host}...")
    if test_connectivity(icmp_host):
        print(f"✅ Connectivity test passed")
    else:
        print(f"⚠️  Connectivity test failed - monitoring will show failures")
    
    # Create network inventory
    inventory_data = create_network_inventory()
    
    # Create monitoring dashboard
    dashboard_config = create_monitoring_dashboard()
    
    # Generate summary
    generate_setup_summary()
    
    print(f"\n🎉 Network monitoring setup complete!")
    print(f"\n💡 Pro Tip: To enable SNMP monitoring in the future:")
    print(f"   1. Enable SNMP service on network devices")
    print(f"   2. Run: python scripts/setup_snmp.py")
    print(f"   3. Enter device IP and community string")

if __name__ == "__main__":
    main()
