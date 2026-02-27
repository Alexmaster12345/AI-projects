from __future__ import annotations

import asyncio
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Db:
    path: Path

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            password_hash TEXT NOT NULL,
                            enc_salt BLOB NOT NULL,
                            role TEXT NOT NULL DEFAULT 'user',
                            is_active INTEGER NOT NULL DEFAULT 1,
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS entries (
                            id TEXT PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            site_name TEXT NOT NULL,
                            url TEXT NOT NULL,
                            login_username TEXT NOT NULL,
                            password_nonce BLOB NOT NULL,
                            password_cipher BLOB NOT NULL,
                            notes_nonce BLOB NOT NULL,
                            notes_cipher BLOB NOT NULL,
                            tags_json TEXT NOT NULL,
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                        );
                        """
                    )

                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS api_tokens (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            name TEXT NOT NULL,
                            token_hash BLOB NOT NULL UNIQUE,
                            vault_key_nonce BLOB NOT NULL,
                            vault_key_cipher BLOB NOT NULL,
                            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                            last_used_at TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                        );
                        """
                    )
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_user_id ON entries(user_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_site ON entries(user_id, site_name);")

                    # Lightweight migrations for existing DBs.
                    cols = {row[1] for row in conn.execute("PRAGMA table_info(users);").fetchall()}
                    if "role" not in cols:
                        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';")
                    if "is_active" not in cols:
                        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")
                    if "totp_secret" not in cols:
                        conn.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT;")
                    if "totp_enabled" not in cols:
                        conn.execute("ALTER TABLE users ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0;")
            finally:
                conn.close()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(sql, params)
        finally:
            conn.close()

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        conn = self._connect()
        try:
            cur = conn.execute(sql, params)
            return cur.fetchone()
        finally:
            conn.close()

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            cur = conn.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        def _run() -> None:
            with self._lock:
                self._execute(sql, params)

        await asyncio.to_thread(_run)

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        def _run() -> Optional[sqlite3.Row]:
            with self._lock:
                return self._fetchone(sql, params)

        return await asyncio.to_thread(_run)

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        def _run() -> list[sqlite3.Row]:
            with self._lock:
                return self._fetchall(sql, params)

        return await asyncio.to_thread(_run)
