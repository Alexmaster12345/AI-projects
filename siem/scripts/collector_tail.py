#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx


SYSLOG_RE = re.compile(
    r"^(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<proc>[^:]+):\s*(?P<msg>.*)$"
)


def _parse_syslog_line(line: str) -> Optional[Dict[str, Any]]:
    m = SYSLOG_RE.match(line)
    if not m:
        return None

    # Syslog timestamp lacks year/timezone; store as "now" and keep raw timestamp in fields.
    now = datetime.now(timezone.utc)
    return {
        "ts": now.isoformat(),
        "source": "syslog",
        "host": m.group("host"),
        "message": m.group("msg"),
        "fields": {
            "syslog_ts": m.group("ts"),
            "process": m.group("proc"),
        },
    }


def _parse_json_line(line: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(line)
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None

    # Normalize minimal fields
    obj.setdefault("ts", datetime.now(timezone.utc).isoformat())
    obj.setdefault("source", "json")
    if "message" not in obj:
        return None

    obj.setdefault("fields", {})
    if not isinstance(obj.get("fields"), dict):
        obj["fields"] = {"fields_raw": obj.get("fields")}

    return obj


def _tail(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.25)
                continue
            yield line.rstrip("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Tail a log file and send events to the SIEM ingest API.")
    ap.add_argument("--file", required=True, help="File to tail")
    ap.add_argument("--endpoint", default="http://VOLVIX.local:8000/ingest", help="Ingest endpoint")
    ap.add_argument("--source", default=None, help="Override source field (e.g., syslog, file, nginx, firewall)")
    ap.add_argument("--log-type", default=None, help="Tag fields.log_type (e.g., web, dns, firewall, windows_security)")
    ap.add_argument("--host", default=None, help="Override host field")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File does not exist: {path}")

    with httpx.Client(timeout=5.0) as client:
        for line in _tail(path):
            if not line.strip():
                continue

            event = _parse_json_line(line) or _parse_syslog_line(line)
            if event is None:
                event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "source": "file",
                    "host": args.host,
                    "message": line,
                    "fields": {},
                }

            if args.host:
                event["host"] = args.host

            if args.source:
                event["source"] = args.source

            if args.log_type:
                fields = event.get("fields")
                if not isinstance(fields, dict):
                    fields = {"fields_raw": fields}
                fields.setdefault("log_type", args.log_type)
                event["fields"] = fields

            try:
                resp = client.post(args.endpoint, json=event)
                resp.raise_for_status()
            except Exception as e:
                # Best-effort shipper; keep tailing.
                print(f"send failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
