# 🔐 Non-Root Agent Deployment Guide

## 🎯 Overview

This guide shows how to deploy ASHD monitoring agents as non-root users, which is more secure and suitable for production environments.

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
systemctl status ashd-agent

# Check agent user
id ashd-agent

# Test agent as non-root user
sudo -u ashd-agent python3 /home/ashd-agent/ashd-agent/ashd_agent.py &
```

## 📋 Manual Non-Root Deployment

### **Step 1: Create Agent User**
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash ashd-agent
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
sudo -u ashd-agent python3 -m pip install --user psutil requests
```

### **Step 4: Create Agent Directory**
```bash
# Create agent home directory
sudo mkdir -p /home/ashd-agent/ashd-agent
sudo chown ashd-agent:ashd-agent /home/ashd-agent/ashd-agent
```

### **Step 5: Deploy Agent Code**
```bash
# Copy agent script
sudo cp agents/rocky/ashd_agent_non_root.py /home/ashd-agent/ashd-agent/ashd_agent.py
sudo chown ashd-agent:ashd-agent /home/ashd-agent/ashd-agent/ashd_agent.py
sudo chmod +x /home/ashd-agent/ashd-agent/ashd_agent.py
```

### **Step 6: Configure SNMP**
```bash
# Configure SNMP (as root)
sudo bash -c 'cat > /etc/snmp/snmpd.conf << EOF
# ASHD SNMP Configuration
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
sudo bash -c 'cat > /etc/sudoers.d/ashd-agent << EOF
# ASHD Agent sudo permissions
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status snmpd
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status chronyd
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/systemctl status ntp
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/chronyc
ashd-agent ALL=(ALL) NOPASSWD: /usr/bin/ntpq
ashd-agent ALL=(ALL) NOPASSWD: /usr/sbin/snmpwalk
EOF'
```

### **Step 10: Create Systemd Service**
```bash
sudo bash -c 'cat > /etc/systemd/system/ashd-agent.service << EOF
[Unit]
Description=ASHD Monitoring Agent (Non-Root)
After=network.target

[Service]
Type=simple
User=ashd-agent
Group=ashd-agent
WorkingDirectory=/home/ashd-agent/ashd-agent
ExecStart=/usr/bin/python3 /home/ashd-agent/ashd-agent/ashd_agent.py
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
sudo systemctl enable ashd-agent
sudo systemctl restart ashd-agent
```

## 🔍 Verification

### **Check Service Status**
```bash
# Check all services
systemctl status snmpd
systemctl status chronyd
systemctl status ashd-agent

# Check agent user
id ashd-agent
ls -la /home/ashd-agent/
```

### **Test SNMP**
```bash
# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Test SNMP from ASHD server
snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0
```

### **Test Agent**
```bash
# Test agent as non-root user
sudo -u ashd-agent python3 /home/ashd-agent/ashd-agent/ashd_agent.py

# Check agent logs
journalctl -u ashd-agent -f
```

### **Check NTP**
```bash
# Check NTP status
chronyc sources
# or
ntpq -p
```

## 🌐 Dashboard Verification

Open ASHD dashboard:
```
http://localhost:8001
```

**Expected Results:**
- **SNMP**: OK · 192.168.50.198:161 responding
- **NTP**: OK · Time synchronized
- **Agent**: OK · Metrics reporting normally
- **User**: Shows as "ashd-agent" in metrics

## 🛠️ Management Commands

### **Agent Management**
```bash
# Restart agent
sudo systemctl restart ashd-agent

# Check status
sudo systemctl status ashd-agent

# View logs
sudo journalctl -u ashd-agent -f

# Test agent manually
sudo -u ashd-agent python3 /home/ashd-agent/ashd-agent/ashd_agent.py
```

### **User Management**
```bash
# Switch to agent user
sudo -u ashd-agent -i

# Check user permissions
sudo -u ashd-agent -l

# Check home directory
ls -la /home/ashd-agent/
```

### **Service Management**
```bash
# Check all services
systemctl status snmpd chronyd ashd-agent

# Restart all services
sudo systemctl restart snmpd chronyd ashd-agent
```

## 🔧 Troubleshooting

### **Permission Issues**
```bash
# Check file permissions
ls -la /home/ashd-agent/ashd-agent/

# Fix ownership
sudo chown -R ashd-agent:ashd-agent /home/ashd-agent/

# Check sudo permissions
sudo -u ashd-agent sudo -l
```

### **Agent Not Starting**
```bash
# Check agent logs
sudo journalctl -u ashd-agent -n 50

# Test agent manually
sudo -u ashd-agent python3 /home/ashd-agent/ashd-agent/ashd_agent.py

# Check Python path
sudo -u ashd-agent which python3
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
**User**: ashd-agent (dedicated non-root user)
**Security**: Minimal privileges with sudo for specific commands
**Deployment**: Scripts ready for all OS types

**Deploy now using the non-root scripts for enhanced security!** 🔐
