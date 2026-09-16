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
from app.scheduler import TimeAllocator, build_plan, record_progress

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


# --- Session duration and recovery policy --------------------------------
for duration, expected_break in ((30, 3), (60, 6), (90, 9), (120, 12), (75, 8)):
    availability = Availability(
        weekday_minutes={0: 600},
        session_length_minutes=duration,
    )
    assert availability.break_minutes == expected_break, (
        duration,
        availability.break_minutes,
    )
print("  [ok] short recovery is always 10% of the selected session length")

BREAK_AVAILABILITY = Availability(
    weekday_minutes={0: 300},
    earliest=time(9, 0),
    latest=time(18, 0),
    session_length_minutes=60,
    long_break_minutes=45,
)
break_allocator = TimeAllocator(BREAK_AVAILABILITY)
break_slots = [break_allocator.allocate(60, START, START) for _ in range(5)]
assert all(slot is not None for slot in break_slots)
confirmed_slots = [slot for slot in break_slots if slot is not None]
gaps = [
    int((current[0] - previous[1]).total_seconds() // 60)
    for previous, current in zip(confirmed_slots, confirmed_slots[1:])
]
assert gaps == [6, 6, 6, 45], gaps
print("  [ok] a configurable 45-minute long break follows 4 hours of study")

custom_break_availability = BREAK_AVAILABILITY.model_copy(
    update={"long_break_minutes": 35}
)
custom_break_allocator = TimeAllocator(custom_break_availability)
custom_slots = [
    custom_break_allocator.allocate(60, START, START) for _ in range(5)
]
assert custom_slots[3] is not None and custom_slots[4] is not None
assert int(
    (custom_slots[4][0] - custom_slots[3][1]).total_seconds() // 60
) == 35
print("  [ok] the user-selected long-break duration is respected")


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

# Dependency: every Vectors learning block must finish before Eigenvalues.
last_vectors = max(s.end for s in plan.sessions if s.topic == "Vectors" and s.repetition == 1)
first_eigen = min(s.start for s in plan.sessions if s.topic == "Eigenvalues")
assert last_vectors <= first_eigen, "prerequisite scheduled after dependent topic"
print("  [ok] prerequisite ordering respected")

# --- Priority + controlled subject interleaving --------------------------
MIXED_AVAILABILITY = Availability(
    weekday_minutes={day: 400 for day in range(7)},
    session_length_minutes=50,
)
MIXED_SUBJECTS = [
    Subject(
        name="High priority",
        exam_date=START + timedelta(days=20),
        priority=5,
        topics=[
            Topic(name=f"High {i}", estimated_minutes=50) for i in range(1, 5)
        ],
    ),
    Subject(
        name="Lower priority",
        exam_date=START + timedelta(days=20),
        priority=1,
        topics=[
            Topic(name=f"Low {i}", estimated_minutes=50) for i in range(1, 5)
        ],
    ),
]
mixed_request = PlanRequest(
    subjects=MIXED_SUBJECTS,
    availability=MIXED_AVAILABILITY,
    start_date=START,
    strategy=Strategy.exam_rush,
)
mixed_plan, _ = build_plan(mixed_request)
mixed_exams = {subject.name: subject.exam_date for subject in MIXED_SUBJECTS}
check_invariants(mixed_plan, MIXED_AVAILABILITY, "interleaving", mixed_exams)
mixed_first_passes = sorted(mixed_plan.sessions, key=lambda session: session.start)
mixed_sequence = [session.subject for session in mixed_first_passes]
assert mixed_sequence[0] == "High priority", mixed_sequence
assert all(
    not (a == b == c)
    for a, b, c in zip(mixed_sequence, mixed_sequence[1:], mixed_sequence[2:])
), f"subject streak exceeded two sessions: {mixed_sequence}"
assert all("priority" in session.rationale for session in mixed_first_passes)
assert all("interleaved" in session.rationale for session in mixed_first_passes)
for subject in MIXED_SUBJECTS:
    actual_topics = [
        session.topic
        for session in mixed_first_passes
        if session.subject == subject.name
    ]
    assert actual_topics == [topic.name for topic in subject.topics], actual_topics

# The algorithm is deterministic: the same request produces the same order.
mixed_plan_again, _ = build_plan(mixed_request)
assert [
    (session.subject, session.topic, session.start) for session in mixed_plan.sessions
] == [
    (session.subject, session.topic, session.start)
    for session in mixed_plan_again.sessions
]
print(f"  [ok] deterministic controlled interleaving: {' -> '.join(mixed_sequence)}")

# With only three slots, priority weighting gives the higher-priority subject
# two slots while the lower-priority subject still receives one interleaved slot.
SCARCE_AVAILABILITY = Availability(
    weekday_minutes={0: 150},
    session_length_minutes=50,
)
scarce_plan, _ = build_plan(
    PlanRequest(
        subjects=[
            subject.model_copy(update={"exam_date": START + timedelta(days=1)})
            for subject in MIXED_SUBJECTS
        ],
        availability=SCARCE_AVAILABILITY,
        start_date=START,
        strategy=Strategy.exam_rush,
    )
)
coverage = {
    subject: sum(1 for session in scarce_plan.sessions if session.subject == subject)
    for subject in ("High priority", "Lower priority")
}
assert coverage == {"High priority": 2, "Lower priority": 1}, coverage
print("  [ok] scarce time follows priority weights without starving another subject")

# Deadline urgency can outweigh a later high-priority subject.
urgent_subjects = [
    Subject(
        name="Exam tomorrow",
        exam_date=START + timedelta(days=1),
        priority=1,
        topics=[Topic(name="Urgent unit", estimated_minutes=50)],
    ),
    Subject(
        name="Later exam",
        exam_date=START + timedelta(days=30),
        priority=5,
        topics=[Topic(name="Later unit", estimated_minutes=50)],
    ),
]
urgent_plan, _ = build_plan(
    PlanRequest(
        subjects=urgent_subjects,
        availability=MIXED_AVAILABILITY,
        start_date=START,
        strategy=Strategy.exam_rush,
    )
)
assert urgent_plan.sessions[0].subject == "Exam tomorrow"
print("  [ok] imminent exam urgency can outweigh a later high priority")

# --- Progress: poor recall adapts the next provisional review ------------
target = next(s for s in plan.sessions if s.topic == "Eigenvalues")
plan, changes = record_progress(plan, target, Completion.completed, Recall.poor, allocator, EXAMS)
check_invariants(plan, AVAILABILITY, "poor-recall")
assert changes, "adaptation must be reported to the UI"
next_review = min(
    s.start
    for s in plan.sessions
    if s.subject == target.subject
    and s.topic == target.topic
    and s.repetition > 1
    and s.start > target.start
)
print(f"\nPOOR RECALL: next review on {next_review:%a %m-%d %H:%M}")
print(f"  change reported: {changes[0].why}")


def adaptive_fixture(exam_in_days=90, difficulty=Difficulty.hard):
    availability = Availability(
        weekday_minutes={day: 300 for day in range(7)},
        session_length_minutes=50,
    )
    subject = Subject(
        name="Adaptive Learning",
        exam_date=START + timedelta(days=exam_in_days),
        topics=[Topic(name="Retrieval", difficulty=difficulty, estimated_minutes=50)],
    )
    adaptive_plan, adaptive_allocator = build_plan(
        PlanRequest(
            subjects=[subject],
            availability=availability,
            start_date=START,
        )
    )
    return adaptive_plan, adaptive_allocator, availability, {subject.name: subject.exam_date}


def next_gap(adaptive_plan, current):
    review = min(
        (
            s
            for s in adaptive_plan.sessions
            if s.subject == current.subject
            and s.topic == current.topic
            and s.repetition > 1
            and s.start > current.start
        ),
        key=lambda s: s.start,
    )
    return (review.start.date() - current.start.date()).days, review


# Initial placeholders use the expanding baseline from the product rule.
adaptive_plan, adaptive_allocator, adaptive_availability, adaptive_exams = adaptive_fixture()
first = next(s for s in adaptive_plan.sessions if s.repetition == 1)
initial_offsets = [
    (s.start.date() - first.start.date()).days
    for s in adaptive_plan.sessions
    if s.repetition > 1
]
assert initial_offsets[:6] == [1, 3, 7, 14, 30, 60], initial_offsets

# Strong recall expands to 7 days, then to 14 after another successful review.
adaptive_plan, strong_changes = record_progress(
    adaptive_plan,
    first,
    Completion.completed,
    Recall.well,
    adaptive_allocator,
    adaptive_exams,
)
gap, strong_review = next_gap(adaptive_plan, first)
assert gap == 7, f"first strong retrieval should target 7 days, got {gap}"
assert strong_changes and strong_changes[0].type.value in ("moved", "kept")

adaptive_plan, stronger_changes = record_progress(
    adaptive_plan,
    strong_review,
    Completion.completed,
    Recall.well,
    adaptive_allocator,
    adaptive_exams,
)
gap, _ = next_gap(adaptive_plan, strong_review)
assert gap == 14, f"repeated strong retrieval should expand to 14 days, got {gap}"
assert stronger_changes
check_invariants(adaptive_plan, adaptive_availability, "strong-recall", adaptive_exams)
print("[ok] strong recall expands 7 -> 14 days")

# Poor and difficult retrievals pull the next review back to 1 and 3 days.
poor_plan, poor_allocator, poor_availability, poor_exams = adaptive_fixture(
    difficulty=Difficulty.easy
)
poor_first = next(s for s in poor_plan.sessions if s.repetition == 1)
poor_plan, _ = record_progress(
    poor_plan, poor_first, Completion.completed, Recall.poor, poor_allocator, poor_exams
)
gap, _ = next_gap(poor_plan, poor_first)
assert gap == 1, f"poor recall should target tomorrow, got {gap} days"
check_invariants(poor_plan, poor_availability, "poor-gap", poor_exams)

medium_plan, medium_allocator, medium_availability, medium_exams = adaptive_fixture()
medium_first = next(s for s in medium_plan.sessions if s.repetition == 1)
medium_plan, _ = record_progress(
    medium_plan,
    medium_first,
    Completion.completed,
    Recall.medium,
    medium_allocator,
    medium_exams,
)
gap, _ = next_gap(medium_plan, medium_first)
assert gap == 3, f"difficult recall should target 3 days, got {gap}"
check_invariants(medium_plan, medium_availability, "medium-gap", medium_exams)
print("[ok] poor/difficult recall targets 1/3 days")

# The exam deadline compresses an otherwise longer strong-recall interval.
exam_plan, exam_allocator, exam_availability, exam_dates = adaptive_fixture(exam_in_days=5)
exam_first = next(s for s in exam_plan.sessions if s.repetition == 1)
exam_plan, exam_changes = record_progress(
    exam_plan,
    exam_first,
    Completion.completed,
    Recall.well,
    exam_allocator,
    exam_dates,
)
gap, exam_review = next_gap(exam_plan, exam_first)
assert exam_review.start.date() == exam_dates[exam_first.subject] - timedelta(days=1)
assert gap == 4
assert "final study day" in exam_changes[0].why
check_invariants(exam_plan, exam_availability, "exam-cap", exam_dates)
print("[ok] next review is capped at the final pre-exam study day")

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
