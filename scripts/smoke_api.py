"""End-to-end API check against the real app, no server needed.

Run: .venv\\Scripts\\python.exe scripts\\smoke_api.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.ai import MaterialAnalyzer
from app.api.routes import get_material_analyzer
from app.main import app

client = TestClient(app)
START = date(2026, 9, 21)

assert client.get("/health").json() == {"status": "ok"}
print("[ok] health")

# Material analysis must remain useful with no network or API key.
app.dependency_overrides[get_material_analyzer] = lambda: MaterialAnalyzer()
r = client.post(
    "/api/analyze",
    json={
        "subject": "Biology",
        "text": """# Cell Biology
- Cell structure and organelles
- Cell division
- Advanced gene regulation
""",
    },
)
assert r.status_code == 200, f"{r.status_code}: {r.text}"
analysis = r.json()
assert analysis["source"] == "fallback"
assert len(analysis["topics"]) >= 3
assert all(
    {"name", "difficulty", "estimated_minutes", "depends_on"} <= set(topic)
    for topic in analysis["topics"]
)
assert client.post(
    "/api/analyze", json={"subject": "Biology", "text": "   "}
).status_code == 422
app.dependency_overrides.pop(get_material_analyzer)
print(f"[ok] POST /api/analyze -> {len(analysis['topics'])} fallback topics")

payload = {
    "start_date": START.isoformat(),
    "strategy": "fresh",
    "subjects": [
        {
            "name": "Linear Algebra",
            "exam_date": (START + timedelta(days=14)).isoformat(),
            "priority": 5,
            "topics": [
                {"name": "Vectors", "difficulty": "easy", "estimated_minutes": 50},
                {"name": "Eigenvalues", "difficulty": "hard", "estimated_minutes": 100},
            ],
        }
    ],
    "availability": {
        "weekday_minutes": {"0": 120, "1": 120, "2": 60, "3": 120, "4": 60, "5": 180},
        "session_length_minutes": 50,
        "busy": [
            {"weekday": 0, "start": "09:00:00", "end": "11:00:00", "label": "Lecture"}
        ],
    },
}

r = client.post("/api/plan", json=payload)
assert r.status_code == 200, f"{r.status_code}: {r.text}"
plan = r.json()
plan_id = plan["plan_id"]
print(f"[ok] POST /api/plan -> {plan['summary']}")
assert plan["sessions"], "expected sessions"

# Calendar shape must be directly consumable by Schedule-X.
r = client.get(f"/api/plan/{plan_id}/events")
assert r.status_code == 200, r.text
events = r.json()
assert len(events) == len(plan["sessions"])
sample = events[0]
for key in ("id", "title", "start", "end", "is_review"):
    assert key in sample, f"calendar event missing {key}"
from datetime import datetime as _dt

_dt.fromisoformat(sample["start"])  # must be parseable by Temporal on the client
assert len(sample["start"]) == 19, f"unexpected start format: {sample['start']}"
print(f"[ok] GET events -> {len(events)} events, e.g. {sample['title']!r} "
      f"at {sample['start']}")

# Progress: poor recall should add a review and report the change.
first = plan["sessions"][0]
r = client.post(
    "/api/progress",
    json={
        "plan_id": plan_id,
        "session_id": first["id"],
        "completion": "completed",
        "recall": "poor",
    },
)
assert r.status_code == 200, r.text
body = r.json()
assert len(body["sessions"]) == len(plan["sessions"]) + 1, "expected an extra review"
assert body["changes"], "adaptation must be reported"
print(f"[ok] POST /api/progress -> {body['changes'][0]['why']}")

# Adaptation must survive a reload, proving it was persisted.
r = client.get(f"/api/plan/{plan_id}/events")
assert len(r.json()) == len(plan["sessions"]) + 1, "change did not persist"
print("[ok] adaptation persisted")

# Error paths.
assert client.get("/api/plan/nope/events").status_code == 404
assert client.post(
    "/api/progress",
    json={"plan_id": plan_id, "session_id": "nope", "completion": "completed"},
).status_code == 404
assert client.post("/api/plan", json={**payload, "subjects": []}).status_code == 422
print("[ok] 404 and 422 paths")

print("\napi smoke passed")
