"""Owner-scoped time-use aggregation for the Progress surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import ACTIVITY_CATEGORY_LABELS, ActivityCategory, ActivityLog


@dataclass(frozen=True)
class ActivitySummary:
    start: date
    end: date
    days: int
    daily: list[tuple[date, dict[ActivityCategory, int]]]
    totals: list[tuple[ActivityCategory, str, int]]


def summarize_activities(
    activities: list[ActivityLog], days: int, end: date
) -> ActivitySummary:
    """Return dense day/category buckets so the UI never invents missing data."""
    if days not in {7, 30}:
        raise ValueError("Activity analytics supports 7 or 30 days.")

    start = end - timedelta(days=days - 1)
    categories = list(ActivityCategory)
    daily_map = {
        start + timedelta(days=offset): {category: 0 for category in categories}
        for offset in range(days)
    }
    totals = {category: 0 for category in categories}

    for activity in activities:
        if activity.occurred_on not in daily_map:
            continue
        daily_map[activity.occurred_on][activity.category] += activity.minutes
        totals[activity.category] += activity.minutes

    return ActivitySummary(
        start=start,
        end=end,
        days=days,
        daily=list(daily_map.items()),
        totals=[
            (category, ACTIVITY_CATEGORY_LABELS[category], totals[category])
            for category in categories
            if category is not ActivityCategory.other or totals[category] > 0
        ],
    )
