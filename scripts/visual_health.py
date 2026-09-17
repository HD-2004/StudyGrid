"""Seed Health Connect aggregates and capture the Progress health dashboard."""

from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("STUDYGRID_VISUAL_BASE", "http://127.0.0.1:5173")
OUTPUT = Path(__file__).resolve().parent.parent / "artifacts" / "health-progress.png"
CALENDAR_OUTPUT = Path(__file__).resolve().parent.parent / "artifacts" / "health-calendar.png"


def require_ok(response, label: str) -> dict:
    assert response.ok, f"{label}: HTTP {response.status} {response.text()}"
    return response.json()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1600, "height": 1000}, color_scheme="dark")
    api = context.request
    today = date.today()
    plan = require_ok(api.post(f"{BASE}/api/plan", data={
        "strategy": "fresh",
        "start_date": today.isoformat(),
        "subjects": [
            {
                "name": "Global Hackathon",
                "exam_date": (today + timedelta(days=2)).isoformat(),
                "priority": 5,
                "topics": [{"name": "Demo story", "estimated_minutes": 120}],
            },
            {
                "name": "Machine Learning",
                "exam_date": (today + timedelta(days=18)).isoformat(),
                "priority": 2,
                "topics": [{"name": "Foundation", "estimated_minutes": 180}],
            },
        ],
        "availability": {
            "weekday_minutes": {str(day): 240 for day in range(7)},
            "earliest": "08:00",
            "latest": "21:00",
            "session_length_minutes": 60,
            "long_break_minutes": 45,
            "busy": [],
        },
    }), "create plan")
    pairing = require_ok(api.post(f"{BASE}/api/health/pairing", data={"plan_id": plan["plan_id"]}), "pair")
    claim = require_ok(api.post(f"{BASE}/api/health/pairing/claim", data={"code": pairing["code"]}), "claim")
    summaries = [
        {
            "occurred_on": (today - timedelta(days=offset)).isoformat(),
            "sleep_minutes": 470 + (offset % 3) * 10,
            "resting_heart_rate_bpm": 60 + (offset % 2),
            "hrv_rmssd_ms": 50 - offset,
            "source_devices": ["Galaxy Watch"],
        }
        for offset in range(6, 0, -1)
    ]
    summaries.append({
        "occurred_on": today.isoformat(),
        "sleep_minutes": 330,
        "resting_heart_rate_bpm": 73,
        "hrv_rmssd_ms": 31,
        "energy_level": 2,
        "source_devices": ["Galaxy Watch"],
    })
    require_ok(api.post(
        f"{BASE}/api/health/sync",
        headers={"Authorization": f"Bearer {claim['access_token']}"},
        data={
            "summaries": summaries,
            "permissions": ["sleep", "resting_heart_rate", "hrv"],
            "sources": ["Galaxy Watch"],
        },
    ), "sync")

    page = context.new_page()
    page.goto(BASE, wait_until="networkidle")
    page.locator(".calendar-readiness").wait_for()
    page.screenshot(path=str(CALENDAR_OUTPUT), full_page=True)
    page.get_by_role("button", name="Tiến độ", exact=True).first.click()
    page.locator(".health-section").wait_for()
    page.screenshot(path=str(OUTPUT), full_page=True)
    print(OUTPUT)
    browser.close()
