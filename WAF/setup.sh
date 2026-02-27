#!/usr/bin/env bash
# =============================================================================
# WAF Setup: ModSecurity v3 + Nginx + OWASP CRS (Rocky Linux / RHEL-based)
# Run as root or with sudo
# =============================================================================
set -euo pipefail

# --------------------------------------------------------------------------
# CONFIGURATION — edit these before running
# --------------------------------------------------------------------------
BACKEND_URL="http://127.0.0.1:8080"   # The app server WAF will proxy to
WAF_PORT=80                            # Port nginx WAF listens on
WAF_DOMAIN="_"                         # Server name (_ = catch-all)
NGINX_VERSION="1.26.3"                 # Nginx version to build connector against
LOG_DIR="/var/log/waf"
MODSEC_DIR="/etc/nginx/modsec"
CRS_DIR="/etc/nginx/modsec/crs"
BUILD_DIR="/tmp/waf-build"

# --------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[WAF]${NC} $*"; }
warn() { echo -e "${YELLOW}[WAF]${NC} $*"; }
die()  { echo -e "${RED}[WAF] ERROR:${NC} $*" >&2; exit 1; }

[[ $EUID -ne 0 ]] && die "Run this script as root (sudo bash setup.sh)"

# --------------------------------------------------------------------------
# 1. System dependencies
# --------------------------------------------------------------------------
log "Installing build dependencies..."
dnf install -y epel-release 2>/dev/null || true
dnf install -y \
  gcc gcc-c++ make automake autoconf libtool pkgconfig \
  git curl wget pcre pcre-devel zlib zlib-devel \
  openssl openssl-devel libxml2 libxml2-devel \
  yajl yajl-devel libmaxminddb libmaxminddb-devel \
  lmdb lmdb-devel ssdeep ssdeep-devel \
  lua lua-devel libcurl libcurl-devel \
  geoip geoip-devel \
  nginx --skip-broken 2>/dev/null || true

# --------------------------------------------------------------------------
# 2. Build ModSecurity v3 from source
# --------------------------------------------------------------------------
log "Building ModSecurity v3 from source..."
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [[ ! -d ModSecurity ]]; then
  git clone --depth 1 --branch v3/master \
    https://github.com/owasp-modsecurity/ModSecurity ModSecurity
fi

cd ModSecurity
git submodule init
git submodule update

./build.sh
./configure --prefix=/usr/local \
  --with-lmdb \
  --with-lua \
  --with-yajl \
  --with-ssdeep \
  --with-libmaxminddb

make -j"$(nproc)"
make install

log "ModSecurity v3 installed to /usr/local"

# --------------------------------------------------------------------------
# 3. Build ModSecurity-nginx connector
# --------------------------------------------------------------------------
log "Building ModSecurity-nginx connector..."
cd "$BUILD_DIR"

# Get installed nginx version
NGINX_INSTALLED=$(nginx -v 2>&1 | grep -oP '[\d.]+' | head -1 || echo "$NGINX_VERSION")
log "Nginx version detected: $NGINX_INSTALLED"

if [[ ! -d ModSecurity-nginx ]]; then
  git clone --depth 1 \
    https://github.com/owasp-modsecurity/ModSecurity-nginx ModSecurity-nginx
fi

# Download matching nginx source for module compilation only
NGINX_SRC="nginx-${NGINX_INSTALLED}"
if [[ ! -d "$NGINX_SRC" ]]; then
  wget -q "http://nginx.org/download/${NGINX_SRC}.tar.gz"
  tar xzf "${NGINX_SRC}.tar.gz"
fi

cd "$NGINX_SRC"

# Get nginx configure args
NGINX_CONFIG_ARGS=$(nginx -V 2>&1 | grep "configure arguments:" | sed 's/configure arguments: //')

./configure $NGINX_CONFIG_ARGS \
  --add-dynamic-module=../ModSecurity-nginx

make -j"$(nproc)" modules

# Copy dynamic module
NGINX_MOD_DIR=$(nginx -V 2>&1 | grep -oP -- '--modules-path=\K[^\s]+' || echo "/usr/lib64/nginx/modules")
mkdir -p "$NGINX_MOD_DIR"
cp objs/ngx_http_modsecurity_module.so "$NGINX_MOD_DIR/"
log "Module copied to $NGINX_MOD_DIR/ngx_http_modsecurity_module.so"

# --------------------------------------------------------------------------
# 4. Download OWASP Core Rule Set (CRS)
# --------------------------------------------------------------------------
log "Downloading OWASP CRS v4..."
mkdir -p "$CRS_DIR"

CRS_VERSION="4.9.0"
CRS_TAR="coreruleset-${CRS_VERSION}.tar.gz"

cd /tmp
if [[ ! -f "$CRS_TAR" ]]; then
  wget -q "https://github.com/coreruleset/coreruleset/archive/refs/tags/v${CRS_VERSION}.tar.gz" \
    -O "$CRS_TAR"
