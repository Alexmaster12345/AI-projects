from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


_IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")


def _table_has_column(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r["name"]) == column for r in rows)


def _ensure_column(conn: sqlite3.Connection, *, table: str, column_def: str) -> None:
    # column_def example: "ips TEXT" or "agent_id TEXT"
    col = (column_def or "").strip().split()[0]
    if not col:
        return
    if _table_has_column(conn, table=table, column=col):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def _extract_ips(*, message: str, fields: Dict[str, Any]) -> List[str]:
    text_parts: List[str] = []
    if message:
        text_parts.append(str(message))
    for _, v in (fields or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float)):
            text_parts.append(str(v))
        elif isinstance(v, list):
            for item in v[:50]:
                if isinstance(item, (str, int, float)):
                    text_parts.append(str(item))
    blob = "\n".join(text_parts)
    ips = _IP_RE.findall(blob)
    uniq: List[str] = []
    seen = set()
    for ip in ips:
        if ip not in seen:
            uniq.append(ip)
            seen.add(ip)
        if len(uniq) >= 20:
            break
    return uniq


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                source TEXT NOT NULL,
                host TEXT,
                facility TEXT,
                severity TEXT,
                message TEXT NOT NULL,
                fields_json TEXT NOT NULL,
                ips TEXT,
                agent_id TEXT,

                -- Derived, normalized pivots (best-effort; may be NULL)
                log_type TEXT,
                event_category TEXT,
                event_action TEXT,
                event_outcome TEXT,
                user TEXT,
                src_ip TEXT,
                dst_ip TEXT,
                src_port INTEGER,
                dst_port INTEGER,
                http_method TEXT,
                http_path TEXT,
                http_status INTEGER,
                dns_qname TEXT,
                user_agent TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
            CREATE INDEX IF NOT EXISTS idx_events_host ON events(host);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                details_json TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
            CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id);

            -- EDR endpoints (agents)
            CREATE TABLE IF NOT EXISTS edr_endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL UNIQUE,
                host TEXT,
                os TEXT,
                ip TEXT,
                version TEXT,
                tags_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_edr_endpoints_agent_id ON edr_endpoints(agent_id);
            CREATE INDEX IF NOT EXISTS idx_edr_endpoints_host ON edr_endpoints(host);
            CREATE INDEX IF NOT EXISTS idx_edr_endpoints_last_seen ON edr_endpoints(last_seen_at);

            -- EDR response actions queue
            CREATE TABLE IF NOT EXISTS edr_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                action_type TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_by TEXT,
                acknowledged_at TEXT,
                completed_at TEXT,
                result_json TEXT NOT NULL,
                FOREIGN KEY(agent_id) REFERENCES edr_endpoints(agent_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_edr_actions_agent_id ON edr_actions(agent_id);
            CREATE INDEX IF NOT EXISTS idx_edr_actions_status ON edr_actions(status);
            CREATE INDEX IF NOT EXISTS idx_edr_actions_created_at ON edr_actions(created_at);

            -- Threat intelligence: Indicators of Compromise (IOCs)
            CREATE TABLE IF NOT EXISTS iocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT,
                note TEXT,
                added_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS ux_iocs_type_value ON iocs(type, value);
            CREATE INDEX IF NOT EXISTS idx_iocs_value ON iocs(value);

            -- Managed Detection & Response (MDR)
            CREATE TABLE IF NOT EXISTS mdr_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                alert_id INTEGER,
                event_id INTEGER,
                assigned_to TEXT,
                tags_json TEXT NOT NULL,
                FOREIGN KEY(alert_id) REFERENCES alerts(id) ON DELETE SET NULL,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mdr_incidents_created_at ON mdr_incidents(created_at);
            CREATE INDEX IF NOT EXISTS idx_mdr_incidents_status ON mdr_incidents(status);
            CREATE INDEX IF NOT EXISTS idx_mdr_incidents_severity ON mdr_incidents(severity);
            CREATE INDEX IF NOT EXISTS idx_mdr_incidents_assigned_to ON mdr_incidents(assigned_to);
            CREATE INDEX IF NOT EXISTS idx_mdr_incidents_alert_id ON mdr_incidents(alert_id);

            CREATE TABLE IF NOT EXISTS mdr_incident_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                author TEXT,
                note TEXT NOT NULL,
                FOREIGN KEY(incident_id) REFERENCES mdr_incidents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_mdr_incident_notes_incident_id ON mdr_incident_notes(incident_id);
            CREATE INDEX IF NOT EXISTS idx_mdr_incident_notes_created_at ON mdr_incident_notes(created_at);
            """
        )

        # Backwards-compatible migration for older DBs.
        # (SQLite doesn't support ADD COLUMN IF NOT EXISTS.)
        _ensure_column(conn, table="events", column_def="ips TEXT")
        _ensure_column(conn, table="events", column_def="agent_id TEXT")
        _ensure_column(conn, table="events", column_def="log_type TEXT")
        _ensure_column(conn, table="events", column_def="event_category TEXT")
        _ensure_column(conn, table="events", column_def="event_action TEXT")
        _ensure_column(conn, table="events", column_def="event_outcome TEXT")
        _ensure_column(conn, table="events", column_def="user TEXT")
        _ensure_column(conn, table="events", column_def="src_ip TEXT")
        _ensure_column(conn, table="events", column_def="dst_ip TEXT")
        _ensure_column(conn, table="events", column_def="src_port INTEGER")
        _ensure_column(conn, table="events", column_def="dst_port INTEGER")
        _ensure_column(conn, table="events", column_def="http_method TEXT")
        _ensure_column(conn, table="events", column_def="http_path TEXT")
        _ensure_column(conn, table="events", column_def="http_status INTEGER")
        _ensure_column(conn, table="events", column_def="dns_qname TEXT")
        _ensure_column(conn, table="events", column_def="user_agent TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ips ON events(ips)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_src_ip ON events(src_ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_dst_ip ON events(dst_ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_dst_port ON events(dst_port)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_http_status ON events(http_status)")

        _init_events_fts(conn)


def upsert_ioc(
    db_path: Path,
    *,
    ioc_type: str,
    value: str,
    source: Optional[str],
    note: Optional[str],
    now: datetime,
) -> int:
    t = (ioc_type or "").strip().lower()
    v = (value or "").strip()
    if not t or not v:
        raise ValueError("ioc_type and value are required")

    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM iocs WHERE type = ? AND value = ?",
            (t, v),
        ).fetchone()
        if row is not None:
            return int(row["id"])

        cur = conn.execute(
            """
            INSERT INTO iocs(type, value, source, note, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (t, v, source, note, now.isoformat()),
        )
        return int(cur.lastrowid)


def list_iocs(db_path: Path, *, limit: int = 500) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, type, value, source, note, added_at
            FROM iocs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "type": r["type"],
                "value": r["value"],
                "source": r["source"],
                "note": r["note"],
                "added_at": r["added_at"],
            }
        )
    return out


