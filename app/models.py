"""Domain models for StudyGrid.

Contract between the AI layer, the scheduler, and the calendar frontend.
Deliberately provider-independent: nothing here knows about any LLM.

Maps to HACKATHON.md sections 6.1-6.6.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from enum import Enum
from math import ceil
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Completion(str, Enum):
    """HACKATHON.md 6.6, first axis: did the session happen."""

    planned = "planned"
    completed = "completed"
    partial = "partial"
    not_completed = "not_completed"


class Recall(str, Enum):
    """HACKATHON.md 6.6, second axis: how well the material was recalled.

    This is what drives adaptive review intervals. Without it the schedule is
    just a calendar; with it the plan responds to actual learning.
    """

    well = "well"  # mostly recalled
    medium = "medium"  # ~50%
    poor = "poor"  # little to nothing


class MissReason(str, Enum):
    """HACKATHON.md 8.3: why a session did not happen.

    Deliberately a short fixed list. Free text cannot be aggregated into
    patterns, and a student reporting a missed session wants one tap, not an
    essay. `other` exists so the list never blocks recording the miss.
    """

    club = "club"
    exercise = "exercise"
    social = "social"
    rest = "rest"
    mood = "mood"
    emergency = "emergency"
    work = "work"
    illness = "illness"
    other = "other"


# Display labels, kept beside the enum so the API can serve them and the UI
# never hardcodes a parallel list that drifts out of sync.
MISS_REASON_LABELS: dict[MissReason, str] = {
    MissReason.club: "Club meeting",
    MissReason.exercise: "Exercise",
    MissReason.social: "Social activity",
    MissReason.rest: "Rest",
    MissReason.mood: "Mood",
    MissReason.emergency: "Emergency",
    MissReason.work: "Unexpected work",
    MissReason.illness: "Illness",
    MissReason.other: "Something else",
}


class Strategy(str, Enum):
    """HACKATHON.md section 7, the three entry points."""

    fresh = "fresh"  # full plan, all passes
    remaining = "remaining"  # mid-semester, skip mastered material
    exam_rush = "exam_rush"  # not enough time, triage coverage over depth


class ChatRole(str, Enum):
    user = "user"
    assistant = "assistant"


class ChatMessage(BaseModel):
    """One persisted turn in the plan-aware Study Coach conversation."""

    role: ChatRole
    content: str = Field(min_length=1, max_length=4_000)


class ActivityCategory(str, Enum):
    """Stable chart groups; `label` on ActivityLog carries user wording."""

    study = "study"
    work = "work"
    entertainment = "entertainment"
    illness = "illness"
    unexpected = "unexpected"
    rest = "rest"
    other = "other"


ACTIVITY_CATEGORY_LABELS: dict[ActivityCategory, str] = {
    ActivityCategory.study: "Study",
    ActivityCategory.work: "Work",
    ActivityCategory.entertainment: "Entertainment",
    ActivityCategory.illness: "Illness",
    ActivityCategory.unexpected: "Unexpected",
    ActivityCategory.rest: "Rest",
    ActivityCategory.other: "Other",
}


class ActivitySource(str, Enum):
    manual = "manual"
    study_session = "study_session"
    cancelled_session = "cancelled_session"


class ActivityLog(BaseModel):
    """One owner-scoped block of real time used by Progress analytics."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    occurred_on: date
    category: ActivityCategory
    label: str = Field(min_length=1, max_length=120)
    minutes: int = Field(ge=1, le=1_440)
    note: str = Field(default="", max_length=1_000)
    source: ActivitySource = ActivitySource.manual
    source_id: str | None = Field(default=None, max_length=200)
    plan_id: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Topic(BaseModel):
    """One unit of material to study.

    Produced by AI material analysis (6.1) or entered by hand.
    """

    name: str
    difficulty: Difficulty = Difficulty.medium
    estimated_minutes: int = Field(default=60, ge=15, le=600)
    # Mid-semester entry point: material already covered needs review, not a
    # first pass.
    already_studied: bool = False
    # 6.1 relationships between concepts. Names of topics that should be
    # scheduled before this one.
    depends_on: list[str] = Field(default_factory=list)


class Subject(BaseModel):
    name: str
    exam_date: date
    topics: list[Topic] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)


class BusyBlock(BaseModel):
    """A recurring fixed commitment: lectures, work, commute (6.2).

    Study sessions must not overlap these.
    """

    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    start: time
    end: time
    label: str = ""

    @model_validator(mode="after")
    def _check_order(self) -> BusyBlock:
        if self.start >= self.end:
            raise ValueError(f"busy block start {self.start} must precede end {self.end}")
        return self


