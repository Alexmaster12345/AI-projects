#!/usr/bin/env python3
"""
Automated Agent Deployment for All Discovered Hosts

Deploys ASHD agents to all discovered hosts with automatic OS detection
and appropriate package installation.
"""

import json
import subprocess
import time
import os
from pathlib import Path
from typing import Dict, List, Optional

class AgentDeployer:
    def __init__(self):
        self.deployment_results = []
        self.agents_dir = Path('agents')
        
    def load_discovery_results(self) -> Dict:
        """Load discovery results from file."""
        try:
            with open('discovery_results.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ Discovery results not found. Run auto_discover_hosts.py first.")
            return {}
    
    def detect_host_os(self, ip: str) -> str:
        """Detect OS type for a host."""
        print(f"   🔍 Detecting OS for {ip}")
        
        try:
            # Try to detect OS via SSH
            result = subprocess.run([
                'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                f'root@{ip}', 
                'cat /etc/os-release | grep -E "^ID=" | cut -d= -f2 | tr -d \\"'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                os_id = result.stdout.strip().lower()
                if 'ubuntu' in os_id:
                    return 'ubuntu'
                elif 'debian' in os_id:
                    return 'debian'
                elif 'rhel' in os_id:
                    return 'rhel'
                elif 'centos' in os_id:
                    return 'centos'
                elif 'rocky' in os_id:
                    return 'rocky'
                else:
                    return 'unknown'
            else:
                return 'unknown'
                
        except Exception as e:
            print(f"     ⚠️  OS detection failed: {e}")
            return 'unknown'
    
    def deploy_agent_to_host(self, ip: str, os_type: str) -> Dict:
        """Deploy agent to a specific host."""
        print(f"🚀 Deploying agent to {ip} ({os_type})")
        
        result = {
            'ip': ip,
            'os_type': os_type,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'success': False,
            'steps': [],
            'error': None
        }
        
        try:
            # Step 1: Test SSH connectivity
            print(f"   1️⃣ Testing SSH connectivity...")
            ssh_result = subprocess.run([
                'ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                f'root@{ip}', 'echo "SSH_OK"'
            ], capture_output=True, text=True, timeout=10)
            
            if ssh_result.returncode != 0 or 'SSH_OK' not in ssh_result.stdout:
                result['error'] = 'SSH connectivity failed'
                result['steps'].append('❌ SSH connectivity failed')
                return result
            
            result['steps'].append('✅ SSH connectivity verified')
            
            # Step 2: Create agent directory
            print(f"   2️⃣ Creating agent directory...")
            mkdir_result = subprocess.run([
                'ssh', f'root@{ip}', 'mkdir -p /opt/ashd-agent'
            ], capture_output=True, text=True, timeout=10)
            
            if mkdir_result.returncode != 0:
                result['error'] = 'Failed to create agent directory'
                result['steps'].append('❌ Failed to create agent directory')
                return result
            
            result['steps'].append('✅ Agent directory created')
            
            # Step 3: Copy agent files
            print(f"   3️⃣ Copying agent files...")
            agent_files = [
                f'agents/{os_type}/ashd_agent.py',
                f'agents/{os_type}/deploy_{os_type}_agent.sh',
                f'agents/{os_type}/ashd-agent.service',
                f'agents/{os_type}/snmpd.conf'
            ]
            
            for file_path in agent_files:
                if not Path(file_path).exists():
                    result['error'] = f'Agent file not found: {file_path}'
                    result['steps'].append(f'❌ File not found: {file_path}')
                    return result
                
                # Copy file to host
                scp_result = subprocess.run([
                    'scp', file_path, f'root@{ip}:/tmp/'
                ], capture_output=True, text=True, timeout=30)
                
                if scp_result.returncode != 0:
                    result['error'] = f'Failed to copy {file_path}'
                    result['steps'].append(f'❌ Failed to copy {file_path}')
                    return result
            
            result['steps'].append('✅ Agent files copied')
            
            # Step 4: Execute deployment script
            print(f"   4️⃣ Executing deployment script...")
            deploy_result = subprocess.run([
                'ssh', f'root@{ip}', 
                f'chmod +x /tmp/deploy_{os_type}_agent.sh && /tmp/deploy_{os_type}_agent.sh'
            ], capture_output=True, text=True, timeout=120)
            
            if deploy_result.returncode != 0:
                result['error'] = f'Deployment script failed: {deploy_result.stderr}'
                result['steps'].append('❌ Deployment script failed')
                return result
            
            result['steps'].append('✅ Deployment script executed')
            
            # Step 5: Verify services
            print(f"   5️⃣ Verifying services...")
            services = ['ashd-agent', 'snmpd', 'chronyd' if os_type in ['rhel', 'centos', 'rocky'] else 'ntp']
            
            for service in services:
                service_result = subprocess.run([
                    'ssh', f'root@{ip}', f'systemctl is-active {service}'
                ], capture_output=True, text=True, timeout=10)
                
                if service_result.returncode == 0 and 'active' in service_result.stdout:
                    result['steps'].append(f'✅ {service} service active')
                else:
                    result['steps'].append(f'⚠️  {service} service not active')
            
            # Step 6: Test SNMP
            print(f"   6️⃣ Testing SNMP...")
            snmp_result = subprocess.run([
                'snmpwalk', '-v2c', '-c', 'public', '-t', '3', 
                f'{ip}:161', '1.3.6.1.2.1.1.1.0'
            ], capture_output=True, text=True, timeout=10)
            
            if snmp_result.returncode == 0:
                result['steps'].append('✅ SNMP responding')
            else:
                result['steps'].append('⚠️  SNMP not responding')
            
            result['success'] = True
            result['steps'].append('🎉 Agent deployment completed successfully')
            
        except Exception as e:
            result['error'] = str(e)
            result['steps'].append(f'❌ Deployment failed: {e}')
        
        return result
    
    def deploy_to_all_hosts(self, force_deploy: bool = False):
        """Deploy agents to all discovered hosts."""
        print("🚀 Starting Automated Agent Deployment")
        print("=" * 50)
        
        # Load discovery results
        discovery = self.load_discovery_results()
        if not discovery:
            return
        
        hosts = discovery['all_hosts']
        print(f"📊 Found {len(hosts)} hosts to process")
        
        for i, host in enumerate(hosts, 1):
            ip = host['ip']
            print(f"\n[{i}/{len(hosts)}] Processing {ip}")
            
            # Skip if already deployed and not forcing
            if not force_deploy and host.get('agent_deployable', False):
                print(f"   ⏭️  Skipping {ip} - already deployable")
                continue
            
            # Detect OS if unknown
            os_type = host.get('os_type', 'unknown')
            if os_type == 'unknown':
                os_type = self.detect_host_os(ip)
                if os_type == 'unknown':
                    print(f"   ❌ Cannot determine OS for {ip}")
                    continue
            
            # Deploy agent
            result = self.deploy_agent_to_host(ip, os_type)
            self.deployment_results.append(result)
            
            # Print result summary
            if result['success']:
                print(f"   ✅ Deployment successful for {ip}")
            else:
                print(f"   ❌ Deployment failed for {ip}: {result['error']}")
        
        # Save deployment results
        self.save_deployment_results()
        
        # Print summary
        self.print_deployment_summary()
    
    def deploy_to_specific_host(self, ip: str):
        """Deploy agent to a specific host."""
        print(f"🚀 Deploying agent to specific host: {ip}")
        
        # Load discovery results
        discovery = self.load_discovery_results()
        if not discovery:
            return
        
        # Find host in discovery results
        target_host = None
        for host in discovery['all_hosts']:
            if host['ip'] == ip:
                target_host = host
                break
        
        if not target_host:
            print(f"❌ Host {ip} not found in discovery results")
            return
        
        # Detect OS if unknown
        os_type = target_host.get('os_type', 'unknown')
        if os_type == 'unknown':
            os_type = self.detect_host_os(ip)
            if os_type == 'unknown':
                print(f"❌ Cannot determine OS for {ip}")
                return
        
        # Deploy agent
        result = self.deploy_agent_to_host(ip, os_type)
        self.deployment_results.append(result)
        
        # Save results
        self.save_deployment_results()
        
        # Print result
        if result['success']:
            print(f"✅ Deployment successful for {ip}")
        else:
            print(f"❌ Deployment failed for {ip}: {result['error']}")
    
    def save_deployment_results(self):
        """Save deployment results to file."""
        results_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_deployments': len(self.deployment_results),
            'successful_deployments': len([r for r in self.deployment_results if r['success']]),
            'failed_deployments': len([r for r in self.deployment_results if not r['success']]),
            'results': self.deployment_results
        }
        
        with open('deployment_results.json', 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"📄 Deployment results saved to deployment_results.json")
    
    def print_deployment_summary(self):
        """Print deployment summary."""
        total = len(self.deployment_results)
        successful = len([r for r in self.deployment_results if r['success']])
        failed = total - successful
        
        print(f"\n📊 Deployment Summary")
        print("=" * 30)
        print(f"Total deployments: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/total*100):.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print(f"\n❌ Failed Deployments:")
            for result in self.deployment_results:
                if not result['success']:
                    print(f"   {result['ip']}: {result['error']}")
        
        print(f"\n🎯 Next Steps:")
        print(f"   1. Check ASHD dashboard: http://localhost:8001")
        print(f"   2. Verify agent status on hosts")
        print(f"   3. Monitor SNMP and system metrics")

def main():
    """Main deployment function."""
    import sys
    
    deployer = AgentDeployer()
    
    if len(sys.argv) > 1:
        # Deploy to specific host
        host_ip = sys.argv[1]
        deployer.deploy_to_specific_host(host_ip)
    else:
        # Deploy to all hosts
        deployer.deploy_to_all_hosts()

if __name__ == "__main__":
    main()
