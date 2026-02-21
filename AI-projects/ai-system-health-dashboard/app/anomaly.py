"""Anomaly detection for system metrics."""

import time
from .models import Insights, Anomaly


def compute_insights() -> Insights:
    """Compute system insights and anomaly detection."""
    current_time = time.time()
    
    # Mock values for now - in real implementation these would come from metrics
    cpu_usage = 25.5
    memory_usage = 45.2
    disk_usage = 60.1
    
    # Simple anomaly detection based on thresholds
    anomalies = []
    
    if cpu_usage > 80:
        anomalies.append(Anomaly(
            metric="cpu",
            z=2.5,
            severity="crit",
            message="High CPU usage detected"
        ))
    
    if memory_usage > 85:
        anomalies.append(Anomaly(
            metric="memory",
            z=2.0,
            severity="warn", 
            message="High memory usage detected"
        ))
    
    if disk_usage > 90:
        anomalies.append(Anomaly(
            metric="disk",
            z=3.0,
            severity="crit",
            message="High disk usage detected"
        ))
    
    # Create summary
    if anomalies:
        summary = f"Found {len(anomalies)} anomalies: " + ", ".join([a.message for a in anomalies])
    else:
        summary = "System operating normally"
    
    return Insights(
        ts=current_time,
        anomalies=anomalies,
        summary=summary
    )