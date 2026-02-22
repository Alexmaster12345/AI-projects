from __future__ import annotations

import asyncio
from collections import deque
import json
import re
import secrets
import socket
import subprocess
import time
from html import escape
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .anomaly import compute_insights
from .auth_storage import auth_storage, init_auth_storage
from .config import settings
from .metrics import add_sample, collect_sample, history, latest
from .models import HostCreate, InventoryItemCreate, ProtocolStatus
from .storage import create_host as db_create_host
from .storage import create_inventory_item as db_create_inventory_item
from .storage import get_history as db_get_history
from .storage import get_hosts as db_get_hosts
from .storage import get_inventory_items as db_get_inventory_items
from .storage import get_latest as db_get_latest
from .storage import get_stats as db_get_stats
from .storage import deactivate_host as db_deactivate_host
from .storage import update_host as db_update_host
from .storage import delete_inventory_item as db_delete_inventory_item
from .storage import init_storage
from .storage import persist_sample
from .storage import prune_old
from .storage import vacuum as db_vacuum
from .storage import storage
from .protocols import start_protocol_checker


app = FastAPI(title="AI-Powered System Health Dashboard")


def _require_session_secret() -> None:
    if settings.session_secret_key.strip() == "":
        # Fail fast: without a secret, session cookies are unsafe/broken.
        raise RuntimeError(
            "SESSION_SECRET_KEY is required for login. Set it in env or in .env (see ai-system-health-dashboard/.env)."
        )


_require_session_secret()

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/") or path in ("/openapi.json",)


def _is_public_path(path: str) -> bool:
    # Only login endpoints are public; everything else requires auth.
    if path in ("/login",):
        return True
    # Allow a single public stylesheet for the login page.
    # Keep this allowlist tight: do NOT make all of /static public.
    if path == "/static/assets/login.css":
        return True
    # Allow favicon even when unauthenticated to avoid noisy logs.
    if path == "/favicon.ico":
        return True
    # Allow hosts management page
    if path == "/hosts":
        return True
    # User management pages (they handle their own auth)
    if path in ("/users", "/user-groups"):
        return True
    # Allow agent metrics endpoint for auto-discovery
    if path == "/api/agent/metrics":
        return True
    return False


def _get_session_user_id(request: Request) -> Optional[int]:
    try:
        v = request.session.get("user_id")  # type: ignore[attr-defined]
    except Exception:
        return None
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


async def _get_current_user(request: Request):
    user_id = _get_session_user_id(request)
    if user_id is None:
        return None
    return await asyncio.to_thread(auth_storage.get_user_by_id, user_id)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if _is_public_path(path):
            return await call_next(request)

        user = await _get_current_user(request)
        if user is None:
            remember_token = request.cookies.get(settings.remember_cookie_name)
            if remember_token:
                uid = await asyncio.to_thread(auth_storage.validate_remember_token, remember_token)
                if uid is not None:
                    try:
                        request.session["user_id"] = int(uid)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    user = await asyncio.to_thread(auth_storage.get_user_by_id, int(uid))
        if user is None or not user.is_active:
            if _is_api_path(path):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        # Admin-only endpoints
        if path.startswith("/api/admin/"):
            if user.role != "admin":
                return JSONResponse({"detail": "Forbidden"}, status_code=403)

        return await call_next(request)


# IMPORTANT: middleware order
# We want SessionMiddleware to run first (outermost) so request.session is available
# when AuthMiddleware runs.
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    max_age=int(settings.session_max_age_seconds),
    session_cookie=settings.session_cookie_name,
    same_site=settings.session_cookie_samesite,
    https_only=bool(settings.session_cookie_secure),
)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Any:
    err = request.query_params.get("err")
    msg = "Invalid username or password." if err else ""
    err_html = f"<div class='err' role='alert'>{escape(msg)}</div>" if msg else ""
    aria_invalid = 'aria-invalid="true"' if msg else ""
    version = escape(getattr(settings, "app_version", "dev") or "dev")

    help_url = (getattr(settings, "help_url", "") or "").strip()
    help_html = (
        f'<a class="helpLink" href="{escape(help_url, quote=True)}" target="_blank" rel="noreferrer">Help / Docs</a>'
        if help_url
        else ""
    )

    # Avoid str.format/f-strings here: the embedded CSS uses lots of curly braces.
    html = """<!doctype html>
<html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>System Dashboard Login</title>
        <link rel="stylesheet" href="/static/assets/login.css" />
    </head>
    <body class="login">
        <div class="loginWrap">
            <div class="loginLogo" aria-hidden="true">System Trace</div>

            <form class="loginCard" method="post" action="/login" novalidate>
                <div class="loginCardHeader">
                    <h1 class="loginTitle">System Dashboard Login</h1>
                    <div class="loginSub">Sign in to view metrics and insights.</div>
                </div>

                <div class="loginCardBody">
                    <div class="field">
                        <label for="username">Username</label>
                        <input id="username" name="username" type="text" autocomplete="username" required autofocus %%ARIA_INVALID%% />
                    </div>

                    <div class="field">
                        <label for="password">Password</label>
                        <div class="pwRow">
                            <input id="password" name="password" type="password" autocomplete="current-password" required %%ARIA_INVALID%% />
                            <button class="pwToggle" type="button" aria-controls="password" aria-pressed="false">Show</button>
                        </div>
                    </div>

                    <label class="check">
                        <input type="checkbox" name="remember_me" />
                        <span>Remember me (7 days)</span>
                    </label>

                    %%ERR_HTML%%

                    <div class="actions">
                        <button class="primary" type="submit">Sign in</button>
                    </div>
                </div>

                <div class="loginFoot">
                    <div class="meta">AI System Health Dashboard · v%%APP_VERSION%%</div>
                    %%HELP_HTML%%
                </div>
            </form>
        </div>

        <script>
            (function () {
                var btn = document.querySelector('.pwToggle');
                var input = document.getElementById('password');
                if (!btn || !input) return;

                function setShown(shown) {
                    input.type = shown ? 'text' : 'password';
                    btn.textContent = shown ? 'Hide' : 'Show';
                    btn.setAttribute('aria-pressed', shown ? 'true' : 'false');
                }

                btn.addEventListener('click', function () {
                    setShown(input.type === 'password');
                });
            })();
        </script>
    </body>
</html>
"""

    return (
        html.replace("%%ERR_HTML%%", err_html)
        .replace("%%ARIA_INVALID%%", aria_invalid)
        .replace("%%APP_VERSION%%", version)
        .replace("%%HELP_HTML%%", help_html)
    )

@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(None),
) -> Any:
    user = await asyncio.to_thread(auth_storage.get_user_by_username, username)
    if user is None or not user.is_active:
        return RedirectResponse(url="/login?err=1", status_code=303)
    ok = await asyncio.to_thread(auth_storage.verify_password, password, user.password_hash)
    if not ok:
        return RedirectResponse(url="/login?err=1", status_code=303)

    request.session["user_id"] = int(user.id)  # type: ignore[attr-defined]

    resp = RedirectResponse(url="/", status_code=303)
    if remember_me is not None:
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + float(settings.remember_max_age_seconds)
        user_agent = request.headers.get("user-agent")
        ip = None
        try:
            if request.client:
                ip = request.client.host
        except Exception:
            ip = None
        await asyncio.to_thread(
            auth_storage.create_remember_token,
            int(user.id),
            token,
            expires_at=float(expires_at),
            user_agent=user_agent,
            ip=ip,
        )
        resp.set_cookie(
            key=settings.remember_cookie_name,
            value=token,
            max_age=int(settings.remember_max_age_seconds),
            expires=int(expires_at),
            httponly=True,
            secure=bool(settings.session_cookie_secure),
            samesite=settings.session_cookie_samesite,
            path="/",
        )
    return resp


@app.post("/logout")
async def logout(request: Request) -> Any:
    remember_token = request.cookies.get(settings.remember_cookie_name)
    if remember_token:
        await asyncio.to_thread(auth_storage.revoke_remember_token, remember_token)
    try:
        request.session.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key=settings.remember_cookie_name, path="/")
    return resp


