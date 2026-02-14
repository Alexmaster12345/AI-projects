# SIEM MVP (local)

Minimal SIEM you can run locally:

- HTTP ingest (`POST /ingest`)
- SQLite storage (`data/siem.sqlite3`)
- YAML detection rules (`rules/default.yml`)
- Web dashboard with search (`GET /`)
- Tail/shipper agent (`scripts/collector_tail.py`)

## Glossary

- **SIEM (Security Information & Event Management)**: Centralizes log data from various sources (network, servers, apps) for real-time analysis, threat detection, and compliance.
- **EDR/XDR (Endpoint/Extended Detection & Response)**: Monitors endpoints (laptops, servers) for malicious activity, offering deep visibility, behavioral analysis, and response actions.
- **SOAR (Security Orchestration, Automation & Response)**: Automates repetitive security tasks and workflows (like alert triage and enrichment) to speed up incident response.
- **Threat Intelligence Platforms (TIPs)**: Aggregates and analyzes threat data from various feeds to provide context and proactive defense.
- **Vulnerability Management**: Scans for, prioritizes, and manages security weaknesses in systems and applications.
- **NDR (Network Detection & Response)**: Analyzes network traffic for anomalies and threats.
- **Cloud Security (CSPM/CDR)**: Focuses on security posture management and detection/response in cloud environments.

## Setup

```bash
cd /home/alex/siem
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run API

```bash
cd /home/alex/siem
source .venv/bin/activate
uvicorn siem.app:app --reload --host 127.0.0.1 --port 8000
```

## Security hardening

Auth is **opt-in**: the server only enforces authentication if you set at least one of the auth env vars.

### Option A: API key (recommended for agents/scripts)

Server:

```bash
export SIEM_API_KEY='change-me-to-a-long-random-secret'
```

Client (curl):

```bash
curl -sS http://127.0.0.1:8000/events -H "x-api-key: $SIEM_API_KEY" | jq
```

EDR agent:

```bash
SIEM_API_KEY="$SIEM_API_KEY" python scripts/edr_agent.py --server http://127.0.0.1:8000 --interval 5
```

### Option B: HTTP Basic auth (works well for browser UI)

Server:

```bash
export SIEM_BASIC_USER='admin'
export SIEM_BASIC_PASS='change-me-to-a-long-random-secret'
```

Then open the dashboard; your browser will prompt for credentials.

### Other security knobs

- `SIEM_AUTH_EXEMPT_PATHS` (default `/health`): comma-separated exact paths (or `*` suffix) that do not require auth.
- `SIEM_TRUSTED_HOSTS`: comma-separated allowed Host headers (enables TrustedHostMiddleware). Example: `127.0.0.1,localhost,VOLVIX.local`.
- `SIEM_RATE_LIMIT_ENABLED`: set to `true` to enable simple per-IP rate limiting.
- `SIEM_RATE_LIMIT_RPS` / `SIEM_RATE_LIMIT_BURST`: rate limit tuning (defaults are high for local use).
- `SIEM_RATE_LIMIT_PATHS` (default `/ingest,/edr`): paths/prefixes to rate limit.
- `SIEM_MAX_BODY_BYTES` (default 1048576): rejects large POST bodies when `Content-Length` exceeds this.

Note: For real deployments, terminate TLS (HTTPS) in front of this service.

### Use a local hostname (VOLVIX.local)

To access the UI as `http://VOLVIX.local:8000/`, map the name to localhost:

```bash
sudo sh -c 'echo "127.0.0.1 VOLVIX.local" >> /etc/hosts'
```

Open:
- http://VOLVIX.local:8000/ (dashboard)
- http://VOLVIX.local:8000/docs (Swagger)

## Health & stats

```bash
curl -sS http://127.0.0.1:8000/health | jq
curl -sS 'http://127.0.0.1:8000/stats?hours=24' | jq
```

## Query filters (ip / agent_id)

The API supports simple server-side filters for IPs and EDR agent IDs.

