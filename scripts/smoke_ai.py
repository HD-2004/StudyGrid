"""Offline checks for AI analysis. Run: python scripts/smoke_ai.py"""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import (  # noqa: E402
    LLMProviderError,
    MaterialAnalyzer,
    OpenAIProvider,
)
from app.models import Difficulty, Topic  # noqa: E402


class FakeProvider:
    def analyze(self, subject: str, text: str) -> list[Topic]:
        return [
            Topic(name=" Vectors ", difficulty=Difficulty.easy, estimated_minutes=45),
            Topic(
                name="Eigenvalues",
                difficulty=Difficulty.hard,
                estimated_minutes=90,
                depends_on=["vectors", "Unknown topic", "Eigenvalues"],
            ),
            Topic(name="vectors", difficulty=Difficulty.medium, estimated_minutes=60),
        ]


class BrokenProvider:
    def analyze(self, subject: str, text: str) -> list[Topic]:
        raise LLMProviderError("simulated outage")


syllabus = """Topics: Introduction to cells, Cell division, Advanced gene regulation
Assessment: final exam
"""

fallback = MaterialAnalyzer()
first = fallback.analyze("Biology", syllabus)
second = fallback.analyze("Biology", syllabus)
assert first.source == "fallback"
assert first.topics == second.topics, "fallback must be deterministic"
assert [topic.name for topic in first.topics] == [
    "Introduction to cells",
    "Cell division",
    "Advanced gene regulation",
]
print("[ok] deterministic fallback")

ai_result = MaterialAnalyzer(provider=FakeProvider()).analyze("Math", "ignored")
assert ai_result.source == "ai"
assert [topic.name for topic in ai_result.topics] == ["Vectors", "Eigenvalues"]
assert ai_result.topics[1].depends_on == ["Vectors"]
print("[ok] provider output normalized")

logging.disable(logging.CRITICAL)
outage_result = MaterialAnalyzer(provider=BrokenProvider()).analyze("Biology", syllabus)
logging.disable(logging.NOTSET)
assert outage_result.source == "fallback"
assert outage_result.topics
print("[ok] provider outage falls back")


class FakeResponses:
    def parse(self, **kwargs: object) -> SimpleNamespace:
        assert kwargs["model"] == "test-model"
        assert kwargs["reasoning"] == {"effort": "low"}
        topic_batch = kwargs["text_format"]
        parsed = topic_batch.model_validate(
            {
                "topics": [
                    {
                        "name": "Cell division",
                        "difficulty": "medium",
                        "estimated_minutes": 60,
                        "depends_on": [],
                    }
                ]
            }
        )
        return SimpleNamespace(output_parsed=parsed)


class FakeOpenAIClient:
    responses = FakeResponses()


provider = OpenAIProvider(
    api_key="test-key",
    model="test-model",
    client=FakeOpenAIClient(),
)
topics = provider.analyze("Biology", "Cell division")
assert len(topics) == 1 and topics[0].name == "Cell division"
print("[ok] OpenAI structured response parsed")


class MalformedResponses:
    def parse(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(output_parsed=None)


class MalformedOpenAIClient:
    responses = MalformedResponses()


malformed_provider = OpenAIProvider(
    api_key="test-key",
    model="test-model",
    client=MalformedOpenAIClient(),
)
try:
    malformed_provider.analyze("Biology", "Cell division")
except LLMProviderError:
    pass
else:
    raise AssertionError("malformed provider output must fail closed")
print("[ok] malformed provider output rejected")

print("\nai smoke passed")
