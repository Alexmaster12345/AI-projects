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
from typing import Any, Optional

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
            <div class="loginLogo" aria-hidden="true">ASHD</div>

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
    # If pysnmp isn't installed, auth_storage imports set getCmd=None.
    try:
        from .protocols import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity  # type: ignore
    except Exception:
        getCmd = None  # type: ignore

    if getCmd is None:
        return ProtocolStatus(status="unknown", checked_ts=ts, message="pysnmp not installed")

    timeout = float(getattr(settings, "snmp_timeout_seconds", 1.2) or 1.2)
    try:
        t0 = time.perf_counter()
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=timeout, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),
        )
        error_indication, error_status, error_index, _var_binds = next(iterator)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        if error_indication:
            return ProtocolStatus(status="crit", checked_ts=ts, latency_ms=latency_ms, message=str(error_indication))
        if error_status:
            return ProtocolStatus(
                status="crit",
                checked_ts=ts,
                latency_ms=latency_ms,
                message=f"{error_status.prettyPrint()} at {error_index}",
            )
        return ProtocolStatus(status="ok", checked_ts=ts, latency_ms=latency_ms, message=f"{host}:{port}")
    except Exception as e:
        return ProtocolStatus(status="crit", checked_ts=ts, message=f"SNMP failed: {e}")


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
    start_protocol_checker()
    asyncio.create_task(_host_checker_loop())
    asyncio.create_task(_sampler_loop())


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
