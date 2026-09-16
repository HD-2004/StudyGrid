"""Material analysis providers.

The rest of the application depends on :class:`MaterialAnalyzer`, not on a
specific model vendor. Provider failures are contained here so plan creation
continues to work with the deterministic fallback.
"""

from .fallback import FallbackAnalyzer
from .openai import OpenAIProvider
from .provider import LLMProvider, LLMProviderError
from .service import AnalysisResult, MaterialAnalyzer, build_analyzer_from_env

__all__ = [
    "AnalysisResult",
    "FallbackAnalyzer",
    "LLMProvider",
    "LLMProviderError",
    "MaterialAnalyzer",
    "OpenAIProvider",
    "build_analyzer_from_env",
]
