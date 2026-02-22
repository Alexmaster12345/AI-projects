#!/usr/bin/env python3
"""
Update ASHD Dashboard with Discovered Hosts

Updates the ASHD configuration to include all discovered hosts
and creates a web interface for agent deployment.
"""

import json
import os
from pathlib import Path

def update_ashd_config():
    """Update ASHD .env configuration with discovered hosts."""
    print("🔧 Updating ASHD configuration with discovered hosts...")
    
    # Read discovery results
    with open('discovery_results.json', 'r') as f:
        discovery = json.load(f)
    
    # Read current .env
    env_path = Path('.env')
    env_vars = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Add discovered hosts to configuration
    discovered_ips = [host['ip'] for host in discovery['all_hosts']]
    
    # Update configuration for multiple hosts
    env_vars['DISCOVERED_HOSTS'] = ','.join(discovered_ips)
    env_vars['MONITORING_HOSTS_COUNT'] = str(len(discovered_ips))
    
    # Keep existing centos-docker configuration
    env_vars['PRIMARY_HOST'] = '192.168.50.198'
    env_vars['PRIMARY_HOSTNAME'] = 'centos-docker'
    
    # Write back to .env
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Updated configuration with {len(discovered_ips)} discovered hosts")
    print(f"   Hosts: {', '.join(discovered_ips)}")
    
    return discovered_ips

def create_hosts_dashboard():
    """Create a hosts management dashboard page."""
    print("📄 Creating hosts management dashboard...")
    
    # Read discovery results
    with open('discovery_results.json', 'r') as f:
        discovery = json.load(f)
    
    def create_hosts_dashboard():
    """Create a hosts management dashboard page."""
    print("📄 Creating hosts management dashboard...")
    
    # Read discovery results
    with open('discovery_results.json', 'r') as f:
        discovery = json.load(f)

    def generate_host_cards(discovery):
        """Generate HTML for host cards."""
        cards = ""
        
        for i, host in enumerate(discovery['all_hosts']):
            status_class = "status-unknown"
            status_text = "Unknown"
            
            if host['ssh_accessible']:
                if host['agent_deployable']:
                    status_class = "status-deployable"
                    status_text = "Deployable"
                else:
                    status_class = "status-unknown"
                    status_text = "SSH Access"
            
            deployable = host['agent_deployable']
            os_type = host['os_type'] or "Unknown"
            
            card = f'''
        <div class="host-card">
            <div class="host-header">
                <div class="host-ip">{host['ip']}</div>
                <div class="host-status {status_class}">{status_text}</div>
            </div>
            
            <div class="host-info">
                <div class="info-item">
                    <span class="info-label">Hostname:</span>
                    <span class="info-value">{host['hostname'] or 'Unknown'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">OS Type:</span>
                    <span class="info-value">{os_type.title()}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">SSH Access:</span>
                    <span class="info-value">{'Yes' if host['ssh_accessible'] else 'No'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">SNMP Available:</span>
                    <span class="info-value">{'Yes' if host['snmp_available'] else 'No'}</span>
                </div>
            </div>
            
            {generate_deployment_section(host, i)}
        </div>'''
            
            cards += card
        
        return cards
    
    def generate_deployment_section(host, index):
        """Generate deployment section for a host."""
        if not host['ssh_accessible']:
            return '''
            <div>
                <button class="deploy-btn" disabled>SSH Not Accessible</button>
                <p style="color: #888; font-size: 0.9em;">SSH key authentication required for deployment</p>
            </div>'''
        
        if not host['agent_deployable']:
            return '''
            <div>
                <button class="deploy-btn" disabled>OS Not Supported</button>
                <p style="color: #888; font-size: 0.9em;">Unsupported OS type for automatic deployment</p>
            </div>'''
        
        os_type = host['os_type']
        ip = host['ip']
        
        return f'''
        <div>
            <button class="deploy-btn" onclick="toggleCommands({index})">Show Deployment Commands</button>
            <button class="copy-btn" onclick="copyCommands({index})">Copy Commands</button>
        </div>
        
        <div id="commands-{index}" class="commands-section">
            <h4>Deployment Commands for {host['hostname'] or ip} ({os_type.title()})</h4>
            <div class="command-block"># Deploy {os_type.title()} Agent to {ip}
# Copy agent files
scp agents/{os_type}/ashd_agent.py root@{ip}:/opt/ashd-agent/
scp agents/{os_type}/deploy_{os_type}_agent.sh root@{ip}:/tmp/
scp agents/{os_type}/ashd-agent.service root@{ip}:/tmp/
scp agents/{os_type}/snmpd.conf root@{ip}:/tmp/

# Execute deployment
ssh root@{ip} 'chmod +x /tmp/deploy_{os_type}_agent.sh'
ssh root@{ip} '/tmp/deploy_{os_type}_agent.sh'

# Verify deployment
ssh root@{ip} 'systemctl status ashd-agent'
ssh root@{ip} 'systemctl status snmpd'
ssh root@{ip} 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'</div>
        </div>'''
    
    # Generate the HTML
    html_content = dashboard_html.replace('{generate_host_cards(discovery)}', generate_host_cards(discovery))
    
    # Save the dashboard
    dashboard_path = Path('app/static/hosts.html')
    with open(dashboard_path, 'w') as f:
        f.write(html_content)
    
    print("✅ Hosts management dashboard created: app/static/hosts.html")

