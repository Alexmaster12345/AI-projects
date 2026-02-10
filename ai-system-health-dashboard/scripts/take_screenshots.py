"""Take UI screenshots for the ASHD project.

This script logs into the dashboard and captures screenshots for key pages.

Usage (example):
  ASHD_USER=admin ASHD_PASS=... python scripts/take_screenshots.py --base-url http://127.0.0.1:8000

Notes:
- Requires Playwright:
    pip install playwright
    python -m playwright install chromium
- The server must be running.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Optional


def _require_env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _shot(page: Any, out: Path) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(250)
    page.screenshot(path=str(out), full_page=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--out-dir", default="docs/screenshots")
    args = ap.parse_args()

    base_url = str(args.base_url).rstrip("/")
    out_dir = Path(args.out_dir)
    _safe_mkdir(out_dir)

    user = _require_env("ASHD_USER")
    pw = _require_env("ASHD_PASS")

    # Lazy import so the script can still be imported without Playwright installed.
    from playwright.sync_api import sync_playwright  # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Login page
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(200)
        _shot(page, out_dir / "01_login.png")

        # Perform login
        page.fill("#username", user)
        page.fill("#password", pw)
        page.click("button.primary")
        page.wait_for_load_state("domcontentloaded")

        # Dashboard
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        _shot(page, out_dir / "02_dashboard.png")

        # Problems
        page.goto(f"{base_url}/#problems", wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        _shot(page, out_dir / "03_problems.png")

        # Hosts
        page.goto(f"{base_url}/#hosts", wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        _shot(page, out_dir / "04_hosts.png")

        # Maps
        page.goto(f"{base_url}/#maps", wait_until="domcontentloaded")
        page.wait_for_timeout(900)
        _shot(page, out_dir / "05_maps.png")

        # Inventory page
        page.goto(f"{base_url}/inventory", wait_until="domcontentloaded")
        page.wait_for_timeout(700)
        _shot(page, out_dir / "06_inventory.png")

        # Overview page
        page.goto(f"{base_url}/overview", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        _shot(page, out_dir / "07_overview.png")

        # Configuration page
        page.goto(f"{base_url}/configuration", wait_until="domcontentloaded")
        page.wait_for_timeout(700)
        _shot(page, out_dir / "08_configuration.png")

        # Optional: host details (if any hosts exist)
        host_id: Optional[int] = None
        try:
            # Use the authenticated API via Playwright request.
            resp = context.request.get(f"{base_url}/api/hosts")
            if resp.ok:
                data = resp.json()
                if isinstance(data, list) and data:
                    first = data[0]
                    if isinstance(first, dict) and "id" in first:
                        host_id = int(first["id"])
        except Exception:
            host_id = None

        if host_id is not None:
            page.goto(f"{base_url}/host/{host_id}", wait_until="domcontentloaded")
            page.wait_for_timeout(700)
            _shot(page, out_dir / "09_host_details.png")

        context.close()
        browser.close()

    print(f"Saved screenshots to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