@app.get("/", response_class=HTMLResponse)
async def index() -> Any:
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/overview", response_class=HTMLResponse)
async def overview_page() -> Any:
    with open("app/static/overview.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/configuration", response_class=HTMLResponse)
async def configuration_page() -> Any:
    with open("app/static/configuration.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page() -> Any:
    with open("app/static/inventory.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/host/{host_id}", response_class=HTMLResponse)
async def host_page(host_id: int) -> Any:
    # host_id is used by the frontend JS; keep the HTML static.
    with open("app/static/host.html", "r", encoding="utf-8") as f:
        return HTMLResponse(
            f.read(),
            headers={
                # The page itself references versioned assets, but browsers may
                # still cache HTML aggressively; prevent stale asset URLs.
                "Cache-Control": "no-store",
            },
        )


@app.get("/api/metrics/latest")
async def api_latest() -> Any:
    sample = latest()
    if sample is None and storage.enabled:
        sample = await db_get_latest()
    return sample.model_dump() if sample else {"status": "no_data"}


@app.get("/api/metrics/history")
async def api_history(seconds: int = 300) -> Any:
    seconds = max(10, min(int(seconds), settings.history_seconds))
    if storage.enabled:
        samples = await db_get_history(seconds)
    else:
        samples = history(seconds)
    return [s.model_dump() for s in samples]


@app.get("/api/insights")
async def api_insights() -> Any:
    return compute_insights().model_dump()


@app.get("/api/me")
async def api_me(request: Request) -> Any:
    # Auth is enforced by middleware for non-public paths, but keep this explicit.
    user = await _get_current_user(request)
    if user is None:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return {
        "id": int(user.id),
        "username": str(user.username),
        "role": str(user.role),
        "is_active": bool(user.is_active),
    }



# === Dashboard Host Selection ===
_DASHBOARD_HOST_FILE = Path('data/dashboard_host.json')

def _get_dashboard_host_id() -> int | None:
    try:
        if _DASHBOARD_HOST_FILE.exists():
            return json.load(open(_DASHBOARD_HOST_FILE)).get('host_id')
    except Exception:
        pass
    return None

def _set_dashboard_host_id(host_id: int | None) -> None:
    _DASHBOARD_HOST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DASHBOARD_HOST_FILE, 'w') as f:
        json.dump({'host_id': host_id}, f)


@app.get("/api/admin/dashboard-host")
async def get_dashboard_host(request: Request) -> Any:
    """Get the currently selected dashboard host (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    host_id = await asyncio.to_thread(_get_dashboard_host_id)
    return {"host_id": host_id}


@app.put("/api/admin/dashboard-host")
async def set_dashboard_host(request: Request) -> Any:
    """Set the dashboard host (admin only). Pass host_id=null to use local metrics."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    body = await request.json()
    host_id = body.get("host_id")  # None = local
    await asyncio.to_thread(_set_dashboard_host_id, int(host_id) if host_id is not None else None)
    return {"host_id": host_id}

@app.get("/api/config")
async def api_config(request: Request) -> Any:
    """Return non-secret configuration values for display in the UI."""
    user = await _get_current_user(request)
    is_admin = bool(user and getattr(user, "role", "") == "admin")

    # IMPORTANT: do not expose secrets (SESSION_SECRET_KEY) or other sensitive fields.
    cfg: dict[str, Any] = {
        "app": {
            "title": "AI-Powered System Health Dashboard",
            "version": getattr(settings, "app_version", "dev") or "dev",
            "help_url": str(getattr(settings, "help_url", "") or ""),
        },
        "sampling": {
            "sample_interval_seconds": float(settings.sample_interval_seconds),
            "history_seconds": int(settings.history_seconds),
        },
        "anomaly": {
            "window_seconds": int(getattr(settings, "anomaly_window_seconds", 0) or 0),
            "z_threshold": float(getattr(settings, "anomaly_z_threshold", 0.0) or 0.0),
        },
        "protocols": {
            "check_interval_seconds": float(getattr(settings, "protocol_check_interval_seconds", 0.0) or 0.0),
            "ntp": {
                "server": str(getattr(settings, "ntp_server", "") or ""),
                "timeout_seconds": float(getattr(settings, "ntp_timeout_seconds", 0.0) or 0.0),
            },
            "icmp": {
                "host": str(getattr(settings, "icmp_host", "") or ""),
                "timeout_seconds": float(getattr(settings, "icmp_timeout_seconds", 0.0) or 0.0),
            },
            "snmp": {
                "host": str(getattr(settings, "snmp_host", "") or ""),
                "port": int(getattr(settings, "snmp_port", 0) or 0),
                "timeout_seconds": float(getattr(settings, "snmp_timeout_seconds", 0.0) or 0.0),
                "community_set": bool(str(getattr(settings, "snmp_community", "") or "").strip()),
            },
            "netflow": {
                "port": int(getattr(settings, "netflow_port", 0) or 0),
            },
        },
        "storage": {
            "enabled": bool(storage.enabled),
            "sqlite_retention_seconds": int(getattr(settings, "sqlite_retention_seconds", 0) or 0),
        },
        "auth": {
            "session_cookie_name": str(settings.session_cookie_name),
            "session_max_age_seconds": int(settings.session_max_age_seconds),
            "session_cookie_samesite": str(settings.session_cookie_samesite),
            "session_cookie_secure": bool(settings.session_cookie_secure),
            "remember_cookie_name": str(settings.remember_cookie_name),
            "remember_max_age_seconds": int(settings.remember_max_age_seconds),
        },
    }

    # Admins can see file paths (useful for operations); viewers should not.
    if is_admin:
        cfg["paths"] = {
            "metrics_db_path": str(getattr(settings, "metrics_db_path", "") or ""),
            "auth_db_path": str(getattr(settings, "auth_db_path", "") or ""),
        }

    # Admins can see DB stats (path/size/rows). Viewers should not.
    if is_admin and storage.enabled:
        try:
            cfg["storage"]["db_stats"] = await db_get_stats()
        except Exception:
            cfg["storage"]["db_stats"] = {"detail": "unavailable"}

    return cfg


@app.get("/api/hosts")
async def api_hosts(active_only: bool = True) -> Any:
    # Auth is handled by middleware (everything except /login is protected).
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    hosts = await db_get_hosts(active_only=bool(active_only))
    return [h.model_dump() for h in hosts]


@app.get("/api/inventory")
async def api_inventory() -> Any:
    # Auth is handled by middleware.
    if not storage.enabled:
        return JSONResponse({"detail": "Inventory storage is disabled"}, status_code=503)
    items = await db_get_inventory_items()
    return [it.model_dump() for it in items]


@app.get("/api/hosts/status")
async def api_hosts_status() -> Any:
    # Auth is handled by middleware.
    async with _host_status_lock:
        return {
            "ts": float(_host_status_ts),
            "statuses": dict(_host_status),
            "checks_ts": float(_host_checks_ts),
            "checks": dict(_host_checks),
        }


@app.get("/api/hosts/{host_id}/status")
async def api_host_status(host_id: int) -> Any:
    # Auth is handled by middleware.
    async with _host_status_lock:
        st = _host_status.get(int(host_id))
        return {"ts": float(_host_status_ts), "host_id": int(host_id), "status": st}


@app.get("/api/hosts/{host_id}/checks")
async def api_host_checks(host_id: int) -> Any:
    # Auth is handled by middleware.
    async with _host_status_lock:
        checks = _host_checks.get(int(host_id))
        return {"ts": float(_host_checks_ts), "host_id": int(host_id), "checks": checks or {}}


@app.get("/api/hosts/{host_id}")
async def api_host(host_id: int) -> Any:
    # Auth is handled by middleware.
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    # Storage layer currently provides list_hosts; keep this simple.
    hosts = await db_get_hosts(active_only=False)
    for h in hosts:
        try:
            if int(getattr(h, "id", -1)) == int(host_id):
                return h.model_dump()
        except Exception:
            continue
    return JSONResponse({"detail": "Not found"}, status_code=404)


