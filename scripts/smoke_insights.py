"""Checks for miss-reason capture and time-use insights (HACKATHON.md 8.3).

Run: .venv\\Scripts\\python.exe scripts\\smoke_insights.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.insights import MIN_FOR_PATTERNS, build_insights
from app.main import app
from app.models import Completion, MissReason, Recall

client = TestClient(app)
START = date(2026, 9, 21)

# Reason options come from the backend so the UI cannot drift out of sync.
r = client.get("/api/miss-reasons")
assert r.status_code == 200, r.text
options = r.json()
assert len(options) == len(MissReason), "every reason must be offered"
assert {o["value"] for o in options} == {m.value for m in MissReason}
assert all(o["label"] for o in options), "every reason needs a label"
print(f"[ok] {len(options)} miss reasons served, e.g. {options[0]['label']!r}")

payload = {
    "start_date": START.isoformat(),
    "strategy": "fresh",
    "subjects": [
        {
            "name": "Statistics",
            "exam_date": (START + timedelta(days=25)).isoformat(),
            "priority": 4,
            "topics": [
                {"name": f"Unit {i}", "difficulty": "medium", "estimated_minutes": 50}
                for i in range(1, 7)
            ],
        }
    ],
    "availability": {
        "weekday_minutes": {"0": 120, "1": 120, "2": 120, "3": 120, "4": 120, "5": 120},
        "session_length_minutes": 50,
    },
}

plan = client.post("/api/plan", json=payload).json()
plan_id = plan["plan_id"]

# Empty state must invite action, not show a wall of zeros.
empty = client.get(f"/api/plan/{plan_id}/insights").json()
assert empty["sessions_logged"] == 0
assert empty["confident"] is False
assert empty["observations"], "empty state needs a prompt"
print(f"[ok] empty insights: {empty['observations'][0]}")

# Log a mix of outcomes, including two missed for the same reason.
outcomes = [
    ("completed", "well", None),
    ("completed", "medium", None),
    ("not_completed", None, "club"),
    ("not_completed", None, "club"),
    ("partial", "poor", "mood"),
    ("completed", "well", None),
]

sessions = plan["sessions"]
assert len(sessions) >= len(outcomes), "need enough sessions to log"

for (completion, recall, reason), session in zip(outcomes, sessions):
    body = {
        "plan_id": plan_id,
        "session_id": session["id"],
        "completion": completion,
        "recall": recall,
        "miss_reason": reason,
    }
    resp = client.post("/api/progress", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["insights"] is not None, "progress should return insights"

ins = client.get(f"/api/plan/{plan_id}/insights").json()
print(f"[ok] logged {ins['sessions_logged']} sessions: "
      f"{ins['completed']} done, {ins['missed']} missed, {ins['partial']} partial")

assert ins["sessions_logged"] == len(outcomes)
assert ins["completed"] == 3
assert ins["missed"] == 2
assert ins["partial"] == 1

# Reasons must be ranked by lost time, with club top at two occurrences.
reasons = ins["reasons"]
assert reasons, "reasons must be aggregated"
assert reasons[0]["reason"] == "club", f"expected club first, got {reasons[0]}"
assert reasons[0]["count"] == 2
assert reasons[0]["minutes_lost"] > 0
print(f"[ok] top reason: {reasons[0]['label']} "
      f"({reasons[0]['count']}x, {reasons[0]['minutes_lost']} min lost)")

# A rescheduled miss must still be counted. This is the regression that the
# history log exists to prevent: rescheduling rewrites the session in place.
assert ins["missed"] == 2, "rescheduling must not erase the record of a miss"
print("[ok] misses survive rescheduling")

assert ins["minutes_studied"] > 0 and ins["minutes_lost"] > 0
assert ins["recall_mix"]["well"] == 2
assert ins["recall_mix"]["poor"] == 1
print(f"[ok] {ins['minutes_studied']} min studied, {ins['minutes_lost']} min lost")

assert ins["confident"] is True, f"{len(outcomes)} >= {MIN_FOR_PATTERNS} should be confident"
assert ins["observations"], "confident report needs observations"
for line in ins["observations"]:
    print(f"     - {line}")

# Small samples must not claim patterns.
thin = build_insights([])
assert thin.confident is False and thin.weak_weekdays == []
print("[ok] small samples withhold pattern claims")

assert client.get("/api/plan/missing/insights").status_code == 404
print("[ok] unknown plan returns 404")

print("\ninsights smoke passed")
