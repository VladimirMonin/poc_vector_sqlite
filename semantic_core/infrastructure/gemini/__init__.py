"""Адаптеры для различных AI-провайдеров.

Модули:
    embedder
        Реализация BaseEmbedder для Google Gemini API.
"""

from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder

__all__ = ["GeminiEmbedder"]
