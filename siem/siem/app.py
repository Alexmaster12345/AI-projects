from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import sqlite3
import uuid
import re
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import (
    AlertOut,
    EdrAckIn,
    EdrActionCreateIn,
    EdrActionCreateOut,
    EdrPollOut,
    EdrRegisterIn,
    EdrRegisterOut,
    EdrResultIn,
    IocCreateOut,
    IocIn,
    IocListOut,
    EdrTelemetryIn,
    EventIn,
    EventOut,
    MdrIncidentCreateIn,
    MdrIncidentCreateOut,
    MdrIncidentListOut,
    MdrIncidentNoteIn,
    MdrIncidentOut,
    MdrIncidentUpdateIn,
)
from .rules_engine import load_rules, match_rules
from .storage import (
    ack_edr_action,
    complete_edr_action,
    delete_ioc,
    find_ioc_matches,
    create_edr_action,
    init_db,
    insert_alert,
    insert_event,
    list_alerts,
    list_edr_actions,
    list_edr_endpoints,
    list_events,
    list_iocs,
    list_pending_edr_actions,
    search_events,
    touch_edr_endpoint,
    upsert_ioc,
    upsert_edr_endpoint,
    db_health,
    get_stats,
    add_mdr_incident_note,
    create_mdr_incident,
    create_mdr_incident_from_alert,
    get_mdr_incident,
    list_mdr_incidents,
    update_mdr_incident,
    alert_exists_for_event_rule,
    count_recent_sshd_failed_password,
    get_event,
    list_events_timeline,
    risk_summary,
    alert_exists_recent,
    count_recent_auth_failures,
    count_distinct_users_auth_failures,
    count_distinct_dst_ports,
    count_recent_http_status,
    list_recent_auth_success_ips_for_user,
)
from .web import render_index
from .soc_scanner import get_scan, read_scan_log_tail, start_scan
from .net_monitor import (
    get_session,
    list_interfaces,
    pcap_info,
    read_log_tail,
    start_capture,
    start_monitor,
    stop_monitor,
)
from .crypto_tools import compute_digests
from .mdr import send_mdr_webhook, should_auto_create_incident_for_alert
from .security import attach_security_middleware
from .mitre_attack import build_attack_catalog
from .normalize import normalize_event


APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / "data" / "siem.sqlite3"
RULES_PATH = APP_ROOT / "rules" / "default.yml"
MITRE_ATTACK_RAW_PATH = APP_ROOT / "rules" / "mitre_attack_raw.txt"
SCANS_DIR = APP_ROOT / "data" / "scans"
NET_LOGS_DIR = APP_ROOT / "data" / "net"

app = FastAPI(title="SIEM MVP", version="0.1.0")


# Optional security hardening controlled by env vars.
# - Auth is only enforced if SIEM_API_KEY or SIEM_BASIC_USER/SIEM_BASIC_PASS are set.
# - /health is exempt by default (configurable via SIEM_AUTH_EXEMPT_PATHS).
_trusted_hosts = (os.environ.get("SIEM_TRUSTED_HOSTS") or "").strip()
if _trusted_hosts and _trusted_hosts != "*":
    allowed_hosts = [h.strip() for h in _trusted_hosts.split(",") if h.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

_cors = (os.environ.get("SIEM_CORS_ALLOW_ORIGINS") or "").strip()
if _cors:
    allow_origins = [o.strip() for o in _cors.split(",") if o.strip()]
    if allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"] ,
        )

attach_security_middleware(app)


_DANGEROUS_EDR_ACTIONS = {
    "isolate_endpoint",
    "unisolate_endpoint",
    "block_ip",
    "unblock_ip",
}


def _dangerous_action_allowlist() -> List[str]:
    raw = (os.environ.get("EDR_DANGEROUS_ACTION_ALLOWLIST") or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _is_dangerous_action_allowed(*, requested_by: Optional[str]) -> bool:
    allow = _dangerous_action_allowlist()
    if not allow:
        return False
    if "*" in allow:
        return True
    actor = (requested_by or "").strip()
    if not actor:
        return False
    return actor in allow


_IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")
_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9-]{1,63}\.)+(?:[a-zA-Z]{2,63})\b")