@app.get("/api/events/recent")
async def api_events_recent(host_id: Optional[int] = None, limit: int = 500) -> Any:
    """Return recent structured host events.

    This is an in-memory ring buffer (max 500) intended for the dashboard UI.
    It resets on server restart.
    """
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 500
    limit_i = max(1, min(500, limit_i))

    async with _host_events_lock:
        evs = list(_host_events)

    if host_id is not None:
        try:
            hid = int(host_id)
            evs = [e for e in evs if int(e.get("host_id") or 0) == hid]
        except Exception:
            evs = []

    if len(evs) > limit_i:
        evs = evs[-limit_i:]

    return {"events": evs}


@app.post("/api/admin/hosts")
async def api_admin_hosts_create(payload: HostCreate) -> Any:
    # Admin role is enforced by middleware for /api/admin/*.
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    try:
        host = await db_create_host(payload)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return host.model_dump()


@app.post("/api/admin/inventory")
async def api_admin_inventory_create(payload: InventoryItemCreate) -> Any:
    # Admin role is enforced by middleware for /api/admin/*.
    if not storage.enabled:
        return JSONResponse({"detail": "Inventory storage is disabled"}, status_code=503)
    try:
        item = await db_create_inventory_item(payload)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return item.model_dump()


@app.put("/api/admin/hosts/{host_id}")
async def api_admin_hosts_update(host_id: int, payload: HostCreate) -> Any:
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    host = await db_update_host(int(host_id), payload)
    if not host:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return host.model_dump()


@app.post("/api/admin/hosts/{host_id}/install-agent")
async def api_admin_hosts_install_agent(host_id: int, payload: dict) -> Any:
    import asyncio, tempfile, os
    hosts = await db_get_hosts(active_only=False)
    host = next((h for h in hosts if h.id == int(host_id)), None)
    if not host:
        return JSONResponse({"detail": "Host not found"}, status_code=404)

    ssh_user = str(payload.get("ssh_user", "root")).strip()
    ssh_pass = str(payload.get("ssh_password", "")).strip()
    ssh_port = int(payload.get("ssh_port", 22))
    server_url = str(payload.get("server_url", "http://192.168.50.225:8001")).strip()
    target_ip = host.address

    agent_src = "/opt/system-trace-agent/ashd_agent.py"
    if not os.path.exists(agent_src):
        return JSONResponse({"detail": "Agent file not found on server"}, status_code=500)

    # Read agent file content to embed directly (avoids heredoc issues with $)
    try:
        with open(agent_src, 'r') as f:
            agent_content = f.read()
        # Escape single quotes for safe embedding
        agent_content_escaped = agent_content.replace("'", "'\\''")
    except Exception as e:
        return JSONResponse({"detail": f"Failed to read agent file: {e}"}, status_code=500)

    # Use sudo only if not root
    if ssh_user == "root":
        priv = ""
    else:
        priv = f"echo '{ssh_pass}' | sudo -S"

    install_script = f"""#!/bin/bash
set -e

# --- Install monitoring agent ---
{priv} mkdir -p /opt/system-trace-agent
cat > /tmp/_ashd_agent.py << 'AGENTEOF'
{agent_content_escaped}
AGENTEOF
{priv} cp /tmp/_ashd_agent.py /opt/system-trace-agent/ashd_agent.py
{priv} sed -i 's|http://192.168.50.225:8001|{server_url}|g' /opt/system-trace-agent/ashd_agent.py
python3 -m pip install psutil requests --quiet 2>/dev/null || pip3 install psutil requests --quiet 2>/dev/null || true

cat > /tmp/_ashd.service << 'SVCEOF'
[Unit]
Description=System Trace Monitoring Agent
After=network.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/system-trace-agent/ashd_agent.py
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
SVCEOF
{priv} cp /tmp/_ashd.service /etc/systemd/system/system-trace-agent.service
{priv} systemctl daemon-reload
{priv} systemctl enable system-trace-agent
{priv} systemctl restart system-trace-agent

# --- Install and configure SNMP (net-snmp) ---
if command -v dnf &>/dev/null; then
    {priv} dnf install -y net-snmp net-snmp-utils 2>/dev/null || true
elif command -v yum &>/dev/null; then
    {priv} yum install -y net-snmp net-snmp-utils 2>/dev/null || true
elif command -v apt-get &>/dev/null; then
    {priv} apt-get install -y snmpd snmp 2>/dev/null || true
fi

# Write minimal snmpd.conf allowing public community
cat > /tmp/_snmpd.conf << 'SNMPEOF'
agentAddress udp:161
rocommunity public default
syslocation "Monitored Host"
syscontact admin@localhost
SNMPEOF
{priv} cp /tmp/_snmpd.conf /etc/snmp/snmpd.conf 2>/dev/null || true
{priv} systemctl enable snmpd 2>/dev/null || true
{priv} systemctl restart snmpd 2>/dev/null || true

# Open SNMP port in firewall if firewalld is active
if {priv} systemctl is-active --quiet firewalld 2>/dev/null; then
    {priv} firewall-cmd --permanent --add-port=161/udp 2>/dev/null || true
    {priv} firewall-cmd --reload 2>/dev/null || true
fi

# --- Install and configure chrony (NTP) ---
if command -v dnf &>/dev/null; then
    {priv} dnf install -y chrony 2>/dev/null || true
elif command -v yum &>/dev/null; then
    {priv} yum install -y chrony 2>/dev/null || true
elif command -v apt-get &>/dev/null; then
    {priv} apt-get install -y chrony 2>/dev/null || true
fi
{priv} systemctl enable chronyd 2>/dev/null || systemctl enable chrony 2>/dev/null || true
{priv} systemctl restart chronyd 2>/dev/null || systemctl restart chrony 2>/dev/null || true

echo "Agent, SNMP and NTP installed successfully"
echo "REAL_HOSTNAME=$(hostname -f 2>/dev/null || hostname)"
"""

    try:
        proc = await asyncio.create_subprocess_exec(
            "sshpass", "-p", ssh_pass,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(ssh_port),
            f"{ssh_user}@{target_ip}",
            "bash -s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=install_script.encode()), timeout=120)
        if proc.returncode != 0:
            return JSONResponse({"detail": stderr.decode() or "Install failed"}, status_code=500)

        output = stdout.decode()

        # Parse real hostname from install script output
        real_hostname = None
        for line in output.splitlines():
            if line.startswith("REAL_HOSTNAME="):
                real_hostname = line.split("=", 1)[1].strip()
                break

        # Update host name in DB with real hostname
        if real_hostname and real_hostname not in ("", "localhost", "localhost.localdomain"):
            try:
                from app.models import HostCreate as HC
                existing_host = next((h for h in hosts if h.id == int(host_id)), None)
                if existing_host:
                    await db_update_host(int(host_id), HC(
                        name=real_hostname,
                        address=existing_host.address,
                        type=existing_host.type or "linux",
                        tags=existing_host.tags or [],
                        notes=existing_host.notes,
                    ))
            except Exception:
                pass

        msg = f"Agent installed on {real_hostname or target_ip} successfully"
        return {"ok": True, "message": msg, "hostname": real_hostname or target_ip}
    except asyncio.TimeoutError:
        return JSONResponse({"detail": "SSH connection timed out"}, status_code=504)
    except FileNotFoundError:
        return JSONResponse({"detail": "sshpass not installed on server. Run: sudo dnf install sshpass"}, status_code=500)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.delete("/api/admin/hosts/{host_id}")
async def api_admin_hosts_delete(host_id: int) -> Any:
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    ok = await db_deactivate_host(int(host_id))
    if not ok:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return {"ok": True}


@app.delete("/api/admin/inventory/{item_id}")
async def api_admin_inventory_delete(item_id: int) -> Any:
    if not storage.enabled:
        return JSONResponse({"detail": "Inventory storage is disabled"}, status_code=503)
    ok = await db_delete_inventory_item(int(item_id))
    if not ok:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return {"ok": True}


@app.get("/api/admin/db")
async def api_admin_db() -> Any:
    return await db_get_stats()


@app.post("/api/admin/db/prune")
async def api_admin_db_prune() -> Any:
    deleted = await prune_old()
    return {"deleted": int(deleted)}


@app.post("/api/admin/db/vacuum")
async def api_admin_db_vacuum() -> Any:
    # Best-effort file size before/after
    before = await db_get_stats()
    await db_vacuum()
    after = await db_get_stats()
    return {"before": before, "after": after}


class Broadcaster:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        data = json.dumps(msg)
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


broadcaster = Broadcaster()


# --- Host status (best-effort ICMP reachability) ---
_host_status_lock = asyncio.Lock()
_host_status_ts: float = 0.0
_host_status: dict[int, dict[str, Any]] = {}

_host_checks_ts: float = 0.0
_host_checks: dict[int, dict[str, Any]] = {}

# --- Recent host events (in-memory, non-persistent) ---
# Used by the dashboard's "Problems" view.
_host_events_lock = asyncio.Lock()
_host_events: deque[dict[str, Any]] = deque(maxlen=500)

_HOST_CHECK_INTERVAL_S = 15.0
_HOST_CHECK_MAX_CONCURRENCY = 12

_PING_RE = re.compile(r"time[=<]?\s*([0-9.]+)\s*ms", re.IGNORECASE)


def _check_tcp_port(address: str, port: int, timeout_s: float) -> ProtocolStatus:
    ts = time.time()
    host = (address or "").strip()
    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no address")
    try:
        t = max(0.2, float(timeout_s or 1.0))
        with socket.create_connection((host, int(port)), timeout=t):
            pass
        return ProtocolStatus(status="ok", checked_ts=ts, message=f"tcp/{int(port)} open")
    except Exception as e:
        msg = str(e)
        msg = msg[:140] if msg else "connect failed"
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"tcp/{int(port)}: {msg}")


