"""Модуль управления контекстом чата.

Классы:
    LastNMessages
        Хранит N последних сообщений.
    TokenBudget
        Ограничивает по токенам.
    Unlimited
        Без ограничений.
    ChatHistoryManager
        Менеджер истории с автотриммингом.
"""

from semantic_core.core.context.strategies import LastNMessages, TokenBudget, Unlimited
from semantic_core.core.context.manager import ChatHistoryManager

__all__ = ["LastNMessages", "TokenBudget", "Unlimited", "ChatHistoryManager"]
