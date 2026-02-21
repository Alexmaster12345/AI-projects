"""System metrics collection and storage."""

from typing import Deque, Optional
import collections
import time
import threading
import socket
import psutil
from .models import SystemSample, DiskUsage, NetIO, ProtocolStatus


# In-memory storage for recent metrics
_history: Deque[SystemSample] = collections.deque(maxlen=1000)
_latest: Optional[SystemSample] = None
_lock = threading.Lock()


def add_sample(sample: SystemSample) -> None:
    """Add a new metric sample."""
    with _lock:
        global _latest
        _history.append(sample)
        _latest = sample


def collect_sample() -> SystemSample:
    """Collect current system metrics."""
    current_time = time.time()
    
    # Collect system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_temp = None
    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                # Try to get CPU temperature
                for name, entries in temps.items():
                    if 'cpu' in name.lower() or 'core' in name.lower():
                        if entries:
                            cpu_temp = entries[0].current
                            break
    except:
        pass
    
    # Load averages
    load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
    
    # Memory info
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Disk info
    disk_partitions = psutil.disk_partitions()
    disk_usage = []
    for partition in disk_partitions:
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_usage.append(DiskUsage(
                mount=partition.mountpoint,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent
            ))
        except:
            continue
    
    # Network I/O
    net_io = psutil.net_io_counters()
    net = NetIO(bytes_sent=net_io.bytes_sent, bytes_recv=net_io.bytes_recv)
    
    # Boot time and uptime
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time
    
    # Top processes
    top_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] is not None:
                    top_processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'] or 'unknown',
                        'cpu_percent': pinfo['cpu_percent'],
                        'memory_percent': pinfo['memory_percent'] or 0
                    })
                if len(top_processes) >= 10:
                    break
            except:
                continue
    except:
        pass
    
    sample = SystemSample(
        ts=current_time,
        hostname=socket.gethostname(),
        cpu_percent=cpu_percent,
        cpu_freq_mhz=cpu_freq.current if cpu_freq else None,
        cpu_temp_c=cpu_temp,
        load1=load_avg[0],
        load5=load_avg[1],
        load15=load_avg[2],
        boot_time_ts=boot_time,
        uptime_seconds=uptime,
        mem_total_bytes=mem.total,
        mem_used_bytes=mem.used,
        mem_available_bytes=mem.available,
        mem_percent=mem.percent,
        swap_total_bytes=swap.total,
        swap_used_bytes=swap.used,
        swap_percent=swap.percent,
        disk=disk_usage,
        disk_health="ok",  # Simple check - could be enhanced
        net=net,
        protocols={},  # Will be populated by protocol checker
        gpu=[],  # Will be populated if GPU info available
        gpu_health="ok",
        top_processes=top_processes
    )
    
    add_sample(sample)
    return sample


def latest() -> Optional[SystemSample]:
    """Get the latest metric sample."""
    with _lock:
        return _latest


def history(seconds: int = 300) -> list[SystemSample]:
    """Get metric samples from the last N seconds."""
    cutoff_time = time.time() - seconds
    with _lock:
        return [s for s in _history if s.ts >= cutoff_time]