def _run_correlation_detectors(
    *,
    event_id: int,
    ts: datetime,
    source: str,
    host: Optional[str],
    message: str,
    fields: Dict[str, Any],
) -> None:
    """Run lightweight correlation detectors that create alerts."""

    try:
        f = fields or {}
        category = str(f.get("event_category") or "").lower().strip()
        outcome = str(f.get("event_outcome") or "").lower().strip()
        action = str(f.get("event_action") or "").lower().strip()
        user = str(f.get("user") or "").strip() or None
        src_ip = str(f.get("src_ip") or "").strip()
        dst_ip = str(f.get("dst_ip") or "").strip() or None
        dst_port = f.get("dst_port")
        http_status = f.get("http_status")
    except Exception:
        category = ""
        outcome = ""
        action = ""
        user = None
        src_ip = ""
        dst_ip = None
        dst_port = None
        http_status = None

    if not src_ip:
        m = _IP_RE.search(message or "")
        src_ip = m.group(0) if m else ""

    # --- Anti-forensics: log clearing (immediate)
    if action == "log_cleared":
        rule_id = "corr_log_cleared"
        if not alert_exists_for_event_rule(DB_PATH, event_id=event_id, rule_id=rule_id):
            insert_alert(
                DB_PATH,
                ts=ts,
                rule_id=rule_id,
                title="Security logs were cleared",
                severity="high",
                event_id=event_id,
                details={
                    "host": host,
                    "user": user,
                    "src_ip": src_ip,
                    "mitre": {
                        "tactics": ["Defense Evasion"],
                        "techniques": ["Indicator Removal"],
                    },
                },
            )

    # --- Authentication correlation
    if category == "authentication" and src_ip:
        # Brute force: X failed logins in Y mins
        if outcome == "failure":
            rule_id = "corr_bruteforce"
            window_minutes = 10
            threshold = 10
            since = (ts - timedelta(minutes=window_minutes)).isoformat()

            if not alert_exists_recent(
                DB_PATH,
                since_ts=since,
                rule_id=rule_id,
                key="src_ip",
                value=src_ip,
            ):
                failures = count_recent_auth_failures(DB_PATH, since_ts=since, src_ip=src_ip, host=host)
                if failures >= threshold:
                    insert_alert(
                        DB_PATH,
                        ts=ts,
                        rule_id=rule_id,
                        title="Brute force suspected (failed logins spike)",
                        severity="high",
                        event_id=event_id,
                        details={
                            "src_ip": src_ip,
                            "host": host,
                            "window_minutes": window_minutes,
                            "failures": failures,
                            "threshold": threshold,
                            "mitre": {"tactics": ["Credential Access"], "techniques": ["Brute Force"]},
                        },
                    )

            # Password spray: many users from one IP
            rule_id = "corr_password_spray"
            window_minutes = 10
            user_threshold = 8
            since = (ts - timedelta(minutes=window_minutes)).isoformat()
            if not alert_exists_recent(
                DB_PATH,
                since_ts=since,
                rule_id=rule_id,
                key="src_ip",
                value=src_ip,
            ):
                distinct_users = count_distinct_users_auth_failures(DB_PATH, since_ts=since, src_ip=src_ip, host=host)
                if distinct_users >= user_threshold:
                    insert_alert(
                        DB_PATH,
                        ts=ts,
                        rule_id=rule_id,
                        title="Password spray suspected (many users failing from one IP)",
                        severity="high",
                        event_id=event_id,
                        details={
                            "src_ip": src_ip,
                            "host": host,
                            "window_minutes": window_minutes,
                            "distinct_users": distinct_users,
                            "threshold": user_threshold,
                            "mitre": {"tactics": ["Credential Access"], "techniques": ["Brute Force"]},
                        },
                    )

        # Successful login after multiple failures (existing behavior; generalized)
        is_success = (outcome == "success") or ("Accepted password" in (message or ""))
        is_auth = (action == "logon") or ("Accepted password" in (message or ""))
        if is_success and is_auth:
            rule_id = "corr_credential_stuffing"
            if not alert_exists_for_event_rule(DB_PATH, event_id=event_id, rule_id=rule_id):
                window_minutes = 10
                threshold = 10
                since = (ts - timedelta(minutes=window_minutes)).isoformat()
                failures = count_recent_sshd_failed_password(DB_PATH, since_ts=since, src_ip=src_ip, host=host)
                if failures >= threshold:
                    insert_alert(
                        DB_PATH,
                        ts=ts,
                        rule_id=rule_id,
                        title="Potential credential stuffing (failed logins then success)",
                        severity="high",
                        event_id=event_id,
                        details={
                            "src_ip": src_ip,
                            "host": host,
                            "window_minutes": window_minutes,
                            "failed_password_count": failures,
                            "threshold": threshold,
                            "mitre": {"tactics": ["Credential Access"], "techniques": ["Brute Force"]},
                        },
                    )

            # Concurrent logins: same user, different IPs in short window
            if user and src_ip:
                rule_id = "corr_concurrent_logins"
                window_minutes = 10
                since = (ts - timedelta(minutes=window_minutes)).isoformat()
                if not alert_exists_recent(DB_PATH, since_ts=since, rule_id=rule_id, key="user", value=user):
                    ips = list_recent_auth_success_ips_for_user(DB_PATH, since_ts=since, user=user, limit=10)
                    other_ips = [ip for ip in ips if ip and ip != src_ip]
                    if other_ips:
                        insert_alert(
                            DB_PATH,
                            ts=ts,
                            rule_id=rule_id,
                            title="Concurrent logins detected (same user, multiple IPs)",
                            severity="medium",
                            event_id=event_id,
                            details={
                                "user": user,
                                "src_ip": src_ip,
                                "other_ips": other_ips[:5],
                                "window_minutes": window_minutes,
                                "mitre": {"tactics": ["Credential Access"], "techniques": ["Valid Accounts"]},
                            },
                        )

    # --- Network scanning: distinct destination ports from same source
    if (category == "network") and src_ip:
        try:
            dpt = int(dst_port) if dst_port is not None else None
        except Exception:
            dpt = None
        if dpt is not None:
            rule_id = "corr_port_scan"
            window_minutes = 5
            threshold = 20
            since = (ts - timedelta(minutes=window_minutes)).isoformat()
            if not alert_exists_recent(DB_PATH, since_ts=since, rule_id=rule_id, key="src_ip", value=src_ip):
                ports = count_distinct_dst_ports(DB_PATH, since_ts=since, src_ip=src_ip, host=host, dst_ip=dst_ip)
                if ports >= threshold:
                    insert_alert(
                        DB_PATH,
                        ts=ts,
                        rule_id=rule_id,
                        title="Port scanning suspected (many destination ports)",
                        severity="high",
                        event_id=event_id,
                        details={
                            "src_ip": src_ip,
                            "host": host,
                            "dst_ip": dst_ip,
                            "window_minutes": window_minutes,
                            "distinct_dst_ports": ports,
                            "threshold": threshold,
                            "mitre": {"tactics": ["Discovery"], "techniques": ["Network Service Discovery"]},
                        },
                    )

    # --- Web scan heuristic: many 404s from one IP
    try:
        status = int(http_status) if http_status is not None else None
    except Exception:
        status = None
    if status == 404 and src_ip:
        rule_id = "corr_404_scan"
        window_minutes = 2
        threshold = 30
        since = (ts - timedelta(minutes=window_minutes)).isoformat()
        if not alert_exists_recent(DB_PATH, since_ts=since, rule_id=rule_id, key="src_ip", value=src_ip):
            count_404 = count_recent_http_status(DB_PATH, since_ts=since, src_ip=src_ip, status=404, host=host)
            if count_404 >= threshold:
                insert_alert(
                    DB_PATH,
                    ts=ts,
                    rule_id=rule_id,
                    title="Web scanning suspected (many 404s)",
                    severity="medium",
                    event_id=event_id,
                    details={
                        "src_ip": src_ip,
                        "host": host,
                        "window_minutes": window_minutes,
                        "count": count_404,
                        "threshold": threshold,
                        "mitre": {"tactics": ["Reconnaissance"], "techniques": ["Active Scanning"]},
                    },
                )


