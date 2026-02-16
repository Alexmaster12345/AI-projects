#!/bin/bash
# Auto-generated deployment script for 192.168.50.1

# Deploy ASHD Agent to 192.168.50.1 (Unknown)
# ================================================

# Step 1: Copy agent files to host
echo "📁 Copying agent files to 192.168.50.1..."
scp agents/unknown/ashd_agent.py root@192.168.50.1:/opt/ashd-agent/
scp agents/unknown/deploy_unknown_agent.sh root@192.168.50.1:/tmp/
scp agents/unknown/ashd-agent.service root@192.168.50.1:/tmp/
scp agents/unknown/snmpd.conf root@192.168.50.1:/tmp/

# Step 2: Execute deployment script
echo "🚀 Executing deployment script on 192.168.50.1..."
ssh root@192.168.50.1 'chmod +x /tmp/deploy_unknown_agent.sh && /tmp/deploy_unknown_agent.sh'

# Step 3: Verify deployment
echo "🔍 Verifying deployment on 192.168.50.1..."
ssh root@192.168.50.1 'systemctl status ashd-agent | head -5'
ssh root@192.168.50.1 'systemctl status snmpd | head -5'
ssh root@192.168.50.1 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'

# Step 4: Check ASHD dashboard
echo "🌐 Check ASHD dashboard: http://localhost:8001"
echo "   Look for 192.168.50.1 in the monitoring data"