def _looks_like_ip(s: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET, s)
        return True
    except Exception:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, s)
        return True
    except Exception:
        return False


def _check_dns(name_or_addr: str, fallback_name: Optional[str] = None) -> ProtocolStatus:
    ts = time.time()
    s = (name_or_addr or "").strip()
    fb = (fallback_name or "").strip()
    if not s and not fb:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no name")

    if s and _looks_like_ip(s):
        return ProtocolStatus(status="ok", checked_ts=ts, message="ip literal")

    target = s or fb
    try:
        infos = socket.getaddrinfo(target, None)
        ip = None
        for inf in infos:
            try:
                ip = inf[4][0]
                break
            except Exception:
                continue
        return ProtocolStatus(status="ok", checked_ts=ts, message=f"{target} -> {ip or 'resolved'}")
    except Exception as e:
        msg = str(e)
        msg = msg[:140] if msg else "resolution failed"
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"dns: {msg}")


def _check_snmp_host(address: str) -> ProtocolStatus:
    # Best-effort SNMP check per host using global community (secret not exposed).
    ts = time.time()
    host = (address or "").strip()
    community = (getattr(settings, "snmp_community", "") or "").strip()
    port = int(getattr(settings, "snmp_port", 161) or 161)
    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no address")
    if not community:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="SNMP_COMMUNITY not set")
    # Use snmpwalk for SNMP checks
    import subprocess  # type: ignore

    timeout = float(getattr(settings, "snmp_timeout_seconds", 2.0) or 2.0)
    try:
        t0 = time.perf_counter()

        # Use snmpget for a single OID — faster than snmpwalk
        cmd = ['snmpget', '-v2c', '-c', community, '-t', str(int(timeout)), '-r', '1',
               f'{host}:{port}', '1.3.6.1.2.1.1.3.0']  # sysUpTime.0

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+2)
        
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        if result.returncode == 0:
            return ProtocolStatus(status="ok", checked_ts=ts, latency_ms=latency_ms, message=f"{host}:{port}")
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            # Timeout or no response = host simply doesn't run snmpd, not a critical failure
            if "Timeout" in error_msg or "No Response" in error_msg or not error_msg:
                return ProtocolStatus(status="unknown", checked_ts=ts, latency_ms=latency_ms, message="SNMP not available")
            else:
                return ProtocolStatus(status="crit", checked_ts=ts, latency_ms=latency_ms, message=f"SNMP: {error_msg[:80]}")

    except subprocess.TimeoutExpired:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="SNMP not available")
    except Exception as e:
        return ProtocolStatus(status="unknown", checked_ts=ts, message=f"SNMP: {e}")


def _check_ntp_server(address: str) -> ProtocolStatus:
    """Best-effort NTP server probe (UDP/123).

    Note: many hosts are NTP clients, not servers; in that case this will time out.
    We report 'unknown' on timeout to avoid false alarms.
    """
    ts = time.time()
    host = (address or "").strip()
    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no address")

    timeout_s = 1.0
    try:
        timeout_s = float(getattr(settings, "ntp_timeout_seconds", 1.2) or 1.2)
    except Exception:
        timeout_s = 1.0

    # Minimal NTP request: 48 bytes, first byte sets LI/VN/Mode.
    pkt = bytearray(48)
    pkt[0] = 0x1B  # LI=0, VN=3, Mode=3 (client)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(max(0.2, timeout_s))
    try:
        t0 = time.perf_counter()
        s.sendto(bytes(pkt), (host, 123))
        _data, _addr = s.recvfrom(512)
        t1 = time.perf_counter()
        return ProtocolStatus(status="ok", checked_ts=ts, latency_ms=(t1 - t0) * 1000.0, message=f"udp/123 {host}")
    except socket.timeout:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no NTP response")
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"NTP probe failed: {e}")
    finally:
        try:
            s.close()
        except Exception:
            pass


def _check_host_icmp(address: str) -> ProtocolStatus:
    ts = time.time()
    host = (address or "").strip()
    if not host:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="no address")

    timeout_s = max(1, int(float(getattr(settings, "icmp_timeout_seconds", 1.0) or 1.0)))
    try:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_s), "-n", host],
            capture_output=True,
            text=True,
            timeout=float(timeout_s) + 0.5,
            check=False,
        )
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"ping failed: {e}")

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        msg = msg[:140] if msg else "no reply"
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"{host}: {msg}")

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = _PING_RE.search(out)
    latency_ms = float(m.group(1)) if m else None
    if latency_ms is None:
        return ProtocolStatus(status="ok", checked_ts=ts, message=host)
    return ProtocolStatus(status="ok", checked_ts=ts, latency_ms=float(latency_ms), message=host)


