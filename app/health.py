"""Privacy-minimised health readiness and deadline-safe schedule adaptation."""

from __future__ import annotations

import os
from datetime import date, timedelta
from math import ceil
from statistics import median

from pydantic import BaseModel, Field

from .models import (
    Completion,
    DailyHealthSummary,
    HealthScheduleRecommendation,
    PlanChange,
    ChangeType,
    ReadinessAssessment,
    ReadinessFactor,
    ReadinessStatus,
    StudySession,
)
from .store.repository import PlanRecord


class HealthPolicy(BaseModel):
    baseline_days: int = Field(ge=3, le=30)
    minimum_baseline_days: int = Field(ge=2, le=14)
    ready_capacity_percent: int = Field(ge=50, le=100)
    reduce_capacity_percent: int = Field(ge=40, le=100)
    recovery_capacity_percent: int = Field(ge=25, le=100)
    pairing_ttl_minutes: int = Field(ge=2, le=60)
    retention_days: int = Field(ge=7, le=365)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def health_policy() -> HealthPolicy:
    """Read deploy-time policy so neither web nor Android hardcodes thresholds."""
    return HealthPolicy(
        baseline_days=_env_int("STUDYGRID_HEALTH_BASELINE_DAYS", 7),
        minimum_baseline_days=_env_int("STUDYGRID_HEALTH_MIN_BASELINE_DAYS", 3),
        ready_capacity_percent=_env_int("STUDYGRID_HEALTH_READY_CAPACITY", 100),
        reduce_capacity_percent=_env_int("STUDYGRID_HEALTH_REDUCE_CAPACITY", 80),
        recovery_capacity_percent=_env_int("STUDYGRID_HEALTH_RECOVERY_CAPACITY", 60),
        pairing_ttl_minutes=_env_int("STUDYGRID_HEALTH_PAIRING_TTL_MINUTES", 10),
        retention_days=_env_int("STUDYGRID_HEALTH_RETENTION_DAYS", 90),
    )


def _metric_median(
    values: list[DailyHealthSummary], attribute: str
) -> float | None:
    present = [float(value) for item in values if (value := getattr(item, attribute)) is not None]
    return median(present) if present else None


