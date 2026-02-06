from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import settings


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    created_at: float


class SQLiteAuthStorage:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._db_path)

    def init(self) -> None:
        if not self.enabled:
            return
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_digest TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL,
                last_used_at REAL,
                user_agent TEXT,
                ip TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_remember_tokens_user_id ON remember_tokens(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_remember_tokens_expires_at ON remember_tokens(expires_at);")
        conn.commit()
        self._conn = conn

    def _remember_digest(self, token: str) -> str:
        # HMAC (peppered) digest so raw tokens never touch disk.
        # Rotating SESSION_SECRET_KEY invalidates existing remember-me cookies.
        key = settings.session_secret_key.encode("utf-8")
        msg = token.encode("utf-8")
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Auth storage not initialized")
        return self._conn

    def get_user_by_username(self, username: str) -> Optional[User]:
        if not self.enabled:
            return None
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT id, username, password_hash, role, is_active, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return User(
            id=int(row[0]),
            username=str(row[1]),
            password_hash=str(row[2]),
            role=str(row[3]),
            is_active=bool(int(row[4] or 0)),
            created_at=float(row[5] or 0.0),
        )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        if not self.enabled:
            return None
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT id, username, password_hash, role, is_active, created_at FROM users WHERE id = ?",
                (int(user_id),),
            ).fetchone()
        if not row:
            return None
        return User(
            id=int(row[0]),
            username=str(row[1]),
            password_hash=str(row[2]),
            role=str(row[3]),
            is_active=bool(int(row[4] or 0)),
            created_at=float(row[5] or 0.0),
        )

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        # Supported format:
        #   pbkdf2_sha256$<iterations>$<salt_b64>$<dk_b64>
        try:
            parts = password_hash.split("$")
            if len(parts) != 4:
                return False
            scheme, iters_s, salt_b64, dk_b64 = parts
            if scheme != "pbkdf2_sha256":
                return False
            iterations = int(iters_s)
            if iterations < 50_000:
                return False
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii") + b"==")
            expected = base64.urlsafe_b64decode(dk_b64.encode("ascii") + b"==")
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt,
                iterations,
                dklen=len(expected),
            )
            return bool(hmac.compare_digest(dk, expected))
        except Exception:
            return False

    def hash_password(self, plain_password: str) -> str:
        iterations = 200_000
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
            dklen=32,
        )

        def _b64(b: bytes) -> str:
            # urlsafe, no padding
            return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")

        return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(dk)}"

    def create_user(self, username: str, plain_password: str, role: str = "viewer") -> User:
        if not self.enabled:
            raise RuntimeError("Auth storage disabled")
        role = role.strip().lower() if role else "viewer"
        if role not in ("viewer", "admin"):
            raise ValueError("role must be 'viewer' or 'admin'")

        password_hash = self.hash_password(plain_password)
        created_at = time.time()

        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                (username, password_hash, role, float(created_at)),
            )
            conn.commit()
            user_id = int(cur.lastrowid)

        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Failed to create user")
        return user

    def create_remember_token(
        self,
        user_id: int,
        token: str,
        *,
        expires_at: float,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            raise RuntimeError("Auth storage disabled")
        conn = self._require_conn()
        token_digest = self._remember_digest(token)
        created_at = time.time()
        with self._lock:
            conn.execute(
                """
                INSERT INTO remember_tokens (user_id, token_digest, created_at, expires_at, revoked_at, last_used_at, user_agent, ip)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    int(user_id),
                    str(token_digest),
                    float(created_at),
                    float(expires_at),
                    (str(user_agent)[:400] if user_agent else None),
                    (str(ip)[:80] if ip else None),
                ),
            )
            conn.commit()

    def validate_remember_token(self, token: str, *, now: Optional[float] = None) -> Optional[int]:
        if not self.enabled:
            return None
        conn = self._require_conn()
        token_digest = self._remember_digest(token)
        now_ts = float(time.time() if now is None else now)
        with self._lock:
            row = conn.execute(
                """
                SELECT user_id, expires_at, revoked_at
                FROM remember_tokens
                WHERE token_digest = ?
                """,
                (str(token_digest),),
            ).fetchone()
            if not row:
                return None
            user_id = int(row[0])
            expires_at = float(row[1] or 0.0)
            revoked_at = row[2]
            if revoked_at is not None:
                return None
            if expires_at <= now_ts:
                return None
            conn.execute(
                "UPDATE remember_tokens SET last_used_at = ? WHERE token_digest = ?",
                (float(now_ts), str(token_digest)),
            )
            conn.commit()
        return user_id

    def revoke_remember_token(self, token: str) -> None:
        if not self.enabled:
            return
        conn = self._require_conn()
        token_digest = self._remember_digest(token)
        now_ts = time.time()
        with self._lock:
            conn.execute(
                "UPDATE remember_tokens SET revoked_at = ? WHERE token_digest = ?",
                (float(now_ts), str(token_digest)),
            )
            conn.commit()


auth_storage = SQLiteAuthStorage(settings.auth_db_path)


async def init_auth_storage() -> None:
    if not auth_storage.enabled:
        return
    await asyncio.to_thread(auth_storage.init)
