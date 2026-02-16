# 🔐 Non-Root Agent Deployment Guide

## 🎯 Overview

This guide shows how to deploy System Trace monitoring agents as non-root users, which is more secure and suitable for production environments.

## 📊 Security Benefits

### **Non-Root Advantages**
- ✅ **Reduced Attack Surface**: Agent runs with limited privileges
- ✅ **Isolation**: Agent user can't access system files
- ✅ **Sudo Control**: Only specific commands allowed via sudo
- ✅ **Audit Trail**: Clear separation of agent activities
- ✅ **Compliance**: Meets security best practices

### **Sudo Permissions**
The agent user gets minimal sudo access for:
- `systemctl status` commands (read-only)
- `chronyc` / `ntpq` (NTP status)
- `snmpwalk` (SNMP queries)

## 🚀 Quick Deployment for centos-docker

### **Step 1: Copy Deployment Script**
```bash
# Copy Rocky Linux non-root script to centos-docker
scp agents/rocky/deploy_rocky_agent_non_root.sh root@192.168.50.198:/tmp/
```

### **Step 2: SSH and Deploy**
```bash
# SSH to centos-docker
ssh root@192.168.50.198

# Execute deployment script
sudo /tmp/deploy_rocky_agent_non_root.sh
```

### **Step 3: Verify Deployment**
```bash
# Check service status
systemctl status system-trace-agent

# Check agent user
id system-trace-agent

# Test agent as non-root user
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py &
```

## 📋 Manual Non-Root Deployment

### **Step 1: Create Agent User**
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash system-trace-agent
```

### **Step 2: Install Packages**
```bash
# Rocky Linux/RHEL/CentOS
sudo dnf update -y
sudo dnf install -y python3 python3-pip net-snmp net-snmp-utils chrony

# Ubuntu/Debian
sudo apt update -y
sudo apt install -y python3 python3-pip net-snmp snmpd ntp
```

### **Step 3: Install Python Dependencies**
```bash
# Install as agent user
sudo -u system-trace-agent python3 -m pip install --user psutil requests
```

### **Step 4: Create Agent Directory**
```bash
# Create agent home directory
sudo mkdir -p /home/system-trace-agent/system-trace-agent
sudo chown system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent
```

### **Step 5: Deploy Agent Code**
```bash
# Copy agent script
sudo cp agents/rocky/system-trace_agent_non_root.py /home/system-trace-agent/system-trace-agent/system-trace_agent.py
sudo chown system-trace-agent:system-trace-agent /home/system-trace-agent/system-trace-agent/system-trace_agent.py
sudo chmod +x /home/system-trace-agent/system-trace-agent/system-trace_agent.py
```

### **Step 6: Configure SNMP**
```bash
# Configure SNMP (as root)
sudo bash -c 'cat > /etc/snmp/snmpd.conf << EOF
# System Trace SNMP Configuration
agentAddress udp:161
com2sec readonly public
group MyROGroup v2c readonly
view all included .1 80
access MyROGroup "" any noauth exact all none none
sysLocation "Data Center"
sysContact "admin@example.com"
sysServices 72
load 12 10 5
EOF'
```

### **Step 7: Configure NTP**
```bash
# Rocky Linux/RHEL/CentOS
sudo bash -c 'cat > /etc/chrony.conf << EOF
pool pool.ntp.org iburst
driftfile /var/lib/chrony/drift
allow 192.168.0.0/16
local stratum 10
EOF'

# Ubuntu/Debian
sudo bash -c 'echo "server pool.ntp.org iburst" >> /etc/ntp.conf'
```

### **Step 8: Configure Firewall**
```bash
# Rocky Linux/RHEL/CentOS
sudo firewall-cmd --permanent --add-port=161/udp
sudo firewall-cmd --permanent --add-port=123/udp
sudo firewall-cmd --reload

