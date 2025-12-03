"""Менеджер истории чата.

Классы:
    ChatHistoryManager
        Управляет историей сообщений с автоматическим триммингом.
"""

from typing import Optional, Literal

from semantic_core.interfaces.chat_history import BaseChatHistoryStrategy, ChatMessage
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class ChatHistoryManager:
    """Управляет историей чата с автоматическим триммингом.

    Хранит список сообщений и автоматически обрезает историю
    согласно выбранной стратегии при добавлении новых сообщений.

    Поддерживает стратегии со сжатием (AdaptiveWithCompression):
    метод get_messages_for_llm() автоматически добавляет summary.

    Attributes:
        strategy: Стратегия управления историей.
        messages: Текущий список сообщений.

    Example:
        >>> from semantic_core.core.context import LastNMessages
        >>> manager = ChatHistoryManager(LastNMessages(n=5))
        >>> manager.add("user", "Привет!", tokens=10)
        >>> manager.add("assistant", "Здравствуйте!", tokens=15)
        >>> history = manager.get_history()
    """

    def __init__(self, strategy: BaseChatHistoryStrategy):
        """Инициализация менеджера.

        Args:
            strategy: Стратегия управления историей.
        """
        self.strategy = strategy
        self._messages: list[ChatMessage] = []

        logger.debug(
            "ChatHistoryManager initialized",
            strategy=strategy.__class__.__name__,
        )

    def add(
        self,
        role: Literal["user", "assistant", "system"],
        content: str,
        tokens: int = 0,
    ) -> None:
        """Добавляет сообщение в историю.

        Автоматически обрезает историю если стратегия требует.

        Args:
            role: Роль отправителя.
            content: Текст сообщения.
            tokens: Количество токенов (для TokenBudget).
        """
        message = ChatMessage(role=role, content=content, tokens=tokens)
        self._messages.append(message)

        # Автотримминг
        if self.strategy.should_trim(self._messages):
            old_count = len(self._messages)
            self._messages = self.strategy.trim(self._messages)
            logger.debug(
                "History trimmed",
                old_count=old_count,
                new_count=len(self._messages),
                strategy=self.strategy.__class__.__name__,
            )

    def add_user(self, content: str, tokens: int = 0) -> None:
        """Добавляет сообщение пользователя."""
        self.add("user", content, tokens)

    def add_assistant(self, content: str, tokens: int = 0) -> None:
        """Добавляет сообщение ассистента."""
        self.add("assistant", content, tokens)

    def add_system(self, content: str, tokens: int = 0) -> None:
        """Добавляет системное сообщение."""
        self.add("system", content, tokens)

    def get_history(self) -> list[ChatMessage]:
        """Возвращает копию истории сообщений."""
        return self._messages.copy()

    def get_messages_for_llm(self) -> list[dict]:
        """Возвращает историю в формате для LLM API.

        Если стратегия поддерживает get_full_context() (например,
        AdaptiveWithCompression), включает summary в начало.

        Returns:
            Список словарей с role и content.
        """
        # Проверяем есть ли у стратегии get_full_context
        if hasattr(self.strategy, "get_full_context"):
            full_messages = self.strategy.get_full_context(self._messages)
            return [{"role": m.role, "content": m.content} for m in full_messages]

        return [{"role": m.role, "content": m.content} for m in self._messages]

    def clear(self) -> None:
        """Очищает историю сообщений."""
        count = len(self._messages)
        self._messages.clear()
        logger.debug("History cleared", cleared_count=count)

    def total_tokens(self) -> int:
        """Возвращает общее количество токенов в истории.

        Включает токены из summary, если стратегия его имеет.
        """
        total = sum(m.tokens for m in self._messages)

        # Добавляем токены summary если есть
        if hasattr(self.strategy, "summary") and self.strategy.summary:
            total += self.strategy.summary.tokens

        return total

    def __len__(self) -> int:
        """Количество сообщений в истории."""
        return len(self._messages)

    @property
    def is_empty(self) -> bool:
        """Пустая ли история."""
        return len(self._messages) == 0

    @property
    def has_summary(self) -> bool:
        """Есть ли сжатое summary в стратегии."""
        return hasattr(self.strategy, "summary") and self.strategy.summary is not None


__all__ = ["ChatHistoryManager"]
