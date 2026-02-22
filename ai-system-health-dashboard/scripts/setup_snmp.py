#!/usr/bin/env python3
"""
SNMP Configuration Setup Script for ASHD

This script helps configure SNMP monitoring for the ASHD dashboard.
It can test SNMP connectivity and update the .env file.
"""

import os
import sys
import subprocess
from pathlib import Path

def test_snmp(host, community='public', port=161, timeout=2):
    """Test SNMP connectivity to a host."""
    try:
        # Try to use snmpwalk to test connectivity
        cmd = [
            'snmpwalk', '-v2c', '-c', community,
            '-t', str(timeout),
            f'{host}:{port}',
            '1.3.6.1.2.1.1.1.0'  # sysDescr.0
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+2)
        
        if result.returncode == 0:
            print(f"✅ SNMP connection to {host} successful")
            print(f"   Response: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ SNMP connection to {host} failed")
            print(f"   Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ SNMP connection to {host} timed out")
        return False
    except FileNotFoundError:
        print("⚠️  snmpwalk command not found. Installing NET-SNMP tools...")
        print("   On Ubuntu/Debian: sudo apt-get install snmp")
        print("   On CentOS/RHEL: sudo yum install net-snmp-utils")
        print("   On macOS: brew install net-snmp")
        return False
    except Exception as e:
        print(f"❌ Error testing SNMP: {e}")
        return False

def update_env_file(host, community='public', port=161, timeout=2):
    """Update the .env file with SNMP configuration."""
    env_path = Path('.env')
    
    # Read existing .env file or create new one
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update SNMP variables
    env_vars['SNMP_HOST'] = host
    env_vars['SNMP_PORT'] = str(port)
    env_vars['SNMP_COMMUNITY'] = community
    env_vars['SNMP_TIMEOUT_SECONDS'] = str(timeout)
    
    # Write back to .env file
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Updated .env file with SNMP configuration:")
    print(f"   SNMP_HOST={host}")
    print(f"   SNMP_PORT={port}")
    print(f"   SNMP_COMMUNITY={community}")
    print(f"   SNMP_TIMEOUT_SECONDS={timeout}")

def main():
    print("🔧 ASHD SNMP Configuration Setup")
    print("=" * 40)
    
    # Check if .env exists
    env_path = Path('.env')
    if not env_path.exists():
        print("⚠️  .env file not found. Creating new one...")
        if Path('.env.example').exists():
            subprocess.run(['cp', '.env.example', '.env'])
            print("✅ Created .env from .env.example")
        else:
            print("❌ .env.example not found. Please create .env file manually.")
            return
    
    # Get current SNMP configuration
    current_host = os.getenv('SNMP_HOST', '')
    if current_host:
        print(f"📋 Current SNMP configuration:")
        print(f"   Host: {current_host}")
        print(f"   Port: {os.getenv('SNMP_PORT', '161')}")
        print(f"   Community: {os.getenv('SNMP_COMMUNITY', 'public')}")
        print()
    
    # Interactive configuration
    print("🎯 Configure SNMP Monitoring:")
    print("   Leave host empty to disable SNMP monitoring")
    
    host = input("SNMP Host (e.g., localhost, 192.168.1.1, switch.example.com): ").strip()
    
    if not host:
        print("🚫 SNMP monitoring disabled")
        # Remove SNMP configuration
        update_env_file('')
        return
    
    port = input(f"SNMP Port [161]: ").strip() or "161"
    community = input(f"SNMP Community [public]: ").strip() or "public"
    timeout = input(f"SNMP Timeout (seconds) [2]: ").strip() or "2"
    
    try:
        port = int(port)
        timeout = float(timeout)
    except ValueError:
        print("❌ Invalid port or timeout value")
        return
    
    print(f"\n🧪 Testing SNMP connection to {host}...")
    if test_snmp(host, community, port, timeout):
        print(f"\n💾 Updating configuration...")
        update_env_file(host, community, port, timeout)
        print(f"\n🔄 Please restart the ASHD server to apply changes:")
        print(f"   - Stop the current server (Ctrl+C)")
        print(f"   - Start again: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        print(f"\n✅ SNMP monitoring will be available after restart!")
    else:
        print(f"\n❌ SNMP test failed. Configuration not updated.")
        print(f"   Please check:")
        print(f"   - SNMP service is running on target device")
        print(f"   - Community string is correct")
        print(f"   - Network connectivity to target")
        print(f"   - Firewall allows SNMP (UDP 161)")

if __name__ == "__main__":
    main()