def delete_ioc(db_path: Path, *, ioc_id: int) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM iocs WHERE id = ?", (ioc_id,))
        return cur.rowcount == 1


def find_ioc_matches(
    db_path: Path,
    *,
    candidates: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """Return matched IOCs.

    candidates: {"ip": [..], "domain": [..], "sha256": [..]}
    """
    hits: List[Dict[str, Any]] = []
    with _connect(db_path) as conn:
        for t, values in (candidates or {}).items():
            if not values:
                continue
            uniq = sorted({v.strip() for v in values if v and v.strip()})[:200]
            if not uniq:
                continue
            qs = ",".join(["?"] * len(uniq))
            rows = conn.execute(
                f"SELECT id, type, value, source, note, added_at FROM iocs WHERE type = ? AND value IN ({qs})",
                (t, *uniq),
            ).fetchall()
            for r in rows:
                hits.append(
                    {
                        "id": r["id"],
                        "type": r["type"],
                        "value": r["value"],
                        "source": r["source"],
                        "note": r["note"],
                        "added_at": r["added_at"],
                    }
                )
    return hits


def _init_events_fts(conn: sqlite3.Connection) -> None:
    """Best-effort FTS5 index for events search.

    If FTS5 isn't available in the SQLite build, this becomes a no-op.
    """
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_fts' LIMIT 1"
        ).fetchone()
        if exists:
            return

        conn.execute(
            """
            CREATE VIRTUAL TABLE events_fts USING fts5(
                message,
                host,
                source,
                content='events',
                content_rowid='id'
            );
            """
        )

        conn.executescript(
            """
            CREATE TRIGGER events_ai AFTER INSERT ON events BEGIN
                INSERT INTO events_fts(rowid, message, host, source)
                VALUES (new.id, new.message, new.host, new.source);
            END;

            CREATE TRIGGER events_ad AFTER DELETE ON events BEGIN
                INSERT INTO events_fts(events_fts, rowid, message, host, source)
                VALUES('delete', old.id, old.message, old.host, old.source);
            END;

            CREATE TRIGGER events_au AFTER UPDATE ON events BEGIN
                INSERT INTO events_fts(events_fts, rowid, message, host, source)
                VALUES('delete', old.id, old.message, old.host, old.source);
                INSERT INTO events_fts(rowid, message, host, source)
                VALUES (new.id, new.message, new.host, new.source);
            END;
            """
        )

        # Populate FTS from existing content.
        conn.execute("INSERT INTO events_fts(events_fts) VALUES('rebuild')")
    except sqlite3.OperationalError:
        # Likely: "no such module: fts5". Keep LIKE-search as fallback.
        return