class Availability(BaseModel):
    """When the student can actually study (6.2).

    weekday_minutes maps weekday index (0 = Monday) to a daily cap in minutes.
    Absent or zero means no study that day.
    """

    weekday_minutes: dict[int, int] = Field(default_factory=dict)
    earliest: time = time(9, 0)
    latest: time = time(22, 0)
    session_length_minutes: int = Field(default=60, ge=15, le=240)
    # Derived in _check_window so API callers and the UI cannot accidentally
    # create a plan that skips the 10% recovery period.
    break_minutes: int = Field(default=6, ge=0, le=60)
    long_break_minutes: int = Field(default=45, ge=30, le=180)
    busy: list[BusyBlock] = Field(default_factory=list)

    @field_validator("weekday_minutes")
    @classmethod
    def _check_weekdays(cls, v: dict[int, int]) -> dict[int, int]:
        for day, minutes in v.items():
            if not 0 <= day <= 6:
                raise ValueError(f"weekday must be 0-6, got {day}")
            if minutes < 0:
                raise ValueError(f"minutes must be non-negative, got {minutes}")
        return v

    @model_validator(mode="after")
    def _check_window(self) -> Availability:
        if self.earliest >= self.latest:
            raise ValueError("earliest must precede latest")
        self.break_minutes = ceil(self.session_length_minutes * 0.10)
        return self


def _new_id() -> str:
    return uuid4().hex[:12]


class StudySession(BaseModel):
    """A single scheduled block. This is what renders on the calendar."""

    # Stable across rescheduling: the frontend references sessions by id, and a
    # session's position in the list changes whenever the plan adapts.
    id: str = Field(default_factory=_new_id)
    subject: str
    topic: str
    start: datetime
    end: datetime
    completion: Completion = Completion.planned
    recall: Recall | None = None
    # Why the session was missed (8.3). Only meaningful when the session was
    # partially or not completed.
    miss_reason: MissReason | None = None
    # Which pass over the material: 1 = first study, 2+ = review.
    repetition: int = Field(default=1, ge=1)
    rationale: str = ""
    # Replacement attempts receive a fresh id. Keeping the source id makes a
    # cancellation auditable without making the cancelled block reappear on
    # the active calendar.
    rescheduled_from_id: str | None = None

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    @property
    def needs_followup(self) -> bool:
        """Poor recall or an unfinished session means the plan should react."""
        return (
            self.completion in (Completion.partial, Completion.not_completed)
            or self.recall == Recall.poor
        )


class PlanRequest(BaseModel):
    subjects: list[Subject]
    availability: Availability
    start_date: date | None = None
    strategy: Strategy = Strategy.fresh
    notes: str = ""


class StudyPlan(BaseModel):
    sessions: list[StudySession] = Field(default_factory=list)
    # Append-only record of every logged outcome (8.3). Cancelled occurrences
    # leave the active calendar, while this history preserves their reason and
    # original time for analytics.
    history: list[StudySession] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    # Set when the calendar cannot fit everything, so the UI can say so plainly
    # instead of quietly dropping material.
    unscheduled: list[str] = Field(default_factory=list)


class ChangeType(str, Enum):
    moved = "moved"
    added = "added"
    kept = "kept"  # existing session already matches the adaptive target
    blocked = "blocked"  # wanted to adapt but had no room
    cancelled = "cancelled"


class PlanChange(BaseModel):
    """One adaptation, described for the UI.

    An adaptation the student cannot see looks like a bug, so every change the
    scheduler makes is reported rather than silently applied.
    """

    type: ChangeType
    topic: str
    why: str
    session_id: str | None = None
    moved_from: datetime | None = None
    moved_to: datetime | None = None


class ReasonCount(BaseModel):
    """How often one reason came up (8.3)."""

    reason: MissReason
    label: str
    count: int
    minutes_lost: int


class Insights(BaseModel):
    """Aggregated time-use patterns (8.3).

    Reports only what the data supports. With a handful of sessions logged there
    is no real pattern to find, so `confident` stays false and the UI should say
    so rather than presenting noise as insight.
    """

    sessions_logged: int = 0
    completed: int = 0
    missed: int = 0
    partial: int = 0
    minutes_studied: int = 0
    minutes_lost: int = 0
    reasons: list[ReasonCount] = Field(default_factory=list)
    # Weekdays where sessions are missed most often, as weekday indexes.
    weak_weekdays: list[int] = Field(default_factory=list)
    recall_mix: dict[str, int] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    confident: bool = False

    @property
    def completion_rate(self) -> float:
        return self.completed / self.sessions_logged if self.sessions_logged else 0.0
