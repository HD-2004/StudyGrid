"""Offline checks for the plan-aware Study Coach."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import (  # noqa: E402
    CoachProviderError,
    OpenAICoachProvider,
    StudyCoach,
)
from app.models import ChatMessage, ChatRole, StudyPlan, StudySession  # noqa: E402


PLAN = StudyPlan(
    sessions=[
        StudySession(
            subject="Linear Algebra",
            topic="Vectors",
            start=datetime(2026, 9, 21, 9, 0),
            end=datetime(2026, 9, 21, 10, 0),
            rationale="priority 5/5, prerequisite for Eigenvalues",
        ),
        StudySession(
            subject="Biology",
            topic="Cell division",
            start=datetime(2026, 9, 21, 10, 6),
            end=datetime(2026, 9, 21, 11, 6),
            rationale="priority 3/5, interleaved across subjects",
        ),
    ],
    summary="2 first-pass sessions",
)


fallback = StudyCoach()
result = fallback.reply(PLAN, [], "What should I study next?")
assert result.source == "fallback"
assert "Vectors" in result.text and "60 minutes" in result.text

vietnamese = fallback.reply(PLAN, [], "Tôi còn lại bao nhiêu giờ học?")
assert "2 buổi" in vietnamese.text and "2.0 giờ" in vietnamese.text

focused = fallback.reply(PLAN, [], "Tại sao lại học phần này?", PLAN.sessions[0])
assert "priority 5/5" in focused.text
print("[ok] deterministic coach answers plan, workload, and focused-session questions")


class FakeProvider:
    def reply(
        self,
        plan_context: str,
        history: list[ChatMessage],
        message: str,
    ) -> str:
        assert "Linear Algebra" in plan_context
        assert history[0].content == "Earlier question"
        assert message == "What now?"
        return "Start with the scheduled Vectors retrieval."


ai_coach = StudyCoach(provider=FakeProvider())
ai_result = ai_coach.reply(
    PLAN,
    [ChatMessage(role=ChatRole.user, content="Earlier question")],
    "What now?",
)
assert ai_result.source == "ai" and "Vectors" in ai_result.text
print("[ok] provider receives bounded conversation and serialized plan context")


class BrokenProvider:
    def reply(
        self,
        plan_context: str,
        history: list[ChatMessage],
        message: str,
    ) -> str:
        raise RuntimeError("simulated outage")


logging.disable(logging.CRITICAL)
outage = StudyCoach(provider=BrokenProvider()).reply(PLAN, [], "What is next?")
logging.disable(logging.NOTSET)
assert outage.source == "fallback" and "Vectors" in outage.text
print("[ok] provider outage falls back without losing plan context")


class FakeResponses:
    def create(self, **kwargs: object) -> SimpleNamespace:
        assert kwargs["model"] == "test-model"
        assert kwargs["max_output_tokens"] == 400
        inputs = kwargs["input"]
        assert any("PLAN CONTEXT" in item["content"] for item in inputs)
        return SimpleNamespace(output_text="Use the next scheduled retrieval.")


class FakeOpenAIClient:
    responses = FakeResponses()


provider = OpenAICoachProvider(
    api_key="test-key",
    model="test-model",
    client=FakeOpenAIClient(),
)
reply = provider.reply("{}", [], "What now?")
assert reply == "Use the next scheduled retrieval."
print("[ok] OpenAI Responses request is bounded and parsed")


class EmptyResponses:
    def create(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(output_text=None)


class EmptyOpenAIClient:
    responses = EmptyResponses()


try:
    OpenAICoachProvider(
        api_key="test-key",
        model="test-model",
        client=EmptyOpenAIClient(),
    ).reply("{}", [], "What now?")
except CoachProviderError:
    pass
else:
    raise AssertionError("empty coach output must fail closed")
print("[ok] empty provider output is rejected")

print("\ncoach smoke passed")
