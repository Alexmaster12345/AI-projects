# CentOS-Docker Monitoring Deployment Guide

## Overview

This guide addresses the monitoring issues for the centos-docker host and provides step-by-step deployment instructions.

## Issues Identified

1. ✅ **pysnmp not installed** - FIXED (already installed in requirements.txt)
2. 🔧 **SNMP not monitoring** - CONFIGURED (SNMP_HOST=centos-docker)
3. 🔧 **High resource usage** - OPTIMIZED (30-second intervals)
4. 🔧 **NTP clock skew** - SCRIPT CREATED
5. 🔧 **Agent deployment** - SCRIPT CREATED

## Current Configuration

```bash
SNMP_HOST=centos-docker
SNMP_PORT=161
SNMP_COMMUNITY=public
SNMP_TIMEOUT_SECONDS=5
ICMP_HOST=centos-docker
NTP_SERVER=pool.ntp.org
PROTOCOL_CHECK_INTERVAL_SECONDS=30
```

## Deployment Steps

### Step 1: Copy Scripts to CentOS-Docker Host

From your local machine:

```bash
# Copy deployment scripts to centos-docker
scp deploy_centos_docker_agent.sh centos-docker:/root/
scp fix_ntp_centos_docker.sh centos-docker:/root/
```

### Step 2: Fix NTP Configuration

SSH into centos-docker and run the NTP fix:

```bash
# SSH to centos-docker
ssh centos-docker

# Run NTP configuration script
sudo ./fix_ntp_centos_docker.sh
```

**What this script does:**
- Installs NTP package
- Configures reliable NTP servers
- Enables NTP service
- Opens firewall for NTP (UDP/123)
- Forces immediate time synchronization
- Verifies NTP status

### Step 3: Deploy System Trace Agent

Still on centos-docker:

```bash
# Run agent deployment script
sudo ./deploy_centos_docker_agent.sh
```

**What this script does:**
- Installs required packages (python3, snmp)
- Configures SNMP service with public community
- Enables and starts SNMP daemon
- Opens firewall for SNMP (UDP/161)
- Creates System Trace monitoring agent
- Sets up systemd service for agent
- Tests SNMP connectivity

### Step 4: Verify Deployment

On centos-docker, verify all services:

```bash
# Check SNMP service
systemctl status snmpd

# Check NTP service
systemctl status ntpd

# Check System Trace agent
systemctl status system-trace-agent

# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check NTP synchronization
ntpq -p

# Check agent logs
journalctl -u system-trace-agent -f
```

### Step 5: Update System Trace Dashboard

The System Trace server should automatically reload with the new configuration. Check:

1. **Dashboard**: http://localhost:8001
2. **Configuration Page**: Verify SNMP settings
3. **Overview Page**: Check protocol health status

## Expected Results

### Before Deployment
```
SNMP: UNKNOWN · not configured in dashboard
NTP: Clock skew / NTP server reachability (udp/123)
Agent: High resource usage (agent reachability)
```

### After Deployment
```
SNMP: OK · centos-docker responding
NTP: OK · Time synchronized
Agent: OK · Metrics reporting normally
```

## Troubleshooting

### SNMP Issues

#### **SNMP timeout or connection failed**
```bash
# Check SNMP service
systemctl status snmpd

# Check SNMP configuration
cat /etc/snmp/snmpd.conf

# Test SNMP locally
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check firewall
firewall-cmd --list-all | grep snmp
```

#### **Fix SNMP issues**
```bash
# Restart SNMP service
sudo systemctl restart snmpd

# Check SNMP logs
journalctl -u snmpd -f

# Ensure SNMP is listening
netstat -ulnp | grep 161
```

### NTP Issues

#### **NTP synchronization problems**
```bash
# Check NTP status
ntpq -p

# Force NTP sync
sudo ntpdate -u pool.ntp.org

# Restart NTP service
sudo systemctl restart ntpd

# Check NTP logs
journalctl -u ntpd -f
```

#### **Fix NTP issues**
```bash
# Check network connectivity to NTP servers
nc -u -v pool.ntp.org 123

# Update NTP configuration
sudo nano /etc/ntp.conf

# Verify NTP port is open
firewall-cmd --list-all | grep ntp
```

### Agent Issues

#### **Agent not reporting**
```bash
# Check agent service
systemctl status system-trace-agent

# Check agent logs
journalctl -u system-trace-agent -f

# Test agent manually
/opt/system-trace-agent/system-trace_agent.py

# Check Python dependencies
python3 -c "import psutil; print('psutil OK')"
```

#### **Fix agent issues**
```bash
# Restart agent service
sudo systemctl restart system-trace-agent

# Install missing dependencies
sudo pip3 install psutil

# Check agent configuration
cat /etc/systemd/system/system-trace-agent.service
```

## Monitoring Dashboard

After successful deployment, you should see:

### **Configuration Page**
- SNMP Host: centos-docker
- SNMP Port: 161
- SNMP Community: public
- ICMP Host: centos-docker
- NTP Server: pool.ntp.org

### **Overview Page**
- **Protocol Health** section showing:
  - SNMP: OK (green)
  - NTP: OK (green)
  - ICMP: OK (green)

### **Main Dashboard**
- Real-time metrics from centos-docker
- System resource utilization
- Network performance indicators

## Advanced Configuration

### **Custom SNMP Community**
If you need a different SNMP community:

```bash
# On centos-docker
sudo nano /etc/snmp/snmpd.conf
# Change: rocommunity public
# To: rocommunity your_community

sudo systemctl restart snmpd

# Update System Trace .env
SNMP_COMMUNITY=your_community
```

### **Custom NTP Servers**
For specific NTP requirements:

```bash
# On centos-docker
sudo nano /etc/ntp.conf
# Add your NTP servers
server your.ntp.server1 iburst
server your.ntp.server2 iburst

sudo systemctl restart ntpd
```

### **Agent Metrics Customization**
Modify the agent script to collect additional metrics:

```bash
# On centos-docker
sudo nano /opt/system-trace-agent/system-trace_agent.py
# Add custom metrics to get_system_metrics() function

sudo systemctl restart system-trace-agent
```

## Security Considerations

### **SNMP Security**
- Change default community string from "public"
- Consider SNMPv3 for enhanced security
- Restrict SNMP access to management networks

### **Agent Security**
- Run agent with minimal privileges
- Secure agent communication
- Monitor agent logs for security events

### **Network Security**
- Use firewall rules to restrict access
- Monitor for unauthorized SNMP queries
- Implement network segmentation

## Maintenance

### **Regular Tasks**
1. **Monitor dashboard** for status changes
2. **Check logs** for error patterns
3. **Update packages** on centos-docker
4. **Verify time synchronization** regularly
5. **Test SNMP connectivity** periodically

### **Performance Optimization**
1. **Adjust check intervals** based on requirements
2. **Monitor resource usage** of agent
3. **Optimize SNMP queries** for efficiency
4. **Review NTP server** selection

## Support

### **Common Issues and Solutions**
- **SNMP timeouts**: Increase timeout values
- **NTP drift**: Check network connectivity
- **Agent crashes**: Review logs and dependencies
- **Firewall blocks**: Verify port accessibility

### **Getting Help**
1. Check System Trace dashboard for real-time status
2. Review system logs on centos-docker
3. Test connectivity manually
4. Consult this guide for troubleshooting steps

---

**Status**: Configuration complete, deployment scripts ready
**Next Step**: Execute deployment scripts on centos-docker host
**Dashboard**: http://localhost:8001
