from __future__ import annotations

import asyncio
import json
import secrets
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
from .models import HostCreate
from .storage import create_host as db_create_host
from .storage import get_history as db_get_history
from .storage import get_hosts as db_get_hosts
from .storage import get_latest as db_get_latest
from .storage import get_stats as db_get_stats
from .storage import deactivate_host as db_deactivate_host
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


@app.get("/api/hosts")
async def api_hosts(active_only: bool = True) -> Any:
    # Auth is handled by middleware (everything except /login is protected).
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    hosts = await db_get_hosts(active_only=bool(active_only))
    return [h.model_dump() for h in hosts]


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


@app.delete("/api/admin/hosts/{host_id}")
async def api_admin_hosts_delete(host_id: int) -> Any:
    if not storage.enabled:
        return JSONResponse({"detail": "Host storage is disabled"}, status_code=503)
    ok = await db_deactivate_host(int(host_id))
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
