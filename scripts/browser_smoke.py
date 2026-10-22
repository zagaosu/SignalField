"""Browser smoke test for the local UI.

Requires Playwright and a Chromium-compatible browser. Uses the installed Edge
by default, so no browser download is needed on this machine.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def wait_for_run(base: str, run_id: str, timeout: float = 20) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = httpx.get(f"{base}/api/runs/{run_id}", timeout=10).json()
        if detail.get("status") not in {"queued", "running", "cancelling"}:
            return detail
        time.sleep(0.3)
    raise RuntimeError("demo seed did not finish")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8790")
    parser.add_argument(
        "--browser",
        default=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    )
    parser.add_argument("--screenshots", default="docs")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    shots = Path(args.screenshots)
    shots.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run: python -m pip install -r requirements-dev.txt")
        raise SystemExit(2)

    config = httpx.get(base + "/api/config", timeout=10).json()
    runs = httpx.get(base + "/api/runs", timeout=10).json()["runs"]
    if not runs:
        response = httpx.post(
            base + "/api/runs",
            json={"topics": ["Agent", "推理部署", "模型工具"], "window": "week", "mode": "demo"},
            timeout=10,
        )
        response.raise_for_status()
        wait_for_run(base, response.json()["id"], timeout=25)

    console_errors = []
    page_errors = []
    failed_requests = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=args.browser, headless=True
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(req.url))
        demo_runs = [run for run in runs if run.get("mode") == "demo"]
        demo_runs.sort(key=lambda run: (run.get("card_count", 0), run.get("created_at", "")), reverse=True)
        demo_run_id = demo_runs[0]["id"] if demo_runs else None
        target = base + (f"/?run={demo_run_id}" if demo_run_id else "")
        page.goto(target, wait_until="networkidle")
        page.wait_for_timeout(900)

        assert "信号场" in page.title()
        if page.locator("#interest-layer").is_visible():
            page.wait_for_timeout(1400)
            assert page.locator(".orb-keyword").count() == 8
            assert page.locator("#interest-mode-switch").is_visible()
            if page.locator("#orb-pause").is_visible():
                page.locator("#orb-pause").click()
            page.wait_for_timeout(600)
            page.screenshot(path=str(shots / "interest.png"))
            page.locator('[data-interest-key="Agent"]').click()
            page.locator('[data-interest-key="推理部署"]').click()
            page.wait_for_timeout(250)
            assert "Agent" in page.locator("#interest-summary").inner_text()
            assert page.locator("#interest-start").is_enabled()
            page.locator("#interest-start").click()
            page.wait_for_timeout(700)
            page.screenshot(path=str(shots / "interest-round2.png"))
            if page.locator("#orb-pause").is_visible():
                page.locator("#orb-pause").click()
            page.locator('[data-interest-key="工具调用"]').click()
            page.locator('[data-interest-key="量化"]').click()
            page.wait_for_timeout(200)
            assert "工具调用" in page.locator("#interest-summary").inner_text()
            assert page.locator("#interest-start").is_enabled()
            page.locator("#interest-skip").click()
            page.wait_for_timeout(600)
            assert page.locator("#radar-toolbar").is_visible()

        cards = page.locator(".event-card").count()
        assert cards >= 1, "no event cards rendered"
        page.screenshot(path=str(shots / "radar.png"), full_page=True)

        page.locator(".event-card").first.click()
        page.wait_for_timeout(400)
        assert page.locator("#detail-drawer").is_visible()
        assert page.locator(".fact-item").count() >= 1
        assert page.locator(".evidence-quote").count() >= 1
        if config["modes"]["demo"]["available"]:
            # Demo sources are explicitly fictional and must not be live links.
            assert page.locator(".source-title[href]").count() == 0
        page.screenshot(path=str(shots / "detail.png"))
        page.locator(".detail-drawer .drawer-close").click()
        page.wait_for_timeout(350)

        page.locator("#query-details summary").click()
        page.wait_for_timeout(200)
        assert page.locator(".query-item").count() >= 1

        page.locator("#history-btn").click()
        page.wait_for_timeout(400)
        assert page.locator("#history-layer").is_visible()
        assert page.locator(".history-item").count() >= 1
        page.locator("#history-layer .drawer-close").click()
        page.wait_for_timeout(300)

        if page.locator("#radar-settings-btn").is_visible():
            page.locator("#radar-settings-btn").click()
            page.wait_for_timeout(300)
            page.screenshot(path=str(shots / "home.png"), full_page=True)

        if not config["modes"]["live"]["available"]:
            page.locator('#mode-segmented button[data-mode="live"]').click()
            page.locator("#scan-btn").click()
            page.wait_for_timeout(500)
            assert page.locator("#inline-error").is_visible()
            assert "缺少服务端配置" in page.locator("#error-text").inner_text()
            page.locator("#dismiss-error").click()
            page.locator('#mode-segmented button[data-mode="demo"]').click()
            # The browser logs the intentionally handled HTTP 400 as a resource
            # console error; page errors and other console errors still fail.
            console_errors[:] = [
                item
                for item in console_errors
                if "status of 400" not in item
            ]

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        page.screenshot(path=str(shots / "mobile.png"), full_page=True)
        overflow = page.evaluate(
            "document.documentElement.scrollWidth > window.innerWidth + 1"
        )
        assert not overflow, "horizontal overflow on mobile viewport"
        browser.close()

    assert not page_errors, page_errors
    assert not console_errors, console_errors
    assert not failed_requests, failed_requests
    print(
        json.dumps(
            {
                "ok": True,
                "cards": cards,
                "console_errors": console_errors,
                "page_errors": page_errors,
                "failed_requests": failed_requests,
                "screenshots": [
                    str(shots / name)
                    for name in (
                        "interest.png",
                        "interest-round2.png",
                        "radar.png",
                        "home.png",
                        "detail.png",
                        "mobile.png",
                    )
                ],
                "live_configured": config["modes"]["live"]["available"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"BROWSER SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
