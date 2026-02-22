#!/bin/bash
# Quick Non-Root Deployment for centos-docker

echo "🚀 Deploying System Trace Agent to centos-docker (Non-Root)"
echo "=============================================="

HOST="192.168.50.198"
SCRIPT="deploy_rocky_agent_non_root.sh"

echo "📁 Step 1: Copying deployment script..."
scp agents/rocky/$SCRIPT root@$HOST:/tmp/

echo "🚀 Step 2: Executing deployment script..."
ssh root@$HOST "chmod +x /tmp/$SCRIPT && sudo /tmp/$SCRIPT"

echo "🔍 Step 3: Verifying deployment..."
echo "Service Status:"
ssh root@$HOST "systemctl status system-trace-agent --no-pager -l | head -5"
ssh root@$HOST "systemctl status snmpd --no-pager -l | head -5"
ssh root@$HOST "systemctl status chronyd --no-pager -l | head -5"

echo ""
echo "SNMP Test:"
ssh root@$HOST "snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0" 2>/dev/null || echo "SNMP test failed"

echo ""
echo "Agent User:"
ssh root@$HOST "id system-trace-agent"

echo ""
echo "🎯 Deployment completed!"
echo "📋 Check System Trace dashboard: http://localhost:8001"
echo "   Agent runs as non-root user: system-trace-agent"
echo "   Enhanced security with minimal privileges"
