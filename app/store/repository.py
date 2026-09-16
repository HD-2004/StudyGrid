"""Plan persistence.

A stored plan needs three things to stay adaptable after the initial build:
the plan itself, the exam dates (so rescheduling knows its deadlines), and the
allocator state (so new sessions do not collide with existing ones).

Storing the allocator is deliberate. Rebuilding occupancy from the session list
on every request is possible but easy to get subtly wrong, and getting it wrong
means double-booked slots.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from ..models import Availability, StudyPlan
from ..scheduler import TimeAllocator


@dataclass
class PlanRecord:
    """Everything needed to serve and adapt one plan."""

    plan_id: str
    plan: StudyPlan
    availability: Availability
    exam_dates: dict[str, date]
    allocator: TimeAllocator
    # Stable session ids, assigned once so the frontend can reference sessions
    # across adaptations. Index into plan.sessions is not stable; sessions move.
    session_ids: dict[str, int] = field(default_factory=dict)


class PlanRepository(Protocol):
    """Storage contract. Implementations must not contain scheduling logic."""

    def save(self, record: PlanRecord) -> None: ...

    def load(self, plan_id: str) -> PlanRecord | None: ...

    def new_id(self) -> str: ...


class InMemoryRepository:
    """Process-local store. Sufficient for a single-user demo.

    Plans vanish on restart, which is acceptable: the demo loads seed data in
    one click. A SqliteRepository satisfying the same protocol can be added
    later without touching callers.
    """

    def __init__(self) -> None:
        self._records: dict[str, PlanRecord] = {}

    def save(self, record: PlanRecord) -> None:
        self._records[record.plan_id] = record

    def load(self, plan_id: str) -> PlanRecord | None:
        return self._records.get(plan_id)

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def clear(self) -> None:
        """Test and demo-reset helper."""
        self._records.clear()
