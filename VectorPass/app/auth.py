from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .db import Db


_ph = PasswordHasher()


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    enc_salt: bytes
    role: str
    is_active: bool
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    email: Optional[str] = None


def _row_to_user(row) -> User:
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        enc_salt=bytes(row["enc_salt"]),
        role=str(row["role"]),
        is_active=bool(int(row["is_active"])),
        totp_secret=row["totp_secret"] if row["totp_secret"] else None,
        totp_enabled=bool(int(row["totp_enabled"] or 0)),
        email=row["email"] if row["email"] else None,
    )


_USER_COLS = "id, username, password_hash, enc_salt, role, is_active, totp_secret, totp_enabled, email"


async def create_user(db: Db, username: str, password: str, role: str = "user", is_active: bool = True, email: Optional[str] = None) -> User:
    # 16 bytes salt for key derivation
    enc_salt = secrets.token_bytes(16)
    password_hash = _ph.hash(password)

    await db.execute(
        "INSERT INTO users(username, password_hash, enc_salt, role, is_active, email) VALUES(?, ?, ?, ?, ?, ?)",
        (username, password_hash, enc_salt, role, 1 if is_active else 0, email),
    )
    row = await db.fetchone(
        f"SELECT {_USER_COLS} FROM users WHERE username = ?",
        (username,),
    )
    assert row is not None
    return _row_to_user(row)


async def get_user_by_username(db: Db, username: str) -> Optional[User]:
    row = await db.fetchone(
        f"SELECT {_USER_COLS} FROM users WHERE username = ?",
        (username,),
    )
    if row is None:
        return None
    return _row_to_user(row)


async def get_user_by_id(db: Db, user_id: int) -> Optional[User]:
    row = await db.fetchone(
        f"SELECT {_USER_COLS} FROM users WHERE id = ?",
        (user_id,),
    )
    if row is None:
        return None
    return _row_to_user(row)


async def set_user_role(db: Db, user_id: int, role: str) -> None:
    await db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


async def set_user_active(db: Db, user_id: int, is_active: bool) -> None:
    await db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))


def verify_password(user: User, password: str) -> bool:
    try:
        return _ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False


# ── TOTP helpers ─────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = "VectorPass") -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # Strip all non-digit characters (spaces, dashes, etc.)
    clean = "".join(c for c in code if c.isdigit())
    return totp.verify(clean, valid_window=10)


async def enable_totp(db: Db, user_id: int, secret: str) -> None:
    await db.execute(
        "UPDATE users SET totp_secret = ?, totp_enabled = 1 WHERE id = ?",
        (secret, user_id),
    )


async def disable_totp(db: Db, user_id: int) -> None:
    await db.execute(
        "UPDATE users SET totp_secret = NULL, totp_enabled = 0 WHERE id = ?",
        (user_id,),
    )


# ── Password reset helpers ────────────────────────────────────────────────────────

async def create_reset_token(db: Db, user_id: int, ttl_minutes: int = 30) -> str:
    """Create a single-use password reset token valid for ttl_minutes."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%dT%H:%M:%fZ")
    # Invalidate any previous unused tokens for this user
    await db.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,),
    )
    await db.execute(
        "INSERT INTO password_reset_tokens(user_id, token, expires_at) VALUES(?, ?, ?)",
        (user_id, token, expires_at),
    )
    return token


async def get_user_by_reset_token(db: Db, token: str) -> Optional[User]:
    """Return the user for a valid, unused, non-expired reset token."""
    row = await db.fetchone(
        """
        SELECT u.id, u.username, u.password_hash, u.enc_salt, u.role, u.is_active,
               u.totp_secret, u.totp_enabled, u.email
        FROM password_reset_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = ?
          AND t.used = 0
          AND t.expires_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (token,),
    )
    if row is None:
        return None
    return _row_to_user(row)


async def consume_reset_token(db: Db, token: str, new_password: str) -> bool:
    """Verify token, update password + re-derive enc_salt, mark token used. Returns True on success."""
    user = await get_user_by_reset_token(db, token)
    if user is None:
        return False
    new_hash = _ph.hash(new_password)
    new_salt = secrets.token_bytes(16)
    await db.execute(
        "UPDATE users SET password_hash = ?, enc_salt = ? WHERE id = ?",
        (new_hash, new_salt, user.id),
    )
    await db.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
        (token,),
    )
    return True


async def get_user_by_email(db: Db, email: str) -> Optional[User]:
    row = await db.fetchone(
        f"SELECT {_USER_COLS} FROM users WHERE email = ?",
        (email.lower().strip(),),
    )
    if row is None:
        return None
    return _row_to_user(row)
