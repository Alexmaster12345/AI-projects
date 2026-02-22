#!/usr/bin/env python3
"""
Create Hosts Management Dashboard

Creates a web interface for managing discovered hosts and deploying agents.
"""

import json
from pathlib import Path

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
    dashboard_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASHD Host Management</title>
    <link rel="stylesheet" href="/static/assets/main.css">
    <style>
        .hosts-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .host-card {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .host-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .host-ip {{
            font-size: 1.2em;
            font-weight: bold;
            color: #4CAF50;
        }}
        .host-status {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
        }}
        .status-unknown {{
            background: #666;
            color: #fff;
        }}
        .status-deployable {{
            background: #4CAF50;
            color: #fff;
        }}
        .host-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-bottom: 15px;
        }}
        .info-item {{
            display: flex;
            justify-content: space-between;
        }}
        .info-label {{
            color: #888;
        }}
        .info-value {{
            color: #fff;
        }}
        .deploy-btn {{
            background: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }}
        .deploy-btn:hover {{
            background: #1976D2;
        }}
        .deploy-btn:disabled {{
            background: #666;
            cursor: not-allowed;
        }}
        .commands-section {{
            background: #2a2a2a;
            border-radius: 4px;
            padding: 15px;
            margin-top: 15px;
            display: none;
        }}
        .commands-section.show {{
            display: block;
        }}
        .command-block {{
            background: #1a1a1a;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 10px;
            font-family: monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
        }}
        .copy-btn {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
        }}
        .summary-section {{
            background: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            text-align: center;
        }}
        .summary-item {{
            padding: 15px;
            background: #1a1a1a;
            border-radius: 8px;
        }}
        .summary-number {{
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
        }}
        .summary-label {{
            color: #888;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="hosts-container">
        <h1>🔍 ASHD Host Management</h1>
        
        <div class="summary-section">
            <h2>📊 Discovery Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-number">{discovery['total_hosts_found']}</div>
                    <div class="summary-label">Total Hosts</div>
                </div>
                <div class="summary-item">
                    <div class="summary-number">{len(discovery['deployable_hosts'])}</div>
                    <div class="summary-label">Deployable</div>
                </div>
                <div class="summary-item">
                    <div class="summary-number">{len(discovery['hosts_by_os'])}</div>
                    <div class="summary-label">OS Types</div>
                </div>
                <div class="summary-item">
                    <div class="summary-number">192.168.50.0/24</div>
                    <div class="summary-label">Network</div>
                </div>
            </div>
        </div>
        
        <h2>🖥️ Discovered Hosts</h2>
        
        {generate_host_cards(discovery)}
        
        <div class="summary-section">
            <h2>📁 Available Agent Files</h2>
            <p>Agent files have been created for all supported operating systems:</p>
            <ul>
                <li><strong>Ubuntu/Debian:</strong> apt-based systems</li>
                <li><strong>RHEL/CentOS/Rocky:</strong> yum/dnf-based systems</li>
            </ul>
            <p>Each agent includes:</p>
            <ul>
                <li>Python monitoring agent (ashd_agent.py)</li>
                <li>Deployment script (deploy_*_agent.sh)</li>
                <li>Systemd service (ashd-agent.service)</li>
                <li>SNMP configuration (snmpd.conf)</li>
            </ul>
        </div>
    </div>

    <script>
        function toggleCommands(hostId) {{
            const section = document.getElementById('commands-' + hostId);
            section.classList.toggle('show');
        }}
        
        function copyCommands(hostId) {{
            const commandsText = document.getElementById('commands-' + hostId).innerText;
            navigator.clipboard.writeText(commandsText).then(() => {{
                alert('Commands copied to clipboard!');
            }});
        }}
        
        // Auto-refresh every 30 seconds
        setTimeout(() => {{
            window.location.reload();
        }}, 30000);
    </script>
</body>
</html>'''
    
    # Save the dashboard
    dashboard_path = Path('app/static/hosts.html')
    with open(dashboard_path, 'w') as f:
        f.write(dashboard_html)
    
    print("✅ Hosts management dashboard created: app/static/hosts.html")

def main():
    """Main function to create hosts dashboard."""
    
    print("🚀 Creating ASHD Hosts Management Dashboard")
    print("=" * 50)
    
    # Create hosts dashboard
    create_hosts_dashboard()
    
    print(f"\n🌐 Dashboard Created!")
    print(f"   Hosts page: app/static/hosts.html")
    print(f"   Access: http://localhost:8001/hosts")
    
    print(f"\n🎯 Next Steps:")
    print(f"   1. Access the hosts dashboard")
    print(f"   2. Review discovered hosts")
    print(f"   3. Deploy agents to accessible hosts")

if __name__ == "__main__":
    main()
