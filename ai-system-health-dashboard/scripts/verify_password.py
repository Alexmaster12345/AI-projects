#!/usr/bin/env python3
"""Offline password verifier for ASHD users.

Usage:
  python scripts/verify_password.py --username admin

Prompts for a password (no echo) and verifies it against the stored hash.
This helps debug "Invalid username or password" without touching the web UI.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Ensure we can import `app` when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth_storage import SQLiteAuthStorage  # noqa: E402
from app.config import settings  # noqa: E402


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Verify a user's password against the auth DB")
    p.add_argument("--username", required=True)
    p.add_argument(
        "--db",
        default=settings.auth_db_path,
        help="Path to auth SQLite DB (default: AUTH_DB_PATH or data/auth.db)",
    )
    args = p.parse_args(argv)

    store = SQLiteAuthStorage(args.db)
    user = store.get_user_by_username(args.username)
    if user is None:
        print(f"User not found: {args.username}")
        return 2
    if not user.is_active:
        print(f"User is inactive: {args.username}")
        return 3

    pw = getpass.getpass(f"Password for '{args.username}': ")
    ok = store.verify_password(pw, user.password_hash)
    print("OK" if ok else "BAD")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
