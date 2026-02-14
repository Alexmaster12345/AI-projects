from __future__ import annotations

from dataclasses import dataclass
import os


# Best-effort support for local `.env` files.
# `uvicorn[standard]` typically installs `python-dotenv`, but we keep this optional.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(override=False)
except Exception:
    pass


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


@dataclass(frozen=True)
class Settings:
    # App metadata
    app_version: str = _get_str("APP_VERSION", "dev")
    help_url: str = _get_str("HELP_URL", "")

    sample_interval_seconds: float = _get_float("SAMPLE_INTERVAL_SECONDS", 1.0)
    history_seconds: int = _get_int("HISTORY_SECONDS", 600)
    anomaly_window_seconds: int = _get_int("ANOMALY_WINDOW_SECONDS", 120)
    anomaly_z_threshold: float = _get_float("ANOMALY_Z_THRESHOLD", 3.0)

    # SQLite persistence
    metrics_db_path: str = _get_str("METRICS_DB_PATH", "data/metrics.db")
    sqlite_retention_seconds: int = _get_int("SQLITE_RETENTION_SECONDS", 24 * 60 * 60)

    # Auth / sessions
    auth_db_path: str = _get_str("AUTH_DB_PATH", "data/auth.db")
    # REQUIRED for login to work. Set via env var (or .env).
    session_secret_key: str = _get_str("SESSION_SECRET_KEY", "")
    session_max_age_seconds: int = _get_int("SESSION_MAX_AGE_SECONDS", 24 * 60 * 60)
    # Cookie security. For LAN HTTP deployments, keep secure_cookie False.
    session_cookie_secure: bool = bool(int(_get_str("SESSION_COOKIE_SECURE", "0") or "0"))
    session_cookie_samesite: str = _get_str("SESSION_COOKIE_SAMESITE", "strict")
    session_cookie_name: str = _get_str("SESSION_COOKIE_NAME", "ashd_session")

    # Remember-me (persistent login)
    remember_cookie_name: str = _get_str("REMEMBER_COOKIE_NAME", "ashd_remember")
    remember_max_age_seconds: int = _get_int("REMEMBER_MAX_AGE_SECONDS", 7 * 24 * 60 * 60)

    # --- Protocol health checks (cached, non-blocking) ---
    protocol_check_interval_seconds: float = _get_float("PROTOCOL_CHECK_INTERVAL_SECONDS", 30.0)

    # NTP
    ntp_server: str = _get_str("NTP_SERVER", "pool.ntp.org")
    ntp_timeout_seconds: float = _get_float("NTP_TIMEOUT_SECONDS", 1.2)

    # ICMP
    icmp_host: str = _get_str("ICMP_HOST", "1.1.1.1")
    icmp_timeout_seconds: float = _get_float("ICMP_TIMEOUT_SECONDS", 1.0)

    # SNMP (empty host disables)
    snmp_host: str = _get_str("SNMP_HOST", "")
    snmp_port: int = _get_int("SNMP_PORT", 161)
    snmp_community: str = _get_str("SNMP_COMMUNITY", "")
    snmp_timeout_seconds: float = _get_float("SNMP_TIMEOUT_SECONDS", 1.2)

    # NetFlow collector (local UDP port expected to be bound)
    netflow_port: int = _get_int("NETFLOW_PORT", 2055)

    # WebSocket settings
    ws_allow_anonymous: bool = bool(int(_get_str("WS_ALLOW_ANONYMOUS", "1") or "1"))


settings = Settings()