fi

tar xzf "$CRS_TAR" -C /tmp
cp -r /tmp/coreruleset-${CRS_VERSION}/rules "$CRS_DIR/"
cp /tmp/coreruleset-${CRS_VERSION}/crs-setup.conf.example "$CRS_DIR/crs-setup.conf"

log "OWASP CRS $CRS_VERSION installed to $CRS_DIR"

# --------------------------------------------------------------------------
# 5. Create ModSecurity configuration
# --------------------------------------------------------------------------
log "Creating ModSecurity configuration..."
mkdir -p "$MODSEC_DIR"

# Copy default ModSecurity config
cp /usr/local/share/modsecurity/unicode.mapping "$MODSEC_DIR/" 2>/dev/null || \
  cp "$BUILD_DIR/ModSecurity/unicode.mapping" "$MODSEC_DIR/" 2>/dev/null || true

# Main ModSec config
cat > "$MODSEC_DIR/modsecurity.conf" << 'MODSECCONF'
# =============================================================================
# ModSecurity Main Configuration
# =============================================================================

SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess On
SecResponseBodyMimeType text/plain text/html text/xml application/json

SecRequestBodyLimit 13107200
SecRequestBodyNoFilesLimit 131072
SecRequestBodyInMemoryLimit 131072
SecRequestBodyLimitAction Reject

SecPcreMatchLimit 100000
SecPcreMatchLimitRecursion 100000

SecDebugLog /var/log/waf/modsec_debug.log
SecDebugLogLevel 0

SecAuditEngine RelevantOnly
SecAuditLogRelevantStatus "^(?:5|4(?!04))"
SecAuditLogParts ABIJDEFHZ
SecAuditLogType Serial
SecAuditLog /var/log/waf/modsec_audit.log

SecArgumentSeparator &
SecCookieFormat 0
SecUnicodeMapFile /etc/nginx/modsec/unicode.mapping 20127
SecStatusEngine Off
MODSECCONF