def upsert_edr_endpoint(
    db_path: Path,
    *,
    agent_id: str,
    host: Optional[str],
    os: Optional[str],
    ip: Optional[str],
    version: Optional[str],
    tags: Dict[str, Any],
    now: datetime,
) -> int:
    """Create or update an EDR endpoint record.

    Returns the numeric endpoint id.
    """
    tags_json = json.dumps(tags or {}, ensure_ascii=False)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM edr_endpoints WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()

        if row is None:
            cur = conn.execute(
                """
                INSERT INTO edr_endpoints (
                    agent_id, host, os, ip, version, tags_json, registered_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    host,
                    os,
                    ip,
                    version,
                    tags_json,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            return int(cur.lastrowid)

        endpoint_id = int(row["id"])
        conn.execute(
            """
            UPDATE edr_endpoints
            SET host = COALESCE(?, host),
                os = COALESCE(?, os),
                ip = COALESCE(?, ip),
                version = COALESCE(?, version),
                tags_json = ?,
                last_seen_at = ?
            WHERE agent_id = ?
            """,
            (
                host,
                os,
                ip,
                version,
                tags_json,
                now.isoformat(),
                agent_id,
            ),
        )
        return endpoint_id


def touch_edr_endpoint(db_path: Path, *, agent_id: str, now: datetime) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE edr_endpoints SET last_seen_at = ? WHERE agent_id = ?",
            (now.isoformat(), agent_id),
        )


def list_edr_endpoints(db_path: Path, *, limit: int = 100) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, agent_id, host, os, ip, version, tags_json, registered_at, last_seen_at
            FROM edr_endpoints
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "host": row["host"],
                "os": row["os"],
                "ip": row["ip"],
                "version": row["version"],
                "tags": json.loads(row["tags_json"] or "{}"),
                "registered_at": row["registered_at"],
                "last_seen_at": row["last_seen_at"],
            }
        )
    return results


def create_edr_action(
    db_path: Path,
    *,
    agent_id: str,
    action_type: str,
    params: Dict[str, Any],
    requested_by: Optional[str],
    now: datetime,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO edr_actions (
                agent_id, created_at, action_type, params_json, status, requested_by,
                acknowledged_at, completed_at, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                agent_id,
                now.isoformat(),
                action_type,
                json.dumps(params or {}, ensure_ascii=False),
                "pending",
                requested_by,
                json.dumps({}, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def list_pending_edr_actions(db_path: Path, *, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, agent_id, created_at, action_type, params_json, status, requested_by,
                   acknowledged_at, completed_at, result_json
            FROM edr_actions
            WHERE agent_id = ? AND status = 'pending'
            ORDER BY id ASC
            LIMIT ?
            """,
            (agent_id, limit),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "created_at": row["created_at"],
                "action_type": row["action_type"],
                "params": json.loads(row["params_json"] or "{}"),
                "status": row["status"],
                "requested_by": row["requested_by"],
                "acknowledged_at": row["acknowledged_at"],
                "completed_at": row["completed_at"],
                "result": json.loads(row["result_json"] or "{}"),
            }
        )
    return results


def list_edr_actions(
    db_path: Path,
    *,
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    args: List[Any] = []

    if agent_id is not None:
        where.append("agent_id = ?")
        args.append(agent_id)

    if status is not None:
        where.append("status = ?")
        args.append(status)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with _connect(db_path) as conn:
        rows = conn.execute(
            (
                """
                SELECT id, agent_id, created_at, action_type, params_json, status, requested_by,
                       acknowledged_at, completed_at, result_json
                FROM edr_actions
                """
                + where_sql
                + " ORDER BY id DESC LIMIT ?"
            ),
            (*args, limit),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "created_at": row["created_at"],
                "action_type": row["action_type"],
                "params": json.loads(row["params_json"] or "{}"),
                "status": row["status"],
                "requested_by": row["requested_by"],
                "acknowledged_at": row["acknowledged_at"],
                "completed_at": row["completed_at"],
                "result": json.loads(row["result_json"] or "{}"),
            }
        )
    return results


def ack_edr_action(db_path: Path, *, action_id: int, agent_id: str, now: datetime) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE edr_actions
            SET status = 'acknowledged', acknowledged_at = ?
            WHERE id = ? AND agent_id = ? AND status = 'pending'
            """,
            (now.isoformat(), action_id, agent_id),
        )
        return cur.rowcount == 1


def complete_edr_action(
    db_path: Path,
    *,
    action_id: int,
    agent_id: str,
    ok: bool,
    result: Dict[str, Any],
    now: datetime,
) -> bool:
    status = "completed" if ok else "failed"
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE edr_actions
            SET status = ?, completed_at = ?, result_json = ?
            WHERE id = ? AND agent_id = ? AND status IN ('pending', 'acknowledged')
            """,
            (
                status,
                now.isoformat(),
                json.dumps(result or {}, ensure_ascii=False),
                action_id,
                agent_id,
            ),
        )
        return cur.rowcount == 1


