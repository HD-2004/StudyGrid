"""End-to-end smoke check for Health Connect pairing and readiness."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.api.routes import get_repo
from app.main import app
from app.store import InMemoryRepository


def plan_payload() -> dict:
    today = date.today()
    return {
        "strategy": "fresh",
        "start_date": today.isoformat(),
        "subjects": [
            {
                "name": "Urgent exam",
                "exam_date": (today + timedelta(days=2)).isoformat(),
                "priority": 5,
                "topics": [{"name": "Core review", "estimated_minutes": 60}],
            },
            {
                "name": "Flexible course",
                "exam_date": (today + timedelta(days=21)).isoformat(),
                "priority": 2,
                "topics": [{"name": "Optional chapter", "estimated_minutes": 120}],
            },
        ],
        "availability": {
            "weekday_minutes": {str(day): 180 for day in range(7)},
            "earliest": "09:00",
            "latest": "20:00",
            "session_length_minutes": 60,
            "long_break_minutes": 45,
            "busy": [],
        },
    }


repo = InMemoryRepository()
app.dependency_overrides[get_repo] = lambda: repo
try:
    with TestClient(app) as owner, TestClient(app) as stranger:
        created = owner.post("/api/plan", json=plan_payload())
        assert created.status_code == 200, created.text
        plan_id = created.json()["plan_id"]

        pairing = owner.post("/api/health/pairing", json={"plan_id": plan_id})
        assert pairing.status_code == 200, pairing.text
        code = pairing.json()["code"]
        assert stranger.get(f"/api/health/dashboard?plan_id={plan_id}").status_code == 404

        claimed = stranger.post("/api/health/pairing/claim", json={"code": code})
        assert claimed.status_code == 200, claimed.text
        token = claimed.json()["access_token"]
        assert stranger.post("/api/health/pairing/claim", json={"code": code}).status_code == 404
        print("[ok] one-use pairing code links the companion without sharing browser cookies")

        today = date.today()
        summaries = []
        for offset in range(5, 0, -1):
            summaries.append({
                "occurred_on": (today - timedelta(days=offset)).isoformat(),
                "sleep_minutes": 480,
                "resting_heart_rate_bpm": 60,
                "hrv_rmssd_ms": 52,
                "source_devices": ["Test watch"],
            })
        summaries.append({
            "occurred_on": today.isoformat(),
            "sleep_minutes": 300,
            "resting_heart_rate_bpm": 75,
            "hrv_rmssd_ms": 30,
            "energy_level": 2,
            "source_devices": ["Test watch"],
        })
        synced = stranger.post(
            "/api/health/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summaries": summaries,
                "permissions": ["sleep", "resting_heart_rate", "hrv"],
                "sources": ["Test watch"],
            },
        )
        assert synced.status_code == 200, synced.text

        dashboard = owner.get(
            f"/api/health/dashboard?plan_id={plan_id}&days=7&end={today.isoformat()}"
        )
        assert dashboard.status_code == 200, dashboard.text
        body = dashboard.json()
        assert body["readiness"]["status"] == "recovery", body["readiness"]
        assert body["connection"]["last_synced_at"]
        assert "token_hash" not in body["connection"]
        assert any(item["protected"] for item in body["recommendations"])
        print("[ok] daily aggregates produce explainable readiness and protect urgent work")

        paused = owner.post("/api/health/connection/pause", json={"plan_id": plan_id})
        assert paused.status_code == 200
        rejected = stranger.post(
            "/api/health/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={"summaries": [summaries[-1]]},
        )
        assert rejected.status_code == 409
        assert owner.post("/api/health/connection/resume", json={"plan_id": plan_id}).status_code == 200
        print("[ok] the browser can pause and resume companion sync")

        applied = owner.post(
            "/api/health/schedule/apply",
            json={"plan_id": plan_id, "occurred_on": today.isoformat()},
        )
        assert applied.status_code == 200, applied.text
        print("[ok] health adaptation requires an explicit apply request")

        assert owner.delete(f"/api/health/connection?plan_id={plan_id}").status_code == 204
        empty = owner.get(f"/api/health/dashboard?plan_id={plan_id}").json()
        assert empty["connection"] is None and empty["summaries"] == []
        print("[ok] disconnect deletes stored health summaries and revokes the token")
finally:
    app.dependency_overrides.clear()

print("health smoke passed")
