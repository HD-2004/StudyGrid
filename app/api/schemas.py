"""Wire shapes for the HTTP boundary.

Separate from app/models.py on purpose: domain models can change without
breaking the frontend contract, and the calendar wants a flatter shape than the
scheduler produces.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models import (
    Completion,
    PlanChange,
    Recall,
    StudySession,
)


class PlanResponse(BaseModel):
    plan_id: str
    sessions: list[StudySession]
    summary: str
    warnings: list[str] = Field(default_factory=list)
    unscheduled: list[str] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    """Shaped for the calendar component.

    Times are ISO 8601 local, no offset. Schedule-X v4 expects
    Temporal.ZonedDateTime, so the frontend attaches the browser timezone
    once in lib/api.ts. Sending naive local time keeps the backend free of
    timezone handling, which is out of scope for a single-user demo.
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


class ProgressResponse(BaseModel):
    sessions: list[StudySession]
    changes: list[PlanChange]
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    subject: str
    text: str = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    topics: list[dict]
    source: str  # "ai" or "fallback"