def assess_readiness(
    summaries: list[DailyHealthSummary],
    on_date: date,
    policy: HealthPolicy | None = None,
) -> ReadinessAssessment:
    """Compare today's aggregates with the user's recent personal baseline."""
    policy = policy or health_policy()
    ordered = sorted(summaries, key=lambda item: item.occurred_on)
    current = next((item for item in reversed(ordered) if item.occurred_on == on_date), None)
    history = [
        item
        for item in ordered
        if on_date - timedelta(days=policy.baseline_days) <= item.occurred_on < on_date
    ]
    sleep_baseline = _metric_median(history, "sleep_minutes")
    hr_baseline = _metric_median(history, "resting_heart_rate_bpm")
    hrv_baseline = _metric_median(history, "hrv_rmssd_ms")

    if current is None or len(history) < policy.minimum_baseline_days:
        missing = "Chưa có dữ liệu hôm nay." if current is None else (
            f"Cần ít nhất {policy.minimum_baseline_days} ngày nền; hiện có {len(history)} ngày."
        )
        return ReadinessAssessment(
            occurred_on=on_date,
            status=ReadinessStatus.insufficient_data,
            capacity_percent=policy.ready_capacity_percent,
            confidence="low",
            baseline_days=len(history),
            factors=[ReadinessFactor(
                key="history",
                label="Chưa đủ dữ liệu",
                impact="neutral",
                detail=missing,
            )],
            sleep_baseline_minutes=sleep_baseline,
            resting_hr_baseline_bpm=hr_baseline,
            hrv_baseline_rmssd_ms=hrv_baseline,
        )

    score = 100
    factors: list[ReadinessFactor] = []
    signal_count = 0

    if current.sleep_minutes is not None and sleep_baseline:
        signal_count += 1
        ratio = current.sleep_minutes / sleep_baseline
        if ratio < 0.75:
            score -= 28
            impact = "negative"
            detail = f"Ngủ ít hơn nền cá nhân {round((1 - ratio) * 100)}%."
        elif ratio < 0.9:
            score -= 14
            impact = "negative"
            detail = f"Ngủ ít hơn nền cá nhân {round((1 - ratio) * 100)}%."
        else:
            score += 3 if ratio >= 1.05 else 0
            impact = "positive" if ratio >= 1.05 else "neutral"
            detail = "Thời lượng ngủ gần với mức nền cá nhân."
        factors.append(ReadinessFactor(
            key="sleep", label="Giấc ngủ", impact=impact, detail=detail
        ))

    if current.resting_heart_rate_bpm is not None and hr_baseline:
        signal_count += 1
        delta = current.resting_heart_rate_bpm - hr_baseline
        if delta >= 10:
            score -= 24
            impact = "negative"
            detail = f"Nhịp tim nghỉ cao hơn nền {delta:.0f} bpm."
        elif delta >= 5:
            score -= 12
            impact = "negative"
            detail = f"Nhịp tim nghỉ cao hơn nền {delta:.0f} bpm."
        else:
            impact = "positive" if delta <= -3 else "neutral"
            detail = "Nhịp tim nghỉ gần với mức nền cá nhân."
        factors.append(ReadinessFactor(
            key="resting_hr", label="Nhịp tim nghỉ", impact=impact, detail=detail
        ))

    if current.hrv_rmssd_ms is not None and hrv_baseline:
        signal_count += 1
        ratio = current.hrv_rmssd_ms / hrv_baseline
        if ratio < 0.7:
            score -= 18
            impact = "negative"
            detail = "HRV thấp đáng kể so với mức nền cá nhân."
        elif ratio < 0.85:
            score -= 8
            impact = "negative"
            detail = "HRV thấp hơn mức nền cá nhân."
        else:
            impact = "positive" if ratio >= 1.05 else "neutral"
            detail = "HRV gần với mức nền cá nhân."
        factors.append(ReadinessFactor(
            key="hrv", label="Biến thiên nhịp tim", impact=impact, detail=detail
        ))

    if current.energy_level is not None:
        signal_count += 1
        if current.energy_level <= 2:
            score -= 16
            impact = "negative"
            detail = f"Bạn tự đánh giá năng lượng {current.energy_level}/5."
        elif current.energy_level >= 4:
            score += 3
            impact = "positive"
            detail = f"Bạn tự đánh giá năng lượng {current.energy_level}/5."
        else:
            impact = "neutral"
            detail = "Mức năng lượng tự đánh giá ở mức trung bình."
        factors.append(ReadinessFactor(
            key="energy", label="Tự đánh giá", impact=impact, detail=detail
        ))

    if current.feels_unwell:
        signal_count += 1
        score -= 40
        factors.append(ReadinessFactor(
            key="unwell",
            label="Cảm thấy không khỏe",
            impact="negative",
            detail="Ưu tiên hồi phục; hãy tìm hỗ trợ y tế nếu triệu chứng đáng lo.",
        ))

    if current.feels_unwell or score <= 55:
        status = ReadinessStatus.recovery
        capacity = policy.recovery_capacity_percent
    elif score <= 78:
        status = ReadinessStatus.reduce_load
        capacity = policy.reduce_capacity_percent
    else:
        status = ReadinessStatus.ready
        capacity = policy.ready_capacity_percent

    confidence = "high" if signal_count >= 3 and len(history) >= 5 else (
        "medium" if signal_count >= 2 else "low"
    )
    return ReadinessAssessment(
        occurred_on=on_date,
        status=status,
        capacity_percent=capacity,
        confidence=confidence,
        factors=factors or [ReadinessFactor(
            key="signals",
            label="Chưa đủ chỉ số",
            impact="neutral",
            detail="Đã có ngày dữ liệu nhưng chưa có đủ chỉ số để so sánh.",
        )],
        baseline_days=len(history),
        sleep_baseline_minutes=sleep_baseline,
        resting_hr_baseline_bpm=hr_baseline,
        hrv_baseline_rmssd_ms=hrv_baseline,
    )


