from __future__ import annotations

import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ScanJob:
    scan_id: str
    target_path: str
    recursive: bool
    started_at: float
    finished_at: Optional[float]
    return_code: Optional[int]
    log_path: Path
    error: Optional[str]


_jobs: Dict[str, ScanJob] = {}
_jobs_lock = threading.Lock()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_line(log_path: Path, line: str) -> None:
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _run_clamscan(job: ScanJob) -> None:
    try:
        args = ["clamscan"]
        if job.recursive:
            args.append("-r")
        args.append(job.target_path)

        _write_line(job.log_path, f"[siem] starting clamscan: {' '.join(args)}")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            _write_line(job.log_path, line)

        rc = proc.wait()
        _write_line(job.log_path, f"[siem] clamscan finished with code {rc}")

        with _jobs_lock:
            job.return_code = rc
            job.finished_at = time.time()
    except FileNotFoundError:
        with _jobs_lock:
            job.error = "clamscan not found. Install ClamAV (e.g., 'sudo dnf install clamav clamav-update' or 'sudo apt install clamav')."
            job.return_code = 127
            job.finished_at = time.time()
        _write_line(job.log_path, f"[siem] ERROR: {job.error}")
    except Exception as e:
        with _jobs_lock:
            job.error = f"scan failed: {e}"
            job.return_code = 1
            job.finished_at = time.time()
        _write_line(job.log_path, f"[siem] ERROR: {job.error}")


def start_scan(*, scans_dir: Path, target_path: str, recursive: bool) -> ScanJob:
    _ensure_dir(scans_dir)

    scan_id = uuid.uuid4().hex
    log_path = scans_dir / f"{scan_id}.log"

    job = ScanJob(
        scan_id=scan_id,
        target_path=target_path,
        recursive=recursive,
        started_at=time.time(),
        finished_at=None,
        return_code=None,
        log_path=log_path,
        error=None,
    )

    _write_line(log_path, f"[siem] scan_id={scan_id}")

    with _jobs_lock:
        _jobs[scan_id] = job

    t = threading.Thread(target=_run_clamscan, args=(job,), daemon=True)
    t.start()

    return job


def get_scan(scan_id: str) -> Optional[ScanJob]:
    with _jobs_lock:
        return _jobs.get(scan_id)


def read_scan_log_tail(job: ScanJob, *, max_bytes: int = 32_000) -> str:
    if not job.log_path.exists():
        return ""

    data = job.log_path.read_bytes()
    if len(data) <= max_bytes:
        return data.decode("utf-8", errors="replace")

    tail = data[-max_bytes:]
    return tail.decode("utf-8", errors="replace")
