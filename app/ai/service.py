"""Provider selection, semantic validation, and fallback orchestration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

from ..models import Topic
from .fallback import FallbackAnalyzer
from .openai import OpenAIProvider
from .provider import LLMProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisResult:
    topics: list[Topic]
    source: Literal["ai", "fallback"]


def _normalize_topics(topics: list[Topic]) -> list[Topic]:
    """Clean provider output and keep dependency names internally consistent."""
    unique: list[Topic] = []
    names: dict[str, str] = {}

    for topic in topics[:30]:
        name = " ".join(topic.name.split())
        key = name.casefold()
        if not name or key in names:
            continue
        names[key] = name
        unique.append(topic.model_copy(update={"name": name}))

    normalized: list[Topic] = []
    for topic in unique:
        dependencies: list[str] = []
        seen_dependencies: set[str] = set()
        for dependency in topic.depends_on:
            key = " ".join(dependency.split()).casefold()
            canonical = names.get(key)
            if (
                canonical is None
                or canonical.casefold() == topic.name.casefold()
                or key in seen_dependencies
            ):
                continue
            seen_dependencies.add(key)
            dependencies.append(canonical)
        normalized.append(topic.model_copy(update={"depends_on": dependencies}))

    if not normalized:
        raise ValueError("Analyzer returned no usable topics")
    return normalized


class MaterialAnalyzer:
    """Use the configured provider when possible and always retain a fallback."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        fallback: FallbackAnalyzer | None = None,
    ) -> None:
        self.provider = provider
        self.fallback = fallback or FallbackAnalyzer()

    def analyze(self, subject: str, text: str) -> AnalysisResult:
        if self.provider is not None:
            try:
                topics = _normalize_topics(self.provider.analyze(subject, text))
                return AnalysisResult(topics=topics, source="ai")
            except Exception:
                # The fallback is a deliberate demo reliability boundary. Do not
                # expose provider credentials, response bodies, or failures to users.
                logger.warning(
                    "Material-analysis provider failed; using deterministic fallback.",
                    exc_info=True,
                )

        topics = _normalize_topics(self.fallback.analyze(subject, text))
        return AnalysisResult(topics=topics, source="fallback")


def build_analyzer_from_env() -> MaterialAnalyzer:
    """Build the configured analyzer; incomplete configuration means fallback-only."""
    load_dotenv()
    provider_name = os.getenv("LLM_PROVIDER", "fallback").strip().casefold()

    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-6-astra").strip()
        if api_key:
            try:
                timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
                if timeout <= 0:
                    raise ValueError
            except ValueError:
                logger.warning(
                    "Invalid OPENAI_TIMEOUT_SECONDS; using the 20-second default."
                )
                timeout = 20.0
            return MaterialAnalyzer(
                provider=OpenAIProvider(
                    api_key=api_key,
                    model=model,
                    timeout_seconds=timeout,
                )
            )
        logger.info("OPENAI_API_KEY is unset; material analysis will use fallback.")
    elif provider_name not in {"", "fallback", "none"}:
        logger.warning("Unknown LLM_PROVIDER %r; using fallback.", provider_name)

    return MaterialAnalyzer()
