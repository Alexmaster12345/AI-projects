#!/usr/bin/env python3
"""
Test common SNMP devices and configurations for ASHD
"""

import subprocess
import socket

def test_snmp_device(host, community='public', port=161, description=''):
    """Test SNMP connectivity to a device."""
    print(f"\n🔍 Testing {description or host}...")
    
    # First test basic connectivity
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        print(f"   ✅ Network connectivity to {host}:{port} OK")
    except Exception as e:
        print(f"   ❌ Network connectivity failed: {e}")
        return False
    
    # Test SNMP
    try:
        cmd = [
            'snmpwalk', '-v2c', '-c', community,
            '-t', '2', '-r', '1',
            f'{host}:{port}',
            '1.3.6.1.2.1.1.1.0'  # sysDescr.0
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print(f"   ✅ SNMP response OK")
            print(f"   📄 System: {result.stdout.split('=')[-1].strip()}")
            return True
        else:
            print(f"   ❌ SNMP failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"   ❌ SNMP timeout")
        return False
    except FileNotFoundError:
        print(f"   ⚠️  snmpwalk not found. Install NET-SNMP tools")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🔧 ASHD SNMP Device Discovery")
    print("=" * 40)
    
    # Common devices to test
    test_devices = [
        ("localhost", "public", 161, "Local SNMP service"),
        ("127.0.0.1", "public", 161, "Localhost (IP)"),
        ("192.168.1.1", "public", 161, "Typical router/gateway"),
        ("192.168.1.1", "admin", 161, "Router with admin community"),
        ("192.168.0.1", "public", 161, "Alternative gateway"),
        ("10.0.0.1", "public", 161, "Enterprise gateway"),
    ]
    
    working_devices = []
    
    for host, community, port, desc in test_devices:
        if test_snmp_device(host, community, port, desc):
            working_devices.append((host, community, port, desc))
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Working devices: {len(working_devices)}")
    
    if working_devices:
        print(f"\n🎯 Recommended configuration:")
        for host, community, port, desc in working_devices:
            print(f"\n   Option: {desc}")
            print(f"   SNMP_HOST={host}")
            print(f"   SNMP_PORT={port}")
            print(f"   SNMP_COMMUNITY={community}")
            print(f"   SNMP_TIMEOUT_SECONDS=2")
        
        print(f"\n💡 To configure, run:")
        print(f"   python scripts/setup_snmp.py")
        print(f"   And enter one of the working hosts above")
    else:
        print(f"\n❌ No working SNMP devices found")
        print(f"\n🔧 Troubleshooting:")
        print(f"   1. Install NET-SNMP tools: sudo apt-get install snmp")
        print(f"   2. Check if SNMP service is running on target devices")
        print(f"   3. Verify community strings")
        print(f"   4. Check firewall rules (UDP 161)")
        print(f"   5. Try specific device IPs instead of hostnames")

if __name__ == "__main__":
    main()
