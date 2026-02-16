from __future__ import annotations

import asyncio
import json
from typing import Any

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
from .storage import get_history as db_get_history
from .storage import get_latest as db_get_latest
from .storage import get_stats as db_get_stats
from .storage import init_storage
from .storage import persist_sample
from .storage import prune_old
from .storage import vacuum as db_vacuum
from .storage import get_hosts
from .storage import create_host as db_create_host
from .storage import deactivate_host as db_deactivate_host
from .storage import update_host as db_update_host
from .storage import storage
from .models import HostCreate, HostUpdate


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
    # Login, agent report, and static assets are truly public (no session needed).
    if path in ("/", "/login", "/api/agent/report"):
        return True
    if path == "/favicon.ico":
        return True
    if path.startswith("/static/"):
        return True
    if path.startswith("/ws/"):
        return True
    # All /api/ paths are allowed through the middleware; individual endpoints
    # handle their own auth (e.g. /api/me returns 401 if no session, /api/admin/*
    # checks admin role).  This avoids the middleware blocking valid session
    # requests to paths it doesn't explicitly list.
    if path.startswith("/api/"):
        return True
    # Host detail pages
    if path.startswith("/host/"):
        return True
    # User management pages (they handle their own auth)
    if path in ("/users", "/user-groups"):
        return True
    return False


