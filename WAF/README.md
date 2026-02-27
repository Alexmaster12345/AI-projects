# WAF — ModSecurity + Nginx from Scratch

A production-ready Web Application Firewall built on **ModSecurity v3** + **Nginx** + **OWASP Core Rule Set (CRS) v4**, configured from scratch on Rocky Linux.

## Architecture

```
Internet
    │
    ▼ HTTP/HTTPS (port 80/443)
┌─────────────────────────────────┐
│   Nginx + ModSecurity v3 (WAF)  │
│                                 │
│  ┌─────────────────────────┐    │
│  │   OWASP CRS v4 Rules    │    │
│  │   Custom Rules          │    │
│  │   Rate Limiting         │    │
│  │   IP Blocklist          │    │
│  └─────────────────────────┘    │
└─────────────────────────────────┘
    │
    ▼ proxy_pass (port 8080)
┌─────────────────────────────────┐
│   Backend Application Server    │
│   (any app: Node, Python, etc.) │
└─────────────────────────────────┘
```

## What It Blocks

| Attack Type | Detection Method |
|-------------|-----------------|
| SQL Injection | OWASP CRS + custom rules |
| Cross-Site Scripting (XSS) | OWASP CRS + CSP headers |
| Local File Inclusion (LFI) | OWASP CRS + path traversal rules |
| Remote Code Execution (RCE) | OWASP CRS |
| Remote File Inclusion (RFI) | OWASP CRS |
| Scanner/Bot detection | Custom User-Agent rules |
| Rate limiting | nginx `limit_req` + ModSecurity counters |
| Web shell uploads | Custom filename rules |
| Protocol violations | OWASP CRS + custom |
| HTTP response splitting | OWASP CRS |
| Null byte injection | Custom rules |

## Quick Setup

### 1. Prerequisites

- Rocky Linux 8/9/10 (or any RHEL-based distro)
- Root / sudo access
- Internet access for downloading ModSecurity and CRS
- A backend app server running on `http://127.0.0.1:8080`

### 2. Configure

Edit the top of `setup.sh`:

```bash
BACKEND_URL="http://127.0.0.1:8080"   # Your app server
WAF_PORT=80                            # Port WAF listens on
WAF_DOMAIN="_"                         # Server name (_ = catch-all)
```

### 3. Run Setup

```bash
sudo bash setup.sh
```

This will:
1. Install all build dependencies
2. Build **ModSecurity v3** from source
3. Build the **ModSecurity-nginx connector** dynamic module
4. Download **OWASP CRS v4**
5. Configure nginx with WAF virtual host
6. Set correct SELinux contexts and firewall rules
7. Start nginx

### 4. Test the WAF

```bash
bash test-waf.sh http://localhost
```

Runs 40+ attack simulations across all major attack categories and reports block rate.

### 5. Monitor Logs

```bash
# Live blocked requests
sudo tail -f /var/log/waf/modsec_audit.log

# Live access log
sudo tail -f /var/log/waf/access.log

# Debug (increase SecDebugLogLevel in modsecurity.conf for more detail)
sudo tail -f /var/log/waf/modsec_debug.log
```

---

## Project Structure

```
WAF/
├── setup.sh                    # Full automated setup script
├── test-waf.sh                 # Attack simulation test suite
├── config/
│   ├── nginx-waf.conf          # Nginx WAF virtual host config
│   ├── modsecurity.conf        # ModSecurity main config
│   ├── crs-setup.conf          # OWASP CRS paranoia/threshold config
│   └── custom-rules.conf       # Site-specific custom rules (IDs 1000-1999)
└── README.md
```

**Live deployment paths (after running setup.sh):**

