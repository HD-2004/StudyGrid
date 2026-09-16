"""End-to-end API check against the real app, no server needed.

Run: .venv\\Scripts\\python.exe scripts\\smoke_api.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.ai import MaterialAnalyzer, StudyCoach
from app.api.routes import get_material_analyzer, get_study_coach
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

# Study Coach must use the stored plan, persist bounded history, and retain a
# deterministic path when no AI provider is configured.
app.dependency_overrides[get_study_coach] = lambda: StudyCoach()
r = client.post(
    "/api/chat",
    json={"plan_id": plan_id, "message": "What should I study next?"},
)
assert r.status_code == 200, r.text
chat = r.json()
assert chat["source"] == "fallback"
assert len(chat["history"]) == 2
first_topic = plan["sessions"][0]["topic"]
assert first_topic in chat["reply"]["content"]

r = client.post(
    "/api/chat",
    json={
        "plan_id": plan_id,
        "session_id": plan["sessions"][0]["id"],
        "message": "Why this session?",
    },
)
assert r.status_code == 200, r.text
assert len(r.json()["history"]) == 4, "chat history should persist per plan"
assert client.post(
    "/api/chat", json={"plan_id": "nope", "message": "What next?"}
).status_code == 404
assert client.post(
    "/api/chat", json={"plan_id": plan_id, "message": "   "}
).status_code == 422
app.dependency_overrides.pop(get_study_coach)
print("[ok] POST /api/chat -> grounded reply with persistent history")

# Progress: poor recall should adapt the next review and report the change.
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
assert body["changes"], "adaptation must be reported"
next_reviews = [
    s
    for s in body["sessions"]
    if s["subject"] == first["subject"]
    and s["topic"] == first["topic"]
    and s["repetition"] > 1
    and s["start"] > first["start"]
]
assert next_reviews, "adaptive review is missing"
print(f"[ok] POST /api/progress -> {body['changes'][0]['why']}")

# Adaptation must survive a reload, proving it was persisted.
r = client.get(f"/api/plan/{plan_id}/events")
assert len(r.json()) == len(body["sessions"]), "change did not persist"
print("[ok] adaptation persisted")

# Manual calendar CRUD: cancellation removes the old block, captures a reason,
# previews the next seven days, and creates a fresh attempt only after consent.
manual_start = START + timedelta(days=7)
r = client.post(
    f"/api/plan/{plan_id}/sessions",
    json={
        "subject": "Capstone",
        "topic": "Demo polish",
        "start": f"{manual_start.isoformat()}T18:00:00",
        "end": f"{manual_start.isoformat()}T19:00:00",
        "deadline": (manual_start + timedelta(days=14)).isoformat(),
    },
)
assert r.status_code == 201, r.text
manual = r.json()
assert manual["completion"] == "planned"

moved_day = manual_start + timedelta(days=1)
r = client.put(
    f"/api/plan/{plan_id}/sessions/{manual['id']}",
    json={
        "subject": "Capstone",
        "topic": "Demo polish and rehearsal",
        "start": f"{moved_day.isoformat()}T18:30:00",
        "end": f"{moved_day.isoformat()}T19:30:00",
    },
)
assert r.status_code == 200, r.text
edited = r.json()
assert edited["topic"] == "Demo polish and rehearsal"
assert edited["start"].endswith("18:30:00")

r = client.post(
    "/api/progress",
    json={
        "plan_id": plan_id,
        "session_id": manual["id"],
        "completion": "not_completed",
        "miss_reason": "work",
    },
)
assert r.status_code == 200, r.text
cancelled = r.json()
change = next(change for change in cancelled["changes"] if change["session_id"] == manual["id"])
assert change["type"] == "cancelled"
assert all(item["id"] != manual["id"] for item in cancelled["sessions"])
assert cancelled["reschedule"]["status"] == "full_slot"

r = client.post(
    "/api/reschedule",
    json={
        "plan_id": plan_id,
        "source_session_id": manual["id"],
        "action": "accept_full",
    },
)
assert r.status_code == 200, r.text
rescheduled = r.json()
assert rescheduled["reschedule"]["status"] == "scheduled"
replacement = next(
    item for item in rescheduled["sessions"] if item["rescheduled_from_id"] == manual["id"]
)
assert replacement["id"] != manual["id"]

r = client.get(f"/api/activities?days=7&end={date.today().isoformat()}")
assert r.status_code == 200, r.text
cancel_logs = [item for item in r.json()["activities"] if item["source"] == "cancelled_session"]
assert cancel_logs and cancel_logs[0]["category"] == "work"
print("[ok] calendar CRUD + cancel reason + consent-based reschedule + dashboard sync")

r = client.delete(f"/api/plan/{plan_id}/sessions/{replacement['id']}")
assert r.status_code == 204, r.text

# Reset removes only the requested plan and makes subsequent access fail.
r = client.delete(f"/api/plan/{plan_id}")
assert r.status_code == 204, r.text
assert client.get(f"/api/plan/{plan_id}/events").status_code == 404
assert client.delete(f"/api/plan/{plan_id}").status_code == 404
print("[ok] DELETE plan -> clean user-test reset")

# Error paths.
assert client.get("/api/plan/nope/events").status_code == 404
assert client.post(
    "/api/progress",
    json={"plan_id": plan_id, "session_id": "nope", "completion": "completed"},
).status_code == 404
assert client.post("/api/plan", json={**payload, "subjects": []}).status_code == 422
print("[ok] 404 and 422 paths")

print("\napi smoke passed")
