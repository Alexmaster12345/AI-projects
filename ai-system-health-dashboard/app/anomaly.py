from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from .config import settings
from .metrics import history
from .models import Anomaly, Insights
from .storage import storage


@dataclass(frozen=True)
class MetricPoint:
    ts: float
    value: float


def _zscore(values: list[float]) -> Optional[float]:
    if len(values) < 10:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(var)
    if std < 1e-9:
        return None
    return (values[-1] - mean) / std


def _severity(z: float) -> str:
    az = abs(z)
    if az >= settings.anomaly_z_threshold * 1.5:
        return "crit"
    if az >= settings.anomaly_z_threshold:
        return "warn"
    return "info"


def compute_insights() -> Insights:
    window = max(10, settings.anomaly_window_seconds)
    # Prefer persisted history so baselines survive restarts.
    if storage.enabled:
        try:
            samples = storage.query_history(window)
        except Exception:
            samples = history(window)
    else:
        samples = history(window)
    now = time.time()
    if len(samples) < 10:
        return Insights(ts=now, anomalies=[], summary="Collecting baseline…")

    metrics: dict[str, list[float]] = {
        "cpu_percent": [s.cpu_percent for s in samples],
        "mem_percent": [s.mem_percent for s in samples],
        "swap_percent": [s.swap_percent for s in samples],
    }
    if samples[-1].load1 is not None:
        metrics["load1"] = [float(s.load1 or 0.0) for s in samples]

    anomalies: list[Anomaly] = []
    for name, values in metrics.items():
        z = _zscore(values)
        if z is None:
            continue
        if abs(z) < settings.anomaly_z_threshold:
            continue
        sev = _severity(z)
        direction = "high" if z > 0 else "low"
        msg = f"{name} unusually {direction} (z={z:.2f})"
        anomalies.append(Anomaly(metric=name, z=float(z), severity=sev, message=msg))

    anomalies.sort(key=lambda a: abs(a.z), reverse=True)
    if not anomalies:
        summary = "No anomalies detected in recent window."
    else:
        top = anomalies[0]
        summary = f"Top anomaly: {top.message}"

    return Insights(ts=now, anomalies=anomalies, summary=summary)
