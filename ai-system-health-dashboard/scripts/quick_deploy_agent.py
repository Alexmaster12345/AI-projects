#!/usr/bin/env python3
"""
Quick Agent Deployment - Dashboard Integration

Creates deployment commands and provides a simple interface for agent installation.
"""

import json
import subprocess
import time
from pathlib import Path

def create_deployment_commands():
    """Create deployment commands for all discovered hosts."""
    print("🚀 Creating Deployment Commands")
    print("=" * 40)
    
    # Load discovery results
    try:
        with open('discovery_results.json', 'r') as f:
            discovery = json.load(f)
    except FileNotFoundError:
        print("❌ Discovery results not found")
        return
    
    # Create deployment commands for each host
    deployment_commands = {}
    
    for host in discovery['all_hosts']:
        ip = host['ip']
        
        # Try to detect OS or use default
        os_type = host.get('os_type', 'rocky')  # Default to rocky for centos-docker
        
        if ip == '192.168.50.198':
            os_type = 'rocky'  # centos-docker is Rocky Linux
        
        commands = f'''# Deploy ASHD Agent to {ip} ({os_type.title()})
# ================================================

# Step 1: Copy agent files to host
echo "📁 Copying agent files to {ip}..."
scp agents/{os_type}/ashd_agent.py root@{ip}:/opt/ashd-agent/
scp agents/{os_type}/deploy_{os_type}_agent.sh root@{ip}:/tmp/
scp agents/{os_type}/ashd-agent.service root@{ip}:/tmp/
scp agents/{os_type}/snmpd.conf root@{ip}:/tmp/

# Step 2: Execute deployment script
echo "🚀 Executing deployment script on {ip}..."
ssh root@{ip} 'chmod +x /tmp/deploy_{os_type}_agent.sh && /tmp/deploy_{os_type}_agent.sh'

# Step 3: Verify deployment
echo "🔍 Verifying deployment on {ip}..."
ssh root@{ip} 'systemctl status ashd-agent | head -5'
ssh root@{ip} 'systemctl status snmpd | head -5'
ssh root@{ip} 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'

# Step 4: Check ASHD dashboard
echo "🌐 Check ASHD dashboard: http://localhost:8001"
echo "   Look for {ip} in the monitoring data"
'''
        
        deployment_commands[ip] = {
            'ip': ip,
            'os_type': os_type,
            'commands': commands,
            'hostname': host.get('hostname', f'host-{ip.split(".")[-1]}')
        }
    
    # Save deployment commands
    with open('deployment_commands.json', 'w') as f:
        json.dump(deployment_commands, f, indent=2)
    
    print(f"✅ Created deployment commands for {len(deployment_commands)} hosts")
    
    # Create individual deployment scripts
    for ip, data in deployment_commands.items():
        script_path = Path(f'deploy_to_{ip.replace(".", "_")}.sh')
        with open(script_path, 'w') as f:
            f.write('#!/bin/bash\n')
            f.write(f'# Auto-generated deployment script for {ip}\n\n')
            f.write(data['commands'])
        
        script_path.chmod(0o755)
        print(f"   📝 Created: {script_path}")
    
    return deployment_commands

def create_interactive_deployment():
    """Create an interactive deployment interface."""
    print("\n🎯 Interactive Deployment Options")
    print("=" * 40)
    
    # Load deployment commands
    try:
        with open('deployment_commands.json', 'r') as f:
            commands = json.load(f)
    except FileNotFoundError:
        commands = create_deployment_commands()
    
    print("\nAvailable hosts for deployment:")
    for i, (ip, data) in enumerate(commands.items(), 1):
        print(f"  {i}. {ip} ({data['os_type'].title()}) - {data['hostname']}")
    
    print(f"\n📋 Deployment Options:")
    print(f"  1. Deploy to centos-docker (192.168.50.198)")
    print(f"  2. Deploy to all hosts")
    print(f"  3. Show commands for manual execution")
    print(f"  4. Exit")
    
    return commands

def deploy_to_centos_docker():
    """Deploy agent specifically to centos-docker."""
    print("🚀 Deploying to centos-docker (192.168.50.198)")
    print("=" * 50)
    
    ip = "192.168.50.198"
    os_type = "rocky"
    
    # Check if agent files exist
    agent_files = [
        f'agents/{os_type}/ashd_agent.py',
        f'agents/{os_type}/deploy_{os_type}_agent.sh',
        f'agents/{os_type}/ashd-agent.service',
        f'agents/{os_type}/snmpd.conf'
    ]
    
    for file_path in agent_files:
        if not Path(file_path).exists():
            print(f"❌ Agent file not found: {file_path}")
            return False
    
    print("✅ All agent files found")
    
    # Execute deployment commands
    commands = [
        f"echo '📁 Copying agent files to {ip}...'",
        f"scp agents/{os_type}/ashd_agent.py root@{ip}:/opt/ashd-agent/",
        f"scp agents/{os_type}/deploy_{os_type}_agent.sh root@{ip}:/tmp/",
        f"scp agents/{os_type}/ashd-agent.service root@{ip}:/tmp/",
        f"scp agents/{os_type}/snmpd.conf root@{ip}:/tmp/",
        f"echo '🚀 Executing deployment script...'",
        f"ssh root@{ip} 'chmod +x /tmp/deploy_{os_type}_agent.sh && /tmp/deploy_{os_type}_agent.sh'",
        f"echo '🔍 Verifying deployment...'",
        f"ssh root@{ip} 'systemctl status ashd-agent | head -5'",
        f"ssh root@{ip} 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'"
    ]
    
    for cmd in commands:
        print(f"\n> {cmd}")
        try:
            if cmd.startswith("echo"):
                print(cmd.split("'")[1])
            else:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print("✅ Success")
                    if result.stdout.strip():
                        print(result.stdout.strip())
                else:
                    print(f"❌ Failed: {result.stderr}")
                    return False
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout: {cmd}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    print(f"\n🎉 Deployment completed for {ip}")
    print(f"🌐 Check dashboard: http://localhost:8001")
    return True

def show_manual_commands():
    """Show manual deployment commands."""
    print("\n📋 Manual Deployment Commands")
    print("=" * 40)
    
    try:
        with open('deployment_commands.json', 'r') as f:
            commands = json.load(f)
    except FileNotFoundError:
        print("❌ Deployment commands not found")
        return
    
    for ip, data in commands.items():
        print(f"\n🖥️  {ip} ({data['os_type'].title()})")
        print("-" * 30)
        print(data['commands'])

def main():
    """Main interactive deployment function."""
    print("🚀 ASHD Agent Deployment System")
    print("=" * 40)
    
    # Create deployment commands
    commands = create_deployment_commands()
    
    while True:
        print("\n🎯 Deployment Options:")
        print("  1. Deploy to centos-docker (192.168.50.198)")
        print("  2. Show manual commands for all hosts")
        print("  3. Create individual deployment scripts")
        print("  4. Exit")
        
        try:
            choice = input("\nSelect option (1-4): ").strip()
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            break
        
        if choice == "1":
            deploy_to_centos_docker()
        elif choice == "2":
            show_manual_commands()
        elif choice == "3":
            print("✅ Individual scripts already created:")
            for ip in commands.keys():
                script_name = f"deploy_to_{ip.replace('.', '_')}.sh"
                print(f"   📝 {script_name}")
        elif choice == "4":
            print("👋 Exiting...")
            break
        else:
            print("❌ Invalid option. Please select 1-4.")

if __name__ == "__main__":
    main()
