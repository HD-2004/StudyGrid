"""Wire shapes for the HTTP boundary.

Separate from app/models.py on purpose: domain models can change without
breaking the frontend contract, and the calendar wants a flatter shape than the
scheduler produces.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ..models import (
    ACTIVITY_CATEGORY_LABELS,
    ActivityCategory,
    ActivityLog,
    ChatMessage,
    Completion,
    Insights,
    MissReason,
    PlanChange,
    Recall,
    StudySession,
    Topic,
)


class PlanResponse(BaseModel):
    plan_id: str
    sessions: list[StudySession]
    summary: str
    warnings: list[str] = Field(default_factory=list)
    unscheduled: list[str] = Field(default_factory=list)


class PrivacyResponse(BaseModel):
    """Public retention facts for the user-test interface."""

    anonymous_session: bool = True
    durable_storage: bool
    retention_days: int


class CalendarEvent(BaseModel):
    """Shaped for the calendar component.

    Times are ISO 8601 local, no offset. Schedule-X v4 expects
    Temporal.ZonedDateTime, so Calendar.svelte attaches the browser timezone to
    each event and configures Schedule-X to render in that same timezone.
    Sending naive local time keeps the backend free of timezone handling, which
    is out of scope for a single-user demo.
    """

    id: str
    title: str
    start: str  # "YYYY-MM-DDTHH:MM:SS"
    end: str
    subject: str
    topic: str
    repetition: int
    completion: Completion
    recall: Recall | None
    rationale: str
    is_review: bool

    @classmethod
    def from_session(cls, s: StudySession) -> CalendarEvent:
        label = f"{s.subject}: {s.topic}"
        if s.repetition > 1:
            label = f"{label} (review {s.repetition - 1})"
        return cls(
            id=s.id,
            title=label,
            start=s.start.isoformat(timespec="seconds"),
            end=s.end.isoformat(timespec="seconds"),
            subject=s.subject,
            topic=s.topic,
            repetition=s.repetition,
            completion=s.completion,
            recall=s.recall,
            rationale=s.rationale,
            is_review=s.repetition > 1,
        )


class ProgressRequest(BaseModel):
    plan_id: str
    session_id: str
    completion: Completion
    recall: Recall | None = None
    # 8.3: why the session was missed. Optional so logging never blocks on it.
    miss_reason: MissReason | None = None


class ProgressResponse(BaseModel):
    sessions: list[StudySession]
    changes: list[PlanChange]
    warnings: list[str] = Field(default_factory=list)
    insights: Insights | None = None


class ReasonOption(BaseModel):
    """A selectable miss reason, served so the UI never hardcodes the list."""

    value: MissReason
    label: str


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=200)
    # Keeps provider cost and latency bounded for pasted text. Uploaded and
    # fetched materials use the same bounded analysis window after extraction.
    text: str = Field(min_length=1, max_length=30_000)


class AnalyzeResponse(BaseModel):
    topics: list[Topic]
    source: Literal["ai", "fallback"]


class MaterialAnalyzeResponse(AnalyzeResponse):
    """Topics plus transparent extraction metadata for uploaded material."""

    material_name: str
    material_type: Literal["text", "markdown", "pdf", "docx", "url", "video"]
    extracted_chars: int
    truncated: bool = False
    transcription_source: Literal["ai"] | None = None


class MaterialUrlRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=200)
    url: AnyHttpUrl


class ActivityRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    occurred_on: date
    category: ActivityCategory
    label: str = Field(min_length=1, max_length=120)
    minutes: int = Field(ge=1, le=1_440)
    note: str = Field(default="", max_length=1_000)


class ActivityCategoryOption(BaseModel):
    value: ActivityCategory
    label: str

    @classmethod
    def all(cls) -> list[ActivityCategoryOption]:
        return [cls(value=value, label=label) for value, label in ACTIVITY_CATEGORY_LABELS.items()]


class ActivityDay(BaseModel):
    date: date
    minutes: dict[ActivityCategory, int]


class ActivityTotal(BaseModel):
    category: ActivityCategory
    label: str
    minutes: int


class ActivityDashboardResponse(BaseModel):
    period_start: date
    period_end: date
    days: int
    daily: list[ActivityDay]
    totals: list[ActivityTotal]
    activities: list[ActivityLog]


class CoachRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    plan_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1_000)
    # When a calendar session is selected, "why this?" can be grounded in it.
    session_id: str | None = Field(default=None, max_length=100)


class CoachResponse(BaseModel):
    reply: ChatMessage
    history: list[ChatMessage]
    source: Literal["ai", "fallback"]
    suggestions: list[str]