def _get_session_user_id(request: Request) -> int | None:
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

        # Check if session exists and has user_id
        user_id = _get_session_user_id(request)
        if user_id is None:
            if _is_api_path(path):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        # Get user from database
        user = await asyncio.to_thread(auth_storage.get_user_by_id, user_id)
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
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    max_age=int(settings.session_max_age_seconds),
    session_cookie=settings.session_cookie_name,
    same_site=settings.session_cookie_samesite,
    https_only=bool(settings.session_cookie_secure),
)
app.add_middleware(AuthMiddleware)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Any:
    err = request.query_params.get("err")
    msg = "Invalid username or password." if err else ""
    err_html = f"<div class='err'>{msg}</div>" if msg else ""

    # Avoid str.format/f-strings here: the embedded CSS uses lots of curly braces.
    html = """<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Login - ASHD</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
                background: linear-gradient(135deg, #070b14 0%, #0a0f1a 100%);
                color: rgba(233, 249, 255, 0.92);
                line-height: 1.6;
            }
            .card {
                width: min(420px, 92vw);
                border: 1px solid rgba(120, 230, 255, 0.18);
                border-radius: 16px;
                background: rgba(0, 0, 0, 0.35);
                backdrop-filter: blur(10px);
                padding: 32px;
                box-shadow: 0 28px 90px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.05);
                transition: all 0.3s ease;
            }
            .card:hover {
                border-color: rgba(120, 230, 255, 0.25);
                box-shadow: 0 28px 90px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.1);
            }
            .t { 
                font-weight: 800; 
                letter-spacing: 0.8px; 
                margin-bottom: 8px; 
                font-size: 24px;
                text-align: center;
                color: #6ee7ff;
            }
            .mut { 
                color: rgba(233, 249, 255, 0.62); 
                font-size: 14px; 
                margin-bottom: 24px; 
                text-align: center;
            }
            label { 
                display: block; 
                font-size: 13px; 
                color: rgba(233, 249, 255, 0.7); 
                margin: 16px 0 8px; 
                font-weight: 500;
            }
            input {
                width: 100%;
                padding: 12px 16px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                background: rgba(0, 0, 0, 0.25);
                color: rgba(233, 249, 255, 0.92);
                outline: none;
                font-size: 15px;
                transition: all 0.2s ease;
            }
            input:focus {
                border-color: #6ee7ff;
                background: rgba(0, 0, 0, 0.35);
                box-shadow: 0 0 0 3px rgba(110, 231, 255, 0.1);
            }
            input::placeholder {
                color: rgba(233, 249, 255, 0.4);
            }
            button {
                margin-top: 20px;
                width: 100%;
                padding: 12px 20px;
                border-radius: 12px;
                border: 1px solid rgba(110, 231, 255, 0.35);
                background: linear-gradient(135deg, rgba(110, 231, 255, 0.1) 0%, rgba(85, 255, 166, 0.1) 100%);
                color: rgba(233, 249, 255, 0.95);
                font-weight: 600;
                font-size: 15px;
                letter-spacing: 0.4px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            button:hover {
                background: linear-gradient(135deg, rgba(110, 231, 255, 0.2) 0%, rgba(85, 255, 166, 0.2) 100%);
                border-color: rgba(110, 231, 255, 0.5);
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(110, 231, 255, 0.2);
            }
            button:active {
                transform: translateY(0);
            }
            .err { 
                margin-top: 12px; 
                padding: 12px;
                background: rgba(255, 77, 109, 0.1);
                border: 1px solid rgba(255, 77, 109, 0.3);
                border-radius: 8px;
                color: #ff4d6d; 
                font-size: 13px;
                text-align: center;
            }
            .brand {
                text-align: center;
                font-size: 32px;
                font-weight: 900;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #6ee7ff 0%, #55ffa6 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
        </style>
    </head>
    <body>
        <form class="card" method="post" action="/login">
            <div class="brand">ASHD</div>
            <div class="t">System Dashboard</div>
            <div class="mut">Sign in to access monitoring and metrics</div>
            <label>Username</label>
            <input name="username" autocomplete="username" placeholder="Enter your username" required />
            <label>Password</label>
            <input name="password" type="password" autocomplete="current-password" placeholder="Enter your password" required />
            %%ERR_HTML%%
            <button type="submit">Sign In</button>
        </form>
    </body>
</html>
"""
    return html.replace("%%ERR_HTML%%", err_html)

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)) -> Any:
    user = await asyncio.to_thread(auth_storage.get_user_by_username, username)
    if user is None or not user.is_active:
        return RedirectResponse(url="/login?err=1", status_code=303)
    ok = await asyncio.to_thread(auth_storage.verify_password, password, user.password_hash)
    if not ok:
        return RedirectResponse(url="/login?err=1", status_code=303)

    request.session["user_id"] = int(user.id)  # type: ignore[attr-defined]
    return RedirectResponse(url="/", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> Any:
    try:
        request.session.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    return RedirectResponse(url="/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def index() -> Any:
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/host/{host_id}", response_class=HTMLResponse)
async def host_page(host_id: int) -> Any:
    with open("app/static/host.html", "r", encoding="utf-8") as f:
        return f.read()


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
    # Get user from session (this works as we've verified)
    user_id = _get_session_user_id(request)
    
    if user_id is None:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    
    user = await asyncio.to_thread(auth_storage.get_user_by_id, user_id)
    if user is None:
        return JSONResponse({"detail": "User not found"}, status_code=401)
    
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active
    }


@app.get("/api/config")
async def api_config() -> Any:
    return {
        "sample_interval_seconds": settings.sample_interval_seconds,
        "history_seconds": settings.history_seconds,
        "ws_allow_anonymous": settings.ws_allow_anonymous,
    }


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


@app.get("/api/hosts")
async def api_get_hosts(active_only: bool = True) -> Any:
    hosts = await get_hosts(active_only=active_only)
    return [h.model_dump() for h in hosts]


@app.get("/api/hosts/{host_id}")
async def api_get_host(host_id: int) -> Any:
    hosts = await get_hosts(active_only=False)
    for h in hosts:
        if h.id == host_id:
            return h.model_dump()
    return JSONResponse({"detail": "Host not found"}, status_code=404)


@app.post("/api/admin/hosts")
async def api_create_host(host_in: HostCreate) -> Any:
    host = await db_create_host(host_in)
    return host.model_dump()


@app.delete("/api/admin/hosts/{host_id}")
async def api_delete_host(host_id: int) -> Any:
    success = await db_deactivate_host(host_id)
    if not success:
        return JSONResponse({"detail": "Host not found"}, status_code=404)
    return {"ok": True}


@app.put("/api/admin/hosts/{host_id}")
async def api_update_host(host_id: int, host_in: HostUpdate) -> Any:
    hosts = await get_hosts(active_only=False)
    if not any(h.id == host_id for h in hosts):
        return JSONResponse({"detail": "Host not found"}, status_code=404)

    updated = await db_update_host(
        host_id,
        name=host_in.name,
        address=host_in.address,
        htype=host_in.type,
        tags=host_in.tags,
        notes=host_in.notes,
    )
    if not updated:
        return JSONResponse({"detail": "No changes applied"}, status_code=400)

    # Return the updated host
    hosts2 = await get_hosts(active_only=False)
    for h in hosts2:
        if h.id == host_id:
            return h.model_dump()
    return JSONResponse({"detail": "Host not found"}, status_code=404)


@app.get("/api/hosts/{host_id}/status")
async def api_get_host_status(host_id: int) -> Any:
    import subprocess
    
    hosts = await get_hosts(active_only=False)
    host = None
    for h in hosts:
        if h.id == host_id:
            host = h
            break
    
    if not host:
        return JSONResponse({"detail": "Host not found"}, status_code=404)
    
    # Try to ping the host
    status = "unknown"
    latency_ms = None
    message = None
    
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", host.address],
            capture_output=True,
            timeout=2.0,
            text=True
        )
        if result.returncode == 0:
            status = "ok"
            # Try to extract latency from ping output
            import re
            match = re.search(r'time=([\d.]+)\s*ms', result.stdout)
            if match:
                latency_ms = float(match.group(1))
            message = "Host is reachable"
        else:
            status = "crit"
            message = "Host is not reachable"
    except Exception as e:
        status = "unknown"
        message = f"Check failed: {str(e)}"
    
    return {
        "status": status,
        "checked_ts": __import__('time').time(),
        "latency_ms": latency_ms,
        "message": message
    }


