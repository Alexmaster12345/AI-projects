from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class EventIn(BaseModel):
    ts: datetime = Field(default_factory=now_utc)
    source: str = Field(default="unknown", description="Where the event came from (syslog,file,agent,api,...)" )
    host: Optional[str] = None
    facility: Optional[str] = None
    severity: Optional[str] = None
    message: str
    fields: Dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    id: int
    ts: datetime
    source: str
    host: Optional[str]
    facility: Optional[str]
    severity: Optional[str]
    message: str
    fields: Dict[str, Any]


class AlertOut(BaseModel):
    id: int
    ts: datetime
    rule_id: str
    title: str
    severity: str
    event_id: int
    details: Dict[str, Any]


class EdrRegisterIn(BaseModel):
    agent_id: Optional[str] = Field(default=None, description="Stable agent identifier (optional; server can generate)")
    host: Optional[str] = None
    os: Optional[str] = None
    ip: Optional[str] = None
    version: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)


class EdrRegisterOut(BaseModel):
    ok: bool
    agent_id: str
    endpoint_id: int


class EdrTelemetryEventIn(BaseModel):
    ts: datetime = Field(default_factory=now_utc)
    facility: Optional[str] = None
    severity: Optional[str] = None
    message: str
    fields: Dict[str, Any] = Field(default_factory=dict)


class EdrTelemetryIn(BaseModel):
    agent_id: str
    host: Optional[str] = None
    events: List[EdrTelemetryEventIn]


class EdrActionCreateIn(BaseModel):
    agent_id: str
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    requested_by: Optional[str] = None


class EdrActionCreateOut(BaseModel):
    ok: bool
    action_id: int


class EdrActionOut(BaseModel):
    id: int
    agent_id: str
    created_at: str
    action_type: str
    params: Dict[str, Any]
    status: str
    requested_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)


class EdrPollOut(BaseModel):
    ok: bool
    actions: List[EdrActionOut]


class EdrAckIn(BaseModel):
    agent_id: str


class EdrResultIn(BaseModel):
    agent_id: str
    ok: bool = True
    result: Dict[str, Any] = Field(default_factory=dict)


class IocIn(BaseModel):
    type: str = Field(description="One of: ip, domain, sha256")
    value: str
    source: Optional[str] = None
    note: Optional[str] = None


class IocOut(BaseModel):
    id: int
    type: str
    value: str
    source: Optional[str] = None
    note: Optional[str] = None
    added_at: str


class IocListOut(BaseModel):
    ok: bool
    iocs: List[IocOut]


class IocCreateOut(BaseModel):
    ok: bool
    id: int


# --- Managed Detection & Response (MDR) ---


class MdrIncidentCreateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: str = Field(default="medium", description="One of: low, medium, high, critical")
    alert_id: Optional[int] = Field(default=None, description="Optional: create incident from an existing alert")
    event_id: Optional[int] = None
    assigned_to: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)


class MdrIncidentUpdateIn(BaseModel):
    status: Optional[str] = Field(default=None, description="open, acknowledged, in_progress, closed")
    assigned_to: Optional[str] = None
    severity: Optional[str] = Field(default=None, description="low, medium, high, critical")


class MdrIncidentNoteIn(BaseModel):
    author: Optional[str] = None
    note: str


class MdrIncidentNoteOut(BaseModel):
    id: int
    incident_id: int
    created_at: str
    author: Optional[str] = None
    note: str


class MdrIncidentOut(BaseModel):
    id: int
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    status: str
    severity: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[int] = None
    event_id: Optional[int] = None
    assigned_to: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)
    note_count: Optional[int] = None
    notes: Optional[List[MdrIncidentNoteOut]] = None


class MdrIncidentCreateOut(BaseModel):
    ok: bool
    incident_id: int


class MdrIncidentListOut(BaseModel):
    ok: bool
    incidents: List[MdrIncidentOut]
