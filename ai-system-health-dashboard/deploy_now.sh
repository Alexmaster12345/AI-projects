#!/bin/bash
# Quick ASHD Agent Deployment Script

echo "🚀 ASHD Agent Deployment"
echo "======================="
echo ""
echo "Available deployment options:"
echo "1. Deploy to centos-docker (192.168.50.198)"
echo "2. Show manual commands"
echo "3. Exit"
echo ""

read -p "Select option (1-3): " choice

case $choice in
    1)
        echo ""
        echo "🎯 Deploying to centos-docker (192.168.50.198)"
        echo "=========================================="
        echo ""
        echo "This will:"
        echo "  • Copy Rocky Linux agent files to centos-docker"
        echo "  • Execute deployment script automatically"
        echo "  • Verify SNMP and agent services"
        echo "  • Show dashboard verification steps"
        echo ""
        read -p "Continue? (y/N): " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            echo ""
            echo "📁 Executing deployment script..."
            ./deploy_to_192_168_50_198.sh
        else
            echo "❌ Deployment cancelled"
        fi
        ;;
    2)
        echo ""
        echo "📋 Manual Deployment Commands for centos-docker"
        echo "=============================================="
        echo ""
        echo "# Step 1: Copy agent files"
        echo "scp agents/rocky/ashd_agent.py root@192.168.50.198:/opt/ashd-agent/"
        echo "scp agents/rocky/deploy_rocky_agent.sh root@192.168.50.198:/tmp/"
        echo "scp agents/rocky/ashd-agent.service root@192.168.50.198:/tmp/"
        echo "scp agents/rocky/snmpd.conf root@192.168.50.198:/tmp/"
        echo ""
        echo "# Step 2: Execute deployment"
        echo "ssh root@192.168.50.198 'chmod +x /tmp/deploy_rocky_agent.sh && /tmp/deploy_rocky_agent.sh'"
        echo ""
        echo "# Step 3: Verify deployment"
        echo "ssh root@192.168.50.198 'systemctl status ashd-agent'"
        echo "snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0"
        echo ""
        echo "# Step 4: Check dashboard"
        echo "http://localhost:8001"
        ;;
    3)
        echo "👋 Exiting..."
        exit 0
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac
