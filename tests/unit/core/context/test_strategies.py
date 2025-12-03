"""Тесты для стратегий управления историей чата."""

import pytest

from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.core.context.strategies import (
    LastNMessages,
    TokenBudget,
    Unlimited,
)


class TestLastNMessages:
    """Тесты для стратегии LastNMessages."""

    def test_init_valid(self):
        """Инициализация с валидным n."""
        strategy = LastNMessages(n=5)
        assert strategy.n == 5

    def test_init_invalid_zero(self):
        """Ошибка при n=0."""
        with pytest.raises(ValueError, match="n должно быть >= 1"):
            LastNMessages(n=0)

    def test_init_invalid_negative(self):
        """Ошибка при отрицательном n."""
        with pytest.raises(ValueError, match="n должно быть >= 1"):
            LastNMessages(n=-1)

    def test_should_trim_under_limit(self):
        """Не требует обрезки если меньше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(3)]
        assert strategy.should_trim(messages) is False

    def test_should_trim_at_limit(self):
        """Не требует обрезки если ровно лимит."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(5)]
        assert strategy.should_trim(messages) is False

    def test_should_trim_over_limit(self):
        """Требует обрезки если больше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(7)]
        assert strategy.should_trim(messages) is True

    def test_trim_keeps_last_n(self):
        """Обрезка оставляет N последних сообщений."""
        strategy = LastNMessages(n=3)
        messages = [ChatMessage("user", f"msg{i}") for i in range(5)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 3
        assert trimmed[0].content == "msg2"
        assert trimmed[1].content == "msg3"
        assert trimmed[2].content == "msg4"

    def test_trim_no_change_under_limit(self):
        """Обрезка не меняет если меньше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(3)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 3
        assert trimmed == messages


class TestTokenBudget:
    """Тесты для стратегии TokenBudget."""

    def test_init_valid(self):
        """Инициализация с валидным бюджетом."""
        strategy = TokenBudget(max_tokens=1000)
        assert strategy.max_tokens == 1000

    def test_init_invalid_zero(self):
        """Ошибка при max_tokens=0."""
        with pytest.raises(ValueError, match="max_tokens должно быть >= 1"):
            TokenBudget(max_tokens=0)

    def test_init_invalid_negative(self):
        """Ошибка при отрицательном бюджете."""
        with pytest.raises(ValueError, match="max_tokens должно быть >= 1"):
            TokenBudget(max_tokens=-100)

    def test_should_trim_under_budget(self):
        """Не требует обрезки если меньше бюджета."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=20),
            ChatMessage("assistant", "msg2", tokens=30),
        ]
        assert strategy.should_trim(messages) is False

    def test_should_trim_at_budget(self):
        """Не требует обрезки если ровно бюджет."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=50),
            ChatMessage("assistant", "msg2", tokens=50),
        ]
        assert strategy.should_trim(messages) is False

    def test_should_trim_over_budget(self):
        """Требует обрезки если больше бюджета."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=60),
            ChatMessage("assistant", "msg2", tokens=60),
        ]
        assert strategy.should_trim(messages) is True

    def test_trim_removes_old_messages(self):
        """Обрезка удаляет старые сообщения."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "old1", tokens=40),
            ChatMessage("assistant", "old2", tokens=40),
            ChatMessage("user", "new1", tokens=30),
            ChatMessage("assistant", "new2", tokens=30),
        ]

        trimmed = strategy.trim(messages)

        # Должны остаться последние 2-3 сообщения (30+30+30 = 90 < 100)
        assert len(trimmed) <= 3
        assert sum(m.tokens for m in trimmed) <= 100
        # Последнее сообщение должно быть new2
        assert trimmed[-1].content == "new2"

    def test_trim_no_change_under_budget(self):
        """Обрезка не меняет если меньше бюджета."""
        strategy = TokenBudget(max_tokens=1000)
        messages = [
            ChatMessage("user", "msg1", tokens=100),
            ChatMessage("assistant", "msg2", tokens=100),
        ]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 2
        assert trimmed == messages

    def test_trim_handles_single_large_message(self):
        """Обрезка справляется с одним большим сообщением."""
        strategy = TokenBudget(max_tokens=50)
        messages = [
            ChatMessage("user", "huge", tokens=100),  # Больше бюджета
        ]

        trimmed = strategy.trim(messages)

        # Не можем удалить последнее сообщение, возвращаем пустой список
        assert len(trimmed) == 0


class TestUnlimited:
    """Тесты для стратегии Unlimited."""

    def test_should_trim_always_false(self):
        """Никогда не требует обрезки."""
        strategy = Unlimited()
        messages = [ChatMessage("user", f"msg{i}") for i in range(1000)]
        assert strategy.should_trim(messages) is False

    def test_trim_no_change(self):
        """Обрезка не меняет список."""
        strategy = Unlimited()
        messages = [ChatMessage("user", f"msg{i}") for i in range(100)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 100
        assert trimmed == messages

    def test_trim_empty_list(self):
        """Обрезка работает с пустым списком."""
        strategy = Unlimited()
        trimmed = strategy.trim([])
        assert trimmed == []
