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
from math import ceil
from typing import TypeVar

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
    Strategy,
    StudyPlan,
    StudySession,
    Subject,
    Topic,
)

# Provisional expanding offsets after the final first-pass session. These make
# an initial calendar possible before any retrieval data exists. Once a student
# logs recall, _adapt_reviews replaces the next interval with evidence from that
# result; these numbers are a starting policy, not a claim of universal optima.
PROVISIONAL_REVIEW_OFFSETS: dict[Difficulty, list[int]] = {
    Difficulty.easy: [3, 7, 14, 30],
    Difficulty.medium: [1, 3, 7, 14, 30],
    Difficulty.hard: [1, 3, 7, 14, 30, 60],
}

# A poor retrieval returns tomorrow, a difficult retrieval in three days, and
# strong retrievals expand over successive spaced review sessions.
STRONG_RECALL_GAPS = [7, 14, 30, 60, 120]
RECALL_GAPS = {Recall.poor: 1, Recall.medium: 3}

_MAX_DAYS_SCAN = 400  # safety net against pathological availability
_MAX_SUBJECT_STREAK = 2
_LONG_BREAK_AFTER_MINUTES = 4 * 60
_T = TypeVar("_T")


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

    def _busy_intervals(self, day: date) -> list[tuple[datetime, datetime]]:
        return [
            (datetime.combine(day, block.start), datetime.combine(day, block.end))
            for block in self._busy_by_day.get(day.weekday(), [])
        ]

    def _required_break(self, studied_before: int, studied_after: int) -> int:
        """Return the recovery time after one chronologically ordered session."""
        crossed_long_break = (
            studied_before // _LONG_BREAK_AFTER_MINUTES
            < studied_after // _LONG_BREAK_AFTER_MINUTES
        )
        if crossed_long_break:
            return self.av.long_break_minutes
        return ceil((studied_after - studied_before) * 0.10)

    def _fits_with_breaks(
        self, day: date, candidate: tuple[datetime, datetime]
    ) -> bool:
        """Check collisions and the recovery period following every session."""
        studies = sorted([*self._reserved.get(day, []), candidate])
        busy = self._busy_intervals(day)

        for index, (study_start, study_end) in enumerate(studies):
            for other_start, other_end in [*busy, *studies[index + 1 :]]:
                if study_start < other_end and study_end > other_start:
                    return False

        events = sorted(
            [(*slot, True) for slot in studies]
            + [(*slot, False) for slot in busy],
            key=lambda item: (item[0], item[1], not item[2]),
        )
        studied = 0
        for index, (study_start, study_end, is_study) in enumerate(events):
            if not is_study:
                continue
            before = studied
            studied += int((study_end - study_start).total_seconds() // 60)
            recovery = timedelta(minutes=self._required_break(before, studied))
            next_event = next(
                (event for event in events[index + 1 :] if event[0] >= study_end),
                None,
            )
            if next_event is not None and next_event[0] < study_end + recovery:
                return False
        return True

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
        """Scan the day for the first slot that preserves all recovery periods."""
        cursor = datetime.combine(day, self.av.earliest)
        limit = datetime.combine(day, self.av.latest)
        need = timedelta(minutes=minutes)
        latest_start = limit - need

        while cursor <= latest_start:
            candidate = (cursor, cursor + need)
            if self._fits_with_breaks(day, candidate):
                return candidate
            cursor += timedelta(minutes=1)
        return None

    def release(self, slot: tuple[datetime, datetime]) -> None:
        """Free a slot so its time can be reused (6.4 adaptive rescheduling)."""
        day = slot[0].date()
        intervals = self._reserved.get(day, [])
        if slot in intervals:
            intervals.remove(slot)
            minutes = int((slot[1] - slot[0]).total_seconds() // 60)
            self._used[day] = max(0, self._used.get(day, 0) - minutes)

    def export_state(self) -> dict[str, object]:
        """Return the durable allocator state used by repository backends."""
        return {
            "reserved": {
                day.isoformat(): [
                    [start.isoformat(), end.isoformat()] for start, end in slots
                ]
                for day, slots in self._reserved.items()
            },
            "used": {day.isoformat(): minutes for day, minutes in self._used.items()},
        }

    @classmethod
    def from_state(
        cls, availability: Availability, state: dict[str, object]
    ) -> TimeAllocator:
        """Restore an allocator without recomputing occupancy from plan rows."""
        allocator = cls(availability)
        reserved = state.get("reserved", {})
        used = state.get("used", {})
        if not isinstance(reserved, dict) or not isinstance(used, dict):
            raise ValueError("Invalid allocator state.")

        allocator._reserved = {
            date.fromisoformat(day): [
                (datetime.fromisoformat(slot[0]), datetime.fromisoformat(slot[1]))
                for slot in slots
            ]
            for day, slots in reserved.items()
        }
        allocator._used = {
            date.fromisoformat(day): int(minutes) for day, minutes in used.items()
        }
        return allocator


def _sessions_needed(estimated_minutes: int, session_length: int) -> int:
    return max(1, -(-estimated_minutes // session_length))  # ceil division


def _provisional_offsets(
    difficulty: Difficulty, anchor: date, last_day: date
) -> list[int]:
    """Return expanding placeholders plus a final pre-exam retrieval if useful."""
    available_days = (last_day - anchor).days
    if available_days <= 0:
        return []

    offsets = [
        gap
        for gap in PROVISIONAL_REVIEW_OFFSETS[difficulty]
        if gap <= available_days
    ]
    # If the expanding sequence leaves more than three days before the exam,
    # reserve one final retrieval on the last study day.
    if not offsets or available_days - offsets[-1] > 3:
        offsets.append(available_days)
    return offsets


def _next_review_gap(plan: StudyPlan, session: StudySession, recall: Recall) -> int:
    """Choose the next gap from retrieval quality and prior spaced successes."""
    if recall in RECALL_GAPS:
        return RECALL_GAPS[recall]

    successful_reviews = sum(
        1
        for outcome in plan.history
        if outcome.subject == session.subject
        and outcome.topic == session.topic
        and outcome.repetition > 1
        and outcome.completion in (Completion.completed, Completion.partial)
        and outcome.recall is Recall.well
    )
    index = min(successful_reviews, len(STRONG_RECALL_GAPS) - 1)
    return STRONG_RECALL_GAPS[index]


def _recall_label(recall: Recall) -> str:
    return {
        Recall.poor: "Recall was poor",
        Recall.medium: "Recall was difficult",
        Recall.well: "Recall was strong",
    }[recall]


def _renumber_future_reviews(plan: StudyPlan, session: StudySession) -> None:
    """Keep review labels sequential after provisional sessions are pruned."""
    previous = [
        item.repetition
        for item in plan.sessions
        if item.subject == session.subject
        and item.topic == session.topic
        and item.repetition > 1
        and item.start <= session.start
    ]
    repetition = max(previous, default=1) + 1
    future = sorted(
        (
            item
            for item in plan.sessions
            if item.subject == session.subject
            and item.topic == session.topic
            and item.repetition > 1
            and item.start > session.start
        ),
        key=lambda item: item.start,
    )
    for item in future:
        item.repetition = repetition
        repetition += 1


def _adapt_reviews(
    plan: StudyPlan,
    session: StudySession,
    recall: Recall,
    allocator: TimeAllocator,
    last_day: date,
) -> PlanChange:
    """Re-plan the next review while leaving later placeholders provisional."""
    label = _recall_label(recall)
    gap = _next_review_gap(plan, session, recall)
    desired = session.start.date() + timedelta(days=gap)

    if session.start.date() >= last_day:
        return PlanChange(
            type=ChangeType.blocked,
            topic=session.topic,
            session_id=session.id,
            why=f"{label}, but the exam is too close for another review.",
        )

    target = min(desired, last_day)
    exam_limited = desired > last_day
    future = sorted(
        (
            item
            for item in plan.sessions
            if item.id != session.id
            and item.subject == session.subject
            and item.topic == session.topic
            and item.repetition > 1
            and item.completion is Completion.planned
            and item.start > session.start
        ),
        key=lambda item: item.start,
    )
    candidate = next((item for item in future if item.start.date() >= target), None)

    if candidate is None:
        slot = allocator.allocate(session.duration_minutes, target, last_day)
        if slot is None:
            return PlanChange(
                type=ChangeType.blocked,
                topic=session.topic,
                session_id=session.id,
                why=f"{label}, but the calendar is full before the exam.",
            )

        for item in future:
            allocator.release((item.start, item.end))
        future_ids = {item.id for item in future}
        plan.sessions = [item for item in plan.sessions if item.id not in future_ids]
        review = StudySession(
            subject=session.subject,
            topic=session.topic,
            start=slot[0],
            end=slot[1],
            repetition=session.repetition + 1,
            rationale=f"Adaptive review: {label.lower()}",
        )
        plan.sessions.append(review)
        _renumber_future_reviews(plan, session)
        plan.sessions.sort(key=lambda item: item.start)
        timing = "on the final study day before the exam" if exam_limited else f"in {gap} days"
        return PlanChange(
            type=ChangeType.added,
            topic=session.topic,
            session_id=review.id,
            moved_to=slot[0],
            why=f"{label}, so the next review was scheduled {timing}.",
        )

    earlier = [item for item in future if item.start < candidate.start]
    moved_from = candidate.start
    moved_to = candidate.start

    # Try to reach the adaptive target before the existing candidate. Keeping
    # the candidate reserved makes this atomic: failure leaves a valid fallback.
    search_end = candidate.start.date() - timedelta(days=1)
    if target <= search_end:
        slot = allocator.allocate(candidate.duration_minutes, target, search_end)
        if slot is not None:
            allocator.release((candidate.start, candidate.end))
            candidate.start, candidate.end = slot
            moved_to = slot[0]

    for item in earlier:
        allocator.release((item.start, item.end))
    earlier_ids = {item.id for item in earlier}
    plan.sessions = [item for item in plan.sessions if item.id not in earlier_ids]
    candidate.rationale = f"Adaptive review: {label.lower()}"
    _renumber_future_reviews(plan, session)
    plan.sessions.sort(key=lambda item: item.start)

    actual_gap = (candidate.start.date() - session.start.date()).days
    if exam_limited and candidate.start.date() == last_day:
        timing = "on the final study day before the exam"
    elif actual_gap > gap:
        unit = "day" if gap == 1 else "days"
        actual_unit = "day" if actual_gap == 1 else "days"
        timing = (
            f"targeted in {gap} {unit}; the next viable slot is in "
            f"{actual_gap} {actual_unit}"
        )
    else:
        timing = f"in {actual_gap} day{'s' if actual_gap != 1 else ''}"
    pruned = (
        f" {len(earlier)} earlier provisional review"
        f"{'s were' if len(earlier) != 1 else ' was'} removed."
        if earlier
        else ""
    )
    changed = moved_to != moved_from
    return PlanChange(
        type=ChangeType.moved if changed else ChangeType.kept,
        topic=session.topic,
        session_id=candidate.id,
        moved_from=moved_from if changed else None,
        moved_to=moved_to,
        why=f"{label}, so the next review is {timing}.{pruned}",
    )


def _order_topics(subject: Subject) -> list[Topic]:
    """Stable topological order: prerequisites first, input order otherwise."""
    remaining = list(subject.topics)
    topic_names = {topic.name for topic in subject.topics}
    placed: set[str] = set()
    ordered: list[Topic] = []

    while remaining:
        ready = [
            topic
            for topic in remaining
            if all(
                dependency in placed or dependency not in topic_names
                for dependency in topic.depends_on
            )
        ]
        # A dependency cycle cannot be topologically ordered. Preserve the
        # student's input order rather than introducing arbitrary shuffling.
        chosen = ready[0] if ready else remaining[0]
        ordered.append(chosen)
        placed.add(chosen.name)
        remaining.remove(chosen)

    return ordered


def _deadline_bonus(subject: Subject, start: date) -> int:
    """Increase scheduling weight as an exam approaches."""
    days = (subject.exam_date - start).days
    if days <= 3:
        return 8
    if days <= 7:
        return 6
    if days <= 14:
        return 4
    if days <= 30:
        return 2
    if days <= 60:
        return 1
    return 0


def _subject_weight(subject: Subject, start: date) -> int:
    return subject.priority + _deadline_bonus(subject, start)


def _priority_reason(subject: Subject, session_day: date) -> str:
    days = max(0, (subject.exam_date - session_day).days)
    return f"priority {subject.priority}/5, exam in {days} day{'s' if days != 1 else ''}"


def _weighted_interleave(
    subjects: list[Subject], queues: dict[str, list[_T]], start: date
) -> list[tuple[Subject, _T]]:
    """Deterministic weighted round-robin with a two-session streak limit.

    Priority and deadline urgency control how often a subject is selected.
    Capping a streak at two avoids long single-subject blocks without turning
    the plan into random task switching.
    """
    positions = {subject.name: index for index, subject in enumerate(subjects)}
    weights = {
        subject.name: _subject_weight(subject, start) for subject in subjects
    }
    credits = {subject.name: 0 for subject in subjects}
    result: list[tuple[Subject, _T]] = []
    last_subject: str | None = None
    streak = 0

    while True:
        active = [subject for subject in subjects if queues.get(subject.name)]
        if not active:
            break

        for subject in active:
            credits[subject.name] += weights[subject.name]

        eligible = active
        if streak >= _MAX_SUBJECT_STREAK and len(active) > 1:
            eligible = [subject for subject in active if subject.name != last_subject]

        chosen = max(
            eligible,
            key=lambda subject: (
                credits[subject.name],
                -subject.exam_date.toordinal(),
                subject.priority,
                -positions[subject.name],
            ),
        )
        credits[chosen.name] -= sum(weights[subject.name] for subject in active)
        result.append((chosen, queues[chosen.name].pop(0)))

        if chosen.name == last_subject:
            streak += 1
        else:
            last_subject = chosen.name
            streak = 1

    return result


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

    sessions: list[StudySession] = []
    review_anchors: list[tuple[Subject, Topic, date, int]] = []

    # Exam rush (section 7, entry point 3): coverage beats depth. Cap first
    # passes at one per topic so nothing is left untouched.
    rush = request.strategy is Strategy.exam_rush

    ordered_topics: dict[str, list[Topic]] = {}
    work_queues: dict[str, list[tuple[Topic, int, int, bool]]] = {
        subject.name: [] for subject in request.subjects
    }
    topic_totals: dict[tuple[str, str], int] = {}
    topic_refreshers: dict[tuple[str, str], bool] = {}

    for subject in request.subjects:
        deadline = subject.exam_date - timedelta(days=1)
        if deadline < start:
            warnings.append(
                f"{subject.name}: exam on {subject.exam_date} has passed or is today."
            )
            unscheduled.extend(
                f"{subject.name} / {topic.name}" for topic in subject.topics
            )
            continue

        topics = _order_topics(subject)
        ordered_topics[subject.name] = topics
        for topic in topics:
            refresher = (
                topic.already_studied and request.strategy is not Strategy.fresh
            )
            total = (
                1
                if refresher or rush
                else _sessions_needed(
                    topic.estimated_minutes, av.session_length_minutes
                )
            )
            key = (subject.name, topic.name)
            topic_totals[key] = total
            topic_refreshers[key] = refresher
            work_queues[subject.name].extend(
                (topic, part, total, refresher)
                for part in range(1, total + 1)
            )

    placed_counts: dict[tuple[str, str], int] = {}
    anchor_days: dict[tuple[str, str], date] = {}
    interleaved = sum(bool(queue) for queue in work_queues.values()) > 1

    for subject, unit in _weighted_interleave(
        request.subjects, work_queues, start
    ):
        topic, part, total, refresher = unit
        deadline = subject.exam_date - timedelta(days=1)
        slot = allocator.allocate(av.session_length_minutes, start, deadline)
        if slot is None:
            continue

        key = (subject.name, topic.name)
        placed_counts[key] = placed_counts.get(key, 0) + 1
        anchor_days[key] = slot[0].date()
        context = _priority_reason(subject, slot[0].date())
        mix = ", interleaved across subjects" if interleaved else ""
        if refresher:
            rationale = f"Refresher: already studied, {context}{mix}"
            repetition = 2
        elif rush:
            rationale = f"Focused pass: exam rush, {context}{mix}"
            repetition = 1
        else:
            rationale = f"First pass ({part} of {total}), {context}{mix}"
            repetition = 1

        sessions.append(
            StudySession(
                subject=subject.name,
                topic=topic.name,
                start=slot[0],
                end=slot[1],
                repetition=repetition,
                rationale=rationale,
            )
        )

    for subject in request.subjects:
        for topic in ordered_topics.get(subject.name, []):
            key = (subject.name, topic.name)
            total = topic_totals[key]
            placed = placed_counts.get(key, 0)
            if placed == 0:
                unscheduled.append(f"{subject.name} / {topic.name}")
                warnings.append(
                    f"{subject.name} / {topic.name}: no free time before the exam."
                )
            elif placed < total:
                warnings.append(
                    f"{subject.name} / {topic.name}: fit {placed} of {total} sessions."
                )

            # Only fully introduced material receives review placeholders.
            if not rush and placed == total:
                first_review = 3 if topic_refreshers[key] else 2
                review_anchors.append(
                    (subject, topic, anchor_days[key], first_review)
                )

    # Review passes second, against whatever time is left. Skipped entirely in
    # an exam rush, where there is no room for spaced repetition.
    if not rush:
        review_queues: dict[
            str, list[tuple[Topic, date, int, int]]
        ] = {subject.name: [] for subject in request.subjects}
        for subject, topic, anchor_day, first_review_number in review_anchors:
            deadline = subject.exam_date - timedelta(days=1)
            offsets = _provisional_offsets(topic.difficulty, anchor_day, deadline)
            for rep, offset in enumerate(offsets, start=first_review_number):
                review_queues[subject.name].append(
                    (topic, anchor_day, rep, offset)
                )

        review_interleaved = sum(
            bool(queue) for queue in review_queues.values()
        ) > 1
        for subject, review in _weighted_interleave(
            request.subjects, review_queues, start
        ):
            topic, anchor_day, rep, offset = review
            deadline = subject.exam_date - timedelta(days=1)
            target = anchor_day + timedelta(days=offset)
            slot = allocator.allocate(av.session_length_minutes, target, deadline)
            if slot is None:
                continue
            context = _priority_reason(subject, slot[0].date())
            mix = ", interleaved across subjects" if review_interleaved else ""
            sessions.append(
                StudySession(
                    subject=subject.name,
                    topic=topic.name,
                    start=slot[0],
                    end=slot[1],
                    repetition=rep,
                    rationale=(
                        f"Provisional expanding review, {offset} days after learning, "
                        f"{context}{mix}"
                    ),
                )
            )

    sessions.sort(key=lambda s: s.start)
    total_hours = sum(s.duration_minutes for s in sessions) / 60

    return (
        StudyPlan(
            sessions=sessions,
            summary=(
                f"{len(sessions)} sessions, {total_hours:.1f} hours across "
                f"{len(request.subjects)} subjects, priority-weighted and interleaved."
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

    Future reviews are provisional. Each retrieval result resets the next
    interval: poor recall shortens it, difficult recall keeps it close, and
    repeated strong recall expands it. The exam date is always the hard cap.
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

    if recall is not None:
        change = _adapt_reviews(plan, session, recall, allocator, last_day)
        changes.append(change)
        if change.type is ChangeType.blocked:
            plan.warnings.append(change.why)

    return plan, changes
