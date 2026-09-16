"""Provider-independent contract for material analysis."""

from __future__ import annotations

from typing import Protocol

from ..models import Topic


class LLMProvider(Protocol):
    """Turn unstructured course material into scheduler-ready topics."""

    def analyze(self, subject: str, text: str) -> list[Topic]: ...


class LLMProviderError(RuntimeError):
    """A provider request or response could not produce valid topics."""
