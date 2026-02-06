#!/usr/bin/env python3
"""Manage users for the AI System Health Dashboard.

This is an offline admin tool intended to be run on the host where the dashboard
runs. It avoids needing the sqlite3 CLI.

Examples:
  python scripts/manage_users.py list
  python scripts/manage_users.py create --username admin --role admin --password 'changeme'
  python scripts/manage_users.py set-password --username admin --password 'newpass'
  python scripts/manage_users.py set-role --username viewer --role admin
  python scripts/manage_users.py deactivate --username viewer

Notes:
- Uses the same PBKDF2 password hashing as the app.
- Reads AUTH_DB_PATH from env/.env via app.config.settings.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

# When running as a script (python scripts/manage_users.py), Python puts the script
# directory on sys.path, not the project root. Ensure we can import `app`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth_storage import SQLiteAuthStorage  # noqa: E402
from app.config import settings  # noqa: E402


CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    if not db_path:
        raise SystemExit("AUTH_DB_PATH is empty; auth storage is disabled")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    con.execute(CREATE_USERS_TABLE_SQL)
    con.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    con.commit()
    return con


def cmd_list(args: argparse.Namespace) -> int:
    con = _connect(args.db)
    cur = con.execute(
        "SELECT id, username, role, is_active, created_at FROM users ORDER BY id"
    )
    rows = cur.fetchall()
    if not rows:
        print("No users found.")
        return 0

    print(f"DB: {args.db}")
    for (uid, username, role, is_active, created_at) in rows:
        status = "active" if int(is_active or 0) else "inactive"
        ts = float(created_at or 0.0)
        print(f"{int(uid):>3}  {username:<20}  {role:<6}  {status:<8}  created_at={ts:.0f}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    username = (args.username or "").strip()
    if not username:
        raise SystemExit("--username is required")

    role = (args.role or "viewer").strip().lower()
    if role not in ("viewer", "admin"):
        raise SystemExit("--role must be viewer|admin")

    if not args.password:
        raise SystemExit("--password is required")

    hasher = SQLiteAuthStorage(args.db)
    password_hash = hasher.hash_password(args.password)

    con = _connect(args.db)
    try:
        con.execute(
            "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
            (username, password_hash, role, float(time.time())),
        )
        con.commit()
    except sqlite3.IntegrityError as e:
        raise SystemExit(f"Failed to create user: {e}")

    print(f"Created user '{username}' with role '{role}'.")
    return 0


def cmd_set_password(args: argparse.Namespace) -> int:
    username = (args.username or "").strip()
    if not username:
        raise SystemExit("--username is required")
    if not args.password:
        raise SystemExit("--password is required")

    hasher = SQLiteAuthStorage(args.db)
    password_hash = hasher.hash_password(args.password)

    con = _connect(args.db)
    cur = con.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (password_hash, username),
    )
    con.commit()
    if cur.rowcount == 0:
        raise SystemExit(f"User not found: {username}")

    print(f"Password updated for '{username}'.")
    return 0


def cmd_set_role(args: argparse.Namespace) -> int:
    username = (args.username or "").strip()
    if not username:
        raise SystemExit("--username is required")

    role = (args.role or "").strip().lower()
    if role not in ("viewer", "admin"):
        raise SystemExit("--role must be viewer|admin")

    con = _connect(args.db)
    cur = con.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    con.commit()
    if cur.rowcount == 0:
        raise SystemExit(f"User not found: {username}")

    print(f"Role updated for '{username}' -> '{role}'.")
    return 0


def _set_active(db: str, username: str, active: bool) -> int:
    username = (username or "").strip()
    if not username:
        raise SystemExit("--username is required")

    con = _connect(db)
    cur = con.execute(
        "UPDATE users SET is_active = ? WHERE username = ?",
        (1 if active else 0, username),
    )
    con.commit()
    if cur.rowcount == 0:
        raise SystemExit(f"User not found: {username}")

    print(f"User '{username}' is now {'active' if active else 'inactive'}.")
    return 0


def cmd_deactivate(args: argparse.Namespace) -> int:
    return _set_active(args.db, args.username, False)


def cmd_activate(args: argparse.Namespace) -> int:
    return _set_active(args.db, args.username, True)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage dashboard auth users")
    p.add_argument(
        "--db",
        default=settings.auth_db_path,
        help="Path to auth SQLite DB (default: AUTH_DB_PATH or data/auth.db)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List users")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("create", help="Create a user")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--role", default="viewer", choices=["viewer", "admin"])
    sp.set_defaults(func=cmd_create)

    sp = sub.add_parser("set-password", help="Set a user's password")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", required=True)
    sp.set_defaults(func=cmd_set_password)

    sp = sub.add_parser("set-role", help="Set a user's role")
    sp.add_argument("--username", required=True)
    sp.add_argument("--role", required=True, choices=["viewer", "admin"])
    sp.set_defaults(func=cmd_set_role)

    sp = sub.add_parser("deactivate", help="Deactivate a user")
    sp.add_argument("--username", required=True)
    sp.set_defaults(func=cmd_deactivate)

    sp = sub.add_parser("activate", help="Activate a user")
    sp.add_argument("--username", required=True)
    sp.set_defaults(func=cmd_activate)

    return p


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
