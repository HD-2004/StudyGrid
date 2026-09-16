"""Smoke a deployed StudyGrid instance without relying on fixed IDs or dates.

Set STUDYGRID_BASE_URL to the deployment origin. The check creates one small
plan and deletes it in a finally block so repeated runs do not accumulate data.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx


BASE_URL = os.getenv("STUDYGRID_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("STUDYGRID_SMOKE_TIMEOUT", "20"))
EXPECT_DURABLE = os.getenv("STUDYGRID_EXPECT_DURABLE", "true").lower() in {
    "1",
    "true",
    "yes",
}


def main() -> None:
    start = date.today()
    plan_id: str | None = None

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert health.json() == {"status": "ok"}

        page = client.get("/")
        page.raise_for_status()
        assert "StudyGrid" in page.text

        reasons = client.get("/api/miss-reasons")
        reasons.raise_for_status()
        assert reasons.json(), "miss-reason contract returned no options"

        privacy = client.get("/api/privacy")
        privacy.raise_for_status()
        assert privacy.json()["anonymous_session"] is True
        assert privacy.json()["durable_storage"] is EXPECT_DURABLE

        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"

        payload = {
            "start_date": start.isoformat(),
            "strategy": "fresh",
            "subjects": [
                {
                    "name": "Deployment smoke subject",
                    "exam_date": (start + timedelta(days=10)).isoformat(),
                    "priority": 3,
                    "topics": [
                        {
                            "name": "Deployment smoke topic",
                            "difficulty": "medium",
                            "estimated_minutes": 45,
                        }
                    ],
                }
            ],
            "availability": {
                "weekday_minutes": {str(day): 90 for day in range(7)},
                "session_length_minutes": 45,
                "long_break_minutes": 45,
                "busy": [],
            },
        }

        try:
            created = client.post("/api/plan", json=payload)
            created.raise_for_status()
            plan = created.json()
            plan_id = plan["plan_id"]
            assert plan["sessions"], "deployment created an empty plan"

            events = client.get(f"/api/plan/{plan_id}/events")
            events.raise_for_status()
            assert len(events.json()) == len(plan["sessions"])
        finally:
            if plan_id:
                deleted = client.delete(f"/api/plan/{plan_id}")
                deleted.raise_for_status()

    print(f"production smoke passed: {BASE_URL}")


if __name__ == "__main__":
    main()
