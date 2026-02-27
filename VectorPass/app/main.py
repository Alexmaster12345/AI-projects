from __future__ import annotations

import base64
import io
import secrets
from pathlib import Path

from typing import Optional, Tuple
from urllib.parse import urlparse

import qrcode
import qrcode.image.svg
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .config import Settings, load_settings
from .db import Db
from .crypto import derive_key_from_password
from .vault_session import VaultKeyCache
from . import vault
from . import tokens


def _new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _get_session(request: Request) -> dict:
    # Starlette SessionMiddleware populates request.session
    return request.session  # type: ignore[attr-defined]


def require_user_id(request: Request) -> int:
    sess = _get_session(request)
    uid = sess.get("user_id")
    if not isinstance(uid, int):
        raise HTTPException(status_code=401)
    return uid


def require_session_id(request: Request) -> str:
    sess = _get_session(request)
    sid = sess.get("sid")
    if not isinstance(sid, str) or not sid:
        sid = _new_session_id()
        sess["sid"] = sid
    return sid


def create_app() -> FastAPI:
    settings = load_settings()
    db = Db(settings.db_path)
    keys = VaultKeyCache()

    app = FastAPI(title=settings.app_name)

    # Allow Chrome extension (or other clients) to call JSON APIs using Bearer tokens.
    # We don't use cookies/credentials for these APIs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie=settings.cookie_name,
        same_site=settings.cookie_samesite,
        https_only=settings.cookie_secure,
        max_age=settings.session_max_age_seconds,
    )

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

    def get_settings() -> Settings:
        return settings

    def get_db() -> Db:
        return db

    def get_keys() -> VaultKeyCache:
        return keys

    def _base_ctx(request: Request) -> dict:
        sess = _get_session(request)
        role = sess.get("role")
        return {
            "request": request,
            "app_name": settings.app_name,
            "username": sess.get("username"),
            "is_admin": role == "admin",
            "is_operator": role in {"operator", "admin"},
        }

    async def _refresh_session_identity(request: Request, user: auth.User) -> None:
        sess = _get_session(request)
        sess["user_id"] = user.id
        sess["username"] = user.username
        sess["role"] = user.role
        if not isinstance(sess.get("sid"), str) or not sess.get("sid"):
            sess["sid"] = _new_session_id()

    async def require_user(request: Request, db: Db = Depends(get_db)) -> auth.User:
        user_id = require_user_id(request)
        user = await auth.get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401)
        await _refresh_session_identity(request, user)
        return user

    async def require_admin(user: auth.User = Depends(require_user)) -> auth.User:
        if user.role != "admin":
            raise HTTPException(status_code=403)
        return user

    async def require_operator(user: auth.User = Depends(require_user)) -> auth.User:
        if user.role not in {"operator", "admin"}:
            raise HTTPException(status_code=403)
        return user

    async def require_token_user_and_key(
        authorization: Optional[str] = Header(None),
        db: Db = Depends(get_db),
    ) -> Tuple[auth.User, bytes]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401)
        token_plain = authorization.split(" ", 1)[1].strip()
        if not token_plain:
            raise HTTPException(status_code=401)

        th = tokens.token_hash(token_plain, settings.session_secret_key)
        tok = await tokens.get_token_by_hash(db, th)
        if tok is None:
            raise HTTPException(status_code=401)

        user = await auth.get_user_by_id(db, tok.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401)
        if user.role not in {"operator", "admin"}:
            raise HTTPException(status_code=403)

        vault_key = tokens.decrypt_vault_key_from_token(token_plain, tok)
        await tokens.touch_token_used(db, tok.id)
        return user, vault_key

    @app.on_event("startup")
    async def _bootstrap_admin() -> None:
        # If VECTORPASS_BOOTSTRAP_ADMIN_* are set, ensure an admin exists.
        if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
            return
        username = settings.bootstrap_admin_username.strip()
        password = settings.bootstrap_admin_password
        if not username or not password:
            return

        existing = await auth.get_user_by_username(db, username)
        if existing is None:
            await auth.create_user(db, username, password, role="admin", is_active=True)
        else:
            # Promote/activate if needed.
            if existing.role != "admin":
                await auth.set_user_role(db, existing.id, "admin")
            if not existing.is_active:
                await auth.set_user_active(db, existing.id, True)

    def is_unlocked(request: Request, user_id: int = Depends(require_user_id), sid: str = Depends(require_session_id), key_cache: VaultKeyCache = Depends(get_keys)) -> bool:
        return key_cache.get(sid, user_id) is not None

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        sess = _get_session(request)
        uid = sess.get("user_id")
        if isinstance(uid, int):
            return RedirectResponse(url="/vault", status_code=303)
        return RedirectResponse(url="/login", status_code=303)

    @app.get("/register", response_class=HTMLResponse)
    async def register_page(request: Request, settings: Settings = Depends(get_settings)) -> HTMLResponse:
        ctx = _base_ctx(request)
        ctx.update({"error": None})
        return templates.TemplateResponse("register.html", ctx)

    @app.post("/register")
    async def register_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        password2: str = Form(...),
        db: Db = Depends(get_db),
        keys: VaultKeyCache = Depends(get_keys),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        username = username.strip()
        if not username:
            return templates.TemplateResponse("register.html", {"request": request, "app_name": settings.app_name, "error": "Username is required."})
        if password != password2:
            return templates.TemplateResponse("register.html", {"request": request, "app_name": settings.app_name, "error": "Passwords do not match."})
        if len(password) < 8:
            return templates.TemplateResponse("register.html", {"request": request, "app_name": settings.app_name, "error": "Password must be at least 8 characters."})

        existing = await auth.get_user_by_username(db, username)
        if existing is not None:
            ctx = _base_ctx(request)
            ctx.update({"error": "Username already exists."})
            return templates.TemplateResponse("register.html", ctx)

        user = await auth.create_user(db, username, password, role="user", is_active=True)
        sess = _get_session(request)
        sess.clear()
        await _refresh_session_identity(request, user)
        # Login is enough: derive the vault key now.
        key = derive_key_from_password(password, user.enc_salt)
        keys.set(sess["sid"], user.id, key, ttl_seconds=settings.vault_unlock_ttl_seconds)
        return RedirectResponse(url="/vault", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, settings: Settings = Depends(get_settings)) -> HTMLResponse:
        ctx = _base_ctx(request)
        ctx.update({"error": None})
        return templates.TemplateResponse("login.html", ctx)

    @app.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Db = Depends(get_db),
        keys: VaultKeyCache = Depends(get_keys),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        username = username.strip()
        user = await auth.get_user_by_username(db, username)
        if user is None or not auth.verify_password(user, password):
            ctx = _base_ctx(request)
            ctx.update({"error": "Invalid username or password."})
            return templates.TemplateResponse("login.html", ctx)
        if not user.is_active:
            ctx = _base_ctx(request)
            ctx.update({"error": "Account is disabled."})
            return templates.TemplateResponse("login.html", ctx)

        sess = _get_session(request)
        sess.clear()

        # If 2FA is enabled, stash pending state and redirect to challenge
        if user.totp_enabled and user.totp_secret:
            sess["2fa_pending_user_id"] = user.id
            # Derive and cache the vault key now — released only after 2FA passes
            key = derive_key_from_password(password, user.enc_salt)
            pending_sid = _new_session_id()
            sess["2fa_pending_sid"] = pending_sid
            keys.set(pending_sid, user.id, key, ttl_seconds=300)  # 5-min window
            return RedirectResponse(url="/2fa", status_code=303)

        await _refresh_session_identity(request, user)
        key = derive_key_from_password(password, user.enc_salt)
        keys.set(sess["sid"], user.id, key, ttl_seconds=settings.vault_unlock_ttl_seconds)
        return RedirectResponse(url="/vault", status_code=303)

    @app.get("/2fa", response_class=HTMLResponse)
    async def totp_challenge_page(request: Request) -> HTMLResponse:
        sess = _get_session(request)
        if not sess.get("2fa_pending_user_id"):
            return RedirectResponse(url="/login", status_code=303)
        ctx = _base_ctx(request)
        ctx.update({"error": None})
        return templates.TemplateResponse("2fa.html", ctx)

    @app.post("/2fa")
    async def totp_challenge_submit(
        request: Request,
        code: str = Form(...),
        db: Db = Depends(get_db),
        keys: VaultKeyCache = Depends(get_keys),
        settings: Settings = Depends(get_settings),
    ) -> HTMLResponse:
        sess = _get_session(request)
        pending_uid = sess.get("2fa_pending_user_id")
        pending_sid = sess.get("2fa_pending_sid")
        if not isinstance(pending_uid, int) or not isinstance(pending_sid, str):
            return RedirectResponse(url="/login", status_code=303)

        user = await auth.get_user_by_id(db, pending_uid)
        if user is None or not user.totp_enabled or not user.totp_secret:
            return RedirectResponse(url="/login", status_code=303)

        if not auth.verify_totp(user.totp_secret, code):
            ctx = _base_ctx(request)
            ctx.update({"error": "Invalid code. Please try again."})
            return templates.TemplateResponse("2fa.html", ctx)

        # Retrieve the pre-derived vault key from the temporary slot
        vault_key = keys.get(pending_sid, pending_uid)
        keys.clear(pending_sid)  # remove temp slot

        # Promote to real session
        sess.pop("2fa_pending_user_id", None)
        sess.pop("2fa_pending_sid", None)
        await _refresh_session_identity(request, user)

        if vault_key is not None:
            keys.set(sess["sid"], user.id, vault_key, ttl_seconds=settings.vault_unlock_ttl_seconds)
        return RedirectResponse(url="/vault", status_code=303)

    # ── 2FA Settings ──────────────────────────────────────────────────────────

    def _make_qr_data_uri(uri: str) -> str:
        """Render a TOTP provisioning URI as a base64 PNG data URI."""
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    @app.get("/settings/2fa", response_class=HTMLResponse)
    async def settings_2fa_page(
        request: Request,
        user: auth.User = Depends(require_user),
    ) -> HTMLResponse:
        ctx = _base_ctx(request)
        ctx.update({
            "totp_enabled": user.totp_enabled,
            "pending_secret": None,
            "qr_uri": None,
            "error": None,
            "success": None,
        })
        return templates.TemplateResponse("settings_2fa.html", ctx)

    @app.post("/settings/2fa/setup", response_class=HTMLResponse)
    async def settings_2fa_setup(
        request: Request,
        user: auth.User = Depends(require_user),
    ) -> HTMLResponse:
        """Generate a new TOTP secret and show the QR code for scanning."""
        secret = auth.generate_totp_secret()
        uri = auth.get_totp_uri(secret, user.username)
        qr_data = _make_qr_data_uri(uri)
        ctx = _base_ctx(request)
        ctx.update({
            "totp_enabled": user.totp_enabled,
            "pending_secret": secret,
            "qr_uri": qr_data,
            "error": None,
            "success": None,
        })
        return templates.TemplateResponse("settings_2fa.html", ctx)

    @app.post("/settings/2fa/enable", response_class=HTMLResponse)
    async def settings_2fa_enable(
        request: Request,
        code: str = Form(...),
        pending_secret: str = Form(...),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
    ) -> HTMLResponse:
        """Verify the first TOTP code to confirm setup and enable 2FA."""
        secret = pending_secret.strip()
        if not secret:
            return RedirectResponse(url="/settings/2fa", status_code=303)

        if not auth.verify_totp(secret, code):
            uri = auth.get_totp_uri(secret, user.username)
            qr_data = _make_qr_data_uri(uri)
            ctx = _base_ctx(request)
            ctx.update({
                "totp_enabled": user.totp_enabled,
                "pending_secret": secret,
                "qr_uri": qr_data,
                "error": "Invalid code — please try again.",
                "success": None,
            })
            return templates.TemplateResponse("settings_2fa.html", ctx)

        await auth.enable_totp(db, user.id, secret)
        ctx = _base_ctx(request)
        ctx.update({
            "totp_enabled": True,
            "pending_secret": None,
            "qr_uri": None,
            "error": None,
            "success": "Two-factor authentication is now enabled.",
        })
        return templates.TemplateResponse("settings_2fa.html", ctx)

    @app.post("/settings/2fa/disable", response_class=HTMLResponse)
    async def settings_2fa_disable(
        request: Request,
        code: str = Form(...),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
    ) -> HTMLResponse:
        """Disable 2FA after confirming with a valid TOTP code."""
        if not user.totp_enabled or not user.totp_secret:
            return RedirectResponse(url="/settings/2fa", status_code=303)
        if not auth.verify_totp(user.totp_secret, code):
            ctx = _base_ctx(request)
            ctx.update({
                "totp_enabled": True,
                "pending_secret": None,
                "qr_uri": None,
                "error": "Invalid code. 2FA not disabled.",
                "success": None,
            })
            return templates.TemplateResponse("settings_2fa.html", ctx)

        await auth.disable_totp(db, user.id)
        ctx = _base_ctx(request)
        ctx.update({
            "totp_enabled": False,
            "pending_secret": None,
            "qr_uri": None,
            "error": None,
            "success": "Two-factor authentication has been disabled.",
        })
        return templates.TemplateResponse("settings_2fa.html", ctx)

    @app.post("/logout")
    async def logout(request: Request, keys: VaultKeyCache = Depends(get_keys)) -> RedirectResponse:
        sess = _get_session(request)
        sid = sess.get("sid")
        if isinstance(sid, str):
            keys.clear(sid)
        sess.clear()
        return RedirectResponse(url="/login", status_code=303)

    @app.get("/unlock", response_class=HTMLResponse)
    async def unlock_page(
        request: Request,
        settings: Settings = Depends(get_settings),
        unlocked: bool = Depends(is_unlocked),
    ) -> HTMLResponse:
        if unlocked:
            return RedirectResponse(url="/vault", status_code=303)
        # Kept as a fallback in case the in-memory key cache expires mid-session.
        ctx = _base_ctx(request)
        ctx.update({"error": None})
        return templates.TemplateResponse("unlock.html", ctx)

    @app.post("/unlock")
    async def unlock_submit(
        request: Request,
        password: str = Form(...),
        settings: Settings = Depends(get_settings),
        db: Db = Depends(get_db),
        keys: VaultKeyCache = Depends(get_keys),
        user_id: int = Depends(require_user_id),
        sid: str = Depends(require_session_id),
    ) -> HTMLResponse:
        user = await auth.get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=401)
        if not user.is_active:
            raise HTTPException(status_code=401)
        if not auth.verify_password(user, password):
            ctx = _base_ctx(request)
            ctx.update({"error": "Wrong password."})
            return templates.TemplateResponse("unlock.html", ctx)

        await _refresh_session_identity(request, user)

        key = derive_key_from_password(password, user.enc_salt)
        keys.set(sid, user_id, key, ttl_seconds=settings.vault_unlock_ttl_seconds)
        return RedirectResponse(url="/vault", status_code=303)

    @app.post("/lock")
    async def lock(request: Request, keys: VaultKeyCache = Depends(get_keys), user_id: int = Depends(require_user_id), sid: str = Depends(require_session_id)) -> RedirectResponse:
        keys.clear(sid)
        return RedirectResponse(url="/unlock", status_code=303)

    def require_vault_key(
        request: Request,
        user_id: int = Depends(require_user_id),
        sid: str = Depends(require_session_id),
        keys: VaultKeyCache = Depends(get_keys),
    ) -> bytes:
        key = keys.get(sid, user_id)
        if key is None:
            raise HTTPException(status_code=403, detail="Vault locked")
        return key

    @app.get("/vault", response_class=HTMLResponse)
    async def vault_list(
        request: Request,
        settings: Settings = Depends(get_settings),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
        unlocked: bool = Depends(is_unlocked),
    ) -> HTMLResponse:
        if not unlocked:
            # When key cache expires, send user to the fallback unlock page.
            return RedirectResponse(url="/unlock", status_code=303)
        entries = await vault.list_entries(db, user.id)
        all_tags = sorted({t for e in entries for t in e.tags})
        ctx = _base_ctx(request)
        ctx.update({"entries": entries, "all_tags": all_tags})
        return templates.TemplateResponse(
            "vault_list.html",
            ctx,
        )

    @app.get("/vault/new", response_class=HTMLResponse)
    async def vault_new_page(
        request: Request,
        settings: Settings = Depends(get_settings),
        _user: auth.User = Depends(require_user),
        _op: auth.User = Depends(require_operator),
        unlocked: bool = Depends(is_unlocked),
    ) -> HTMLResponse:
        if not unlocked:
            return RedirectResponse(url="/unlock", status_code=303)
        ctx = _base_ctx(request)
        ctx.update(
            {
                "mode": "new",
                "entry": None,
                "password": "",
                "notes": "",
                "tags": "",
                "error": None,
            }
        )
        return templates.TemplateResponse(
            "vault_edit.html",
            ctx,
        )

    @app.get("/vault/{entry_id}/edit", response_class=HTMLResponse)
    async def vault_edit_page(
        request: Request,
        entry_id: str,
        settings: Settings = Depends(get_settings),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
        _op: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ) -> HTMLResponse:
        meta = await vault.get_entry_meta(db, user.id, entry_id)
        if meta is None:
            raise HTTPException(status_code=404)
        secrets_tuple = await vault.get_entry_secrets(db, user.id, entry_id, key)
        if secrets_tuple is None:
            raise HTTPException(status_code=404)
        password, notes = secrets_tuple
        ctx = _base_ctx(request)
        ctx.update(
            {
                "mode": "edit",
                "entry": meta,
                "password": password,
                "notes": notes,
                "tags": ", ".join(meta.tags),
                "error": None,
            }
        )
        return templates.TemplateResponse(
            "vault_edit.html",
            ctx,
        )

    @app.post("/vault/save")
    async def vault_save(
        request: Request,
        entry_id: str = Form(""),
        site_name: str = Form(...),
        url: str = Form(...),
        login_username: str = Form(...),
        password: str = Form(...),
        notes: str = Form(""),
        tags: str = Form(""),
        settings: Settings = Depends(get_settings),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
        _op: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ) -> HTMLResponse:
        site_name = site_name.strip()
        url = url.strip()
        login_username = login_username.strip()
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        if not site_name or not url or not login_username:
            # Re-render form with error; best-effort preserve.
            meta = None
            if entry_id:
                meta = await vault.get_entry_meta(db, user.id, entry_id)
            ctx = _base_ctx(request)
            ctx.update(
                {
                    "mode": "edit" if entry_id else "new",
                    "entry": meta,
                    "password": password,
                    "notes": notes,
                    "tags": tags,
                    "error": "Site name, URL, and username are required.",
                }
            )
            return templates.TemplateResponse(
                "vault_edit.html",
                ctx,
            )

        eid = await vault.upsert_entry(
            db,
            user.id,
            key,
            entry_id=entry_id or None,
            site_name=site_name,
            url=url,
            login_username=login_username,
            password=password,
            notes=notes,
            tags=tags_list,
        )
        return RedirectResponse(url=f"/vault/{eid}/edit", status_code=303)

    @app.post("/vault/{entry_id}/delete")
    async def vault_delete(
        request: Request,
        entry_id: str,
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
        _op: auth.User = Depends(require_operator),
        _key: bytes = Depends(require_vault_key),
    ) -> RedirectResponse:
        await vault.delete_entry(db, user.id, entry_id)
        return RedirectResponse(url="/vault", status_code=303)

    # ── Import / Export ───────────────────────────────────────────────────────

    @app.get("/vault/export/json")
    async def vault_export_json(
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ):
        from fastapi.responses import StreamingResponse
        entries = await vault.list_entries(db, user.id)
        rows = []
        for e in entries:
            sec = await vault.get_entry_secrets(db, user.id, e.id, key)
            password, notes = sec if sec else ("", "")
            rows.append({
                "site_name": e.site_name,
                "url": e.url,
                "username": e.login_username,
                "password": password,
                "notes": notes,
                "tags": e.tags,
            })
        import json as _json
        content = _json.dumps(rows, indent=2, ensure_ascii=False)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=vectorpass-export.json"},
        )

    @app.get("/vault/export/csv")
    async def vault_export_csv(
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ):
        from fastapi.responses import StreamingResponse
        import csv, io as _io
        entries = await vault.list_entries(db, user.id)
        buf = _io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "url", "username", "password", "notes", "tags"])
        for e in entries:
            sec = await vault.get_entry_secrets(db, user.id, e.id, key)
            password, notes = sec if sec else ("", "")
            writer.writerow([e.site_name, e.url, e.login_username, password, notes, ",".join(e.tags)])
        content = buf.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=vectorpass-export.csv"},
        )

    @app.get("/vault/import", response_class=HTMLResponse)
    async def vault_import_page(
        request: Request,
        _op: auth.User = Depends(require_operator),
    ) -> HTMLResponse:
        ctx = _base_ctx(request)
        ctx.update({"error": None, "success": None})
        return templates.TemplateResponse("vault_import.html", ctx)

    @app.post("/vault/import", response_class=HTMLResponse)
    async def vault_import_submit(
        request: Request,
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ) -> HTMLResponse:
        from fastapi import UploadFile, File
        import csv, io as _io, json as _json
        form = await request.form()
        file: UploadFile = form.get("file")
        if file is None:
            ctx = _base_ctx(request)
            ctx.update({"error": "No file uploaded.", "success": None})
            return templates.TemplateResponse("vault_import.html", ctx)

        raw = await file.read()
        fname = (file.filename or "").lower()
        imported = 0
        errors = []

        try:
            if fname.endswith(".json"):
                rows = _json.loads(raw.decode("utf-8"))
                for i, row in enumerate(rows):
                    try:
                        tags = row.get("tags", [])
                        if isinstance(tags, str):
                            tags = [t.strip() for t in tags.split(",") if t.strip()]
                        await vault.upsert_entry(
                            db, user.id, key, entry_id=None,
                            site_name=str(row.get("site_name", row.get("name", ""))).strip() or "Imported",
                            url=str(row.get("url", "")).strip() or "https://",
                            login_username=str(row.get("username", row.get("login_username", ""))).strip(),
                            password=str(row.get("password", "")),
                            notes=str(row.get("notes", "")),
                            tags=[str(t).strip() for t in tags if str(t).strip()],
                        )
                        imported += 1
                    except Exception as e:
                        errors.append(f"Row {i+1}: {e}")
            elif fname.endswith(".csv"):
                reader = csv.DictReader(_io.StringIO(raw.decode("utf-8")))
                for i, row in enumerate(reader):
                    try:
                        tags_raw = row.get("tags", "")
                        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                        await vault.upsert_entry(
                            db, user.id, key, entry_id=None,
                            site_name=str(row.get("name", row.get("site_name", ""))).strip() or "Imported",
                            url=str(row.get("url", "")).strip() or "https://",
                            login_username=str(row.get("username", row.get("login_username", ""))).strip(),
                            password=str(row.get("password", "")),
                            notes=str(row.get("notes", "")),
                            tags=tags,
                        )
                        imported += 1
                    except Exception as e:
                        errors.append(f"Row {i+1}: {e}")
            else:
                ctx = _base_ctx(request)
                ctx.update({"error": "Unsupported format. Upload a .json or .csv file.", "success": None})
                return templates.TemplateResponse("vault_import.html", ctx)
        except Exception as e:
            ctx = _base_ctx(request)
            ctx.update({"error": f"Parse error: {e}", "success": None})
            return templates.TemplateResponse("vault_import.html", ctx)

        msg = f"Imported {imported} entr{'y' if imported==1 else 'ies'}."
        if errors:
            msg += f" {len(errors)} skipped: " + "; ".join(errors[:3])
        ctx = _base_ctx(request)
        ctx.update({"error": None, "success": msg})
        return templates.TemplateResponse("vault_import.html", ctx)

    @app.get("/api/entries/{entry_id}/reveal")
    async def api_reveal_password(
        entry_id: str,
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
        _op: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ) -> dict:
        secrets_tuple = await vault.get_entry_secrets(db, user.id, entry_id, key)
        if secrets_tuple is None:
            raise HTTPException(status_code=404)
        password, _notes = secrets_tuple
        return {"password": password}

    @app.get("/admin/users", response_class=HTMLResponse)
    async def admin_users_page(
        request: Request,
        _admin: auth.User = Depends(require_admin),
        db: Db = Depends(get_db),
    ) -> HTMLResponse:
        rows = await db.fetchall("SELECT id, username, role, is_active, created_at FROM users ORDER BY created_at DESC")
        users = [
            {
                "id": int(r["id"]),
                "username": str(r["username"]),
                "role": str(r["role"]),
                "is_active": bool(int(r["is_active"])),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
        ctx = _base_ctx(request)
        ctx.update({"users": users})
        return templates.TemplateResponse("admin_users.html", ctx)

    @app.post("/admin/users/{target_user_id}/set_active")
    async def admin_set_active(
        request: Request,
        target_user_id: int,
        active: int = Form(...),
        admin_user: auth.User = Depends(require_admin),
        db: Db = Depends(get_db),
    ) -> RedirectResponse:
        # Prevent self-lockout.
        if target_user_id == admin_user.id and active == 0:
            return RedirectResponse(url="/admin/users", status_code=303)
        await auth.set_user_active(db, target_user_id, bool(active))
        return RedirectResponse(url="/admin/users", status_code=303)

    @app.post("/admin/users/{target_user_id}/set_role")
    async def admin_set_role(
        request: Request,
        target_user_id: int,
        role: str = Form(...),
        admin_user: auth.User = Depends(require_admin),
        db: Db = Depends(get_db),
    ) -> RedirectResponse:
        role = role.strip().lower()
        if role not in {"user", "operator", "admin"}:
            return RedirectResponse(url="/admin/users", status_code=303)
        # Prevent removing your own admin role.
        if target_user_id == admin_user.id and role != "admin":
            return RedirectResponse(url="/admin/users", status_code=303)
        await auth.set_user_role(db, target_user_id, role)
        return RedirectResponse(url="/admin/users", status_code=303)

    @app.get("/tokens", response_class=HTMLResponse)
    async def tokens_page(
        request: Request,
        _op: auth.User = Depends(require_operator),
    ) -> HTMLResponse:
        ctx = _base_ctx(request)
        ctx.update({"created_token": None})
        return templates.TemplateResponse("tokens.html", ctx)

    @app.post("/tokens/create", response_class=HTMLResponse)
    async def tokens_create(
        request: Request,
        name: str = Form(...),
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_operator),
        key: bytes = Depends(require_vault_key),
    ) -> HTMLResponse:
        token_plain, _token_id = await tokens.create_api_token(
            db,
            user.id,
            key,
            name=name.strip() or "Chrome extension",
            server_secret=settings.session_secret_key,
        )
        ctx = _base_ctx(request)
        ctx.update({"created_token": token_plain})
        return templates.TemplateResponse("tokens.html", ctx)

    @app.get("/vault/{entry_id}", response_class=HTMLResponse)
    async def vault_view_page(
        request: Request,
        entry_id: str,
        db: Db = Depends(get_db),
        user: auth.User = Depends(require_user),
    ) -> HTMLResponse:
        meta = await vault.get_entry_meta(db, user.id, entry_id)
        if meta is None:
            raise HTTPException(status_code=404)
        ctx = _base_ctx(request)
        ctx.update({"entry": meta})
        return templates.TemplateResponse("vault_view.html", ctx)

    @app.get("/api/ext/match")
    async def api_ext_match(
        url: str,
        db: Db = Depends(get_db),
        user_and_key: Tuple[auth.User, bytes] = Depends(require_token_user_and_key),
    ) -> dict:
        user, key = user_and_key
        # Match by URL substring (host), prefer longer stored URLs.
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.strip()
        if not host:
            return {"match": None}
        like = f"%{host}%"
        row = await db.fetchone(
            """
            SELECT id, site_name, url, login_username
            FROM entries
            WHERE user_id = ? AND url LIKE ?
            ORDER BY length(url) DESC
            LIMIT 1
            """,
            (user.id, like),
        )
        if row is None:
            return {"match": None}
        entry_id = str(row["id"])
        secrets_tuple = await vault.get_entry_secrets(db, user.id, entry_id, key)
        if secrets_tuple is None:
            return {"match": None}
        password, _notes = secrets_tuple
        return {
            "match": {
                "id": entry_id,
                "site_name": str(row["site_name"]),
                "url": str(row["url"]),
                "username": str(row["login_username"]),
                "password": password,
            }
        }

    @app.post("/api/ext/add")
    async def api_ext_add(
        payload: dict,
        db: Db = Depends(get_db),
        user_and_key: Tuple[auth.User, bytes] = Depends(require_token_user_and_key),
    ) -> dict:
        user, key = user_and_key
        site_name = str(payload.get("site_name", "")).strip()
        url = str(payload.get("url", "")).strip()
        login_username = str(payload.get("login_username", "")).strip()
        password = str(payload.get("password", ""))
        notes = str(payload.get("notes", ""))
        tags = payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tags_list = [str(t).strip() for t in tags if str(t).strip()]

        if not site_name or not url or not login_username:
            raise HTTPException(status_code=400, detail="Missing required fields")

        entry_id = await vault.upsert_entry(
            db,
            user.id,
            key,
            entry_id=None,
            site_name=site_name,
            url=url,
            login_username=login_username,
            password=password,
            notes=notes,
            tags=tags_list,
        )
        return {"id": entry_id}

    return app


app = create_app()
