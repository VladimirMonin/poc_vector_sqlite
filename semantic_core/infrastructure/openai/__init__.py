"""Модуль интеграции с OpenAI API.

Этот модуль предоставляет адаптер для работы с OpenAI LLM API.

Классы:
    OpenAILLMProvider
        Провайдер для генерации ответов через OpenAI API.
"""

from semantic_core.infrastructure.openai.llm import OpenAILLMProvider

__all__ = [
    "OpenAILLMProvider",
]
