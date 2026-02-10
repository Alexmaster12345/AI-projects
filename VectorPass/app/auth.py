from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional

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


async def create_user(db: Db, username: str, password: str, role: str = "user", is_active: bool = True) -> User:
    # 16 bytes salt for key derivation
    enc_salt = secrets.token_bytes(16)
    password_hash = _ph.hash(password)

    await db.execute(
        "INSERT INTO users(username, password_hash, enc_salt, role, is_active) VALUES(?, ?, ?, ?, ?)",
        (username, password_hash, enc_salt, role, 1 if is_active else 0),
    )
    row = await db.fetchone(
        "SELECT id, username, password_hash, enc_salt, role, is_active FROM users WHERE username = ?",
        (username,),
    )
    assert row is not None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        enc_salt=bytes(row["enc_salt"]),
        role=str(row["role"]),
        is_active=bool(int(row["is_active"])),
    )


async def get_user_by_username(db: Db, username: str) -> Optional[User]:
    row = await db.fetchone(
        "SELECT id, username, password_hash, enc_salt, role, is_active FROM users WHERE username = ?",
        (username,),
    )
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        enc_salt=bytes(row["enc_salt"]),
        role=str(row["role"]),
        is_active=bool(int(row["is_active"])),
    )


async def get_user_by_id(db: Db, user_id: int) -> Optional[User]:
    row = await db.fetchone(
        "SELECT id, username, password_hash, enc_salt, role, is_active FROM users WHERE id = ?",
        (user_id,),
    )
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        enc_salt=bytes(row["enc_salt"]),
        role=str(row["role"]),
        is_active=bool(int(row["is_active"])),
    )


async def set_user_role(db: Db, user_id: int, role: str) -> None:
    await db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


async def set_user_active(db: Db, user_id: int, is_active: bool) -> None:
    await db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))


def verify_password(user: User, password: str) -> bool:
    try:
        return _ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False
