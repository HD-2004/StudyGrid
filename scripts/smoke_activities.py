"""Smoke checks for owner-scoped activity analytics and study-session sync."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.api.routes import get_repo
from app.main import app
from app.models import ActivityCategory, ActivityLog
from app.store import InMemoryRepository, SqliteRepository


def plan_payload() -> dict:
    today = date.today()
    return {
        "strategy": "fresh",
        "start_date": today.isoformat(),
        "subjects": [
            {
                "name": "Linear Algebra",
                "exam_date": (today + timedelta(days=14)).isoformat(),
                "priority": 4,
                "topics": [
                    {
                        "name": "Vectors",
                        "difficulty": "medium",
                        "estimated_minutes": 60,
                    }
                ],
            }
        ],
        "availability": {
            "weekday_minutes": {str(day): 120 for day in range(7)},
            "earliest": "09:00",
            "latest": "18:00",
            "session_length_minutes": 60,
            "long_break_minutes": 45,
            "busy": [],
        },
    }


repo = InMemoryRepository()
app.dependency_overrides[get_repo] = lambda: repo
try:
    with TestClient(app) as owner, TestClient(app) as stranger:
        today = date.today().isoformat()
        created = owner.post(
            "/api/activities",
            json={
                "occurred_on": today,
                "category": "work",
                "label": "Project shift",
                "minutes": 90,
                "note": "Unexpected deadline",
            },
        )
        assert created.status_code == 201, created.text
        activity_id = created.json()["id"]

        dashboard = owner.get(f"/api/activities?days=7&end={today}")
        assert dashboard.status_code == 200
        assert next(item for item in dashboard.json()["totals"] if item["category"] == "work")["minutes"] == 90
        assert stranger.get(f"/api/activities?days=7&end={today}").json()["activities"] == []
        print("[ok] manual activities are owner-scoped and aggregated")

        updated = owner.put(
            f"/api/activities/{activity_id}",
            json={
                "occurred_on": today,
                "category": "unexpected",
                "label": "Urgent project work",
                "minutes": 120,
                "note": "",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["minutes"] == 120
        assert stranger.delete(f"/api/activities/{activity_id}").status_code == 404
        print("[ok] activity update/delete cannot cross browser owners")

        plan = owner.post("/api/plan", json=plan_payload())
        assert plan.status_code == 200, plan.text
        plan_id = plan.json()["plan_id"]
        event = owner.get(f"/api/plan/{plan_id}/events").json()[0]
        progress = owner.post(
            "/api/progress",
            json={
                "plan_id": plan_id,
                "session_id": event["id"],
                "completion": "completed",
                "recall": "well",
                "miss_reason": None,
            },
        )
        assert progress.status_code == 200, progress.text
        synced = owner.get(f"/api/activities?days=30&end={(date.today() + timedelta(days=14)).isoformat()}").json()
        assert any(item["source"] == "study_session" for item in synced["activities"])
        print("[ok] completed study session syncs into Progress analytics")

        assert owner.delete(f"/api/activities/{activity_id}").status_code == 204
finally:
    app.dependency_overrides.clear()

with TemporaryDirectory() as temporary:
    database = Path(temporary) / "activity.db"
    first = SqliteRepository(database)
    activity = ActivityLog(
        occurred_on=date.today(),
        category=ActivityCategory.rest,
        label="Recovery",
        minutes=45,
    )
    first.save_activity(activity, "owner-a")
    reopened = SqliteRepository(database)
    restored = reopened.load_activity(activity.id, "owner-a")
    assert restored is not None and restored.minutes == 45
    assert reopened.load_activity(activity.id, "owner-b") is None
    print("[ok] activity logs survive SQLite restart and remain owner-scoped")

print("activity smoke passed")