def schedule_recommendations(
    record: PlanRecord,
    assessment: ReadinessAssessment,
    on_date: date,
) -> list[HealthScheduleRecommendation]:
    pending = [
        session
        for session in record.plan.sessions
        if session.start.date() == on_date and session.completion is Completion.planned
    ]
    if not pending:
        return [HealthScheduleRecommendation(
            id="no-pending",
            kind="no_change",
            title="Không có khối Pending hôm nay",
            detail="Lịch không cần điều chỉnh.",
        )]
    if assessment.status in {ReadinessStatus.insufficient_data, ReadinessStatus.ready}:
        detail = (
            "Giữ nguyên lịch cho đến khi có đủ dữ liệu nền."
            if assessment.status is ReadinessStatus.insufficient_data
            else "Các chỉ số hôm nay không yêu cầu giảm tải."
        )
        return [HealthScheduleRecommendation(
            id="keep-current",
            kind="no_change",
            title="Giữ nguyên kế hoạch",
            detail=detail,
        )]

    nearest_deadline = min(
        (record.exam_dates.get(session.subject, on_date + timedelta(days=365)) for session in pending),
        default=on_date + timedelta(days=365),
    )

    def is_protected(session: StudySession) -> bool:
        deadline = record.exam_dates.get(session.subject, on_date + timedelta(days=365))
        priority = record.subject_priorities.get(session.subject, 3)
        return deadline <= on_date + timedelta(days=3) or deadline == nearest_deadline or priority >= 4

    recommendations: list[HealthScheduleRecommendation] = []
    protected = [session for session in pending if is_protected(session)]
    for session in protected:
        deadline = record.exam_dates.get(session.subject)
        recommendations.append(HealthScheduleRecommendation(
            id=f"protect-{session.id}",
            kind="protect",
            title=f"Giữ {session.topic}",
            detail=(
                f"Được bảo vệ vì hạn {deadline.isoformat()} hoặc mức ưu tiên cao."
                if deadline else "Được bảo vệ vì mức ưu tiên cao."
            ),
            session_id=session.id,
            protected=True,
            keep_minutes=session.duration_minutes,
        ))

    scheduled_minutes = sum(session.duration_minutes for session in pending)
    configured_capacity = record.availability.weekday_minutes.get(on_date.weekday(), scheduled_minutes)
    configured_capacity = configured_capacity or scheduled_minutes
    target_minutes = max(15, configured_capacity * assessment.capacity_percent // 100)
    reduction_left = max(0, scheduled_minutes - target_minutes)
    preferred = 30 if assessment.status is ReadinessStatus.recovery else 45
    minimum_keep = 15 if assessment.status is ReadinessStatus.recovery else 30
    flexible = sorted(
        (session for session in pending if not is_protected(session)),
        key=lambda session: (
            record.subject_priorities.get(session.subject, 3),
            -record.exam_dates.get(session.subject, on_date + timedelta(days=365)).toordinal(),
            -session.duration_minutes,
        ),
    )
    for session in flexible:
        if reduction_left <= 0:
            break
        if f"health-adjusted:{on_date.isoformat()}" in session.rationale:
            continue
        available = max(0, session.duration_minutes - minimum_keep)
        if available < 15:
            continue
        deferred = min(available, max(15, ceil(reduction_left / 15) * 15))
        keep = session.duration_minutes - deferred
        recommendations.append(HealthScheduleRecommendation(
            id=f"shorten-{session.id}",
            kind="shorten_move",
            title=f"Rút gọn {session.topic}",
            detail=f"Học {keep} phút hôm nay và dời {deferred} phút sang khung trống trước hạn.",
            session_id=session.id,
            keep_minutes=keep,
            defer_minutes=deferred,
        ))
        reduction_left -= deferred

    recommendations.append(HealthScheduleRecommendation(
        id="recovery-breaks",
        kind="recovery_break",
        title="Giữ khoảng nghỉ phục hồi",
        detail=f"Ưu tiên các khối tối đa {preferred} phút; lịch mới vẫn tuân thủ khoảng nghỉ của bạn.",
    ))
    if reduction_left > 0:
        recommendations.append(HealthScheduleRecommendation(
            id="protected-capacity",
            kind="no_change",
            title="Khối khẩn cấp vượt mức giảm tải",
            detail=(
                f"Còn {reduction_left} phút được giữ vì deadline/ưu tiên. "
                "StudyGrid không tự dời các khối này."
            ),
            protected=True,
        ))
    return recommendations


def apply_health_adjustment(
    record: PlanRecord,
    assessment: ReadinessAssessment,
    on_date: date,
) -> list[PlanChange]:
    """Apply only previewed flexible reductions; protected work never moves."""
    recommendations = schedule_recommendations(record, assessment, on_date)
    changes: list[PlanChange] = []
    for recommendation in recommendations:
        if recommendation.kind != "shorten_move" or not recommendation.session_id:
            continue
        session = next(
            (item for item in record.plan.sessions if item.id == recommendation.session_id),
            None,
        )
        if session is None or session.completion is not Completion.planned:
            continue
        original_slot = (session.start, session.end)
        shortened_end = session.start + timedelta(minutes=recommendation.keep_minutes)
        record.allocator.release(original_slot)
        if not record.allocator.reserve_exact((session.start, shortened_end)):
            record.allocator.reserve_exact(original_slot)
            continue
        session.end = shortened_end
        session.rationale = (
            f"Health-adjusted:{on_date.isoformat()} — shortened after explicit confirmation"
        )
        changes.append(PlanChange(
            type=ChangeType.kept,
            topic=session.topic,
            session_id=session.id,
            why=f"Kept {recommendation.keep_minutes} minutes today and protected its deadline.",
        ))

        remaining = recommendation.defer_minutes
        deadline = record.exam_dates.get(session.subject, on_date + timedelta(days=7))
        earliest = on_date + timedelta(days=1)
        preferred = 30 if assessment.status is ReadinessStatus.recovery else 45
        while remaining > 0 and earliest <= deadline:
            chunk = min(preferred, remaining)
            slot = record.allocator.allocate(chunk, earliest, deadline)
            if slot is None and chunk > 15:
                chunk = min(15, remaining)
                slot = record.allocator.allocate(chunk, earliest, deadline)
            if slot is None:
                break
            replacement = StudySession(
                subject=session.subject,
                topic=session.topic,
                start=slot[0],
                end=slot[1],
                repetition=session.repetition,
                rationale=(
                    f"Health-adjusted:{on_date.isoformat()} — deferred from a lower-readiness day"
                ),
                rescheduled_from_id=session.id,
            )
            record.plan.sessions.append(replacement)
            changes.append(PlanChange(
                type=ChangeType.moved,
                topic=session.topic,
                session_id=replacement.id,
                moved_from=original_slot[0],
                moved_to=slot[0],
                why="Moved a flexible portion while keeping deadline-priority work in place.",
            ))
            remaining -= chunk
        if remaining:
            backlog = f"{session.subject}: {session.topic} · {remaining} min (health recovery)"
            if backlog not in record.plan.unscheduled:
                record.plan.unscheduled.append(backlog)
            changes.append(PlanChange(
                type=ChangeType.blocked,
                topic=session.topic,
                session_id=session.id,
                why=f"{remaining} minutes could not fit before the deadline and remain unscheduled.",
            ))
    record.plan.sessions.sort(key=lambda item: item.start)
    return changes
