"""Адаптеры для различных AI-провайдеров.

Модули:
    embedder
        Реализация BaseEmbedder для Google Gemini API.
    batching
        Клиент для работы с Google Batch API.
"""

from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
from semantic_core.infrastructure.gemini.batching import GeminiBatchClient

__all__ = ["GeminiEmbedder", "GeminiBatchClient"]
