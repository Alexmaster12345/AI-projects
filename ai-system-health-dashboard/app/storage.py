from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from .config import settings
from .models import Host, HostCreate, SystemSample


class SQLiteMetricsStorage:
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                ts REAL PRIMARY KEY,
                sample_json TEXT NOT NULL
            );
            """
        )

        # Hosts inventory (admin-managed; used by UI and future per-host checks).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                type TEXT,
                tags_json TEXT NOT NULL,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_ts REAL NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hosts_active ON hosts(is_active);")
        conn.commit()
        self._conn = conn

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLite storage not initialized")
        return self._conn

    def insert_sample(self, sample: SystemSample) -> None:
        if not self.enabled:
            return
        conn = self._require_conn()
        payload = json.dumps(sample.model_dump(), separators=(",", ":"))
        with self._lock:
            conn.execute(
                "INSERT OR REPLACE INTO samples (ts, sample_json) VALUES (?, ?)",
                (float(sample.ts), payload),
            )
            conn.commit()

    def query_latest(self) -> Optional[SystemSample]:
        if not self.enabled:
            return None
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT sample_json FROM samples ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return SystemSample.model_validate(data)

    def query_history(self, seconds: int) -> list[SystemSample]:
        if not self.enabled:
            return []
        conn = self._require_conn()
        cutoff = time.time() - max(1, int(seconds))
        with self._lock:
            rows = conn.execute(
                "SELECT sample_json FROM samples WHERE ts >= ? ORDER BY ts ASC",
                (float(cutoff),),
            ).fetchall()
        out: list[SystemSample] = []
        for (sample_json,) in rows:
            try:
                out.append(SystemSample.model_validate(json.loads(sample_json)))
            except Exception:
                continue
        return out

    def prune_old(self) -> int:
        if not self.enabled:
            return 0
        retention = int(settings.sqlite_retention_seconds)
        if retention <= 0:
            return 0
        conn = self._require_conn()
        cutoff = time.time() - retention
        with self._lock:
            cur = conn.execute("DELETE FROM samples WHERE ts < ?", (float(cutoff),))
            conn.commit()
            return int(cur.rowcount or 0)

    def stats(self) -> dict:
        if not self.enabled:
            return {
                "enabled": False,
                "db_path": self._db_path,
            }
        path = Path(self._db_path)
        file_bytes = int(path.stat().st_size) if path.exists() else 0
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT COUNT(*), MIN(ts), MAX(ts) FROM samples"
            ).fetchone()
        count = int(row[0] or 0) if row else 0
        ts_min = float(row[1]) if row and row[1] is not None else None
        ts_max = float(row[2]) if row and row[2] is not None else None
        return {
            "enabled": True,
            "db_path": str(path),
            "exists": path.exists(),
            "file_bytes": file_bytes,
            "rows": count,
            "ts_min": ts_min,
            "ts_max": ts_max,
            "retention_seconds": int(settings.sqlite_retention_seconds),
            "journal_mode": "WAL",
        }

    def vacuum(self) -> None:
        if not self.enabled:
            return
        conn = self._require_conn()
        # VACUUM cannot run inside a transaction.
        with self._lock:
            conn.execute("VACUUM")
            conn.commit()

    def list_hosts(self, active_only: bool = True) -> list[Host]:
        if not self.enabled:
            return []
        conn = self._require_conn()
        sql = (
            "SELECT id, name, address, type, tags_json, notes, is_active, created_ts "
            "FROM hosts "
            + ("WHERE is_active = 1 " if active_only else "")
            + "ORDER BY id DESC"
        )
        with self._lock:
            rows = conn.execute(sql).fetchall()
        out: list[Host] = []
        for row in rows:
            (hid, name, address, htype, tags_json, notes, is_active, created_ts) = row
            tags: list[str] = []
            try:
                parsed = json.loads(tags_json or "[]")
                if isinstance(parsed, list):
                    tags = [str(t) for t in parsed if str(t).strip()]
            except Exception:
                tags = []
            out.append(
                Host(
                    id=int(hid),
                    name=str(name),
                    address=str(address),
                    type=str(htype) if htype is not None and str(htype).strip() != "" else None,
                    tags=tags,
                    notes=str(notes) if notes is not None and str(notes).strip() != "" else None,
                    is_active=bool(int(is_active) if is_active is not None else 0),
                    created_ts=float(created_ts),
                )
            )
        return out

    def create_host(self, host_in: HostCreate) -> Host:
        if not self.enabled:
            raise RuntimeError("Host storage is disabled (metrics DB path not set)")
        conn = self._require_conn()
        now = time.time()
        tags = [str(t).strip() for t in (host_in.tags or []) if str(t).strip()]
        tags_json = json.dumps(tags, separators=(",", ":"))
        with self._lock:
            cur = conn.execute(
                "INSERT INTO hosts (name, address, type, tags_json, notes, is_active, created_ts) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (
                    str(host_in.name).strip(),
                    str(host_in.address).strip(),
                    (str(host_in.type).strip() if host_in.type is not None and str(host_in.type).strip() != "" else None),
                    tags_json,
                    (str(host_in.notes) if host_in.notes is not None and str(host_in.notes).strip() != "" else None),
                    float(now),
                ),
            )
            conn.commit()
            hid = int(cur.lastrowid)
        return Host(
            id=hid,
            name=str(host_in.name).strip(),
            address=str(host_in.address).strip(),
            type=(str(host_in.type).strip() if host_in.type is not None and str(host_in.type).strip() != "" else None),
            tags=tags,
            notes=(str(host_in.notes) if host_in.notes is not None and str(host_in.notes).strip() != "" else None),
            is_active=True,
            created_ts=float(now),
        )

    def deactivate_host(self, host_id: int) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute("UPDATE hosts SET is_active = 0 WHERE id = ?", (int(host_id),))
            conn.commit()
            return bool(cur.rowcount or 0)


    def update_host(
        self,
        host_id: int,
        *,
        name: str | None = None,
        address: str | None = None,
        htype: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        conn = self._require_conn()

        fields: list[str] = []
        params: list[object] = []

        if name is not None:
            fields.append("name = ?")
            params.append(str(name).strip())
        if address is not None:
            fields.append("address = ?")
            params.append(str(address).strip())
        if htype is not None:
            v = str(htype).strip()
            fields.append("type = ?")
            params.append(v if v != "" else None)
        if tags is not None:
            cleaned = [str(t).strip() for t in (tags or []) if str(t).strip()]
            fields.append("tags_json = ?")
            params.append(json.dumps(cleaned, separators=(",", ":")))
        if notes is not None:
            v = str(notes).strip()
            fields.append("notes = ?")
            params.append(v if v != "" else None)

        if not fields:
            return False

        params.append(int(host_id))
        sql = "UPDATE hosts SET " + ", ".join(fields) + " WHERE id = ?"
        with self._lock:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return bool(cur.rowcount or 0)


storage = SQLiteMetricsStorage(settings.metrics_db_path)


async def init_storage() -> None:
    if not storage.enabled:
        return
    await asyncio.to_thread(storage.init)


async def persist_sample(sample: SystemSample) -> None:
    if not storage.enabled:
        return
    await asyncio.to_thread(storage.insert_sample, sample)


async def get_latest() -> Optional[SystemSample]:
    if not storage.enabled:
        return None
    return await asyncio.to_thread(storage.query_latest)


async def get_history(seconds: int) -> list[SystemSample]:
    if not storage.enabled:
        return []
    return await asyncio.to_thread(storage.query_history, seconds)


async def prune_old() -> int:
    if not storage.enabled:
        return 0
    return await asyncio.to_thread(storage.prune_old)


async def get_stats() -> dict:
    return await asyncio.to_thread(storage.stats)


async def vacuum() -> None:
    if not storage.enabled:
        return
    await asyncio.to_thread(storage.vacuum)


async def get_hosts(active_only: bool = True) -> list[Host]:
    if not storage.enabled:
        return []
    return await asyncio.to_thread(storage.list_hosts, bool(active_only))


async def create_host(host_in: HostCreate) -> Host:
    if not storage.enabled:
        raise RuntimeError("Host storage is disabled (metrics DB path not set)")
    return await asyncio.to_thread(storage.create_host, host_in)


async def deactivate_host(host_id: int) -> bool:
    if not storage.enabled:
        return False
    return await asyncio.to_thread(storage.deactivate_host, int(host_id))


async def update_host(
    host_id: int,
    *,
    name: str | None = None,
    address: str | None = None,
    htype: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> bool:
    if not storage.enabled:
        return False
    return await asyncio.to_thread(
        storage.update_host,
        int(host_id),
        name=name,
        address=address,
        htype=htype,
        tags=tags,
        notes=notes,
    )
