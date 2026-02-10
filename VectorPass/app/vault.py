from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from .crypto import decrypt_aesgcm, encrypt_aesgcm
from .db import Db


@dataclass(frozen=True)
class EntryMeta:
    id: str
    site_name: str
    url: str
    login_username: str
    tags: list[str]
    created_at: str
    updated_at: str


def _aad(user_id: int, entry_id: str) -> bytes:
    return f"vp:{user_id}:{entry_id}".encode("utf-8")


async def list_entries(db: Db, user_id: int) -> list[EntryMeta]:
    rows = await db.fetchall(
        """
        SELECT id, site_name, url, login_username, tags_json, created_at, updated_at
        FROM entries
        WHERE user_id = ?
        ORDER BY site_name COLLATE NOCASE ASC, updated_at DESC
        """,
        (user_id,),
    )
    out: list[EntryMeta] = []
    for r in rows:
        out.append(
            EntryMeta(
                id=str(r["id"]),
                site_name=str(r["site_name"]),
                url=str(r["url"]),
                login_username=str(r["login_username"]),
                tags=list(json.loads(str(r["tags_json"]) or "[]")),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
        )
    return out


async def get_entry_meta(db: Db, user_id: int, entry_id: str) -> Optional[EntryMeta]:
    r = await db.fetchone(
        """
        SELECT id, site_name, url, login_username, tags_json, created_at, updated_at
        FROM entries
        WHERE user_id = ? AND id = ?
        """,
        (user_id, entry_id),
    )
    if r is None:
        return None
    return EntryMeta(
        id=str(r["id"]),
        site_name=str(r["site_name"]),
        url=str(r["url"]),
        login_username=str(r["login_username"]),
        tags=list(json.loads(str(r["tags_json"]) or "[]")),
        created_at=str(r["created_at"]),
        updated_at=str(r["updated_at"]),
    )


async def get_entry_secrets(db: Db, user_id: int, entry_id: str, key: bytes) -> Optional[Tuple[str, str]]:
    r = await db.fetchone(
        """
        SELECT password_nonce, password_cipher, notes_nonce, notes_cipher
        FROM entries
        WHERE user_id = ? AND id = ?
        """,
        (user_id, entry_id),
    )
    if r is None:
        return None

    aad = _aad(user_id, entry_id)
    password = decrypt_aesgcm(key, bytes(r["password_nonce"]), bytes(r["password_cipher"]), aad).decode("utf-8")
    notes = decrypt_aesgcm(key, bytes(r["notes_nonce"]), bytes(r["notes_cipher"]), aad).decode("utf-8")
    return password, notes


async def upsert_entry(
    db: Db,
    user_id: int,
    key: bytes,
    *,
    entry_id: Optional[str],
    site_name: str,
    url: str,
    login_username: str,
    password: str,
    notes: str,
    tags: list[str],
) -> str:
    eid = entry_id or str(uuid.uuid4())
    aad = _aad(user_id, eid)

    p_nonce, p_cipher = encrypt_aesgcm(key, password.encode("utf-8"), aad)
    n_nonce, n_cipher = encrypt_aesgcm(key, notes.encode("utf-8"), aad)

    tags_json = json.dumps(tags, ensure_ascii=False)

    if entry_id is None:
        await db.execute(
            """
            INSERT INTO entries(
                id, user_id, site_name, url, login_username,
                password_nonce, password_cipher,
                notes_nonce, notes_cipher,
                tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (eid, user_id, site_name, url, login_username, p_nonce, p_cipher, n_nonce, n_cipher, tags_json),
        )
    else:
        await db.execute(
            """
            UPDATE entries
            SET site_name = ?, url = ?, login_username = ?,
                password_nonce = ?, password_cipher = ?,
                notes_nonce = ?, notes_cipher = ?,
                tags_json = ?,
                updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            WHERE user_id = ? AND id = ?
            """,
            (site_name, url, login_username, p_nonce, p_cipher, n_nonce, n_cipher, tags_json, user_id, eid),
        )
    return eid


async def delete_entry(db: Db, user_id: int, entry_id: str) -> None:
    await db.execute("DELETE FROM entries WHERE user_id = ? AND id = ?", (user_id, entry_id))
