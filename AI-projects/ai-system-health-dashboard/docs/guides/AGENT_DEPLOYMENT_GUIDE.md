# System Trace Agent Deployment Guide

## 🎯 Overview

This guide provides step-by-step instructions for deploying System Trace monitoring agents to discovered hosts. The system has identified 4 hosts in the 192.168.50.0/24 network and created platform-specific agent packages.

## 📊 Discovered Hosts

| IP Address | Host Type | OS | Status | Deployment |
|------------|-----------|----|---------|------------|
| 192.168.50.198 | centos-docker | Rocky Linux | Ready | ✅ Available |
| 192.168.50.81 | Unknown | Unknown | SSH Required | ⏳ Pending |
| 192.168.50.89 | Unknown | Unknown | SSH Required | ⏳ Pending |
| 192.168.50.1 | Gateway | Unknown | Not Accessible | ❌ Skip |

## 🚀 Quick Deployment Options

### **Option 1: Deploy to centos-docker (Recommended)**

Since 192.168.50.198 (centos-docker) is our primary target, use this simple command:

```bash
# Execute the pre-generated deployment script
./deploy_to_192_168_50_198.sh
```

**What this does:**
1. Copies Rocky Linux agent files to centos-docker
2. Executes the deployment script automatically
3. Verifies SNMP and agent services
4. Shows dashboard verification steps

### **Option 2: Manual Deployment to centos-docker**

If the script fails due to SSH authentication, deploy manually:

```bash
# Step 1: Copy agent files
scp agents/rocky/system-trace_agent.py root@192.168.50.198:/opt/system-trace-agent/
scp agents/rocky/deploy_rocky_agent.sh root@192.168.50.198:/tmp/
scp agents/rocky/system-trace-agent.service root@192.168.50.198:/tmp/
scp agents/rocky/snmpd.conf root@192.168.50.198:/tmp/

# Step 2: Execute deployment
ssh root@192.168.50.198 'chmod +x /tmp/deploy_rocky_agent.sh && /tmp/deploy_rocky_agent.sh'

# Step 3: Verify deployment
ssh root@192.168.50.198 'systemctl status system-trace-agent'
ssh root@192.168.50.198 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'
```

### **Option 3: Interactive Deployment**

Use the interactive deployment system:

```bash
python scripts/quick_deploy_agent.py
```

Then select option 1 for centos-docker deployment.

## 🔐 SSH Authentication Setup

### **Method 1: SSH Key Authentication (Recommended)**

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096

# Copy SSH key to centos-docker
ssh-copy-id root@192.168.50.198

# Test connection
ssh root@192.168.50.198 'hostname'
```

### **Method 2: Password Authentication**

If you prefer password authentication, the deployment scripts will prompt for the password when needed.

## 📁 Agent Files Structure

### **Rocky Linux Agent (for centos-docker)**

```
agents/rocky/
├── system-trace_agent.py          # Python monitoring agent
├── deploy_rocky_agent.sh  # Deployment script
├── system-trace-agent.service     # Systemd service
└── snmpd.conf            # SNMP configuration
```

### **Agent Capabilities**

- **System Monitoring**: CPU, memory, disk, network metrics
- **SNMP Support**: Full SNMP v2c implementation
- **NTP Sync**: Time service configuration
- **Service Management**: Automatic start/restart
- **Firewall Config**: Opens required ports (161, 123)

## 🔍 Deployment Verification

### **1. Check Service Status**

```bash
# On centos-docker
ssh root@192.168.50.198 'systemctl status system-trace-agent'
ssh root@192.168.50.198 'systemctl status snmpd'
ssh root@192.168.50.198 'systemctl status chronyd'
```

### **2. Test SNMP Connectivity**

```bash
# From System Trace server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0

# From centos-docker
ssh root@192.168.50.198 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'
```

### **3. Check System Trace Dashboard**

```
http://localhost:8001
```

Look for:
- **SNMP Status**: Should show "OK · 192.168.50.198:161 responding"
- **Protocol Health**: ICMP, SNMP, NTP should be green
- **System Metrics**: CPU, memory, disk data appearing

## 🛠️ Troubleshooting

### **SSH Connection Issues**

```bash
# Check connectivity
ping -c 3 192.168.50.198

# Test SSH manually
ssh -o ConnectTimeout=10 root@192.168.50.198 'echo "SSH_OK"'

# Setup SSH keys if needed
ssh-copy-id root@192.168.50.198
```

### **Agent Service Issues**

```bash
# Check service status
ssh root@192.168.50.198 'systemctl status system-trace-agent'

# Check service logs
ssh root@192.168.50.198 'journalctl -u system-trace-agent -f'

# Restart service
ssh root@192.168.50.198 'systemctl restart system-trace-agent'
```

### **SNMP Issues**

```bash
# Check SNMP service
ssh root@192.168.50.198 'systemctl status snmpd'

# Check SNMP configuration
ssh root@192.168.50.198 'cat /etc/snmp/snmpd.conf'

# Test SNMP locally
ssh root@192.168.50.198 'snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0'

# Check firewall
ssh root@192.168.50.198 'firewall-cmd --list-all | grep 161'
```

### **NTP Issues**

```bash
# Check NTP service
ssh root@192.168.50.198 'systemctl status chronyd'

# Check NTP sources
ssh root@192.168.50.198 'chronyc sources'

# Force NTP sync
ssh root@192.168.50.198 'chronyc -a makestep'
```

## 📊 Expected Results

### **Before Deployment**
```
SNMP: CRIT · SNMP timeout
Agent: Not deployed
NTP: Clock skew / NTP server reachability
```

### **After Successful Deployment**
```
SNMP: OK · 192.168.50.198:161 responding
Agent: OK · Metrics reporting normally
NTP: OK · Time synchronized
ICMP: OK · 192.168.50.198 responding
```

### **Dashboard Verification**

On the System Trace dashboard (http://localhost:8001):

1. **Configuration Page**: 
   - SNMP_HOST: 192.168.50.198
   - SNMP_PORT: 161
   - SNMP_COMMUNITY: public

2. **Overview Page**:
   - All protocol statuses should be green
   - System metrics should be updating

3. **Hosts Page**:
   - http://localhost:8001/hosts
   - Shows deployment status and commands

## 🎯 Next Steps

### **Immediate Actions**

1. **Deploy to centos-docker**:
   ```bash
   ./deploy_to_192_168_50_198.sh
   ```

2. **Verify deployment**:
   ```bash
   ssh root@192.168.50.198 'systemctl status system-trace-agent'
   snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0
   ```

3. **Check dashboard**:
   ```
   http://localhost:8001
   ```

### **Future Deployments**

Once SSH authentication is set up for other hosts:

1. **Deploy to other hosts** using their individual scripts:
   ```bash
   ./deploy_to_192_168_50_81.sh
   ./deploy_to_192_168_50_89.sh
   ```

2. **Use the hosts dashboard** for management:
   ```
   http://localhost:8001/hosts
   ```

## 📚 Additional Resources

- **Auto-Discovery Summary**: `auto_discovery_summary.md`
- **Hosts Dashboard**: http://localhost:8001/hosts
- **Agent Files**: `agents/` directory
- **Deployment Scripts**: `deploy_to_*.sh` files
- **Discovery Results**: `discovery_results.json`

---

**Status**: ✅ **Ready for deployment**
**Primary Target**: 192.168.50.198 (centos-docker)
**Deployment Method**: Automated script available
**Next**: Execute deployment script and verify on dashboard
