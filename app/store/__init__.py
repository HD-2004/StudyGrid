"""Data layer. Persistence and nothing else.

Everything above this layer depends on the PlanRepository protocol, never on a
concrete implementation. SQLite is on the cut list, so the in-memory store is
the default and the interface exists from day one to make swapping cheap.
"""

from .repository import InMemoryRepository, PlanRecord, PlanRepository

__all__ = ["InMemoryRepository", "PlanRecord", "PlanRepository"]
