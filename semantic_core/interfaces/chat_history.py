"""Интерфейсы для управления историей чата.

Классы:
    ChatMessage
        DTO сообщения в истории чата.
    BaseChatHistoryStrategy
        Абстрактная стратегия управления историей.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class ChatMessage:
    """Сообщение в истории чата.

    Attributes:
        role: Роль отправителя (user/assistant/system).
        content: Текст сообщения.
        tokens: Количество токенов (0 если неизвестно).
    """

    role: Literal["user", "assistant", "system"]
    content: str
    tokens: int = 0


class BaseChatHistoryStrategy(ABC):
    """Абстрактная стратегия управления историей чата.

    Определяет, когда и как обрезать историю сообщений.
    Реализации могут ограничивать по количеству сообщений,
    токенам или другим критериям.
    """

    @abstractmethod
    def should_trim(self, messages: list[ChatMessage]) -> bool:
        """Проверяет, нужно ли обрезать историю.

        Args:
            messages: Текущий список сообщений.

        Returns:
            True если история превышает лимит.
        """
        pass

    @abstractmethod
    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Обрезает историю согласно стратегии.

        Args:
            messages: Текущий список сообщений.

        Returns:
            Обрезанный список сообщений.
        """
        pass


__all__ = ["ChatMessage", "BaseChatHistoryStrategy"]