# Includes file — loads CRS
cat > "$MODSEC_DIR/main.conf" << MAINCONF
Include /etc/nginx/modsec/modsecurity.conf
Include /etc/nginx/modsec/crs/crs-setup.conf
Include /etc/nginx/modsec/crs/rules/*.conf
Include /etc/nginx/modsec/custom-rules.conf
MAINCONF

# Custom rules placeholder
cat > "$MODSEC_DIR/custom-rules.conf" << 'CUSTOMCONF'
# =============================================================================
# Custom WAF Rules
# Add your site-specific rules below
# =============================================================================

# Block requests with no User-Agent
SecRule &REQUEST_HEADERS:User-Agent "@eq 0" \
  "id:1001,phase:1,deny,status:400,log,msg:'Missing User-Agent header'"

# Block common scanner signatures
SecRule REQUEST_HEADERS:User-Agent "@pmf /etc/nginx/modsec/scanners.txt" \
  "id:1002,phase:1,deny,status:403,log,msg:'Scanner/Bot detected'"

# Rate limit — max 100 req/minute per IP (tracked via IP header)
# (ModSecurity rate limiting via setvar)
SecAction \
  "id:1010,phase:1,pass,initcol:ip=%{REMOTE_ADDR},nolog"

SecRule IP:REQUEST_COUNTER "@gt 100" \
  "id:1011,phase:1,deny,status:429,log,msg:'Rate limit exceeded',\
  expirevar:ip.request_counter=60"

SecAction \
  "id:1012,phase:1,pass,setvar:ip.request_counter=+1,nolog"
CUSTOMCONF

# Scanner signatures list
cat > "$MODSEC_DIR/scanners.txt" << 'SCANNERS'
nikto
sqlmap
nmap
masscan
zgrab
dirbuster
dirb
gobuster
nuclei
wfuzz
hydra
SCANNERS

log "ModSecurity configuration created at $MODSEC_DIR"

# --------------------------------------------------------------------------
# 6. Configure Nginx
# --------------------------------------------------------------------------
log "Configuring Nginx with ModSecurity..."

NGINX_MOD_DIR_CONF=$(nginx -V 2>&1 | grep -oP -- '--modules-path=\K[^\s]+' || echo "/usr/lib64/nginx/modules")

# Load module in main nginx.conf
NGINX_CONF="/etc/nginx/nginx.conf"
if ! grep -q "ngx_http_modsecurity_module" "$NGINX_CONF"; then
  sed -i "1s|^|load_module ${NGINX_MOD_DIR_CONF}/ngx_http_modsecurity_module.so;\n|" "$NGINX_CONF"
fi

# Create WAF virtual host config
mkdir -p /etc/nginx/conf.d
cat > /etc/nginx/conf.d/waf.conf << NGINXCONF
# =============================================================================
# Nginx WAF Virtual Host
# =============================================================================

server {
    listen ${WAF_PORT};
    server_name ${WAF_DOMAIN};

    # ModSecurity
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsec/main.conf;

    # Logging
    access_log /var/log/waf/access.log combined;
    error_log  /var/log/waf/error.log warn;

    # Security headers
    add_header X-Content-Type-Options "nosniff"   always;
    add_header X-Frame-Options        "SAMEORIGIN" always;
    add_header X-XSS-Protection       "1; mode=block" always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    server_tokens off;

    # Proxy to backend
    location / {
        modsecurity on;
        proxy_pass         ${BACKEND_URL};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout    60s;
        proxy_send_timeout    60s;
    }

    # WAF block page
    error_page 403 /waf-block.html;
    error_page 429 /waf-ratelimit.html;

    location = /waf-block.html {
        root /etc/nginx/waf-pages;
        internal;
    }
    location = /waf-ratelimit.html {
        root /etc/nginx/waf-pages;
        internal;
    }
}
NGINXCONF

# --------------------------------------------------------------------------
# 7. Custom error pages
# --------------------------------------------------------------------------
mkdir -p /etc/nginx/waf-pages

cat > /etc/nginx/waf-pages/waf-block.html << 'BLOCKPAGE'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>403 – Blocked by WAF</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; color: #e6edf3; font-family: -apple-system, sans-serif;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .box { text-align: center; padding: 40px; max-width: 480px; }
    .icon { font-size: 64px; margin-bottom: 20px; }
    h1 { font-size: 28px; color: #f85149; margin-bottom: 12px; }
    p  { color: #8b949e; line-height: 1.6; }
    code { background: #21262d; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
  </style>
</head>
<body>
  <div class="box">
    <div class="icon">🛡️</div>
    <h1>403 – Request Blocked</h1>
    <p>Your request has been blocked by the Web Application Firewall.</p>
    <p style="margin-top:16px">If you believe this is a mistake, contact the administrator with reference code: <code>WAF-403</code></p>
  </div>
</body>
</html>
BLOCKPAGE

cat > /etc/nginx/waf-pages/waf-ratelimit.html << 'RLPAGE'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>429 – Too Many Requests</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; color: #e6edf3; font-family: -apple-system, sans-serif;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .box { text-align: center; padding: 40px; max-width: 480px; }
    .icon { font-size: 64px; margin-bottom: 20px; }
    h1 { font-size: 28px; color: #d29922; margin-bottom: 12px; }
    p  { color: #8b949e; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="box">
    <div class="icon">⏱️</div>
    <h1>429 – Too Many Requests</h1>
    <p>You are sending too many requests. Please slow down and try again in a moment.</p>
  </div>
</body>
</html>
RLPAGE

# --------------------------------------------------------------------------
# 8. Log directory + SELinux
# --------------------------------------------------------------------------
log "Setting up log directory..."
mkdir -p "$LOG_DIR"
chown nginx:nginx "$LOG_DIR" 2>/dev/null || chown www-data:www-data "$LOG_DIR" 2>/dev/null || true
chmod 750 "$LOG_DIR"

# SELinux contexts if enabled
if command -v semanage &>/dev/null && sestatus 2>/dev/null | grep -q "enabled"; then
  log "Setting SELinux contexts..."
  semanage fcontext -a -t httpd_log_t      "/var/log/waf(/.*)?"      2>/dev/null || true
  semanage fcontext -a -t httpd_config_t   "/etc/nginx/modsec(/.*)?" 2>/dev/null || true
  restorecon -Rv /var/log/waf /etc/nginx/modsec 2>/dev/null || true
  setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi

# Firewall
if command -v firewall-cmd &>/dev/null; then
  log "Opening firewall port $WAF_PORT..."
  firewall-cmd --permanent --add-port="${WAF_PORT}/tcp" 2>/dev/null || true
  firewall-cmd --reload 2>/dev/null || true
fi

# --------------------------------------------------------------------------
# 9. Test config and start nginx
# --------------------------------------------------------------------------
log "Testing nginx configuration..."
nginx -t

log "Starting nginx..."
systemctl enable nginx
systemctl restart nginx

# --------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  WAF Setup Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  WAF listening on:   http://$(hostname -I | awk '{print $1}'):${WAF_PORT}"
echo "  Proxying to:        ${BACKEND_URL}"
echo "  ModSecurity config: ${MODSEC_DIR}/"
echo "  OWASP CRS rules:    ${CRS_DIR}/rules/"
echo "  Logs:               ${LOG_DIR}/"
echo ""
echo "  Next steps:"
echo "  1. Set BACKEND_URL at top of this script to your app server"
echo "  2. Check /var/log/waf/modsec_audit.log for blocked requests"
echo "  3. Run: bash test-waf.sh to simulate attacks"
echo "  4. Tune rules in ${MODSEC_DIR}/custom-rules.conf"
echo ""
