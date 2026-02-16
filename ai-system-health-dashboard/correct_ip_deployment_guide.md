# CentOS-Docker Deployment Guide - Correct IP

## ✅ IP Address Updated

**Name**: centos-docker  
**Correct IP**: 192.168.50.198  
**Previous IP**: 192.168.50.225 (incorrect)

## 🎯 Current Status

### **✅ Configuration Updated**
```bash
ICMP_HOST=192.168.50.198
SNMP_HOST=192.168.50.198
```

### **✅ Connectivity Verified**
```bash
✅ Packet loss: 0%
✅ Average response time: 0.408ms
✅ Hostname resolution: Working
```

### **✅ ASHD Server Reloaded**
- Configuration automatically applied
- Monitoring now targets correct IP
- Ready for agent deployment

## 🚀 Agent Deployment Commands

### **Step 1: Copy Scripts to CentOS-Docker**
```bash
scp deploy_centos_docker_agent.sh root@192.168.50.198:/root/
scp fix_ntp_centos_docker.sh root@192.168.50.198:/root/
```

### **Step 2: Connect to CentOS-Docker**
```bash
ssh root@192.168.50.198
```

### **Step 3: Run NTP Configuration**
```bash
sudo ./fix_ntp_centos_docker.sh
```

### **Step 4: Deploy ASHD Agent**
```bash
sudo ./deploy_centos_docker_agent.sh
```

### **Step 5: Verify Deployment**
```bash
# Check services
systemctl status snmpd
systemctl status ntpd
systemctl status ashd-agent

# Test SNMP
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0

# Check NTP
ntpq -p

# Check agent logs
journalctl -u ashd-agent -f
```

### **Step 6: Return and Check Dashboard**
```bash
exit
# Open: http://localhost:8001
```

## 📊 Expected Results

### **Before Agent Deployment**
```
ICMP: OK · 192.168.50.198 responding
SNMP: UNKNOWN · not configured in dashboard
NTP: Clock skew / NTP server reachability (udp/123)
```

### **After Agent Deployment**
```
ICMP: OK · 192.168.50.198 responding
SNMP: OK · centos-docker responding
NTP: OK · Time synchronized
Agent: OK · Metrics reporting normally
```

## 🔍 Verification Checklist

### **Dashboard Checks**
- [ ] Configuration page shows ICMP_HOST=192.168.50.198
- [ ] Configuration page shows SNMP_HOST=192.168.50.198
- [ ] Overview page shows ICMP status as "OK"
- [ ] System logs show no hostname resolution errors

### **Agent Checks (on centos-docker)**
- [ ] SNMP service running: `systemctl status snmpd`
- [ ] NTP service running: `systemctl status ntpd`
- [ ] ASHD agent running: `systemctl status ashd-agent`
- [ ] SNMP responding: `snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0`
- [ ] NTP synchronized: `ntpq -p`

### **Network Checks**
- [ ] Ping from ASHD server: `ping 192.168.50.198`
- [ ] Ping hostname: `ping centos-docker`
- [ ] SNMP from ASHD server: `snmpwalk -v2c -c public 192.168.50.198 1.3.6.1.2.1.1.1.0`

## 🛠️ Troubleshooting

### **SNMP Issues**
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

### **NTP Issues**
```bash
# Check NTP status
ntpq -p

# Force NTP sync
ntpdate -u pool.ntp.org

# Restart NTP service
systemctl restart ntpd
```

### **Agent Issues**
```bash
# Check agent service
systemctl status ashd-agent

# Check agent logs
journalctl -u ashd-agent -f

# Test agent manually
/opt/ashd-agent/ashd_agent.py
```

### **Connectivity Issues**
```bash
# Test from ASHD server
ping -c 3 192.168.50.198

# Test hostname resolution
nslookup centos-docker

# Check ports
nmap -p 161,123 192.168.50.198
```

## 📈 Monitoring Capabilities

### **After Deployment**
- **Real-time ICMP monitoring**: Response times, packet loss
- **SNMP system metrics**: CPU, memory, disk, network
- **NTP time synchronization**: Clock accuracy
- **Agent metrics**: Process monitoring, system health
- **Historical data**: 24-hour retention and trends

### **Dashboard Features**
- **Protocol Health**: ICMP, SNMP, NTP status
- **System Metrics**: Real-time performance data
- **Alert System**: Automatic fault detection
- **Historical Analysis**: Performance trends

## 🎯 Use Cases Enabled

### **Network Performance Monitoring**
- Response time tracking (0.408ms current)
- Packet loss monitoring (0% current)
- Network availability status
- Historical performance analysis

### **Fault Detection**
- Device reachability monitoring
- Service health checks
- Protocol failure detection
- Automatic alert generation

### **Device Inventory Management**
- System information collection
- Hardware and software inventory
- Network topology mapping
- Asset management tracking

## 📚 Documentation

- **Full Guide**: `docs/CENTOS_DOCKER_DEPLOYMENT.md`
- **Network Monitoring**: `docs/NETWORK_MONITORING_GUIDE.md`
- **Status Report**: `agent_status_report.json`
- **Deployment Scripts**: Ready and updated

---

**Status**: ✅ **IP address corrected, connectivity verified, ready for deployment**
**Target**: 192.168.50.198 (centos-docker)
**Dashboard**: http://localhost:8001
**Next**: Deploy SNMP agent using commands above