def _extract_ioc_candidates(message: str, fields: Dict[str, Any]) -> Dict[str, List[str]]:
    text_parts: List[str] = []
    if message:
        text_parts.append(str(message))

    # Pull string-ish field values
    for k, v in (fields or {}).items():
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
    hashes = _SHA256_RE.findall(blob)
    domains = _DOMAIN_RE.findall(blob)

    # Avoid obvious local noise.
    domains = [d for d in domains if d.lower() not in {"localhost"}]

    return {
        "ip": ips[:200],
        "sha256": hashes[:200],
        "domain": domains[:200],
    }


@app.on_event("startup")
def _startup() -> None:
    init_db(DB_PATH)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    alerts = list_alerts(DB_PATH, limit=50)
    events = list_events(DB_PATH, limit=50)
    return render_index(alerts=alerts, events=events)

@app.get("/health")
def health() -> Dict[str, Any]:
    init_db(DB_PATH)
    return db_health(DB_PATH)

@app.get("/stats")
def stats(hours: int = Query(default=24, ge=1, le=720)) -> Dict[str, Any]:
    init_db(DB_PATH)
    since = (datetime.now(timezone.utc) - timedelta(hours=int(hours))).isoformat()
    return {"ok": True, "stats": get_stats(DB_PATH, since_ts=since)}


@app.get("/web/info")
def web_info(hours: int = Query(default=24, ge=1, le=720)) -> Dict[str, Any]:
    """Consolidated info endpoint for the web UI.

    Returns lightweight metadata and health/stats so the UI can avoid multiple round-trips.
    """
    init_db(DB_PATH)
    since = (datetime.now(timezone.utc) - timedelta(hours=int(hours))).isoformat()

    try:
        rules = load_rules(RULES_PATH)
        rule_count = len(rules)
    except Exception:
        rule_count = None

    try:
        mitre = build_attack_catalog(MITRE_ATTACK_RAW_PATH)
        mitre_summary = {
            "ok": bool(mitre.get("ok")),
            "parsed_total_techniques": int(mitre.get("parsed_total_techniques") or 0),
            "leftover_count": int(mitre.get("leftover_count") or 0),
        }
    except Exception:
        mitre_summary = {"ok": False}

    return {
        "ok": True,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "app": {"title": app.title, "version": app.version},
        "db": db_health(DB_PATH),
        "stats": get_stats(DB_PATH, since_ts=since),
        "risk": risk_summary(DB_PATH, since_ts=since),
        "rules": {"path": str(RULES_PATH), "count": rule_count},
        "mitre_attack": mitre_summary,
    }


