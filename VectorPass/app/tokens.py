from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional, Tuple

from .crypto import decrypt_aesgcm, encrypt_aesgcm
from .db import Db


@dataclass(frozen=True)
class ApiToken:
    id: int
    user_id: int
    name: str
    token_hash: bytes
    vault_key_nonce: bytes
    vault_key_cipher: bytes


def token_hash(token: str, server_secret: str) -> bytes:
    # HMAC avoids storing a directly reusable hash if DB is leaked.
    return hmac.new(server_secret.encode("utf-8"), token.encode("utf-8"), sha256).digest()


def token_key(token: str) -> bytes:
    # 32-byte key for AES-GCM derived from token. Token must be high entropy.
    return sha256(token.encode("utf-8")).digest()


def _aad(user_id: int, token_hash_bytes: bytes) -> bytes:
    return b"vp_token:" + str(user_id).encode("utf-8") + b":" + token_hash_bytes


async def create_api_token(db: Db, user_id: int, vault_key: bytes, *, name: str, server_secret: str) -> Tuple[str, int]:
    token_plain = secrets.token_urlsafe(32)
    th = token_hash(token_plain, server_secret)
    tk = token_key(token_plain)
    nonce, cipher = encrypt_aesgcm(tk, vault_key, _aad(user_id, th))

    await db.execute(
        "INSERT INTO api_tokens(user_id, name, token_hash, vault_key_nonce, vault_key_cipher) VALUES(?, ?, ?, ?, ?)",
        (user_id, name, th, nonce, cipher),
    )

    row = await db.fetchone(
        "SELECT id FROM api_tokens WHERE token_hash = ?",
        (th,),
    )
    assert row is not None
    return token_plain, int(row["id"])


async def get_token_by_hash(db: Db, token_hash_bytes: bytes) -> Optional[ApiToken]:
    row = await db.fetchone(
        """
        SELECT id, user_id, name, token_hash, vault_key_nonce, vault_key_cipher
        FROM api_tokens
        WHERE token_hash = ?
        """,
        (token_hash_bytes,),
    )
    if row is None:
        return None
    return ApiToken(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        token_hash=bytes(row["token_hash"]),
        vault_key_nonce=bytes(row["vault_key_nonce"]),
        vault_key_cipher=bytes(row["vault_key_cipher"]),
    )


async def touch_token_used(db: Db, token_id: int) -> None:
    await db.execute(
        "UPDATE api_tokens SET last_used_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE id = ?",
        (token_id,),
    )


def decrypt_vault_key_from_token(token_plain: str, token: ApiToken) -> bytes:
    tk = token_key(token_plain)
    return decrypt_aesgcm(tk, token.vault_key_nonce, token.vault_key_cipher, _aad(token.user_id, token.token_hash))
