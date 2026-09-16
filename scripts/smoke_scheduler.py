"""Smoke check for the scheduling core. Run: python scripts/smoke_scheduler.py

Asserts the invariants the calendar depends on: no overlaps, nothing inside a
fixed commitment, nothing past an exam, daily budgets respected.
"""

import sys
from datetime import date, timedelta, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    Availability,
    BusyBlock,
    Completion,
    Difficulty,
    PlanRequest,
    Recall,
    Strategy,
    Subject,
    Topic,
)
from app.scheduler import build_plan, record_progress

START = date(2026, 9, 21)  # a Monday

AVAILABILITY = Availability(
    weekday_minutes={0: 120, 1: 120, 2: 60, 3: 120, 4: 60, 5: 180, 6: 0},
    session_length_minutes=50,
    busy=[
        BusyBlock(weekday=0, start=time(9, 0), end=time(11, 0), label="Lecture"),
        BusyBlock(weekday=1, start=time(14, 0), end=time(16, 0), label="Lab"),
    ],
)

SUBJECTS = [
    Subject(
        name="Linear Algebra",
        exam_date=START + timedelta(days=18),
        priority=5,
        topics=[
            Topic(name="Vectors", difficulty=Difficulty.easy, estimated_minutes=50),
            Topic(
                name="Eigenvalues",
                difficulty=Difficulty.hard,
                estimated_minutes=120,
                depends_on=["Vectors"],
            ),
        ],
    ),
    Subject(
        name="Biology",
        exam_date=START + timedelta(days=10),
        priority=3,
        topics=[Topic(name="Cell Division", difficulty=Difficulty.easy, estimated_minutes=50)],
    ),
]

EXAMS = {s.name: s.exam_date for s in SUBJECTS}


def check_invariants(plan, availability, label, exams=None):
    exams = exams if exams is not None else EXAMS
    by_day = {}
    for s in plan.sessions:
        by_day.setdefault(s.start.date(), []).append(s)

    for day, items in by_day.items():
        items.sort(key=lambda s: s.start)
        for a, b in zip(items, items[1:]):
            assert a.end <= b.start, f"[{label}] overlap on {day}: {a.topic} / {b.topic}"

        budget = availability.weekday_minutes.get(day.weekday(), 0)
        used = sum(s.duration_minutes for s in items)
        assert used <= budget, f"[{label}] {day} over budget: {used} > {budget}"

        for s in items:
            assert s.start.time() >= availability.earliest, f"[{label}] {s.topic} too early"
            assert s.end.time() <= availability.latest, f"[{label}] {s.topic} too late"
            for block in availability.busy:
                if block.weekday != day.weekday():
                    continue
                assert not (
                    s.start.time() < block.end and s.end.time() > block.start
                ), f"[{label}] {s.topic} collides with {block.label} on {day}"

    for s in plan.sessions:
        assert s.start.date() < exams[s.subject], f"[{label}] {s.topic} on/after exam"

    for a, b in zip(plan.sessions, plan.sessions[1:]):
        assert a.start <= b.start, f"[{label}] sessions not sorted"


# --- Entry point 1: fresh start ------------------------------------------
plan, allocator = build_plan(
    PlanRequest(subjects=SUBJECTS, availability=AVAILABILITY, start_date=START)
)
print("FRESH:", plan.summary)
for s in plan.sessions:
    print(f"  {s.start:%a %m-%d %H:%M}-{s.end:%H:%M}  r{s.repetition}  "
          f"{s.subject} / {s.topic}  ({s.rationale})")
for w in plan.warnings:
    print("  warning:", w)
check_invariants(plan, AVAILABILITY, "fresh")
assert plan.sessions, "expected sessions"

# Monday sessions must start after the 09:00-11:00 lecture.
mondays = [s for s in plan.sessions if s.start.weekday() == 0]
assert mondays, "expected at least one Monday session"
for s in mondays:
    assert s.start.time() >= time(11, 0), f"Monday session at {s.start.time()} hits lecture"
print(f"  [ok] {len(mondays)} Monday sessions all after the lecture")

# Dependency: Vectors before Eigenvalues.
first_vectors = min(s.start for s in plan.sessions if s.topic == "Vectors")
first_eigen = min(s.start for s in plan.sessions if s.topic == "Eigenvalues")
assert first_vectors < first_eigen, "prerequisite scheduled after dependent topic"
print("  [ok] prerequisite ordering respected")

# --- Progress: poor recall triggers an extra review ----------------------
target = next(s for s in plan.sessions if s.topic == "Eigenvalues")
before = len(plan.sessions)
plan, changes = record_progress(plan, target, Completion.completed, Recall.poor, allocator, EXAMS)
assert len(plan.sessions) == before + 1, "poor recall should add a review"
check_invariants(plan, AVAILABILITY, "poor-recall")
extra = [s for s in plan.sessions if "recall was poor" in s.rationale]
print(f"\nPOOR RECALL: added review on {extra[0].start:%a %m-%d %H:%M}")
assert changes, "adaptation must be reported to the UI"
assert changes[0].type.value == "added", f"expected an added review, got {changes[0].type}"
print(f"  change reported: {changes[0].why}")

# --- Progress: missed session moves, never disappears -------------------
missed = next(s for s in plan.sessions if s.completion == Completion.planned)
before = len(plan.sessions)
old_start = missed.start
plan, changes2 = record_progress(plan, missed, Completion.not_completed, None, allocator, EXAMS)
assert len(plan.sessions) == before, "reschedule must not drop or duplicate sessions"
moved = [s for s in plan.sessions if s.topic == missed.topic and s.start > old_start]
assert moved, "missed session should move later"
check_invariants(plan, AVAILABILITY, "missed")
assert changes2 and changes2[0].type.value in ("moved", "blocked")
assert {s.id for s in plan.sessions}.__len__() == len(plan.sessions), "session ids must be unique"
print(f"MISSED: {missed.topic} moved off {old_start:%a %m-%d %H:%M}")
print(f"  change reported: {changes2[0].why}")

# --- Entry point 3: exam rush -------------------------------------------
rush_subject = Subject(
    name="Chemistry",
    exam_date=START + timedelta(days=3),
    priority=5,
    topics=[
        Topic(name=f"Unit {i}", difficulty=Difficulty.hard, estimated_minutes=150)
        for i in range(1, 7)
    ],
)
rush_plan, _ = build_plan(
    PlanRequest(
        subjects=[rush_subject],
        availability=AVAILABILITY,
        start_date=START,
        strategy=Strategy.exam_rush,
    )
)
print(f"\nEXAM RUSH: {rush_plan.summary}")
check_invariants(rush_plan, AVAILABILITY, "rush", {rush_subject.name: rush_subject.exam_date})
topics_covered = {s.topic for s in rush_plan.sessions}
assert all(s.repetition == 1 for s in rush_plan.sessions), "rush should not add reviews"
print(f"  covered {len(topics_covered)} of 6 units; "
      f"{len(rush_plan.unscheduled)} could not fit")
assert rush_plan.unscheduled, "tight deadline should report unscheduled work honestly"

# --- Edge case: empty availability --------------------------------------
empty_plan, _ = build_plan(
    PlanRequest(
        subjects=SUBJECTS,
        availability=Availability(weekday_minutes={}),
        start_date=START,
    )
)
assert empty_plan.sessions == [], "no availability means no sessions"
assert empty_plan.warnings, "should warn on empty availability"
print("\n[ok] empty availability handled")

print("\nall invariants passed")