@app.get("/web/bootstrap")
def web_bootstrap(
    limit: int = Query(default=50, ge=1, le=1000),
    hours: int = Query(default=24, ge=1, le=720),
) -> Dict[str, Any]:
    """Single-call bootstrap for the dashboard UI.

    Includes the same info as /web/info plus the latest alerts/events.
    """
    init_db(DB_PATH)
    info = web_info(hours=hours)
    return {
        **info,
        "alerts": list_alerts(DB_PATH, limit=limit),
        "events": list_events(DB_PATH, limit=limit),
    }


@app.get("/mitre/attack")
def mitre_attack_catalog() -> Dict[str, Any]:
    """Return the MITRE ATT&CK tactics/techniques catalog (from rules/mitre_attack_raw.txt).

    This is a lightweight catalog intended for tagging detections and powering UI lookups.
    """
    try:
        return build_attack_catalog(MITRE_ATTACK_RAW_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/timeline")
def timeline(
    event_id: int = Query(ge=1),
    before_seconds: int = Query(default=300, ge=0, le=86400),
    after_seconds: int = Query(default=300, ge=0, le=86400),
    pivot: str = Query(default="auto", max_length=20),
    limit: int = Query(default=200, ge=1, le=2000),
) -> Dict[str, Any]:
    """Forensic timeline: events around an anchor event.

    pivot:
      - auto: prefers agent_id, then host, then first IP
      - agent: same agent_id
      - host: same host
      - ip: first IP in anchor event's ips
      - none: no pivot (time window only)
    """
    init_db(DB_PATH)
    ev = get_event(DB_PATH, event_id=event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="event not found")

    try:
        anchor_ts = datetime.fromisoformat(str(ev["ts"]))
    except Exception:
        raise HTTPException(status_code=500, detail="invalid event timestamp")

    start_ts = (anchor_ts - timedelta(seconds=int(before_seconds))).isoformat()
    end_ts = (anchor_ts + timedelta(seconds=int(after_seconds))).isoformat()

    p = (pivot or "auto").strip().lower()
    agent_id = str(ev.get("agent_id") or "").strip() or None
    host = str(ev.get("host") or "").strip() or None
    ip = None
    ips_raw = str(ev.get("ips") or "").strip()
    if ips_raw:
        ip = ips_raw.split(",")[0].strip() or None

    q_host = None
    q_agent = None
    q_ip = None

    if p == "none":
        pass
    elif p == "agent":
        q_agent = agent_id
    elif p == "host":
        q_host = host
    elif p == "ip":
        q_ip = ip
    else:
        if agent_id:
            q_agent = agent_id
        elif host:
            q_host = host
        elif ip:
            q_ip = ip

    items = list_events_timeline(
        DB_PATH,
        start_ts=start_ts,
        end_ts=end_ts,
        host=q_host,
        agent_id=q_agent,
        ip=q_ip,
        limit=limit,
    )

    return {
        "ok": True,
        "anchor": ev,
        "window": {
            "start": start_ts,
            "end": end_ts,
            "before_seconds": before_seconds,
            "after_seconds": after_seconds,
        },
        "pivot": {"mode": p, "host": q_host, "agent_id": q_agent, "ip": q_ip},
        "events": items,
    }


@app.post("/ingest", response_model=List[EventOut])
def ingest(payload: Union[EventIn, List[EventIn]]) -> List[EventOut]:
    init_db(DB_PATH)
    rules = load_rules(RULES_PATH)

    items: List[EventIn] = payload if isinstance(payload, list) else [payload]
    out: List[EventOut] = []

    for item in items:
        norm_message, norm_fields = normalize_event(
            source=item.source,
            message=item.message,
            fields=item.fields or {},
            host=item.host,
        )
        event_id = insert_event(
            DB_PATH,
            ts=item.ts,
            source=item.source,
            host=item.host,
            facility=item.facility,
            severity=item.severity,
            message=norm_message,
            fields=norm_fields,
        )

        event_dict: Dict[str, Any] = {
            "id": event_id,
            "ts": item.ts.isoformat(),
            "source": item.source,
            "host": item.host,
            "facility": item.facility,
            "severity": item.severity,
            "message": norm_message,
            "fields": norm_fields,
        }

        matches = match_rules(event_dict, rules)
        for match in matches:
            alert_id = insert_alert(
                DB_PATH,
                ts=datetime.fromisoformat(match["ts"]),
                rule_id=match["rule_id"],
                title=match["title"],
                severity=match["severity"],
                event_id=event_id,
                details=match.get("details") or {},
            )

            # MDR hook (best-effort): webhook + optional incident creation.
            try:
                send_mdr_webhook(
                    event_type="alert.created",
                    payload={
                        "alert_id": alert_id,
                        "ts": match["ts"],
                        "rule_id": match["rule_id"],
                        "title": match["title"],
                        "severity": match["severity"],
                        "event_id": event_id,
                    },
                )
            except Exception:
                pass

            try:
                if should_auto_create_incident_for_alert(severity=match["severity"]):
                    create_mdr_incident_from_alert(
                        DB_PATH,
                        alert_id=alert_id,
                        created_at=datetime.now(timezone.utc),
                    )
            except Exception:
                pass

        # Correlation detectors (best-effort)
        try:
            _run_correlation_detectors(
                event_id=event_id,
                ts=item.ts,
                source=item.source,
                host=item.host,
                message=norm_message,
                fields=norm_fields,
            )
        except Exception:
            pass

        # Threat intel matches (IOCs)
        try:
            candidates = _extract_ioc_candidates(norm_message, norm_fields)
            hits = find_ioc_matches(DB_PATH, candidates=candidates)
        except Exception:
            hits = []

        for hit in hits:
            alert_id = insert_alert(
                DB_PATH,
                ts=item.ts,
                rule_id=f"ti_{hit['type']}",
                title=f"Threat Intel match: {hit['type']}",
                severity="high",
                event_id=event_id,
                details={"ioc": hit, "candidates": candidates},
            )

            try:
                send_mdr_webhook(
                    event_type="alert.created",
                    payload={
                        "alert_id": alert_id,
                        "ts": item.ts.isoformat(),
                        "rule_id": f"ti_{hit['type']}",
                        "title": f"Threat Intel match: {hit['type']}",
                        "severity": "high",
                        "event_id": event_id,
                    },
                )
            except Exception:
                pass

            try:
                if should_auto_create_incident_for_alert(severity="high"):
                    create_mdr_incident_from_alert(
                        DB_PATH,
                        alert_id=alert_id,
                        created_at=datetime.now(timezone.utc),
                    )
            except Exception:
                pass

        out.append(
            EventOut(
                id=event_id,
                ts=item.ts,
                source=item.source,
                host=item.host,
                facility=item.facility,
                severity=item.severity,
                message=norm_message,
                fields=norm_fields,
            )
        )

    return out


@app.get("/ti/iocs", response_model=IocListOut)
def ti_list_iocs(limit: int = Query(default=200, ge=1, le=2000)) -> IocListOut:
    init_db(DB_PATH)
    return IocListOut(ok=True, iocs=list_iocs(DB_PATH, limit=limit))


@app.post("/ti/iocs", response_model=IocCreateOut)
def ti_add_ioc(payload: IocIn) -> IocCreateOut:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    ioc_type = (payload.type or "").strip().lower()
    if ioc_type not in {"ip", "domain", "sha256"}:
        return IocCreateOut(ok=False, id=0)
    try:
        ioc_id = upsert_ioc(
            DB_PATH,
            ioc_type=ioc_type,
            value=payload.value,
            source=payload.source,
            note=payload.note,
            now=now,
        )
    except Exception:
        return IocCreateOut(ok=False, id=0)
    return IocCreateOut(ok=True, id=ioc_id)


@app.delete("/ti/iocs/{ioc_id}")
def ti_delete_ioc(ioc_id: int) -> Dict[str, Any]:
    init_db(DB_PATH)
    return {"ok": delete_ioc(DB_PATH, ioc_id=ioc_id)}


@app.post("/edr/register", response_model=EdrRegisterOut)
def edr_register(payload: EdrRegisterIn) -> EdrRegisterOut:
    init_db(DB_PATH)

    agent_id = (payload.agent_id or "").strip() or uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    endpoint_id = upsert_edr_endpoint(
        DB_PATH,
        agent_id=agent_id,
        host=payload.host,
        os=payload.os,
        ip=payload.ip,
        version=payload.version,
        tags=payload.tags,
        now=now,
    )
    return EdrRegisterOut(ok=True, agent_id=agent_id, endpoint_id=endpoint_id)


@app.get("/edr/endpoints")
def edr_endpoints(limit: int = Query(default=100, ge=1, le=1000)) -> Dict[str, Any]:
    init_db(DB_PATH)
    return {"ok": True, "endpoints": list_edr_endpoints(DB_PATH, limit=limit)}


@app.post("/edr/telemetry")
def edr_telemetry(payload: EdrTelemetryIn) -> Dict[str, Any]:
    init_db(DB_PATH)
    rules = load_rules(RULES_PATH)

    now = datetime.now(timezone.utc)
    touch_edr_endpoint(DB_PATH, agent_id=payload.agent_id, now=now)

    inserted: int = 0
    alerts_created: int = 0

    for ev in payload.events:
        norm_message, norm_fields = normalize_event(
            source="edr",
            message=ev.message,
            fields={**(ev.fields or {}), "agent_id": payload.agent_id},
            host=payload.host,
        )
        event_id = insert_event(
            DB_PATH,
            ts=ev.ts,
            source="edr",
            host=payload.host,
            facility=ev.facility,
            severity=ev.severity,
            message=norm_message,
            fields=norm_fields,
        )
        inserted += 1

        event_dict: Dict[str, Any] = {
            "id": event_id,
            "ts": ev.ts.isoformat(),
            "source": "edr",
            "host": payload.host,
            "facility": ev.facility,
            "severity": ev.severity,
            "message": norm_message,
            "fields": norm_fields,
        }

        matches = match_rules(event_dict, rules)
        for match in matches:
            alert_id = insert_alert(
                DB_PATH,
                ts=datetime.fromisoformat(match["ts"]),
                rule_id=match["rule_id"],
                title=match["title"],
                severity=match["severity"],
                event_id=event_id,
                details=match.get("details") or {},
            )
            alerts_created += 1

            try:
                send_mdr_webhook(
                    event_type="alert.created",
                    payload={
                        "alert_id": alert_id,
                        "ts": match["ts"],
                        "rule_id": match["rule_id"],
                        "title": match["title"],
                        "severity": match["severity"],
                        "event_id": event_id,
                        "agent_id": payload.agent_id,
                        "host": payload.host,
                    },
                )
            except Exception:
                pass

            try:
                if should_auto_create_incident_for_alert(severity=match["severity"]):
                    create_mdr_incident_from_alert(
                        DB_PATH,
                        alert_id=alert_id,
                        created_at=datetime.now(timezone.utc),
                        tags={"agent_id": payload.agent_id, "host": payload.host} if payload.host else {"agent_id": payload.agent_id},
                    )
            except Exception:
                pass

        # Threat intel matches (IOCs)
        try:
            candidates = _extract_ioc_candidates(norm_message, norm_fields)
            hits = find_ioc_matches(DB_PATH, candidates=candidates)
        except Exception:
            hits = []

        try:
            _run_correlation_detectors(
                event_id=event_id,
                ts=ev.ts,
                source="edr",
                host=payload.host,
                message=norm_message,
                fields=norm_fields,
            )
        except Exception:
            pass

        for hit in hits:
            alert_id = insert_alert(
                DB_PATH,
                ts=ev.ts,
                rule_id=f"ti_{hit['type']}",
                title=f"Threat Intel match: {hit['type']}",
                severity="high",
                event_id=event_id,
                details={"ioc": hit, "candidates": candidates},
            )
            alerts_created += 1

            try:
                send_mdr_webhook(
                    event_type="alert.created",
                    payload={
                        "alert_id": alert_id,
                        "ts": ev.ts.isoformat(),
                        "rule_id": f"ti_{hit['type']}",
                        "title": f"Threat Intel match: {hit['type']}",
                        "severity": "high",
                        "event_id": event_id,
                        "agent_id": payload.agent_id,
                        "host": payload.host,
                    },
                )
            except Exception:
                pass

            try:
                if should_auto_create_incident_for_alert(severity="high"):
                    create_mdr_incident_from_alert(
                        DB_PATH,
                        alert_id=alert_id,
                        created_at=datetime.now(timezone.utc),
                        tags={"agent_id": payload.agent_id, "host": payload.host} if payload.host else {"agent_id": payload.agent_id},
                    )
            except Exception:
                pass

    return {"ok": True, "inserted": inserted, "alerts_created": alerts_created}


@app.get("/mdr/incidents", response_model=MdrIncidentListOut)
def mdr_list_incidents(
    status: Optional[str] = Query(default=None, max_length=40),
    limit: int = Query(default=200, ge=1, le=2000),
) -> MdrIncidentListOut:
    init_db(DB_PATH)
    items = list_mdr_incidents(DB_PATH, status=status, limit=limit)
    return MdrIncidentListOut(ok=True, incidents=[MdrIncidentOut(**i) for i in items])


@app.get("/mdr/incidents/{incident_id}", response_model=MdrIncidentOut)
def mdr_get_incident(incident_id: int) -> MdrIncidentOut:
    init_db(DB_PATH)
    item = get_mdr_incident(DB_PATH, incident_id=incident_id)
    if item is None:
        raise HTTPException(status_code=404, detail="incident not found")
    # notes are already in the dict; Pydantic will coerce
    return MdrIncidentOut(**item)


@app.post("/mdr/incidents", response_model=MdrIncidentCreateOut)
def mdr_create_incident(payload: MdrIncidentCreateIn) -> MdrIncidentCreateOut:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)

    try:
        if payload.alert_id is not None:
            incident_id = create_mdr_incident_from_alert(
                DB_PATH,
                alert_id=int(payload.alert_id),
                created_at=now,
                assigned_to=payload.assigned_to,
                tags=payload.tags,
            )
        else:
            title = (payload.title or "").strip()
            if not title:
                raise HTTPException(status_code=400, detail="title is required (or provide alert_id)")
            incident_id = create_mdr_incident(
                DB_PATH,
                created_at=now,
                status="open",
                severity=payload.severity,
                title=title,
                description=payload.description,
                alert_id=None,
                event_id=payload.event_id,
                assigned_to=payload.assigned_to,
                tags=payload.tags,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MdrIncidentCreateOut(ok=True, incident_id=incident_id)


@app.post("/mdr/incidents/{incident_id}")
def mdr_update_incident(incident_id: int, payload: MdrIncidentUpdateIn) -> Dict[str, Any]:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    ok = update_mdr_incident(
        DB_PATH,
        incident_id=incident_id,
        now=now,
        status=payload.status,
        assigned_to=payload.assigned_to,
        severity=payload.severity,
    )
    if not ok:
        # Could be not found or no fields set; disambiguate lightly.
        if get_mdr_incident(DB_PATH, incident_id=incident_id) is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return {"ok": False}
    return {"ok": True}


@app.post("/mdr/incidents/{incident_id}/notes")
def mdr_add_note(incident_id: int, payload: MdrIncidentNoteIn) -> Dict[str, Any]:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    if get_mdr_incident(DB_PATH, incident_id=incident_id) is None:
        raise HTTPException(status_code=404, detail="incident not found")
    try:
        note_id = add_mdr_incident_note(
            DB_PATH,
            incident_id=incident_id,
            created_at=now,
            author=payload.author,
            note=payload.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "note_id": note_id}


@app.post("/edr/actions", response_model=EdrActionCreateOut)
def edr_create_action(payload: EdrActionCreateIn) -> EdrActionCreateOut:
    init_db(DB_PATH)

    action_type = (payload.action_type or "").strip().lower()
    if action_type in _DANGEROUS_EDR_ACTIONS:
        if not _is_dangerous_action_allowed(requested_by=payload.requested_by):
            # Audit trail: store a SIEM event for denied dangerous actions.
            try:
                insert_event(
                    DB_PATH,
                    ts=datetime.now(timezone.utc),
                    source="edr",
                    host=None,
                    facility="edr",
                    severity="warning",
                    message="edr_action_denied",
                    fields={
                        "agent_id": payload.agent_id,
                        "action_type": action_type,
                        "requested_by": payload.requested_by,
                        "params": payload.params,
                        "reason": "dangerous action denied by allowlist",
                    },
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=403,
                detail=(
                    "dangerous action denied; set EDR_DANGEROUS_ACTION_ALLOWLIST to a comma-separated "
                    "list of allowed requested_by values (or '*')"
                ),
            )

    now = datetime.now(timezone.utc)
    try:
        action_id = create_edr_action(
            DB_PATH,
            agent_id=payload.agent_id,
            action_type=payload.action_type,
            params=payload.params,
            requested_by=payload.requested_by,
            now=now,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="unknown agent_id; register endpoint first")
    return EdrActionCreateOut(ok=True, action_id=action_id)


@app.get("/edr/actions/poll", response_model=EdrPollOut)
def edr_poll_actions(
    agent_id: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=200),
) -> EdrPollOut:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    touch_edr_endpoint(DB_PATH, agent_id=agent_id, now=now)
    actions = list_pending_edr_actions(DB_PATH, agent_id=agent_id, limit=limit)
    return EdrPollOut(ok=True, actions=actions)  # pydantic will coerce dicts


