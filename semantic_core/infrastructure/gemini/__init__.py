"""Адаптеры для различных AI-провайдеров.

Модули:
    embedder
        Реализация BaseEmbedder для Google Gemini API.
    batching
        Клиент для работы с Google Batch API.
    image_analyzer
        Анализатор изображений через Gemini Vision API.
    audio_analyzer
        Анализатор аудио через Gemini API (Phase 6.2).
    video_analyzer
        Мультимодальный анализатор видео (Phase 6.2).
    resilience
        Retry-декораторы и обработка ошибок.
    rate_limiter
        Rate Limiter для API-вызовов.
"""

from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
from semantic_core.infrastructure.gemini.batching import GeminiBatchClient
from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer
from semantic_core.infrastructure.gemini.resilience import (
    MediaProcessingError,
    retry_with_backoff,
)
from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter

__all__ = [
    "GeminiEmbedder",
    "GeminiBatchClient",
    "GeminiImageAnalyzer",
    "GeminiAudioAnalyzer",
    "GeminiVideoAnalyzer",
    "MediaProcessingError",
    "retry_with_backoff",
    "RateLimiter",
]