async def _host_checker_loop() -> None:
    await asyncio.sleep(1.0)

    while True:
        try:
            if not storage.enabled:
                async with _host_status_lock:
                    global _host_status_ts, _host_status
                    _host_status_ts = time.time()
                    _host_status = {}
                    global _host_checks_ts, _host_checks
                    _host_checks_ts = _host_status_ts
                    _host_checks = {}
                await asyncio.sleep(_HOST_CHECK_INTERVAL_S)
                continue

            hosts = await db_get_hosts(active_only=True)
            sem = asyncio.Semaphore(_HOST_CHECK_MAX_CONCURRENCY)

            async def one(h) -> tuple[int, dict[str, Any]]:
                async with sem:
                    try:
                        addr = str(getattr(h, "address", "") or "")
                        name = str(getattr(h, "name", "") or "")
                        icmp = await asyncio.to_thread(_check_host_icmp, addr)
                        ssh = await asyncio.to_thread(_check_tcp_port, addr, 22, 1.0)
                        dns = await asyncio.to_thread(_check_dns, addr, name)
                        snmp = await asyncio.to_thread(_check_snmp_host, addr)
                        ntp = await asyncio.to_thread(_check_ntp_server, addr)
                        checks = {
                            "icmp": icmp.model_dump(),
                            "ssh": ssh.model_dump(),
                            "dns": dns.model_dump(),
                            "snmp": snmp.model_dump(),
                            "ntp": ntp.model_dump(),
                        }
                    except Exception as e:
                        icmp = ProtocolStatus(status="crit", checked_ts=time.time(), message=f"check error: {e}")
                        checks = {"icmp": icmp.model_dump()}
                    # keep legacy per-host status = ICMP
                    return (int(getattr(h, "id", 0)), {"icmp": icmp.model_dump(), "checks": checks})

            pairs = await asyncio.gather(*(one(h) for h in hosts), return_exceptions=True)
            results: dict[int, dict[str, Any]] = {}
            checks_all: dict[int, dict[str, Any]] = {}
            for p in pairs:
                if isinstance(p, Exception):
                    continue
                hid, payload = p
                if hid:
                    try:
                        results[int(hid)] = dict(payload.get("icmp") or {})
                    except Exception:
                        results[int(hid)] = {}
                    try:
                        checks_all[int(hid)] = dict(payload.get("checks") or {})
                    except Exception:
                        checks_all[int(hid)] = {}

            ts = time.time()

            # --- SYSTEM LOGS: emit host failure/recovery events on state changes ---
            # The dashboard's SYSTEM LOGS panel is line-based text; we broadcast
            # lightweight events over the existing websocket.
            host_name_by_id: dict[int, str] = {}
            host_addr_by_id: dict[int, str] = {}
            for h in hosts:
                try:
                    hid = int(getattr(h, "id", 0) or 0)
                except Exception:
                    continue
                if not hid:
                    continue
                name = str(getattr(h, "name", "") or "").strip()
                addr = str(getattr(h, "address", "") or "").strip()
                host_name_by_id[hid] = name or addr or f"host-{hid}"
                host_addr_by_id[hid] = addr

            async with _host_status_lock:
                prev_statuses = dict(_host_status)
                prev_checks = dict(_host_checks)

            def _norm_status(v: Any) -> str:
                try:
                    return str(v or "unknown").lower().strip()
                except Exception:
                    return "unknown"

            events: list[dict[str, Any]] = []
            host_events: list[dict[str, Any]] = []

            def _add_event(level: str, message: str) -> None:
                events.append({"type": "log", "ts": float(ts), "level": str(level), "message": str(message)})

            def _add_host_event(host_id: int, level: str, check: str, status: str, message: str) -> None:
                try:
                    hid = int(host_id)
                except Exception:
                    return
                host_events.append(
                    {
                        "type": "host_event",
                        "ts": float(ts),
                        "level": str(level),
                        "host_id": hid,
                        "host_name": host_name_by_id.get(hid, f"host-{hid}"),
                        "address": host_addr_by_id.get(hid, ""),
                        "check": str(check),
                        "status": str(status),
                        "message": str(message),
                    }
                )

            def _detail_line(proto_dump: Any) -> str:
                """Best-effort human detail for a ProtocolStatus model_dump()."""
                try:
                    if not isinstance(proto_dump, dict):
                        return ""
                    msg = str(proto_dump.get("message") or "").strip()
                    lat = proto_dump.get("latency_ms")
                    parts: list[str] = []
                    if msg:
                        # Avoid gigantic lines.
                        parts.append(msg[:180])
                    if lat is not None:
                        try:
                            parts.append(f"{int(round(float(lat)))} ms")
                        except Exception:
                            pass
                    return " · ".join(parts)
                except Exception:
                    return ""

            for hid, st in results.items():
                name = host_name_by_id.get(int(hid), f"host-{hid}")
                new_icmp = _norm_status((st or {}).get("status"))
                prev_icmp = _norm_status(((prev_statuses.get(int(hid)) or {}) if isinstance(prev_statuses, dict) else {}).get("status"))

                # ICMP: log both failure + recovery.
                if prev_icmp != "crit" and new_icmp == "crit":
                    detail = _detail_line(st)
                    suffix = f": {detail}" if detail else ""
                    _add_event("CRIT", f"Host {name} unreachable (ICMP){suffix}")
                    _add_host_event(int(hid), "CRIT", "icmp", "crit", detail or "unreachable")
                elif prev_icmp == "crit" and new_icmp == "ok":
                    _add_event("INFO", f"Host {name} reachable (ICMP)")
                    _add_host_event(int(hid), "INFO", "icmp", "ok", "reachable")

                # Other protocols: log transitions into critical.
                new_host_checks = checks_all.get(int(hid)) or {}
                prev_host_checks = prev_checks.get(int(hid)) or {}
                for proto_key, proto_label in (
                    ("ssh", "SSH"),
                    ("dns", "DNS"),
                    ("snmp", "SNMP"),
                    ("ntp", "NTP"),
                ):
                    new_p = _norm_status((new_host_checks.get(proto_key) or {}).get("status"))
                    prev_p = _norm_status((prev_host_checks.get(proto_key) or {}).get("status"))
                    if prev_p != "crit" and new_p == "crit":
                        detail = _detail_line(new_host_checks.get(proto_key) or {})
                        suffix = f": {detail}" if detail else ""
                        _add_event("CRIT", f"Host {name} {proto_label} check failed{suffix}")
                        _add_host_event(int(hid), "CRIT", proto_key, "crit", detail or "check failed")

            async with _host_status_lock:
                _host_status_ts = ts
                _host_status = results
                _host_checks_ts = ts
                _host_checks = checks_all

            # Broadcast host check events first so the UI can show the failure as it happens.
            for ev in events:
                await broadcaster.broadcast(ev)

            # Store + broadcast structured host events (Problems view).
            if host_events:
                async with _host_events_lock:
                    for ev in host_events:
                        _host_events.append(ev)
                for ev in host_events:
                    await broadcaster.broadcast(ev)

            # Push to connected clients (dashboard listens and updates buttons).
            await broadcaster.broadcast(
                {
                    "type": "host_status",
                    "ts": ts,
                    "statuses": results,
                    "checks": checks_all,
                }
            )
        except Exception:
            # Never let this loop die.
            pass

        await asyncio.sleep(_HOST_CHECK_INTERVAL_S)


async def _sampler_loop() -> None:
    # Warm up CPU percent counters
    collect_sample()
    await asyncio.sleep(0.1)

    last_prune = 0.0

    while True:
        sample = collect_sample()
        add_sample(sample)
        if storage.enabled:
            await persist_sample(sample)
            # prune at most once per minute
            now = asyncio.get_event_loop().time()
            if now - last_prune > 60.0:
                last_prune = now
                await prune_old()
        insights = compute_insights()
        await broadcaster.broadcast(
            {
                "type": "sample",
                "sample": sample.model_dump(),
                "insights": insights.model_dump(),
            }
        )
        await asyncio.sleep(max(0.1, settings.sample_interval_seconds))


@app.on_event("startup")
async def startup() -> None:
    await init_auth_storage()
    await init_storage()
    await _seed_default_admin()
    start_protocol_checker()
    asyncio.create_task(_host_checker_loop())
    asyncio.create_task(_sampler_loop())