@app.get("/edr/actions/history", response_model=EdrPollOut)
def edr_actions_history(
    agent_id: Optional[str] = Query(default=None, max_length=200),
    status: Optional[str] = Query(default=None, max_length=40),
    limit: int = Query(default=100, ge=1, le=1000),
) -> EdrPollOut:
    init_db(DB_PATH)
    actions = list_edr_actions(DB_PATH, agent_id=agent_id, status=status, limit=limit)
    return EdrPollOut(ok=True, actions=actions)


@app.post("/edr/actions/{action_id}/ack")
def edr_ack_action(action_id: int, payload: EdrAckIn) -> Dict[str, Any]:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    ok = ack_edr_action(DB_PATH, action_id=action_id, agent_id=payload.agent_id, now=now)
    return {"ok": ok}


@app.post("/edr/actions/{action_id}/result")
def edr_action_result(action_id: int, payload: EdrResultIn) -> Dict[str, Any]:
    init_db(DB_PATH)
    now = datetime.now(timezone.utc)
    ok = complete_edr_action(
        DB_PATH,
        action_id=action_id,
        agent_id=payload.agent_id,
        ok=payload.ok,
        result=payload.result,
        now=now,
    )

    # Forensics: store action result as a normal event.
    if ok:
        try:
            insert_event(
                DB_PATH,
                ts=now,
                source="edr",
                host=None,
                facility="edr",
                severity="info" if payload.ok else "warning",
                message="edr_action_result",
                fields={
                    "agent_id": payload.agent_id,
                    "action_id": action_id,
                    "ok": payload.ok,
                    "result": payload.result,
                },
            )
        except Exception:
            pass
    return {"ok": ok}