def insert_event(
    db_path: Path,
    *,
    ts: datetime,
    source: str,
    host: Optional[str],
    facility: Optional[str],
    severity: Optional[str],
    message: str,
    fields: Dict[str, Any],
) -> int:
    def _get_any(*keys: str) -> Optional[Any]:
        for k in keys:
            if not k:
                continue
            if isinstance(fields, dict) and k in fields:
                return fields.get(k)
        return None

    def _as_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        try:
            s = str(v).strip()
            if not s:
                return None
            return int(s)
        except Exception:
            return None

    def _as_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        try:
            s = str(v).strip()
        except Exception:
            return None
        return s if s else None

    agent_id = None
    try:
        if isinstance(fields, dict) and fields.get("agent_id") is not None:
            agent_id = str(fields.get("agent_id")).strip() or None
    except Exception:
        agent_id = None

    try:
        ips = _extract_ips(message=message, fields=fields)
        ips_text = ",".join(ips) if ips else None
    except Exception:
        ips_text = None

    with _connect(db_path) as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO events (ts, source, host, facility, severity, message, fields_json, ips, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts.isoformat(),
                    source,
                    host,
                    facility,
                    severity,
                    message,
                    json.dumps(fields, ensure_ascii=False),
                    ips_text,
                    agent_id,
                ),
            )
            event_id = int(cur.lastrowid)
        except sqlite3.OperationalError:
            # Fallback for very old schemas if init_db wasn't called.
            cur = conn.execute(
                """
                INSERT INTO events (ts, source, host, facility, severity, message, fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts.isoformat(),
                    source,
                    host,
                    facility,
                    severity,
                    message,
                    json.dumps(fields, ensure_ascii=False),
                ),
            )
            event_id = int(cur.lastrowid)

        # Best-effort: populate derived columns for correlation.
        try:
            log_type = _as_str(_get_any("log_type", "event.dataset", "dataset"))
            event_category = _as_str(_get_any("event_category"))
            event_action = _as_str(_get_any("event_action"))
            event_outcome = _as_str(_get_any("event_outcome"))
            user = _as_str(_get_any("user"))
            src_ip = _as_str(_get_any("src_ip"))
            dst_ip = _as_str(_get_any("dst_ip"))
            src_port = _as_int(_get_any("src_port"))
            dst_port = _as_int(_get_any("dst_port"))
            http_method = _as_str(_get_any("http_method"))
            http_path = _as_str(_get_any("http_path"))
            http_status = _as_int(_get_any("http_status"))
            dns_qname = _as_str(_get_any("dns_qname"))
            user_agent = _as_str(_get_any("user_agent"))

            conn.execute(
                """
                UPDATE events
                SET log_type = ?, event_category = ?, event_action = ?, event_outcome = ?,
                    user = ?, src_ip = ?, dst_ip = ?, src_port = ?, dst_port = ?,
                    http_method = ?, http_path = ?, http_status = ?, dns_qname = ?, user_agent = ?
                WHERE id = ?
                """,
                (
                    log_type,
                    event_category,
                    event_action,
                    event_outcome,
                    user,
                    src_ip,
                    dst_ip,
                    src_port,
                    dst_port,
                    http_method,
                    http_path,
                    http_status,
                    dns_qname,
                    user_agent,
                    event_id,
                ),
            )
        except Exception:
            pass

        return event_id


def insert_alert(
    db_path: Path,
    *,
    ts: datetime,
    rule_id: str,
    title: str,
    severity: str,
    event_id: int,
    details: Dict[str, Any],
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO alerts (ts, rule_id, title, severity, event_id, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ts.isoformat(),
                rule_id,
                title,
                severity,
                event_id,
                json.dumps(details, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def alert_exists_for_event_rule(db_path: Path, *, event_id: int, rule_id: str) -> bool:
    rid = (rule_id or "").strip()
    if not rid:
        return False
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM alerts
            WHERE event_id = ? AND rule_id = ?
            LIMIT 1
            """,
            (event_id, rid),
        ).fetchone()
        return row is not None


def count_recent_sshd_failed_password(
    db_path: Path,
    *,
    since_ts: str,
    src_ip: str,
    host: Optional[str] = None,
) -> int:
    ip = (src_ip or "").strip()
    if not ip:
        return 0

    where = ["ts >= ?", "message LIKE '%Failed password%'"]
    args: List[Any] = [since_ts]

    # Prefer normalized field if present, but keep a message fallback.
    where.append("(fields_json LIKE '%\"event_outcome\": \"failure\"%')")

    where.append("ips LIKE ?")
    args.append(f"%{ip}%")

    if host:
        where.append("host = ?")
        args.append(host)

    sql = "SELECT COUNT(1) AS n FROM events WHERE " + " AND ".join(where)
    with _connect(db_path) as conn:
        row = conn.execute(sql, tuple(args)).fetchone()
        return int(row["n"]) if row else 0


def alert_exists_recent(
    db_path: Path,
    *,
    since_ts: str,
    rule_id: str,
    key: Optional[str] = None,
    value: Optional[str] = None,
) -> bool:
    rid = (rule_id or "").strip()
    if not rid:
        return False

    where = ["ts >= ?", "rule_id = ?"]
    args: List[Any] = [since_ts, rid]

    if key and value:
        # details_json stores arbitrary JSON; do a simple substring match.
        where.append("details_json LIKE ?")
        args.append(f"%\"{key}\": %\"{value}%")

    sql = "SELECT 1 FROM alerts WHERE " + " AND ".join(where) + " LIMIT 1"
    with _connect(db_path) as conn:
        row = conn.execute(sql, tuple(args)).fetchone()
        return row is not None


def count_recent_auth_failures(
    db_path: Path,
    *,
    since_ts: str,
    src_ip: Optional[str] = None,
    user: Optional[str] = None,
    host: Optional[str] = None,
    service: Optional[str] = None,
) -> int:
    where: List[str] = ["ts >= ?", "event_category = 'authentication'", "event_outcome = 'failure'"]
    args: List[Any] = [since_ts]

    if src_ip:
        where.append("src_ip = ?")
        args.append(src_ip)
    if user:
        where.append("user = ?")
        args.append(user)
    if host:
        where.append("host = ?")
        args.append(host)
    if service:
        where.append("fields_json LIKE ?")
        args.append(f"%\"auth.service\": \"{service}%")

    sql = "SELECT COUNT(1) AS n FROM events WHERE " + " AND ".join(where)
    with _connect(db_path) as conn:
        try:
            row = conn.execute(sql, tuple(args)).fetchone()
            return int(row["n"]) if row else 0
        except sqlite3.OperationalError:
            # Older schema fallback
            where2 = ["ts >= ?", "fields_json LIKE '%\"event_category\": \"authentication\"%'"]
            where2.append("fields_json LIKE '%\"event_outcome\": \"failure\"%'")
            args2: List[Any] = [since_ts]
            if src_ip:
                where2.append("ips LIKE ?")
                args2.append(f"%{src_ip}%")
            if user:
                where2.append("fields_json LIKE ?")
                args2.append(f"%\"user\": \"{user}%")
            if host:
                where2.append("host = ?")
                args2.append(host)
            if service:
                where2.append("fields_json LIKE ?")
                args2.append(f"%\"auth.service\": \"{service}%")
            sql2 = "SELECT COUNT(1) AS n FROM events WHERE " + " AND ".join(where2)
            row = conn.execute(sql2, tuple(args2)).fetchone()
            return int(row["n"]) if row else 0


