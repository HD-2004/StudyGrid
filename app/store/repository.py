"""Plan persistence with owner isolation and optional SQLite durability."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from ..models import (
    ActivityLog,
    Availability,
    ChatMessage,
    DailyHealthSummary,
    HealthAdjustmentLog,
    HealthConnection,
    HealthPairing,
    StudyPlan,
)
from ..scheduler import TimeAllocator


@dataclass
class PlanRecord:
    """Everything needed to serve and adapt one plan."""

    plan_id: str
    plan: StudyPlan
    availability: Availability
    exam_dates: dict[str, date]
    allocator: TimeAllocator
    session_ids: dict[str, int] = field(default_factory=dict)
    chat_history: list[ChatMessage] = field(default_factory=list)
    subject_priorities: dict[str, int] = field(default_factory=dict)
    health_pairing: HealthPairing | None = None
    health_connection: HealthConnection | None = None
    health_summaries: list[DailyHealthSummary] = field(default_factory=list)
    health_adjustments: list[HealthAdjustmentLog] = field(default_factory=list)


class PlanRepository(Protocol):
    """Storage contract. Every plan operation is scoped to one owner."""

    retention_days: int
    durable: bool

    def save(self, record: PlanRecord, owner_id: str) -> None: ...

    def load(self, plan_id: str, owner_id: str) -> PlanRecord | None: ...

    def latest(self, owner_id: str) -> PlanRecord | None: ...

    def find_by_health_pairing(self, code_hash: str) -> tuple[str, PlanRecord] | None: ...

    def find_by_health_token(self, token_hash: str) -> tuple[str, PlanRecord] | None: ...

    def delete(self, plan_id: str, owner_id: str) -> bool: ...

    def delete_owner(self, owner_id: str) -> int: ...

    def save_activity(self, activity: ActivityLog, owner_id: str) -> None: ...

    def load_activity(self, activity_id: str, owner_id: str) -> ActivityLog | None: ...

    def list_activities(
        self, owner_id: str, start: date, end: date
    ) -> list[ActivityLog]: ...

    def delete_activity(self, activity_id: str, owner_id: str) -> bool: ...

    def new_id(self) -> str: ...


class InMemoryRepository:
    """Process-local implementation used when no database path is configured."""

    def __init__(self, retention_days: int = 30) -> None:
        self.retention_days = retention_days
        self.durable = False
        self._records: dict[str, tuple[str, PlanRecord, datetime]] = {}
        self._activities: dict[str, tuple[str, ActivityLog]] = {}

    def save(self, record: PlanRecord, owner_id: str) -> None:
        existing = self._records.get(record.plan_id)
        if existing is not None and existing[0] != owner_id:
            raise PermissionError("Plan id belongs to another owner.")
        self._records[record.plan_id] = (owner_id, record, datetime.now(UTC))

    def load(self, plan_id: str, owner_id: str) -> PlanRecord | None:
        stored = self._records.get(plan_id)
        if stored is None or stored[0] != owner_id:
            return None
        return stored[1]

    def latest(self, owner_id: str) -> PlanRecord | None:
        owned = [entry for entry in self._records.values() if entry[0] == owner_id]
        return max(owned, key=lambda entry: entry[2])[1] if owned else None

    def find_by_health_pairing(self, code_hash: str) -> tuple[str, PlanRecord] | None:
        now = datetime.now(UTC)
        for owner_id, record, _ in self._records.values():
            pairing = record.health_pairing
            if pairing and pairing.code_hash == code_hash and pairing.expires_at > now:
                return owner_id, record
        return None

    def find_by_health_token(self, token_hash: str) -> tuple[str, PlanRecord] | None:
        for owner_id, record, _ in self._records.values():
            connection = record.health_connection
            if connection and connection.token_hash == token_hash:
                return owner_id, record
        return None

    def delete(self, plan_id: str, owner_id: str) -> bool:
        stored = self._records.get(plan_id)
        if stored is None or stored[0] != owner_id:
            return False
        del self._records[plan_id]
        for activity_id, entry in list(self._activities.items()):
            if entry[0] == owner_id and entry[1].plan_id == plan_id:
                del self._activities[activity_id]
        return True

    def delete_owner(self, owner_id: str) -> int:
        plan_ids = [plan_id for plan_id, entry in self._records.items() if entry[0] == owner_id]
        for plan_id in plan_ids:
            del self._records[plan_id]
        activity_ids = [
            activity_id
            for activity_id, entry in self._activities.items()
            if entry[0] == owner_id
        ]
        for activity_id in activity_ids:
            del self._activities[activity_id]
        return len(plan_ids) + len(activity_ids)

    def save_activity(self, activity: ActivityLog, owner_id: str) -> None:
        existing = self._activities.get(activity.id)
        if existing is not None and existing[0] != owner_id:
            raise PermissionError("Activity id belongs to another owner.")
        self._activities[activity.id] = (owner_id, activity)

    def load_activity(self, activity_id: str, owner_id: str) -> ActivityLog | None:
        stored = self._activities.get(activity_id)
        if stored is None or stored[0] != owner_id:
            return None
        if stored[1].created_at <= datetime.now(UTC) - timedelta(days=self.retention_days):
            del self._activities[activity_id]
            return None
        return stored[1]

    def list_activities(self, owner_id: str, start: date, end: date) -> list[ActivityLog]:
        return sorted(
            (
                entry[1]
                for entry in self._activities.values()
                if entry[0] == owner_id
                and entry[1].created_at > datetime.now(UTC) - timedelta(days=self.retention_days)
                and start <= entry[1].occurred_on <= end
            ),
            key=lambda activity: (activity.occurred_on, activity.created_at),
            reverse=True,
        )

    def delete_activity(self, activity_id: str, owner_id: str) -> bool:
        stored = self._activities.get(activity_id)
        if stored is None or stored[0] != owner_id:
            return False
        del self._activities[activity_id]
        return True

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def clear(self) -> None:
        self._records.clear()
        self._activities.clear()


class SqliteRepository:
    """SQLite-backed plan store safe for one shared application instance."""

    _SCHEMA_VERSION = 2

    def __init__(self, path: str | Path, retention_days: int = 30) -> None:
        self.path = Path(path)
        self.retention_days = retention_days
        self.durable = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode = WAL")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version == 0:
                connection.executescript(
                    """
                    CREATE TABLE plans (
                        plan_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    CREATE INDEX plans_owner_updated
                        ON plans(owner_id, updated_at DESC);
                    CREATE INDEX plans_expiry ON plans(expires_at);
                    CREATE TABLE activity_logs (
                        activity_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        occurred_on TEXT NOT NULL,
                        category TEXT NOT NULL,
                        label TEXT NOT NULL,
                        minutes INTEGER NOT NULL,
                        note TEXT NOT NULL,
                        source TEXT NOT NULL,
                        source_id TEXT,
                        plan_id TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX activity_owner_date
                        ON activity_logs(owner_id, occurred_on DESC, created_at DESC);
                    CREATE INDEX activity_plan
                        ON activity_logs(owner_id, plan_id);
                    PRAGMA user_version = 2;
                    """
                )
            elif version == 1:
                connection.executescript(
                    """
                    CREATE TABLE activity_logs (
                        activity_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        occurred_on TEXT NOT NULL,
                        category TEXT NOT NULL,
                        label TEXT NOT NULL,
                        minutes INTEGER NOT NULL,
                        note TEXT NOT NULL,
                        source TEXT NOT NULL,
                        source_id TEXT,
                        plan_id TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX activity_owner_date
                        ON activity_logs(owner_id, occurred_on DESC, created_at DESC);
                    CREATE INDEX activity_plan
                        ON activity_logs(owner_id, plan_id);
                    PRAGMA user_version = 2;
                    """
                )
            elif version != self._SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported StudyGrid database schema {version}; "
                    f"expected {self._SCHEMA_VERSION}."
                )

    @staticmethod
    def _encode(record: PlanRecord) -> str:
        return json.dumps(
            {
                "plan": record.plan.model_dump(mode="json"),
                "availability": record.availability.model_dump(mode="json"),
                "exam_dates": {
                    subject: exam_date.isoformat()
                    for subject, exam_date in record.exam_dates.items()
                },
                "allocator": record.allocator.export_state(),
                "session_ids": record.session_ids,
                "chat_history": [
                    message.model_dump(mode="json") for message in record.chat_history
                ],
                "subject_priorities": record.subject_priorities,
                "health_pairing": (
                    record.health_pairing.model_dump(mode="json")
                    if record.health_pairing
                    else None
                ),
                "health_connection": (
                    record.health_connection.model_dump(mode="json")
                    if record.health_connection
                    else None
                ),
                "health_summaries": [
                    summary.model_dump(mode="json")
                    for summary in record.health_summaries
                ],
                "health_adjustments": [
                    adjustment.model_dump(mode="json")
                    for adjustment in record.health_adjustments
                ],
            },
            separators=(",", ":"),
        )

    @staticmethod
    def _decode(plan_id: str, payload: str) -> PlanRecord:
        raw = json.loads(payload)
        availability = Availability.model_validate(raw["availability"])
        return PlanRecord(
            plan_id=plan_id,
            plan=StudyPlan.model_validate(raw["plan"]),
            availability=availability,
            exam_dates={
                subject: date.fromisoformat(exam_date)
                for subject, exam_date in raw["exam_dates"].items()
            },
            allocator=TimeAllocator.from_state(availability, raw["allocator"]),
            session_ids={
                key: int(value) for key, value in raw.get("session_ids", {}).items()
            },
            chat_history=[
                ChatMessage.model_validate(message)
                for message in raw.get("chat_history", [])
            ],
            subject_priorities={
                subject: int(priority)
                for subject, priority in raw.get("subject_priorities", {}).items()
            },
            health_pairing=(
                HealthPairing.model_validate(raw["health_pairing"])
                if raw.get("health_pairing")
                else None
            ),
            health_connection=(
                HealthConnection.model_validate(raw["health_connection"])
                if raw.get("health_connection")
                else None
            ),
            health_summaries=[
                DailyHealthSummary.model_validate(summary)
                for summary in raw.get("health_summaries", [])
            ],
            health_adjustments=[
                HealthAdjustmentLog.model_validate(adjustment)
                for adjustment in raw.get("health_adjustments", [])
            ],
        )

    def _cleanup_expired(self, connection: sqlite3.Connection) -> None:
        now = datetime.now(UTC)
        connection.execute(
            "DELETE FROM plans WHERE expires_at <= ?", (now.isoformat(),)
        )
        connection.execute(
            "DELETE FROM activity_logs WHERE created_at <= ?",
            ((now - timedelta(days=self.retention_days)).isoformat(),),
        )

    def save(self, record: PlanRecord, owner_id: str) -> None:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=self.retention_days)
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            cursor = connection.execute(
                """
                INSERT INTO plans (
                    plan_id, owner_id, payload, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                WHERE plans.owner_id = excluded.owner_id
                """,
                (
                    record.plan_id,
                    owner_id,
                    self._encode(record),
                    now.isoformat(),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Plan id belongs to another owner.")

    def load(self, plan_id: str, owner_id: str) -> PlanRecord | None:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            row = connection.execute(
                "SELECT payload FROM plans WHERE plan_id = ? AND owner_id = ?",
                (plan_id, owner_id),
            ).fetchone()
        return self._decode(plan_id, row["payload"]) if row is not None else None

    def latest(self, owner_id: str) -> PlanRecord | None:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            row = connection.execute(
                """
                SELECT plan_id, payload FROM plans
                WHERE owner_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (owner_id,),
            ).fetchone()
        return self._decode(row["plan_id"], row["payload"]) if row is not None else None

    def _find_by_health_secret(
        self, field: str, secret_hash: str
    ) -> tuple[str, PlanRecord] | None:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            rows = connection.execute(
                "SELECT plan_id, owner_id, payload FROM plans ORDER BY updated_at DESC"
            ).fetchall()
        for row in rows:
            record = self._decode(row["plan_id"], row["payload"])
            if field == "pairing":
                pairing = record.health_pairing
                if (
                    pairing
                    and pairing.code_hash == secret_hash
                    and pairing.expires_at > datetime.now(UTC)
                ):
                    return row["owner_id"], record
            else:
                connection = record.health_connection
                if connection and connection.token_hash == secret_hash:
                    return row["owner_id"], record
        return None

    def find_by_health_pairing(self, code_hash: str) -> tuple[str, PlanRecord] | None:
        return self._find_by_health_secret("pairing", code_hash)

    def find_by_health_token(self, token_hash: str) -> tuple[str, PlanRecord] | None:
        return self._find_by_health_secret("token", token_hash)

    def delete(self, plan_id: str, owner_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM plans WHERE plan_id = ? AND owner_id = ?",
                (plan_id, owner_id),
            )
            if cursor.rowcount == 1:
                connection.execute(
                    "DELETE FROM activity_logs WHERE owner_id = ? AND plan_id = ?",
                    (owner_id, plan_id),
                )
        return cursor.rowcount == 1

    def delete_owner(self, owner_id: str) -> int:
        with closing(self._connect()) as connection, connection:
            plans = connection.execute(
                "DELETE FROM plans WHERE owner_id = ?", (owner_id,)
            )
            activities = connection.execute(
                "DELETE FROM activity_logs WHERE owner_id = ?", (owner_id,)
            )
        return plans.rowcount + activities.rowcount

    def save_activity(self, activity: ActivityLog, owner_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            cursor = connection.execute(
                """
                INSERT INTO activity_logs (
                    activity_id, owner_id, occurred_on, category, label, minutes,
                    note, source, source_id, plan_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    occurred_on = excluded.occurred_on,
                    category = excluded.category,
                    label = excluded.label,
                    minutes = excluded.minutes,
                    note = excluded.note,
                    source = excluded.source,
                    source_id = excluded.source_id,
                    plan_id = excluded.plan_id
                WHERE activity_logs.owner_id = excluded.owner_id
                """,
                (
                    activity.id,
                    owner_id,
                    activity.occurred_on.isoformat(),
                    activity.category.value,
                    activity.label,
                    activity.minutes,
                    activity.note,
                    activity.source.value,
                    activity.source_id,
                    activity.plan_id,
                    activity.created_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Activity id belongs to another owner.")

    @staticmethod
    def _activity_from_row(row: sqlite3.Row) -> ActivityLog:
        return ActivityLog.model_validate(
            {
                "id": row["activity_id"],
                "occurred_on": row["occurred_on"],
                "category": row["category"],
                "label": row["label"],
                "minutes": row["minutes"],
                "note": row["note"],
                "source": row["source"],
                "source_id": row["source_id"],
                "plan_id": row["plan_id"],
                "created_at": row["created_at"],
            }
        )

    def load_activity(self, activity_id: str, owner_id: str) -> ActivityLog | None:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            row = connection.execute(
                "SELECT * FROM activity_logs WHERE activity_id = ? AND owner_id = ?",
                (activity_id, owner_id),
            ).fetchone()
        return self._activity_from_row(row) if row is not None else None

    def list_activities(self, owner_id: str, start: date, end: date) -> list[ActivityLog]:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            rows = connection.execute(
                """
                SELECT * FROM activity_logs
                WHERE owner_id = ? AND occurred_on BETWEEN ? AND ?
                ORDER BY occurred_on DESC, created_at DESC
                """,
                (owner_id, start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._activity_from_row(row) for row in rows]

    def delete_activity(self, activity_id: str, owner_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            self._cleanup_expired(connection)
            cursor = connection.execute(
                "DELETE FROM activity_logs WHERE activity_id = ? AND owner_id = ?",
                (activity_id, owner_id),
            )
        return cursor.rowcount == 1

    def new_id(self) -> str:
        return uuid.uuid4().hex


def build_repository_from_env() -> PlanRepository:
    """Use SQLite when configured; retain an in-memory local-dev fallback."""
    load_dotenv()
    retention_days = int(os.getenv("PLAN_RETENTION_DAYS", "30"))
    if not 1 <= retention_days <= 365:
        raise ValueError("PLAN_RETENTION_DAYS must be between 1 and 365.")
    database_path = os.getenv("STUDYGRID_DB_PATH", "").strip()
    if database_path:
        return SqliteRepository(database_path, retention_days=retention_days)
    return InMemoryRepository(retention_days=retention_days)
