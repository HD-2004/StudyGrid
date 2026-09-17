"""Route handlers.

Thin by design: validate, delegate to the scheduler, persist, return. Any logic
that decides *when* something is studied belongs in app/scheduler.py.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile

from ..activity import summarize_activities
from ..ai import MaterialAnalyzer, StudyCoach, build_analyzer_from_env, build_coach_from_env
from ..insights import build_insights
from ..health import (
    apply_health_adjustment,
    assess_readiness,
    health_policy,
    schedule_recommendations,
)
from ..materials import MaterialError, extract_upload, extract_url, max_upload_bytes, prepare_for_analysis
from ..models import (
    ActivityCategory,
    ActivityLog,
    ActivitySource,
    ChatMessage,
    ChatRole,
    Completion,
    DailyHealthSummary,
    HealthAdjustmentLog,
    HealthConnection,
    HealthConnectionStatus,
    HealthPairing,
    Insights,
    MISS_REASON_LABELS,
    MissReason,
    PlanRequest,
    StudySession,
)
from ..scheduler import (
    RECOVERY_CHUNK_MINUTES,
    RESCHEDULE_WINDOW_DAYS,
    build_plan,
    commit_reschedule,
    propose_full_reschedule,
    propose_split_reschedule,
    record_progress,
    reschedule_window,
)
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
    HealthCheckInRequest,
    HealthConnectionView,
    HealthDashboardResponse,
    HealthPairingClaimRequest,
    HealthPairingClaimResponse,
    HealthPairingRequest,
    HealthPairingResponse,
    HealthPlanRequest,
    HealthPolicyResponse,
    HealthScheduleApplyRequest,
    HealthScheduleApplyResponse,
    HealthSyncRequest,
    HealthSyncResponse,
    MaterialAnalyzeResponse,
    MaterialUrlRequest,
    PlanResponse,
    PrivacyResponse,
    ProgressRequest,
    ProgressResponse,
    RescheduleProposal,
    RescheduleRequest,
    RescheduleResponse,
    RescheduleSlot,
    SessionCreateRequest,
    SessionUpdateRequest,
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


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalise_pairing_code(value: str) -> str:
    return value.strip().upper().replace("-", "")


def _record_for_health_token(
    authorization: str | None, repo: PlanRepository
) -> tuple[str, PlanRecord]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A companion access token is required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="A companion access token is required.")
    found = repo.find_by_health_token(_secret_hash(token))
    if found is None:
        raise HTTPException(status_code=401, detail="The companion token is invalid or revoked.")
    return found


def _health_dashboard_for(
    record: PlanRecord, days: int, end: date
) -> HealthDashboardResponse:
    policy = health_policy()
    start = end - timedelta(days=days - 1)
    visible = sorted(
        (item for item in record.health_summaries if start <= item.occurred_on <= end),
        key=lambda item: item.occurred_on,
    )
    readiness = assess_readiness(record.health_summaries, end, policy)
    connection = (
        HealthConnectionView.model_validate(
            record.health_connection.model_dump(exclude={"token_hash"})
        )
        if record.health_connection
        else None
    )
    return HealthDashboardResponse(
        plan_id=record.plan_id,
        connection=connection,
        summaries=visible,
        readiness=readiness,
        recommendations=schedule_recommendations(record, readiness, end),
        adjustments=sorted(
            (
                item
                for item in record.health_adjustments
                if start <= item.occurred_on <= end
            ),
            key=lambda item: item.applied_at,
            reverse=True,
        ),
        policy=HealthPolicyResponse.model_validate(
            policy.model_dump(exclude={"pairing_ttl_minutes"})
        ),
    )


def _reschedule_proposal(
    session: StudySession,
    exam_dates: dict[str, date],
    status: str,
    slots: list[tuple] | None = None,
    extra_minutes: int = 0,
) -> RescheduleProposal:
    window = reschedule_window(session, exam_dates)
    search_through = (
        window[1]
        if window
        else session.start.date() + timedelta(days=RESCHEDULE_WINDOW_DAYS)
    )
    return RescheduleProposal(
        source_session_id=session.id,
        subject=session.subject,
        topic=session.topic,
        duration_minutes=session.duration_minutes,
        status=status,
        slots=[RescheduleSlot(start=start, end=end) for start, end in slots or []],
        extra_minutes=extra_minutes,
        search_through=search_through,
        search_days=RESCHEDULE_WINDOW_DAYS,
        chunk_minutes=RECOVERY_CHUNK_MINUTES,
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
        subject_priorities={subject.name: subject.priority for subject in request.subjects},
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


@router.post(
    "/plan/{plan_id}/sessions", response_model=CalendarEvent, status_code=201
)
def create_session(
    plan_id: str,
    request: SessionCreateRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> CalendarEvent:
    """Create a real persisted task from the calendar's Create action."""
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    slot = (request.start, request.end)
    if not record.allocator.reserve_exact(slot):
        raise HTTPException(
            status_code=409,
            detail="That time overlaps another session or fixed commitment.",
        )
    session = StudySession(
        subject=request.subject,
        topic=request.topic,
        start=request.start,
        end=request.end,
        rationale="Created manually by the student",
    )
    record.plan.sessions.append(session)
    record.plan.sessions.sort(key=lambda item: item.start)
    deadline = request.deadline or (request.start.date() + timedelta(days=30))
    current_deadline = record.exam_dates.get(request.subject)
    if current_deadline is None or deadline > current_deadline:
        record.exam_dates[request.subject] = deadline
    repo.save(record, owner_id)
    return CalendarEvent.from_session(session)


