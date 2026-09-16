"""Route handlers.

Thin by design: validate, delegate to the scheduler, persist, return. Any logic
that decides *when* something is studied belongs in app/scheduler.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from ..activity import summarize_activities
from ..ai import MaterialAnalyzer, StudyCoach, build_analyzer_from_env, build_coach_from_env
from ..insights import build_insights
from ..materials import MaterialError, extract_upload, extract_url, max_upload_bytes, prepare_for_analysis
from ..models import (
    ActivityCategory,
    ActivityLog,
    ActivitySource,
    ChatMessage,
    ChatRole,
    Completion,
    Insights,
    MISS_REASON_LABELS,
    PlanRequest,
)
from ..scheduler import build_plan, record_progress
from ..security import clear_session_cookie, get_owner_id
from ..store import PlanRecord, PlanRepository, build_repository_from_env
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ActivityCategoryOption,
    ActivityDashboardResponse,
    ActivityDay,
    ActivityRequest,
    ActivityTotal,
    CalendarEvent,
    CoachRequest,
    CoachResponse,
    MaterialAnalyzeResponse,
    MaterialUrlRequest,
    PlanResponse,
    PrivacyResponse,
    ProgressRequest,
    ProgressResponse,
    ReasonOption,
)

router = APIRouter(prefix="/api")

# Local development stays zero-config. Deployments set STUDYGRID_DB_PATH to
# enable durable SQLite without changing callers.
_repo = build_repository_from_env()
_material_analyzer = build_analyzer_from_env()
_study_coach = build_coach_from_env()


def get_repo() -> PlanRepository:
    return _repo


def get_material_analyzer() -> MaterialAnalyzer:
    return _material_analyzer


def get_study_coach() -> StudyCoach:
    return _study_coach


def _response_for(record: PlanRecord) -> PlanResponse:
    return PlanResponse(
        plan_id=record.plan_id,
        sessions=record.plan.sessions,
        summary=record.plan.summary,
        warnings=record.plan.warnings,
        unscheduled=record.plan.unscheduled,
    )


def _analyze_extracted(
    subject: str,
    material_name: str,
    material_type: str,
    text: str,
    transcription_source: str | None,
    analyzer: MaterialAnalyzer,
) -> MaterialAnalyzeResponse:
    prepared, truncated = prepare_for_analysis(text)
    result = analyzer.analyze(subject, prepared)
    return MaterialAnalyzeResponse(
        topics=result.topics,
        source=result.source,
        material_name=material_name,
        material_type=material_type,
        extracted_chars=len(text),
        truncated=truncated,
        transcription_source=transcription_source,
    )


def _dashboard_for(
    repo: PlanRepository, owner_id: str, days: int, end: date
) -> ActivityDashboardResponse:
    start = end - timedelta(days=days - 1)
    activities = repo.list_activities(owner_id, start, end)
    summary = summarize_activities(activities, days, end)
    return ActivityDashboardResponse(
        period_start=summary.start,
        period_end=summary.end,
        days=summary.days,
        daily=[ActivityDay(date=day, minutes=minutes) for day, minutes in summary.daily],
        totals=[
            ActivityTotal(category=category, label=label, minutes=minutes)
            for category, label, minutes in summary.totals
        ],
        activities=activities,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_material(
    request: AnalyzeRequest,
    analyzer: MaterialAnalyzer = Depends(get_material_analyzer),
) -> AnalyzeResponse:
    """Extract scheduler-ready topics from pasted course material (6.1)."""
    result = analyzer.analyze(request.subject, request.text)
    return AnalyzeResponse(topics=result.topics, source=result.source)


@router.post("/materials/upload", response_model=MaterialAnalyzeResponse)
async def analyze_uploaded_material(
    subject: str = Form(min_length=1, max_length=200),
    file: UploadFile = File(...),
    analyzer: MaterialAnalyzer = Depends(get_material_analyzer),
) -> MaterialAnalyzeResponse:
    """Extract and analyze a bounded document, text file, or media transcript."""
    try:
        data = await file.read(max_upload_bytes() + 1)
        material = extract_upload(file.filename or "material", data)
        return _analyze_extracted(
            subject.strip(),
            material.name,
            material.kind,
            material.text,
            material.transcription_source,
            analyzer,
        )
    except MaterialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        await file.close()


@router.post("/materials/url", response_model=MaterialAnalyzeResponse)
def analyze_material_url(
    request: MaterialUrlRequest,
    analyzer: MaterialAnalyzer = Depends(get_material_analyzer),
) -> MaterialAnalyzeResponse:
    """Fetch a public URL with SSRF protection, extract readable text, and analyze it."""
    try:
        material = extract_url(str(request.url))
        return _analyze_extracted(
            request.subject,
            material.name,
            material.kind,
            material.text,
            material.transcription_source,
            analyzer,
        )
    except MaterialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/plan", response_model=PlanResponse)
def create_plan(
    request: PlanRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> PlanResponse:
    """Build and persist a study plan owned by this browser session."""
    if not request.subjects:
        raise HTTPException(status_code=422, detail="At least one subject is required.")

    plan, allocator = build_plan(request)
    record = PlanRecord(
        plan_id=repo.new_id(),
        plan=plan,
        availability=request.availability,
        exam_dates={subject.name: subject.exam_date for subject in request.subjects},
        allocator=allocator,
    )
    repo.save(record, owner_id)
    return _response_for(record)


@router.get("/plan/latest", response_model=PlanResponse | None)
def get_latest_plan(
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> PlanResponse | None:
    """Restore the most recently updated plan owned by this browser session."""
    record = repo.latest(owner_id)
    return _response_for(record) if record is not None else None


@router.get("/plan/{plan_id}/events", response_model=list[CalendarEvent])
def get_events(
    plan_id: str,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> list[CalendarEvent]:
    """Return calendar events only when the current session owns the plan."""
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return [CalendarEvent.from_session(session) for session in record.plan.sessions]


@router.delete("/plan/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> None:
    """Remove one owned plan so a user-test session can restart cleanly."""
    if not repo.delete(plan_id, owner_id):
        raise HTTPException(status_code=404, detail="Plan not found.")


@router.post("/progress", response_model=ProgressResponse)
def submit_progress(
    request: ProgressRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> ProgressResponse:
    """Record completion and recall, then adapt the owned plan."""
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    session = next(
        (item for item in record.plan.sessions if item.id == request.session_id), None
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found in this plan.")

    completed_activity_id = f"study-{request.plan_id}-{session.id}"
    # A tester may complete a session early. Progress analytics reflects when
    # time has actually happened and must never place completed work in a
    # future chart bucket.
    occurred_on = min(session.start.date(), date.today())
    activity_label = f"{session.subject}: {session.topic}"
    activity_minutes = session.duration_minutes

    plan, changes = record_progress(
        record.plan,
        session,
        request.completion,
        request.recall,
        record.allocator,
        record.exam_dates,
        miss_reason=request.miss_reason,
    )
    record.plan = plan
    repo.save(record, owner_id)
    if request.completion is Completion.completed:
        repo.save_activity(
            ActivityLog(
                id=completed_activity_id,
                occurred_on=occurred_on,
                category=ActivityCategory.study,
                label=activity_label,
                minutes=activity_minutes,
                source=ActivitySource.study_session,
                source_id=session.id,
                plan_id=request.plan_id,
            ),
            owner_id,
        )
    else:
        repo.delete_activity(completed_activity_id, owner_id)

    return ProgressResponse(
        sessions=plan.sessions,
        changes=changes,
        warnings=plan.warnings,
        insights=build_insights(plan.history),
    )


@router.get("/plan/{plan_id}/insights", response_model=Insights)
def get_insights(
    plan_id: str,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> Insights:
    """Return time-use insights only for an owned plan."""
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return build_insights(record.plan.history)


@router.get("/miss-reasons", response_model=list[ReasonOption])
def get_miss_reasons() -> list[ReasonOption]:
    """Reason options for the missed-session prompt (8.3)."""
    return [
        ReasonOption(value=reason, label=label)
        for reason, label in MISS_REASON_LABELS.items()
    ]


@router.get("/activity-categories", response_model=list[ActivityCategoryOption])
def get_activity_categories() -> list[ActivityCategoryOption]:
    return ActivityCategoryOption.all()


@router.get("/activities", response_model=ActivityDashboardResponse)
def get_activities(
    days: int = Query(default=7),
    end: date | None = Query(default=None),
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> ActivityDashboardResponse:
    if days not in {7, 30}:
        raise HTTPException(status_code=422, detail="days must be 7 or 30.")
    return _dashboard_for(repo, owner_id, days, end or date.today())


@router.post("/activities", response_model=ActivityLog, status_code=201)
def create_activity(
    request: ActivityRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> ActivityLog:
    activity = ActivityLog(**request.model_dump())
    repo.save_activity(activity, owner_id)
    return activity


@router.put("/activities/{activity_id}", response_model=ActivityLog)
def update_activity(
    activity_id: str,
    request: ActivityRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> ActivityLog:
    activity = repo.load_activity(activity_id, owner_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found.")
    if activity.source is not ActivitySource.manual:
        raise HTTPException(
            status_code=409,
            detail="Study-session time is updated from session progress, not edited here.",
        )
    updated = activity.model_copy(update=request.model_dump())
    repo.save_activity(updated, owner_id)
    return updated


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: str,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> None:
    activity = repo.load_activity(activity_id, owner_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found.")
    if activity.source is not ActivitySource.manual:
        raise HTTPException(
            status_code=409,
            detail="Study-session time is removed by changing that session's progress.",
        )
    repo.delete_activity(activity_id, owner_id)


@router.get("/privacy", response_model=PrivacyResponse)
def get_privacy(repo: PlanRepository = Depends(get_repo)) -> PrivacyResponse:
    """Describe the active retention boundary without exposing server paths."""
    return PrivacyResponse(
        durable_storage=repo.durable,
        retention_days=repo.retention_days,
    )


@router.delete("/session", status_code=204)
def delete_session_data(
    response: Response,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> None:
    """Delete every plan owned by the current anonymous browser session."""
    repo.delete_owner(owner_id)
    clear_session_cookie(response)


@router.post("/chat", response_model=CoachResponse)
def chat_with_coach(
    request: CoachRequest,
    repo: PlanRepository = Depends(get_repo),
    coach: StudyCoach = Depends(get_study_coach),
    owner_id: str = Depends(get_owner_id),
) -> CoachResponse:
    """Answer questions using an owned plan without mutating its schedule."""
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    focus = None
    if request.session_id is not None:
        focus = next(
            (
                session
                for session in record.plan.sessions
                if session.id == request.session_id
            ),
            None,
        )
        if focus is None:
            raise HTTPException(status_code=404, detail="Session not found in this plan.")

    result = coach.reply(record.plan, record.chat_history, request.message, focus)
    user_turn = ChatMessage(role=ChatRole.user, content=request.message)
    assistant_turn = ChatMessage(role=ChatRole.assistant, content=result.text)
    record.chat_history = [
        *record.chat_history,
        user_turn,
        assistant_turn,
    ][-24:]
    repo.save(record, owner_id)

    return CoachResponse(
        reply=assistant_turn,
        history=record.chat_history,
        source=result.source,
        suggestions=result.suggestions,
    )