def count_distinct_users_auth_failures(
    db_path: Path,
    *,
    since_ts: str,
    src_ip: str,
    host: Optional[str] = None,
) -> int:
    ip = (src_ip or "").strip()
    if not ip:
        return 0
    where: List[str] = ["ts >= ?", "event_category = 'authentication'", "event_outcome = 'failure'", "src_ip = ?", "user IS NOT NULL", "user <> ''"]
    args: List[Any] = [since_ts, ip]
    if host:
        where.append("host = ?")
        args.append(host)
    sql = "SELECT COUNT(DISTINCT user) AS n FROM events WHERE " + " AND ".join(where)
    with _connect(db_path) as conn:
        try:
            row = conn.execute(sql, tuple(args)).fetchone()
            return int(row["n"]) if row else 0
        except sqlite3.OperationalError:
            return 0


def list_recent_auth_success_ips_for_user(
    db_path: Path,
    *,
    since_ts: str,
    user: str,
    limit: int = 10,
) -> List[str]:
    u = (user or "").strip()
    if not u:
        return []
    sql = (
        "SELECT DISTINCT src_ip FROM events "
        "WHERE ts >= ? AND event_category = 'authentication' AND event_outcome = 'success' AND user = ? "
        "AND src_ip IS NOT NULL AND src_ip <> '' ORDER BY ts DESC LIMIT ?"
    )
    with _connect(db_path) as conn:
        try:
            rows = conn.execute(sql, (since_ts, u, limit)).fetchall()
            return [str(r["src_ip"]) for r in rows if r and r["src_ip"]]
        except sqlite3.OperationalError:
            return []


def count_distinct_dst_ports(
    db_path: Path,
    *,
    since_ts: str,
    src_ip: str,
    host: Optional[str] = None,
    dst_ip: Optional[str] = None,
) -> int:
    ip = (src_ip or "").strip()
    if not ip:
        return 0
    where: List[str] = ["ts >= ?", "src_ip = ?", "dst_port IS NOT NULL"]
    args: List[Any] = [since_ts, ip]
    if host:
        where.append("host = ?")
        args.append(host)
    if dst_ip:
        where.append("dst_ip = ?")
        args.append(dst_ip)
    sql = "SELECT COUNT(DISTINCT dst_port) AS n FROM events WHERE " + " AND ".join(where)
    with _connect(db_path) as conn:
        try:
            row = conn.execute(sql, tuple(args)).fetchone()
            return int(row["n"]) if row else 0
        except sqlite3.OperationalError:
            return 0


def count_recent_http_status(
    db_path: Path,
    *,
    since_ts: str,
    src_ip: str,
    status: int,
    host: Optional[str] = None,
) -> int:
    ip = (src_ip or "").strip()
    if not ip:
        return 0
    where: List[str] = ["ts >= ?", "src_ip = ?", "http_status = ?"]
    args: List[Any] = [since_ts, ip, int(status)]
    if host:
        where.append("host = ?")
        args.append(host)
    sql = "SELECT COUNT(1) AS n FROM events WHERE " + " AND ".join(where)
    with _connect(db_path) as conn:
        try:
            row = conn.execute(sql, tuple(args)).fetchone()
            return int(row["n"]) if row else 0
        except sqlite3.OperationalError:
            # Fallback: basic heuristic using message text.
            where2: List[str] = ["ts >= ?", "ips LIKE ?", "message LIKE ?"]
            args2: List[Any] = [since_ts, f"%{ip}%", f"% {int(status)} %"]
            if host:
                where2.append("host = ?")
                args2.append(host)
            sql2 = "SELECT COUNT(1) AS n FROM events WHERE " + " AND ".join(where2)
            row = conn.execute(sql2, tuple(args2)).fetchone()
            return int(row["n"]) if row else 0


def get_event(db_path: Path, *, event_id: int) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, ts, source, host, facility, severity, message, fields_json, ips, agent_id
            FROM events
            WHERE id = ?
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "ts": row["ts"],
            "source": row["source"],
            "host": row["host"],
            "facility": row["facility"],
            "severity": row["severity"],
            "message": row["message"],
            "fields": json.loads(row["fields_json"] or "{}"),
            "ips": row["ips"],
            "agent_id": row["agent_id"],
        }


