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


# Импортируем здесь чтобы избежать circular imports
# TYPE_CHECKING не работает с runtime imports
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from semantic_core.core.context.compressor import ContextCompressor


class AdaptiveWithCompression(BaseChatHistoryStrategy):
    """Сжимает историю при достижении порога токенов.

    Когда сумма токенов превышает threshold — запускает LLM summarization
    для старых сообщений, сохраняя последние в пределах target.

    Attributes:
        compressor: Компрессор для создания summary.
        threshold_tokens: Порог срабатывания сжатия.
        target_tokens: Целевое количество токенов после сжатия.
        summary: Текущее сжатое summary (если есть).

    Example:
        >>> compressor = ContextCompressor(llm)
        >>> strategy = AdaptiveWithCompression(
        ...     compressor,
        ...     threshold_tokens=30000,
        ...     target_tokens=10000,
        ... )
        >>> # При достижении 30k токенов → сжимает до ~10k + summary
    """

    def __init__(
        self,
        compressor: "ContextCompressor",
        threshold_tokens: int = 30000,
        target_tokens: int = 10000,
    ):
        """Инициализация стратегии.

        Args:
            compressor: Компрессор для создания summary.
            threshold_tokens: Порог срабатывания (по умолчанию 30k).
            target_tokens: Целевое количество токенов (по умолчанию 10k).

        Raises:
            ValueError: Если threshold <= target.
        """
        if threshold_tokens <= target_tokens:
            raise ValueError("threshold_tokens должен быть > target_tokens")
        if target_tokens < 1:
            raise ValueError("target_tokens должно быть >= 1")

        self.compressor = compressor
        self.threshold = threshold_tokens
        self.target = target_tokens
        self._summary: Optional[ChatMessage] = None

    @property
    def summary(self) -> Optional[ChatMessage]:
        """Текущее сжатое summary."""
        return self._summary

    def should_trim(self, messages: list[ChatMessage]) -> bool:
        """Проверяет, превышен ли порог токенов."""
        total = sum(m.tokens for m in messages)
        if self._summary:
            total += self._summary.tokens
        return total > self.threshold

    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Сжимает старые сообщения, оставляя новые.

        Алгоритм:
        1. Разделяет сообщения на to_compress и to_keep
        2. to_keep — последние сообщения в пределах target
        3. to_compress + старый summary → новый summary
        """
        # Разделяем: идём с конца, собираем пока не превысим target
        to_keep: list[ChatMessage] = []
        to_compress: list[ChatMessage] = []
        running_tokens = 0

        for msg in reversed(messages):
            if running_tokens + msg.tokens <= self.target:
                to_keep.insert(0, msg)
                running_tokens += msg.tokens
            else:
                to_compress.insert(0, msg)

        # Если нечего сжимать — просто возвращаем всё
        if not to_compress:
            return messages

        # Добавляем старый summary к сообщениям для сжатия
        compress_input = list(to_compress)
        if self._summary:
            compress_input.insert(0, self._summary)

        # Сжимаем через LLM
        self._summary = self.compressor.compress(compress_input)

        return to_keep

    def get_full_context(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Возвращает контекст с summary в начале.

        Args:
            messages: Текущие сообщения (после trim).

        Returns:
            Summary (если есть) + messages.
        """
        if self._summary:
            return [self._summary] + messages
        return messages


__all__ = ["LastNMessages", "TokenBudget", "Unlimited", "AdaptiveWithCompression"]