async def _seed_default_admin() -> None:
    """Create default admin/admin user if the users table is empty."""
    import logging
    try:
        users = await asyncio.to_thread(auth_storage.get_all_users)
        if not users:
            await asyncio.to_thread(
                auth_storage.create_user,
                "admin", "admin", role="admin"
            )
            logging.getLogger("uvicorn").warning(
                "No users found — created default admin user "
                "(username: admin, password: admin). "
                "Please change this password after first login."
            )
    except Exception:
        pass


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    # Auth for WebSocket: SessionMiddleware stores session on the ASGI scope.
    # Reject if missing/invalid.
    session = ws.scope.get("session")  # type: ignore[assignment]
    user_id = None
    try:
        if isinstance(session, dict):
            user_id = session.get("user_id")
    except Exception:
        user_id = None
    if user_id is None:
        remember_token = None
        try:
            remember_token = ws.cookies.get(settings.remember_cookie_name)
        except Exception:
            remember_token = None
        if remember_token:
            uid = await asyncio.to_thread(auth_storage.validate_remember_token, remember_token)
            if uid is not None:
                user_id = uid
                try:
                    if isinstance(session, dict):
                        session["user_id"] = int(uid)
                except Exception:
                    pass
        if user_id is None:
            await ws.close(code=4401)
            return
    try:
        uid = int(user_id)
    except Exception:
        await ws.close(code=4401)
        return
    user = await asyncio.to_thread(auth_storage.get_user_by_id, uid)
    if user is None or not user.is_active:
        await ws.close(code=4401)
        return

    await ws.accept()
    await broadcaster.add(ws)
    try:
        # Send immediate snapshot
        sample = latest()
        await ws.send_text(
            json.dumps(
                {
                    "type": "snapshot",
                    "sample": sample.model_dump() if sample else None,
                    "insights": compute_insights().model_dump(),
                }
            )
        )
        while True:
            # Keepalive / allow client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.remove(ws)


# === User Management API Endpoints ===

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    user_groups: Optional[list[int]] = []

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    user_groups: Optional[list[int]] = None

class UserGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    allowed_hosts: Optional[list[str]] = []

class UserGroupUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    allowed_hosts: Optional[list[str]] = []

