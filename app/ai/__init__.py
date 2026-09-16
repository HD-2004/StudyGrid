"""Material analysis providers.

The rest of the application depends on :class:`MaterialAnalyzer`, not on a
specific model vendor. Provider failures are contained here so plan creation
continues to work with the deterministic fallback.
"""

from .fallback import FallbackAnalyzer
from .coach import (
    CoachProvider,
    CoachProviderError,
    CoachResult,
    FallbackCoach,
    OpenAICoachProvider,
    StudyCoach,
    build_coach_from_env,
)
from .openai import OpenAIProvider
from .provider import LLMProvider, LLMProviderError
from .service import AnalysisResult, MaterialAnalyzer, build_analyzer_from_env

__all__ = [
    "AnalysisResult",
    "CoachProvider",
    "CoachProviderError",
    "CoachResult",
    "FallbackAnalyzer",
    "FallbackCoach",
    "LLMProvider",
    "LLMProviderError",
    "MaterialAnalyzer",
    "OpenAIProvider",
    "OpenAICoachProvider",
    "StudyCoach",
    "build_analyzer_from_env",
    "build_coach_from_env",
]
