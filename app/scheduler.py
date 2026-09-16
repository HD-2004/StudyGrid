"""Deterministic scheduling core (HACKATHON.md 6.3, 6.4, 8.1).

Design note: the LLM decides *what* to study, how to break material into topics,
and how long each needs. This module decides *when*, using plain arithmetic.
Letting a model emit wall-clock times produces overlapping and out-of-bounds
slots; keeping placement deterministic means the calendar is always internally
consistent, it costs no tokens, and it is reproducible in a demo.

All placement goes through one TimeAllocator instance so first passes and review
passes compete for the same pool of free time. Two allocators over the same
calendar would hand out the same slot twice.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .models import (
    Availability,
    BusyBlock,
    ChangeType,
    Completion,
    Difficulty,
    MissReason,
    PlanChange,
    PlanRequest,
    Recall,
    RECALL_MULTIPLIER,
    Strategy,
    StudyPlan,
    StudySession,
    Subject,
    Topic,
)

# Base review offsets in days after the first pass, by difficulty (6.3).
# Harder material gets more passes at tighter intervals.
REVIEW_OFFSETS: dict[Difficulty, list[int]] = {
    Difficulty.easy: [3, 10],
    Difficulty.medium: [2, 7, 16],
    Difficulty.hard: [1, 4, 10, 21],
}

_MAX_DAYS_SCAN = 400  # safety net against pathological availability


class TimeAllocator:
    """Hands out non-overlapping slots that respect availability and busy blocks.

    One instance owns the whole calendar. Tracks per-day reserved intervals, so
    requests arriving out of chronological order (review passes) cannot collide
    with already-placed sessions.
    """

    def __init__(self, availability: Availability):
        self.av = availability
        self._reserved: dict[date, list[tuple[datetime, datetime]]] = {}
        self._used: dict[date, int] = {}
        self._busy_by_day: dict[int, list[BusyBlock]] = {}
        for block in availability.busy:
            self._busy_by_day.setdefault(block.weekday, []).append(block)

    def _blocked_intervals(self, day: date) -> list[tuple[datetime, datetime]]:
        """Busy blocks plus already-reserved sessions for a given day."""
        out = list(self._reserved.get(day, []))
        for block in self._busy_by_day.get(day.weekday(), []):
            out.append(
                (datetime.combine(day, block.start), datetime.combine(day, block.end))
            )
        out.sort()
        return out

    def allocate(
        self, minutes: int, earliest: date, deadline: date
    ) -> tuple[datetime, datetime] | None:
        """Reserve the first free slot in [earliest, deadline], or None."""
        day = max(earliest, earliest)
        scanned = 0

        while day <= deadline and scanned < _MAX_DAYS_SCAN:
            scanned += 1
            budget = self.av.weekday_minutes.get(day.weekday(), 0)
            if budget == 0 or self._used.get(day, 0) + minutes > budget:
                day += timedelta(days=1)
                continue

            slot = self._first_gap(day, minutes)
            if slot is not None:
                self._reserved.setdefault(day, []).append(slot)
                self._used[day] = self._used.get(day, 0) + minutes
                return slot

            day += timedelta(days=1)

        return None

    def _first_gap(self, day: date, minutes: int) -> tuple[datetime, datetime] | None:
        """Walk the day's gaps and return the first that fits."""
        cursor = datetime.combine(day, self.av.earliest)
        limit = datetime.combine(day, self.av.latest)
        need = timedelta(minutes=minutes)
        gap = timedelta(minutes=self.av.break_minutes)

        for blocked_start, blocked_end in self._blocked_intervals(day):
            if cursor + need <= blocked_start:
                return cursor, cursor + need
            if blocked_end > cursor:
                cursor = blocked_end + gap

        if cursor + need <= limit:
            return cursor, cursor + need
        return None

    def release(self, slot: tuple[datetime, datetime]) -> None:
        """Free a slot so its time can be reused (6.4 adaptive rescheduling)."""
        day = slot[0].date()
        intervals = self._reserved.get(day, [])
        if slot in intervals:
            intervals.remove(slot)
            minutes = int((slot[1] - slot[0]).total_seconds() // 60)
            self._used[day] = max(0, self._used.get(day, 0) - minutes)


def _sessions_needed(estimated_minutes: int, session_length: int) -> int:
    return max(1, -(-estimated_minutes // session_length))  # ceil division


def _order_work(subjects: list[Subject]) -> list[tuple[Subject, Topic]]:
    """Urgency order: earliest exam, then priority, then difficulty.

    Dependencies (6.1) are respected within a subject by placing prerequisites
    before the topics that need them.
    """
    difficulty_rank = {Difficulty.hard: 0, Difficulty.medium: 1, Difficulty.easy: 2}
    work: list[tuple[Subject, Topic]] = []

    for subject in sorted(subjects, key=lambda s: (s.exam_date, -s.priority)):
        remaining = list(subject.topics)
        placed: set[str] = set()
        ordered: list[Topic] = []

        # Repeatedly take topics whose prerequisites are already placed.
        while remaining:
            ready = [
                t
                for t in remaining
                if all(d in placed or d not in {x.name for x in subject.topics} for d in t.depends_on)
            ]
            if not ready:
                ready = remaining  # dependency cycle; fall back to given order
            ready.sort(key=lambda t: difficulty_rank[t.difficulty])
            chosen = ready[0]
            ordered.append(chosen)
            placed.add(chosen.name)
            remaining.remove(chosen)

        work.extend((subject, t) for t in ordered)

    return work


def build_plan(request: PlanRequest) -> tuple[StudyPlan, TimeAllocator]:
    """Turn subjects plus availability into concrete calendar sessions (8.1).

    Returns the plan and the allocator, so later rescheduling reuses the same
    occupancy state instead of rebuilding it and risking double-booking.
    """
    start = request.start_date or date.today()
    av = request.availability
    warnings: list[str] = []
    unscheduled: list[str] = []
    allocator = TimeAllocator(av)

    if not any(av.weekday_minutes.values()):
        return (
            StudyPlan(
                sessions=[],
                summary="No study time available.",
                warnings=["Availability is empty, so no sessions could be scheduled."],
            ),
            allocator,
        )

    work = _order_work(request.subjects)
    sessions: list[StudySession] = []
    review_anchors: list[tuple[Subject, Topic, date]] = []

    # Exam rush (section 7, entry point 3): coverage beats depth. Cap first
    # passes at one per topic so nothing is left untouched.
    rush = request.strategy is Strategy.exam_rush

    for subject, topic in work:
        deadline = subject.exam_date - timedelta(days=1)
        if deadline < start:
            warnings.append(
                f"{subject.name}: exam on {subject.exam_date} has passed or is today."
            )
            unscheduled.append(f"{subject.name} / {topic.name}")
            continue

        # Mid-semester (entry point 2): studied material gets review only.
        if topic.already_studied and request.strategy is not Strategy.fresh:
            slot = allocator.allocate(av.session_length_minutes, start, deadline)
            if slot is None:
                unscheduled.append(f"{subject.name} / {topic.name}")
                continue
            sessions.append(
                StudySession(
                    subject=subject.name,
                    topic=topic.name,
                    start=slot[0],
                    end=slot[1],
                    repetition=2,
                    rationale="Refresher: already studied",
                )
            )
            review_anchors.append((subject, topic, slot[0].date()))
            continue

        total = 1 if rush else _sessions_needed(topic.estimated_minutes, av.session_length_minutes)
        first_day: date | None = None
        placed = 0

        for i in range(total):
            slot = allocator.allocate(av.session_length_minutes, start, deadline)
            if slot is None:
                break
            sessions.append(
                StudySession(
                    subject=subject.name,
                    topic=topic.name,
                    start=slot[0],
                    end=slot[1],
                    repetition=1,
                    rationale=(
                        "Focused pass (exam rush)"
                        if rush
                        else f"First pass ({i + 1} of {total})"
                    ),
                )
            )
            placed += 1
            if first_day is None:
                first_day = slot[0].date()

        if placed == 0:
            unscheduled.append(f"{subject.name} / {topic.name}")
            warnings.append(
                f"{subject.name} / {topic.name}: no free time before the exam."
            )
        elif placed < total:
            warnings.append(
                f"{subject.name} / {topic.name}: fit {placed} of {total} sessions."
            )

        if first_day is not None:
            review_anchors.append((subject, topic, first_day))

    # Review passes second, against whatever time is left. Skipped entirely in
    # an exam rush, where there is no room for spaced repetition.
    if not rush:
        for subject, topic, first_day in review_anchors:
            deadline = subject.exam_date - timedelta(days=1)
            for rep, offset in enumerate(REVIEW_OFFSETS[topic.difficulty], start=2):
                target = first_day + timedelta(days=offset)
                if target > deadline:
                    continue
                slot = allocator.allocate(av.session_length_minutes, target, deadline)
                if slot is None:
                    continue
                sessions.append(
                    StudySession(
                        subject=subject.name,
                        topic=topic.name,
                        start=slot[0],
                        end=slot[1],
                        repetition=rep,
                        rationale=f"Review, {offset} days after first pass",
                    )
                )

    sessions.sort(key=lambda s: s.start)
    total_hours = sum(s.duration_minutes for s in sessions) / 60

    return (
        StudyPlan(
            sessions=sessions,
            summary=(
                f"{len(sessions)} sessions, {total_hours:.1f} hours across "
                f"{len(request.subjects)} subjects."
            ),
            warnings=warnings,
            unscheduled=unscheduled,
        ),
        allocator,
    )


def record_progress(
    plan: StudyPlan,
    session: StudySession,
    completion: Completion,
    recall: Recall | None,
    allocator: TimeAllocator,
    exam_dates: dict[str, date],
    miss_reason: MissReason | None = None,
) -> tuple[StudyPlan, list[PlanChange]]:
    """Apply progress feedback and adapt the remaining plan (6.4, 6.6).

    Returns the plan and a list of changes. Every adaptation is reported so the
    UI can show what moved and why; a silent adaptation reads as a bug.

    The interesting case is poor recall: the topic gets an extra near-term
    review rather than waiting for its next scheduled pass.
    """
    changes: list[PlanChange] = []
    session.completion = completion
    session.recall = recall
    # Only meaningful for sessions that did not fully happen (8.3).
    session.miss_reason = (
        miss_reason
        if completion in (Completion.partial, Completion.not_completed)
        else None
    )

    # Snapshot the outcome before any rescheduling rewrites the session, so the
    # insight report keeps a complete record (8.3).
    plan.history.append(session.model_copy())

    deadline = exam_dates.get(session.subject)
    if deadline is None:
        plan.warnings.append(f"No exam date known for {session.subject}.")
        return plan, changes

    last_day = deadline - timedelta(days=1)

    # Unfinished work gets moved forward so it is not silently lost.
    if completion is Completion.not_completed:
        allocator.release((session.start, session.end))
        slot = allocator.allocate(
            session.duration_minutes, session.start.date() + timedelta(days=1), last_day
        )
        if slot is None:
            plan.warnings.append(f"No free time to redo {session.topic} before {deadline}.")
            changes.append(
                PlanChange(
                    type=ChangeType.blocked,
                    topic=session.topic,
                    session_id=session.id,
                    why=f"Missed, but no free time before {deadline}.",
                )
            )
            return plan, changes

        original_start = session.start
        # The replacement is a fresh attempt with no progress data. The miss
        # itself is preserved in plan.history above.
        moved = session.model_copy(
            update={
                "start": slot[0],
                "end": slot[1],
                "completion": Completion.planned,
                "recall": None,
                "miss_reason": None,
                "rationale": "Rescheduled after a missed session",
            }
        )
        plan.sessions = [s for s in plan.sessions if s.id != session.id]
        plan.sessions.append(moved)
        plan.sessions.sort(key=lambda s: s.start)
        changes.append(
            PlanChange(
                type=ChangeType.moved,
                topic=session.topic,
                session_id=moved.id,
                moved_from=original_start,
                moved_to=slot[0],
                why="Session was missed, so it moved to the next free slot.",
            )
        )
        return plan, changes

    # Weak recall earns an extra review, timed by the recall multiplier.
    if recall in (Recall.poor, Recall.medium):
        base = 2 if recall is Recall.poor else 4
        offset = max(1, round(base * RECALL_MULTIPLIER[recall]))
        target = session.start.date() + timedelta(days=offset)

        if target > last_day:
            plan.warnings.append(
                f"{session.topic}: weak recall but no time left before {deadline}."
            )
            changes.append(
                PlanChange(
                    type=ChangeType.blocked,
                    topic=session.topic,
                    session_id=session.id,
                    why=f"Recall was {recall.value}, but the exam is too close for another review.",
                )
            )
            return plan, changes

        slot = allocator.allocate(session.duration_minutes, target, last_day)
        if slot is None:
            changes.append(
                PlanChange(
                    type=ChangeType.blocked,
                    topic=session.topic,
                    session_id=session.id,
                    why=f"Recall was {recall.value}, but the calendar is full before the exam.",
                )
            )
            return plan, changes

        extra = StudySession(
            subject=session.subject,
            topic=session.topic,
            start=slot[0],
            end=slot[1],
            repetition=session.repetition + 1,
            rationale=f"Extra review: recall was {recall.value}",
        )
        plan.sessions.append(extra)
        plan.sessions.sort(key=lambda s: s.start)
        changes.append(
            PlanChange(
                type=ChangeType.added,
                topic=session.topic,
                session_id=extra.id,
                moved_to=slot[0],
                why=f"Recall was {recall.value}, so an extra review was added in {offset} days.",
            )
        )

    return plan, changes
