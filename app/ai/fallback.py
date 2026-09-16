"""Deterministic material analyzer used when no model is available."""

from __future__ import annotations

import re

from ..models import Difficulty, Topic

_MAX_TOPICS = 24
_BULLET_PREFIX = re.compile(
    r"^\s*(?:#{1,6}\s*|[-*+\u2022]\s*|\d{1,3}[.)]\s*|[A-Za-z][.)]\s*)"
)
_SECTION_PREFIX = re.compile(
    r"^(?:week|unit|module|chapter|lesson|topic|section)\s+[\w.-]+\s*[:\-]\s*",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

_METADATA_PREFIXES = (
    "course code",
    "course title",
    "instructor",
    "lecturer",
    "email",
    "office hours",
    "assessment",
    "grading",
    "attendance",
    "textbook",
    "references",
)
_EASY_HINTS = {
    "introduction",
    "overview",
    "basics",
    "basic",
    "fundamentals",
    "terminology",
}
_HARD_HINTS = {
    "advanced",
    "proof",
    "derivation",
    "optimization",
    "eigenvalue",
    "integration",
    "mechanism",
    "complex",
    "synthesis",
    "evaluation",
}


def _clean_candidate(value: str) -> str:
    value = _BULLET_PREFIX.sub("", value.strip())
    value = _SECTION_PREFIX.sub("", value)
    value = value.strip(" \t:;-\u2013\u2014")
    value = _SPACE.sub(" ", value)
    return value


def _is_candidate(value: str) -> bool:
    if not 3 <= len(value) <= 120:
        return False
    lowered = value.casefold()
    if lowered.startswith(_METADATA_PREFIXES):
        return False
    if re.fullmatch(r"[\W\d_]+", value):
        return False
    return True


def _difficulty(name: str) -> Difficulty:
    words = set(re.findall(r"[a-z]+", name.casefold()))
    if words & _HARD_HINTS:
        return Difficulty.hard
    if words & _EASY_HINTS:
        return Difficulty.easy
    return Difficulty.medium


def _estimate(name: str, difficulty: Difficulty) -> int:
    base = {
        Difficulty.easy: 45,
        Difficulty.medium: 60,
        Difficulty.hard: 90,
    }[difficulty]
    if len(name.split()) >= 10:
        base += 15
    return base


class FallbackAnalyzer:
    """Extract headings and list items without network access or randomness."""

    def analyze(self, subject: str, text: str) -> list[Topic]:
        candidates: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            lowered = line.casefold()
            if lowered.startswith(("topics:", "units:", "modules:")):
                _, content = line.split(":", 1)
                candidates.extend(_clean_candidate(p) for p in re.split(r"[,;]", content))
                continue

            cleaned = _clean_candidate(line)
            if _is_candidate(cleaned):
                candidates.append(cleaned)

        # A pasted paragraph has no useful line structure. Sentences are a
        # better emergency split than treating the entire document as one topic.
        if len(candidates) <= 1:
            sentence_candidates = [
                _clean_candidate(sentence)
                for sentence in _SENTENCE.split(_SPACE.sub(" ", text.strip()))
            ]
            useful_sentences = [s.rstrip(".!?") for s in sentence_candidates if _is_candidate(s)]
            if len(useful_sentences) > len(candidates):
                candidates = useful_sentences

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.rstrip(".!?")
            key = candidate.casefold()
            if not _is_candidate(candidate) or key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
            if len(unique) == _MAX_TOPICS:
                break

        if not unique:
            clean_subject = _SPACE.sub(" ", subject.strip()) or "Course"
            unique = [f"{clean_subject} core concepts"]

        topics: list[Topic] = []
        for name in unique:
            difficulty = _difficulty(name)
            topics.append(
                Topic(
                    name=name,
                    difficulty=difficulty,
                    estimated_minutes=_estimate(name, difficulty),
                )
            )
        return topics