@router.put("/plan/{plan_id}/sessions/{session_id}", response_model=CalendarEvent)
def update_session(
    plan_id: str,
    session_id: str,
    request: SessionUpdateRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> CalendarEvent:
    """Persist direct calendar edits, including drag and resize operations."""
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    session = next((item for item in record.plan.sessions if item.id == session_id), None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found in this plan.")
    if session.completion is not Completion.planned:
        raise HTTPException(status_code=409, detail="Only pending sessions can be moved.")

    original = (session.start, session.end)
    requested = (request.start, request.end)
    record.allocator.release(original)
    if not record.allocator.reserve_exact(requested):
        record.allocator.reserve_exact(original)
        raise HTTPException(
            status_code=409,
            detail="That time overlaps another session or fixed commitment.",
        )

    session.start = request.start
    session.end = request.end
    if request.subject is not None:
        session.subject = request.subject
    if request.topic is not None:
        session.topic = request.topic
    session.rationale = "Adjusted manually on the calendar"
    record.plan.sessions.sort(key=lambda item: item.start)
    repo.save(record, owner_id)
    return CalendarEvent.from_session(session)


@router.delete("/plan/{plan_id}/sessions/{session_id}", status_code=204)
def delete_session(
    plan_id: str,
    session_id: str,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> None:
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    session = next((item for item in record.plan.sessions if item.id == session_id), None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found in this plan.")
    record.allocator.release((session.start, session.end))
    record.plan.sessions = [item for item in record.plan.sessions if item.id != session_id]
    repo.delete_activity(f"study-{plan_id}-{session_id}", owner_id)
    repo.save(record, owner_id)


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
    reschedule = None
    if request.completion is Completion.not_completed:
        proposed_slot = propose_full_reschedule(session, record.allocator, record.exam_dates)
        reschedule = _reschedule_proposal(
            session,
            record.exam_dates,
            "full_slot" if proposed_slot else "no_full_slot",
            [proposed_slot] if proposed_slot else [],
        )
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

    if request.completion is Completion.not_completed and request.miss_reason is not None:
        category_by_reason = {
            MissReason.club: ActivityCategory.entertainment,
            MissReason.social: ActivityCategory.entertainment,
            MissReason.exercise: ActivityCategory.other,
            MissReason.rest: ActivityCategory.rest,
            MissReason.mood: ActivityCategory.rest,
            MissReason.emergency: ActivityCategory.unexpected,
            MissReason.work: ActivityCategory.work,
            MissReason.illness: ActivityCategory.illness,
            MissReason.other: ActivityCategory.other,
        }
        repo.save_activity(
            ActivityLog(
                id=f"cancelled-{request.plan_id}-{session.id}-{len(plan.history)}",
                occurred_on=occurred_on,
                category=category_by_reason[request.miss_reason],
                label=f"Cancelled: {activity_label}",
                minutes=activity_minutes,
                note=MISS_REASON_LABELS[request.miss_reason],
                source=ActivitySource.cancelled_session,
                source_id=session.id,
                plan_id=request.plan_id,
            ),
            owner_id,
        )

    return ProgressResponse(
        sessions=plan.sessions,
        changes=changes,
        warnings=plan.warnings,
        unscheduled=plan.unscheduled,
        insights=build_insights(plan.history),
        reschedule=reschedule,
    )


@router.post("/reschedule", response_model=RescheduleResponse)
def reschedule_cancelled_session(
    request: RescheduleRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> RescheduleResponse:
    """Apply the student's chosen recovery path for one cancelled block."""
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    source = next(
        (
            item
            for item in reversed(record.plan.history)
            if item.id == request.source_session_id
            and item.completion is Completion.not_completed
        ),
        None,
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Cancelled session not found.")
    if any(
        item.rescheduled_from_id == source.id for item in record.plan.sessions
    ):
        raise HTTPException(status_code=409, detail="This task has already been rescheduled.")

    backlog_item = f"{source.subject}: {source.topic} · {source.duration_minutes} min"
    changes = []
    proposal: RescheduleProposal

    if request.action == "backlog":
        if backlog_item not in record.plan.unscheduled:
            record.plan.unscheduled.append(backlog_item)
        proposal = _reschedule_proposal(
            source, record.exam_dates, "backlog"
        )
        repo.save(record, owner_id)
    elif request.action == "accept_full":
        slot = propose_full_reschedule(source, record.allocator, record.exam_dates)
        if slot is None:
            proposal = _reschedule_proposal(
                source, record.exam_dates, "no_full_slot"
            )
        else:
            replacements, changes = commit_reschedule(
                record.plan, source, record.allocator, [slot], split=False
            )
            if not replacements:
                raise HTTPException(
                    status_code=409,
                    detail="That proposed time is no longer available. Please try again.",
                )
            proposal = _reschedule_proposal(
                source, record.exam_dates, "scheduled", [slot]
            )
            repo.save(record, owner_id)
    elif request.action == "split":
        slots, remaining, _ = propose_split_reschedule(
            source, record.allocator, record.exam_dates
        )
        if remaining == 0:
            replacements, changes = commit_reschedule(
                record.plan, source, record.allocator, slots, split=True
            )
            if not replacements:
                raise HTTPException(
                    status_code=409,
                    detail="The recovery slots changed. Please try again.",
                )
            proposal = _reschedule_proposal(
                source, record.exam_dates, "scheduled", slots
            )
            repo.save(record, owner_id)
        else:
            override_slots: list[tuple] = []
            override_extra = 0
            override_remaining = source.duration_minutes
            # Find the smallest 15-minute daily cap increase that can recover
            # the whole task. The UI shows this exact cost before committing.
            for daily_extra in range(
                RECOVERY_CHUNK_MINUTES,
                source.duration_minutes + RECOVERY_CHUNK_MINUTES,
                RECOVERY_CHUNK_MINUTES,
            ):
                candidate_slots, candidate_remaining, candidate_extra = (
                    propose_split_reschedule(
                        source,
                        record.allocator,
                        record.exam_dates,
                        daily_extra_minutes=daily_extra,
                    )
                )
                if candidate_remaining == 0:
                    override_slots = candidate_slots
                    override_remaining = 0
                    override_extra = candidate_extra
                    break
            if override_remaining == 0:
                proposal = _reschedule_proposal(
                    source,
                    record.exam_dates,
                    "needs_limit_approval",
                    override_slots,
                    override_extra,
                )
            else:
                if backlog_item not in record.plan.unscheduled:
                    record.plan.unscheduled.append(backlog_item)
                proposal = _reschedule_proposal(
                    source, record.exam_dates, "backlog"
                )
                repo.save(record, owner_id)
    else:  # approve_limit
        approved_slots: list[tuple] = []
        approved_extra = 0
        for daily_extra in range(
            RECOVERY_CHUNK_MINUTES,
            source.duration_minutes + RECOVERY_CHUNK_MINUTES,
            RECOVERY_CHUNK_MINUTES,
        ):
            candidate_slots, remaining, extra = propose_split_reschedule(
                source,
                record.allocator,
                record.exam_dates,
                daily_extra_minutes=daily_extra,
            )
            if remaining == 0:
                approved_slots = candidate_slots
                approved_extra = extra
                break
        if not approved_slots:
            if backlog_item not in record.plan.unscheduled:
                record.plan.unscheduled.append(backlog_item)
            proposal = _reschedule_proposal(
                source, record.exam_dates, "backlog"
            )
            repo.save(record, owner_id)
        else:
            replacements, changes = commit_reschedule(
                record.plan, source, record.allocator, approved_slots, split=True
            )
            if not replacements:
                raise HTTPException(
                    status_code=409,
                    detail="The recovery slots changed. Please try again.",
                )
            proposal = _reschedule_proposal(
                source,
                record.exam_dates,
                "scheduled",
                approved_slots,
                approved_extra,
            )
            repo.save(record, owner_id)

    return RescheduleResponse(
        sessions=record.plan.sessions,
        changes=changes,
        warnings=record.plan.warnings,
        unscheduled=record.plan.unscheduled,
        reschedule=proposal,
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


@router.post("/health/pairing", response_model=HealthPairingResponse)
def create_health_pairing(
    request: HealthPairingRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthPairingResponse:
    """Create a short-lived, one-use code for the Android companion."""
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    policy = health_policy()
    expires_at = datetime.now(UTC) + timedelta(minutes=policy.pairing_ttl_minutes)
    record.health_pairing = HealthPairing(
        code_hash=_secret_hash(code), expires_at=expires_at
    )
    repo.save(record, owner_id)
    return HealthPairingResponse(
        plan_id=record.plan_id,
        code=f"{code[:4]}-{code[4:]}",
        expires_at=expires_at,
    )


@router.post("/health/pairing/claim", response_model=HealthPairingClaimResponse)
def claim_health_pairing(
    request: HealthPairingClaimRequest,
    repo: PlanRepository = Depends(get_repo),
) -> HealthPairingClaimResponse:
    """Exchange a one-use code for a revocable companion bearer token."""
    code = _normalise_pairing_code(request.code)
    found = repo.find_by_health_pairing(_secret_hash(code))
    if found is None:
        raise HTTPException(status_code=404, detail="Pairing code is invalid or expired.")
    owner_id, record = found
    token = secrets.token_urlsafe(32)
    record.health_connection = HealthConnection(token_hash=_secret_hash(token))
    record.health_pairing = None
    repo.save(record, owner_id)
    return HealthPairingClaimResponse(plan_id=record.plan_id, access_token=token)


@router.post("/health/sync", response_model=HealthSyncResponse)
def sync_health_connect(
    request: HealthSyncRequest,
    authorization: str | None = Header(default=None),
    repo: PlanRepository = Depends(get_repo),
) -> HealthSyncResponse:
    """Accept daily aggregates from the paired companion, never raw HR samples."""
    owner_id, record = _record_for_health_token(authorization, repo)
    connection = record.health_connection
    if connection is None:
        raise HTTPException(status_code=401, detail="The companion connection was revoked.")
    if connection.status is HealthConnectionStatus.paused:
        raise HTTPException(status_code=409, detail="Health sync is paused in StudyGrid.")
    now = datetime.now(UTC)
    by_date = {item.occurred_on: item for item in record.health_summaries}
    for summary in request.summaries:
        by_date[summary.occurred_on] = summary.model_copy(update={"synced_at": now})
    cutoff = date.today() - timedelta(days=health_policy().retention_days - 1)
    record.health_summaries = sorted(
        (item for day, item in by_date.items() if day >= cutoff),
        key=lambda item: item.occurred_on,
    )
    record.health_connection = connection.model_copy(update={
        "last_synced_at": now,
        "permissions": sorted(set(request.permissions)),
        "sources": sorted(set(request.sources)),
    })
    repo.save(record, owner_id)
    return HealthSyncResponse(accepted_days=len(request.summaries), last_synced_at=now)


@router.get("/health/dashboard", response_model=HealthDashboardResponse)
def get_health_dashboard(
    plan_id: str = Query(min_length=1, max_length=100),
    days: int = Query(default=7),
    end: date | None = Query(default=None),
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthDashboardResponse:
    if days not in {7, 30}:
        raise HTTPException(status_code=422, detail="days must be 7 or 30.")
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return _health_dashboard_for(record, days, end or date.today())


@router.post("/health/check-in", response_model=HealthDashboardResponse)
def save_health_check_in(
    request: HealthCheckInRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthDashboardResponse:
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    existing = next(
        (item for item in record.health_summaries if item.occurred_on == request.occurred_on),
        None,
    )
    if existing:
        updated = existing.model_copy(update={
            "energy_level": request.energy_level,
            "feels_unwell": request.feels_unwell,
            "synced_at": datetime.now(UTC),
        })
        record.health_summaries = [
            updated if item.occurred_on == request.occurred_on else item
            for item in record.health_summaries
        ]
    else:
        record.health_summaries.append(DailyHealthSummary(
            occurred_on=request.occurred_on,
            energy_level=request.energy_level,
            feels_unwell=request.feels_unwell,
        ))
    record.health_summaries.sort(key=lambda item: item.occurred_on)
    repo.save(record, owner_id)
    return _health_dashboard_for(record, 7, request.occurred_on)


@router.post("/health/connection/pause", response_model=HealthDashboardResponse)
def pause_health_connection(
    request: HealthPlanRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthDashboardResponse:
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if record.health_connection is None:
        raise HTTPException(status_code=409, detail="Health Connect is not connected.")
    record.health_connection = record.health_connection.model_copy(
        update={"status": HealthConnectionStatus.paused}
    )
    repo.save(record, owner_id)
    return _health_dashboard_for(record, 7, date.today())


@router.post("/health/connection/resume", response_model=HealthDashboardResponse)
def resume_health_connection(
    request: HealthPlanRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthDashboardResponse:
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if record.health_connection is None:
        raise HTTPException(status_code=409, detail="Health Connect is not connected.")
    record.health_connection = record.health_connection.model_copy(
        update={"status": HealthConnectionStatus.connected}
    )
    repo.save(record, owner_id)
    return _health_dashboard_for(record, 7, date.today())


@router.delete("/health/connection", status_code=204)
def delete_health_connection(
    plan_id: str = Query(min_length=1, max_length=100),
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> None:
    record = repo.load(plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    record.health_pairing = None
    record.health_connection = None
    record.health_summaries = []
    record.health_adjustments = []
    repo.save(record, owner_id)


@router.post("/health/schedule/apply", response_model=HealthScheduleApplyResponse)
def apply_health_schedule(
    request: HealthScheduleApplyRequest,
    repo: PlanRepository = Depends(get_repo),
    owner_id: str = Depends(get_owner_id),
) -> HealthScheduleApplyResponse:
    """Apply the previewed low-readiness plan only after browser confirmation."""
    record = repo.load(request.plan_id, owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    readiness = assess_readiness(record.health_summaries, request.occurred_on)
    changes = apply_health_adjustment(record, readiness, request.occurred_on)
    if changes:
        record.health_adjustments.append(HealthAdjustmentLog(
            occurred_on=request.occurred_on,
            readiness_status=readiness.status,
            changes=changes,
        ))
        record.health_adjustments = record.health_adjustments[-50:]
    repo.save(record, owner_id)
    return HealthScheduleApplyResponse(
        sessions=record.plan.sessions,
        changes=changes,
        unscheduled=record.plan.unscheduled,
        readiness=readiness,
        recommendations=schedule_recommendations(record, readiness, request.occurred_on),
    )


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
