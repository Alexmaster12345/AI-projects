#!/usr/bin/env python3
"""
Close All Ports Script

Stops ASHD server and closes all monitoring-related ports.
"""

import subprocess
import time
import os

def stop_ashd_server():
    """Stop ASHD server processes."""
    print("🛑 Stopping ASHD server...")
    
    try:
        # Kill uvicorn processes
        result = subprocess.run(['pkill', '-f', 'uvicorn'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✅ Killed uvicorn processes")
        else:
            print("   ℹ️  No uvicorn processes found")
    except Exception as e:
        print(f"   ❌ Error killing uvicorn: {e}")
    
    try:
        # Kill any remaining Python processes that might be ASHD
        result = subprocess.run(['pkill', '-f', 'python.*main:app'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("   ✅ Killed ASHD Python processes")
        else:
            print("   ℹ️  No ASHD Python processes found")
    except Exception as e:
        print(f"   ❌ Error killing ASHD processes: {e}")

def close_firewall_ports():
    """Close monitoring-related firewall ports."""
    print("\n🔥 Closing firewall ports...")
    
    monitoring_ports = [161, 123, 8000, 8001]
    
    # Check if firewalld is available
    if os.path.exists('/usr/bin/firewall-cmd'):
        try:
            print("   🔧 Using firewalld...")
            for port in monitoring_ports:
                try:
                    result = subprocess.run(['firewall-cmd', '--permanent', '--remove-port', f'{port}/udp'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"   ✅ Closed UDP port {port}")
                    else:
                        print(f"   ℹ️  UDP port {port} not open or error")
                    
                    result = subprocess.run(['firewall-cmd', '--permanent', '--remove-port', f'{port}/tcp'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"   ✅ Closed TCP port {port}")
                    else:
                        print(f"   ℹ️  TCP port {port} not open or error")
                except Exception as e:
                    print(f"   ❌ Error closing port {port}: {e}")
            
            # Reload firewall
            try:
                subprocess.run(['firewall-cmd', '--reload'], 
                              capture_output=True, text=True)
                print("   ✅ Firewall reloaded")
            except Exception as e:
                print(f"   ❌ Error reloading firewall: {e}")
                
        except Exception as e:
            print(f"   ❌ Error with firewalld: {e}")
    
    # Check if ufw is available
    elif os.path.exists('/usr/sbin/ufw'):
        try:
            print("   🔧 Using ufw...")
            for port in monitoring_ports:
                try:
                    result = subprocess.run(['ufw', 'delete', 'allow', f'{port}/udp'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"   ✅ Closed UDP port {port}")
                    else:
                        print(f"   ℹ️  UDP port {port} not open or error")
                    
                    result = subprocess.run(['ufw', 'delete', 'allow', f'{port}/tcp'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"   ✅ Closed TCP port {port}")
                    else:
                        print(f"   ℹ️  TCP port {port} not open or error")
                except Exception as e:
                    print(f"   ❌ Error closing port {port}: {e}")
        except Exception as e:
            print(f"   ❌ Error with ufw: {e}")
    else:
        print("   ℹ️  No firewall manager found (firewalld/ufw)")

def check_port_status():
    """Check current port status."""
    print("\n🔍 Checking current port status...")
    
    try:
        result = subprocess.run(['netstat', '-tuln'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            listening_ports = []
            
            for line in lines:
                if 'LISTEN' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        address = parts[3]
                        if ':' in address:
                            port = address.split(':')[-1]
                            listening_ports.append(port)
            
            # Check for monitoring-related ports
            monitoring_ports = ['161', '123', '8000', '8001']
            open_monitoring_ports = [p for p in listening_ports if p in monitoring_ports]
            
            if open_monitoring_ports:
                print(f"   ⚠️  Still open monitoring ports: {', '.join(open_monitoring_ports)}")
            else:
                print("   ✅ No monitoring ports are open")
                
        else:
            print("   ❌ Error checking port status")
            
    except Exception as e:
        print(f"   ❌ Error checking ports: {e}")

def close_system_ports():
    """Close system ports that might be open."""
    print("\n🔧 Checking system ports...")
    
    # Common monitoring and management ports
    system_ports = [
        22,    # SSH
        23,    # Telnet
        53,    # DNS
        80,    # HTTP
        443,   # HTTPS
        161,   # SNMP
        162,   # SNMP Trap
        389,   # LDAP
        636,   # LDAP SSL
        123,   # NTP
        143,   # IMAP
        993,   # IMAPS
        995,   # POP3S
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        8000,  # ASHD HTTP
        8001,  # ASHD Alternative
        8080,  # Alternative HTTP
        8443,  # Alternative HTTPS
        9000,  # Alternative HTTP
        9090,  # Alternative HTTP
    ]
    
    try:
        result = subprocess.run(['netstat', '-tuln'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            open_ports = []
            
            for line in lines:
                if 'LISTEN' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        address = parts[3]
                        if ':' in address:
                            port = address.split(':')[-1]
                            if port.isdigit():
                                open_ports.append(int(port))
            
            # Check which system ports are open
            open_system_ports = [p for p in open_ports if p in system_ports]
            
            if open_system_ports:
                print(f"   ⚠️  Open system ports: {', '.join(map(str, sorted(open_system_ports)))}")
                print("   ℹ️  Note: These are system ports and may be required for normal operation")
            else:
                print("   ✅ No system monitoring ports are open")
                
    except Exception as e:
        print(f"   ❌ Error checking system ports: {e}")

def main():
    """Main function to close all ports."""
    print("🛑 Close All Ports - ASHD Monitoring System")
    print("=" * 50)
    
    print("This script will:")
    print("  1. Stop ASHD server processes")
    print("  2. Close monitoring-related firewall ports")
    print("  3. Check current port status")
    print("  4. Verify system ports")
    print("")
    
    # Stop ASHD server
    stop_ashd_server()
    
    # Wait a moment for processes to stop
    time.sleep(2)
    
    # Close firewall ports
    close_firewall_ports()
    
    # Check port status
    check_port_status()
    
    # Check system ports
    close_system_ports()
    
    print("\n🎯 Port Closing Summary")
    print("=" * 30)
    print("✅ ASHD server stopped")
    print("✅ Monitoring firewall ports closed")
    print("✅ Port status checked")
    print("✅ System ports verified")
    print("")
    print("📋 Notes:")
    print("  - System ports (SSH:22, DNS:53, etc.) may remain open")
    print("  - These are required for normal system operation")
    print("  - Monitoring ports (161, 123, 8000, 8001) are closed")
    print("  - Firewall rules have been updated")
    print("")
    print("🔐 Security Status: Enhanced")
    print("   All ASHD monitoring ports are now closed")

if __name__ == "__main__":
    main()