def create_agent_api():
    """Create API endpoints for agent management."""
    print("🔧 Creating agent management API...")
    
    api_code = '''
# Add to main.py - Agent Management API

@app.get("/hosts")
async def hosts_page(request: Request):
    """Serve the hosts management page."""
    return FileResponse("app/static/hosts.html")

@app.get("/api/discovery/results")
async def get_discovery_results():
    """Get discovery results."""
    try:
        with open('discovery_results.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Discovery results not found"}

@app.get("/api/agent/files/{os_type}")
async def get_agent_files(os_type: str):
    """Get available agent files for OS type."""
    agent_dir = Path(f'agents/{os_type}')
    if not agent_dir.exists():
        return {"error": f"OS type {os_type} not supported"}
    
    files = {}
    for file_path in agent_dir.glob('*'):
        files[file_path.name] = str(file_path)
    
    return {"os_type": os_type, "files": files}

@app.post("/api/agent/deploy/{host_ip}")
async def deploy_agent_to_host(host_ip: str, request: Request):
    """Deploy agent to specific host."""
    try:
        data = await request.json()
        os_type = data.get('os_type')
        
        if not os_type:
            return {"error": "OS type required"}
        
        # Get deployment commands
        with open('deployment_plan.json', 'r') as f:
            plan = json.load(f)
        
        if host_ip in plan['deployment_commands']:
            commands = plan['deployment_commands'][host_ip]
            return {"host_ip": host_ip, "commands": commands}
        else:
            return {"error": f"No deployment commands for {host_ip}"}
            
    except Exception as e:
        return {"error": str(e)}
'''
    
    # Save API code for reference
    with open('agent_api_endpoints.py', 'w') as f:
        f.write(api_code)
    
    print("✅ Agent API endpoints created: agent_api_endpoints.py")

def main():
    """Main function to update dashboard with discovered hosts."""
    
    print("🚀 Updating ASHD Dashboard with Discovered Hosts")
    print("=" * 50)
    
    # Update ASHD configuration
    discovered_ips = update_ashd_config()
    
    # Create hosts dashboard
    create_hosts_dashboard()
    
    # Create agent API
    create_agent_api()
    
    print(f"\n📊 Dashboard Updated!")
    print(f"   Discovered hosts: {len(discovered_ips)}")
    print(f"   Configuration updated: .env")
    print(f"   Dashboard page: app/static/hosts.html")
    print(f"   API endpoints: agent_api_endpoints.py")
    
    print(f"\n🌐 Access the hosts dashboard:")
    print(f"   http://localhost:8001/hosts")
    
    print(f"\n🎯 Next Steps:")
    print(f"   1. Access the hosts dashboard")
    print(f"   2. Review discovered hosts")
    print(f"   3. Deploy agents to accessible hosts")
    print(f"   4. Monitor agents on main dashboard")

if __name__ == "__main__":
    main()
