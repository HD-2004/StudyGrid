"""Time-use aggregation (HACKATHON.md 8.3).

Turns logged sessions into patterns a student can act on. Pure functions over a
session list: no I/O, no AI, no clock reads, so the output is reproducible in a
demo and testable in milliseconds.

Design constraint: never manufacture a pattern from too little data. Two missed
sessions is not a habit. Below MIN_FOR_PATTERNS the report still shows counts,
but withholds claims about trends.
"""

from __future__ import annotations

from collections import Counter

from .models import (
    Completion,
    Insights,
    MISS_REASON_LABELS,
    MissReason,
    Recall,
    ReasonCount,
    StudySession,
)

# Below this many logged sessions, report counts but not patterns.
MIN_FOR_PATTERNS = 5

_WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def build_insights(history: list[StudySession]) -> Insights:
    """Aggregate logged outcomes into a time-use report.

    Takes `plan.history`, the append-only outcome log, rather than the live
    session list: a rescheduled session is rewritten in place, so the live list
    no longer shows that it was missed.
    """
    logged = [s for s in history if s.completion is not Completion.planned]

    if not logged:
        return Insights(
            observations=[
                "Log a few sessions and this fills in with where your study time goes."
            ]
        )

    completed = [s for s in logged if s.completion is Completion.completed]
    partial = [s for s in logged if s.completion is Completion.partial]
    missed = [s for s in logged if s.completion is Completion.not_completed]

    # Partial sessions count toward studied time; a missed one contributes none.
    minutes_studied = sum(s.duration_minutes for s in completed)
    minutes_studied += sum(s.duration_minutes // 2 for s in partial)
    minutes_lost = sum(s.duration_minutes for s in missed)
    minutes_lost += sum(s.duration_minutes - s.duration_minutes // 2 for s in partial)

    # Reason tallies, ordered by how much time each one costs.
    reason_counts: Counter[MissReason] = Counter()
    reason_minutes: Counter[MissReason] = Counter()
    for s in logged:
        if s.miss_reason is None:
            continue
        lost = (
            s.duration_minutes
            if s.completion is Completion.not_completed
            else s.duration_minutes - s.duration_minutes // 2
        )
        reason_counts[s.miss_reason] += 1
        reason_minutes[s.miss_reason] += lost

    reasons = [
        ReasonCount(
            reason=reason,
            label=MISS_REASON_LABELS[reason],
            count=count,
            minutes_lost=reason_minutes[reason],
        )
        for reason, count in reason_counts.most_common()
    ]

    recall_mix = {
        level.value: sum(1 for s in logged if s.recall is level) for level in Recall
    }

    # Weekdays where more sessions are missed than kept.
    missed_by_day: Counter[int] = Counter(s.start.weekday() for s in missed)
    kept_by_day: Counter[int] = Counter(s.start.weekday() for s in completed)
    weak_weekdays = sorted(
        (day for day, n in missed_by_day.items() if n > kept_by_day.get(day, 0)),
        key=lambda d: (-missed_by_day[d], d),
    )

    confident = len(logged) >= MIN_FOR_PATTERNS
    observations = _observe(
        logged=logged,
        completed=completed,
        missed=missed,
        reasons=reasons,
        recall_mix=recall_mix,
        weak_weekdays=weak_weekdays,
        confident=confident,
        minutes_lost=minutes_lost,
    )

    return Insights(
        sessions_logged=len(logged),
        completed=len(completed),
        missed=len(missed),
        partial=len(partial),
        minutes_studied=minutes_studied,
        minutes_lost=minutes_lost,
        reasons=reasons,
        weak_weekdays=weak_weekdays if confident else [],
        recall_mix=recall_mix,
        observations=observations,
        confident=confident,
    )


def _observe(
    *,
    logged: list[StudySession],
    completed: list[StudySession],
    missed: list[StudySession],
    reasons: list[ReasonCount],
    recall_mix: dict[str, int],
    weak_weekdays: list[int],
    confident: bool,
    minutes_lost: int,
) -> list[str]:
    """Plain-language readings of the numbers.

    Written as statements a student can act on, not encouragement. Each one is
    tied to a specific count so nothing here is generic filler.
    """
    out: list[str] = []
    total = len(logged)

    if not confident:
        remaining = MIN_FOR_PATTERNS - total
        out.append(
            f"{total} session{'s' if total != 1 else ''} logged. "
            f"{remaining} more and patterns start to show."
        )

    rate = len(completed) / total
    if confident:
        out.append(f"You finish {rate:.0%} of the sessions you plan.")

    if reasons:
        top = reasons[0]
        hours = top.minutes_lost / 60
        if hours >= 1:
            out.append(
                f"{top.label.lower()} accounts for the most lost study time: "
                f"{hours:.1f} hours across {top.count} session"
                f"{'s' if top.count != 1 else ''}."
            )
        else:
            out.append(
                f"Most common reason for a missed session: {top.label.lower()} "
                f"({top.count}×)."
            )

    if confident and weak_weekdays:
        names = ", ".join(_WEEKDAY_NAMES[d] for d in weak_weekdays[:2])
        out.append(f"{names} rarely works out. Consider planning less on those days.")

    poor = recall_mix.get(Recall.poor.value, 0)
    if poor and poor >= max(1, total // 3):
        out.append(
            f"Recall was weak in {poor} of {total} sessions, so reviews are being "
            "pulled earlier."
        )

    if confident and rate >= 0.8 and minutes_lost == 0:
        out.append("Your plan matches your real week. No adjustment needed.")

    return out