# Ubuntu/Debian
sudo ufw allow 161/udp comment "SNMP"
sudo ufw allow 123/udp comment "NTP"
sudo ufw --force enable
```

### **Step 9: Setup Sudo Permissions**
```bash
# Create sudoers file for agent user
sudo bash -c 'cat > /etc/sudoers.d/system-trace-agent << EOF
# System Trace Agent sudo permissions
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status ntp
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/chronyc
system-trace-agent ALL=(ALL) NOPASSWD: /usr/bin/ntpq
system-trace-agent ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF'
```

### **Step 10: Create Systemd Service**
```bash
sudo bash -c 'cat > /etc/systemd/system/system-trace-agent.service << EOF
[Unit]
Description=System Trace Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User=system-trace-agent
Group=system-trace-agent
WorkingDirectory=/home/system-trace-agent/system-trace-agent
ExecStart=/usr/bin/python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF'
```

### **Step 11: Start Services**
```bash
# Start all services
sudo systemctl daemon-reload
sudo systemctl enable snmpd
sudo systemctl restart snmpd
sudo systemctl enable chronyd
sudo systemctl restart chronyd
sudo systemctl enable system-trace-agent
sudo systemctl restart system-trace-agent
```

## 🔍 Verification

### **Check Service Status**
```bash
# Check all services
systemctl status snmpd
systemctl status chronyd
systemctl status system-trace-agent

# Check agent user
id system-trace-agent
ls -la /home/system-trace-agent/
```

### **Test SNMP**
```bash
# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Test SNMP from System Trace server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0
```

### **Test Agent**
```bash
# Test agent as non-root user
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py

# Check agent logs
journalctl -u system-trace-agent -f
```

### **Check NTP**
```bash
# Check NTP status
chronyc sources
# or
ntpq -p
```

## 🌐 Dashboard Verification

Open System Trace dashboard:
```
http://localhost:8001
```

**Expected Results:**
- **SNMP**: OK · 192.168.50.198:161 responding
- **NTP**: OK · Time synchronized
- **Agent**: OK · Metrics reporting normally
- **User**: Shows as "system-trace-agent" in metrics

## 🛠️ Management Commands

### **Agent Management**
```bash
# Restart agent
sudo systemctl restart system-trace-agent

# Check status
sudo systemctl status system-trace-agent

# View logs
sudo journalctl -u system-trace-agent -f

# Test agent manually
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py
```

### **User Management**
```bash
# Switch to agent user
sudo -u system-trace-agent -i

# Check user permissions
sudo -u system-trace-agent -l

# Check home directory
ls -la /home/system-trace-agent/
```

### **Service Management**
```bash
# Check all services
systemctl status snmpd chronyd system-trace-agent

# Restart all services
sudo systemctl restart snmpd chronyd system-trace-agent
```

## 🔧 Troubleshooting

### **Permission Issues**
```bash
# Check file permissions
ls -la /home/system-trace-agent/system-trace-agent/

# Fix ownership
sudo chown -R system-trace-agent:system-trace-agent /home/system-trace-agent/

# Check sudo permissions
sudo -u system-trace-agent sudo -l
```

### **Agent Not Starting**
```bash
# Check agent logs
sudo journalctl -u system-trace-agent -n 50

# Test agent manually
sudo -u system-trace-agent python3 /home/system-trace-agent/system-trace-agent/system-trace_agent.py

# Check Python path
sudo -u system-trace-agent which python3
```

### **SNMP Issues**
```bash
# Check SNMP service
sudo systemctl status snmpd

# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check SNMP config
sudo cat /etc/snmp/snmpd.conf
```

### **NTP Issues**
```bash
# Check NTP service
sudo systemctl status chronyd

# Check NTP sources
chronyc sources

# Force NTP sync
chronyc -a makestep
```

## 📊 Non-Root vs Root Deployment

| Aspect | Non-Root | Root |
|--------|----------|------|
| **Security** | ✅ High | ⚠️ Lower |
| **Permissions** | Limited | Full |
| **Attack Surface** | Small | Large |
| **Compliance** | ✅ Better | ⚠️ Worse |
| **Setup Complexity** | Medium | Simple |
| **Management** | Isolated | Integrated |

## 🎯 Best Practices

### **Security**
- ✅ Use dedicated agent user
- ✅ Minimal sudo permissions
- ✅ Regular user audits
- ✅ Monitor agent logs

### **Operational**
- ✅ Document agent user credentials
- ✅ Use systemd for service management
- ✅ Set up log rotation
- ✅ Monitor resource usage

### **Maintenance**
- ✅ Regular security updates
- ✅ Monitor agent performance
- ✅ Backup configuration files
- ✅ Test disaster recovery

---

## 🚀 **Non-Root Deployment Ready!**

**Status**: ✅ **Non-root deployment scripts created**
**User**: system-trace-agent (dedicated non-root user)
**Security**: Minimal privileges with sudo for specific commands
**Deployment**: Scripts ready for all OS types

**Deploy now using the non-root scripts for enhanced security!** 🔐