```bash
# Latest EDR events from a specific agent
curl -sS 'http://127.0.0.1:8000/events?agent_id=demo-agent&limit=50' | jq

# Latest events containing a specific IP (stored in events.ips)
curl -sS 'http://127.0.0.1:8000/events?ip=203.0.113.77&limit=50' | jq

# Search + filter together
curl -sS 'http://127.0.0.1:8000/search?q=edr_listen_socket&agent_id=demo-agent&limit=50' | jq

# Alerts tied to events containing an IP / agent_id
curl -sS 'http://127.0.0.1:8000/alerts?ip=203.0.113.77&limit=50' | jq
curl -sS 'http://127.0.0.1:8000/alerts?agent_id=demo-agent&limit=50' | jq
```

## Threat Intel (IOCs)

Add an IOC (types: `ip`, `domain`, `sha256`):

```bash
curl -sS http://127.0.0.1:8000/ti/iocs \
  -H 'content-type: application/json' \
  -d '{"type":"ip","value":"10.0.0.5","source":"demo","note":"test indicator"}' | jq
```

List IOCs:

```bash
curl -sS 'http://127.0.0.1:8000/ti/iocs?limit=50' | jq
```

When any ingested event (including `source="edr"`) contains a matching IOC in its message/fields,
the SIEM creates an alert with `rule_id` like `ti_ip`, `ti_domain`, or `ti_sha256`.

## Ingest an event

```bash
curl -sS http://127.0.0.1:8000/ingest \
  -H 'content-type: application/json' \
  -d '{
    "source": "syslog",
    "host": "demo-host",
    "message": "Failed password for invalid user admin from 10.0.0.5 port 53422 ssh2",
    "fields": {"program": "sshd"}
  }' | jq
```

Then check alerts:

```bash
curl -sS 'http://127.0.0.1:8000/alerts?limit=20' | jq

If you set up `VOLVIX.local` above, you can also use `http://VOLVIX.local:8000/...` for all API calls.
```

## Tail a log file into SIEM

Example: tail `/var/log/auth.log` (requires permissions):

```bash
cd /home/alex/siem
source .venv/bin/activate
python scripts/collector_tail.py --file /var/log/auth.log --endpoint http://127.0.0.1:8000/ingest
```

### Recommended log source tagging

The shipper supports tagging events so the SIEM can normalize different sources consistently:

```bash
python scripts/collector_tail.py \
  --file /var/log/nginx/access.log \
  --endpoint http://127.0.0.1:8000/ingest \
  --source file \
  --log-type web
```

Common `--log-type` values supported by the normalizer:

- `web` (Apache/Nginx access logs)
- `firewall` (UFW/iptables style)
- `dns` (BIND/unbound query logs)
- `dhcp` (ISC DHCP style)
- `sudo` (Linux sudo events)
- `windows_security` / `powershell` (Windows Event Logs shipped as JSON)

### Network / infrastructure syslog

If routers/switches/firewalls send syslog, forward UDP syslog into the SIEM:

```bash
cd /home/alex/siem
source .venv/bin/activate
python scripts/syslog_udp_shipper.py --bind 0.0.0.0 --port 5140 --endpoint http://127.0.0.1:8000/ingest
```

Then point your devices to `UDP/5140` on this host.

### Example source mapping (quick starts)

- Firewall logs (UFW): tail `/var/log/ufw.log` with `--log-type firewall`
- DNS query logs (BIND): tail `/var/log/named/named.log` with `--log-type dns`
- DHCP leases (ISC dhcpd): tail `/var/log/syslog` (or dhcpd log) with `--log-type dhcp`
- Web gateway / proxy logs: ship as JSON or raw lines with a `fields.log_type` of `web`
- Windows Event Logs: ship JSON that includes `fields.EventID` and common fields like `TargetUserName`, `IpAddress`

## EDR (endpoint agent)

This repo now includes a minimal Linux EDR agent that:

- registers to the SIEM (`POST /edr/register`)
- sends telemetry (`POST /edr/telemetry`, stored as regular events with `source="edr"`)
- polls a response-action queue (`GET /edr/actions/poll`)

Run the agent:

```bash
cd /home/alex/siem
source .venv/bin/activate
python scripts/edr_agent.py --server http://127.0.0.1:8000 --interval 5
```

By default the agent will NOT execute response actions. To enable response actions (dangerous / requires permissions), run:

```bash
python scripts/edr_agent.py --server http://127.0.0.1:8000 --allow-response
```

Some response actions (endpoint isolation / IP blocking) require root / elevated capabilities on the endpoint. If you want those to work, run the agent with sufficient privileges (for example: `sudo -E ...`).

The server also enforces an allowlist for these “dangerous” actions. Set `EDR_DANGEROUS_ACTION_ALLOWLIST` (comma-separated `requested_by` values, or `*`) in the SIEM server environment.

List registered endpoints:

```bash
curl -sS 'http://127.0.0.1:8000/edr/endpoints?limit=50' | jq
```

Queue a response action (examples):

```bash
# Ask an agent to compute a SHA256 for a file
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"collect_file_hash","params":{"path":"/bin/bash"},"requested_by":"demo"}' | jq

