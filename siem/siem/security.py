from __future__ import annotations

import base64
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class SecurityConfig:
    api_key: str
    basic_user: str
    basic_pass: str
    exempt_paths: Tuple[str, ...]

    rate_limit_enabled: bool
    rate_limit_rps: float
    rate_limit_burst: int
    rate_limit_paths: Tuple[str, ...]

    max_body_bytes: int


def _parse_csv(value: str) -> Tuple[str, ...]:
    parts = [p.strip() for p in (value or "").split(",")]
    return tuple([p for p in parts if p])


def load_security_config() -> SecurityConfig:
    exempt = _parse_csv(os.environ.get("SIEM_AUTH_EXEMPT_PATHS") or "/health")

    api_key = (os.environ.get("SIEM_API_KEY") or "").strip()
    basic_user = (os.environ.get("SIEM_BASIC_USER") or "").strip()
    basic_pass = (os.environ.get("SIEM_BASIC_PASS") or "").strip()

    rate_limit_enabled = (os.environ.get("SIEM_RATE_LIMIT_ENABLED") or "").strip().lower() in {"1", "true", "yes"}
    rate_limit_rps = float((os.environ.get("SIEM_RATE_LIMIT_RPS") or "200").strip() or 200.0)
    rate_limit_burst = int((os.environ.get("SIEM_RATE_LIMIT_BURST") or "400").strip() or 400)
    rate_limit_paths = _parse_csv(os.environ.get("SIEM_RATE_LIMIT_PATHS") or "/ingest,/edr")

    max_body_bytes = int((os.environ.get("SIEM_MAX_BODY_BYTES") or str(1_048_576)).strip() or 1_048_576)

    return SecurityConfig(
        api_key=api_key,
        basic_user=basic_user,
        basic_pass=basic_pass,
        exempt_paths=exempt,
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_rps=rate_limit_rps,
        rate_limit_burst=rate_limit_burst,
        rate_limit_paths=rate_limit_paths,
        max_body_bytes=max_body_bytes,
    )


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _path_is_exempt(path: str, exempt_paths: Iterable[str]) -> bool:
    for p in exempt_paths:
        if not p:
            continue
        if p == path:
            return True
        if p.endswith("*") and path.startswith(p[:-1]):
            return True
    return False


def _path_matches_prefixes(path: str, prefixes: Tuple[str, ...]) -> bool:
    for pref in prefixes:
        if not pref:
            continue
        if path == pref:
            return True
        # common use: "/edr" should cover "/edr/..."
        if path.startswith(pref.rstrip("/") + "/"):
            return True
    return False


def _unauthorized_basic() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"ok": False, "error": "unauthorized"},
        headers={"www-authenticate": 'Basic realm="SIEM"'},
    )


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})


def _forbidden() -> JSONResponse:
    return JSONResponse(status_code=403, content={"ok": False, "error": "forbidden"})


def _parse_basic_auth(authz: str) -> Optional[Tuple[str, str]]:
    try:
        scheme, value = authz.split(" ", 1)
        if scheme.lower() != "basic":
            return None
        raw = base64.b64decode(value.strip().encode("ascii"))
        user_pass = raw.decode("utf-8", errors="replace")
        if ":" not in user_pass:
            return None
        user, pwd = user_pass.split(":", 1)
        return user, pwd
    except Exception:
        return None


def _parse_bearer(authz: str) -> Optional[str]:
    try:
        scheme, value = authz.split(" ", 1)
        if scheme.lower() != "bearer":
            return None
        return value.strip()
    except Exception:
        return None


def _check_auth(request: Request, cfg: SecurityConfig) -> Tuple[bool, Optional[JSONResponse]]:
    """Return (authorized, error_response_if_any)."""
    auth_required = bool(cfg.api_key or cfg.basic_user or cfg.basic_pass)
    if not auth_required:
        return True, None

    path = request.url.path
    if _path_is_exempt(path, cfg.exempt_paths):
        return True, None

    # API key auth
    if cfg.api_key:
        header_key = (request.headers.get("x-api-key") or "").strip()
        authz = (request.headers.get("authorization") or "").strip()
        bearer = _parse_bearer(authz) if authz else None

        candidate = header_key or (bearer or "")
        if candidate and secrets.compare_digest(candidate, cfg.api_key):
            return True, None

    # Basic auth
    if cfg.basic_user and cfg.basic_pass:
        authz = (request.headers.get("authorization") or "").strip()
        parsed = _parse_basic_auth(authz) if authz else None
        if parsed is not None:
            user, pwd = parsed
            if secrets.compare_digest(user, cfg.basic_user) and secrets.compare_digest(pwd, cfg.basic_pass):
                return True, None
        return False, _unauthorized_basic()

    return False, _unauthorized()


class _TokenBucket:
    def __init__(self, *, rps: float, burst: int) -> None:
        self._rps = max(float(rps), 0.1)
        self._burst = max(int(burst), 1)
        self._events: Dict[str, Deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window = float(self._burst) / float(self._rps)
        q = self._events.get(key)
        if q is None:
            q = deque()
            self._events[key] = q

        # purge old
        cutoff = now - window
        while q and q[0] < cutoff:
            q.popleft()

        if len(q) >= self._burst:
            return False
        q.append(now)
        return True


def attach_security_middleware(app, *, cfg: Optional[SecurityConfig] = None) -> None:
    cfg = cfg or load_security_config()
    limiter = _TokenBucket(rps=cfg.rate_limit_rps, burst=cfg.rate_limit_burst)

    @app.middleware("http")
    async def _security_mw(request: Request, call_next):
        # Basic request size guard for POST/PUT/PATCH (best-effort via Content-Length)
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                clen = request.headers.get("content-length")
                if clen is not None:
                    if int(clen) > cfg.max_body_bytes:
                        return JSONResponse(status_code=413, content={"ok": False, "error": "payload too large"})
            except Exception:
                return JSONResponse(status_code=400, content={"ok": False, "error": "invalid content-length"})

        # Rate limit (defaults to /ingest and /edr/*)
        if cfg.rate_limit_enabled and _path_matches_prefixes(request.url.path, cfg.rate_limit_paths):
            ip = _client_ip(request)
            key = f"{ip}:{request.url.path}"
            if not limiter.allow(key):
                return JSONResponse(status_code=429, content={"ok": False, "error": "rate limited"})

        ok, err = _check_auth(request, cfg)
        if not ok:
            return err or _forbidden()

        resp = await call_next(request)

        # Security headers
        resp.headers.setdefault("x-content-type-options", "nosniff")
        resp.headers.setdefault("x-frame-options", "DENY")
        resp.headers.setdefault("referrer-policy", "no-referrer")
        resp.headers.setdefault("permissions-policy", "geolocation=(), microphone=(), camera=()")
        resp.headers.setdefault("cross-origin-opener-policy", "same-origin")
        resp.headers.setdefault("cross-origin-resource-policy", "same-origin")

        # CSP: keep permissive enough for inline <style>/<script> in the dashboard.
        resp.headers.setdefault(
            "content-security-policy",
            "default-src 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'",
        )

        # Only set HSTS when request is HTTPS (or behind a proxy that sets X-Forwarded-Proto=https)
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
        if proto == "https":
            resp.headers.setdefault("strict-transport-security", "max-age=15552000; includeSubDomains")

        return resp
