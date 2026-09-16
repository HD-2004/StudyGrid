r"""SQLite durability and anonymous multi-user isolation smoke test.

Run: .venv\Scripts\python.exe scripts\smoke_persistence.py
"""

from __future__ import annotations

import sys
import os
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.api.routes import get_repo
from app.main import app
from app.security import build_session_settings
from app.store import SqliteRepository


def payload(subject: str) -> dict[str, object]:
    start = date.today()
    return {
        "start_date": start.isoformat(),
        "strategy": "fresh",
        "subjects": [
            {
                "name": subject,
                "exam_date": (start + timedelta(days=12)).isoformat(),
                "priority": 3,
                "topics": [
                    {
                        "name": "Persistence",
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


with patch.dict(
    os.environ,
    {"ENVIRONMENT": "production", "SESSION_SECRET": "too-short"},
):
    try:
        build_session_settings()
    except RuntimeError as error:
        assert "at least 32 bytes" in str(error)
    else:
        raise AssertionError("production accepted a weak SESSION_SECRET")
print("[ok] production rejects a session secret shorter than 32 bytes")


with TemporaryDirectory(prefix="studygrid-") as directory:
    database = Path(directory) / "studygrid.db"
    repository = SqliteRepository(database, retention_days=14)
    app.dependency_overrides[get_repo] = lambda: repository

    try:
        with TestClient(app) as alice, TestClient(app) as bob:
            privacy = alice.get("/api/privacy")
            assert privacy.status_code == 200, privacy.text
            assert privacy.json() == {
                "anonymous_session": True,
                "durable_storage": True,
                "retention_days": 14,
            }

            created = alice.post("/api/plan", json=payload("Alice subject"))
            assert created.status_code == 200, created.text
            alice_plan = created.json()
            alice_id = alice_plan["plan_id"]

            assert alice.get(f"/api/plan/{alice_id}/events").status_code == 200
            assert bob.get(f"/api/plan/{alice_id}/events").status_code == 404
            assert bob.delete(f"/api/plan/{alice_id}").status_code == 404
            assert bob.get("/api/plan/latest").json() is None
            print("[ok] one anonymous browser cannot read or delete another browser's plan")

            alice_cookie = alice.cookies.get("studygrid_session")
            assert alice_cookie and "." in alice_cookie
            replacement = "a" if alice_cookie[-1] != "a" else "b"
            with TestClient(app) as tampered:
                tampered.cookies.set("studygrid_session", alice_cookie[:-1] + replacement)
                assert tampered.get(f"/api/plan/{alice_id}/events").status_code == 404
            print("[ok] a tampered owner cookie cannot impersonate another browser")

            bob_created = bob.post("/api/plan", json=payload("Bob subject"))
            assert bob_created.status_code == 200, bob_created.text
            bob_id = bob_created.json()["plan_id"]

            # Simulate a process/repository restart while preserving the same DB.
            restarted = SqliteRepository(database, retention_days=14)
            app.dependency_overrides[get_repo] = lambda: restarted
            latest = alice.get("/api/plan/latest")
            assert latest.status_code == 200, latest.text
            assert latest.json()["plan_id"] == alice_id

            first_session = latest.json()["sessions"][0]
            adapted = alice.post(
                "/api/progress",
                json={
                    "plan_id": alice_id,
                    "session_id": first_session["id"],
                    "completion": "completed",
                    "recall": "poor",
                },
            )
            assert adapted.status_code == 200, adapted.text
            assert adapted.json()["changes"], "restored allocator did not adapt the plan"
            print("[ok] plan and allocator state survive a SQLite repository restart")

            erased = alice.delete("/api/session")
            assert erased.status_code == 204, erased.text
            assert alice.get("/api/plan/latest").json() is None
            assert bob.get(f"/api/plan/{bob_id}/events").status_code == 200
            print("[ok] delete-my-data removes only the current browser's records")
    finally:
        app.dependency_overrides.pop(get_repo, None)

print("\npersistence smoke passed")
