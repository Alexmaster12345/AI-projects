from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

import httpx


_SEVERITY_ORDER = {
    "low": 10,
    "medium": 20,
    "high": 30,
    "critical": 40,
}


def _sev_rank(sev: Optional[str]) -> int:
    return _SEVERITY_ORDER.get((sev or "").strip().lower(), 0)


def should_auto_create_incident_for_alert(*, severity: str) -> bool:
    enabled = (os.environ.get("MDR_AUTO_CREATE_INCIDENTS") or "").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return False

    min_sev = (os.environ.get("MDR_AUTO_CREATE_MIN_SEVERITY") or "medium").strip().lower()
    return _sev_rank(severity) >= _sev_rank(min_sev)


def send_mdr_webhook(*, event_type: str, payload: Dict[str, Any]) -> bool:
    url = (os.environ.get("MDR_WEBHOOK_URL") or "").strip()
    if not url:
        return False

    secret = (os.environ.get("MDR_WEBHOOK_SECRET") or "").encode("utf-8")
    body = json.dumps({"type": event_type, "payload": payload}, ensure_ascii=False).encode("utf-8")

    headers = {
        "content-type": "application/json",
        "x-siem-event": event_type,
    }

    if secret:
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
        headers["x-siem-signature"] = f"sha256={sig}"

    timeout = float((os.environ.get("MDR_WEBHOOK_TIMEOUT") or "1.5").strip() or 1.5)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, content=body, headers=headers)
            return 200 <= r.status_code < 300
    except Exception:
        return False