# Ask an agent to terminate a PID
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"kill_process","params":{"pid":1234},"requested_by":"demo"}' | jq

# Isolate an endpoint (firewall lockdown; keeps SIEM connectivity)
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"isolate_endpoint","params":{},"requested_by":"demo"}' | jq

# Remove isolation
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"unisolate_endpoint","params":{},"requested_by":"demo"}' | jq

# Block an IPv4
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"block_ip","params":{"ip":"10.0.0.5"},"requested_by":"demo"}' | jq

# Unblock an IPv4
curl -sS http://127.0.0.1:8000/edr/actions \
  -H 'content-type: application/json' \
  -d '{"agent_id":"<agent_id>","action_type":"unblock_ip","params":{"ip":"10.0.0.5"},"requested_by":"demo"}' | jq
```

View action history/results:

```bash
curl -sS 'http://127.0.0.1:8000/edr/actions/history?agent_id=<agent_id>&limit=50' | jq
```

## MDR (Managed Detection & Response)

The SIEM includes a minimal MDR workflow to triage detections as incidents.

### MDR API

Create an incident (manual):

```bash
curl -sS http://127.0.0.1:8000/mdr/incidents \
  -H 'content-type: application/json' \
  -d '{"title":"Suspicious activity","severity":"high","assigned_to":"analyst1"}' | jq
```

Create an incident from an existing alert:

```bash
curl -sS http://127.0.0.1:8000/mdr/incidents \
  -H 'content-type: application/json' \
  -d '{"alert_id": 123, "assigned_to": "analyst1"}' | jq
```

List incidents:

```bash
curl -sS 'http://127.0.0.1:8000/mdr/incidents?limit=50' | jq
curl -sS 'http://127.0.0.1:8000/mdr/incidents?status=open&limit=50' | jq
```

Update incident state / assignment:

```bash
curl -sS http://127.0.0.1:8000/mdr/incidents/1 \
  -H 'content-type: application/json' \
  -d '{"status":"acknowledged","assigned_to":"analyst1"}' | jq
```

Add a note:

```bash
curl -sS http://127.0.0.1:8000/mdr/incidents/1/notes \
  -H 'content-type: application/json' \
  -d '{"author":"analyst1","note":"triaged"}' | jq
```

Get incident details:

```bash
curl -sS http://127.0.0.1:8000/mdr/incidents/1 | jq
```

### Optional: MDR webhook + auto-create incidents

The server can (best-effort) emit a webhook when alerts are created, and can auto-create incidents
for alerts at or above a minimum severity.

Environment variables:

- `MDR_WEBHOOK_URL`: If set, POSTs JSON on `alert.created`.
- `MDR_WEBHOOK_SECRET`: If set, adds `x-siem-signature: sha256=<hex>` HMAC for the request body.
- `MDR_WEBHOOK_TIMEOUT`: HTTP timeout seconds (default: 1.5).
- `MDR_AUTO_CREATE_INCIDENTS`: `1|true|yes` to enable auto incident creation on new alerts.
- `MDR_AUTO_CREATE_MIN_SEVERITY`: `low|medium|high|critical` (default: `medium`).

## Rules

Rules live in `rules/default.yml`.

Supported conditions:

- `contains`: substring match
- `equals`: exact string match
- `regex`: Python regex match
- `any`: OR group
- `all`: AND group
