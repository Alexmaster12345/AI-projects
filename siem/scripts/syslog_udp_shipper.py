#!/usr/bin/env python3

from __future__ import annotations

import argparse
import socket
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx


def _parse_syslog_line(line: str) -> Dict[str, Any]:
    # Keep parsing intentionally minimal; normalization will do deeper extraction.
    now = datetime.now(timezone.utc)
    return {
        "ts": now.isoformat(),
        "source": "syslog",
        "host": None,
        "message": line,
        "fields": {},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Listen on UDP syslog and forward to SIEM /ingest")
    ap.add_argument("--bind", default="0.0.0.0", help="Bind address")
    ap.add_argument("--port", type=int, default=5140, help="UDP port to listen on (default: 5140)")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8000/ingest", help="SIEM ingest endpoint")
    ap.add_argument("--host", default=None, help="Override host field")
    ap.add_argument("--log-type", default=None, help="Tag fields.log_type (e.g., firewall, dns, router_syslog)")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    with httpx.Client(timeout=5.0) as client:
        while True:
            data, addr = sock.recvfrom(65535)
            try:
                line = data.decode("utf-8", errors="replace").strip()
            except Exception:
                continue
            if not line:
                continue

            event = _parse_syslog_line(line)
            if args.host:
                event["host"] = args.host
            if args.log_type:
                event["fields"]["log_type"] = args.log_type
            # Preserve sender for context
            event["fields"]["sender"] = {"ip": addr[0], "port": addr[1]}

            try:
                resp = client.post(args.endpoint, json=event)
                resp.raise_for_status()
            except Exception as e:
                print(f"send failed: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