| Config File | Deployed to |
|-------------|-------------|
| `config/nginx-waf.conf` | `/etc/nginx/conf.d/waf.conf` |
| `config/modsecurity.conf` | `/etc/nginx/modsec/modsecurity.conf` |
| `config/crs-setup.conf` | `/etc/nginx/modsec/crs/crs-setup.conf` |
| `config/custom-rules.conf` | `/etc/nginx/modsec/custom-rules.conf` |
| OWASP CRS rules | `/etc/nginx/modsec/crs/rules/` |
| WAF logs | `/var/log/waf/` |
| Error pages | `/etc/nginx/waf-pages/` |

---

## Configuration Reference

### ModSecurity Rule Engine Modes

Edit `/etc/nginx/modsec/modsecurity.conf`:

```apache
SecRuleEngine On             # Block + log (production)
SecRuleEngine DetectionOnly  # Log only, never block (tuning mode)
SecRuleEngine Off            # Disabled
```

### Paranoia Level (OWASP CRS)

Edit `/etc/nginx/modsec/crs/crs-setup.conf`:

```apache
setvar:tx.blocking_paranoia_level=1   # Level 1 = low false positives (recommended)
setvar:tx.blocking_paranoia_level=2   # More rules, some false positives
setvar:tx.blocking_paranoia_level=3   # High security — tune carefully
setvar:tx.blocking_paranoia_level=4   # Maximum — many false positives
```

### Anomaly Scoring Thresholds

```apache
setvar:tx.inbound_anomaly_score_threshold=5    # Block if score >= 5 (1 critical hit)
setvar:tx.inbound_anomaly_score_threshold=10   # More lenient
setvar:tx.outbound_anomaly_score_threshold=4   # Response scanning
```

### Custom Rules

Add to `/etc/nginx/modsec/custom-rules.conf`. Rules use IDs 1000–1999.

```apache
# Block specific IP
SecRule REMOTE_ADDR "@ipMatch 1.2.3.4" \
  "id:1020,phase:1,deny,status:403,log,msg:'Blocked IP'"

# Whitelist trusted IP range (bypass WAF)
SecRule REMOTE_ADDR "@ipMatch 192.168.50.0/24" \
  "id:1030,phase:1,allow,nolog,msg:'Trusted IP'"

# Block specific URI pattern
SecRule REQUEST_URI "@contains /api/admin" \
  "id:1040,phase:1,deny,status:403,log,msg:'Admin API blocked externally'"
```

### Rate Limiting

Two layers:

1. **nginx `limit_req`** (in `nginx-waf.conf`) — 30 req/sec, burst 50
2. **ModSecurity IP counter** (in `custom-rules.conf`) — 100 req/60 sec

Adjust in respective config files.

### Excluding Rules (Tuning)

To disable a specific CRS rule causing false positives:

```apache
# In custom-rules.conf — disable rule 942100 (SQL injection)
SecRuleRemoveById 942100

# Disable for specific URI only
SecRule REQUEST_URI "@beginsWith /api/search" \
  "id:1100,phase:1,pass,nolog,ctl:ruleRemoveById=942100"
```

---

## HTTPS / SSL

After obtaining a certificate (Let's Encrypt recommended):

```bash
sudo dnf install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

Or use the commented HTTPS server block in `config/nginx-waf.conf`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ngx_http_modsecurity_module.so` not found | Check `NGINX_MOD_DIR` in setup.sh matches nginx modules path |
| nginx fails to start | Run `nginx -t` and check `/var/log/nginx/error.log` |
| Everything gets blocked | Switch to `SecRuleEngine DetectionOnly` to tune |
| False positives | Lower paranoia level or remove specific rule IDs |
| High CPU usage | Disable response body inspection: `SecResponseBodyAccess Off` |
| SELinux denials | Run `ausearch -c nginx --raw \| audit2allow -M nginx-waf` |

```bash
# Reload nginx after config changes
sudo nginx -t && sudo systemctl reload nginx

# Check which rule blocked a request
sudo grep "id \"942" /var/log/waf/modsec_audit.log | tail -20

# Test nginx config
sudo nginx -t

# Check ModSecurity is loaded
nginx -V 2>&1 | grep modsecurity
```
