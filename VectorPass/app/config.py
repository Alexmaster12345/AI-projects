from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name)
    if v is None:
        if default is None:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default
    return v


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    return int(v)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str

    session_secret_key: str
    cookie_name: str
    cookie_samesite: str
    cookie_secure: bool
    session_max_age_seconds: int

    db_path: Path

    vault_unlock_ttl_seconds: int

    host: str
    port: int

    bootstrap_admin_username: Optional[str]
    bootstrap_admin_password: Optional[str]


def load_settings() -> Settings:
    # Load .env if present (local dev); production can use real env vars.
    load_dotenv(override=False)

    db_path = Path(_env("VECTORPASS_DB_PATH"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        app_name=os.getenv("VECTORPASS_APP_NAME", "VectorPass"),
        session_secret_key=_env("VECTORPASS_SESSION_SECRET_KEY"),
        cookie_name=os.getenv("VECTORPASS_COOKIE_NAME", "vectorpass_session"),
        cookie_samesite=os.getenv("VECTORPASS_COOKIE_SAMESITE", "lax"),
        cookie_secure=_env_bool("VECTORPASS_COOKIE_SECURE", False),
        session_max_age_seconds=_env_int("VECTORPASS_SESSION_MAX_AGE_SECONDS", 86400),
        db_path=db_path,
        vault_unlock_ttl_seconds=_env_int("VECTORPASS_VAULT_UNLOCK_TTL_SECONDS", 900),
        host=os.getenv("VECTORPASS_HOST", "127.0.0.1"),
        port=_env_int("VECTORPASS_PORT", 8001),

        bootstrap_admin_username=os.getenv("VECTORPASS_BOOTSTRAP_ADMIN_USERNAME") or None,
        bootstrap_admin_password=os.getenv("VECTORPASS_BOOTSTRAP_ADMIN_PASSWORD") or None,
    )