@app.get("/api/hosts/{host_id}/checks")
async def api_get_host_checks(host_id: int) -> Any:
    import subprocess
    import socket
    hosts = await get_hosts(active_only=False)
    host = None
    for h in hosts:
        if h.id == host_id:
            host = h
            break
    
    if not host:
        return JSONResponse({"detail": "Host not found"}, status_code=404)
    
    def check_port(addr: str, port: int, timeout: float = 1.0) -> dict[str, Any]:
        try:
            with socket.create_connection((addr, port), timeout=timeout):
                return {"status": "ok", "message": f"Port {port} open"}
        except Exception:
            return {"status": "crit", "message": f"Port {port} closed or filtered"}
    
    # Basic port checks for common services
    ssh = check_port(host.address, 22)
    snmp = check_port(host.address, 161)
    syslog = check_port(host.address, 514)
    # NetFlow/sFlow typically uses 2055/6343; we'll just check one representative port
    netflow = check_port(host.address, 2055)
    
    return {
        "icmp": {"status": "unknown", "message": "Use /status endpoint for ICMP"},
        "ssh": ssh,
        "snmp": snmp,
        "syslog": syslog,
        "netflow": netflow,
    }


@app.post("/api/agent/report")
async def api_agent_report(data: dict[str, Any]) -> Any:
    """
    Simple agent endpoint for hosts to push metrics.
    Expected payload:
    {
        "hostname": "...",
        "cpu_percent": 12.3,
        "mem_percent": 45.6,
        "disk_percent": 78.9,
        "net_bytes_sent": 1234567,
        "net_bytes_recv": 7654321,
        "uptime_seconds": 123456,
        "load1": 0.5,
        "load5": 0.4,
        "load15": 0.3,
        "timestamp": 1739500000
    }
    """
    # For now, just accept and store in memory (could be extended to DB)
    # In a real deployment, you'd authenticate the agent and store per-host metrics
    try:
        hostname = data.get("hostname")
        if not hostname:
            return JSONResponse({"detail": "Missing hostname"}, status_code=400)
        # Store in a simple in-memory dict for demo (key: hostname -> latest report)
        if not hasattr(app.state, "_agent_reports"):
            app.state._agent_reports = {}
        report = {
            **data,
            "received_ts": __import__('time').time(),
        }
        app.state._agent_reports[hostname] = report

        # Broadcast real-time update to WebSocket clients
        from .broadcast import broadcaster
        await broadcaster.broadcast(json.dumps({
            "type": "agent_report",
            "hostname": hostname,
            "report": report,
        }))

        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"detail": f"Error processing report: {e}"}, status_code=500)


@app.get("/api/hosts/{host_id}/metrics")
async def api_get_host_metrics(host_id: int) -> Any:
    """
    Return the latest agent metrics for a host (if any).
    """
    hosts = await get_hosts(active_only=False)
    host = None
    for h in hosts:
        if h.id == host_id:
            host = h
            break
    if not host:
        return JSONResponse({"detail": "Host not found"}, status_code=404)
    reports = getattr(app.state, "_agent_reports", {})
    # Try to match by hostname first, then by address as fallback
    report = reports.get(host.name) or reports.get(host.address)
    # Also try common variations (e.g., space vs dash)
    if not report:
        for key, val in reports.items():
            if key.replace(' ', '-').replace('-', ' ').lower() == host.name.replace(' ', '-').replace('-', ' ').lower():
                report = val
                break
    if not report:
        return {"status": "no_data"}
    return report


