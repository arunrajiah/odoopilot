#!/usr/bin/env python3
"""Render odoopilot/static/description/banner_source.html to banner.png.

Run from the repo root::

    python3 scripts/render_banner.py

Requires Playwright with the chromium browser installed::

    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
SOURCE = ROOT / "odoopilot/static/description/banner_source.html"
TARGET = ROOT / "odoopilot/static/description/banner.png"
WIDTH = 1200
HEIGHT = 630


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run:")
        print("    pip install playwright && playwright install chromium")
        return 2

    if not SOURCE.exists():
        print(f"ERROR: {SOURCE} not found")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(SOURCE.absolute().as_uri())
        # Give web fonts a beat to load.
        page.wait_for_timeout(400)
        page.screenshot(
            path=str(TARGET),
            clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT},
        )
        browser.close()

    print(f"OK: wrote {TARGET} ({TARGET.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