def list_events_timeline(
    db_path: Path,
    *,
    start_ts: str,
    end_ts: str,
    host: Optional[str] = None,
    agent_id: Optional[str] = None,
    ip: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    where: List[str] = ["ts >= ?", "ts <= ?"]
    args: List[Any] = [start_ts, end_ts]

    if host:
        where.append("host = ?")
        args.append(host)

    if agent_id:
        where.append("agent_id = ?")
        args.append(agent_id)

    if ip:
        where.append("ips LIKE ?")
        args.append(f"%{ip}%")

    sql = (
        "SELECT id, ts, source, host, facility, severity, message, fields_json, ips, agent_id "
        "FROM events WHERE "
        + " AND ".join(where)
        + " ORDER BY ts ASC LIMIT ?"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (*args, limit)).fetchall()

    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "source": row["source"],
                "host": row["host"],
                "facility": row["facility"],
                "severity": row["severity"],
                "message": row["message"],
                "fields": json.loads(row["fields_json"] or "{}"),
                "ips": row["ips"],
                "agent_id": row["agent_id"],
            }
        )
    return out


def get_alert(db_path: Path, *, alert_id: int) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, ts, rule_id, title, severity, event_id, details_json
            FROM alerts
            WHERE id = ?
            LIMIT 1
            """,
            (alert_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "ts": row["ts"],
            "rule_id": row["rule_id"],
            "title": row["title"],
            "severity": row["severity"],
            "event_id": row["event_id"],
            "details": json.loads(row["details_json"] or "{}"),
        }


def create_mdr_incident(
    db_path: Path,
    *,
    created_at: datetime,
    status: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    alert_id: Optional[int] = None,
    event_id: Optional[int] = None,
    assigned_to: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> int:
    st = (status or "").strip().lower() or "open"
    sev = (severity or "").strip().lower() or "low"
    t = (title or "").strip()
    if not t:
        raise ValueError("title is required")

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO mdr_incidents (
                created_at, updated_at, closed_at, status, severity, title, description,
                alert_id, event_id, assigned_to, tags_json
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at.isoformat(),
                created_at.isoformat(),
                st,
                sev,
                t,
                description,
                alert_id,
                event_id,
                assigned_to,
                json.dumps(tags or {}, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def create_mdr_incident_from_alert(
    db_path: Path,
    *,
    alert_id: int,
    created_at: datetime,
    assigned_to: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> int:
    alert = get_alert(db_path, alert_id=alert_id)
    if alert is None:
        raise ValueError("unknown alert_id")
    return create_mdr_incident(
        db_path,
        created_at=created_at,
        status="open",
        severity=str(alert.get("severity") or "low"),
        title=str(alert.get("title") or f"Alert {alert_id}"),
        description=f"Created from alert_id={alert_id} (rule_id={alert.get('rule_id')})",
        alert_id=alert_id,
        event_id=int(alert.get("event_id") or 0) or None,
        assigned_to=assigned_to,
        tags=tags,
    )


def list_mdr_incidents(
    db_path: Path,
    *,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    where_sql = ""
    args: List[Any] = []
    if status is not None:
        where_sql = " WHERE status = ?"
        args.append((status or "").strip().lower())

    with _connect(db_path) as conn:
        rows = conn.execute(
            (
                """
                SELECT i.id, i.created_at, i.updated_at, i.closed_at, i.status, i.severity,
                       i.title, i.description, i.alert_id, i.event_id, i.assigned_to, i.tags_json,
                       COALESCE(n.n, 0) AS note_count
                FROM mdr_incidents i
                LEFT JOIN (
                    SELECT incident_id, COUNT(1) AS n
                    FROM mdr_incident_notes
                    GROUP BY incident_id
                ) n ON n.incident_id = i.id
                """
                + where_sql
                + " ORDER BY i.id DESC LIMIT ?"
            ),
            (*args, limit),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "closed_at": r["closed_at"],
                "status": r["status"],
                "severity": r["severity"],
                "title": r["title"],
                "description": r["description"],
                "alert_id": r["alert_id"],
                "event_id": r["event_id"],
                "assigned_to": r["assigned_to"],
                "tags": json.loads(r["tags_json"] or "{}"),
                "note_count": int(r["note_count"]),
            }
        )
    return out


def get_mdr_incident(db_path: Path, *, incident_id: int) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        r = conn.execute(
            """
            SELECT id, created_at, updated_at, closed_at, status, severity,
                   title, description, alert_id, event_id, assigned_to, tags_json
            FROM mdr_incidents
            WHERE id = ?
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        if r is None:
            return None

        notes = conn.execute(
            """
            SELECT id, incident_id, created_at, author, note
            FROM mdr_incident_notes
            WHERE incident_id = ?
            ORDER BY id ASC
            LIMIT 500
            """,
            (incident_id,),
        ).fetchall()

    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "closed_at": r["closed_at"],
        "status": r["status"],
        "severity": r["severity"],
        "title": r["title"],
        "description": r["description"],
        "alert_id": r["alert_id"],
        "event_id": r["event_id"],
        "assigned_to": r["assigned_to"],
        "tags": json.loads(r["tags_json"] or "{}"),
        "notes": [
            {
                "id": n["id"],
                "incident_id": n["incident_id"],
                "created_at": n["created_at"],
                "author": n["author"],
                "note": n["note"],
            }
            for n in notes
        ],
    }


