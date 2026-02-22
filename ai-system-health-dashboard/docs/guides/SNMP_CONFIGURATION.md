# SNMP Configuration Guide for System Trace

## Overview

System Trace supports SNMP monitoring to track the health and availability of network devices, servers, and infrastructure equipment. This guide explains how to configure SNMP monitoring.

## Current Status

❌ **SNMP is currently not configured** - The dashboard shows "SNMP UNKNOWN · not configured in dashboard"

## Quick Setup Options

### Option 1: Use SNMP Simulator (Recommended for Testing)

Perfect for testing SNMP functionality without real hardware:

```bash
# 1. Start SNMP simulator
cd /home/alexk/AI-projects/ai-system-health-dashboard
python scripts/snmp_simulator.py

# 2. In another terminal, configure System Trace
python scripts/setup_snmp.py
# Enter: localhost
# Enter: 1161 (if simulator uses alternative port)
# Enter: public
# Enter: 2

# 3. Restart System Trace server
# Stop current server (Ctrl+C) and restart:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Option 2: Configure Real SNMP Device

If you have a real SNMP device (router, switch, server):

```bash
# 1. Test SNMP connectivity
python scripts/test_snmp_devices.py

# 2. Configure System Trace with working device
python scripts/setup_snmp.py
# Enter the IP/hostname of your SNMP device
# Enter community string (usually "public")
# Enter port (usually 161)

# 3. Restart System Trace server
```

## Configuration Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `SNMP_HOST` | SNMP device IP or hostname | "" (disabled) | "192.168.1.1" |
| `SNMP_PORT` | SNMP port number | 161 | 161 |
| `SNMP_COMMUNITY` | SNMP community string | "" | "public" |
| `SNMP_TIMEOUT_SECONDS` | SNMP query timeout | 2.0 | 2.0 |

## Environment Variables

Add these to your `.env` file:

```bash
# Enable SNMP monitoring
SNMP_HOST=192.168.1.1
SNMP_PORT=161
SNMP_COMMUNITY=public
SNMP_TIMEOUT_SECONDS=2

# Disable SNMP (empty host)
SNMP_HOST=
```

## Common SNMP Devices

### Network Equipment
- **Routers**: 192.168.1.1, 192.168.0.1
- **Switches**: 192.168.1.x range
- **Firewalls**: Usually gateway IP

### Servers
- **Linux servers**: Require SNMP daemon installation
- **Windows servers**: Enable SNMP service
- **VMware ESXi**: Built-in SNMP support

### IoT Devices
- **APC UPS**: Network management cards
- **Printers**: Network printers with SNMP
- **IP cameras**: Many support SNMP

## Device Setup Examples

### Linux Server SNMP Setup

```bash
# Install SNMP daemon
sudo apt-get install snmp snmpd  # Ubuntu/Debian
sudo dnf install net-snmp net-snmp-utils  # CentOS/RHEL

# Configure SNMP
sudo nano /etc/snmp/snmpd.conf
# Add: rocommunity public

# Restart SNMP service
sudo systemctl restart snmpd
sudo systemctl enable snmpd

# Test
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0
```

### Cisco Router SNMP Setup

```
enable
configure terminal
snmp-server community public RO
snmp-server location "Data Center"
snmp-server contact "Network Admin"
end
write memory
```

### Windows Server SNMP Setup

1. Install SNMP feature via Server Manager
2. Configure SNMP service:
   - Community: public
   - Accept SNMP packets from any host
3. Test with PowerShell:
   ```powershell
   Get-WmiObject -Class Win32_OperatingSystem
   ```

## Troubleshooting

### SNMP Not Responding

1. **Check network connectivity**:
   ```bash
   ping 192.168.1.1
   telnet 192.168.1.1 161
   ```

2. **Verify SNMP service**:
   ```bash
   snmpwalk -v2c -c public 192.168.1.1 1.3.6.1.2.1.1.1.0
   ```

3. **Check firewall**:
   ```bash
   # Allow SNMP (UDP 161)
   sudo ufw allow 161/udp
   ```

4. **Verify community string**:
   - Try common communities: "public", "private", "admin"
   - Check device documentation

### Permission Issues

SNMP port 161 requires root privileges. Use alternative port for testing:

```bash
# Use port 1161 for testing
SNMP_PORT=1161
```

### System Trace Still Shows "Not Configured"

1. **Check .env file**:
   ```bash
   cat .env | grep SNMP
   ```

2. **Restart System Trace server**:
   - Stop current server (Ctrl+C)
   - Start again: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`

3. **Check configuration page**:
   - Visit http://localhost:8001/configuration
   - Verify SNMP settings are displayed

## Advanced Configuration

### Multiple SNMP Devices

For monitoring multiple devices, you can:

1. **Use network management system** (NMS) like:
   - Zabbix
   - Nagios
   - Prometheus with SNMP exporter

2. **Configure System Trace for critical device**:
   - Choose most important device for System Trace monitoring
   - Use NMS for comprehensive monitoring

### SNMPv3 Configuration

For enhanced security, configure SNMPv3:

```bash
# SNMPv3 example (future enhancement)
SNMP_VERSION=3
SNMP_USER=monitoring
SNMP_AUTH_PROTOCOL=SHA
SNMP_AUTH_PASSWORD=secret123
SNMP_PRIV_PROTOCOL=AES
SNMP_PRIV_PASSWORD=secret456
```

## Security Considerations

1. **Use SNMPv3** instead of SNMPv2c when possible
2. **Restrict SNMP access** to management networks only
3. **Change default community strings**
4. **Monitor SNMP logs** for unusual activity
5. **Use firewall rules** to limit SNMP access

## Integration with System Trace

Once SNMP is configured, System Trace will:

- ✅ Show SNMP status on dashboard
- ✅ Monitor device availability
- ✅ Track response times
- ✅ Log SNMP failures
- ✅ Display device information

The SNMP status will change from:
- ❌ "SNMP UNKNOWN · not configured in dashboard"
- To ✅ "SNMP OK · device responding"

## Support Scripts

System Trace includes helpful scripts:

- `scripts/setup_snmp.py` - Interactive SNMP configuration
- `scripts/test_snmp_devices.py` - Test multiple devices
- `scripts/snmp_simulator.py` - SNMP simulator for testing

## Next Steps

1. Choose setup option (simulator vs real device)
2. Configure SNMP using setup script
3. Restart System Trace server
4. Verify SNMP status on dashboard
5. Monitor SNMP performance in overview

For additional help, check the System Trace documentation or create an issue on GitHub.
