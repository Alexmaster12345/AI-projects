from __future__ import annotations

import secrets
from dataclasses import dataclass
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
    )


_USER_COLS = "id, username, password_hash, enc_salt, role, is_active, totp_secret, totp_enabled"


async def create_user(db: Db, username: str, password: str, role: str = "user", is_active: bool = True) -> User:
    # 16 bytes salt for key derivation
    enc_salt = secrets.token_bytes(16)
    password_hash = _ph.hash(password)

    await db.execute(
        "INSERT INTO users(username, password_hash, enc_salt, role, is_active) VALUES(?, ?, ?, ?, ?)",
        (username, password_hash, enc_salt, role, 1 if is_active else 0),
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
    return totp.verify(clean, valid_window=2)


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
