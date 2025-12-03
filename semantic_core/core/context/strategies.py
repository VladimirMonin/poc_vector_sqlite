"""Стратегии управления историей чата.

Реализации BaseChatHistoryStrategy для разных сценариев:
- LastNMessages: хранить N последних сообщений
- TokenBudget: ограничение по токенам
- Unlimited: без ограничений

Классы:
    LastNMessages
        Хранит только N последних сообщений.
    TokenBudget
        Ограничивает историю по общему количеству токенов.
    Unlimited
        Без ограничений (осторожно!).
"""

from semantic_core.interfaces.chat_history import BaseChatHistoryStrategy, ChatMessage


class LastNMessages(BaseChatHistoryStrategy):
    """Хранит только N последних сообщений.

    Самая простая стратегия: при превышении лимита
    отбрасывает старые сообщения с начала списка.

    Attributes:
        n: Максимальное количество сообщений.

    Example:
        >>> strategy = LastNMessages(n=10)
        >>> messages = [ChatMessage("user", "msg")] * 15
        >>> strategy.should_trim(messages)  # True
        >>> trimmed = strategy.trim(messages)
        >>> len(trimmed)  # 10
    """

    def __init__(self, n: int = 10):
        """Инициализация стратегии.

        Args:
            n: Максимальное количество сообщений (по умолчанию 10).

        Raises:
            ValueError: Если n < 1.
        """
        if n < 1:
            raise ValueError("n должно быть >= 1")
        self.n = n

    def should_trim(self, messages: list[ChatMessage]) -> bool:
        """Проверяет, превышен ли лимит сообщений."""
        return len(messages) > self.n

    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Оставляет только N последних сообщений."""
        if len(messages) <= self.n:
            return messages
        return messages[-self.n :]


class TokenBudget(BaseChatHistoryStrategy):
    """Ограничивает историю по общему количеству токенов.

    При превышении бюджета удаляет старые сообщения,
    пока сумма токенов не уложится в лимит.

    Attributes:
        max_tokens: Максимальный бюджет токенов.

    Example:
        >>> strategy = TokenBudget(max_tokens=1000)
        >>> # При добавлении сообщений с большим числом токенов
        >>> # старые сообщения будут удаляться
    """

    def __init__(self, max_tokens: int = 50000):
        """Инициализация стратегии.

        Args:
            max_tokens: Максимальный бюджет токенов (по умолчанию 50000).

        Raises:
            ValueError: Если max_tokens < 1.
        """
        if max_tokens < 1:
            raise ValueError("max_tokens должно быть >= 1")
        self.max_tokens = max_tokens

    def should_trim(self, messages: list[ChatMessage]) -> bool:
        """Проверяет, превышен ли бюджет токенов."""
        return sum(m.tokens for m in messages) > self.max_tokens

    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Удаляет старые сообщения до соблюдения бюджета.

        Идёт с конца (новые сообщения), добавляя пока
        не превысится бюджет.
        """
        total = sum(m.tokens for m in messages)
        if total <= self.max_tokens:
            return messages

        # Идём с конца, собираем сообщения пока влезают
        result: list[ChatMessage] = []
        current_budget = 0

        for msg in reversed(messages):
            if current_budget + msg.tokens > self.max_tokens:
                break
            result.insert(0, msg)
            current_budget += msg.tokens

        return result


class Unlimited(BaseChatHistoryStrategy):
    """Без ограничений — хранит всю историю.

    ⚠️ ОСТОРОЖНО: может привести к переполнению контекста LLM.
    Используйте только для коротких сессий или тестирования.

    Example:
        >>> strategy = Unlimited()
        >>> strategy.should_trim(messages)  # Всегда False
    """

    def should_trim(self, messages: list[ChatMessage]) -> bool:
        """Никогда не требует обрезки."""
        return False

    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Возвращает список без изменений."""
        return messages


__all__ = ["LastNMessages", "TokenBudget", "Unlimited"]