@app.get("/events", response_model=List[Dict[str, Any]])
def events(
    limit: int = Query(default=100, ge=1, le=1000),
    agent_id: Optional[str] = Query(default=None, max_length=200),
    ip: Optional[str] = Query(default=None, max_length=64),
) -> List[Dict[str, Any]]:
    init_db(DB_PATH)
    return list_events(DB_PATH, limit=limit, agent_id=agent_id, ip=ip)


@app.get("/search", response_model=List[Dict[str, Any]])
def search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=1000),
    agent_id: Optional[str] = Query(default=None, max_length=200),
    ip: Optional[str] = Query(default=None, max_length=64),
) -> List[Dict[str, Any]]:
    init_db(DB_PATH)
    return search_events(DB_PATH, q=q, limit=limit, agent_id=agent_id, ip=ip)


@app.get("/alerts", response_model=List[Dict[str, Any]])
def alerts(
    limit: int = Query(default=100, ge=1, le=1000),
    agent_id: Optional[str] = Query(default=None, max_length=200),
    ip: Optional[str] = Query(default=None, max_length=64),
) -> List[Dict[str, Any]]:
    init_db(DB_PATH)
    return list_alerts(DB_PATH, limit=limit, agent_id=agent_id, ip=ip)


@app.post("/soc/scan")
def soc_scan(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = str(payload.get("path", "")).strip()
    recursive = bool(payload.get("recursive", False))

    if not target:
        return {"ok": False, "error": "path is required"}

    p = Path(target)
    if not p.exists():
        return {"ok": False, "error": f"path does not exist: {target}"}

    if p.is_dir() and not recursive:
        return {"ok": False, "error": "path is a directory; set recursive=true to scan directories"}

    job = start_scan(scans_dir=SCANS_DIR, target_path=str(p), recursive=recursive)
    return {"ok": True, "scan_id": job.scan_id}


@app.get("/soc/scan/{scan_id}")
def soc_scan_status(scan_id: str) -> Dict[str, Any]:
    job = get_scan(scan_id)
    if job is None:
        return {"ok": False, "error": "scan_id not found"}

    log_tail = read_scan_log_tail(job)
    done = job.finished_at is not None
    return {
        "ok": True,
        "scan_id": job.scan_id,
        "path": job.target_path,
        "recursive": job.recursive,
        "done": done,
        "return_code": job.return_code,
        "error": job.error,
        "log": log_tail,
    }


@app.get("/soc/net/interfaces")
def soc_net_interfaces() -> Dict[str, Any]:
    return {"ok": True, "interfaces": list_interfaces()}


@app.post("/soc/net/start")
def soc_net_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    interface = str(payload.get("interface", "")).strip()
    bpf_filter = str(payload.get("filter", "")).strip()
    mode = str(payload.get("mode", "summary")).strip().lower()

    if not interface:
        return {"ok": False, "error": "interface is required"}

    if mode not in {"summary", "pcap"}:
        return {"ok": False, "error": "mode must be 'summary' or 'pcap'"}

    if mode == "pcap":
        session = start_capture(logs_dir=NET_LOGS_DIR, interface=interface, bpf_filter=bpf_filter)
    else:
        session = start_monitor(logs_dir=NET_LOGS_DIR, interface=interface, bpf_filter=bpf_filter)

    return {"ok": True, "session_id": session.session_id, "mode": session.mode}


@app.post("/soc/net/stop/{session_id}")
def soc_net_stop(session_id: str) -> Dict[str, Any]:
    ok = stop_monitor(session_id)
    return {"ok": ok}


@app.get("/soc/net/{session_id}")
def soc_net_status(session_id: str) -> Dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        return {"ok": False, "error": "session_id not found"}

    log_tail = read_log_tail(session)
    done = session.finished_at is not None
    return {
        "ok": True,
        "session_id": session.session_id,
        "interface": session.interface,
        "filter": session.bpf_filter,
        "mode": session.mode,
        "done": done,
        "return_code": session.return_code,
        "error": session.error,
        "log": log_tail,
        **pcap_info(session),
    }


@app.post("/soc/crypto/digests")
def soc_crypto_digests(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = str(payload.get("input", ""))
    input_format = str(payload.get("input_format", "text"))
    algorithms = payload.get("algorithms", [])
    if not isinstance(algorithms, list):
        return {"ok": False, "error": "algorithms must be a list"}

    results = compute_digests(raw_input=raw, input_format=input_format, algorithms=algorithms)
    # If decoding failed, compute_digests returns a single 'error' entry.
    if "error" in results and not results["error"].ok:
        return {"ok": False, "error": results["error"].error or "invalid input"}

    return {
        "ok": True,
        "results": {
            k: {
                "ok": v.ok,
                "hex": v.hex,
                "error": v.error,
                "note": v.note,
            }
            for k, v in results.items()
        },
    }


@app.get("/soc/net/download/{session_id}")
def soc_net_download(session_id: str):
    session = get_session(session_id)
    if session is None:
        return {"ok": False, "error": "session_id not found"}

    if session.pcap_path is None:
        return {"ok": False, "error": "no pcap available for this session"}

    if not session.pcap_path.exists():
        return {"ok": False, "error": "pcap file not found"}

    return FileResponse(
        path=str(session.pcap_path),
        filename=session.pcap_path.name,
        media_type="application/vnd.tcpdump.pcap",
    )