def update_mdr_incident(
    db_path: Path,
    *,
    incident_id: int,
    now: datetime,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    severity: Optional[str] = None,
) -> bool:
    fields: List[str] = []
    args: List[Any] = []

    if status is not None:
        fields.append("status = ?")
        args.append((status or "").strip().lower())
        if (status or "").strip().lower() in {"closed", "resolved"}:
            fields.append("closed_at = ?")
            args.append(now.isoformat())
        else:
            fields.append("closed_at = NULL")

    if assigned_to is not None:
        fields.append("assigned_to = ?")
        args.append((assigned_to or "").strip() or None)

    if severity is not None:
        fields.append("severity = ?")
        args.append((severity or "").strip().lower() or "low")

    if not fields:
        return False

    fields.append("updated_at = ?")
    args.append(now.isoformat())
    args.append(incident_id)

    with _connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE mdr_incidents SET {', '.join(fields)} WHERE id = ?",
            tuple(args),
        )
        return cur.rowcount == 1


def add_mdr_incident_note(
    db_path: Path,
    *,
    incident_id: int,
    created_at: datetime,
    author: Optional[str],
    note: str,
) -> int:
    n = (note or "").strip()
    if not n:
        raise ValueError("note is required")

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO mdr_incident_notes (incident_id, created_at, author, note)
            VALUES (?, ?, ?, ?)
            """,
            (incident_id, created_at.isoformat(), author, n),
        )
        conn.execute(
            "UPDATE mdr_incidents SET updated_at = ? WHERE id = ?",
            (created_at.isoformat(), incident_id),
        )
        return int(cur.lastrowid)


def list_events(
    db_path: Path,
    *,
    limit: int = 100,
    agent_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    args: List[Any] = []

    if agent_id is not None:
        where.append("agent_id = ?")
        args.append((agent_id or "").strip())

    if ip is not None:
        needle = (ip or "").strip()
        if needle:
            where.append("ips LIKE ?")
            args.append(f"%{needle}%")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with _connect(db_path) as conn:
        rows = conn.execute(
            (
                """
                SELECT id, ts, source, host, facility, severity, message, fields_json, ips, agent_id
                FROM events
                """
                + where_sql
                + " ORDER BY id DESC LIMIT ?"
            ),
            (*args, limit),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "source": row["source"],
                "host": row["host"],
                "facility": row["facility"],
                "severity": row["severity"],
                "message": row["message"],
                "fields": json.loads(row["fields_json"]),
                "ips": row["ips"],
                "agent_id": row["agent_id"],
            }
        )
    return results


def search_events(
    db_path: Path,
    *,
    q: str,
    limit: int = 100,
    agent_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        has_fts = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_fts' LIMIT 1"
        ).fetchone()

        where: List[str] = []
        args: List[Any] = []

        if agent_id is not None:
            where.append("e.agent_id = ?")
            args.append((agent_id or "").strip())

        if ip is not None:
            needle = (ip or "").strip()
            if needle:
                where.append("e.ips LIKE ?")
                args.append(f"%{needle}%")

        where_sql = (" AND " + " AND ".join(where)) if where else ""

        if has_fts:
            # Convert user input into a conservative FTS query.
            # Example: "failed password 10.0.0.5" -> "failed AND password AND 10.0.0.5"
            tokens = re.findall(r"[A-Za-z0-9_.:@/-]+", q or "")
            if tokens:
                fts_q = " AND ".join(tokens[:12])
                try:
                    rows = conn.execute(
                        """
                        SELECT e.id, e.ts, e.source, e.host, e.facility, e.severity, e.message, e.fields_json, e.ips, e.agent_id
                        FROM events e
                        JOIN events_fts fts ON fts.rowid = e.id
                        WHERE fts MATCH ?
                        """
                        + where_sql
                        + """
                        ORDER BY e.id DESC
                        LIMIT ?
                        """,
                        (fts_q, *args, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = []
        else:
            rows = []

        if not rows:
            # Fallback: LIKE search over message/host/source.
            needle = f"%{q}%"
            where2: List[str] = []
            args2: List[Any] = []
            if agent_id is not None:
                where2.append("agent_id = ?")
                args2.append((agent_id or "").strip())
            if ip is not None:
                ip_needle = (ip or "").strip()
                if ip_needle:
                    where2.append("ips LIKE ?")
                    args2.append(f"%{ip_needle}%")
            where2_sql = (" AND " + " AND ".join(where2)) if where2 else ""

            rows = conn.execute(
                """
                SELECT id, ts, source, host, facility, severity, message, fields_json, ips, agent_id
                FROM events
                WHERE message LIKE ? OR host LIKE ? OR source LIKE ? OR ips LIKE ? OR agent_id LIKE ?
                """
                + where2_sql
                + """
                ORDER BY id DESC
                LIMIT ?
                """,
                (needle, needle, needle, needle, needle, *args2, limit),
            ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "source": row["source"],
                "host": row["host"],
                "facility": row["facility"],
                "severity": row["severity"],
                "message": row["message"],
                "fields": json.loads(row["fields_json"]),
                "ips": row["ips"],
                "agent_id": row["agent_id"],
            }
        )
    return results


def list_alerts(
    db_path: Path,
    *,
    limit: int = 100,
    agent_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    args: List[Any] = []

    if agent_id is not None:
        where.append("e.agent_id = ?")
        args.append((agent_id or "").strip())

    if ip is not None:
        needle = (ip or "").strip()
        if needle:
            where.append("e.ips LIKE ?")
            args.append(f"%{needle}%")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with _connect(db_path) as conn:
        rows = conn.execute(
            (
                """
                SELECT a.id, a.ts, a.rule_id, a.title, a.severity, a.event_id, a.details_json,
                       e.source AS event_source, e.host AS event_host, e.ips AS event_ips, e.agent_id AS event_agent_id
                FROM alerts a
                JOIN events e ON e.id = a.event_id
                """
                + where_sql
                + " ORDER BY a.id DESC LIMIT ?"
            ),
            (*args, limit),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "rule_id": row["rule_id"],
                "title": row["title"],
                "severity": row["severity"],
                "event_id": row["event_id"],
                "details": json.loads(row["details_json"]),
                "event_source": row["event_source"],
                "event_host": row["event_host"],
                "event_ips": row["event_ips"],
                "event_agent_id": row["event_agent_id"],
            }
        )
    return results


def db_health(db_path: Path) -> Dict[str, Any]:
    """Lightweight DB check used by /health."""
    try:
        with _connect(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
            row = conn.execute("SELECT COUNT(1) AS n FROM events").fetchone()
            events_count = int(row["n"]) if row else 0
            row2 = conn.execute("SELECT COUNT(1) AS n FROM alerts").fetchone()
            alerts_count = int(row2["n"]) if row2 else 0
            has_fts = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_fts' LIMIT 1"
                ).fetchone()
            )
        return {"ok": True, "events": events_count, "alerts": alerts_count, "fts": has_fts}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def risk_summary(
    db_path: Path,
    *,
    since_ts: str,
    limit: int = 5000,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Compute a lightweight risk score summary from recent alerts.

    Score is a simple weighted sum by severity (MVP):
      critical=10, high=6, medium=3, low=1, other=1

    Returns top-N ranked hosts, agents, and IPs.
    """

    sev_w = {"critical": 10, "high": 6, "medium": 3, "low": 1}

    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.ts, a.severity,
                   e.host AS event_host,
                   e.agent_id AS event_agent_id,
                   e.ips AS event_ips
            FROM alerts a
            JOIN events e ON e.id = a.event_id
            WHERE a.ts >= ?
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (since_ts, int(limit)),
        ).fetchall()

    def bump(m: Dict[str, Dict[str, Any]], key: str, sev: str) -> None:
        if not key:
            return
        s = (sev or "").strip().lower()
        w = int(sev_w.get(s, 1))
        cur = m.get(key)
        if cur is None:
            m[key] = {"key": key, "score": w, "alerts": 1, "severity_max": s or "other"}
            return
        cur["score"] = int(cur.get("score") or 0) + w
        cur["alerts"] = int(cur.get("alerts") or 0) + 1
        # Keep max severity label by weight.
        cur_max = str(cur.get("severity_max") or "other")
        if int(sev_w.get(s, 1)) > int(sev_w.get(cur_max, 1)):
            cur["severity_max"] = s

    by_host: Dict[str, Dict[str, Any]] = {}
    by_agent: Dict[str, Dict[str, Any]] = {}
    by_ip: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        sev = str(r["severity"] or "")
        host = str(r["event_host"] or "").strip()
        agent = str(r["event_agent_id"] or "").strip()
        ips_raw = str(r["event_ips"] or "").strip()

        if host:
            bump(by_host, host, sev)
        if agent:
            bump(by_agent, agent, sev)

        if ips_raw:
            for ip in [p.strip() for p in ips_raw.split(",") if p.strip()]:
                bump(by_ip, ip, sev)

    def top(m: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        items = list(m.values())
        items.sort(key=lambda x: (int(x.get("score") or 0), int(x.get("alerts") or 0)), reverse=True)
        return items[: int(top_n)]

    return {
        "ok": True,
        "since": since_ts,
        "weights": sev_w,
        "rows_scanned": len(rows),
        "top_hosts": top(by_host),
        "top_agents": top(by_agent),
        "top_ips": top(by_ip),
    }


def get_stats(db_path: Path, *, since_ts: str) -> Dict[str, Any]:
    """Aggregate stats for dashboarding / quick triage.

    since_ts should be an ISO timestamp string comparable to stored `ts`.
    """
    with _connect(db_path) as conn:
        ev_row = conn.execute(
            "SELECT COUNT(1) AS n FROM events WHERE ts >= ?",
            (since_ts,),
        ).fetchone()
        al_row = conn.execute(
            "SELECT COUNT(1) AS n FROM alerts WHERE ts >= ?",
            (since_ts,),
        ).fetchone()

        top_sources = conn.execute(
            """
            SELECT COALESCE(source, 'unknown') AS k, COUNT(1) AS n
            FROM events
            WHERE ts >= ?
            GROUP BY COALESCE(source, 'unknown')
            ORDER BY n DESC
            LIMIT 10
            """,
            (since_ts,),
        ).fetchall()

        alert_sev = conn.execute(
            """
            SELECT COALESCE(severity, 'unknown') AS k, COUNT(1) AS n
            FROM alerts
            WHERE ts >= ?
            GROUP BY COALESCE(severity, 'unknown')
            ORDER BY n DESC
            """,
            (since_ts,),
        ).fetchall()

    return {
        "since": since_ts,
        "events": int(ev_row["n"]) if ev_row else 0,
        "alerts": int(al_row["n"]) if al_row else 0,
        "top_sources": [{"source": r["k"], "count": int(r["n"])} for r in top_sources],
        "alert_severity": [{"severity": r["k"], "count": int(r["n"])} for r in alert_sev],
    }