@app.post("/api/admin/hosts/discover")
async def api_discover_hosts(data: dict[str, Any]) -> Any:
    import ipaddress
    import subprocess
    import socket
    import re
    
    network = data.get("network", "192.168.50.0/24")
    timeout = float(data.get("timeout", 0.5))
    
    try:
        net = ipaddress.ip_network(network, strict=False)
    except ValueError as e:
        return JSONResponse({"detail": f"Invalid network: {e}"}, status_code=400)
    
    # Safety: limit to /24 or smaller
    if net.num_addresses > 256:
        return JSONResponse(
            {"detail": "Network too large. Maximum /24 (256 addresses) allowed for safety."},
            status_code=400
        )
    
    discovered = []
    existing_hosts = await get_hosts(active_only=True)
    existing_addrs = {h.address for h in existing_hosts}

    def _normalize_hostname(raw: str | None, ip_str: str) -> str:
        v = (str(raw or "").strip()).rstrip(".")
        if v == "":
            return f"host-{ip_str.replace('.', '-')}"
        # Prefer short hostname (strip domain) if it's a FQDN.
        if "." in v:
            v = v.split(".", 1)[0]
        v = v.strip().lower()
        # Replace invalid chars with '-', collapse repeats.
        v = re.sub(r"[^a-z0-9-]+", "-", v)
        v = re.sub(r"-+", "-", v).strip("-")
        if v == "" or v == "localhost":
            return f"host-{ip_str.replace('.', '-')}"
        return v
    
    # Scan network
    for ip in net.hosts():
        ip_str = str(ip)
        
        # Quick ping check
        try:
            ping_wait_s = max(1, int(round(float(timeout))))
            run_timeout_s = max(1.0, float(timeout) + 0.5)
            result = subprocess.run(
                ["ping", "-n", "-c", "1", "-W", str(ping_wait_s), ip_str],
                capture_output=True,
                timeout=run_timeout_s,
            )
            if result.returncode == 0:
                # Try to resolve hostname
                try:
                    hostname = socket.gethostbyaddr(ip_str)[0]
                except Exception:
                    hostname = f"host-{ip_str.replace('.', '-')}"

                discovered.append({"address": ip_str, "name": _normalize_hostname(hostname, ip_str)})
        except Exception:
            continue
    
    # Add new hosts
    added = 0
    for disc in discovered:
        if disc["address"] not in existing_addrs:
            host_in = HostCreate(
                name=disc["name"],
                address=disc["address"],
                type="Auto-discovered",
                tags=["auto-discovered"],
                notes=f"Discovered on {network}"
            )
            await db_create_host(host_in)
            added += 1
    
    return {"discovered": len(discovered), "added": added, "scanned": net.num_addresses}


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
    asyncio.create_task(_sampler_loop())


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    # Auth for WebSocket: SessionMiddleware stores session on the ASGI scope.
    # Reject if missing/invalid.
    session = ws.scope.get("session")  # type: ignore[assignment]
    user_id = None
    anonymous = False
    try:
        if isinstance(session, dict):
            user_id = session.get("user_id")
    except Exception:
        user_id = None
    if user_id is None:
            if settings.ws_allow_anonymous:
                anonymous = True
            else:
                await ws.close(code=4401)
                return

    if not anonymous:
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
        
        # Update user groups if specified
        if user_in.user_groups is not None:
            # Get current groups
            current_groups = await asyncio.to_thread(auth_storage.get_user_groups, user_id)
            current_group_ids = {g["id"] for g in current_groups}
            new_group_ids = set(user_in.user_groups)
            
            # Remove from groups not in new list
            for group_id in current_group_ids - new_group_ids:
                await asyncio.to_thread(auth_storage.remove_user_from_group, user_id, group_id)
            
            # Add to groups in new list
            for group_id in new_group_ids - current_group_ids:
                await asyncio.to_thread(auth_storage.add_user_to_group, user_id, group_id)
        
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

# === Routes for User Management Pages ===

@app.get("/users")
async def users_page(request: Request) -> Any:
    """Serve the users management page."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return RedirectResponse(url="/login", status_code=303)
    
    return FileResponse("app/static/users.html")

@app.get("/user-groups")
async def user_groups_page(request: Request) -> Any:
    """Serve the user groups management page."""
    user = await _get_current_user(request)
    if user is None or user.role != "admin":
        return RedirectResponse(url="/login", status_code=303)
    
    return FileResponse("app/static/user-groups.html")
