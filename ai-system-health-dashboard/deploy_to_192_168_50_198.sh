#!/bin/bash
# Auto-generated deployment script for 192.168.50.198

# Deploy ASHD Agent to 192.168.50.198 (Rocky)
# ================================================

# Step 1: Copy agent files to host
echo "📁 Copying agent files to 192.168.50.198..."
scp agents/rocky/ashd_agent.py root@192.168.50.198:/opt/ashd-agent/
scp agents/rocky/deploy_rocky_agent.sh root@192.168.50.198:/tmp/
scp agents/rocky/ashd-agent.service root@192.168.50.198:/tmp/
scp agents/rocky/snmpd.conf root@192.168.50.198:/tmp/

# Step 2: Execute deployment script
echo "🚀 Executing deployment script on 192.168.50.198..."
ssh root@192.168.50.198 'chmod +x /tmp/deploy_rocky_agent.sh && /tmp/deploy_rocky_agent.sh'

# Step 3: Verify deployment
echo "🔍 Verifying deployment on 192.168.50.198..."
ssh root@192.168.50.198 'systemctl status ashd-agent | head -5'
ssh root@192.168.50.198 'systemctl status snmpd | head -5'
ssh root@192.168.50.198 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'

# Step 4: Check ASHD dashboard
echo "🌐 Check ASHD dashboard: http://localhost:8001"
echo "   Look for 192.168.50.198 in the monitoring data"
