"""Route handlers.

Thin by design: validate, delegate to the scheduler, persist, return. Any logic
that decides *when* something is studied belongs in app/scheduler.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..models import PlanRequest
from ..scheduler import build_plan, record_progress
from ..store import InMemoryRepository, PlanRecord, PlanRepository
from .schemas import (
    CalendarEvent,
    PlanResponse,
    ProgressRequest,
    ProgressResponse,
)

router = APIRouter(prefix="/api")

# Single process-local store for the demo. Swapped for SQLite by changing this
# one line, since callers depend only on the protocol.
_repo = InMemoryRepository()


def get_repo() -> PlanRepository:
    return _repo


@router.post("/plan", response_model=PlanResponse)
def create_plan(
    request: PlanRequest, repo: PlanRepository = Depends(get_repo)
) -> PlanResponse:
    """Build a study plan (HACKATHON.md 8.1)."""
    if not request.subjects:
        raise HTTPException(status_code=422, detail="At least one subject is required.")

    plan, allocator = build_plan(request)
    plan_id = repo.new_id()

    repo.save(
        PlanRecord(
            plan_id=plan_id,
            plan=plan,
            availability=request.availability,
            exam_dates={s.name: s.exam_date for s in request.subjects},
            allocator=allocator,
        )
    )

    return PlanResponse(
        plan_id=plan_id,
        sessions=plan.sessions,
        summary=plan.summary,
        warnings=plan.warnings,
        unscheduled=plan.unscheduled,
    )


@router.get("/plan/{plan_id}/events", response_model=list[CalendarEvent])
def get_events(
    plan_id: str, repo: PlanRepository = Depends(get_repo)
) -> list[CalendarEvent]:
    """Sessions shaped for the calendar component."""
    record = repo.load(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return [CalendarEvent.from_session(s) for s in record.plan.sessions]


@router.post("/progress", response_model=ProgressResponse)
def submit_progress(
    request: ProgressRequest, repo: PlanRepository = Depends(get_repo)
) -> ProgressResponse:
    """Record completion and recall, then adapt the plan (6.4, 6.6)."""
    record = repo.load(request.plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    session = next(
        (s for s in record.plan.sessions if s.id == request.session_id), None
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found in this plan.")

    plan, changes = record_progress(
        record.plan,
        session,
        request.completion,
        request.recall,
        record.allocator,
        record.exam_dates,
    )

    record.plan = plan
    repo.save(record)

    return ProgressResponse(
        sessions=plan.sessions, changes=changes, warnings=plan.warnings
    )