@app.get("/api/admin/users")
async def api_get_users(request: Request) -> Any:
    """Get all users (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    users = await asyncio.to_thread(auth_storage.get_all_users)
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
            "last_login": u.last_login,
            "user_groups": [g["id"] for g in await asyncio.to_thread(auth_storage.get_user_groups, u.id)]
        }
        for u in users
    ]

@app.post("/api/admin/users")
async def api_create_user(user_in: UserCreate, request: Request) -> Any:
    """Create a new user (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    try:
        new_user = await asyncio.to_thread(
            auth_storage.create_user,
            username=user_in.username,
            password=user_in.password,
            email=user_in.email,
            role=user_in.role,
            is_active=user_in.is_active
        )
        
        # Add user to groups if specified
        for group_id in user_in.user_groups or []:
            await asyncio.to_thread(auth_storage.add_user_to_group, new_user.id, group_id)
        
        return {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at,
            "last_login": new_user.last_login
        }
    except Exception as e:
        return JSONResponse({"detail": f"Failed to create user: {str(e)}"}, status_code=400)

@app.put("/api/admin/users/{user_id}")
async def api_update_user(user_id: int, user_in: UserUpdate, request: Request) -> Any:
    """Update a user (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    try:
        # Update user fields
        update_data = {}
        if user_in.username is not None:
            update_data["username"] = user_in.username
        if user_in.password is not None and user_in.password:
            update_data["password"] = user_in.password
        if user_in.email is not None:
            update_data["email"] = user_in.email
        if user_in.role is not None:
            update_data["role"] = user_in.role
        if user_in.is_active is not None:
            update_data["is_active"] = user_in.is_active
        
        if update_data:
            success = await asyncio.to_thread(auth_storage.update_user, user_id, **update_data)
            if not success:
                return JSONResponse({"detail": "User not found or no changes made"}, status_code=404)
        
        return {"detail": "User updated successfully"}
    except Exception as e:
        return JSONResponse({"detail": f"Failed to update user: {str(e)}"}, status_code=400)

@app.delete("/api/admin/users/{user_id}")
async def api_delete_user(user_id: int, request: Request) -> Any:
    """Delete a user (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    # Prevent self-deletion
    if user.id == user_id:
        return JSONResponse({"detail": "Cannot delete yourself"}, status_code=400)
    
    try:
        success = await asyncio.to_thread(auth_storage.delete_user, user_id)
        if not success:
            return JSONResponse({"detail": "User not found"}, status_code=404)
        return {"detail": "User deleted successfully"}
    except Exception as e:
        return JSONResponse({"detail": f"Failed to delete user: {str(e)}"}, status_code=400)

# === User Groups API Endpoints ===

@app.get("/api/admin/user-groups")
async def api_get_user_groups(request: Request) -> Any:
    """Get all user groups (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    groups = await asyncio.to_thread(auth_storage.get_all_user_groups)
    return groups

@app.post("/api/admin/user-groups")
async def api_create_user_group(group_in: UserGroupCreate, request: Request) -> Any:
    """Create a new user group (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    try:
        group_id = await asyncio.to_thread(
            auth_storage.create_user_group,
            name=group_in.name,
            description=group_in.description,
            allowed_hosts=group_in.allowed_hosts
        )
        return {"id": group_id, "name": group_in.name, "description": group_in.description, "allowed_hosts": group_in.allowed_hosts}
    except Exception as e:
        return JSONResponse({"detail": f"Failed to create user group: {str(e)}"}, status_code=400)

@app.put("/api/admin/user-groups/{group_id}")
async def api_update_user_group(group_id: int, group_in: UserGroupUpdate, request: Request) -> Any:
    """Update an existing user group (admin only)."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    
    try:
        await asyncio.to_thread(
            auth_storage.update_user_group,
            group_id=group_id,
            name=group_in.name,
            description=group_in.description,
            allowed_hosts=group_in.allowed_hosts
        )
        return {"id": group_id, "name": group_in.name, "description": group_in.description, "allowed_hosts": group_in.allowed_hosts}
    except Exception as e:
        return JSONResponse({"detail": f"Failed to update user group: {str(e)}"}, status_code=400)

# === System Logs ===

LOGS_FILE = Path('data/system_logs.json')
MAX_LOGS = 2000  # rolling cap

def _read_logs() -> list:
    try:
        if LOGS_FILE.exists():
            with open(LOGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _write_logs(logs: list) -> None:
    LOGS_FILE.parent.mkdir(exist_ok=True)
    with open(LOGS_FILE, 'w') as f:
        json.dump(logs[-MAX_LOGS:], f)

def write_log(level: str, source: str, message: str, hostname: str = '', ip: str = '') -> None:
    """Append one entry to system_logs.json (non-blocking best-effort)."""
    try:
        logs = _read_logs()
        logs.append({
            'ts': time.time(),
            'level': level,       # 'info' | 'warn' | 'error' | 'crit'
            'source': source,
            'hostname': hostname,
            'ip': ip,
            'message': message,
        })
        _write_logs(logs)
    except Exception as e:
        print(f"[log write error] {e}")

@app.get("/api/logs")
async def get_logs(limit: int = 200, level: str = '', hostname: str = '') -> Any:
    """Return recent system log entries, newest first."""
    try:
        logs = _read_logs()
        if level:
            logs = [l for l in logs if l.get('level') == level]
        if hostname:
            logs = [l for l in logs if l.get('hostname') == hostname]
        return {"logs": list(reversed(logs[-limit:]))}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.post("/api/logs")
async def post_log(entry: dict) -> Any:
    """Accept a log entry from the frontend."""
    try:
        write_log(
            level=str(entry.get('level', 'info')),
            source=str(entry.get('source', 'frontend')),
            message=str(entry.get('message', '')),
            hostname=str(entry.get('hostname', '')),
            ip=str(entry.get('ip', '')),
        )
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.delete("/api/logs")
async def clear_logs() -> Any:
    """Clear all system logs (admin)."""
    try:
        _write_logs([])
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/logs/host/{hostname}")
async def get_host_logs(hostname: str, limit: int = 100) -> Any:
    """Return log entries for a specific host, newest first."""
    try:
        logs = _read_logs()
        filtered = [l for l in logs if l.get('hostname') == hostname]
        return {"logs": list(reversed(filtered[-limit:]))}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

# === Agent Management API ===

@app.post("/api/agent/metrics")
async def receive_agent_metrics(metrics: dict, request: Request) -> Any:
    """Receive metrics from monitoring agents."""
    try:
        # Extract hostname from metrics
        hostname = metrics.get('hostname', 'unknown')
        agent_id = metrics.get('agent_id', 'unknown')
        os_type = metrics.get('os_type', 'unknown')
        # IP: prefer what agent reports, fall back to request source IP
        ip = metrics.get('ip') or request.client.host

        # Log the received metrics with hostname
        print(f"Received metrics from agent: {hostname} ({agent_id}) IP: {ip} - OS: {os_type}")
        
        # Store metrics in a file for now (in production, use database)
        metrics_file = Path('data/agent_metrics.json')
        metrics_file.parent.mkdir(exist_ok=True)
        
        # Read existing metrics or create new structure
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                all_metrics = json.load(f)
        else:
            all_metrics = {}
        
        # Keep rolling history (last 400 samples = ~20 min at 3s interval)
        MAX_HISTORY = 400
        existing = all_metrics.get(hostname, {})
        history = existing.get('history', [])
        history.append({
            'ts': time.time(),
            'cpu': metrics.get('cpu', {}).get('percent', 0),
            'mem': metrics.get('memory', {}).get('percent', 0),
            'disk': metrics.get('disk', {}).get('percent', 0),
            'net_sent': metrics.get('network', {}).get('bytes_sent', 0),
            'net_recv': metrics.get('network', {}).get('bytes_recv', 0),
            'processes': metrics.get('processes', 0),
            'uptime': metrics.get('uptime', 0),
            'gpu': metrics.get('gpu') or [],
        })
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        # Store metrics with hostname as key
        all_metrics[hostname] = {
            'last_seen': time.time(),
            'hostname': hostname,
            'ip': ip,
            'agent_id': agent_id,
            'os_type': os_type,
            'metrics': metrics,
            'history': history,
            'discovered_at': existing.get('discovered_at', time.time())
        }
        
        # Save updated metrics
        with open(metrics_file, 'w') as f:
            json.dump(all_metrics, f, indent=2)

        # Auto-log threshold breaches (only log every ~30s per host to avoid spam)
        cpu_pct  = metrics.get('cpu', {}).get('percent', 0)
        mem_pct  = metrics.get('memory', {}).get('percent', 0)
        disk_pct = metrics.get('disk', {}).get('percent', 0)
        prev_log_ts = existing.get('last_problem_log_ts', 0)
        now_ts = time.time()
        if now_ts - prev_log_ts >= 30:
            problems = []
            if cpu_pct >= 90:
                problems.append(f"CPU critical: {cpu_pct:.1f}%")
            elif cpu_pct >= 75:
                problems.append(f"CPU high: {cpu_pct:.1f}%")
            if mem_pct >= 90:
                problems.append(f"RAM critical: {mem_pct:.1f}%")
            elif mem_pct >= 80:
                problems.append(f"RAM high: {mem_pct:.1f}%")
            if disk_pct >= 95:
                problems.append(f"Disk critical: {disk_pct:.1f}%")
            elif disk_pct >= 85:
                problems.append(f"Disk high: {disk_pct:.1f}%")
            gpu_list = metrics.get('gpu') or []
            if isinstance(gpu_list, list):
                for g in gpu_list:
                    gidx = g.get('index', 0)
                    gpct = g.get('percent', 0)
                    gtemp = g.get('temperature')
                    if gpct >= 95:
                        problems.append(f"GPU {gidx} critical: {gpct:.1f}%")
                    elif gpct >= 85:
                        problems.append(f"GPU {gidx} high: {gpct:.1f}%")
                    if gtemp is not None:
                        if gtemp >= 90:
                            problems.append(f"GPU {gidx} temp critical: {gtemp:.0f}°C")
                        elif gtemp >= 80:
                            problems.append(f"GPU {gidx} temp high: {gtemp:.0f}°C")
            if problems:
                level = 'crit' if any('critical' in p for p in problems) else 'warn'
                write_log(level=level, source='agent', hostname=hostname, ip=ip,
                          message='; '.join(problems))
                all_metrics[hostname]['last_problem_log_ts'] = now_ts
                with open(metrics_file, 'w') as f:
                    json.dump(all_metrics, f, indent=2)

        return {"status": "success", "message": f"Metrics received from {hostname}"}
    
    except Exception as e:
        print(f"Error processing agent metrics: {e}")
        return JSONResponse({"detail": f"Failed to process metrics: {str(e)}"}, status_code=500)

@app.get("/api/hosts/{host_id}/agent-metrics")
async def get_host_agent_metrics(host_id: int) -> Any:
    """Return latest snapshot + history for a specific host by ID."""
    try:
        hosts = await db_get_hosts(active_only=False)
        host = next((h for h in hosts if h.id == int(host_id)), None)
        if not host:
            return JSONResponse({"detail": "Host not found"}, status_code=404)

        metrics_file = Path('data/agent_metrics.json')
        if not metrics_file.exists():
            return {"found": False}
        with open(metrics_file, 'r') as f:
            all_metrics = json.load(f)

        # Match by IP or hostname
        address = str(host.address or "").strip()
        name = str(host.name or "").strip()
        data = None
        for entry in all_metrics.values():
            if entry.get('ip') == address or entry.get('hostname') == name or entry.get('hostname') == address:
                data = entry
                break

        if not data:
            return {"found": False}

        now = time.time()
        online = (now - data.get('last_seen', 0)) < 120
        latest = data.get('metrics', {})
        history = data.get('history', [])

        # Compute network delta (bytes/s) from last 2 history points
        net_sent_rate = 0
        net_recv_rate = 0
        if len(history) >= 2:
            h1, h2 = history[-2], history[-1]
            dt = max(h2['ts'] - h1['ts'], 1)
            net_sent_rate = max(0, (h2['net_sent'] - h1['net_sent']) / dt)
            net_recv_rate = max(0, (h2['net_recv'] - h1['net_recv']) / dt)

        return {
            "found": True,
            "online": online,
            "last_seen": data.get('last_seen'),
            "hostname": data.get('hostname'),
            "ip": data.get('ip'),
            "os_type": data.get('os_type'),
            "latest": {
                "cpu": latest.get('cpu', {}),
                "memory": latest.get('memory', {}),
                "disk": latest.get('disk', {}),
                "network": latest.get('network', {}),
                "uptime": latest.get('uptime', 0),
                "processes": latest.get('processes', 0),
                "gpu": latest.get('gpu'),
            },
            "net_sent_rate": round(net_sent_rate),
            "net_recv_rate": round(net_recv_rate),
            "history": history,
        }
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.get("/api/agent/status")
async def get_agent_status() -> Any:
    """Return agent online/offline status keyed by IP address and hostname."""
    try:
        metrics_file = Path('data/agent_metrics.json')
        if not metrics_file.exists():
            return {}
        with open(metrics_file, 'r') as f:
            all_metrics = json.load(f)
        now = time.time()
        result = {}
        for hostname, data in all_metrics.items():
            last_seen = data.get('last_seen', 0)
            online = (now - last_seen) < 120
            ip = data.get('ip') or data.get('metrics', {}).get('ip')
            entry = {
                'hostname': hostname,
                'last_seen': last_seen,
                'status': 'online' if online else 'offline',
            }
            # Index by hostname
            result[hostname] = entry
            # Also index by IP if available
            if ip:
                result[ip] = entry
        return result
    except Exception as e:
        return {}


@app.get("/api/agent/metrics")
async def get_agent_metrics() -> Any:
    """Get all agent metrics."""
    try:
        metrics_file = Path('data/agent_metrics.json')
        if not metrics_file.exists():
            return {"agents": []}
        
        with open(metrics_file, 'r') as f:
            all_metrics = json.load(f)
        
        # Return list of agents with their latest metrics
        agents = []
        for hostname, data in all_metrics.items():
            agents.append({
                'hostname': hostname,
                'agent_id': data.get('agent_id'),
                'os_type': data.get('os_type'),
                'last_seen': data.get('last_seen'),
                'discovered_at': data.get('discovered_at'),
                'status': 'online' if (time.time() - data.get('last_seen', 0)) < 120 else 'offline'
            })
        
        return {"agents": agents}
    
    except Exception as e:
        print(f"Error getting agent metrics: {e}")
        return JSONResponse({"detail": f"Failed to get metrics: {str(e)}"}, status_code=500)

# === Discovery API ===

def _classify_device_type(ip: str, open_ports: set, snmp_sysdescr: str) -> str:
    """Classify a discovered device into a device type based on open ports and SNMP sysDescr."""
    desc = (snmp_sysdescr or "").lower()

    # SNMP sysDescr keyword matching (most reliable)
    if any(k in desc for k in ("cisco ios", "juniper", "junos", "extreme networks", "aruba", "hp procurve",
                                "dell powerconnect", "netgear gs", "catalyst", "nexus", "3com")):
        if any(k in desc for k in ("switch", "catalyst", "nexus", "gs", "powerconnect", "procurve")):
            return "switch"
        if any(k in desc for k in ("router", "asr", "isr", "mx series", "srx")):
            return "router"
        if any(k in desc for k in ("firewall", "asa", "pix", "fortigate", "pfsense", "checkpoint", "srx")):
            return "firewall"

    if any(k in desc for k in ("pfsense", "opnsense", "fortigate", "checkpoint", "asa", "firewall", "netscreen")):
        return "firewall"

    if any(k in desc for k in ("switch", "catalyst", "nexus", "procurve", "powerconnect")):
        return "switch"

    if any(k in desc for k in ("router", "asr", "isr", "mikrotik", "routeros")):
        return "router"

    if any(k in desc for k in ("linux", "ubuntu", "debian", "centos", "rhel", "rocky", "fedora",
                                "windows", "microsoft", "freebsd", "proxmox", "esxi", "vmware")):
        return "rack-server"

    # Port-based heuristics
    has_ssh = 22 in open_ports
    has_http = 80 in open_ports or 443 in open_ports or 8080 in open_ports or 8443 in open_ports
    has_telnet = 23 in open_ports
    has_snmp = 161 in open_ports
    has_rdp = 3389 in open_ports
    has_bgp = 179 in open_ports
    has_ospf_port = 520 in open_ports or 521 in open_ports

    # Firewall/router: BGP or routing ports, no SSH server services
    if has_bgp or has_ospf_port:
        return "router"

    # Telnet + SNMP + no SSH = likely network device
    if has_telnet and has_snmp and not has_ssh:
        return "switch"

    # SNMP only, no SSH, no HTTP = likely network device (switch/router)
    if has_snmp and not has_ssh and not has_http and not has_rdp:
        return "switch"

    # SSH + HTTP/HTTPS = Linux server
    if has_ssh and has_http:
        return "rack-server"

    # RDP = Windows server
    if has_rdp:
        return "rack-server"

    # SSH only = Linux server
    if has_ssh:
        return "rack-server"

    # SNMP + HTTP = could be managed switch with web UI
    if has_snmp and has_http:
        return "switch"

    # Default: generic server
    return "rack-server"


def _probe_ports_sync(ip: str, ports: list, timeout: float = 0.8) -> set:
    """Synchronously probe a list of TCP ports; return set of open ones."""
    open_ports = set()
    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                open_ports.add(port)
        except Exception:
            pass
    return open_ports


def _snmp_sysdescr_sync(ip: str, community: str = "public", timeout: float = 1.5) -> str:
    """Try to fetch SNMP sysDescr.0 via snmpget; return empty string on failure."""
    try:
        result = subprocess.run(
            ["snmpget", "-v2c", "-c", community, "-t", "1", "-r", "1",
             f"{ip}:161", "1.3.6.1.2.1.1.1.0"],
            capture_output=True, text=True, timeout=timeout + 1
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            # Output: SNMPv2-MIB::sysDescr.0 = STRING: <value>
            if "STRING:" in out:
                return out.split("STRING:", 1)[-1].strip().strip('"')
            return out
    except Exception:
        pass
    return ""


@app.post("/api/discovery/start")
async def start_discovery() -> Any:
    """Scan network, discover hosts, and save new ones to the database."""
    import asyncio, re, socket

    network = "192.168.50.0/24"
    server_ip = "192.168.50.225"

    async def run(cmd):
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        return stdout.decode()

    async def ping_host(ip):
        try:
            proc = await asyncio.create_subprocess_shell(
                f"ping -c 1 -W 1 {ip}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3)
            return proc.returncode == 0
        except Exception:
            return False

    # nmap ping scan
    nmap_ips = set()
    try:
        output = await run(f"nmap -sn --host-timeout 3s {network}")
        nmap_ips = set(re.findall(r'Nmap scan report for (?:\S+ \()?(\d+\.\d+\.\d+\.\d+)\)?', output))
    except Exception:
        pass

    # Parallel ping sweep for the full /24 (catches hosts nmap misses)
    import ipaddress
    all_ips = [str(ip) for ip in ipaddress.ip_network(network, strict=False).hosts()
               if not str(ip).endswith('.255')]
    ping_tasks = [ping_host(ip) for ip in all_ips]
    ping_results = await asyncio.gather(*ping_tasks)
    ping_ips = {ip for ip, alive in zip(all_ips, ping_results) if alive}

    # Combine both sets, exclude server itself
    found_ips = sorted((nmap_ips | ping_ips) - {server_ip})

    if not found_ips:
        return {"status": "done", "message": "No hosts found on network", "added": 0, "found": 0}

    # Get existing active hosts to avoid duplicates
    existing = await db_get_hosts(active_only=True)
    existing_addresses = {h.address for h in existing}

    # Ports to probe for device classification
    PROBE_PORTS = [22, 23, 80, 179, 443, 520, 521, 3389, 8080, 8443]
    SNMP_COMMUNITY = (getattr(settings, "snmp_community", "") or "public").strip() or "public"

    async def classify_ip(ip: str) -> tuple[str, str, str]:
        """Returns (ip, hostname, device_type)."""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = f"host-{ip.split('.')[-1]}"

        # Run port probe + SNMP in thread pool concurrently
        open_ports, sysdescr = await asyncio.gather(
            asyncio.to_thread(_probe_ports_sync, ip, PROBE_PORTS, 0.8),
            asyncio.to_thread(_snmp_sysdescr_sync, ip, SNMP_COMMUNITY, 1.5),
        )
        device_type = _classify_device_type(ip, open_ports, sysdescr)
        return (ip, hostname, device_type)

    # Classify all new IPs concurrently (limit concurrency)
    sem = asyncio.Semaphore(16)
    async def classify_limited(ip):
        async with sem:
            return await classify_ip(ip)

    classify_tasks = [classify_limited(ip) for ip in found_ips if ip not in existing_addresses]
    classifications = await asyncio.gather(*classify_tasks, return_exceptions=True)

    added = []
    for result in classifications:
        if isinstance(result, Exception):
            continue
        ip, hostname, device_type = result
        try:
            from app.models import HostCreate as HC
            await db_create_host(HC(name=hostname, address=ip, type=device_type, tags=[], notes=None))
            added.append({"ip": ip, "type": device_type})
        except Exception:
            pass

    return {
        "status": "done",
        "message": f"Discovery complete. Found {len(found_ips)} hosts, added {len(added)} new.",
        "found": len(found_ips),
        "added": len(added),
        "new_hosts": added,
    }

# === Routes for User Management Pages ===

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Serve the system logs page."""
    return FileResponse("app/static/logs.html")

@app.get("/hosts", response_class=HTMLResponse)
async def hosts_page(request: Request):
    """Serve the hosts management page."""
    return FileResponse("app/static/hosts.html")

@app.get("/maps", response_class=HTMLResponse)
async def maps_page(request: Request):
    """Serve the network maps page."""
    return FileResponse("app/static/maps.html")

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """Serve the user management page."""
    return FileResponse("app/static/users.html")

@app.get("/user-groups", response_class=HTMLResponse)
async def user_groups_page(request: Request):
    """Serve the user groups management page."""
    return FileResponse("app/static/user-groups.html")
