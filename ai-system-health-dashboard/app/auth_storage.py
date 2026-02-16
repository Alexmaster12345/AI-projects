from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
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
    email: Optional[str] = None
    last_login: Optional[float] = None


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
                created_at REAL NOT NULL,
                email TEXT,
                last_login REAL
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

        # Add user groups table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                allowed_hosts TEXT,  -- JSON array of host IDs or patterns like "DC-*", "LABS-*"
                created_at REAL NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_name ON user_groups(name);")

        # Add user group memberships table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_group_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
                UNIQUE(user_id, group_id)
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_group_memberships_user_id ON user_group_memberships(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_group_memberships_group_id ON user_group_memberships(group_id);")

        # Migrate existing database schema
        self._migrate_database(conn)

        conn.commit()
        self._conn = conn

    def _remember_digest(self, token: str) -> str:
        # HMAC (peppered) digest so raw tokens never touch disk.
        # Rotating SESSION_SECRET_KEY invalidates existing remember-me cookies.
        key = settings.session_secret_key.encode("utf-8")
        msg = token.encode("utf-8")
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def _migrate_database(self, conn: sqlite3.Connection) -> None:
        """Migrate database schema to latest version."""
        try:
            # Check if email column exists in users table
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'email' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            
            if 'last_login' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN last_login REAL")
            
            # Check if user_groups table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_groups'")
            if cursor.fetchone() is None:
                conn.execute(
                    """
                    CREATE TABLE user_groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        allowed_hosts TEXT,
                        created_at REAL NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_name ON user_groups(name);")
            
            # Check if user_group_memberships table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_group_memberships'")
            if cursor.fetchone() is None:
                conn.execute(
                    """
                    CREATE TABLE user_group_memberships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        created_at REAL NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
                        UNIQUE(user_id, group_id)
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_group_memberships_user_id ON user_group_memberships(user_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_group_memberships_group_id ON user_group_memberships(group_id);")
                
        except Exception as e:
            print(f"Database migration error: {e}")

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

    # User Management Methods
    def create_user(self, username: str, password: str, role: str = "user", email: Optional[str] = None, is_active: bool = True) -> User:
        if not self.enabled:
            raise RuntimeError("Auth storage not enabled")
        conn = self._require_conn()
        password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"salt", 100000).hex()
        created_at = time.time()
        
        with self._lock:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, is_active, created_at, email)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, password_hash, role, 1 if is_active else 0, created_at, email),
            )
            user_id = cursor.lastrowid
            conn.commit()
        
        return User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
            created_at=created_at,
            email=email,
            last_login=None,
        )

    def update_user(self, user_id: int, **kwargs) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()
        
        # Build dynamic update query
        set_clauses = []
        params = []
        
        if 'username' in kwargs:
            set_clauses.append("username = ?")
            params.append(kwargs['username'])
        if 'password' in kwargs and kwargs['password']:
            password_hash = hashlib.pbkdf2_hmac("sha256", kwargs['password'].encode("utf-8"), b"salt", 100000).hex()
            set_clauses.append("password_hash = ?")
            params.append(password_hash)
        if 'role' in kwargs:
            set_clauses.append("role = ?")
            params.append(kwargs['role'])
        if 'is_active' in kwargs:
            set_clauses.append("is_active = ?")
            params.append(1 if kwargs['is_active'] else 0)
        if 'email' in kwargs:
            set_clauses.append("email = ?")
            params.append(kwargs['email'])
        if 'last_login' in kwargs:
            set_clauses.append("last_login = ?")
            params.append(kwargs['last_login'])
        
        if not set_clauses:
            return False
        
        params.append(user_id)
        
        with self._lock:
            conn.execute(
                f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            conn.commit()
        
        return conn.total_changes > 0

    def delete_user(self, user_id: int) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()
        
        with self._lock:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        
        return conn.total_changes > 0

    def get_all_users(self) -> list[User]:
        if not self.enabled:
            return []
        conn = self._require_conn()
        
        with self._lock:
            rows = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active, created_at, email, last_login
                FROM users
                ORDER BY username
                """
            ).fetchall()
        
        return [
            User(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                role=row[3],
                is_active=bool(row[4]),
                created_at=row[5],
                email=row[6],
                last_login=row[7],
            )
            for row in rows
        ]

    def update_last_login(self, user_id: int) -> None:
        """Update the last_login timestamp for a user."""
        if not self.enabled:
            return
        conn = self._require_conn()
        
        with self._lock:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (time.time(), user_id),
            )
            conn.commit()

    # User Group Management Methods
    def create_user_group(self, name: str, description: Optional[str] = None, allowed_hosts: Optional[list] = None) -> int:
        if not self.enabled:
            raise RuntimeError("Auth storage not enabled")
        conn = self._require_conn()
        created_at = time.time()
        allowed_hosts_json = json.dumps(allowed_hosts or []) if allowed_hosts else None
        
        with self._lock:
            cursor = conn.execute(
                """
                INSERT INTO user_groups (name, description, allowed_hosts, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, allowed_hosts_json, created_at),
            )
            group_id = cursor.lastrowid
            conn.commit()
        
        return group_id

    def get_all_user_groups(self) -> list[dict]:
        if not self.enabled:
            return []
        conn = self._require_conn()
        
        with self._lock:
            rows = conn.execute(
                """
                SELECT id, name, description, allowed_hosts, created_at
                FROM user_groups
                ORDER BY name
                """
            ).fetchall()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "allowed_hosts": json.loads(row[3]) if row[3] else [],
                "created_at": row[4],
            }
            for row in rows
        ]

    def add_user_to_group(self, user_id: int, group_id: int) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()
        created_at = time.time()
        
        with self._lock:
            try:
                conn.execute(
                    """
                    INSERT INTO user_group_memberships (user_id, group_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, group_id, created_at),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # User already in group
                return False

    def remove_user_from_group(self, user_id: int, group_id: int) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()
        
        with self._lock:
            conn.execute(
                "DELETE FROM user_group_memberships WHERE user_id = ? AND group_id = ?",
                (user_id, group_id),
            )
            conn.commit()
        
        return conn.total_changes > 0

    def get_user_groups(self, user_id: int) -> list[dict]:
        if not self.enabled:
            return []
        conn = self._require_conn()
        
        with self._lock:
            rows = conn.execute(
                """
                SELECT g.id, g.name, g.description, g.allowed_hosts, g.created_at
                FROM user_groups g
                JOIN user_group_memberships ugm ON g.id = ugm.group_id
                WHERE ugm.user_id = ?
                ORDER BY g.name
                """,
                (user_id,),
            ).fetchall()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "allowed_hosts": json.loads(row[3]) if row[3] else [],
                "created_at": row[4],
            }
            for row in rows
        ]

    def get_user_accessible_hosts(self, user_id: int) -> list[str]:
        """Get list of host patterns/IDs that user can access based on their groups."""
        if not self.enabled:
            return []
        conn = self._require_conn()
        
        with self._lock:
            rows = conn.execute(
                """
                SELECT DISTINCT g.allowed_hosts
                FROM user_groups g
                JOIN user_group_memberships ugm ON g.id = ugm.group_id
                WHERE ugm.user_id = ? AND g.allowed_hosts IS NOT NULL
                """,
                (user_id,),
            ).fetchall()
        
        allowed_hosts = []
        for row in rows:
            if row[0]:
                allowed_hosts.extend(json.loads(row[0]))
        
        return allowed_hosts


auth_storage = SQLiteAuthStorage(settings.auth_db_path)


async def init_auth_storage() -> None:
    if not auth_storage.enabled:
        return
    await asyncio.to_thread(auth_storage.init)
