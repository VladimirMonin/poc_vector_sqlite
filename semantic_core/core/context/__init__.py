"""Модуль управления контекстом чата.

Классы:
    LastNMessages
        Хранит N последних сообщений.
    TokenBudget
        Ограничивает по токенам.
    Unlimited
        Без ограничений.
    AdaptiveWithCompression
        Сжимает через LLM при достижении порога.
    ChatHistoryManager
        Менеджер истории с автотриммингом.
    ContextCompressor
        Сжимает историю через LLM summarization.
"""

from semantic_core.core.context.strategies import (
    LastNMessages,
    TokenBudget,
    Unlimited,
    AdaptiveWithCompression,
)
from semantic_core.core.context.manager import ChatHistoryManager
from semantic_core.core.context.compressor import ContextCompressor

__all__ = [
    "LastNMessages",
    "TokenBudget",
    "Unlimited",
    "AdaptiveWithCompression",
    "ChatHistoryManager",
    "ContextCompressor",
]
