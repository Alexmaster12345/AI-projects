from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class DiskUsage(BaseModel):
    mount: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


class NetIO(BaseModel):
    bytes_sent: int
    bytes_recv: int


class ProtocolStatus(BaseModel):
    status: Literal["ok", "warn", "crit", "unknown"] = "unknown"
    checked_ts: Optional[float] = None
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HostBase(BaseModel):
    name: str = Field(..., description="Display name")
    address: str = Field(..., description="IP address or hostname")
    type: Optional[str] = Field(None, description="Optional host type (e.g. Linux/Windows/Network)")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering/grouping")
    notes: Optional[str] = Field(None, description="Free-form notes")


class HostCreate(HostBase):
    pass


class Host(HostBase):
    id: int
    is_active: bool = True
    created_ts: float


class InventoryItemBase(BaseModel):
    name: str = Field(..., description="Item name (e.g. rack, server, switch)")
    category: Optional[str] = Field(None, description="Optional category (e.g. Server, Network, Rack, UPS)")
    location: Optional[str] = Field(None, description="Optional location (e.g. DC1 Row A Rack 12)")
    quantity: int = Field(1, ge=0, description="Quantity on hand")
    notes: Optional[str] = Field(None, description="Free-form notes")


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItem(InventoryItemBase):
    id: int
    created_ts: float


class GpuDevice(BaseModel):
    name: str
    util_percent: Optional[float] = None
    mem_used_mb: Optional[int] = None
    mem_total_mb: Optional[int] = None
    temp_c: Optional[float] = None


class SystemSample(BaseModel):
    ts: float = Field(..., description="Unix timestamp (seconds)")
    hostname: str

    cpu_percent: float
    cpu_freq_mhz: Optional[float] = None
    cpu_temp_c: Optional[float] = None
    load1: Optional[float] = None
    load5: Optional[float] = None
    load15: Optional[float] = None

    boot_time_ts: Optional[float] = None
    uptime_seconds: Optional[float] = None

    mem_total_bytes: int
    mem_used_bytes: int
    mem_available_bytes: int
    mem_percent: float

    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float

    disk: list[DiskUsage]
    # Simple derived status based on disk usage thresholds.
    disk_health: Literal["ok", "warn", "crit", "unknown"] = "unknown"
    net: NetIO

    # Cached protocol health checks (populated by background checker; safe default for old persisted samples).
    protocols: dict[str, ProtocolStatus] = Field(default_factory=dict)

    gpu: list[GpuDevice] = Field(default_factory=list)

    # Simple derived status based on GPU telemetry thresholds (best-effort).
    gpu_health: Literal["ok", "warn", "crit", "unknown"] = "unknown"

    top_processes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Best-effort list of process info (pid/name/cpu/mem)",
    )


class Anomaly(BaseModel):
    metric: str
    z: float
    severity: Literal["info", "warn", "crit"]
    message: str


class Insights(BaseModel):
    ts: float
    anomalies: list[Anomaly]
    summary: str
