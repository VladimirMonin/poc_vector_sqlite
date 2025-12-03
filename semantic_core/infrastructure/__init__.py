"""Реализации инфраструктурных компонентов.

Модули:
    gemini
        Адаптеры для Google Gemini API.
    llm
        Провайдеры LLM для генерации текста.
    storage
        Адаптеры для хранилищ данных.
    text_processing
        Реализации обработки текста.
"""

from semantic_core.infrastructure.gemini import GeminiEmbedder
from semantic_core.infrastructure.llm import GeminiLLMProvider
from semantic_core.infrastructure.storage import (
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.infrastructure.text_processing import (
    SimpleSplitter,
    BasicContextStrategy,
)

__all__ = [
    # Gemini
    "GeminiEmbedder",
    # LLM
    "GeminiLLMProvider",
    # Storage
    "PeeweeVectorStore",
    "init_peewee_database",
    # Text Processing
    "SimpleSplitter",
    "BasicContextStrategy",
]
